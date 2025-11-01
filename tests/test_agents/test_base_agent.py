"""
Tests for BaseAgent

TDD approach: Write failing tests first, then implement BaseAgent.

Test Coverage:
- Initialization with different agent types
- OpenRouter configuration loading
- Text generation with different parameters
- Error handling (API errors, rate limits, timeouts)
- Retry logic with exponential backoff
- Cost calculation
- Logging
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import yaml

from src.agents.base_agent import BaseAgent, AgentError


# ==================== Fixtures ====================

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    with patch('src.agents.base_agent.OpenAI') as mock_client:
        # Mock chat completions response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Generated text response"))]
        mock_response.usage = Mock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )

        mock_client.return_value.chat.completions.create.return_value = mock_response
        yield mock_client


@pytest.fixture
def models_config():
    """Load models.yaml for testing"""
    config_path = Path(__file__).parent.parent.parent / "config" / "models.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


# ==================== Initialization Tests ====================

def test_base_agent_init_writing_agent(mock_openai_client, models_config):
    """Test BaseAgent initialization for writing agent"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")

    # Verify agent configuration loaded correctly
    assert agent.agent_type == "writing"
    assert agent.model == models_config['agents']['writing']['model']
    assert agent.temperature == models_config['agents']['writing']['temperature']
    assert agent.max_tokens == models_config['agents']['writing']['max_tokens']

    # Verify OpenAI client initialized with OpenRouter URL
    mock_openai_client.assert_called_once()
    call_kwargs = mock_openai_client.call_args.kwargs
    assert call_kwargs['api_key'] == "test-key"
    assert call_kwargs['base_url'] == "https://openrouter.ai/api/v1"


def test_base_agent_init_repurposing_agent(mock_openai_client, models_config):
    """Test BaseAgent initialization for repurposing agent"""
    agent = BaseAgent(agent_type="repurposing", api_key="test-key")

    assert agent.agent_type == "repurposing"
    assert agent.model == models_config['agents']['repurposing']['model']
    assert agent.temperature == models_config['agents']['repurposing']['temperature']
    assert agent.max_tokens == models_config['agents']['repurposing']['max_tokens']


def test_base_agent_init_publishing_agent(mock_openai_client, models_config):
    """Test BaseAgent initialization for publishing agent"""
    agent = BaseAgent(agent_type="publishing", api_key="test-key")

    assert agent.agent_type == "publishing"
    assert agent.model == models_config['agents']['publishing']['model']


def test_base_agent_init_invalid_agent_type(mock_openai_client):
    """Test BaseAgent initialization with invalid agent type"""
    with pytest.raises(AgentError, match="Invalid agent type"):
        BaseAgent(agent_type="invalid_agent", api_key="test-key")


def test_base_agent_init_missing_api_key(mock_openai_client):
    """Test BaseAgent initialization with missing API key"""
    with pytest.raises(AgentError, match="API key is required"):
        BaseAgent(agent_type="writing", api_key="")


def test_base_agent_custom_config_override(mock_openai_client):
    """Test BaseAgent with custom configuration override"""
    custom_config = {
        "model": "custom/model",
        "temperature": 0.9,
        "max_tokens": 2000
    }

    agent = BaseAgent(
        agent_type="writing",
        api_key="test-key",
        custom_config=custom_config
    )

    assert agent.model == "custom/model"
    assert agent.temperature == 0.9
    assert agent.max_tokens == 2000


# ==================== Text Generation Tests ====================

