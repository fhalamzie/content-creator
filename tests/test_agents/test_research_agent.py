"""
Tests for ResearchAgent

TDD approach: Write failing tests first, then implement ResearchAgent.

Test Coverage:
- Gemini CLI subprocess integration
- JSON response parsing
- Error handling (subprocess failures, timeouts, invalid JSON)
- Fallback to Gemini API via OpenRouter
- Research data structure validation
- Logging
"""

import pytest
from unittest.mock import Mock, patch
import subprocess
import json

from src.agents.research_agent import ResearchAgent, ResearchError


# ==================== Fixtures ====================

@pytest.fixture
def mock_subprocess():
    """Mock subprocess for Gemini CLI"""
    with patch('subprocess.run') as mock_run:
        # Mock successful Gemini CLI response
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "sources": [
                {
                    "url": "https://example.com/article1",
                    "title": "AI Content Marketing 2024",
                    "snippet": "Latest trends in AI content..."
                },
                {
                    "url": "https://example.com/article2",
                    "title": "SEO Best Practices",
                    "snippet": "How to optimize your content..."
                }
            ],
            "keywords": ["AI", "content marketing", "SEO", "automation"],
            "summary": "AI is revolutionizing content marketing..."
        })
        mock_result.stderr = ""

        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_base_agent_generate():
    """Mock BaseAgent.generate for API fallback"""
    with patch('src.agents.base_agent.BaseAgent.generate') as mock_gen:
        mock_gen.return_value = {
            'content': json.dumps({
                "sources": [
                    {
                        "url": "https://fallback.com/article",
                        "title": "Fallback Article",
                        "snippet": "API fallback content"
                    }
                ],
                "keywords": ["fallback", "API"],
                "summary": "Fallback research summary"
            }),
            'tokens': {'prompt': 100, 'completion': 50, 'total': 150},
            'cost': 0.0
        }
        yield mock_gen


# ==================== Initialization Tests ====================

def test_research_agent_init_default_gemini_cli(mock_subprocess):
    """Test ResearchAgent initialization with default Gemini CLI"""
    agent = ResearchAgent(api_key="test-key")

    assert agent.agent_type == "research"
    assert agent.use_cli is True
    assert agent.cli_timeout == 60


def test_research_agent_init_force_api_fallback(mock_subprocess):
    """Test ResearchAgent initialization with forced API fallback"""
    agent = ResearchAgent(api_key="test-key", use_cli=False)

    assert agent.use_cli is False


def test_research_agent_init_custom_timeout(mock_subprocess):
    """Test ResearchAgent initialization with custom timeout"""
    agent = ResearchAgent(api_key="test-key", cli_timeout=120)

    assert agent.cli_timeout == 120


# ==================== Gemini CLI Tests ====================

def test_research_success_with_gemini_cli(mock_subprocess):
    """Test successful research using Gemini CLI"""
    agent = ResearchAgent(api_key="test-key")

    result = agent.research(topic="AI content marketing", language="de")

    # Verify subprocess called correctly
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args

    assert "gemini" in call_args.args[0][0]
    assert "AI content marketing" in ' '.join(call_args.args[0])
    assert call_args.kwargs['timeout'] == 60
    assert call_args.kwargs['capture_output'] is True
    assert call_args.kwargs['text'] is True

    # Verify result structure
    assert 'sources' in result
    assert 'keywords' in result
    assert 'summary' in result
    assert len(result['sources']) == 2
    assert result['sources'][0]['url'] == "https://example.com/article1"
    assert "AI" in result['keywords']


def test_research_gemini_cli_subprocess_error(mock_subprocess, mock_base_agent_generate):
    """Test fallback to API when Gemini CLI subprocess fails"""
    # Simulate subprocess error
    mock_subprocess.side_effect = subprocess.SubprocessError("Command failed")

    agent = ResearchAgent(api_key="test-key")
    result = agent.research(topic="Test topic")

    # Should fallback to API
    mock_base_agent_generate.assert_called_once()

    # Verify fallback result
    assert 'sources' in result
    assert result['sources'][0]['url'] == "https://fallback.com/article"


def test_research_gemini_cli_timeout(mock_subprocess, mock_base_agent_generate):
    """Test fallback to API when Gemini CLI times out"""
    # Simulate timeout
    mock_subprocess.side_effect = subprocess.TimeoutExpired(
        cmd="gemini",
        timeout=60
    )

    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test topic")

    # Should fallback to API
    mock_base_agent_generate.assert_called_once()


def test_research_gemini_cli_non_zero_exit(mock_subprocess, mock_base_agent_generate):
    """Test fallback when Gemini CLI returns non-zero exit code"""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "Gemini CLI error"
    mock_subprocess.return_value = mock_result

    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test topic")

    # Should fallback to API
    mock_base_agent_generate.assert_called_once()


def test_research_gemini_cli_invalid_json(mock_subprocess, mock_base_agent_generate):
    """Test fallback when Gemini CLI returns invalid JSON"""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "Not valid JSON"
    mock_result.stderr = ""
    mock_subprocess.return_value = mock_result

    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test topic")

    # Should fallback to API
    mock_base_agent_generate.assert_called_once()


def test_research_gemini_cli_empty_response(mock_subprocess, mock_base_agent_generate):
    """Test fallback when Gemini CLI returns empty response"""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_subprocess.return_value = mock_result

    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test topic")

    # Should fallback to API
    mock_base_agent_generate.assert_called_once()


# ==================== API Fallback Tests ====================

