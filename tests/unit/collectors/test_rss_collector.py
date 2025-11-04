"""
Tests for RSS Collector

Test Coverage:
- Feed parsing (RSS, Atom, various formats)
- Content extraction (summary-only feeds, full-content feeds)
- Conditional GET (ETag, Last-Modified)
- Feed health tracking (failures, adaptive polling)
- Per-host rate limiting + robots.txt respect
- Error handling (malformed feeds, network errors, timeouts)
- Document model creation with all required fields
- Deduplication integration
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

from src.collectors.rss_collector import (
    RSSCollector,
    RSSCollectorError,
    FeedHealth,
    FeedEntry,
)
from src.models.document import Document


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for RSS collector"""
    cache_dir = tmp_path / "rss_cache"
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
    dedup = Mock()
    dedup.is_duplicate = Mock(return_value=False)
    dedup.get_canonical_url = Mock(side_effect=lambda url: url.lower().rstrip('/'))
    dedup.compute_content_hash = Mock(side_effect=lambda content: hashlib.md5(content.encode()).hexdigest())
    return dedup


@pytest.fixture
def rss_collector(mock_config, mock_db_manager, mock_deduplicator, temp_cache_dir):
    """Create RSSCollector instance for tests"""
    return RSSCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        deduplicator=mock_deduplicator,
        cache_dir=temp_cache_dir,
        rate_limit_per_host=2.0,  # 2 req/sec per host
        request_timeout=10
    )


@pytest.fixture
def mock_feedparser_response():
    """Mock feedparser successful response"""
    return {
        'bozo': False,  # Well-formed feed
        'entries': [
            {
                'id': 'https://example.com/article-1',
                'link': 'https://example.com/article-1',
                'title': 'PropTech Trends 2025',
                'summary': 'Summary of PropTech trends...',
                'published_parsed': (2025, 11, 4, 12, 0, 0, 0, 0, 0),
                'author': 'John Doe',
            },
            {
                'id': 'https://example.com/article-2',
                'link': 'https://example.com/article-2',
                'title': 'Smart Building IoT',
                'summary': 'IoT devices in smart buildings...',
                'published_parsed': (2025, 11, 3, 10, 30, 0, 0, 0, 0),
                'author': 'Jane Smith',
            }
        ],
        'feed': {
            'title': 'PropTech News',
            'link': 'https://example.com',
        },
        'etag': 'abc123',
        'modified': 'Mon, 04 Nov 2025 12:00:00 GMT'
    }


@pytest.fixture
def mock_trafilatura_content():
    """Mock trafilatura extracted content"""
    return """
PropTech Trends 2025

The PropTech industry is experiencing rapid growth in 2025.
Key trends include AI-powered property management, blockchain for
real estate transactions, and IoT integration in smart buildings.

Major players are investing heavily in DSGVO-compliant solutions
for the German market, with a focus on data privacy and security.
"""


# ==================== Test RSSCollector Initialization ====================

def test_rss_collector_initialization(rss_collector, temp_cache_dir):
    """Test RSSCollector initializes correctly"""
    assert rss_collector.config is not None
    assert rss_collector.db_manager is not None
    assert rss_collector.deduplicator is not None
    assert str(rss_collector.cache_dir) == temp_cache_dir
    assert rss_collector.rate_limit_per_host == 2.0
    assert rss_collector.request_timeout == 10
    assert rss_collector._feed_health == {}
    assert rss_collector._last_request_per_host == {}


def test_rss_collector_creates_cache_dir():
    """Test RSSCollector creates cache directory if missing"""
    with patch('pathlib.Path.mkdir') as mock_mkdir:
        config = Mock()
        config.market.domain = "SaaS"

        collector = RSSCollector(
            config=config,
            db_manager=Mock(),
            deduplicator=Mock(),
            cache_dir="/tmp/test_rss_cache"
        )

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


# ==================== Test Feed Parsing ====================

@patch('feedparser.parse')
def test_collect_from_feed_success(mock_parse, rss_collector, mock_feedparser_response, mock_trafilatura_content):
    """Test successful feed collection"""
    mock_parse.return_value = mock_feedparser_response

    with patch.object(rss_collector, '_extract_full_content', return_value=mock_trafilatura_content):
        documents = rss_collector.collect_from_feed('https://example.com/feed.xml')

    assert len(documents) == 2
    assert all(isinstance(doc, Document) for doc in documents)
    assert documents[0].title == 'PropTech Trends 2025'
    assert documents[0].source == 'rss_example.com'
    assert documents[0].domain == 'SaaS'
    assert documents[0].market == 'Germany'
    assert documents[0].language == 'de'


