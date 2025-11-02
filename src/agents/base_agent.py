"""
BaseAgent - OpenRouter Integration

Base class for all AI agents with OpenRouter API support.

Design Principles:
- Single responsibility (only handles LLM API calls)
- Configuration from models.yaml
- Retry logic with exponential backoff
- Cost calculation
- Comprehensive logging
"""

import logging
import time
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from openai import OpenAI, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for agent errors"""
    pass


class BaseAgent:
    """
    Base AI agent with OpenRouter integration.

    Handles:
    - Model configuration loading from models.yaml
    - OpenAI client initialization with OpenRouter base URL
    - Text generation with retry logic
    - Cost calculation based on token usage
    - Comprehensive logging

    Usage:
        agent = BaseAgent(agent_type="writing", api_key="sk-xxx")
        result = agent.generate(
            prompt="Write a blog post",
            system_prompt="You are a German content writer"
        )
        print(result['content'])
        print(f"Cost: ${result['cost']:.4f}")
    """

    # Retry configuration
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 1

    def __init__(
        self,
        agent_type: str,
        api_key: str,
        custom_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize BaseAgent.

        Args:
            agent_type: Type of agent (writing, repurposing, publishing)
            api_key: OpenRouter API key
            custom_config: Optional custom configuration override

        Raises:
            AgentError: If configuration is invalid or API key is missing
        """
        if not api_key or not api_key.strip():
            raise AgentError("API key is required")

        self.agent_type = agent_type
        self.api_key = api_key

        # Load configuration
        self._load_config(custom_config)

        # Initialize OpenAI client with OpenRouter base URL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.openrouter_base_url
        )

        logger.info(
            f"BaseAgent initialized: type={agent_type}, "
            f"model={self.model}, "
            f"temperature={self.temperature}"
        )

    def _load_config(self, custom_config: Optional[Dict[str, Any]] = None) -> None:
        """
        Load configuration from models.yaml or custom_config.

        Args:
            custom_config: Optional custom configuration override

        Raises:
            AgentError: If models.yaml not found or invalid
        """
        # Load models.yaml
        config_path = Path(__file__).parent.parent.parent / "config" / "models.yaml"

        if not config_path.exists():
            raise AgentError(f"models.yaml not found at {config_path}")

        try:
            with open(config_path, 'r') as f:
                full_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise AgentError(f"Failed to load models.yaml: {e}") from e

        # Get OpenRouter base URL
        self.openrouter_base_url = full_config.get('openrouter', {}).get(
            'base_url',
            'https://openrouter.ai/api/v1'
        )

        # Get agent-specific configuration
        agents_config = full_config.get('agents', {})

        if self.agent_type not in agents_config:
            valid_types = ', '.join(agents_config.keys())
            raise AgentError(
                f"Invalid agent type: {self.agent_type}. "
                f"Valid types: {valid_types}"
            )

        agent_config = agents_config[self.agent_type]

        # Apply custom config override if provided
        if custom_config:
            agent_config = {**agent_config, **custom_config}

        # Set agent properties
        self.model = agent_config.get('model')
        self.temperature = agent_config.get('temperature', 0.7)
        self.max_tokens = agent_config.get('max_tokens', 4000)
        self.cost_per_1m_input = agent_config.get('cost_per_1m_input', 0.0)
        self.cost_per_1m_output = agent_config.get('cost_per_1m_output', 0.0)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generate text using OpenRouter API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Optional temperature override
            max_tokens: Optional max_tokens override
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            Dict with:
                - content: Generated text
                - tokens: Dict with prompt, completion, total counts
                - cost: Estimated cost in USD

        Raises:
            AgentError: If generation fails after max retries
        """
        logger.info(
            f"Generating text: agent={self.agent_type}, "
            f"model={self.model}, "
            f"prompt_length={len(prompt)}, "
            f"response_format={response_format}"
        )

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Use overrides or defaults
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                # Build API call parameters
                api_params = {
                    'model': self.model,
                    'messages': messages,
                    'temperature': temp,
                    'max_tokens': tokens
                }

                # Add response_format if specified
                if response_format:
                    api_params['response_format'] = response_format

                response = self.client.chat.completions.create(**api_params)

                # Extract content
                content = response.choices[0].message.content

                if not content or not content.strip():
                    raise AgentError("Empty response from API")

                # Extract token usage
                usage = response.usage
                tokens_used = {
                    'prompt': usage.prompt_tokens,
                    'completion': usage.completion_tokens,
                    'total': usage.total_tokens
                }

                # Calculate cost
                cost = self.calculate_cost(
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens
                )

                logger.info(
                    f"Generated text successfully: "
                    f"tokens={tokens_used['total']}, "
                    f"cost=${cost:.4f}"
                )

                return {
                    'content': content,
                    'tokens': tokens_used,
                    'cost': cost
                }

            except (RateLimitError, APITimeoutError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self.BASE_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.MAX_RETRIES} "
                        f"after {backoff}s: {e}"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Failed after {self.MAX_RETRIES} retries: {e}")

            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self.BASE_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.MAX_RETRIES} "
                        f"after {backoff}s: {e}"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Failed after {self.MAX_RETRIES} retries: {e}")

        # All retries exhausted
        raise AgentError(
            f"Failed after {self.MAX_RETRIES} retries: {last_error}"
        ) from last_error

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost based on token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * self.cost_per_1m_input
        output_cost = (output_tokens / 1_000_000) * self.cost_per_1m_output
        return input_cost + output_cost