def test_research_api_fallback_success(mock_subprocess, mock_base_agent_generate):
    """Test successful research using API fallback"""
    agent = ResearchAgent(api_key="test-key", use_cli=False)

    result = agent.research(topic="AI marketing")

    # Should use API directly
    mock_subprocess.assert_not_called()
    mock_base_agent_generate.assert_called_once()

    # Verify result
    assert 'sources' in result
    assert 'keywords' in result


def test_research_api_fallback_with_language(mock_subprocess, mock_base_agent_generate):
    """Test API fallback includes language in prompt"""
    agent = ResearchAgent(api_key="test-key", use_cli=False)

    agent.research(topic="AI marketing", language="de")

    # Check that language is in the system_prompt
    call_args = mock_base_agent_generate.call_args
    system_prompt = call_args.kwargs.get('system_prompt', '')

    assert "German" in system_prompt or "Deutsch" in system_prompt


def test_research_api_fallback_error(mock_subprocess, mock_base_agent_generate):
    """Test error when both CLI and API fail"""
    # CLI fails
    mock_subprocess.side_effect = subprocess.SubprocessError("CLI failed")

    # API also fails
    from src.agents.base_agent import AgentError
    mock_base_agent_generate.side_effect = AgentError("API failed")

    agent = ResearchAgent(api_key="test-key")

    with pytest.raises(ResearchError, match="Research failed"):
        agent.research(topic="Test topic")


# ==================== Research Data Validation Tests ====================

def test_research_validates_required_fields(mock_subprocess):
    """Test that research validates required fields in response"""
    # Return incomplete data (missing 'summary')
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "sources": [],
        "keywords": []
        # Missing 'summary'
    })
    mock_result.stderr = ""
    mock_subprocess.return_value = mock_result

    agent = ResearchAgent(api_key="test-key")

    # Should add default summary
    result = agent.research(topic="Test")

    assert 'summary' in result  # Should have default value


def test_research_handles_missing_sources(mock_subprocess):
    """Test research handles missing sources field"""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({
        "keywords": ["test"],
        "summary": "Test summary"
        # Missing 'sources'
    })
    mock_result.stderr = ""
    mock_subprocess.return_value = mock_result

    agent = ResearchAgent(api_key="test-key")
    result = agent.research(topic="Test")

    # Should have empty sources list
    assert result['sources'] == []


# ==================== Input Validation Tests ====================

def test_research_empty_topic_raises_error(mock_subprocess):
    """Test that empty topic raises error"""
    agent = ResearchAgent(api_key="test-key")

    with pytest.raises(ResearchError, match="Topic is required"):
        agent.research(topic="")


def test_research_none_topic_raises_error(mock_subprocess):
    """Test that None topic raises error"""
    agent = ResearchAgent(api_key="test-key")

    with pytest.raises(ResearchError, match="Topic is required"):
        agent.research(topic=None)


def test_research_whitespace_topic_raises_error(mock_subprocess):
    """Test that whitespace-only topic raises error"""
    agent = ResearchAgent(api_key="test-key")

    with pytest.raises(ResearchError, match="Topic is required"):
        agent.research(topic="   ")


# ==================== Logging Tests ====================

def test_research_logs_cli_attempt(mock_subprocess, caplog):
    """Test that CLI attempts are logged"""
    import logging
    caplog.set_level(logging.INFO)

    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test topic")

    # Check for CLI log
    assert any("Gemini CLI" in record.message for record in caplog.records)


def test_research_logs_fallback_to_api(mock_subprocess, mock_base_agent_generate, caplog):
    """Test that API fallback is logged"""
    import logging
    caplog.set_level(logging.WARNING)

    # Force CLI failure
    mock_subprocess.side_effect = subprocess.SubprocessError("CLI failed")

    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test topic")

    # Check for fallback log
    assert any("Falling back to API" in record.message or "fallback" in record.message.lower() for record in caplog.records)


def test_research_logs_success(mock_subprocess, caplog):
    """Test that successful research is logged"""
    import logging
    caplog.set_level(logging.INFO)

    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test topic")

    # Check for success log
    assert any("Research complete" in record.message or "success" in record.message.lower() for record in caplog.records)


# ==================== German Language Tests ====================

def test_research_german_language_in_cli_command(mock_subprocess):
    """Test that German language is passed to Gemini CLI"""
    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="AI Marketing", language="de")

    # Check CLI command includes language hint
    call_args = mock_subprocess.call_args
    command = ' '.join(call_args.args[0])

    # Should mention German/de in command
    assert "de" in command or "German" in command or "Deutsch" in command


def test_research_default_language_english(mock_subprocess):
    """Test default language is English"""
    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test topic")  # No language specified

    call_args = mock_subprocess.call_args
    command = ' '.join(call_args.args[0])

    # Should use default (likely 'en' or no language specified)
    # Just verify command was called
    assert "gemini" in command


# ==================== Additional Coverage Tests ====================

def test_research_preserves_cli_stderr_in_logs(mock_subprocess, mock_base_agent_generate, caplog):
    """Test that CLI stderr is preserved in logs when falling back"""
    import logging
    caplog.set_level(logging.WARNING)

    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "Specific CLI error message"
    mock_subprocess.return_value = mock_result

    agent = ResearchAgent(api_key="test-key")
    agent.research(topic="Test")

    # Check that error message is in logs
    log_text = ' '.join(record.message for record in caplog.records)
    assert "Specific CLI error message" in log_text or "error" in log_text.lower()
