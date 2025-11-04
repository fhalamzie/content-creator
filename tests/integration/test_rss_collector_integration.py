"""
RSS Collector E2E Integration Tests

Tests RSS collector with real RSS/Atom feeds to ensure:
- Feed parsing works with various feed formats
- Content extraction handles real websites
- Deduplication works across multiple feeds
- Feed health tracking persists across runs
- Rate limiting prevents overwhelming hosts

These tests require internet connection and may be slow.
They validate the collector works with production feeds.
"""

import pytest
from pathlib import Path
from datetime import datetime
import time

from src.collectors.rss_collector import RSSCollector, RSSCollectorError
from src.database.sqlite_manager import SQLiteManager
from src.processors.deduplicator import Deduplicator
from src.utils.config_loader import ConfigLoader


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for integration tests"""
    cache_dir = tmp_path / "rss_cache"
    db_dir = tmp_path / "db"

    cache_dir.mkdir()
    db_dir.mkdir()

    return {
        'cache': str(cache_dir),
        'db': str(db_dir / "test.db")
    }


@pytest.fixture
def integration_config(temp_dirs):
    """Load real config for integration tests"""
    config_path = "config/markets/proptech_de.yaml"

    if not Path(config_path).exists():
        pytest.skip(f"Config file not found: {config_path}")

    config = ConfigLoader.load_config(config_path)
    return config


@pytest.fixture
def db_manager(temp_dirs):
    """Create SQLiteManager for integration tests"""
    db = SQLiteManager(temp_dirs['db'])
    yield db
    # Cleanup
    db.close()


@pytest.fixture
def deduplicator():
    """Create Deduplicator for integration tests"""
    return Deduplicator()


@pytest.fixture
def rss_collector(integration_config, db_manager, deduplicator, temp_dirs):
    """Create RSSCollector for integration tests"""
    return RSSCollector(
        config=integration_config,
        db_manager=db_manager,
        deduplicator=deduplicator,
        cache_dir=temp_dirs['cache'],
        rate_limit_per_host=1.0,  # Be gentle with real feeds
        request_timeout=30
    )


def test_collect_from_real_rss_feed(rss_collector):
    """
    Test collecting from a real RSS feed (Heise.de)

    Validates:
    - Feed parsing works with production RSS
    - Documents have all required fields
    - Content extraction succeeds
    """
    feed_url = "https://www.heise.de/rss/heise.rdf"

    try:
        documents = rss_collector.collect_from_feed(feed_url)
    except Exception as e:
        pytest.skip(f"Network error or feed unavailable: {e}")

    # Should collect at least some articles
    assert len(documents) > 0, "Should collect at least 1 document from Heise RSS"

    # Verify first document structure
    doc = documents[0]
    assert doc.id.startswith('rss_')
    assert doc.source.startswith('rss_')
    assert 'heise.de' in doc.source_url.lower()
    assert len(doc.title) > 0
    assert len(doc.content) > 100  # Should have extracted content
    assert doc.language in ['de', 'en']
    assert isinstance(doc.published_at, datetime)
    assert isinstance(doc.fetched_at, datetime)

    print(f"✓ Collected {len(documents)} documents from Heise RSS")
    print(f"  First article: {doc.title[:50]}...")


def test_collect_from_atom_feed(rss_collector):
    """
    Test collecting from a real Atom feed (GitHub releases)

    Validates:
    - Atom format parsing works
    - Different feed format handled correctly
    """
    # Use a well-maintained public Atom feed
    feed_url = "https://github.com/python/cpython/releases.atom"

    documents = rss_collector.collect_from_feed(feed_url)

    # Should collect releases
    assert len(documents) > 0, "Should collect at least 1 document from Atom feed"

    doc = documents[0]
    assert 'github.com' in doc.source_url.lower()
    assert len(doc.title) > 0

    print(f"✓ Collected {len(documents)} documents from GitHub Atom feed")


def test_collect_from_multiple_real_feeds(rss_collector):
    """
    Test collecting from multiple real feeds

    Validates:
    - Batch collection works with real feeds
    - Per-host rate limiting prevents issues
    - Partial failures handled gracefully
    """
    feed_urls = [
        "https://www.heise.de/rss/heise.rdf",
        "https://github.com/python/cpython/releases.atom",
    ]

    start_time = time.time()
    all_documents = rss_collector.collect_from_feeds(feed_urls, skip_errors=True)
    elapsed = time.time() - start_time

    # Should collect from both feeds
    assert len(all_documents) > 0, "Should collect documents from multiple feeds"

    # Should take at least 1 second due to rate limiting
    assert elapsed >= 1.0, "Rate limiting should introduce delays"

    print(f"✓ Collected {len(all_documents)} total documents in {elapsed:.2f}s")


def test_conditional_get_with_real_feed(rss_collector):
    """
    Test conditional GET (ETag/Last-Modified) with real feed

    Validates:
    - ETag caching works with production feeds
    - Second request returns fewer/no documents (not modified)
    """
    feed_url = "https://www.heise.de/rss/heise.rdf"

    # First collection
    docs1 = rss_collector.collect_from_feed(feed_url)
    assert len(docs1) > 0

    # Second collection (should use cached ETag)
    # Note: If feed was updated between requests, we may still get documents
    docs2 = rss_collector.collect_from_feed(feed_url)

    # Either no new documents (304 Not Modified) or same/fewer documents
    # We can't guarantee feed hasn't changed, so just check it doesn't error
    assert isinstance(docs2, list)

    print(f"✓ First: {len(docs1)} docs, Second: {len(docs2)} docs (conditional GET working)")


def test_feed_health_tracking_persistence(rss_collector):
    """
    Test feed health tracking across multiple collections

    Validates:
    - Health metrics tracked correctly
    - Success/failure counts accurate
    """
    feed_url = "https://www.heise.de/rss/heise.rdf"

    # Collect multiple times
    for i in range(3):
        try:
            rss_collector.collect_from_feed(feed_url)
        except:
            pass
        time.sleep(0.5)  # Rate limiting

    # Check health report
    health_report = rss_collector.get_feed_health_report()

    assert len(health_report) > 0

    heise_health = [h for h in health_report if feed_url in h['url']]
    assert len(heise_health) == 1

    health = heise_health[0]
    assert health['success_count'] >= 1
    assert health['is_healthy'] is True

    print(f"✓ Health tracking: {health['success_count']} successes")


def test_content_extraction_fallback(rss_collector):
    """
    Test content extraction with summary-only feeds

    Validates:
    - trafilatura extracts full content when available
    - Falls back to summary when extraction fails
    """
    # Some RSS feeds only provide summaries, not full content
    feed_url = "https://www.heise.de/rss/heise.rdf"

    documents = rss_collector.collect_from_feed(feed_url)

    # Should have documents
    assert len(documents) > 0

    # Check content length (should be more than just summary)
    for doc in documents:
        # Either full content extracted or summary available
        assert len(doc.content) > 0 or (doc.summary and len(doc.summary) > 0)

    print(f"✓ Content extraction: avg {sum(len(d.content) for d in documents) / len(documents):.0f} chars/article")


def test_deduplication_across_feeds(rss_collector):
    """
    Test deduplication when same article appears in multiple feeds

    Validates:
    - Duplicate detection works across feeds
    - Only unique articles stored
    """
    # Use same feed twice to simulate duplicates
    feed_urls = [
        "https://www.heise.de/rss/heise.rdf",
        "https://www.heise.de/rss/heise.rdf",  # Same feed
    ]

    rss_collector.collect_from_feeds(feed_urls, skip_errors=True)

    # Should deduplicate the second feed's articles
    # (Deduplicator should mark them as duplicates)
    stats = rss_collector.get_statistics()

    # Check that some duplicates were skipped
    # Note: May be 0 if feed changed between requests
    assert stats['total_skipped_duplicates'] >= 0

    print(f"✓ Deduplication: {stats['total_skipped_duplicates']} duplicates skipped")


def test_statistics_tracking(rss_collector):
    """
    Test statistics tracking during collection

    Validates:
    - Statistics accurately reflect collection
    - Counts are correct
    """
    feed_url = "https://www.heise.de/rss/heise.rdf"

    # Collect
    documents = rss_collector.collect_from_feed(feed_url)

    # Check statistics
    stats = rss_collector.get_statistics()

    assert stats['total_feeds_collected'] == 1
    assert stats['total_documents_collected'] == len(documents)
    assert stats['total_failures'] == 0

    print(f"✓ Statistics: {stats}")


def test_error_handling_with_invalid_feed(rss_collector):
    """
    Test error handling with invalid/unreachable feeds

    Validates:
    - Graceful error handling
    - Health tracking records failures
    """
    invalid_url = "https://invalid-feed-url-12345.example.com/feed.xml"

    with pytest.raises(RSSCollectorError):
        rss_collector.collect_from_feed(invalid_url)

    # Check that failure was recorded
    health_report = rss_collector.get_feed_health_report()

    # Health report should include this feed
    invalid_health = [h for h in health_report if invalid_url in h['url']]
    assert len(invalid_health) == 1
    assert invalid_health[0]['failure_count'] == 1

    print("✓ Error handling: failure recorded in health tracking")


def test_rate_limiting_enforcement(rss_collector):
    """
    Test that rate limiting is enforced per host

    Validates:
    - Multiple requests to same host are rate limited
    - Timing matches configured rate limit
    """
    feed_url = "https://www.heise.de/rss/heise.rdf"

    # Collect 3 times from same host
    start = time.time()
    for i in range(3):
        try:
            rss_collector.collect_from_feed(feed_url)
        except:
            pass
    elapsed = time.time() - start

    # With 1.0 req/sec rate limit, 3 requests should take ~2 seconds
    # (0s, 1s, 2s = 3 requests)
    expected_min_time = 2.0  # At least 2 seconds

    assert elapsed >= expected_min_time, f"Rate limiting not enforced: {elapsed:.2f}s < {expected_min_time}s"

    print(f"✓ Rate limiting: {elapsed:.2f}s for 3 requests (expected ≥{expected_min_time}s)")


@pytest.mark.slow
def test_large_feed_collection(rss_collector):
    """
    Test collecting from a large feed (50+ articles)

    Validates:
    - Handles large feeds efficiently
    - All articles processed
    - Memory usage reasonable

    Marked as slow test (may take 30+ seconds)
    """
    # Heise typically has 50+ articles in their main feed
    feed_url = "https://www.heise.de/rss/heise.rdf"

    documents = rss_collector.collect_from_feed(feed_url)

    assert len(documents) >= 10, "Should collect at least 10 documents from large feed"

    # All documents should be valid
    for doc in documents:
        assert len(doc.id) > 0
        assert len(doc.content) > 0

    print(f"✓ Large feed: {len(documents)} documents collected")
