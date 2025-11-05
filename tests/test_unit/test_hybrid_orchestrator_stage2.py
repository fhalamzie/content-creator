"""
Unit tests for HybridResearchOrchestrator Stage 2 (Competitor Research).

Tests the research_competitors() method which uses Gemini API with grounding
to identify competitors, extract additional keywords, and discover market topics.

Coverage:
- Successful competitor research with grounding
- Response parsing and limit enforcement
- Error handling (Gemini API failures)
- Empty/invalid input handling
- Cost tracking
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
from src.agents.gemini_agent import GeminiAgentError


@pytest.fixture(autouse=True)
def mock_gemini_api_key(monkeypatch):
    """Set fake GEMINI_API_KEY for all tests"""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key-12345")


class TestStage2CompetitorResearch:
    """Test Stage 2: Competitor Research"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance"""
        return HybridResearchOrchestrator()

    @pytest.fixture
    def stage1_output(self):
        """Sample Stage 1 output"""
        return {
            "keywords": ["PropTech", "Smart Building", "IoT", "Property Management"],
            "tags": ["real estate", "technology", "automation"],
            "themes": ["Digital transformation", "Sustainability"],
            "tone": ["innovative", "professional"],
            "setting": ["B2B", "SaaS"],
            "niche": ["commercial real estate"],
            "domain": "PropTech"
        }

    @pytest.fixture
    def customer_info(self):
        """Sample customer info"""
        return {
            "market": "Germany",
            "vertical": "PropTech",
            "language": "de",
            "domain": "PropTech"
        }

    @pytest.mark.asyncio
    async def test_research_competitors_success(self, orchestrator, stage1_output, customer_info):
        """Test successful competitor research"""
        # Mock Gemini agent
        mock_response = {
            "content": {
                "competitors": [
                    {"name": "Allthings", "url": "https://allthings.me", "topics": ["Tenant Engagement", "PropTech"]},
                    {"name": "Smarter.Homes", "url": "https://smarter.homes", "topics": ["Smart Home", "IoT"]},
                    {"name": "KIWI.KI", "url": "https://kiwi.ki", "topics": ["Access Control", "Smart Building"]}
                ],
                "additional_keywords": [
                    "tenant engagement", "smart access", "building analytics",
                    "facility management", "predictive maintenance"
                ],
                "market_topics": [
                    "AI in property management",
                    "Sustainable buildings",
                    "Smart city integration"
                ]
            },
            "cost": 0.0
        }

        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response

            # Call Stage 2
            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify result structure
        assert "competitors" in result
        assert "additional_keywords" in result
        assert "market_topics" in result
        assert "cost" in result

        # Verify data
        assert len(result["competitors"]) == 3
        assert result["competitors"][0]["name"] == "Allthings"
        assert len(result["additional_keywords"]) == 5
        assert len(result["market_topics"]) == 3
        assert result["cost"] == 0.0

    @pytest.mark.asyncio
    async def test_research_competitors_max_limit_enforcement(self, orchestrator, stage1_output, customer_info):
        """Test that max_competitors limit is enforced"""
        # Mock Gemini agent with 15 competitors
        competitors_list = [
            {"name": f"Competitor {i}", "url": f"https://comp{i}.com", "topics": ["PropTech"]}
            for i in range(15)
        ]

        mock_response = {
            "content": {
                "competitors": competitors_list,
                "additional_keywords": ["keyword1", "keyword2"],
                "market_topics": ["topic1"]
            },
            "cost": 0.0
        }

        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response

            # Call Stage 2 with max_competitors=5
            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=5
            )

        # Verify limit enforcement
        assert len(result["competitors"]) == 5

    @pytest.mark.asyncio
    async def test_research_competitors_empty_keywords(self, orchestrator, customer_info):
        """Test Stage 2 with empty keywords list"""
        result = await orchestrator.research_competitors(
            keywords=[],
            customer_info=customer_info,
            max_competitors=10
        )

        # Should still return empty structure (not crash)
        assert result["competitors"] == []
        assert result["additional_keywords"] == []
        assert result["market_topics"] == []
        assert result["cost"] == 0.0

    @pytest.mark.asyncio
    async def test_research_competitors_gemini_error(self, orchestrator, stage1_output, customer_info):
        """Test error handling when Gemini API fails"""
        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = GeminiAgentError("API rate limit exceeded")

            # Call Stage 2
            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify graceful error handling
        assert "error" in result
        assert "API rate limit exceeded" in result["error"]
        assert result["competitors"] == []
        assert result["additional_keywords"] == []
        assert result["market_topics"] == []

    @pytest.mark.asyncio
    async def test_research_competitors_missing_fields(self, orchestrator, stage1_output, customer_info):
        """Test handling of incomplete Gemini response"""
        # Mock response missing some fields
        mock_response = {
            "content": {
                "competitors": [
                    {"name": "Allthings", "url": "https://allthings.me"}
                    # Missing 'topics' field
                ],
                # Missing 'additional_keywords' field
                "market_topics": ["AI in PropTech"]
            },
            "cost": 0.0
        }

        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response

            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify defaults are used
        assert len(result["competitors"]) == 1
        assert result["additional_keywords"] == []  # Default
        assert len(result["market_topics"]) == 1

    @pytest.mark.asyncio
    async def test_research_competitors_json_string_parsing(self, orchestrator, stage1_output, customer_info):
        """Test parsing when content is JSON string (not dict)"""
        import json

        # Mock response with JSON string
        content_dict = {
            "competitors": [{"name": "Test", "url": "https://test.com", "topics": ["PropTech"]}],
            "additional_keywords": ["keyword1"],
            "market_topics": ["topic1"]
        }

        mock_response = {
            "content": json.dumps(content_dict),  # JSON string
            "cost": 0.0
        }

        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response

            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify parsing succeeded
        assert len(result["competitors"]) == 1
        assert result["competitors"][0]["name"] == "Test"

    @pytest.mark.asyncio
    async def test_research_competitors_cost_tracking(self, orchestrator, stage1_output, customer_info):
        """Test that cost is properly tracked"""
        mock_response = {
            "content": {
                "competitors": [],
                "additional_keywords": [],
                "market_topics": []
            },
            "cost": 0.00123  # Small cost from Gemini API
        }

        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response

            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify cost is tracked
        assert result["cost"] == 0.00123

    @pytest.mark.asyncio
    async def test_research_competitors_grounding_enabled(self, orchestrator, stage1_output, customer_info):
        """Test that Gemini agent is called with grounding enabled"""
        mock_response = {
            "content": {
                "competitors": [],
                "additional_keywords": [],
                "market_topics": []
            },
            "cost": 0.0
        }

        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response

            await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify gemini_agent.generate was called
        assert mock_generate.called

        # Verify response_schema was provided (for structured output)
        call_kwargs = mock_generate.call_args[1]
        assert "response_schema" in call_kwargs

    @pytest.mark.asyncio
    async def test_research_competitors_keyword_limit_50(self, orchestrator, stage1_output, customer_info):
        """Test that additional_keywords are limited to 50"""
        # Mock response with 70 keywords
        keywords_list = [f"keyword_{i}" for i in range(70)]

        mock_response = {
            "content": {
                "competitors": [],
                "additional_keywords": keywords_list,
                "market_topics": []
            },
            "cost": 0.0
        }

        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response

            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify limit enforcement
        assert len(result["additional_keywords"]) == 50

    @pytest.mark.asyncio
    async def test_research_competitors_topic_limit_20(self, orchestrator, stage1_output, customer_info):
        """Test that market_topics are limited to 20"""
        # Mock response with 30 topics
        topics_list = [f"topic_{i}" for i in range(30)]

        mock_response = {
            "content": {
                "competitors": [],
                "additional_keywords": [],
                "market_topics": topics_list
            },
            "cost": 0.0
        }

        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response

            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify limit enforcement
        assert len(result["market_topics"]) == 20

    @pytest.mark.asyncio
    async def test_research_competitors_exception_handling(self, orchestrator, stage1_output, customer_info):
        """Test generic exception handling"""
        with patch.object(orchestrator.gemini_agent, 'generate', new_callable=AsyncMock) as mock_generate:
            mock_generate.side_effect = Exception("Unexpected error")

            result = await orchestrator.research_competitors(
                keywords=stage1_output["keywords"],
                customer_info=customer_info,
                max_competitors=10
            )

        # Verify graceful error handling
        assert "error" in result
        assert "Unexpected error" in result["error"]
        assert result["cost"] == 0.0
