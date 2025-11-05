"""
Unit tests for HybridResearchOrchestrator Stage 3: Consolidation

Tests the `consolidate_keywords_and_topics()` method which combines
keywords and tags from Stage 1 (website) and Stage 2 (competitor research)
into a unified topic list.

TDD approach: Write tests first, run (fail), then ensure implementation passes.
"""

import pytest
from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator


class TestStage3Consolidation:
    """Unit tests for Stage 3: consolidate_keywords_and_topics()"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance (no API calls needed for Stage 3)"""
        return HybridResearchOrchestrator()

    def test_consolidate_combines_all_keywords(self, orchestrator):
        """Test that consolidation combines website + competitor keywords"""
        website_data = {
            "keywords": ["PropTech", "Smart Building", "IoT"],
            "tags": ["Real Estate Tech"],
            "themes": ["Innovation"],
            "cost": 0.0
        }

        competitor_data = {
            "competitors": [],
            "additional_keywords": ["Property Management", "Building Automation"],
            "market_topics": ["Smart Cities"],
            "cost": 0.0
        }

        result = orchestrator.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # Should combine all keywords (website + competitor)
        expected_keywords = {
            "PropTech", "Smart Building", "IoT",
            "Property Management", "Building Automation"
        }
        assert set(result["consolidated_keywords"]) == expected_keywords

    def test_consolidate_combines_all_tags(self, orchestrator):
        """Test that consolidation combines tags, themes, and market topics"""
        website_data = {
            "keywords": [],
            "tags": ["Real Estate Tech", "IoT"],
            "themes": ["Innovation", "Sustainability"],
            "cost": 0.0
        }

        competitor_data = {
            "competitors": [],
            "additional_keywords": [],
            "market_topics": ["Smart Cities", "Green Building"],
            "cost": 0.0
        }

        result = orchestrator.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # Should combine tags + themes + market_topics
        expected_tags = {
            "Real Estate Tech", "IoT",
            "Innovation", "Sustainability",
            "Smart Cities", "Green Building"
        }
        assert set(result["consolidated_tags"]) == expected_tags

    def test_consolidate_removes_duplicates(self, orchestrator):
        """Test that consolidation removes duplicate keywords/tags"""
        website_data = {
            "keywords": ["PropTech", "IoT", "Smart Building"],
            "tags": ["PropTech", "Real Estate"],
            "themes": [],
            "cost": 0.0
        }

        competitor_data = {
            "competitors": [],
            "additional_keywords": ["IoT", "PropTech", "AI"],  # Duplicates
            "market_topics": ["PropTech", "Smart Homes"],  # More duplicates
            "cost": 0.0
        }

        result = orchestrator.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # Keywords should be deduplicated
        assert len(result["consolidated_keywords"]) == 4  # PropTech, IoT, Smart Building, AI
        assert "PropTech" in result["consolidated_keywords"]
        assert "IoT" in result["consolidated_keywords"]

        # Tags should be deduplicated
        assert len(result["consolidated_tags"]) == 3  # PropTech, Real Estate, Smart Homes

    def test_consolidate_priority_topics_from_market_trends(self, orchestrator):
        """Test that priority_topics includes top market trends first"""
        website_data = {
            "keywords": [],
            "tags": [],
            "themes": ["Theme1", "Theme2", "Theme3"],
            "cost": 0.0
        }

        competitor_data = {
            "competitors": [],
            "additional_keywords": [],
            "market_topics": ["Topic1", "Topic2", "Topic3", "Topic4", "Topic5", "Topic6"],
            "cost": 0.0
        }

        result = orchestrator.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # priority_topics should contain:
        # - First 5 market_topics
        # - First 3 themes
        assert "priority_topics" in result
        assert len(result["priority_topics"]) == 8  # 5 market + 3 themes

        # First 5 should be market topics (in order)
        assert result["priority_topics"][:5] == [
            "Topic1", "Topic2", "Topic3", "Topic4", "Topic5"
        ]

        # Next 3 should be themes
        assert set(result["priority_topics"][5:]) == {"Theme1", "Theme2", "Theme3"}

    def test_consolidate_handles_empty_website_data(self, orchestrator):
        """Test that consolidation works with empty website data"""
        website_data = {
            "keywords": [],
            "tags": [],
            "themes": [],
            "cost": 0.0
        }

        competitor_data = {
            "competitors": [],
            "additional_keywords": ["Keyword1", "Keyword2"],
            "market_topics": ["Topic1"],
            "cost": 0.0
        }

        result = orchestrator.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # Should still consolidate competitor data
        assert len(result["consolidated_keywords"]) == 2
        assert len(result["consolidated_tags"]) == 1
        assert "Keyword1" in result["consolidated_keywords"]

    def test_consolidate_handles_empty_competitor_data(self, orchestrator):
        """Test that consolidation works with empty competitor data"""
        website_data = {
            "keywords": ["Keyword1", "Keyword2"],
            "tags": ["Tag1"],
            "themes": ["Theme1"],
            "cost": 0.0
        }

        competitor_data = {
            "competitors": [],
            "additional_keywords": [],
            "market_topics": [],
            "cost": 0.0
        }

        result = orchestrator.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # Should still consolidate website data
        assert len(result["consolidated_keywords"]) == 2
        assert len(result["consolidated_tags"]) == 2  # Tag1 + Theme1
        assert "Keyword1" in result["consolidated_keywords"]

    def test_consolidate_returns_sorted_keywords(self, orchestrator):
        """Test that consolidated keywords are sorted alphabetically"""
        website_data = {
            "keywords": ["Zeta", "Alpha", "Beta"],
            "tags": [],
            "themes": [],
            "cost": 0.0
        }

        competitor_data = {
            "competitors": [],
            "additional_keywords": ["Gamma", "Delta"],
            "market_topics": [],
            "cost": 0.0
        }

        result = orchestrator.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # Keywords should be sorted
        assert result["consolidated_keywords"] == [
            "Alpha", "Beta", "Delta", "Gamma", "Zeta"
        ]

    def test_consolidate_returns_sorted_tags(self, orchestrator):
        """Test that consolidated tags are sorted alphabetically"""
        website_data = {
            "keywords": [],
            "tags": ["Zeta", "Alpha"],
            "themes": ["Beta"],
            "cost": 0.0
        }

        competitor_data = {
            "competitors": [],
            "additional_keywords": [],
            "market_topics": ["Gamma", "Delta"],
            "cost": 0.0
        }

        result = orchestrator.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # Tags should be sorted
        assert result["consolidated_tags"] == [
            "Alpha", "Beta", "Delta", "Gamma", "Zeta"
        ]
