"""
Tests for KeywordResearchAgent

TDD approach: Write failing tests first, then implement KeywordResearchAgent.

Test Coverage:
- Gemini CLI subprocess integration for keyword research
- JSON response parsing and validation
- Error handling (subprocess failures, timeouts, invalid JSON)
- Fallback to Gemini API via OpenRouter
- Keyword data structure validation
- Keyword ranking and selection logic
- Caching behavior
- Empty results handling
- Multiple language support
"""

import pytest
from unittest.mock import Mock, patch
import subprocess
import json
from pathlib import Path

from src.agents.keyword_research_agent import (
    KeywordResearchAgent,
    KeywordResearchError
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_subprocess_keywords():
    """Mock subprocess for Gemini CLI keyword research"""
    with patch('subprocess.run') as mock_run:
        # Mock successful Gemini CLI response
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "primary_keyword": {
                "keyword": "KI Content Marketing",
                "search_volume": "1K-10K",
                "competition": "Medium",
                "difficulty": 45,
                "intent": "Informational"
            },
            "secondary_keywords": [
                {
                    "keyword": "Content Marketing Software",
                    "search_volume": "10K-100K",
                    "competition": "High",
                    "difficulty": 65,
                    "relevance": 0.85
                },
                {
                    "keyword": "Marketing Automation",
                    "search_volume": "1K-10K",
                    "competition": "Medium",
                    "difficulty": 50,
                    "relevance": 0.75
                },
                {
                    "keyword": "Content Strategie",
                    "search_volume": "100-1K",
                    "competition": "Low",
                    "difficulty": 30,
                    "relevance": 0.70
                }
            ],
            "long_tail_keywords": [
                {
                    "keyword": "KI Content Marketing für KMU",
                    "search_volume": "10-100",
                    "competition": "Low",
                    "difficulty": 20
                },
                {
                    "keyword": "Content Marketing Strategie entwickeln",
                    "search_volume": "100-1K",
                    "competition": "Low",
                    "difficulty": 25
                }
            ],
            "related_questions": [
                "Was ist KI Content Marketing?",
                "Wie funktioniert Content Marketing?",
                "Welche Tools für Content Marketing?"
            ],
            "search_trends": {
                "trending_up": ["KI-gestützte Inhalte", "Automatisierung"],
                "trending_down": ["Manuelle Content-Erstellung"],
                "seasonal": False
            },
            "recommendation": "Focus on long-tail keywords with low competition"
        })
        mock_result.stderr = ""

        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_base_agent_generate_keywords():
    """Mock BaseAgent.generate for API fallback"""
    with patch('src.agents.base_agent.BaseAgent.generate') as mock_gen:
        mock_gen.return_value = {
            'content': json.dumps({
                "primary_keyword": {
                    "keyword": "API Keyword",
                    "search_volume": "1K-10K",
                    "competition": "Medium",
                    "difficulty": 50,
                    "intent": "Commercial"
                },
                "secondary_keywords": [
                    {
                        "keyword": "Secondary API Keyword",
                        "search_volume": "100-1K",
                        "competition": "Low",
                        "difficulty": 30,
                        "relevance": 0.80
                    }
                ],
                "long_tail_keywords": [],
                "related_questions": [],
                "search_trends": {
                    "trending_up": [],
                    "trending_down": [],
                    "seasonal": False
                },
                "recommendation": "API recommendation"
            }),
            'tokens': {'prompt': 150, 'completion': 80, 'total': 230},
            'cost': 0.0
        }
        yield mock_gen


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory"""
    cache_dir = tmp_path / "cache" / "research"
    cache_dir.mkdir(parents=True)
    return str(tmp_path / "cache")


# ==================== Initialization Tests ====================

def test_keyword_agent_init_default(mock_subprocess_keywords):
    """Test KeywordResearchAgent initialization with defaults"""
    agent = KeywordResearchAgent(api_key="test-key")

    assert agent.agent_type == "research"
    assert agent.use_cli is True
    assert agent.cli_timeout == 60


def test_keyword_agent_init_with_cache(mock_subprocess_keywords, temp_cache_dir):
    """Test KeywordResearchAgent initialization with cache directory"""
    agent = KeywordResearchAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    assert agent.cache_manager is not None


def test_keyword_agent_init_custom_timeout(mock_subprocess_keywords):
    """Test KeywordResearchAgent initialization with custom timeout"""
    agent = KeywordResearchAgent(api_key="test-key", cli_timeout=90)

    assert agent.cli_timeout == 90


def test_keyword_agent_init_force_api(mock_subprocess_keywords):
    """Test KeywordResearchAgent initialization forcing API"""
    agent = KeywordResearchAgent(api_key="test-key", use_cli=False)

    assert agent.use_cli is False


# ==================== CLI Research Tests ====================

def test_research_keywords_cli_success(mock_subprocess_keywords):
    """Test successful keyword research via Gemini CLI"""
    agent = KeywordResearchAgent(api_key="test-key")

    result = agent.research_keywords(
        topic="content marketing",
        language="en"
    )

    # Verify CLI was called
    mock_subprocess_keywords.assert_called_once()
    call_args = mock_subprocess_keywords.call_args[0][0]
    assert "gemini" in call_args[0]
    assert "search" in call_args[1]

    # Verify response structure
    assert "primary_keyword" in result
    assert "secondary_keywords" in result
    assert "long_tail_keywords" in result
    assert "related_questions" in result
    assert "search_trends" in result
    assert "recommendation" in result

    # Verify primary keyword structure
    primary = result['primary_keyword']
    assert primary['keyword'] == "KI Content Marketing"
    assert primary['search_volume'] == "1K-10K"
    assert primary['competition'] == "Medium"
    assert primary['difficulty'] == 45
    assert primary['intent'] == "Informational"


def test_research_keywords_german_language(mock_subprocess_keywords):
    """Test keyword research with German language"""
    agent = KeywordResearchAgent(api_key="test-key")

    result = agent.research_keywords(
        topic="KI Marketing",
        language="de",
        target_audience="German small businesses"
    )

    # Verify language hint in CLI command
    call_args = mock_subprocess_keywords.call_args[0][0]
    assert "de" in " ".join(call_args).lower() or "german" in " ".join(call_args).lower()


def test_research_keywords_with_target_audience(mock_subprocess_keywords):
    """Test keyword research with target audience"""
    agent = KeywordResearchAgent(api_key="test-key")

    result = agent.research_keywords(
        topic="marketing automation",
        target_audience="Marketing managers in SMBs"
    )

    # Should include target audience in research
    assert "primary_keyword" in result


def test_research_keywords_custom_count(mock_subprocess_keywords):
    """Test keyword research with custom keyword count"""
    agent = KeywordResearchAgent(api_key="test-key")

    result = agent.research_keywords(
        topic="SEO tools",
        keyword_count=15
    )

    # Should respect keyword_count (may be enforced in CLI or post-processing)
    total_keywords = len(result['secondary_keywords']) + len(result['long_tail_keywords'])
    # Allow some flexibility in count
    assert total_keywords >= 5


# ==================== API Fallback Tests ====================

def test_research_keywords_api_fallback_on_cli_failure(
    mock_subprocess_keywords,
    mock_base_agent_generate_keywords
):
    """Test fallback to API when CLI fails"""
    # Make CLI fail
    mock_subprocess_keywords.side_effect = subprocess.SubprocessError("CLI failed")

    agent = KeywordResearchAgent(api_key="test-key")

    result = agent.research_keywords(
        topic="marketing tools",
        language="en"
    )

    # Verify API was called
    mock_base_agent_generate_keywords.assert_called_once()

    # Verify result from API
    assert result['primary_keyword']['keyword'] == "API Keyword"


def test_research_keywords_api_fallback_on_timeout(
    mock_subprocess_keywords,
    mock_base_agent_generate_keywords
):
    """Test fallback to API when CLI times out"""
    # Make CLI timeout
    mock_subprocess_keywords.side_effect = subprocess.TimeoutExpired(
        cmd="gemini", timeout=60
    )

    agent = KeywordResearchAgent(api_key="test-key")

    result = agent.research_keywords(topic="marketing")

    # Verify API was called
    mock_base_agent_generate_keywords.assert_called_once()


def test_research_keywords_force_api_usage(mock_base_agent_generate_keywords):
    """Test forcing API usage instead of CLI"""
    agent = KeywordResearchAgent(api_key="test-key", use_cli=False)

    result = agent.research_keywords(topic="marketing")

    # Verify API was called directly
    mock_base_agent_generate_keywords.assert_called_once()


# ==================== Error Handling Tests ====================

def test_research_keywords_empty_topic_error():
    """Test error when topic is empty"""
    agent = KeywordResearchAgent(api_key="test-key")

    with pytest.raises(KeywordResearchError, match="Topic is required"):
        agent.research_keywords(topic="")


def test_research_keywords_whitespace_topic_error():
    """Test error when topic is only whitespace"""
    agent = KeywordResearchAgent(api_key="test-key")

    with pytest.raises(KeywordResearchError, match="Topic is required"):
        agent.research_keywords(topic="   ")


def test_research_keywords_none_topic_error():
    """Test error when topic is None"""
    agent = KeywordResearchAgent(api_key="test-key")

    with pytest.raises(KeywordResearchError, match="Topic is required"):
        agent.research_keywords(topic=None)


def test_research_keywords_cli_invalid_json(mock_subprocess_keywords):
    """Test handling of invalid JSON from CLI"""
    # Return invalid JSON
    mock_subprocess_keywords.return_value.stdout = "Invalid JSON {["

    agent = KeywordResearchAgent(api_key="test-key", use_cli=False)

    # Should raise error
    with pytest.raises(KeywordResearchError):
        agent.research_keywords(topic="marketing")


def test_research_keywords_cli_empty_response(mock_subprocess_keywords):
    """Test handling of empty CLI response"""
    mock_subprocess_keywords.return_value.stdout = ""

    agent = KeywordResearchAgent(api_key="test-key", use_cli=False)

    with pytest.raises(KeywordResearchError):
        agent.research_keywords(topic="marketing")


def test_research_keywords_cli_non_zero_exit(mock_subprocess_keywords):
    """Test handling of non-zero exit code from CLI"""
    mock_subprocess_keywords.return_value.returncode = 1
    mock_subprocess_keywords.return_value.stderr = "CLI error"

    agent = KeywordResearchAgent(api_key="test-key", use_cli=False)

    with pytest.raises(KeywordResearchError):
        agent.research_keywords(topic="marketing")


# ==================== Data Normalization Tests ====================

def test_normalize_keyword_data_minimal():
    """Test normalization with minimal keyword data"""
    agent = KeywordResearchAgent(api_key="test-key")

    data = {
        "primary_keyword": {
            "keyword": "Test Keyword"
        }
    }

    normalized = agent._normalize_keyword_data(data)

    # Should add default values for missing fields
    primary = normalized['primary_keyword']
    assert primary['keyword'] == "Test Keyword"
    assert 'search_volume' in primary
    assert 'competition' in primary
    assert 'difficulty' in primary
    assert 'intent' in primary


def test_normalize_keyword_data_missing_secondary_keywords():
    """Test normalization when secondary keywords are missing"""
    agent = KeywordResearchAgent(api_key="test-key")

    data = {
        "primary_keyword": {
            "keyword": "Test",
            "search_volume": "1K-10K",
            "competition": "Medium",
            "difficulty": 50,
            "intent": "Informational"
        }
    }

    normalized = agent._normalize_keyword_data(data)

    # Should have default empty lists
    assert normalized['secondary_keywords'] == []
    assert normalized['long_tail_keywords'] == []


def test_normalize_keyword_data_missing_trends():
    """Test normalization when search trends are missing"""
    agent = KeywordResearchAgent(api_key="test-key")

    data = {
        "primary_keyword": {
            "keyword": "Test",
            "search_volume": "1K",
            "competition": "Low",
            "difficulty": 30,
            "intent": "Commercial"
        }
    }

    normalized = agent._normalize_keyword_data(data)

    # Should have default search trends structure
    trends = normalized['search_trends']
    assert 'trending_up' in trends
    assert 'trending_down' in trends
    assert 'seasonal' in trends


# ==================== Caching Tests ====================

def test_research_keywords_save_to_cache(
    mock_subprocess_keywords,
    temp_cache_dir
):
    """Test saving keyword research to cache"""
    agent = KeywordResearchAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    result = agent.research_keywords(
        topic="marketing automation",
        save_to_cache=True
    )

    # Verify cache file was created
    cache_path = Path(temp_cache_dir) / "research"
    cache_files = list(cache_path.glob("keywords_*.json"))
    assert len(cache_files) == 1

    # Verify cached data
    with open(cache_files[0], 'r') as f:
        cached_data = json.load(f)

    assert cached_data['primary_keyword'] == result['primary_keyword']


def test_research_keywords_no_cache_when_disabled(
    mock_subprocess_keywords,
    temp_cache_dir
):
    """Test that caching is skipped when save_to_cache=False"""
    agent = KeywordResearchAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    agent.research_keywords(
        topic="marketing automation",
        save_to_cache=False
    )

    # Verify no cache file was created
    cache_path = Path(temp_cache_dir) / "research"
    cache_files = list(cache_path.glob("keywords_*.json"))
    assert len(cache_files) == 0


def test_research_keywords_no_cache_without_cache_dir(mock_subprocess_keywords):
    """Test that caching is skipped when no cache_dir provided"""
    agent = KeywordResearchAgent(api_key="test-key")

    # Should not raise error even with save_to_cache=True
    result = agent.research_keywords(
        topic="marketing",
        save_to_cache=True
    )

    assert "primary_keyword" in result


# ==================== Keyword Ranking Tests ====================

def test_keyword_difficulty_calculation():
    """Test keyword difficulty calculation logic"""
    agent = KeywordResearchAgent(api_key="test-key")

    # Test difficulty based on competition and volume
    difficulty = agent._calculate_keyword_difficulty(
        search_volume="10K-100K",
        competition="High"
    )

    assert 50 <= difficulty <= 100


def test_keyword_difficulty_low_competition():
    """Test keyword difficulty with low competition"""
    agent = KeywordResearchAgent(api_key="test-key")

    difficulty = agent._calculate_keyword_difficulty(
        search_volume="100-1K",
        competition="Low"
    )

    assert 0 <= difficulty <= 40


def test_keyword_ranking_by_relevance():
    """Test sorting keywords by relevance"""
    agent = KeywordResearchAgent(api_key="test-key")

    keywords = [
        {"keyword": "A", "relevance": 0.5},
        {"keyword": "B", "relevance": 0.9},
        {"keyword": "C", "relevance": 0.7}
    ]

    sorted_keywords = agent._rank_keywords_by_relevance(keywords)

    # Should be sorted by relevance descending
    assert sorted_keywords[0]['keyword'] == "B"
    assert sorted_keywords[1]['keyword'] == "C"
    assert sorted_keywords[2]['keyword'] == "A"


# ==================== Integration Tests ====================

def test_research_keywords_complete_workflow(
    mock_subprocess_keywords,
    temp_cache_dir
):
    """Test complete keyword research workflow"""
    agent = KeywordResearchAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    result = agent.research_keywords(
        topic="AI content marketing",
        language="de",
        target_audience="German small business owners",
        keyword_count=10,
        save_to_cache=True
    )

    # Verify all data present
    assert result['primary_keyword']['keyword'] != ""
    assert len(result['secondary_keywords']) > 0
    assert len(result['long_tail_keywords']) > 0
    assert result['recommendation'] != ""

    # Verify keyword structure
    primary = result['primary_keyword']
    assert 'keyword' in primary
    assert 'search_volume' in primary
    assert 'competition' in primary
    assert 'difficulty' in primary
    assert 'intent' in primary

    # Verify secondary keyword structure
    secondary = result['secondary_keywords'][0]
    assert 'keyword' in secondary
    assert 'search_volume' in secondary
    assert 'relevance' in secondary

    # Verify caching worked
    cache_path = Path(temp_cache_dir) / "research"
    cache_files = list(cache_path.glob("keywords_*.json"))
    assert len(cache_files) == 1