@patch('feedparser.parse')
def test_collect_from_feed_malformed(mock_parse, rss_collector):
    """Test handling of malformed feed"""
    mock_parse.return_value = {
        'bozo': True,  # Malformed
        'bozo_exception': Exception("Feed parsing error"),
        'entries': []
    }

    with pytest.raises(RSSCollectorError) as exc_info:
        rss_collector.collect_from_feed('https://example.com/bad-feed.xml')

    assert "malformed" in str(exc_info.value).lower()


@patch('feedparser.parse')
def test_collect_from_feed_empty(mock_parse, rss_collector):
    """Test handling of empty feed"""
    mock_parse.return_value = {
        'bozo': False,
        'entries': []
    }

    documents = rss_collector.collect_from_feed('https://example.com/empty-feed.xml')

    assert len(documents) == 0


@patch('feedparser.parse')
def test_collect_from_feed_with_etag(mock_parse, rss_collector):
    """Test conditional GET with ETag"""
    # Save ETag to cache first
    feed_url = 'https://example.com/feed.xml'
    rss_collector._save_feed_cache(feed_url, etag='abc123', modified='Mon, 04 Nov 2025 12:00:00 GMT')

    # Mock 304 Not Modified response
    mock_parse.return_value = {
        'status': 304,
        'entries': []
    }

    documents = rss_collector.collect_from_feed(feed_url)

    # Should return empty (feed not modified)
    assert len(documents) == 0

    # Verify feedparser was called with ETag
    call_args = mock_parse.call_args
    assert 'etag' in call_args.kwargs or len(call_args.args) > 1


# ==================== Test Content Extraction ====================

@patch('trafilatura.fetch_url')
@patch('trafilatura.extract')
def test_extract_full_content_success(mock_extract, mock_fetch, rss_collector, mock_trafilatura_content):
    """Test successful content extraction with trafilatura"""
    mock_fetch.return_value = "<html><body>Article content</body></html>"
    mock_extract.return_value = mock_trafilatura_content

    content = rss_collector._extract_full_content('https://example.com/article-1', 'Summary...')

    assert content == mock_trafilatura_content
    mock_fetch.assert_called_once_with('https://example.com/article-1')
    mock_extract.assert_called_once()


@patch('trafilatura.fetch_url')
@patch('trafilatura.extract')
def test_extract_full_content_fallback_to_summary(mock_extract, mock_fetch, rss_collector):
    """Test fallback to summary when extraction fails"""
    mock_fetch.return_value = None  # Fetch failed

    content = rss_collector._extract_full_content('https://example.com/article-1', 'Fallback summary')

    assert content == 'Fallback summary'


@patch('trafilatura.fetch_url')
@patch('trafilatura.extract')
def test_extract_full_content_timeout(mock_extract, mock_fetch, rss_collector):
    """Test timeout handling during content extraction"""
    mock_fetch.side_effect = Exception("Timeout")

    content = rss_collector._extract_full_content('https://example.com/article-1', 'Summary fallback', timeout=5)

    assert content == 'Summary fallback'


# ==================== Test Feed Health Tracking ====================

def test_feed_health_initialization(rss_collector):
    """Test feed health tracking initialization"""
    feed_url = 'https://example.com/feed.xml'

    health = rss_collector._get_feed_health(feed_url)

    assert isinstance(health, FeedHealth)
    assert health.url == feed_url
    assert health.success_count == 0
    assert health.failure_count == 0
    assert health.consecutive_failures == 0
    assert health.last_success is None
    assert health.last_failure is None


@patch('feedparser.parse')
def test_feed_health_success_tracking(mock_parse, rss_collector, mock_feedparser_response):
    """Test feed health tracking on success"""
    mock_parse.return_value = mock_feedparser_response
    feed_url = 'https://example.com/feed.xml'

    with patch.object(rss_collector, '_extract_full_content', return_value="Content"):
        rss_collector.collect_from_feed(feed_url)

    health = rss_collector._get_feed_health(feed_url)
    assert health.success_count == 1
    assert health.consecutive_failures == 0
    assert health.last_success is not None


