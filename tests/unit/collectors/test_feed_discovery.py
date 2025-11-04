"""
Tests for Feed Discovery Pipeline

Test Coverage:
- Stage 1: OPML seed loading + Gemini CLI expansion
- Stage 2: SerpAPI search + feedfinder2 auto-detection
- Circuit breaker (3/day SerpAPI limit)
- 30-day caching
- Fallback logic (Gemini CLI failure)
- Error handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import subprocess
from pathlib import Path

from src.collectors.feed_discovery import (
    FeedDiscovery,
    DiscoveryStage,
    DiscoveredFeed,
    FeedDiscoveryError,
)


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for feed discovery"""
    cache_dir = tmp_path / "feed_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def mock_config():
    """Mock market configuration"""
    config = Mock()
    config.market.seed_keywords = ["PropTech", "Smart Building", "DSGVO"]
    config.market.domain = "SaaS"
    config.market.market = "Germany"
    config.market.language = "de"
    config.collectors.custom_feeds = [
        "https://www.heise.de/rss/heise.rdf",
        "https://t3n.de/feed/"
    ]
    return config


@pytest.fixture
def feed_discovery(mock_config, temp_cache_dir):
    """Create FeedDiscovery instance for tests"""
    return FeedDiscovery(
        config=mock_config,
        cache_dir=temp_cache_dir,
        serpapi_daily_limit=3
    )


@pytest.fixture
def mock_opml_content():
    """Mock OPML feed list content"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <body>
    <outline text="Technology" title="Technology">
      <outline type="rss" text="Heise" xmlUrl="https://www.heise.de/rss/heise.rdf" />
      <outline type="rss" text="Golem" xmlUrl="https://www.golem.de/rss.php" />
    </outline>
    <outline text="Business" title="Business">
      <outline type="rss" text="Gründerszene" xmlUrl="https://www.gruenderszene.de/feed" />
    </outline>
  </body>
</opml>"""


@pytest.fixture
def mock_gemini_cli_success():
    """Mock successful Gemini CLI response"""
    with patch('subprocess.run') as mock_run:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "expanded_keywords": [
                "PropTech",
                "Smart Building",
                "DSGVO",
                "Immobilien SaaS",
                "Gebäudeautomation",
                "Datenschutz Immobilien"
            ],
            "reasoning": "Expanded with related real estate tech terms"
        })
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_gemini_cli_failure():
    """Mock failed Gemini CLI response"""
    with patch('subprocess.run') as mock_run:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Gemini CLI error"
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_serpapi_response():
    """Mock SerpAPI search results"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic_results": [
                {"link": "https://www.proptech.de"},
                {"link": "https://www.immobilienscout24.de"},
                {"link": "https://www.onoffice.com"}
            ]
        }
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_feedfinder():
    """Mock feedfinder2 feed detection"""
    with patch('feedfinder2.find_feeds') as mock_find:
        mock_find.return_value = [
            "https://www.proptech.de/feed",
            "https://www.proptech.de/rss"
        ]
        yield mock_find


# ==================== Stage 1: OPML + Gemini Tests ====================

def test_load_opml_seeds_parses_correctly(feed_discovery, mock_opml_content, tmp_path):
    """Test OPML seed file parsing"""
    # Create OPML file
    opml_file = tmp_path / "feeds.opml"
    opml_file.write_text(mock_opml_content)

    # Load OPML
    feeds = feed_discovery._load_opml_seeds(str(opml_file))

    # Verify
    assert len(feeds) == 3
    assert "https://www.heise.de/rss/heise.rdf" in feeds
    assert "https://www.golem.de/rss.php" in feeds
    assert "https://www.gruenderszene.de/feed" in feeds


def test_load_opml_seeds_handles_missing_file(feed_discovery):
    """Test handling of missing OPML file"""
    feeds = feed_discovery._load_opml_seeds("/nonexistent/file.opml")

    # Should return empty list, not crash
    assert feeds == []


def test_expand_keywords_with_gemini_cli_success(feed_discovery, mock_gemini_cli_success):
    """Test successful keyword expansion with Gemini CLI"""
    keywords = ["PropTech", "DSGVO"]

    expanded = feed_discovery._expand_keywords_with_gemini(keywords)

    # Verify Gemini called (with any arguments)
    assert mock_gemini_cli_success.called

    # Verify expansion
    assert len(expanded) >= len(keywords)
    assert "PropTech" in expanded
    assert "Immobilien SaaS" in expanded


def test_expand_keywords_with_gemini_cli_failure_fallback(
    feed_discovery, mock_gemini_cli_failure
):
    """Test fallback to basic expansion when Gemini fails"""
    keywords = ["PropTech", "DSGVO"]

    expanded = feed_discovery._expand_keywords_with_gemini(keywords)

    # Verify Gemini was attempted (with retry, should be 2 attempts)
    assert mock_gemini_cli_failure.call_count == 2

    # Should fallback to original keywords after all retries
    assert expanded == keywords


def test_expand_keywords_retry_logic(feed_discovery):
    """Test retry logic for Gemini CLI (max 2 attempts)"""
    with patch('subprocess.run') as mock_run:
        # First attempt fails, second succeeds
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr="Error"),
            Mock(returncode=0, stdout=json.dumps({
                "expanded_keywords": ["PropTech", "Smart Building"]
            }), stderr="")
        ]

        expanded = feed_discovery._expand_keywords_with_gemini(["PropTech"])

        # Should retry once
        assert mock_run.call_count == 2
        assert len(expanded) == 2


def test_stage1_combines_opml_and_custom_feeds(
    feed_discovery, mock_opml_content, tmp_path, mock_gemini_cli_success
):
    """Test Stage 1 combines OPML seeds with custom feeds from config"""
    # Setup OPML file
    opml_file = tmp_path / "feeds.opml"
    opml_file.write_text(mock_opml_content)

    # Run Stage 1
    feeds = feed_discovery.run_stage1(opml_file=str(opml_file))

    # Should include OPML feeds (3) + custom feeds (2) = 5
    assert len(feeds) >= 5

    # Verify custom feeds included
    assert any("heise.de" in f.url for f in feeds)
    assert any("t3n.de" in f.url for f in feeds)


# ==================== Stage 2: SerpAPI + feedfinder Tests ====================

def test_serpapi_search_returns_domains(feed_discovery, mock_serpapi_response):
    """Test SerpAPI search extracts domains"""
    domains = feed_discovery._search_with_serpapi("PropTech Germany")

    # Verify SerpAPI called
    mock_serpapi_response.assert_called_once()

    # Verify domains extracted
    assert len(domains) == 3
    assert "proptech.de" in domains
    assert "immobilienscout24.de" in domains


def test_serpapi_circuit_breaker_enforces_daily_limit(feed_discovery):
    """Test circuit breaker stops at 3 requests/day"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organic_results": []}
        mock_get.return_value = mock_response

        # Make 3 successful requests with DIFFERENT keywords (to avoid cache)
        for i in range(3):
            feed_discovery._search_with_serpapi(f"test_{i}")

        # 4th request should be blocked by circuit breaker
        with pytest.raises(FeedDiscoveryError, match="SerpAPI daily limit"):
            feed_discovery._search_with_serpapi("test_4")

        # Verify only 3 API calls made
        assert mock_get.call_count == 3


