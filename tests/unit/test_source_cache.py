"""
Unit Tests for Source Cache

Tests source caching with quality scoring and freshness tracking.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import json

from src.research.source_cache import SourceCache


class TestSourceCache:
    """Unit tests for SourceCache class"""

    @pytest.fixture
    def mock_db(self):
        """Mock database manager"""
        db = Mock()
        db._get_connection = Mock()
        return db

    @pytest.fixture
    def source_cache(self, mock_db):
        """Create SourceCache with mocked database"""
        return SourceCache(mock_db)

    # Test 1: Quality score calculation - High-quality news source
    def test_calculate_quality_score_major_news(self, source_cache):
        """High-quality news source gets high score"""
        score, signals = source_cache.calculate_quality_score(
            domain="nytimes.com",
            published_at=datetime.utcnow(),  # Fresh
            usage_count=10,
            content="Breaking news article..."
        )

        # NYTimes = 0.95 authority, news = 0.9, fresh = 1.0, usage = moderate
        # Expected: 0.95*0.4 + 0.9*0.3 + 1.0*0.2 + ~0.35*0.1 = ~0.925
        assert score > 0.9
        assert signals['domain_authority'] == 0.95
        assert signals['publication_type'] == 'news'
        assert signals['freshness'] > 0.95  # Very fresh

    # Test 2: Quality score - Government source
    def test_calculate_quality_score_gov(self, source_cache):
        """Government source gets highest authority"""
        score, signals = source_cache.calculate_quality_score(
            domain="cdc.gov",
            published_at=datetime.utcnow() - timedelta(days=5),
            usage_count=5,
            content="Official CDC guidance..."
        )

        assert signals['domain_authority'] == 1.0  # .gov = highest
        assert score > 0.75  # High score despite 5-day freshness decay
        assert signals['freshness'] > 0.8  # 5 days old, still fresh

    # Test 3: Quality score - Blog with low authority
    def test_calculate_quality_score_blog(self, source_cache):
        """Blog posts get lower scores"""
        score, signals = source_cache.calculate_quality_score(
            domain="medium.com",
            published_at=datetime.utcnow() - timedelta(days=90),  # Old
            usage_count=1,
            content="My thoughts on..."
        )

        assert signals['domain_authority'] == 0.6  # Medium.com
        assert signals['publication_type'] == 'blog'
        assert signals['freshness'] < 0.1  # 90 days old, stale
        assert score < 0.6  # Low overall

    # Test 4: Quality score - Academic source
    def test_calculate_quality_score_academic(self, source_cache):
        """Academic sources get high publication type score"""
        score, signals = source_cache.calculate_quality_score(
            domain="arxiv.org",
            published_at=datetime.utcnow() - timedelta(days=30),
            usage_count=20,
            content="Abstract: This paper presents..."
        )

        assert signals['publication_type'] == 'academic'
        assert signals['publication_score'] == 1.0  # Highest type
        assert score > 0.79  # Very high despite 30-day age (freshness ~0.37)

    # Test 5: Quality score - Unknown domain
    def test_calculate_quality_score_unknown_domain(self, source_cache):
        """Unknown domain gets default medium score"""
        score, signals = source_cache.calculate_quality_score(
            domain="random-blog.com",
            published_at=None,  # Unknown date
            usage_count=1,
            content="Some content..."
        )

        assert signals['domain_authority'] == 0.5  # Default
        assert signals['publication_type'] == 'unknown'
        assert signals['freshness'] == 0.5  # Unknown age
        assert 0.4 < score < 0.6  # Medium score

    # Test 6: Detect publication type - News
    def test_detect_publication_type_news(self, source_cache):
        """Detect news publication types"""
        assert source_cache._detect_publication_type("nytimes.com", None) == 'news'
        assert source_cache._detect_publication_type("reuters.com", None) == 'news'
        assert source_cache._detect_publication_type("bbc.co.uk", None) == 'news'

    # Test 7: Detect publication type - Academic
    def test_detect_publication_type_academic(self, source_cache):
        """Detect academic publication types"""
        assert source_cache._detect_publication_type("stanford.edu", None) == 'academic'
        assert source_cache._detect_publication_type("scholar.google.com", None) == 'academic'
        assert source_cache._detect_publication_type("arxiv.org", None) == 'academic'

    # Test 8: Detect publication type - Blog
    def test_detect_publication_type_blog(self, source_cache):
        """Detect blog platforms"""
        assert source_cache._detect_publication_type("medium.com", None) == 'blog'
        assert source_cache._detect_publication_type("substack.com", None) == 'blog'
        assert source_cache._detect_publication_type("wordpress.com", None) == 'blog'

    # Test 9: Detect publication type - Industry
    def test_detect_publication_type_industry(self, source_cache):
        """Detect industry publications"""
        assert source_cache._detect_publication_type("techcrunch.com", None) == 'industry'
        assert source_cache._detect_publication_type("venturebeat.com", None) == 'industry'
        assert source_cache._detect_publication_type("wired.com", None) == 'industry'

    # Test 10: Detect publication type - Social
    def test_detect_publication_type_social(self, source_cache):
        """Detect social media"""
        assert source_cache._detect_publication_type("twitter.com", None) == 'social'
        assert source_cache._detect_publication_type("linkedin.com", None) == 'social'
        assert source_cache._detect_publication_type("reddit.com", None) == 'social'

    # Test 11: Usage popularity scoring
    def test_usage_popularity_scaling(self, source_cache):
        """Usage count scales logarithmically"""
        # 1 use = low popularity (log10(2)/log10(100) = 0.15)
        _, signals_1 = source_cache.calculate_quality_score("test.com", None, 1)
        assert signals_1['usage_popularity'] < 0.2

        # 10 uses = medium popularity (log10(11)/log10(100) = 0.52)
        _, signals_10 = source_cache.calculate_quality_score("test.com", None, 10)
        assert 0.4 < signals_10['usage_popularity'] < 0.6

        # 100 uses = max popularity (log10(101)/log10(100) = 1.0)
        _, signals_100 = source_cache.calculate_quality_score("test.com", None, 100)
        assert signals_100['usage_popularity'] >= 0.99

    # Test 12: Freshness decay - Exponential
    def test_freshness_exponential_decay(self, source_cache):
        """Freshness decays exponentially over time (e^(-days/30))"""
        # Fresh (today)
        _, signals_0 = source_cache.calculate_quality_score(
            "test.com", datetime.utcnow(), 1
        )
        assert signals_0['freshness'] > 0.95

        # 30 days (e^(-30/30) = e^(-1) = 0.368)
        _, signals_30 = source_cache.calculate_quality_score(
            "test.com", datetime.utcnow() - timedelta(days=30), 1
        )
        assert 0.35 < signals_30['freshness'] < 0.40  # ~0.368

        # 90 days (e^(-90/30) = e^(-3) = 0.0498)
        _, signals_90 = source_cache.calculate_quality_score(
            "test.com", datetime.utcnow() - timedelta(days=90), 1
        )
        assert signals_90['freshness'] < 0.1

    # Test 13: Domain extraction
    def test_domain_extraction(self, source_cache, mock_db):
        """Extract domain from URL correctly"""
        # Mock database responses
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # New source

        source_cache.save_source(
            url="https://www.nytimes.com/2025/article",
            title="Test Article",
            content="Content...",
            topic_id="test-topic"
        )

        # Check that domain was extracted correctly (www. removed)
        call_args = mock_cursor.execute.call_args_list
        insert_call = [c for c in call_args if 'INSERT INTO sources' in str(c)][0]
        insert_values = insert_call[0][1]
        assert insert_values[1] == 'nytimes.com'  # domain field

    # Test 14: Save source - New source
    def test_save_source_new(self, source_cache, mock_db):
        """Saving new source creates database entry"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # No existing source

        result = source_cache.save_source(
            url="https://test.com/article",
            title="Test Article",
            content="This is test content for caching.",
            topic_id="test-123"
        )

        # Verify INSERT was called
        assert any('INSERT INTO sources' in str(call) for call in mock_cursor.execute.call_args_list)

        # Verify result structure
        assert result['url'] == "https://test.com/article"
        assert result['domain'] == 'test.com'
        assert result['title'] == "Test Article"
        assert 'quality_score' in result
        assert 'e_e_a_t_signals' in result

    # Test 15: Save source - Update existing
    def test_save_source_update_existing(self, source_cache, mock_db):
        """Updating existing source increments counters"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # First call: existing source check
        # Second call: get last_fetched_at
        existing_topic_ids = json.dumps(["old-topic"])
        mock_cursor.fetchone.side_effect = [
            (existing_topic_ids, 5, 5),  # First SELECT (topic_ids, fetch_count, usage_count)
            ((datetime.utcnow() - timedelta(days=2)).isoformat(),),  # Second SELECT (last_fetched_at)
        ]

        result = source_cache.save_source(
            url="https://test.com/article",
            title="Updated Article",
            content="Updated content...",
            topic_id="new-topic"
        )

        # Verify UPDATE was called
        assert any('UPDATE sources' in str(call) for call in mock_cursor.execute.call_args_list)

        # Verify result
        assert result['url'] == "https://test.com/article"
        assert result['is_stale'] == False  # Just refreshed

    # Test 16: Get source - Found
    def test_get_source_found(self, source_cache, mock_db):
        """Retrieving existing source returns data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock database row
        now = datetime.utcnow()
        mock_cursor.fetchone.return_value = (
            "https://test.com/article",  # url
            "test.com",  # domain
            "Test Article",  # title
            "Content preview...",  # content_preview
            (now - timedelta(days=10)).isoformat(),  # first_fetched_at
            (now - timedelta(days=2)).isoformat(),  # last_fetched_at
            3,  # fetch_count
            json.dumps(["topic-1", "topic-2"]),  # topic_ids
            2,  # usage_count
            0.85,  # quality_score
            json.dumps({'domain_authority': 0.8}),  # e_e_a_t_signals
            "John Doe",  # author
            now.isoformat(),  # published_at
            False  # is_stale
        )

        result = source_cache.get_source("https://test.com/article")

        assert result is not None
        assert result['url'] == "https://test.com/article"
        assert result['domain'] == "test.com"
        assert result['quality_score'] == 0.85
        assert result['fetch_count'] == 3
        assert result['usage_count'] == 2
        assert len(result['topic_ids']) == 2
        assert result['is_stale'] == False  # 2 days old, still fresh

    # Test 17: Get source - Not found
    def test_get_source_not_found(self, source_cache, mock_db):
        """Retrieving non-existent source returns None"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = source_cache.get_source("https://nonexistent.com/article")

        assert result is None

    # Test 18: Get source - Stale detection
    def test_get_source_stale_detection(self, source_cache, mock_db):
        """Source older than 7 days is marked as stale"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock source fetched 10 days ago
        now = datetime.utcnow()
        old_date = now - timedelta(days=10)
        mock_cursor.fetchone.return_value = (
            "https://test.com/article", "test.com", "Old Article", "Content...",
            old_date.isoformat(), old_date.isoformat(),
            1, "[]", 1, 0.7, "{}", None, None, False  # is_stale=False initially
        )

        result = source_cache.get_source("https://test.com/article")

        assert result['is_stale'] == True  # Detected as stale
        assert result['days_old'] == 10

    # Test 19: Mark usage
    def test_mark_usage(self, source_cache, mock_db):
        """Marking usage increments usage_count"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock existing source
        existing_topics = json.dumps(["topic-1"])
        mock_cursor.fetchone.return_value = (existing_topics, 5)

        success = source_cache.mark_usage("https://test.com/article", "topic-2")

        assert success == True
        # Verify UPDATE was called
        assert any('UPDATE sources' in str(call) for call in mock_cursor.execute.call_args_list)

    # Test 20: Mark usage - Source not found
    def test_mark_usage_not_found(self, source_cache, mock_db):
        """Marking usage for non-existent source returns False"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        success = source_cache.mark_usage("https://nonexistent.com/article", "topic-1")

        assert success == False

    # Test 21: Get stats
    def test_get_stats(self, source_cache, mock_db):
        """Get cache statistics"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock statistics queries
        mock_cursor.fetchone.side_effect = [
            (150,),  # total_sources
            (0.75,),  # avg_quality
            (30,),   # stale_count
        ]
        mock_cursor.fetchall.return_value = [
            ('nytimes.com', 25, 0.9),
            ('reuters.com', 20, 0.85),
        ]

        stats = source_cache.get_stats()

        assert stats['total_sources'] == 150
        assert stats['avg_quality'] == 0.75
        assert stats['stale_count'] == 30
        assert stats['fresh_count'] == 120  # 150 - 30
        assert len(stats['top_domains']) == 2
        assert stats['top_domains'][0]['domain'] == 'nytimes.com'

    # Test 22: Get stale sources
    def test_get_stale_sources(self, source_cache, mock_db):
        """Get list of stale sources"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db._get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock stale sources
        old_date = (datetime.utcnow() - timedelta(days=10)).isoformat()
        mock_cursor.fetchall.return_value = [
            ('https://test1.com/article', 'test1.com', 'Article 1', 0.8, old_date),
            ('https://test2.com/article', 'test2.com', 'Article 2', 0.7, old_date),
        ]

        stale = source_cache.get_stale_sources(limit=10)

        assert len(stale) == 2
        assert stale[0]['url'] == 'https://test1.com/article'
        assert stale[0]['days_old'] == 10
        assert stale[0]['quality_score'] == 0.8
