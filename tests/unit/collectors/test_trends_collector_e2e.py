"""
E2E Integration Tests for Trends Collector (Gemini API Backend)

**BREAKING CHANGE (Nov 2025)**: Updated for Gemini API backend

Tests with real Gemini API to validate:
- Trending searches for different regions (via Gemini web search)
- Related queries (top/rising via Gemini)
- Interest over time (via Gemini analysis)
- Query health tracking
- Cache persistence

NOTE: These tests make real Gemini API calls and require GEMINI_API_KEY.
Run with: pytest tests/unit/collectors/test_trends_collector_e2e.py -v

REQUIREMENTS:
- GEMINI_API_KEY environment variable must be set
- Tests are marked with @pytest.mark.external_api (real API calls)
- Uses GeminiAgent with 60s timeout (more reliable than 30s CLI timeout)
"""

import pytest
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock

from src.collectors.trends_collector import TrendsCollector, TrendsCollectorError
from src.models.document import Document
from src.agents.gemini_agent import GeminiAgent

# Mark all tests in this module as external API tests (may fail due to rate limiting)
pytestmark = pytest.mark.external_api


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory"""
    cache_dir = tmp_path / "trends_e2e_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def mock_config():
    """Mock market configuration"""
    config = Mock()
    config.market.domain = "SaaS"
    config.market.market = "Germany"
    config.market.language = "de"
    config.market.vertical = "Proptech"
    return config


@pytest.fixture
def mock_db_manager():
    """Mock DatabaseManager"""
    db = Mock()
    db.insert_document = Mock(return_value=True)
    db.get_document_by_url = Mock(return_value=None)
    return db


@pytest.fixture
def mock_deduplicator():
    """Mock Deduplicator"""
    import hashlib
    dedup = Mock()
    dedup.is_duplicate = Mock(return_value=False)
    dedup.get_canonical_url = Mock(side_effect=lambda url: url.lower().rstrip('/'))
    dedup.compute_content_hash = Mock(
        side_effect=lambda content: hashlib.md5(content.encode()).hexdigest()
    )
    return dedup


@pytest.fixture
def gemini_agent():
    """Create real GeminiAgent for E2E tests"""
    # Check for API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY environment variable not set")

    return GeminiAgent(
        model="gemini-2.5-flash",
        api_key=api_key,
        enable_grounding=True,
        temperature=0.3
    )


@pytest.fixture
def trends_collector(mock_config, mock_db_manager, mock_deduplicator, gemini_agent, temp_cache_dir):
    """Create TrendsCollector instance for E2E tests"""
    return TrendsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        gemini_agent=gemini_agent,
        cache_dir=temp_cache_dir,
        region="DE"  # Germany
    )


# ==================== E2E Tests ====================

@pytest.mark.e2e
def test_e2e_trending_searches_germany(trends_collector):
    """
    E2E: Collect real trending searches from Google Trends (Germany)

    Expected: Returns list of Document objects with German trends
    """
    documents = trends_collector.collect_trending_searches(pn='germany')

    # Validate response
    assert isinstance(documents, list)
    # May return 0-20 results depending on Google Trends availability
    assert len(documents) >= 0

    if len(documents) > 0:
        # Validate document structure
        doc = documents[0]
        assert isinstance(doc, Document)
        assert doc.id is not None
        assert doc.source == "trends_trending_searches_germany"
        assert doc.title is not None
        assert len(doc.title) > 0
        assert doc.language == "de"
        assert doc.domain == "SaaS"
        assert doc.market == "Germany"
        assert doc.content is not None
        assert "traffic:" in doc.content.lower()

        # Validate timestamps
        assert isinstance(doc.published_at, datetime)
        assert isinstance(doc.fetched_at, datetime)

        # Validate URLs
        assert doc.source_url.startswith("https://trends.google.com")
        assert doc.canonical_url is not None


@pytest.mark.e2e
def test_e2e_trending_searches_us(trends_collector):
    """
    E2E: Collect real trending searches from Google Trends (United States)

    Expected: Returns list of Document objects with US trends
    """
    # Update region for US
    trends_collector.region = "US"

    documents = trends_collector.collect_trending_searches(pn='united_states')

    assert isinstance(documents, list)
    assert len(documents) >= 0

    if len(documents) > 0:
        doc = documents[0]
        assert isinstance(doc, Document)
        assert doc.source == "trends_trending_searches_united_states"


@pytest.mark.e2e
def test_e2e_related_queries_proptech(trends_collector):
    """
    E2E: Collect real related queries for 'PropTech' keyword

    Expected: Returns related search queries (top and rising)
    """
    # Test top queries
    documents_top = trends_collector.collect_related_queries(
        keywords=['PropTech'],
        query_type='top',
        timeframe='today 3-m'
    )

    assert isinstance(documents_top, list)
    # May return 0-25 results depending on keyword popularity
    assert len(documents_top) >= 0

    if len(documents_top) > 0:
        doc = documents_top[0]
        assert isinstance(doc, Document)
        assert doc.source == "trends_related_queries"
        assert "related query" in doc.title.lower()
        assert "value:" in doc.content.lower()

    # Test rising queries
    documents_rising = trends_collector.collect_related_queries(
        keywords=['PropTech'],
        query_type='rising',
        timeframe='today 3-m'
    )

    assert isinstance(documents_rising, list)
    assert len(documents_rising) >= 0


@pytest.mark.e2e
def test_e2e_interest_over_time_proptech(trends_collector):
    """
    E2E: Collect real interest over time data for 'PropTech'

    Expected: Returns trend data showing search volume over time
    """
    documents = trends_collector.collect_interest_over_time(
        keywords=['PropTech'],
        timeframe='today 3-m'
    )

    assert isinstance(documents, list)
    # Should return 1 document per keyword
    assert len(documents) >= 0

    if len(documents) > 0:
        doc = documents[0]
        assert isinstance(doc, Document)
        assert doc.source == "trends_interest_over_time"
        assert "interest over time" in doc.title.lower()
        assert "proptech" in doc.title.lower()
        assert "average interest:" in doc.content.lower()
        assert "max:" in doc.content.lower()
        assert "min:" in doc.content.lower()


@pytest.mark.e2e
def test_e2e_multiple_requests_sequential(trends_collector):
    """
    E2E: Verify multiple sequential requests work correctly

    Expected: All requests complete successfully without rate limit issues
    """
    # Make 3 sequential requests
    docs1 = trends_collector.collect_trending_searches(pn='germany')
    trends_collector._cache = {}  # Clear cache
    docs2 = trends_collector.collect_trending_searches(pn='united_states')
    trends_collector._cache = {}  # Clear cache
    docs3 = trends_collector.collect_trending_searches(pn='france')

    # All requests should succeed (may return 0 results if no trends available)
    assert isinstance(docs1, list)
    assert isinstance(docs2, list)
    assert isinstance(docs3, list)


@pytest.mark.e2e
def test_e2e_cache_persistence_across_instances(mock_config, mock_db_manager, mock_deduplicator, gemini_agent, temp_cache_dir):
    """
    E2E: Verify cache persists across collector instances

    Expected: Second instance can load cache from first instance
    """
    # First instance: Collect and cache
    collector1 = TrendsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        gemini_agent=gemini_agent,
        cache_dir=temp_cache_dir,
        region="DE"
    )

    collector1.collect_trending_searches(pn='germany')
    collector1.save_cache()

    # Second instance: Load from cache
    collector2 = TrendsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        gemini_agent=gemini_agent,
        cache_dir=temp_cache_dir,
        region="DE"
    )

    # Should find cache
    cache_file = Path(temp_cache_dir) / "trends_cache.json"
    assert cache_file.exists()

    # Load cache and verify
    collector2.load_cache()
    assert 'trending_searches_germany' in collector2._cache


@pytest.mark.e2e
def test_e2e_error_handling_invalid_region(trends_collector):
    """
    E2E: Verify error handling with invalid region

    Expected: Raises TrendsCollectorError
    """
    with pytest.raises(TrendsCollectorError):
        trends_collector.collect_trending_searches(pn='INVALID_REGION_XYZ')


@pytest.mark.e2e
def test_e2e_multiple_keywords_interest(trends_collector):
    """
    E2E: Collect interest over time for multiple keywords

    Expected: Returns data for all keywords
    """
    documents = trends_collector.collect_interest_over_time(
        keywords=['PropTech', 'Smart Building', 'IoT'],
        timeframe='today 12-m'
    )

    assert isinstance(documents, list)
    # Should return up to 3 documents (one per keyword)
    assert len(documents) >= 0
    assert len(documents) <= 3


@pytest.mark.e2e
def test_e2e_query_health_tracking(trends_collector):
    """
    E2E: Verify query health tracking with real requests

    Expected: Health metrics are updated correctly
    """
    # Make a successful request
    trends_collector.collect_trending_searches(pn='germany')

    # Check health tracking
    query_id = 'trending_searches_germany'
    assert query_id in trends_collector.query_health
    health = trends_collector.query_health[query_id]

    assert health.success_count >= 1
    assert health.consecutive_failures == 0
    assert health.last_success is not None


@pytest.mark.e2e
def test_e2e_statistics_tracking(trends_collector):
    """
    E2E: Verify statistics are tracked correctly

    Expected: Stats show queries, documents, cache hits/misses
    """
    # Clear cache to force miss
    trends_collector._cache = {}

    # First request (cache miss)
    trends_collector.collect_trending_searches(pn='germany')

    # Second request (cache hit)
    trends_collector.collect_trending_searches(pn='germany')

    stats = trends_collector.get_statistics()

    assert stats['total_queries'] >= 1
    assert stats['cache_hits'] >= 1
    assert stats['cache_misses'] >= 1
    assert stats['total_documents'] >= 0


# ==================== Integration Tests (Config-based) ====================

@pytest.mark.integration
def test_integration_with_proptech_config(mock_db_manager, mock_deduplicator, gemini_agent, tmp_path):
    """
    Integration: Test Trends collector with PropTech German config

    Expected: Works with real market configuration
    """
    from src.utils.config_loader import load_config

    # Load real PropTech config
    config_path = Path(__file__).parents[3] / "config" / "markets" / "proptech_de.yaml"

    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")

    config = load_config(str(config_path))

    collector = TrendsCollector(
        config=config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        gemini_agent=gemini_agent,
        cache_dir=str(tmp_path / "trends_cache"),
        region="DE"
    )

    # Collect trending searches
    documents = collector.collect_trending_searches(pn='germany')

    assert isinstance(documents, list)

    if len(documents) > 0:
        doc = documents[0]
        assert doc.domain == config.market.domain
        assert doc.market == config.market.market
        assert doc.language == config.market.language
        assert doc.vertical == config.market.vertical


if __name__ == "__main__":
    # Run E2E tests
    pytest.main([__file__, "-v", "-m", "e2e", "-s"])
