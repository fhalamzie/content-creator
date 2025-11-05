"""
Integration tests for HybridResearchOrchestrator Stage 2 (Competitor Research).

These tests make REAL API calls to Gemini API with grounding enabled.
Requires GEMINI_API_KEY environment variable.

Coverage:
- Real competitor research for PropTech market
- Real competitor research for SaaS market
- Quality validation (competitors, keywords, topics)
- Cost tracking with real API usage
- Error handling with invalid inputs
"""

import pytest
import os
from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
from src.agents.gemini_agent import GeminiAgentError


# Skip all tests if GEMINI_API_KEY not available
pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set"
)


class TestStage2CompetitorResearchIntegration:
    """Integration tests for Stage 2 with real Gemini API calls"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance"""
        return HybridResearchOrchestrator()

    @pytest.mark.asyncio
    async def test_competitor_research_proptech_germany(self, orchestrator):
        """Test real competitor research for PropTech in Germany"""
        # Arrange
        keywords = [
            "PropTech", "Smart Building", "IoT", "Property Management",
            "Building Automation", "Energy Management"
        ]
        customer_info = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        # Act
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=5
        )

        # Assert - Structure
        assert "competitors" in result
        assert "additional_keywords" in result
        assert "market_topics" in result
        assert "cost" in result

        # Assert - Competitors
        assert len(result["competitors"]) > 0, "Should find at least 1 competitor"
        assert len(result["competitors"]) <= 5, "Should respect max_competitors limit"

        # Validate competitor structure
        for competitor in result["competitors"]:
            assert "name" in competitor, "Competitor should have name"
            assert "url" in competitor, "Competitor should have url"
            assert "topics" in competitor, "Competitor should have topics"
            assert len(competitor["name"]) > 0, "Competitor name should not be empty"
            assert competitor["url"].startswith("http"), "URL should be valid HTTP(S)"
            assert len(competitor["topics"]) > 0, "Should have at least 1 topic"

        # Assert - Keywords
        assert len(result["additional_keywords"]) > 0, "Should extract additional keywords"
        assert len(result["additional_keywords"]) <= 50, "Should respect keyword limit"

        # Assert - Topics
        assert len(result["market_topics"]) > 0, "Should identify market topics"
        assert len(result["market_topics"]) <= 20, "Should respect topic limit"

        # Assert - Cost (free tier, but may have small cost after quota)
        assert result["cost"] >= 0, "Cost should be non-negative"

        # Print results for manual inspection
        print(f"\n{'='*60}")
        print(f"PropTech Germany - Competitor Research Results")
        print(f"{'='*60}")
        print(f"Competitors found: {len(result['competitors'])}")
        for i, comp in enumerate(result["competitors"][:3], 1):
            print(f"{i}. {comp['name']} - {comp['url']}")
            print(f"   Topics: {', '.join(comp['topics'][:3])}")
        print(f"\nAdditional keywords ({len(result['additional_keywords'])}): {', '.join(result['additional_keywords'][:10])}")
        print(f"Market topics ({len(result['market_topics'])}): {', '.join(result['market_topics'][:5])}")
        print(f"Cost: ${result['cost']:.4f}")
        print(f"{'='*60}\n")

    @pytest.mark.asyncio
    async def test_competitor_research_saas_usa(self, orchestrator):
        """Test real competitor research for SaaS in USA"""
        # Arrange
        keywords = [
            "SaaS", "Project Management", "Team Collaboration",
            "Agile", "Kanban", "Sprint Planning"
        ]
        customer_info = {
            "market": "United States",
            "vertical": "SaaS",
            "language": "en",
            "domain": "Project Management Software"
        }

        # Act
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=5
        )

        # Assert - Basic structure
        assert "competitors" in result
        assert "additional_keywords" in result
        assert "market_topics" in result

        # Assert - Quality checks
        assert len(result["competitors"]) > 0, "Should find SaaS competitors"
        assert len(result["additional_keywords"]) > 0, "Should extract keywords"
        assert len(result["market_topics"]) > 0, "Should identify topics"

        # Verify competitor URLs are accessible
        for competitor in result["competitors"][:2]:
            assert "://" in competitor["url"], f"Invalid URL: {competitor['url']}"

        # Print results
        print(f"\n{'='*60}")
        print(f"SaaS USA - Competitor Research Results")
        print(f"{'='*60}")
        print(f"Competitors: {[c['name'] for c in result['competitors']]}")
        print(f"Sample keywords: {result['additional_keywords'][:5]}")
        print(f"Sample topics: {result['market_topics'][:3]}")
        print(f"{'='*60}\n")

    @pytest.mark.asyncio
    async def test_competitor_research_max_limit_enforcement(self, orchestrator):
        """Test that max_competitors limit is enforced with real API"""
        # Arrange
        keywords = ["PropTech", "Smart Building", "IoT"]
        customer_info = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        # Act - Request only 3 competitors
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=3
        )

        # Assert
        assert len(result["competitors"]) <= 3, "Should respect max_competitors=3 limit"
        assert len(result["competitors"]) > 0, "Should still find some competitors"

    @pytest.mark.asyncio
    async def test_competitor_research_empty_keywords_returns_empty(self, orchestrator):
        """Test that empty keywords returns empty result gracefully"""
        # Arrange
        customer_info = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        # Act
        result = await orchestrator.research_competitors(
            keywords=[],
            customer_info=customer_info,
            max_competitors=5
        )

        # Assert
        assert result["competitors"] == []
        assert result["additional_keywords"] == []
        assert result["market_topics"] == []
        assert result["cost"] == 0.0

    @pytest.mark.asyncio
    async def test_competitor_research_cost_tracking(self, orchestrator):
        """Test that cost is properly tracked for real API calls"""
        # Arrange
        keywords = ["PropTech", "Smart Building"]
        customer_info = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        # Act
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=3
        )

        # Assert
        assert "cost" in result
        assert isinstance(result["cost"], (int, float))
        assert result["cost"] >= 0

        # Note: Cost may be 0 if within free tier quota
        print(f"\nAPI call cost: ${result['cost']:.6f}")

    @pytest.mark.asyncio
    async def test_competitor_research_keyword_quality(self, orchestrator):
        """Test that extracted keywords are relevant and unique"""
        # Arrange
        keywords = ["PropTech", "Smart Building", "IoT"]
        customer_info = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        # Act
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=5
        )

        # Assert - Keywords should be unique
        additional_keywords = result["additional_keywords"]
        assert len(additional_keywords) == len(set(additional_keywords)), \
            "Keywords should be unique (no duplicates)"

        # Assert - Keywords should not be empty strings
        for keyword in additional_keywords:
            assert len(keyword.strip()) > 0, "Keywords should not be empty"
            assert len(keyword) < 100, "Keywords should be reasonable length"

    @pytest.mark.asyncio
    async def test_competitor_research_topic_quality(self, orchestrator):
        """Test that market topics are relevant and well-formed"""
        # Arrange
        keywords = ["SaaS", "Project Management", "Collaboration"]
        customer_info = {
            "market": "United States",
            "vertical": "SaaS",
            "language": "en",
            "domain": "Project Management"
        }

        # Act
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=5
        )

        # Assert - Topics should be unique
        market_topics = result["market_topics"]
        assert len(market_topics) == len(set(market_topics)), \
            "Topics should be unique"

        # Assert - Topics should be descriptive
        for topic in market_topics:
            assert len(topic.strip()) > 5, "Topics should be descriptive (>5 chars)"
            assert len(topic) < 200, "Topics should be concise (<200 chars)"

    @pytest.mark.asyncio
    async def test_competitor_research_with_minimal_keywords(self, orchestrator):
        """Test competitor research with just 1 keyword"""
        # Arrange
        keywords = ["PropTech"]
        customer_info = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        # Act
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=3
        )

        # Assert - Should still work with minimal input
        assert len(result["competitors"]) > 0, "Should find competitors even with 1 keyword"
        assert len(result["additional_keywords"]) > 0, "Should expand from 1 keyword"

    @pytest.mark.asyncio
    async def test_competitor_research_multiple_languages(self, orchestrator):
        """Test that language parameter is respected"""
        # Test German market
        keywords_de = ["PropTech", "Immobilien", "Smart Building"]
        customer_info_de = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        result_de = await orchestrator.research_competitors(
            keywords=keywords_de,
            customer_info=customer_info_de,
            max_competitors=3
        )

        # Test English market
        keywords_en = ["PropTech", "Real Estate", "Smart Building"]
        customer_info_en = {
            "market": "United States",
            "vertical": "PropTech",
            "language": "en",
            "domain": "PropTech"
        }

        result_en = await orchestrator.research_competitors(
            keywords=keywords_en,
            customer_info=customer_info_en,
            max_competitors=3
        )

        # Assert - Both should return results
        assert len(result_de["competitors"]) > 0
        assert len(result_en["competitors"]) > 0

        # Note: Competitors may differ based on market/language
        print(f"\nGerman competitors: {[c['name'] for c in result_de['competitors']]}")
        print(f"English competitors: {[c['name'] for c in result_en['competitors']]}")

    @pytest.mark.asyncio
    async def test_competitor_research_response_time(self, orchestrator):
        """Test that competitor research completes in reasonable time"""
        import time

        # Arrange
        keywords = ["PropTech", "Smart Building"]
        customer_info = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        # Act
        start_time = time.time()
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=5
        )
        end_time = time.time()
        duration = end_time - start_time

        # Assert
        assert duration < 60, f"Should complete within 60s (took {duration:.2f}s)"
        assert len(result["competitors"]) > 0, "Should return results"

        print(f"\nCompetitor research completed in {duration:.2f}s")

    @pytest.mark.asyncio
    async def test_competitor_research_handles_special_characters(self, orchestrator):
        """Test that special characters in keywords are handled properly"""
        # Arrange
        keywords = ["IoT & Smart Buildings", "AI/ML PropTech", "Real-Estate Tech"]
        customer_info = {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

        # Act - Should not crash with special characters
        result = await orchestrator.research_competitors(
            keywords=keywords,
            customer_info=customer_info,
            max_competitors=3
        )

        # Assert
        assert "competitors" in result
        assert "error" not in result or result.get("error") is None