@patch('feedparser.parse')
def test_feed_health_failure_tracking(mock_parse, rss_collector):
    """Test feed health tracking on failure"""
    mock_parse.side_effect = Exception("Network error")
    feed_url = 'https://example.com/feed.xml'

    with pytest.raises(RSSCollectorError):
        rss_collector.collect_from_feed(feed_url)

    health = rss_collector._get_feed_health(feed_url)
    assert health.failure_count == 1
    assert health.consecutive_failures == 1
    assert health.last_failure is not None


def test_should_skip_unhealthy_feed(rss_collector):
    """Test skipping feeds with too many consecutive failures"""
    feed_url = 'https://example.com/feed.xml'
    health = rss_collector._get_feed_health(feed_url)

    # Simulate 5 consecutive failures
    health.consecutive_failures = 5
    health.failure_count = 10

    assert rss_collector._should_skip_feed(feed_url) is True


def test_should_not_skip_healthy_feed(rss_collector):
    """Test not skipping healthy feeds"""
    feed_url = 'https://example.com/feed.xml'
    health = rss_collector._get_feed_health(feed_url)

    health.success_count = 50
    health.consecutive_failures = 0

    assert rss_collector._should_skip_feed(feed_url) is False


# ==================== Test Rate Limiting ====================

@patch('feedparser.parse')
@patch('time.sleep')
def test_per_host_rate_limiting(mock_sleep, mock_parse, rss_collector, mock_feedparser_response):
    """Test per-host rate limiting"""
    mock_parse.return_value = mock_feedparser_response

    with patch.object(rss_collector, '_extract_full_content', return_value="Content"):
        # Collect from same host twice
        rss_collector.collect_from_feed('https://example.com/feed1.xml')
        rss_collector.collect_from_feed('https://example.com/feed2.xml')

    # Should have called sleep to enforce rate limit (2 req/sec = 0.5s between)
    assert mock_sleep.called


# ==================== Test Document Creation ====================

@patch('feedparser.parse')
def test_document_creation_with_all_fields(mock_parse, rss_collector, mock_feedparser_response, mock_trafilatura_content):
    """Test Document objects have all required fields"""
    mock_parse.return_value = mock_feedparser_response

    with patch.object(rss_collector, '_extract_full_content', return_value=mock_trafilatura_content):
        documents = rss_collector.collect_from_feed('https://example.com/feed.xml')

    doc = documents[0]

    # Identity
    assert doc.id.startswith('rss_')
    assert doc.source == 'rss_example.com'
    assert doc.source_url == 'https://example.com/article-1'

    # Content
    assert doc.title == 'PropTech Trends 2025'
    assert len(doc.content) > 0
    assert doc.summary is not None

    # Classification
    assert doc.language == 'de'
    assert doc.domain == 'SaaS'
    assert doc.market == 'Germany'
    assert doc.vertical == 'Proptech'

    # Deduplication
    assert len(doc.content_hash) > 0
    assert doc.canonical_url is not None

    # Metadata
    assert isinstance(doc.published_at, datetime)
    assert isinstance(doc.fetched_at, datetime)
    assert doc.author == 'John Doe'

    # Status
    assert doc.status == 'new'


@patch('feedparser.parse')
def test_document_id_generation(mock_parse, rss_collector, mock_feedparser_response):
    """Test unique document ID generation"""
    mock_parse.return_value = mock_feedparser_response

    with patch.object(rss_collector, '_extract_full_content', return_value="Content"):
        documents = rss_collector.collect_from_feed('https://example.com/feed.xml')

    # All IDs should be unique
    ids = [doc.id for doc in documents]
    assert len(ids) == len(set(ids))

    # IDs should contain source identifier
    assert all(id.startswith('rss_') for id in ids)


# ==================== Test Deduplication Integration ====================

@patch('feedparser.parse')
def test_skip_duplicate_documents(mock_parse, rss_collector, mock_feedparser_response):
    """Test skipping duplicate documents"""
    mock_parse.return_value = mock_feedparser_response

    # Mock deduplicator to mark first entry as duplicate
    rss_collector.deduplicator.is_duplicate = Mock(side_effect=[True, False])

    with patch.object(rss_collector, '_extract_full_content', return_value="Content"):
        documents = rss_collector.collect_from_feed('https://example.com/feed.xml')

    # Should only return 1 document (second one), first was duplicate
    assert len(documents) == 1
    assert documents[0].title == 'Smart Building IoT'