def test_generate_success(mock_openai_client):
    """Test successful text generation"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")

    result = agent.generate(
        prompt="Write a blog post about AI",
        system_prompt="You are a German content writer"
    )

    assert result['content'] == "Generated text response"
    assert result['tokens']['prompt'] == 100
    assert result['tokens']['completion'] == 50
    assert result['tokens']['total'] == 150
    assert 'cost' in result

    # Verify OpenAI API was called correctly
    client_instance = mock_openai_client.return_value
    client_instance.chat.completions.create.assert_called_once()
    call_kwargs = client_instance.chat.completions.create.call_args.kwargs

    assert call_kwargs['model'] == "qwen/qwq-32b-preview"
    assert call_kwargs['messages'] == [
        {"role": "system", "content": "You are a German content writer"},
        {"role": "user", "content": "Write a blog post about AI"}
    ]
    assert call_kwargs['temperature'] == 0.7
    assert call_kwargs['max_tokens'] == 4000


def test_generate_without_system_prompt(mock_openai_client):
    """Test generation without system prompt"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")

    result = agent.generate(prompt="Write a blog post")

    client_instance = mock_openai_client.return_value
    call_kwargs = client_instance.chat.completions.create.call_args.kwargs

    # Should only have user message
    assert len(call_kwargs['messages']) == 1
    assert call_kwargs['messages'][0]['role'] == "user"


def test_generate_with_temperature_override(mock_openai_client):
    """Test generation with temperature override"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")

    agent.generate(prompt="Test", temperature=0.5)

    client_instance = mock_openai_client.return_value
    call_kwargs = client_instance.chat.completions.create.call_args.kwargs
    assert call_kwargs['temperature'] == 0.5


def test_generate_with_max_tokens_override(mock_openai_client):
    """Test generation with max_tokens override"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")

    agent.generate(prompt="Test", max_tokens=2000)

    client_instance = mock_openai_client.return_value
    call_kwargs = client_instance.chat.completions.create.call_args.kwargs
    assert call_kwargs['max_tokens'] == 2000


# ==================== Error Handling Tests ====================

def test_generate_api_error_with_retry(mock_openai_client):
    """Test API error handling with retry logic"""
    client_instance = mock_openai_client.return_value

    # First two calls fail, third succeeds
    client_instance.chat.completions.create.side_effect = [
        Exception("API Error"),
        Exception("API Error"),
        Mock(
            choices=[Mock(message=Mock(content="Success"))],
            usage=Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        )
    ]

    agent = BaseAgent(agent_type="writing", api_key="test-key")
    result = agent.generate(prompt="Test")

    # Should succeed after retries
    assert result['content'] == "Success"
    assert client_instance.chat.completions.create.call_count == 3


def test_generate_max_retries_exceeded(mock_openai_client):
    """Test failure when max retries exceeded"""
    client_instance = mock_openai_client.return_value
    client_instance.chat.completions.create.side_effect = Exception("API Error")

    agent = BaseAgent(agent_type="writing", api_key="test-key")

    with pytest.raises(AgentError, match="Failed after 3 retries"):
        agent.generate(prompt="Test")


def test_generate_rate_limit_error(mock_openai_client):
    """Test rate limit error handling"""
    from openai import RateLimitError

    client_instance = mock_openai_client.return_value

    # Simulate rate limit on first call, success on second
    mock_response = Mock(status_code=429)
    client_instance.chat.completions.create.side_effect = [
        RateLimitError("Rate limit exceeded", response=mock_response, body=None),
        Mock(
            choices=[Mock(message=Mock(content="Success"))],
            usage=Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        )
    ]

    agent = BaseAgent(agent_type="writing", api_key="test-key")
    result = agent.generate(prompt="Test")

    # Should succeed after retry with backoff
    assert result['content'] == "Success"


def test_generate_timeout_error(mock_openai_client):
    """Test timeout error handling"""
    from openai import APITimeoutError

    client_instance = mock_openai_client.return_value
    client_instance.chat.completions.create.side_effect = APITimeoutError("Timeout")

    agent = BaseAgent(agent_type="writing", api_key="test-key")

    with pytest.raises(AgentError, match="Failed after 3 retries"):
        agent.generate(prompt="Test")


def test_generate_empty_response(mock_openai_client):
    """Test handling of empty API response"""
    client_instance = mock_openai_client.return_value

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content=""))]
    mock_response.usage = Mock(prompt_tokens=100, completion_tokens=0, total_tokens=100)

    client_instance.chat.completions.create.return_value = mock_response

    agent = BaseAgent(agent_type="writing", api_key="test-key")

    with pytest.raises(AgentError, match="Empty response"):
        agent.generate(prompt="Test")


# ==================== Cost Calculation Tests ====================

