"""
ResearchAgent - Web Research with Gemini CLI

Performs web research using Gemini CLI (FREE Google Search) with fallback to API.

Design Principles:
- Gemini CLI first (FREE), API fallback (also FREE)
- Subprocess management with timeout
- JSON response parsing with validation
- Comprehensive error handling
- Structured research data output
"""

import logging
import subprocess
import json
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent, AgentError

logger = logging.getLogger(__name__)


class ResearchError(Exception):
    """Base exception for research errors"""
    pass


class ResearchAgent(BaseAgent):
    """
    Web research agent using Gemini CLI with API fallback.

    Features:
    - Gemini CLI integration (FREE Google Search)
    - Automatic fallback to Gemini API via OpenRouter
    - JSON response parsing and validation
    - Subprocess error handling
    - Structured research data output

    Usage:
        agent = ResearchAgent(api_key="sk-xxx")
        result = agent.research(
            topic="AI content marketing",
            language="de"
        )
        print(result['sources'])
        print(result['keywords'])
        print(result['summary'])
    """

    def __init__(
        self,
        api_key: str,
        use_cli: bool = True,
        cli_timeout: int = 60
    ):
        """
        Initialize ResearchAgent.

        Args:
            api_key: OpenRouter API key (for fallback)
            use_cli: Use Gemini CLI (default: True)
            cli_timeout: CLI timeout in seconds (default: 60)

        Raises:
            AgentError: If initialization fails
        """
        # Initialize base agent with research config
        super().__init__(agent_type="research", api_key=api_key)

        self.use_cli = use_cli
        self.cli_timeout = cli_timeout

        logger.info(
            f"ResearchAgent initialized: "
            f"use_cli={use_cli}, timeout={cli_timeout}s"
        )

    def research(
        self,
        topic: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Perform web research on topic.

        Args:
            topic: Research topic
            language: Content language (ISO 639-1 code, default: en)

        Returns:
            Dict with:
                - sources: List of source dicts (url, title, snippet)
                - keywords: List of relevant keywords
                - summary: Research summary

        Raises:
            ResearchError: If research fails
        """
        # Validate input
        if not topic or not topic.strip():
            raise ResearchError("Topic is required")

        topic = topic.strip()

        logger.info(f"Starting research: topic='{topic}', language={language}")

        # Try Gemini CLI first (if enabled)
        if self.use_cli:
            try:
                result = self._research_with_cli(topic, language)
                logger.info("Research completed using Gemini CLI")
                return result
            except Exception as e:
                logger.warning(
                    f"Gemini CLI failed: {e}. Falling back to API"
                )

        # Fallback to API
        try:
            result = self._research_with_api(topic, language)
            logger.info("Research completed using API fallback")
            return result
        except Exception as e:
            logger.error(f"Research failed: {e}")
            raise ResearchError(f"Research failed: {e}") from e

    def _research_with_cli(
        self,
        topic: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Perform research using Gemini CLI.

        Args:
            topic: Research topic
            language: Content language

        Returns:
            Parsed research data

        Raises:
            Exception: If CLI fails or returns invalid data
        """
        # Build Gemini CLI command
        language_hint = f" in {language}" if language != "en" else ""
        command = [
            "gemini",
            "search",
            f"{topic}{language_hint}",
            "--format", "json"
        ]

        logger.info(f"Running Gemini CLI: {' '.join(command)}")

        # Run subprocess with timeout
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.cli_timeout
            )
        except subprocess.TimeoutExpired as e:
            raise Exception(f"Gemini CLI timeout after {self.cli_timeout}s") from e
        except subprocess.SubprocessError as e:
            raise Exception(f"Gemini CLI subprocess error: {e}") from e

        # Check return code
        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            raise Exception(f"Gemini CLI failed (code {result.returncode}): {error_msg}")

        # Parse JSON response
        if not result.stdout or not result.stdout.strip():
            raise Exception("Empty response from Gemini CLI")

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON from Gemini CLI: {e}") from e

        # Validate and normalize data
        return self._normalize_research_data(data)

    def _research_with_api(
        self,
        topic: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Perform research using Gemini API via OpenRouter.

        Args:
            topic: Research topic
            language: Content language

        Returns:
            Parsed research data

        Raises:
            AgentError: If API call fails
        """
        language_name = self._get_language_name(language)

        system_prompt = (
            f"You are a research assistant. Perform web research on the given topic "
            f"and return results in JSON format with:\n"
            f"- sources: Array of {{url, title, snippet}}\n"
            f"- keywords: Array of relevant keywords\n"
            f"- summary: Brief research summary\n\n"
            f"Language: {language_name}\n\n"
            f"IMPORTANT: You must return valid JSON only, no additional text."
        )

        user_prompt = (
            f"Research topic: {topic}\n\n"
            f"Return comprehensive research results in JSON format."
        )

        # Call API with JSON mode enabled
        result = self.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_format={"type": "json_object"}
        )

        # Parse JSON from content
        try:
            data = json.loads(result['content'])
        except json.JSONDecodeError as e:
            raise AgentError(f"Invalid JSON from API: {e}") from e

        # Validate and normalize data
        return self._normalize_research_data(data)

    def _normalize_research_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and validate research data.

        Args:
            data: Raw research data

        Returns:
            Normalized data with all required fields
        """
        return {
            'sources': data.get('sources', []),
            'keywords': data.get('keywords', []),
            'summary': data.get('summary', 'No summary available')
        }

    def _get_language_name(self, language_code: str) -> str:
        """
        Get language name from ISO 639-1 code.

        Args:
            language_code: ISO 639-1 code (e.g., 'de', 'en')

        Returns:
            Language name (e.g., 'German', 'English')
        """
        language_map = {
            'de': 'German (Deutsch)',
            'en': 'English',
            'es': 'Spanish (Español)',
            'fr': 'French (Français)',
            'it': 'Italian (Italiano)',
            'pt': 'Portuguese (Português)',
            'nl': 'Dutch (Nederlands)',
            'pl': 'Polish (Polski)',
            'ru': 'Russian (Русский)',
            'ja': 'Japanese (日本語)',
            'zh': 'Chinese (中文)',
            'ko': 'Korean (한국어)',
            'ar': 'Arabic (العربية)',
            'hi': 'Hindi (हिन्दी)',
            'tr': 'Turkish (Türkçe)',
            'vi': 'Vietnamese (Tiếng Việt)',
            'th': 'Thai (ไทย)',
            'id': 'Indonesian (Bahasa Indonesia)',
        }

        return language_map.get(language_code.lower(), f'Language: {language_code}')