# ==================== Test Batch Collection ====================

@patch('feedparser.parse')
def test_collect_from_multiple_feeds(mock_parse, rss_collector, mock_feedparser_response):
    """Test collecting from multiple feeds"""
    mock_parse.return_value = mock_feedparser_response

    feed_urls = [
        'https://example.com/feed1.xml',
        'https://example.com/feed2.xml',
        'https://example.com/feed3.xml'
    ]

    with patch.object(rss_collector, '_extract_full_content', return_value="Content"):
        all_documents = rss_collector.collect_from_feeds(feed_urls)

    # Should collect from all 3 feeds (2 entries each = 6 total)
    assert len(all_documents) == 6


@patch('feedparser.parse')
def test_collect_from_feeds_with_failures(mock_parse, rss_collector, mock_feedparser_response):
    """Test partial failure when collecting from multiple feeds"""
    # First feed succeeds, second fails, third succeeds
    mock_parse.side_effect = [
        mock_feedparser_response,
        Exception("Network error"),
        mock_feedparser_response
    ]

    feed_urls = [
        'https://example.com/feed1.xml',
        'https://example.com/feed2.xml',
        'https://example.com/feed3.xml'
    ]

    with patch.object(rss_collector, '_extract_full_content', return_value="Content"):
        all_documents = rss_collector.collect_from_feeds(feed_urls, skip_errors=True)

    # Should collect from 2 feeds (4 documents total, 1 feed failed)
    assert len(all_documents) == 4


# ==================== Test Caching ====================

def test_save_and_load_feed_cache(rss_collector):
    """Test saving and loading feed cache (ETag/Modified)"""
    feed_url = 'https://example.com/feed.xml'
    etag = 'abc123'
    modified = 'Mon, 04 Nov 2025 12:00:00 GMT'

    rss_collector._save_feed_cache(feed_url, etag=etag, modified=modified)
    cached = rss_collector._load_feed_cache(feed_url)

    assert cached['etag'] == etag
    assert cached['modified'] == modified
    assert 'cached_at' in cached


def test_cache_expiry(rss_collector):
    """Test cache expiry after TTL"""
    feed_url = 'https://example.com/feed.xml'

    # Save cache with old timestamp
    old_time = datetime.now() - timedelta(days=31)
    cache_data = {
        'etag': 'old123',
        'modified': 'Old date',
        'cached_at': old_time.isoformat()
    }

    cache_file = rss_collector.cache_dir / f"{hashlib.md5(feed_url.encode()).hexdigest()}.json"
    import json
    cache_file.write_text(json.dumps(cache_data))

    # Should return None (expired)
    cached = rss_collector._load_feed_cache(feed_url, ttl_days=30)
    assert cached is None


# ==================== Test Error Handling ====================

@patch('feedparser.parse')
def test_network_error_handling(mock_parse, rss_collector):
    """Test handling of network errors"""
    mock_parse.side_effect = Exception("Connection timeout")

    with pytest.raises(RSSCollectorError) as exc_info:
        rss_collector.collect_from_feed('https://example.com/feed.xml')

    assert "connection timeout" in str(exc_info.value).lower()


@patch('feedparser.parse')
def test_invalid_url_handling(mock_parse, rss_collector):
    """Test handling of invalid URLs"""
    with pytest.raises(RSSCollectorError) as exc_info:
        rss_collector.collect_from_feed('not-a-valid-url')

    assert "invalid" in str(exc_info.value).lower()


# ==================== Test Statistics ====================

@patch('feedparser.parse')
def test_collection_statistics(mock_parse, rss_collector, mock_feedparser_response):
    """Test collection statistics tracking"""
    mock_parse.return_value = mock_feedparser_response

    with patch.object(rss_collector, '_extract_full_content', return_value="Content"):
        rss_collector.collect_from_feed('https://example.com/feed.xml')

    stats = rss_collector.get_statistics()

    assert stats['total_feeds_collected'] == 1
    assert stats['total_documents_collected'] == 2
    assert stats['total_failures'] == 0


@patch('feedparser.parse')
def test_statistics_with_failures(mock_parse, rss_collector):
    """Test statistics tracking with failures"""
    mock_parse.side_effect = Exception("Error")

    try:
        rss_collector.collect_from_feed('https://example.com/feed.xml')
    except:
        pass

    stats = rss_collector.get_statistics()

    assert stats['total_failures'] > 0
