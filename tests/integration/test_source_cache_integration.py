"""
Integration Tests for Source Cache

Tests source caching with real SQLite database.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from src.database.sqlite_manager import SQLiteManager
from src.research.source_cache import SourceCache


class TestSourceCacheIntegration:
    """Integration tests with real database"""

    @pytest.fixture
    def db_manager(self):
        """Create in-memory database for testing"""
        db = SQLiteManager(':memory:')
        return db

    @pytest.fixture
    def source_cache(self, db_manager):
        """Create SourceCache with real database"""
        return SourceCache(db_manager)

    # Test 1: Save and retrieve source
    def test_save_and_retrieve_source(self, source_cache):
        """Save a source and retrieve it"""
        # Save source
        result = source_cache.save_source(
            url="https://nytimes.com/article-1",
            title="Breaking News Article",
            content="This is a test article with important news content.",
            topic_id="test-topic-1",
            author="John Reporter",
            published_at=datetime.utcnow()
        )

        assert result['url'] == "https://nytimes.com/article-1"
        assert result['domain'] == 'nytimes.com'
        assert result['quality_score'] > 0.85  # NYTimes is high quality

        # Retrieve source
        cached = source_cache.get_source("https://nytimes.com/article-1")

        assert cached is not None
        assert cached['url'] == "https://nytimes.com/article-1"
        assert cached['title'] == "Breaking News Article"
        assert cached['author'] == "John Reporter"
        assert cached['fetch_count'] == 1
        assert cached['usage_count'] == 1
        assert len(cached['topic_ids']) == 1
        assert 'test-topic-1' in cached['topic_ids']
        assert cached['is_stale'] == False

    # Test 2: Update existing source
    def test_update_existing_source(self, source_cache):
        """Updating existing source increments counters"""
        # Save initial source
        source_cache.save_source(
            url="https://test.com/article",
            title="Original Title",
            content="Original content",
            topic_id="topic-1"
        )

        # Save again with different topic
        result = source_cache.save_source(
            url="https://test.com/article",
            title="Updated Title",
            content="Updated content",
            topic_id="topic-2"
        )

        # Verify counters incremented
        cached = source_cache.get_source("https://test.com/article")
        assert cached['fetch_count'] == 2  # Incremented
        assert cached['usage_count'] == 2  # Two topics
        assert len(cached['topic_ids']) == 2
        assert 'topic-1' in cached['topic_ids']
        assert 'topic-2' in cached['topic_ids']
        assert cached['title'] == "Updated Title"  # Updated

    # Test 3: Quality score calculation - Real database
    def test_quality_scores_vary_by_domain(self, source_cache):
        """Different domains get different quality scores"""
        # High-quality news source
        news = source_cache.save_source(
            url="https://nytimes.com/test",
            title="News Article",
            content="Breaking news...",
            topic_id="topic-1",
            published_at=datetime.utcnow()
        )

        # Government source (highest quality)
        gov = source_cache.save_source(
            url="https://cdc.gov/test",
            title="Official Guidance",
            content="Official CDC guidance...",
            topic_id="topic-1",
            published_at=datetime.utcnow()
        )

        # Blog (lower quality)
        blog = source_cache.save_source(
            url="https://medium.com/@author/test",
            title="Blog Post",
            content="My thoughts on...",
            topic_id="topic-1",
            published_at=datetime.utcnow()
        )

        # Verify quality ordering
        # Note: NYT gets 'news' type (0.9) which boosts it above .gov with 'unknown' type (0.5)
        #  but both should still be high quality overall
        assert news['quality_score'] > blog['quality_score']  # news > blog
        assert gov['quality_score'] > blog['quality_score']  # .gov > blog
        assert gov['quality_score'] > 0.75  # .gov has max domain authority (1.0)
        assert news['quality_score'] > 0.83  # NYT high quality
        assert blog['quality_score'] < 0.7

    # Test 4: Freshness tracking
    def test_freshness_tracking(self, source_cache):
        """Fresh sources get higher scores than stale sources"""
        # Fresh source (today)
        fresh = source_cache.save_source(
            url="https://test.com/fresh",
            title="Fresh Article",
            content="Just published...",
            topic_id="topic-1",
            published_at=datetime.utcnow()
        )

        # Old source (90 days ago)
        old = source_cache.save_source(
            url="https://test.com/old",
            title="Old Article",
            content="Published long ago...",
            topic_id="topic-1",
            published_at=datetime.utcnow() - timedelta(days=90)
        )

        # Fresh should have higher score
        assert fresh['quality_score'] > old['quality_score']
        assert fresh['e_e_a_t_signals']['freshness'] > 0.9
        assert old['e_e_a_t_signals']['freshness'] < 0.1

    # Test 5: Stale detection after 7 days
    def test_stale_detection(self, source_cache, db_manager):
        """Sources older than 7 days are detected as stale"""
        # Insert source with old last_fetched_at (10 days ago)
        old_date = datetime.utcnow() - timedelta(days=10)

        with db_manager._get_connection() as conn:
            conn.execute("""
            INSERT INTO sources (
                url, domain, title, content_preview,
                first_fetched_at, last_fetched_at, fetch_count,
                topic_ids, usage_count, quality_score, e_e_a_t_signals,
                is_stale, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "https://test.com/old",
            "test.com",
            "Old Article",
            "Content...",
            old_date,
            old_date,
            1,
            '["topic-1"]',
            1,
            0.7,
            '{}',
            0,  # Not marked stale yet
            old_date
            ))
            conn.commit()

        # Retrieve source - should detect staleness
        cached = source_cache.get_source("https://test.com/old")

        assert cached is not None
        assert cached['is_stale'] == True
        assert cached['days_old'] == 10

    # Test 6: Mark usage for existing source
    def test_mark_usage(self, source_cache):
        """Marking usage tracks topic IDs"""
        # Save source
        source_cache.save_source(
            url="https://test.com/article",
            title="Test Article",
            content="Content...",
            topic_id="topic-1"
        )

        # Mark usage from another topic
        success = source_cache.mark_usage("https://test.com/article", "topic-2")
        assert success == True

        # Verify tracking
        cached = source_cache.get_source("https://test.com/article")
        assert cached['usage_count'] == 2
        assert len(cached['topic_ids']) == 2
        assert 'topic-2' in cached['topic_ids']

    # Test 7: Mark usage - Duplicate topic
    def test_mark_usage_duplicate_topic(self, source_cache):
        """Marking usage with same topic doesn't duplicate"""
        # Save source
        source_cache.save_source(
            url="https://test.com/article",
            title="Test Article",
            content="Content...",
            topic_id="topic-1"
        )

        # Mark usage from same topic
        source_cache.mark_usage("https://test.com/article", "topic-1")

        # Verify no duplication
        cached = source_cache.get_source("https://test.com/article")
        assert cached['usage_count'] == 1  # Not incremented
        assert len(cached['topic_ids']) == 1

    # Test 8: Get stale sources
    def test_get_stale_sources(self, source_cache, db_manager):
        """Get list of stale sources"""
        # Insert fresh and stale sources
        now = datetime.utcnow()
        old_date = now - timedelta(days=10)

        with db_manager._get_connection() as conn:
            # Fresh source
            conn.execute("""
            INSERT INTO sources (
                url, domain, title, content_preview,
                first_fetched_at, last_fetched_at, fetch_count,
                topic_ids, usage_count, quality_score, e_e_a_t_signals,
                is_stale, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "https://test.com/fresh", "test.com", "Fresh", "Content...",
            now, now, 1, '["topic-1"]', 1, 0.8, '{}', 0, now
            ))

            # Stale source
            conn.execute("""
            INSERT INTO sources (
                url, domain, title, content_preview,
                first_fetched_at, last_fetched_at, fetch_count,
                topic_ids, usage_count, quality_score, e_e_a_t_signals,
                is_stale, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "https://test.com/stale", "test.com", "Stale", "Content...",
            old_date, old_date, 1, '["topic-1"]', 1, 0.7, '{}', 1, old_date
            ))

            conn.commit()

        # Get stale sources
        stale = source_cache.get_stale_sources(limit=10)

        assert len(stale) == 1
        assert stale[0]['url'] == 'https://test.com/stale'
        assert stale[0]['days_old'] == 10

    # Test 9: Get cache statistics
    def test_get_stats(self, source_cache):
        """Get cache statistics"""
        # Insert multiple sources from different domains
        for i in range(5):
            source_cache.save_source(
                url=f"https://nytimes.com/article-{i}",
                title=f"Article {i}",
                content="Content...",
                topic_id=f"topic-{i}",
                published_at=datetime.utcnow()
            )

        for i in range(3):
            source_cache.save_source(
                url=f"https://reuters.com/article-{i}",
                title=f"Article {i}",
                content="Content...",
                topic_id=f"topic-{i}",
                published_at=datetime.utcnow()
            )

        stats = source_cache.get_stats()

        assert stats['total_sources'] == 8
        assert stats['avg_quality'] > 0.8  # High-quality sources
        assert stats['stale_count'] == 0  # All fresh
        assert stats['fresh_count'] == 8
        assert len(stats['top_domains']) >= 2
        assert stats['top_domains'][0]['domain'] == 'nytimes.com'  # Most sources
        assert stats['top_domains'][0]['count'] == 5

    # Test 10: Multiple topics using same source
    def test_multiple_topics_same_source(self, source_cache):
        """Multiple topics can use the same source (deduplication)"""
        # Topic 1 saves source
        source_cache.save_source(
            url="https://test.com/popular",
            title="Popular Article",
            content="This article is used by multiple topics...",
            topic_id="topic-1"
        )

        # Topic 2 uses same source
        source_cache.save_source(
            url="https://test.com/popular",
            title="Popular Article",
            content="This article is used by multiple topics...",
            topic_id="topic-2"
        )

        # Topic 3 uses same source
        source_cache.save_source(
            url="https://test.com/popular",
            title="Popular Article",
            content="This article is used by multiple topics...",
            topic_id="topic-3"
        )

        # Verify deduplication
        cached = source_cache.get_source("https://test.com/popular")
        assert cached['fetch_count'] == 3  # Fetched 3 times (tracked)
        assert cached['usage_count'] == 3  # Used by 3 topics
        assert len(cached['topic_ids']) == 3

        # Quality score should be influenced by usage (3 uses = log10(4)/log10(100) = 0.30)
        assert cached['quality_score'] > 0.45  # Base + usage component

    # Test 11: Content preview truncation
    def test_content_preview_truncation(self, source_cache):
        """Content is truncated to 500 chars for preview"""
        long_content = "A" * 1000  # 1000 chars

        source_cache.save_source(
            url="https://test.com/long",
            title="Long Article",
            content=long_content,
            topic_id="topic-1"
        )

        cached = source_cache.get_source("https://test.com/long")
        assert len(cached['content_preview']) == 500

    # Test 12: Quality score recalculation on update
    def test_quality_score_recalculation(self, source_cache):
        """Quality score recalculated when source is updated"""
        # Save initial source (1 use)
        result1 = source_cache.save_source(
            url="https://test.com/article",
            title="Article",
            content="Content...",
            topic_id="topic-1",
            published_at=datetime.utcnow()
        )
        initial_score = result1['quality_score']

        # Update with more usage (should increase score due to usage_popularity)
        for i in range(2, 11):  # 9 more topics = 10 total
            source_cache.save_source(
                url="https://test.com/article",
                title="Article",
                content="Content...",
                topic_id=f"topic-{i}",
                published_at=datetime.utcnow()
            )

        cached = source_cache.get_source("https://test.com/article")
        final_score = cached['quality_score']

        # Score should increase with usage
        assert final_score > initial_score

    # Test 13: E-E-A-T signals completeness
    def test_e_e_a_t_signals_completeness(self, source_cache):
        """E-E-A-T signals contain all required fields"""
        result = source_cache.save_source(
            url="https://nytimes.com/test",
            title="Test Article",
            content="Content...",
            topic_id="topic-1",
            published_at=datetime.utcnow()
        )

        signals = result['e_e_a_t_signals']
        assert 'domain_authority' in signals
        assert 'publication_type' in signals
        assert 'publication_score' in signals
        assert 'freshness' in signals
        assert 'usage_popularity' in signals
        assert 'days_old' in signals

        # Verify ranges
        assert 0 <= signals['domain_authority'] <= 1
        assert 0 <= signals['publication_score'] <= 1
        assert 0 <= signals['freshness'] <= 1
        assert 0 <= signals['usage_popularity'] <= 1