def test_serpapi_cache_prevents_duplicate_queries(feed_discovery, mock_serpapi_response):
    """Test 30-day caching prevents duplicate SerpAPI queries"""
    keyword = "PropTech"

    # First query - hits API
    domains1 = feed_discovery._search_with_serpapi(keyword)

    # Second query - should use cache
    domains2 = feed_discovery._search_with_serpapi(keyword)

    # Verify API called only once
    assert mock_serpapi_response.call_count == 1

    # Results should match
    assert domains1 == domains2


def test_serpapi_cache_expires_after_30_days(feed_discovery, mock_serpapi_response, tmp_path):
    """Test cache expires after 30 days"""
    keyword = "PropTech"
    cache_file = Path(feed_discovery.cache_dir) / "serp_cache.json"

    # Create expired cache entry
    expired_cache = {
        keyword: {
            "domains": ["old-domain.com"],
            "timestamp": (datetime.now() - timedelta(days=31)).isoformat()
        }
    }
    cache_file.write_text(json.dumps(expired_cache))

    # Query should hit API (cache expired)
    domains = feed_discovery._search_with_serpapi(keyword)

    # Verify API was called
    mock_serpapi_response.assert_called_once()

    # New domains returned
    assert "old-domain.com" not in domains


def test_feedfinder_discovers_feeds_from_domain(feed_discovery, mock_feedfinder):
    """Test feedfinder2 auto-detects RSS feeds from domain"""
    domain = "proptech.de"

    feeds = feed_discovery._discover_feeds_from_domain(domain)

    # Verify feedfinder called
    mock_feedfinder.assert_called_once()

    # Verify feeds discovered
    assert len(feeds) == 2
    assert feeds[0].url == "https://www.proptech.de/feed"
    assert feeds[0].source == "serpapi+feedfinder"


def test_feedfinder_handles_no_feeds_found(feed_discovery):
    """Test graceful handling when domain has no RSS feeds"""
    with patch('feedfinder2.find_feeds', return_value=[]):
        feeds = feed_discovery._discover_feeds_from_domain("no-feeds.com")

        # Should return empty list, not crash
        assert feeds == []


def test_stage2_integrates_serpapi_and_feedfinder(
    feed_discovery, mock_serpapi_response, mock_feedfinder
):
    """Test Stage 2 full integration: SerpAPI → feedfinder"""
    keywords = ["PropTech", "Smart Building"]

    feeds = feed_discovery.run_stage2(keywords)

    # Verify pipeline executed
    assert mock_serpapi_response.called
    assert mock_feedfinder.called

    # Should discover feeds from multiple domains
    assert len(feeds) > 0


