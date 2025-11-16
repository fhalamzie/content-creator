"""
Integration tests for DeepResearcher with source caching

Tests cache-first research flow, cost tracking, and statistics.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.research.deep_researcher import DeepResearcher, DeepResearchError
from src.database.sqlite_manager import SQLiteManager
from src.research.source_cache import SourceCache


@pytest.fixture
def test_db():
    """Create test database"""
    import tempfile
    import os

    db_path = tempfile.mktemp(suffix=".db")
    db = SQLiteManager(db_path)
    yield db
    os.unlink(db_path)


@pytest.fixture
def researcher_with_cache(test_db):
    """Create DeepResearcher with caching enabled"""
    return DeepResearcher(db_manager=test_db)


@pytest.fixture
def researcher_without_cache():
    """Create DeepResearcher without caching"""
    return DeepResearcher(db_manager=None)


class TestDeepResearcherCacheIntegration:
    """Test suite for DeepResearcher with source caching"""

    @pytest.mark.asyncio
    async def test_caching_enabled_when_db_manager_provided(self, researcher_with_cache):
        """Verify source cache is enabled when db_manager is provided"""
        assert researcher_with_cache.source_cache is not None
        assert isinstance(researcher_with_cache.source_cache, SourceCache)
        assert researcher_with_cache.cache_hits == 0
        assert researcher_with_cache.cache_misses == 0

    @pytest.mark.asyncio
    async def test_caching_disabled_when_db_manager_not_provided(self, researcher_without_cache):
        """Verify source cache is disabled when db_manager is None"""
        assert researcher_without_cache.source_cache is None
        stats = researcher_without_cache.get_statistics()
        assert stats['caching_enabled'] is False

    @pytest.mark.asyncio
    async def test_sources_saved_to_cache_after_research(self, researcher_with_cache):
        """Test that sources are saved to cache after successful research"""
        # Mock gpt-researcher
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            # Setup mock
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="Test report content with detailed analysis.")
            mock_instance.get_source_urls = Mock(return_value=[
                "https://nytimes.com/article-1",
                "https://bbc.com/news/article-2",
                "https://techcrunch.com/article-3"
            ])
            mock_gpt.return_value = mock_instance

            # Conduct research
            config = {'domain': 'SaaS', 'market': 'Germany', 'language': 'de'}
            result = await researcher_with_cache.research_topic("PropTech Trends", config)

            # Verify sources returned
            assert len(result['sources']) == 3
            assert result['sources'][0] == "https://nytimes.com/article-1"

            # Verify sources saved to cache (all new, no hits)
            assert researcher_with_cache.cache_hits == 0
            assert researcher_with_cache.cache_misses == 3

            # Verify sources in database
            cache = researcher_with_cache.source_cache
            cached_source = cache.get_source("https://nytimes.com/article-1")
            assert cached_source is not None
            assert cached_source['url'] == "https://nytimes.com/article-1"
            assert 'nytimes.com' in cached_source['domain']

    @pytest.mark.asyncio
    async def test_cache_hit_when_source_already_exists(self, researcher_with_cache, test_db):
        """Test cache hit detection when source already in cache"""
        # Pre-populate cache with a source
        cache = SourceCache(test_db)
        cache.save_source(
            url="https://nytimes.com/article-1",
            title="Existing Article",
            content="Pre-existing content",
            topic_id="previous-topic"
        )

        # Mock gpt-researcher to return same source + new source
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="New report content.")
            mock_instance.get_source_urls = Mock(return_value=[
                "https://nytimes.com/article-1",  # Already cached
                "https://bbc.com/news/article-2"   # New source
            ])
            mock_gpt.return_value = mock_instance

            # Conduct research
            config = {'domain': 'SaaS', 'market': 'Germany'}
            result = await researcher_with_cache.research_topic("PropTech 2025", config)

            # Verify cache statistics
            assert researcher_with_cache.cache_hits == 1  # NYT article was cached
            assert researcher_with_cache.cache_misses == 1  # BBC article is new
            assert researcher_with_cache.api_calls_saved == 1

            # Verify cache hit rate
            stats = researcher_with_cache.get_statistics()
            assert stats['cache_hit_rate'] == 50.0  # 1/2 sources cached

    @pytest.mark.asyncio
    async def test_multiple_topics_share_sources(self, researcher_with_cache):
        """Test that multiple topics can share cached sources"""
        # Mock gpt-researcher for first topic
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="First report.")
            mock_instance.get_source_urls = Mock(return_value=[
                "https://nytimes.com/proptech",
                "https://techcrunch.com/smart-buildings"
            ])
            mock_gpt.return_value = mock_instance

            # Research Topic A
            config = {'domain': 'SaaS'}
            await researcher_with_cache.research_topic("PropTech Trends", config)

            # Stats after Topic A
            assert researcher_with_cache.cache_hits == 0
            assert researcher_with_cache.cache_misses == 2

        # Mock gpt-researcher for second topic (overlapping sources)
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="Second report.")
            mock_instance.get_source_urls = Mock(return_value=[
                "https://nytimes.com/proptech",  # Same as Topic A
                "https://bbc.com/real-estate"    # New source
            ])
            mock_gpt.return_value = mock_instance

            # Research Topic B
            await researcher_with_cache.research_topic("Smart Buildings", config)

            # Stats after Topic B (cumulative)
            assert researcher_with_cache.cache_hits == 1  # NYT shared
            assert researcher_with_cache.cache_misses == 3  # 2 from A + 1 new from B
            assert researcher_with_cache.api_calls_saved == 1

            # Verify cache hit rate
            stats = researcher_with_cache.get_statistics()
            assert stats['cache_hit_rate'] == 25.0  # 1/4 total sources cached

    @pytest.mark.asyncio
    async def test_slugify_topic_generates_valid_ids(self, researcher_with_cache):
        """Test topic slugification for cache keys"""
        assert researcher_with_cache._slugify_topic("PropTech Trends 2025") == "proptech-trends-2025"
        assert researcher_with_cache._slugify_topic("Smart Buildings: AI Edition") == "smart-buildings-ai-edition"
        assert researcher_with_cache._slugify_topic("SaaS & Cloud Computing!") == "saas-cloud-computing"

    @pytest.mark.asyncio
    async def test_cache_statistics_in_get_statistics(self, researcher_with_cache):
        """Test that cache statistics are included in get_statistics()"""
        # Mock research
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="Report")
            mock_instance.get_source_urls = Mock(return_value=[
                "https://nytimes.com/article"
            ])
            mock_gpt.return_value = mock_instance

            await researcher_with_cache.research_topic("Test Topic", {'domain': 'Tech'})

        # Get statistics
        stats = researcher_with_cache.get_statistics()

        # Verify cache stats included
        assert 'caching_enabled' in stats
        assert stats['caching_enabled'] is True
        assert 'cache_hits' in stats
        assert 'cache_misses' in stats
        assert 'cache_hit_rate' in stats
        assert 'api_calls_saved' in stats
        assert stats['cache_misses'] == 1

    @pytest.mark.asyncio
    async def test_reset_statistics_clears_cache_stats(self, researcher_with_cache):
        """Test that reset_statistics() clears cache statistics"""
        # Set some stats manually
        researcher_with_cache.cache_hits = 10
        researcher_with_cache.cache_misses = 5
        researcher_with_cache.api_calls_saved = 10

        # Reset
        researcher_with_cache.reset_statistics()

        # Verify all reset
        assert researcher_with_cache.cache_hits == 0
        assert researcher_with_cache.cache_misses == 0
        assert researcher_with_cache.api_calls_saved == 0

    @pytest.mark.asyncio
    async def test_cache_marks_usage_for_topics(self, researcher_with_cache, test_db):
        """Test that cache tracks which topics use which sources"""
        # Mock research for Topic A
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="Report A")
            mock_instance.get_source_urls = Mock(return_value=["https://nytimes.com/shared"])
            mock_gpt.return_value = mock_instance

            await researcher_with_cache.research_topic("Topic A", {'domain': 'Tech'})

        # Mock research for Topic B (same source)
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="Report B")
            mock_instance.get_source_urls = Mock(return_value=["https://nytimes.com/shared"])
            mock_gpt.return_value = mock_instance

            await researcher_with_cache.research_topic("Topic B", {'domain': 'SaaS'})

        # Verify source usage tracking
        cache = researcher_with_cache.source_cache
        source = cache.get_source("https://nytimes.com/shared")
        assert source is not None
        assert source['usage_count'] == 2  # Used by 2 topics
        assert 'topic-a' in source['topic_ids']
        assert 'topic-b' in source['topic_ids']

    @pytest.mark.asyncio
    async def test_extract_source_context(self, researcher_with_cache):
        """Test source context extraction from report"""
        report = "This is a comprehensive report about PropTech trends in Germany. " * 20
        context = researcher_with_cache._extract_source_context(report, "nytimes.com")

        # Should be truncated to 500 chars
        assert len(context) <= 500
        assert "PropTech" in context or len(context) == 500

    @pytest.mark.asyncio
    async def test_caching_disabled_does_not_save_sources(self, researcher_without_cache):
        """Test that sources are NOT saved when caching disabled"""
        # Mock research
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="Report")
            mock_instance.get_source_urls = Mock(return_value=[
                "https://nytimes.com/article"
            ])
            mock_gpt.return_value = mock_instance

            result = await researcher_without_cache.research_topic("Test", {'domain': 'Tech'})

            # Verify sources returned but stats not tracked
            assert len(result['sources']) == 1
            assert researcher_without_cache.cache_hits == 0
            assert researcher_without_cache.cache_misses == 0

            # Stats should not include cache info
            stats = researcher_without_cache.get_statistics()
            assert stats['caching_enabled'] is False
            assert 'cache_hits' not in stats

    @pytest.mark.asyncio
    async def test_high_cache_hit_rate_scenario(self, researcher_with_cache):
        """Test scenario with high cache hit rate (cost savings)"""
        # Pre-populate cache with common sources
        cache = researcher_with_cache.source_cache
        common_sources = [
            "https://nytimes.com/proptech",
            "https://techcrunch.com/saas",
            "https://bbc.com/technology"
        ]
        for url in common_sources:
            cache.save_source(url, f"Article from {url}", "Content", "seed-topic")

        # Mock research that returns mostly cached sources
        with patch('src.research.deep_researcher.GPTResearcher') as mock_gpt:
            mock_instance = AsyncMock()
            mock_instance.conduct_research = AsyncMock()
            mock_instance.write_report = AsyncMock(return_value="Report")
            mock_instance.get_source_urls = Mock(return_value=[
                "https://nytimes.com/proptech",    # Cached
                "https://techcrunch.com/saas",     # Cached
                "https://bbc.com/technology",      # Cached
                "https://wired.com/new-article"    # New
            ])
            mock_gpt.return_value = mock_instance

            await researcher_with_cache.research_topic("PropTech", {'domain': 'SaaS'})

            # Verify high cache hit rate
            stats = researcher_with_cache.get_statistics()
            assert stats['cache_hits'] == 3
            assert stats['cache_misses'] == 1
            assert stats['cache_hit_rate'] == 75.0  # 3/4 cached
            assert stats['api_calls_saved'] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
