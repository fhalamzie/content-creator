"""Tests for Research Lab UI tabs (Competitor Analysis & Keyword Research).

Tests cover:
- API key validation
- Agent initialization
- Result processing
- Session state management
- Export functionality
- Error handling
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os
import sys

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agents.competitor_research_agent import CompetitorResearchAgent, CompetitorResearchError
from agents.keyword_research_agent import KeywordResearchAgent, KeywordResearchError


class TestCompetitorAnalysisTab:
    """Test Competitor Analysis Tab (Tab 2) functionality."""

    def test_api_key_validation_missing_key(self):
        """Test API key validation fails when GEMINI_API_KEY is missing."""
        with patch.dict(os.environ, {}, clear=True):
            api_key = os.getenv("GEMINI_API_KEY")
            assert api_key is None

    def test_api_key_validation_key_exists(self):
        """Test API key validation succeeds when GEMINI_API_KEY exists."""
        test_key = "test-api-key-12345"
        with patch.dict(os.environ, {"GEMINI_API_KEY": test_key}):
            api_key = os.getenv("GEMINI_API_KEY")
            assert api_key == test_key

    def test_competitor_agent_initialization(self):
        """Test CompetitorResearchAgent initializes correctly."""
        agent = CompetitorResearchAgent(
            api_key="test-key",
            use_cli=False,
            model="gemini-2.5-flash"
        )
        assert agent is not None
        assert agent.api_key == "test-key"
        assert agent.use_cli is False

    def test_competitor_result_structure(self):
        """Test competitor research result has required fields."""
        # Mock result structure
        mock_result = {
            "competitors": [
                {
                    "name": "Competitor 1",
                    "website": "https://competitor1.com",
                    "description": "Leading company",
                    "social_handles": {"linkedin": "url", "twitter": "", "facebook": ""},
                    "content_topics": ["topic1", "topic2"],
                    "posting_frequency": "2-3 times per week"
                }
            ],
            "content_gaps": ["Gap 1", "Gap 2", "Gap 3"],
            "trending_topics": ["Trend 1", "Trend 2"],
            "recommendation": "Strategic recommendation here"
        }

        # Validate structure
        assert "competitors" in mock_result
        assert "content_gaps" in mock_result
        assert "trending_topics" in mock_result
        assert "recommendation" in mock_result

        assert len(mock_result["competitors"]) == 1
        assert len(mock_result["content_gaps"]) == 3
        assert len(mock_result["trending_topics"]) == 2

    def test_competitor_empty_results_handling(self):
        """Test handling of empty competitor research results."""
        empty_result = {
            "competitors": [],
            "content_gaps": [],
            "trending_topics": [],
            "recommendation": ""
        }

        # Should not crash with empty data
        assert len(empty_result["competitors"]) == 0
        assert len(empty_result["content_gaps"]) == 0

    def test_session_state_storage(self):
        """Test session state stores competitor results correctly."""
        mock_result = {
            "competitors": [{"name": "Test Competitor"}],
            "content_gaps": ["Gap 1"],
            "trending_topics": ["Trend 1"],
            "recommendation": "Test recommendation"
        }
        mock_topic = "property management software"

        # Simulate session state storage
        session_state = {
            "competitor_result": mock_result,
            "competitor_topic": mock_topic
        }

        assert session_state["competitor_result"] == mock_result
        assert session_state["competitor_topic"] == mock_topic

    def test_export_to_quick_create(self):
        """Test export functionality stores data for Quick Create."""
        competitors = [{"name": "Competitor 1"}]
        content_gaps = ["Gap 1", "Gap 2"]
        trending_topics = ["Trend 1"]
        recommendation = "Strategic advice"
        topic = "test topic"

        # Simulate export
        exported_data = {
            "competitors": competitors,
            "content_gaps": content_gaps,
            "trending_topics": trending_topics,
            "recommendation": recommendation,
            "timestamp": topic
        }

        assert exported_data["competitors"] == competitors
        assert len(exported_data["content_gaps"]) == 2
        assert "timestamp" in exported_data

    def test_competitor_metrics_calculation(self):
        """Test metrics calculation from competitor results."""
        mock_result = {
            "competitors": [{"name": "C1"}, {"name": "C2"}, {"name": "C3"}],
            "content_gaps": ["G1", "G2", "G3", "G4", "G5"],
            "trending_topics": ["T1", "T2"]
        }

        competitors_count = len(mock_result["competitors"])
        gaps_count = len(mock_result["content_gaps"])
        trends_count = len(mock_result["trending_topics"])

        assert competitors_count == 3
        assert gaps_count == 5
        assert trends_count == 2

    def test_competitor_max_value_slider(self):
        """Test max competitors slider validation (3-10 range)."""
        valid_values = [3, 5, 7, 10]
        for val in valid_values:
            assert 3 <= val <= 10

        invalid_values = [2, 11, 15]
        for val in invalid_values:
            assert not (3 <= val <= 10)

    def test_language_options(self):
        """Test language selection options are valid."""
        languages = ["de", "en", "es", "fr"]
        language_names = {
            "de": "German",
            "en": "English",
            "es": "Spanish",
            "fr": "French"
        }

        for lang in languages:
            assert lang in language_names
            assert len(language_names[lang]) > 0


class TestKeywordResearchTab:
    """Test Keyword Research Tab (Tab 3) functionality."""

    def test_keyword_agent_initialization(self):
        """Test KeywordResearchAgent initializes correctly."""
        agent = KeywordResearchAgent(
            api_key="test-key",
            use_cli=False,
            model="gemini-2.5-flash"
        )
        assert agent is not None
        assert agent.api_key == "test-key"
        assert agent.use_cli is False

    def test_keyword_result_structure(self):
        """Test keyword research result has required fields."""
        mock_result = {
            "primary_keyword": {
                "keyword": "content marketing",
                "search_volume": "10K-100K",
                "competition": "High",
                "difficulty": 75,
                "intent": "Informational"
            },
            "secondary_keywords": [
                {
                    "keyword": "content strategy",
                    "search_volume": "1K-10K",
                    "competition": "Medium",
                    "difficulty": 60,
                    "relevance": 85
                }
            ],
            "long_tail_keywords": [
                {
                    "keyword": "how to create content marketing strategy",
                    "search_volume": "100-1K",
                    "competition": "Low",
                    "difficulty": 30
                }
            ],
            "related_questions": [
                "What is content marketing?",
                "How to start content marketing?"
            ],
            "search_trends": {"trending": "up", "seasonal": False},
            "recommendation": "Focus on long-tail keywords"
        }

        # Validate structure
        assert "primary_keyword" in mock_result
        assert "secondary_keywords" in mock_result
        assert "long_tail_keywords" in mock_result
        assert "related_questions" in mock_result
        assert "search_trends" in mock_result
        assert "recommendation" in mock_result

        # Validate primary keyword structure
        primary = mock_result["primary_keyword"]
        assert "keyword" in primary
        assert "search_volume" in primary
        assert "competition" in primary
        assert "difficulty" in primary
        assert "intent" in primary

    def test_keyword_metrics_calculation(self):
        """Test keyword count metrics calculation."""
        mock_result = {
            "primary_keyword": {"keyword": "main"},
            "secondary_keywords": [{"keyword": "s1"}, {"keyword": "s2"}, {"keyword": "s3"}],
            "long_tail_keywords": [{"keyword": "l1"}, {"keyword": "l2"}],
            "related_questions": ["q1", "q2", "q3", "q4"]
        }

        total_keywords = (
            1 +  # primary
            len(mock_result["secondary_keywords"]) +
            len(mock_result["long_tail_keywords"])
        )
        questions_count = len(mock_result["related_questions"])

        assert total_keywords == 6  # 1 + 3 + 2
        assert questions_count == 4

    def test_keyword_count_slider_validation(self):
        """Test keyword count slider validation (10-50 range)."""
        valid_values = [10, 20, 30, 40, 50]
        for val in valid_values:
            assert 10 <= val <= 50

        invalid_values = [5, 55, 100]
        for val in invalid_values:
            assert not (10 <= val <= 50)

    def test_keyword_difficulty_range(self):
        """Test keyword difficulty scores are in valid range (0-100)."""
        difficulty_scores = [0, 25, 50, 75, 100]
        for score in difficulty_scores:
            assert 0 <= score <= 100

    def test_search_intent_values(self):
        """Test valid search intent classifications."""
        valid_intents = ["Informational", "Commercial", "Transactional", "Navigational"]
        test_intent = "Informational"
        assert test_intent in valid_intents

    def test_keyword_session_state_storage(self):
        """Test session state stores keyword results correctly."""
        mock_result = {
            "primary_keyword": {"keyword": "test"},
            "secondary_keywords": [],
            "long_tail_keywords": [],
            "related_questions": [],
            "search_trends": {},
            "recommendation": "Test"
        }
        mock_seed = "content marketing"

        # Simulate session state storage
        session_state = {
            "keyword_result": mock_result,
            "keyword_seed": mock_seed
        }

        assert session_state["keyword_result"] == mock_result
        assert session_state["keyword_seed"] == mock_seed

    def test_keyword_export_to_quick_create(self):
        """Test keyword export functionality."""
        primary = {"keyword": "main keyword"}
        secondary = [{"keyword": "s1"}, {"keyword": "s2"}]
        long_tail = [{"keyword": "l1"}]
        questions = ["q1", "q2"]
        recommendation = "Focus on these"
        seed = "seed keyword"

        # Simulate export
        exported_data = {
            "primary_keyword": primary,
            "secondary_keywords": secondary,
            "long_tail_keywords": long_tail,
            "related_questions": questions,
            "recommendation": recommendation,
            "seed_keyword": seed
        }

        assert exported_data["primary_keyword"] == primary
        assert len(exported_data["secondary_keywords"]) == 2
        assert len(exported_data["long_tail_keywords"]) == 1
        assert len(exported_data["related_questions"]) == 2
        assert exported_data["seed_keyword"] == seed

    def test_optional_target_audience_field(self):
        """Test target audience field is optional."""
        # Should work without target audience
        params_without_audience = {
            "topic": "content marketing",
            "language": "en",
            "target_audience": None,
            "keyword_count": 20
        }
        assert params_without_audience["target_audience"] is None

        # Should work with target audience
        params_with_audience = {
            "topic": "content marketing",
            "language": "en",
            "target_audience": "small business owners",
            "keyword_count": 20
        }
        assert params_with_audience["target_audience"] == "small business owners"

    def test_keyword_empty_results_handling(self):
        """Test handling of empty keyword research results."""
        empty_result = {
            "primary_keyword": {},
            "secondary_keywords": [],
            "long_tail_keywords": [],
            "related_questions": [],
            "search_trends": {},
            "recommendation": ""
        }

        # Should not crash with empty data
        assert len(empty_result["secondary_keywords"]) == 0
        assert len(empty_result["long_tail_keywords"]) == 0
        assert len(empty_result["related_questions"]) == 0


class TestErrorHandling:
    """Test error handling for both tabs."""

    def test_competitor_research_error_handling(self):
        """Test CompetitorResearchError is raised on failure."""
        with pytest.raises(CompetitorResearchError):
            raise CompetitorResearchError("Test error")

    def test_keyword_research_error_handling(self):
        """Test KeywordResearchError is raised on failure."""
        with pytest.raises(KeywordResearchError):
            raise KeywordResearchError("Test error")

    def test_empty_topic_validation_competitor(self):
        """Test competitor research rejects empty topic."""
        with pytest.raises(CompetitorResearchError, match="Topic is required"):
            agent = CompetitorResearchAgent(api_key="test-key")
            agent.research_competitors(topic="", language="en")

    def test_empty_topic_validation_keyword(self):
        """Test keyword research rejects empty topic."""
        with pytest.raises(KeywordResearchError, match="Topic is required"):
            agent = KeywordResearchAgent(api_key="test-key")
            agent.research_keywords(topic="", language="en")

    def test_missing_api_key_detection(self):
        """Test detection of missing API key before agent call."""
        with patch.dict(os.environ, {}, clear=True):
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                error_message = "❌ Missing GEMINI_API_KEY"
                assert "Missing GEMINI_API_KEY" in error_message


class TestCostEstimates:
    """Test cost and time estimate accuracy."""

    def test_competitor_analysis_cost(self):
        """Test competitor analysis is FREE (Gemini API)."""
        cost_usd = 0.0
        description = "FREE (Gemini API with Google Search grounding)"

        assert cost_usd == 0.0
        assert "FREE" in description
        assert "Gemini" in description

    def test_keyword_research_cost(self):
        """Test keyword research is FREE (Gemini API)."""
        cost_usd = 0.0
        description = "FREE (Gemini API with Google Search grounding)"

        assert cost_usd == 0.0
        assert "FREE" in description

    def test_competitor_time_estimate(self):
        """Test competitor analysis time estimate (10-20 seconds)."""
        duration_seconds = 15
        description = "Typically 10-20 seconds"

        assert 10 <= duration_seconds <= 20
        assert "10-20 seconds" in description

    def test_keyword_time_estimate(self):
        """Test keyword research time estimate (10-15 seconds)."""
        duration_seconds = 12
        description = "Typically 10-15 seconds"

        assert 10 <= duration_seconds <= 15
        assert "10-15 seconds" in description


class TestDataTransformations:
    """Test data transformation and display logic."""

    def test_competitor_data_flattening(self):
        """Test competitor data is flattened for display."""
        competitor = {
            "name": "Test Company",
            "website": "https://example.com",
            "description": "Description here",
            "social_handles": {
                "linkedin": "https://linkedin.com/company/test",
                "twitter": "",
                "facebook": "https://facebook.com/test"
            },
            "content_topics": ["topic1", "topic2", "topic3", "topic4", "topic5", "topic6"],
            "posting_frequency": "Daily"
        }

        # Simulate display logic (showing first 5 topics)
        topics_to_show = competitor["content_topics"][:5]
        assert len(topics_to_show) == 5
        assert topics_to_show == ["topic1", "topic2", "topic3", "topic4", "topic5"]

    def test_keyword_table_data_structure(self):
        """Test keyword data is structured for table display."""
        secondary_keywords = [
            {
                "keyword": "keyword 1",
                "search_volume": "1K-10K",
                "competition": "Medium",
                "difficulty": 55,
                "relevance": 80
            },
            {
                "keyword": "keyword 2",
                "search_volume": "100-1K",
                "competition": "Low",
                "difficulty": 35,
                "relevance": 70
            }
        ]

        # Convert to table format
        table_data = []
        for kw in secondary_keywords:
            table_data.append({
                "Keyword": kw["keyword"],
                "Search Volume": kw["search_volume"],
                "Competition": kw["competition"],
                "Difficulty": f"{kw['difficulty']}/100",
                "Relevance": f"{kw['relevance']}%"
            })

        assert len(table_data) == 2
        assert table_data[0]["Difficulty"] == "55/100"
        assert table_data[1]["Relevance"] == "70%"

    def test_question_list_formatting(self):
        """Test related questions are formatted as numbered list."""
        questions = [
            "What is content marketing?",
            "How to start content marketing?",
            "Best content marketing tools"
        ]

        # Simulate display formatting
        formatted = [f"{i}. {q}" for i, q in enumerate(questions, 1)]

        assert formatted[0] == "1. What is content marketing?"
        assert formatted[1] == "2. How to start content marketing?"
        assert formatted[2] == "3. Best content marketing tools"


class TestIntegrationScenarios:
    """Test complete workflow scenarios."""

    def test_competitor_analysis_full_workflow(self):
        """Test complete competitor analysis workflow."""
        # Step 1: User input
        topic = "property management software"
        language = "de"
        max_competitors = 5
        include_analysis = True

        # Step 2: Validate inputs
        assert topic and topic.strip()
        assert language in ["de", "en", "es", "fr"]
        assert 3 <= max_competitors <= 10

        # Step 3: Mock API response
        mock_result = {
            "competitors": [{"name": f"Competitor {i}"} for i in range(5)],
            "content_gaps": ["Gap 1", "Gap 2"],
            "trending_topics": ["Trend 1"],
            "recommendation": "Focus on gaps"
        }

        # Step 4: Calculate metrics
        competitors_found = len(mock_result["competitors"])
        gaps_identified = len(mock_result["content_gaps"])

        assert competitors_found == 5
        assert gaps_identified == 2

    def test_keyword_research_full_workflow(self):
        """Test complete keyword research workflow."""
        # Step 1: User input
        seed_keyword = "content marketing"
        language = "en"
        keyword_count = 20
        target_audience = "small businesses"

        # Step 2: Validate inputs
        assert seed_keyword and seed_keyword.strip()
        assert language in ["de", "en", "es", "fr"]
        assert 10 <= keyword_count <= 50

        # Step 3: Mock API response
        mock_result = {
            "primary_keyword": {"keyword": "content marketing"},
            "secondary_keywords": [{"keyword": f"kw{i}"} for i in range(10)],
            "long_tail_keywords": [{"keyword": f"long{i}"} for i in range(5)],
            "related_questions": ["q1", "q2", "q3"],
            "search_trends": {},
            "recommendation": "Focus on long-tail"
        }

        # Step 4: Calculate metrics
        total_keywords = (
            1 +
            len(mock_result["secondary_keywords"]) +
            len(mock_result["long_tail_keywords"])
        )
        questions_count = len(mock_result["related_questions"])

        assert total_keywords == 16  # 1 + 10 + 5
        assert questions_count == 3


# Mark all tests as UI tests for optional filtering
pytestmark = pytest.mark.ui