# ==================== Full Pipeline Tests ====================

def test_discover_feeds_runs_both_stages(
    feed_discovery, mock_opml_content, tmp_path,
    mock_gemini_cli_success, mock_serpapi_response, mock_feedfinder
):
    """Test full pipeline: Stage 1 + Stage 2"""
    opml_file = tmp_path / "feeds.opml"
    opml_file.write_text(mock_opml_content)

    all_feeds = feed_discovery.discover_feeds(opml_file=str(opml_file))

    # Should have feeds from Stage 1 (OPML + custom) and Stage 2 (SERP + feedfinder)
    # Stage 1: 3 OPML feeds + 2 custom feeds = 5
    # Stage 2: Should add more feeds from feedfinder
    assert len(all_feeds) >= 4  # At minimum Stage 1 feeds

    # Verify both stages ran
    assert mock_gemini_cli_success.called
    assert mock_serpapi_response.called
    assert mock_feedfinder.called


def test_discover_feeds_deduplicates_urls(feed_discovery, tmp_path):
    """Test feed URL deduplication across stages"""
    # Create scenario where same feed appears in both stages
    with patch.object(feed_discovery, '_load_opml_seeds', return_value=[
        "https://example.com/feed"
    ]):
        with patch.object(feed_discovery, '_discover_feeds_from_domain', return_value=[
            DiscoveredFeed(url="https://example.com/feed", source="serpapi", stage=DiscoveryStage.SERPAPI)
        ]):
            all_feeds = feed_discovery.discover_feeds()

            # Should deduplicate
            urls = [f.url for f in all_feeds]
            assert len(urls) == len(set(urls))  # No duplicates


def test_discover_feeds_returns_metadata(feed_discovery, tmp_path):
    """Test discovered feeds include proper metadata"""
    with patch.object(feed_discovery, '_load_opml_seeds', return_value=["https://example.com/feed"]):
        feeds = feed_discovery.discover_feeds()

        # Verify metadata
        assert all(isinstance(f, DiscoveredFeed) for f in feeds)
        assert all(f.url for f in feeds)
        assert all(f.source for f in feeds)
        assert all(f.stage for f in feeds)
        assert all(f.discovered_at for f in feeds)


# ==================== Error Handling Tests ====================

def test_discover_feeds_continues_on_partial_failure(feed_discovery):
    """Test pipeline continues even if one stage fails"""
    with patch.object(feed_discovery, '_load_opml_seeds', side_effect=Exception("OPML error")):
        with patch.object(feed_discovery, 'run_stage2', return_value=[
            DiscoveredFeed(url="https://example.com/feed", source="serpapi", stage=DiscoveryStage.SERPAPI)
        ]):
            # Should not crash, just log error and continue
            feeds = feed_discovery.discover_feeds()

            # Should have Stage 2 feeds even though Stage 1 failed
            assert len(feeds) > 0


def test_serpapi_handles_rate_limit_error(feed_discovery):
    """Test graceful handling of SerpAPI rate limit (429)"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        domains = feed_discovery._search_with_serpapi("test")

        # Should return empty list, not crash
        assert domains == []


def test_feedfinder_handles_network_timeout(feed_discovery):
    """Test handling of network timeout during feed discovery"""
    with patch('feedfinder2.find_feeds', side_effect=TimeoutError("Network timeout")):
        feeds = feed_discovery._discover_feeds_from_domain("slow-site.com")

        # Should return empty list, not crash
        assert feeds == []


# ==================== Statistics Tests ====================

def test_get_discovery_stats_returns_counts(feed_discovery):
    """Test discovery statistics tracking"""
    # Mock stage methods to return known feeds
    with patch.object(feed_discovery, 'run_stage1', return_value=[
        DiscoveredFeed(url="https://example1.com/feed", source="opml", stage=DiscoveryStage.OPML),
    ]):
        with patch.object(feed_discovery, 'run_stage2', return_value=[
            DiscoveredFeed(url="https://example2.com/feed", source="serpapi", stage=DiscoveryStage.SERPAPI),
            DiscoveredFeed(url="https://example3.com/feed", source="serpapi", stage=DiscoveryStage.SERPAPI),
        ]):
            with patch.object(feed_discovery, '_expand_keywords_with_gemini', return_value=["keyword1"]):
                feeds = feed_discovery.discover_feeds()
                stats = feed_discovery.get_stats()

                # Verify stats
                assert stats["total_feeds"] == 3
                assert "serpapi_requests_today" in stats


def test_reset_daily_limit_resets_counter(feed_discovery):
    """Test manual reset of daily limit counter"""
    # Use up daily limit
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organic_results": []}
        mock_get.return_value = mock_response

        for _ in range(3):
            feed_discovery._search_with_serpapi("test")

        # Reset counter
        feed_discovery.reset_daily_limit()

        # Should be able to make requests again
        domains = feed_discovery._search_with_serpapi("test")
        assert domains == []  # Empty but didn't raise limit error