def test_calculate_cost_writing_agent(mock_openai_client, models_config):
    """Test cost calculation for writing agent"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")

    # 100K input tokens, 50K output tokens
    cost = agent.calculate_cost(input_tokens=100000, output_tokens=50000)

    expected_cost = (100000 / 1_000_000 * 1.60) + (50000 / 1_000_000 * 6.40)
    assert cost == pytest.approx(expected_cost, rel=1e-6)


def test_calculate_cost_repurposing_agent(mock_openai_client, models_config):
    """Test cost calculation for repurposing agent"""
    agent = BaseAgent(agent_type="repurposing", api_key="test-key")

    # 80K input tokens, 30K output tokens
    cost = agent.calculate_cost(input_tokens=80000, output_tokens=30000)

    expected_cost = (80000 / 1_000_000 * 1.60) + (30000 / 1_000_000 * 6.40)
    assert cost == pytest.approx(expected_cost, rel=1e-6)


def test_calculate_cost_zero_tokens(mock_openai_client):
    """Test cost calculation with zero tokens"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")
    cost = agent.calculate_cost(input_tokens=0, output_tokens=0)
    assert cost == 0.0


def test_generate_includes_cost_in_response(mock_openai_client):
    """Test that generate() includes cost in response"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")
    result = agent.generate(prompt="Test")

    assert 'cost' in result
    assert isinstance(result['cost'], float)
    assert result['cost'] > 0


# ==================== Logging Tests ====================

def test_generate_logs_api_call(mock_openai_client, caplog):
    """Test that API calls are logged"""
    import logging
    caplog.set_level(logging.INFO)

    agent = BaseAgent(agent_type="writing", api_key="test-key")
    agent.generate(prompt="Test prompt")

    # Check that START and SUCCESS logs exist
    assert any("Generating text" in record.message for record in caplog.records)
    assert any("Generated" in record.message for record in caplog.records)


def test_generate_logs_retry_attempts(mock_openai_client, caplog):
    """Test that retry attempts are logged"""
    import logging
    caplog.set_level(logging.WARNING)

    client_instance = mock_openai_client.return_value
    client_instance.chat.completions.create.side_effect = [
        Exception("API Error"),
        Mock(
            choices=[Mock(message=Mock(content="Success"))],
            usage=Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        )
    ]

    agent = BaseAgent(agent_type="writing", api_key="test-key")
    agent.generate(prompt="Test")

    # Check that retry log exists
    assert any("Retry attempt" in record.message for record in caplog.records)


def test_generate_logs_failure(mock_openai_client, caplog):
    """Test that failures are logged"""
    import logging
    caplog.set_level(logging.ERROR)

    client_instance = mock_openai_client.return_value
    client_instance.chat.completions.create.side_effect = Exception("API Error")

    agent = BaseAgent(agent_type="writing", api_key="test-key")

    with pytest.raises(AgentError):
        agent.generate(prompt="Test")

    # Check that error log exists
    assert any("Failed" in record.message for record in caplog.records)


# ==================== Configuration Loading Tests ====================

def test_load_models_config_success(mock_openai_client):
    """Test successful loading of models.yaml"""
    agent = BaseAgent(agent_type="writing", api_key="test-key")

    # Should load config without errors
    assert agent.model is not None
    assert agent.temperature is not None
    assert agent.max_tokens is not None


def test_load_models_config_missing_file(mock_openai_client):
    """Test handling of missing models.yaml file"""
    with patch('pathlib.Path.exists', return_value=False):
        with pytest.raises(AgentError, match="models.yaml not found"):
            BaseAgent(agent_type="writing", api_key="test-key")


def test_load_models_config_invalid_yaml(mock_openai_client):
    """Test handling of invalid YAML in models.yaml"""
    with patch('builtins.open', mock_open(read_data="invalid: yaml: content:")):
        with pytest.raises(AgentError, match="Failed to load models.yaml"):
            BaseAgent(agent_type="writing", api_key="test-key")


# ==================== Helper Functions ====================

def mock_open(read_data):
    """Helper to mock file open"""
    from unittest.mock import mock_open as _mock_open
    return _mock_open(read_data=read_data)
