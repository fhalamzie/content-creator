"""
Gemini Agent with Google Search Grounding Support

Uses the native Google Gemini API (not OpenRouter) to enable:
- Google Search grounding (web research)
- Structured JSON output via responseSchema
- Free tier: 1,500 grounded queries/day

Architecture:
- Uses google-generativeai SDK (not OpenAI client)
- Supports grounding with automatic web search
- Returns structured JSON with citations

Usage:
    agent = GeminiAgent(
        model="gemini-2.5-flash",
        api_key=os.getenv("GEMINI_API_KEY"),
        enable_grounding=True
    )

    result = agent.generate(
        prompt="Find top PropTech competitors",
        response_schema={
            "type": "object",
            "properties": {
                "competitors": {"type": "array"},
                "sources": {"type": "array"}
            }
        }
    )
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    raise ImportError(
        "google-genai not installed. Install with: pip install google-genai"
    )

from src.utils.logger import get_logger
from src.utils.json_parser import extract_json_from_text, schema_to_json_prompt

logger = get_logger(__name__)


class GeminiAgentError(Exception):
    """Gemini agent errors"""
    pass


class GeminiAgent:
    """
    Native Gemini API agent with Google Search grounding support.

    Features:
    - Google Search grounding (web research)
    - Structured JSON output (responseSchema)
    - Free tier: 1,500 grounded queries/day
    - Citation metadata (sources, queries, grounding info)

    Models supported:
    - gemini-2.5-pro (50 RPD free, 1,500 grounding/day)
    - gemini-2.5-flash (250 RPD free, 1,500 grounding/day)
    - gemini-2.5-flash-lite (1,000 RPD free, 1,500 grounding/day)
    """

    # Retry configuration
    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 1

    # Default models
    DEFAULT_MODEL = "gemini-2.5-flash"

    # Cost per 1M tokens (paid tier, after free quota)
    COST_PER_1M_INPUT = {
        "gemini-2.5-pro": 1.25,
        "gemini-2.5-flash": 0.075,
        "gemini-2.5-flash-lite": 0.0375
    }
    COST_PER_1M_OUTPUT = {
        "gemini-2.5-pro": 5.00,
        "gemini-2.5-flash": 0.30,
        "gemini-2.5-flash-lite": 0.15
    }

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        enable_grounding: bool = True,
        temperature: float = 0.3,
        max_tokens: int = 8000
    ):
        """
        Initialize GeminiAgent.

        Args:
            model: Gemini model name (default: gemini-2.5-flash)
            api_key: Google AI API key (loads from GEMINI_API_KEY env if not provided)
            enable_grounding: Enable Google Search grounding (default: True)
            temperature: Sampling temperature 0.0-1.0 (default: 0.3)
            max_tokens: Maximum output tokens (default: 8000)

        Raises:
            GeminiAgentError: If API key is missing or invalid
        """
        # Load API key
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY")

        if not api_key or not api_key.strip():
            raise GeminiAgentError(
                "GEMINI_API_KEY required. Set environment variable or pass api_key parameter."
            )

        self.model_name = model
        self.api_key = api_key
        self.enable_grounding = enable_grounding
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize Gemini client (new SDK)
        self.client = genai.Client(api_key=self.api_key)

        logger.info(
            f"GeminiAgent initialized: model={model}, "
            f"grounding={enable_grounding}, temp={temperature}"
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        enable_grounding: Optional[bool] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate text using Gemini API with optional grounding.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            response_schema: JSON schema for structured output (JSON object schema)
            enable_grounding: Override default grounding setting
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Dict with:
                - content: Generated text or structured JSON
                - grounding_metadata: Citations and sources (if grounding enabled)
                - tokens: Token usage
                - cost: Estimated cost in USD

        Raises:
            GeminiAgentError: If generation fails
        """
        logger.info(
            f"Generating with Gemini: model={self.model_name}, "
            f"prompt_length={len(prompt)}, "
            f"grounding={enable_grounding if enable_grounding is not None else self.enable_grounding}"
        )

        # Use overrides or defaults
        use_grounding = enable_grounding if enable_grounding is not None else self.enable_grounding
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        try:
            # Build tools (grounding) - new SDK uses google_search
            # NOTE: Gemini API doesn't support tools + JSON schema simultaneously
            # WORKAROUND: Use grounding + JSON-in-prompt, then parse manually
            tools = None
            use_json_in_prompt = False

            if use_grounding and response_schema:
                # WORKAROUND: Request JSON in prompt instead of schema
                logger.info(
                    "grounding_with_json_workaround",
                    message="Using grounding + JSON-in-prompt workaround (Gemini API limitation)"
                )
                tools = [types.Tool(google_search=types.GoogleSearch())]
                use_json_in_prompt = True
            elif use_grounding:
                # Normal grounding without JSON schema
                tools = [types.Tool(google_search=types.GoogleSearch())]

            # Combine system prompt and user prompt
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            # Add JSON schema instructions to prompt (workaround)
            if use_json_in_prompt and response_schema:
                json_instructions = schema_to_json_prompt(response_schema)
                full_prompt = f"{full_prompt}\n\n{json_instructions}"

            # Build generation config (new SDK)
            config = types.GenerateContentConfig(
                temperature=temp,
                max_output_tokens=tokens,
                # Only use response_schema if NOT using JSON-in-prompt workaround
                response_mime_type="application/json" if (response_schema and not use_json_in_prompt) else None,
                response_schema=response_schema if not use_json_in_prompt else None,
                tools=tools
            )

            # Generate content (new SDK API)
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=config
            )

            # Extract content
            content = response.text

            if not content or not content.strip():
                raise GeminiAgentError("Empty response from Gemini API")

            # Extract grounding metadata FIRST (new SDK: in candidates[0])
            # Do this before JSON parsing to ensure metadata is always available
            grounding_metadata = None
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    grounding_metadata = self._extract_grounding_metadata(candidate.grounding_metadata)

            # Parse JSON if using workaround
            if use_json_in_prompt and response_schema:
                logger.debug("parsing_json_from_grounded_response")
                try:
                    # Extract JSON from response (may have extra text)
                    parsed_json = extract_json_from_text(content, response_schema)
                    # Convert back to JSON string for consistency
                    content = json.dumps(parsed_json, ensure_ascii=False)
                    logger.info("json_parsed_successfully", keys=list(parsed_json.keys()))
                except Exception as e:
                    logger.error("json_parsing_failed", error=str(e), content_preview=content[:300])
                    # Don't fail - return raw content and let caller handle it
                    logger.warning("returning_raw_content_due_to_parse_error")

            # Extract token usage
            tokens_used = {
                'prompt': response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
                'completion': response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
                'total': response.usage_metadata.total_token_count if response.usage_metadata else 0
            }

            # Calculate cost
            cost = self._calculate_cost(
                input_tokens=tokens_used['prompt'],
                output_tokens=tokens_used['completion']
            )

            logger.info(
                f"Generated successfully: "
                f"tokens={tokens_used['total']}, "
                f"cost=${cost:.4f}, "
                f"grounded={grounding_metadata is not None}"
            )

            result = {
                'content': content,
                'tokens': tokens_used,
                'cost': cost
            }

            if grounding_metadata:
                result['grounding_metadata'] = grounding_metadata

            return result

        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise GeminiAgentError(f"Generation failed: {e}") from e

    def _extract_grounding_metadata(self, metadata) -> Dict[str, Any]:
        """
        Extract grounding metadata (sources, citations).

        Args:
            metadata: Gemini grounding metadata object

        Returns:
            Dict with search_queries, sources, grounding_supports
        """
        try:
            result = {
                'search_queries': [],
                'sources': [],
                'grounding_supports': []
            }

            # Extract search queries (new SDK has web_search_queries)
            if hasattr(metadata, 'web_search_queries') and metadata.web_search_queries:
                result['search_queries'].extend(metadata.web_search_queries)
            elif hasattr(metadata, 'search_entry_point') and metadata.search_entry_point:
                if hasattr(metadata.search_entry_point, 'rendered_content'):
                    result['search_queries'].append(metadata.search_entry_point.rendered_content)

            # Extract sources
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web') and chunk.web:
                        result['sources'].append({
                            'url': chunk.web.uri if hasattr(chunk.web, 'uri') else None,
                            'title': chunk.web.title if hasattr(chunk.web, 'title') else None
                        })

            # Extract grounding supports
            if hasattr(metadata, 'grounding_supports') and metadata.grounding_supports:
                for support in metadata.grounding_supports:
                    result['grounding_supports'].append({
                        'segment_text': support.segment.text if hasattr(support, 'segment') else None,
                        'source_indices': list(support.grounding_chunk_indices) if hasattr(support, 'grounding_chunk_indices') else []
                    })

            return result

        except Exception as e:
            logger.warning(f"Failed to extract grounding metadata: {e}")
            return {'error': str(e)}

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost based on token usage.

        Note: Free tier provides generous quotas before charges apply.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD (based on paid tier pricing)
        """
        # Get model-specific pricing
        input_cost_per_1m = self.COST_PER_1M_INPUT.get(self.model_name, 1.0)
        output_cost_per_1m = self.COST_PER_1M_OUTPUT.get(self.model_name, 5.0)

        input_cost = (input_tokens / 1_000_000) * input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * output_cost_per_1m

        return input_cost + output_cost
