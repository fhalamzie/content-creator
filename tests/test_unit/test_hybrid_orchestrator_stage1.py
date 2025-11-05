"""
Unit tests for HybridResearchOrchestrator Stage 1 (Website Keyword Extraction)

Tests trafilatura fetching, Gemini analysis, error handling, and limit enforcement.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
from src.agents.gemini_agent import GeminiAgentError


@pytest.fixture
def orchestrator():
    """Create orchestrator instance"""
    return HybridResearchOrchestrator()


@pytest.fixture
def mock_website_content():
    """Mock website content (> 100 chars)"""
    return """
    PropTech Solutions Inc.

    We are a leading provider of smart building technology for commercial real estate.
    Our AI-powered platform helps property managers reduce energy costs by 30%
    through predictive maintenance and intelligent automation.

    Our solutions include:
    - IoT sensor networks for real-time monitoring
    - Machine learning for energy optimization
    - Cloud-based analytics dashboards
    - Mobile apps for facility management

    Serving over 500 buildings across Europe and North America.
    """


@pytest.fixture
def mock_gemini_response_dict():
    """Mock Gemini response as dict"""
    return {
        "content": {
            "keywords": [
                "PropTech", "smart building", "commercial real estate", "property management",
                "energy optimization", "predictive maintenance", "IoT sensors", "machine learning",
                "facility management", "building automation"
            ],
            "tags": ["PropTech", "AI", "IoT", "Energy Management", "Cloud Computing"],
            "themes": ["Cost Reduction", "Sustainability", "Digital Transformation"],
            "tone": ["Professional", "Technical", "Innovative"],
            "setting": ["B2B", "Enterprise", "Commercial"],
            "niche": ["PropTech", "Smart Buildings", "IoT"],
            "domain": "Real Estate Technology"
        },
        "cost": 0.001
    }


@pytest.fixture
def mock_gemini_response_json_string():
    """Mock Gemini response as JSON string"""
    return {
        "content": json.dumps({
            "keywords": ["PropTech", "smart building"],
            "tags": ["PropTech", "AI"],
            "themes": ["Cost Reduction"],
            "tone": ["Professional"],
            "setting": ["B2B"],
            "niche": ["PropTech"],
            "domain": "Technology"
        }),
        "cost": 0.001
    }


class TestStage1WebsiteKeywordExtraction:
    """Test Stage 1: Website keyword extraction"""

    @pytest.mark.asyncio
    async def test_successful_extraction_with_dict_response(
        self, orchestrator, mock_website_content, mock_gemini_response_dict
    ):
        """Test successful extraction with dict response from Gemini"""
        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('src.orchestrator.hybrid_research_orchestrator.GeminiAgent') as mock_agent_cls:

            # Setup mocks
            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = mock_website_content

            mock_agent = MagicMock()
            mock_agent.generate.return_value = mock_gemini_response_dict
            mock_agent_cls.return_value = mock_agent

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify original fields
            assert result["keywords"] == mock_gemini_response_dict["content"]["keywords"]
            assert result["tags"] == mock_gemini_response_dict["content"]["tags"]
            assert result["themes"] == mock_gemini_response_dict["content"]["themes"]

            # Verify new fields (Session 034)
            assert result["tone"] == mock_gemini_response_dict["content"]["tone"]
            assert result["setting"] == mock_gemini_response_dict["content"]["setting"]
            assert result["niche"] == mock_gemini_response_dict["content"]["niche"]
            assert result["domain"] == mock_gemini_response_dict["content"]["domain"]

            assert result["cost"] == 0.001
            assert "error" not in result

            # Verify trafilatura was called
            mock_fetch.assert_called_once_with("https://example.com")
            mock_extract.assert_called_once()

            # Verify Gemini was called
            mock_agent.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_extraction_with_json_string_response(
        self, orchestrator, mock_website_content, mock_gemini_response_json_string
    ):
        """Test successful extraction with JSON string response from Gemini"""
        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('src.orchestrator.hybrid_research_orchestrator.GeminiAgent') as mock_agent_cls:

            # Setup mocks
            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = mock_website_content

            mock_agent = MagicMock()
            mock_agent.generate.return_value = mock_gemini_response_json_string
            mock_agent_cls.return_value = mock_agent

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify JSON was parsed (original fields)
            assert result["keywords"] == ["PropTech", "smart building"]
            assert result["tags"] == ["PropTech", "AI"]
            assert result["themes"] == ["Cost Reduction"]

            # Verify new fields (Session 034)
            assert result["tone"] == ["Professional"]
            assert result["setting"] == ["B2B"]
            assert result["niche"] == ["PropTech"]
            assert result["domain"] == "Technology"

            assert "error" not in result

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_empty_result(self, orchestrator):
        """Test that fetch failure returns empty result with error message"""
        with patch('trafilatura.fetch_url') as mock_fetch:
            mock_fetch.return_value = None  # Fetch failed

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify empty result with error (original fields)
            assert result["keywords"] == []
            assert result["tags"] == []
            assert result["themes"] == []

            # Verify new fields (Session 034) are properly defaulted
            assert result["tone"] == []
            assert result["setting"] == []
            assert result["niche"] == []
            assert result["domain"] == "Unknown"

            assert result["cost"] == 0.0
            assert "error" in result
            assert "Failed to fetch website content" in result["error"]

    @pytest.mark.asyncio
    async def test_insufficient_content_returns_empty_result(self, orchestrator):
        """Test that insufficient content (<100 chars) returns empty result"""
        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract:

            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = "Short"  # < 100 chars

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify empty result with error (original fields)
            assert result["keywords"] == []
            assert result["tags"] == []
            assert result["themes"] == []

            # Verify new fields (Session 034) are properly defaulted
            assert result["tone"] == []
            assert result["setting"] == []
            assert result["niche"] == []
            assert result["domain"] == "Unknown"

            assert result["cost"] == 0.0
            assert "error" in result
            assert "Insufficient content" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_content_returns_empty_result(self, orchestrator):
        """Test that empty content returns empty result"""
        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract:

            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = ""  # Empty

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify empty result with error (original fields)
            assert result["keywords"] == []
            assert result["tags"] == []
            assert result["themes"] == []

            # Verify new fields (Session 034) are properly defaulted
            assert result["tone"] == []
            assert result["setting"] == []
            assert result["niche"] == []
            assert result["domain"] == "Unknown"

            assert "error" in result

    @pytest.mark.asyncio
    async def test_max_keywords_limit_enforced(
        self, orchestrator, mock_website_content
    ):
        """Test that max_keywords limit is enforced (default 50)"""
        # Create response with 60 keywords
        many_keywords = [f"keyword{i}" for i in range(60)]

        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('src.orchestrator.hybrid_research_orchestrator.GeminiAgent') as mock_agent_cls:

            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = mock_website_content

            mock_agent = MagicMock()
            mock_agent.generate.return_value = {
                "content": {
                    "keywords": many_keywords,
                    "tags": ["tag1", "tag2"],
                    "themes": ["theme1"]
                },
                "cost": 0.001
            }
            mock_agent_cls.return_value = mock_agent

            # Execute with default limit (50)
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify only first 50 keywords returned
            assert len(result["keywords"]) == 50
            assert result["keywords"] == many_keywords[:50]

    @pytest.mark.asyncio
    async def test_custom_max_keywords_limit(
        self, orchestrator, mock_website_content
    ):
        """Test custom max_keywords limit"""
        many_keywords = [f"keyword{i}" for i in range(30)]

        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('src.orchestrator.hybrid_research_orchestrator.GeminiAgent') as mock_agent_cls:

            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = mock_website_content

            mock_agent = MagicMock()
            mock_agent.generate.return_value = {
                "content": {
                    "keywords": many_keywords,
                    "tags": ["tag1"],
                    "themes": ["theme1"]
                },
                "cost": 0.001
            }
            mock_agent_cls.return_value = mock_agent

            # Execute with custom limit (10)
            result = await orchestrator.extract_website_keywords(
                "https://example.com", max_keywords=10
            )

            # Verify only first 10 keywords returned
            assert len(result["keywords"]) == 10
            assert result["keywords"] == many_keywords[:10]

    @pytest.mark.asyncio
    async def test_max_tags_limit_enforced(
        self, orchestrator, mock_website_content
    ):
        """Test that max tags limit (10) is enforced"""
        many_tags = [f"tag{i}" for i in range(15)]

        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('src.orchestrator.hybrid_research_orchestrator.GeminiAgent') as mock_agent_cls:

            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = mock_website_content

            mock_agent = MagicMock()
            mock_agent.generate.return_value = {
                "content": {
                    "keywords": ["keyword1"],
                    "tags": many_tags,
                    "themes": ["theme1"]
                },
                "cost": 0.001
            }
            mock_agent_cls.return_value = mock_agent

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify only first 10 tags returned
            assert len(result["tags"]) == 10
            assert result["tags"] == many_tags[:10]

    @pytest.mark.asyncio
    async def test_max_themes_limit_enforced(
        self, orchestrator, mock_website_content
    ):
        """Test that max themes limit (5) is enforced"""
        many_themes = [f"theme{i}" for i in range(8)]

        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('src.orchestrator.hybrid_research_orchestrator.GeminiAgent') as mock_agent_cls:

            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = mock_website_content

            mock_agent = MagicMock()
            mock_agent.generate.return_value = {
                "content": {
                    "keywords": ["keyword1"],
                    "tags": ["tag1"],
                    "themes": many_themes
                },
                "cost": 0.001
            }
            mock_agent_cls.return_value = mock_agent

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify only first 5 themes returned
            assert len(result["themes"]) == 5
            assert result["themes"] == many_themes[:5]

    @pytest.mark.asyncio
    async def test_gemini_error_handling(
        self, orchestrator, mock_website_content
    ):
        """Test Gemini error is caught and returns empty result"""
        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('src.orchestrator.hybrid_research_orchestrator.GeminiAgent') as mock_agent_cls:

            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = mock_website_content

            mock_agent = MagicMock()
            mock_agent.generate.side_effect = GeminiAgentError("API rate limit exceeded")
            mock_agent_cls.return_value = mock_agent

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify empty result with error (original fields)
            assert result["keywords"] == []
            assert result["tags"] == []
            assert result["themes"] == []

            # Verify new fields (Session 034) are properly defaulted
            assert result["tone"] == []
            assert result["setting"] == []
            assert result["niche"] == []
            assert result["domain"] == "Unknown"

            assert result["cost"] == 0.0
            assert "error" in result
            assert "Gemini analysis failed" in result["error"]
            assert "API rate limit exceeded" in result["error"]

    @pytest.mark.asyncio
    async def test_general_exception_handling(
        self, orchestrator, mock_website_content
    ):
        """Test general exception is caught and returns empty result"""
        with patch('trafilatura.fetch_url') as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify empty result with error (original fields)
            assert result["keywords"] == []
            assert result["tags"] == []
            assert result["themes"] == []

            # Verify new fields (Session 034) are properly defaulted
            assert result["tone"] == []
            assert result["setting"] == []
            assert result["niche"] == []
            assert result["domain"] == "Unknown"

            assert result["cost"] == 0.0
            assert "error" in result
            assert "Extraction failed" in result["error"]
            assert "Network error" in result["error"]

    @pytest.mark.asyncio
    async def test_trafilatura_content_limit_5000_chars(
        self, orchestrator
    ):
        """Test that only first 5000 chars are sent to Gemini"""
        # Create content where content after 5000 chars has unique markers
        # Position 0-4999: 'a' characters
        # Position 5000+: 'b' characters + END_MARKER
        long_content = "a" * 5000 + "b" * 5000 + " END_MARKER_10000"
        assert len(long_content) > 5000  # Verify test data is long enough

        with patch('trafilatura.fetch_url') as mock_fetch, \
             patch('trafilatura.extract') as mock_extract, \
             patch('src.orchestrator.hybrid_research_orchestrator.GeminiAgent') as mock_agent_cls:

            mock_fetch.return_value = "<html>content</html>"
            mock_extract.return_value = long_content

            mock_agent = MagicMock()
            mock_agent.generate.return_value = {
                "content": {
                    "keywords": ["keyword1"],
                    "tags": ["tag1"],
                    "themes": ["theme1"]
                },
                "cost": 0.001
            }
            mock_agent_cls.return_value = mock_agent

            # Execute
            result = await orchestrator.extract_website_keywords("https://example.com")

            # Verify Gemini was called
            mock_agent.generate.assert_called_once()

            # Extract the prompt that was passed to Gemini
            call_args = mock_agent.generate.call_args
            prompt = call_args.kwargs['prompt']

            # Verify only first 5000 chars were included
            # 'a' characters should be present (first 5000 chars)
            assert "aaaa" in prompt

            # END_MARKER_10000 should NOT be present (it's beyond 5000 chars)
            assert "END_MARKER_10000" not in prompt

            # Verify the 'b' characters (which start at position 5000) are NOT in prompt
            # Check for absence of even short 'b' sequences
            assert "bbbb" not in prompt
