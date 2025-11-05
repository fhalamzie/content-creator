"""
Unit tests for HybridResearchOrchestrator Stage 4: Topic Discovery from Collectors

Tests the `discover_topics_from_collectors()` method which expands keywords
using simulated collector patterns (autocomplete, trends, reddit, rss, news).

TDD approach: Write tests first, run (fail), then ensure implementation passes.
"""

import pytest
from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator


class TestStage4TopicDiscovery:
    """Unit tests for Stage 4: discover_topics_from_collectors()"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance (no API calls needed for Stage 4)"""
        return HybridResearchOrchestrator()

    @pytest.mark.asyncio
    async def test_discover_topics_generates_autocomplete_style_topics(self, orchestrator):
        """Test that discovery generates autocomplete-style questions"""
        keywords = ["PropTech", "Smart Building"]
        tags = ["Innovation"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should have autocomplete topics
        assert "topics_by_source" in result
        assert "autocomplete" in result["topics_by_source"]

        autocomplete_topics = result["topics_by_source"]["autocomplete"]
        assert len(autocomplete_topics) > 0

        # Should have question-style topics
        question_topics = [t for t in autocomplete_topics if any(
            t.startswith(prefix) for prefix in ['how', 'what', 'why', 'when', 'where', 'best']
        )]
        assert len(question_topics) > 0

    @pytest.mark.asyncio
    async def test_discover_topics_generates_trends_style_topics(self, orchestrator):
        """Test that discovery generates trends-style topics"""
        keywords = ["AI", "Machine Learning"]
        tags = ["Technology"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should have trends topics
        assert "trends" in result["topics_by_source"]

        trends_topics = result["topics_by_source"]["trends"]
        assert len(trends_topics) > 0

        # Should have trend-style suffixes
        trend_topics = [t for t in trends_topics if any(
            suffix in t for suffix in ['trends', 'innovations', 'future', 'market analysis']
        )]
        assert len(trend_topics) > 0

    @pytest.mark.asyncio
    async def test_discover_topics_generates_reddit_style_topics(self, orchestrator):
        """Test that discovery generates reddit-style discussion topics"""
        keywords = ["Python", "Django"]
        tags = ["Web Development"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should have reddit topics
        assert "reddit" in result["topics_by_source"]

        reddit_topics = result["topics_by_source"]["reddit"]
        assert len(reddit_topics) > 0

        # Should have discussion-style patterns
        discussion_topics = [t for t in reddit_topics if any(
            pattern in t for pattern in ['discussion', 'questions', 'guide', 'tips']
        )]
        assert len(discussion_topics) > 0

    @pytest.mark.asyncio
    async def test_discover_topics_generates_rss_style_topics(self, orchestrator):
        """Test that discovery generates RSS/blog-style topics"""
        keywords = ["React"]
        tags = ["JavaScript", "Frontend"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should have RSS topics
        assert "rss" in result["topics_by_source"]

        rss_topics = result["topics_by_source"]["rss"]
        assert len(rss_topics) > 0

        # Should have blog-style suffixes
        blog_topics = [t for t in rss_topics if any(
            suffix in t for suffix in ['blog', 'article', 'case study', 'best practices']
        )]
        assert len(blog_topics) > 0

    @pytest.mark.asyncio
    async def test_discover_topics_generates_news_style_topics(self, orchestrator):
        """Test that discovery generates news-style topics"""
        keywords = ["Bitcoin", "Cryptocurrency"]
        tags = ["Finance"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should have news topics
        assert "news" in result["topics_by_source"]

        news_topics = result["topics_by_source"]["news"]
        assert len(news_topics) > 0

        # Should have news-style suffixes
        news_style_topics = [t for t in news_topics if any(
            suffix in t for suffix in ['latest news', 'recent developments', 'updates']
        )]
        assert len(news_style_topics) > 0

    @pytest.mark.asyncio
    async def test_discover_topics_respects_max_topics_per_collector(self, orchestrator):
        """Test that max_topics_per_collector limit is enforced"""
        keywords = ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"]
        tags = ["tag1", "tag2", "tag3"]

        max_limit = 5
        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags,
            max_topics_per_collector=max_limit
        )

        # Each collector should respect the limit
        for source, topics in result["topics_by_source"].items():
            assert len(topics) <= max_limit, f"{source} exceeded limit: {len(topics)} > {max_limit}"

    @pytest.mark.asyncio
    async def test_discover_topics_deduplicates_across_sources(self, orchestrator):
        """Test that discovered topics are deduplicated"""
        keywords = ["PropTech"]
        tags = ["PropTech"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Count total topics across all sources
        total_topics_by_source = sum(
            len(topics) for topics in result["topics_by_source"].values()
        )

        # Deduplicated count should be <= total
        assert result["total_topics"] <= total_topics_by_source

        # discovered_topics should have unique items only
        assert len(result["discovered_topics"]) == len(set(result["discovered_topics"]))

    @pytest.mark.asyncio
    async def test_discover_topics_handles_empty_keywords(self, orchestrator):
        """Test that discovery works with empty keywords"""
        keywords = []
        tags = ["Tag1", "Tag2"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should still work, though fewer topics
        assert "discovered_topics" in result
        assert "topics_by_source" in result

        # RSS topics should still be generated from tags
        assert len(result["topics_by_source"].get("rss", [])) > 0

    @pytest.mark.asyncio
    async def test_discover_topics_handles_empty_tags(self, orchestrator):
        """Test that discovery works with empty tags"""
        keywords = ["Keyword1", "Keyword2"]
        tags = []

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should still work, though fewer RSS topics
        assert "discovered_topics" in result
        assert "topics_by_source" in result

        # Other collectors should still generate topics
        assert len(result["topics_by_source"].get("autocomplete", [])) > 0
        assert len(result["topics_by_source"].get("trends", [])) > 0

    @pytest.mark.asyncio
    async def test_discover_topics_limits_seed_keywords(self, orchestrator):
        """Test that only top 10 keywords are used for discovery"""
        # Provide 20 keywords
        keywords = [f"keyword{i}" for i in range(20)]
        tags = ["tag1"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should have topics generated
        assert result["total_topics"] > 0

        # Verify that topics are generated from top keywords only
        # (implementation uses top 10 keywords, top 5 for most collectors)
        discovered = result["discovered_topics"]

        # Should not have topics for keyword15-keyword19
        topics_from_late_keywords = [
            t for t in discovered
            if any(f"keyword{i}" in t for i in range(15, 20))
        ]
        # Late keywords should not appear (or very few)
        assert len(topics_from_late_keywords) == 0

    @pytest.mark.asyncio
    async def test_discover_topics_returns_sorted_list(self, orchestrator):
        """Test that discovered topics are sorted alphabetically"""
        keywords = ["Zeta", "Alpha", "Beta"]
        tags = ["Gamma"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should be sorted
        discovered = result["discovered_topics"]
        assert discovered == sorted(discovered)

    @pytest.mark.asyncio
    async def test_discover_topics_includes_total_count(self, orchestrator):
        """Test that total_topics matches discovered_topics length"""
        keywords = ["AI", "ML"]
        tags = ["Tech"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Total should match length
        assert result["total_topics"] == len(result["discovered_topics"])

    @pytest.mark.asyncio
    async def test_discover_topics_all_sources_present(self, orchestrator):
        """Test that all 5 collector sources are present"""
        keywords = ["test"]
        tags = ["test"]

        result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags
        )

        # Should have all 5 sources
        assert "autocomplete" in result["topics_by_source"]
        assert "trends" in result["topics_by_source"]
        assert "reddit" in result["topics_by_source"]
        assert "rss" in result["topics_by_source"]
        assert "news" in result["topics_by_source"]
