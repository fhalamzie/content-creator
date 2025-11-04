"""
Tests for CompetitorResearchAgent

TDD approach: Write failing tests first, then implement CompetitorResearchAgent.

Test Coverage:
- Gemini CLI subprocess integration for competitor research
- JSON response parsing and validation
- Error handling (subprocess failures, timeouts, invalid JSON)
- Fallback to Gemini API via OpenRouter
- Competitor data structure validation
- Caching behavior
- Empty results handling
- Social handles parsing
- Content strategy analysis
"""

import pytest
from unittest.mock import Mock, patch
import subprocess
import json
from pathlib import Path

from src.agents.competitor_research_agent import (
    CompetitorResearchAgent,
    CompetitorResearchError
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_subprocess_competitors():
    """Mock subprocess for Gemini CLI competitor research"""
    with patch('subprocess.run') as mock_run:
        # Mock successful Gemini CLI response
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "competitors": [
                {
                    "name": "HubSpot",
                    "website": "https://www.hubspot.com",
                    "description": "Marketing, sales, and service software",
                    "social_handles": {
                        "linkedin": "hubspot",
                        "twitter": "hubspot",
                        "facebook": "hubspot",
                        "instagram": "hubspot"
                    },
                    "content_strategy": {
                        "topics": ["Marketing", "Sales", "CRM", "Automation"],
                        "posting_frequency": "Daily",
                        "content_types": ["blog", "video", "ebook", "webinar"],
                        "strengths": ["Comprehensive guides", "Free tools"],
                        "weaknesses": ["Too broad", "Less industry-specific"]
                    }
                },
                {
                    "name": "Mailchimp",
                    "website": "https://mailchimp.com",
                    "description": "Email marketing platform",
                    "social_handles": {
                        "linkedin": "mailchimp",
                        "twitter": "mailchimp",
                        "facebook": "",
                        "instagram": "mailchimp"
                    },
                    "content_strategy": {
                        "topics": ["Email Marketing", "Automation", "Analytics"],
                        "posting_frequency": "2-3 posts/week",
                        "content_types": ["blog", "case study"],
                        "strengths": ["Beginner-friendly", "Templates"],
                        "weaknesses": ["Limited advanced topics"]
                    }
                }
            ],
            "content_gaps": [
                "AI-powered content optimization",
                "German-specific marketing strategies",
                "Small business case studies"
            ],
            "trending_topics": [
                "AI content generation",
                "Marketing automation",
                "Personalization"
            ],
            "recommendation": "Focus on AI-powered solutions for German small businesses"
        })
        mock_result.stderr = ""

        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_base_agent_generate_competitors():
    """Mock BaseAgent.generate for API fallback"""
    with patch('src.agents.base_agent.BaseAgent.generate') as mock_gen:
        mock_gen.return_value = {
            'content': json.dumps({
                "competitors": [
                    {
                        "name": "API Competitor",
                        "website": "https://api-competitor.com",
                        "description": "API fallback competitor",
                        "social_handles": {
                            "linkedin": "api-competitor",
                            "twitter": "",
                            "facebook": "",
                            "instagram": ""
                        },
                        "content_strategy": {
                            "topics": ["Tech"],
                            "posting_frequency": "Weekly",
                            "content_types": ["blog"],
                            "strengths": ["Technical depth"],
                            "weaknesses": ["Limited reach"]
                        }
                    }
                ],
                "content_gaps": ["AI integration"],
                "trending_topics": ["Automation"],
                "recommendation": "Focus on automation"
            }),
            'tokens': {'prompt': 200, 'completion': 100, 'total': 300},
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

def test_competitor_agent_init_default(mock_subprocess_competitors):
    """Test CompetitorResearchAgent initialization with defaults"""
    agent = CompetitorResearchAgent(api_key="test-key")

    assert agent.agent_type == "research"
    assert agent.use_cli is True
    assert agent.cli_timeout == 60


def test_competitor_agent_init_with_cache(mock_subprocess_competitors, temp_cache_dir):
    """Test CompetitorResearchAgent initialization with cache directory"""
    agent = CompetitorResearchAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    assert agent.cache_manager is not None


def test_competitor_agent_init_custom_timeout(mock_subprocess_competitors):
    """Test CompetitorResearchAgent initialization with custom timeout"""
    agent = CompetitorResearchAgent(api_key="test-key", cli_timeout=120)

    assert agent.cli_timeout == 120


def test_competitor_agent_init_force_api(mock_subprocess_competitors):
    """Test CompetitorResearchAgent initialization forcing API"""
    agent = CompetitorResearchAgent(api_key="test-key", use_cli=False)

    assert agent.use_cli is False


# ==================== CLI Research Tests ====================

def test_research_competitors_cli_success(mock_subprocess_competitors):
    """Test successful competitor research via Gemini CLI"""
    agent = CompetitorResearchAgent(api_key="test-key")

    result = agent.research_competitors(
        topic="content marketing software",
        language="en"
    )

    # Verify CLI was called
    mock_subprocess_competitors.assert_called_once()
    call_args = mock_subprocess_competitors.call_args[0][0]
    assert "gemini" in call_args[0]
    assert "search" in call_args[1]

    # Verify response structure
    assert "competitors" in result
    assert "content_gaps" in result
    assert "trending_topics" in result
    assert "recommendation" in result

    # Verify competitor data
    assert len(result['competitors']) == 2
    assert result['competitors'][0]['name'] == "HubSpot"
    assert result['competitors'][0]['website'] == "https://www.hubspot.com"


def test_research_competitors_german_language(mock_subprocess_competitors):
    """Test competitor research with German language"""
    agent = CompetitorResearchAgent(api_key="test-key")

    agent.research_competitors(
        topic="KI Content Marketing",
        language="de"
    )

    # Verify language hint in CLI command
    call_args = mock_subprocess_competitors.call_args[0][0]
    assert "de" in " ".join(call_args).lower() or "german" in " ".join(call_args).lower()


def test_research_competitors_max_competitors_limit(mock_subprocess_competitors):
    """Test max_competitors parameter"""
    agent = CompetitorResearchAgent(api_key="test-key")

    result = agent.research_competitors(
        topic="email marketing",
        max_competitors=3
    )

    # Should respect max limit in CLI command or post-processing
    assert len(result['competitors']) <= 3


def test_research_competitors_content_analysis_disabled(mock_subprocess_competitors):
    """Test competitor research without content analysis"""
    agent = CompetitorResearchAgent(api_key="test-key")

    result = agent.research_competitors(
        topic="marketing automation",
        include_content_analysis=False
    )

    # Should still return basic competitor info
    assert "competitors" in result


# ==================== API Fallback Tests ====================

def test_research_competitors_api_fallback_on_cli_failure(
    mock_subprocess_competitors,
    mock_base_agent_generate_competitors
):
    """Test fallback to API when CLI fails"""
    # Make CLI fail
    mock_subprocess_competitors.side_effect = subprocess.SubprocessError("CLI failed")

    agent = CompetitorResearchAgent(api_key="test-key")

    result = agent.research_competitors(
        topic="content tools",
        language="en"
    )

    # Verify API was called
    mock_base_agent_generate_competitors.assert_called_once()

    # Verify result from API
    assert len(result['competitors']) == 1
    assert result['competitors'][0]['name'] == "API Competitor"


def test_research_competitors_api_fallback_on_timeout(
    mock_subprocess_competitors,
    mock_base_agent_generate_competitors
):
    """Test fallback to API when CLI times out"""
    # Make CLI timeout
    mock_subprocess_competitors.side_effect = subprocess.TimeoutExpired(
        cmd="gemini", timeout=60
    )

    agent = CompetitorResearchAgent(api_key="test-key")

    agent.research_competitors(topic="marketing")

    # Verify API was called
    mock_base_agent_generate_competitors.assert_called_once()


def test_research_competitors_force_api_usage(mock_base_agent_generate_competitors):
    """Test forcing API usage instead of CLI"""
    agent = CompetitorResearchAgent(api_key="test-key", use_cli=False)

    agent.research_competitors(topic="marketing")

    # Verify API was called directly
    mock_base_agent_generate_competitors.assert_called_once()


# ==================== Error Handling Tests ====================

def test_research_competitors_empty_topic_error():
    """Test error when topic is empty"""
    agent = CompetitorResearchAgent(api_key="test-key")

    with pytest.raises(CompetitorResearchError, match="Topic is required"):
        agent.research_competitors(topic="")


def test_research_competitors_whitespace_topic_error():
    """Test error when topic is only whitespace"""
    agent = CompetitorResearchAgent(api_key="test-key")

    with pytest.raises(CompetitorResearchError, match="Topic is required"):
        agent.research_competitors(topic="   ")


def test_research_competitors_none_topic_error():
    """Test error when topic is None"""
    agent = CompetitorResearchAgent(api_key="test-key")

    with pytest.raises(CompetitorResearchError, match="Topic is required"):
        agent.research_competitors(topic=None)


def test_research_competitors_cli_invalid_json(mock_subprocess_competitors):
    """Test handling of invalid JSON from CLI"""
    # Return invalid JSON
    mock_subprocess_competitors.return_value.stdout = "Invalid JSON {["

    agent = CompetitorResearchAgent(api_key="test-key", use_cli=False)

    # Should raise error or fallback to API
    with pytest.raises(CompetitorResearchError):
        agent.research_competitors(topic="marketing")


def test_research_competitors_cli_empty_response(mock_subprocess_competitors):
    """Test handling of empty CLI response"""
    mock_subprocess_competitors.return_value.stdout = ""

    agent = CompetitorResearchAgent(api_key="test-key", use_cli=False)

    with pytest.raises(CompetitorResearchError):
        agent.research_competitors(topic="marketing")


def test_research_competitors_cli_non_zero_exit(mock_subprocess_competitors):
    """Test handling of non-zero exit code from CLI"""
    mock_subprocess_competitors.return_value.returncode = 1
    mock_subprocess_competitors.return_value.stderr = "CLI error"

    agent = CompetitorResearchAgent(api_key="test-key", use_cli=False)

    with pytest.raises(CompetitorResearchError):
        agent.research_competitors(topic="marketing")


# ==================== Data Normalization Tests ====================

def test_normalize_competitor_data_minimal():
    """Test normalization with minimal competitor data"""
    agent = CompetitorResearchAgent(api_key="test-key")

    data = {
        "competitors": [
            {
                "name": "Minimal Competitor",
                "website": "https://example.com"
            }
        ]
    }

    normalized = agent._normalize_competitor_data(data)

    # Should add default values for missing fields
    assert normalized['competitors'][0]['name'] == "Minimal Competitor"
    assert normalized['competitors'][0]['website'] == "https://example.com"
    assert 'description' in normalized['competitors'][0]
    assert 'social_handles' in normalized['competitors'][0]
    assert 'content_strategy' in normalized['competitors'][0]


def test_normalize_competitor_data_missing_social_handles():
    """Test normalization when social handles are missing"""
    agent = CompetitorResearchAgent(api_key="test-key")

    data = {
        "competitors": [
            {
                "name": "Company",
                "website": "https://example.com",
                "social_handles": {}
            }
        ]
    }

    normalized = agent._normalize_competitor_data(data)

    # Should add default social handles
    social = normalized['competitors'][0]['social_handles']
    assert 'linkedin' in social
    assert 'twitter' in social
    assert 'facebook' in social
    assert 'instagram' in social


def test_normalize_competitor_data_empty_competitors():
    """Test normalization with no competitors found"""
    agent = CompetitorResearchAgent(api_key="test-key")

    data = {}

    normalized = agent._normalize_competitor_data(data)

    assert normalized['competitors'] == []
    assert normalized['content_gaps'] == []
    assert normalized['trending_topics'] == []
    assert 'recommendation' in normalized


# ==================== Caching Tests ====================

def test_research_competitors_save_to_cache(
    mock_subprocess_competitors,
    temp_cache_dir
):
    """Test saving competitor research to cache"""
    agent = CompetitorResearchAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    result = agent.research_competitors(
        topic="marketing automation",
        save_to_cache=True
    )

    # Verify cache file was created
    cache_path = Path(temp_cache_dir) / "research"
    cache_files = list(cache_path.glob("competitors_*.json"))
    assert len(cache_files) == 1

    # Verify cached data
    with open(cache_files[0], 'r') as f:
        cached_data = json.load(f)

    assert cached_data['competitors'] == result['competitors']


def test_research_competitors_no_cache_when_disabled(
    mock_subprocess_competitors,
    temp_cache_dir
):
    """Test that caching is skipped when save_to_cache=False"""
    agent = CompetitorResearchAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    agent.research_competitors(
        topic="marketing automation",
        save_to_cache=False
    )

    # Verify no cache file was created
    cache_path = Path(temp_cache_dir) / "research"
    cache_files = list(cache_path.glob("competitors_*.json"))
    assert len(cache_files) == 0


def test_research_competitors_no_cache_without_cache_dir(mock_subprocess_competitors):
    """Test that caching is skipped when no cache_dir provided"""
    agent = CompetitorResearchAgent(api_key="test-key")

    # Should not raise error even with save_to_cache=True
    result = agent.research_competitors(
        topic="marketing",
        save_to_cache=True
    )

    assert "competitors" in result


# ==================== Integration Tests ====================

def test_research_competitors_complete_workflow(
    mock_subprocess_competitors,
    temp_cache_dir
):
    """Test complete competitor research workflow"""
    agent = CompetitorResearchAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    result = agent.research_competitors(
        topic="AI content marketing",
        language="de",
        max_competitors=5,
        include_content_analysis=True,
        save_to_cache=True
    )

    # Verify all data present
    assert len(result['competitors']) > 0
    assert len(result['content_gaps']) > 0
    assert len(result['trending_topics']) > 0
    assert result['recommendation'] != ""

    # Verify competitor structure
    competitor = result['competitors'][0]
    assert 'name' in competitor
    assert 'website' in competitor
    assert 'description' in competitor
    assert 'social_handles' in competitor
    assert 'content_strategy' in competitor

    # Verify caching worked
    cache_path = Path(temp_cache_dir) / "research"
    cache_files = list(cache_path.glob("competitors_*.json"))
    assert len(cache_files) == 1
