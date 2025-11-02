"""
CompetitorResearchAgent - Competitor Analysis with Gemini CLI

Performs competitor research using Gemini CLI (FREE Google Search) with fallback to API.

Design Principles:
- Gemini CLI first (FREE), API fallback (also FREE)
- Subprocess management with timeout
- JSON response parsing with validation
- Comprehensive error handling
- Structured competitor data output
- Cache integration
"""

import logging
import subprocess
import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.agents.base_agent import BaseAgent, AgentError
from src.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class CompetitorResearchError(Exception):
    """Base exception for competitor research errors"""
    pass


class CompetitorResearchAgent(BaseAgent):
    """
    Competitor research agent using Gemini CLI with API fallback.

    Features:
    - Gemini CLI integration (FREE Google Search)
    - Automatic fallback to Gemini API via OpenRouter
    - JSON response parsing and validation
    - Subprocess error handling
    - Structured competitor data output
    - Cache integration

    Usage:
        agent = CompetitorResearchAgent(api_key="sk-xxx")
        result = agent.research_competitors(
            topic="content marketing software",
            language="de",
            max_competitors=5
        )
        print(result['competitors'])
        print(result['content_gaps'])
    """

    def __init__(
        self,
        api_key: str,
        use_cli: bool = True,
        cli_timeout: int = 60,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize CompetitorResearchAgent.

        Args:
            api_key: OpenRouter API key (for fallback)
            use_cli: Use Gemini CLI (default: True)
            cli_timeout: CLI timeout in seconds (default: 60)
            cache_dir: Optional cache directory

        Raises:
            AgentError: If initialization fails
        """
        # Initialize base agent with research config
        super().__init__(agent_type="research", api_key=api_key)

        self.use_cli = use_cli
        self.cli_timeout = cli_timeout

        # Initialize cache manager if cache_dir provided
        self.cache_manager = None
        if cache_dir:
            self.cache_manager = CacheManager(cache_dir=cache_dir)

        logger.info(
            f"CompetitorResearchAgent initialized: "
            f"use_cli={use_cli}, timeout={cli_timeout}s, cache={cache_dir is not None}"
        )

    def research_competitors(
        self,
        topic: str,
        language: str = "en",
        max_competitors: int = 5,
        include_content_analysis: bool = True,
        save_to_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Perform competitor research on topic.

        Args:
            topic: Research topic or niche
            language: Content language (ISO 639-1 code, default: en)
            max_competitors: Maximum number of competitors to analyze (default: 5)
            include_content_analysis: Include content strategy analysis (default: True)
            save_to_cache: Save results to cache (default: False)

        Returns:
            Dict with:
                - competitors: List of competitor dicts
                - content_gaps: List of content opportunities
                - trending_topics: List of trending topics in niche
                - recommendation: Strategic recommendation

        Raises:
            CompetitorResearchError: If research fails
        """
        # Validate input
        if not topic or not topic.strip():
            raise CompetitorResearchError("Topic is required")

        topic = topic.strip()

        logger.info(
            f"Starting competitor research: topic='{topic}', "
            f"language={language}, max={max_competitors}"
        )

        # Try Gemini CLI first (if enabled)
        if self.use_cli:
            try:
                result = self._research_with_cli(
                    topic, language, max_competitors, include_content_analysis
                )
                logger.info("Competitor research completed using Gemini CLI")

                # Save to cache if requested
                if save_to_cache and self.cache_manager:
                    self._save_to_cache(topic, result)

                return result
            except Exception as e:
                logger.warning(
                    f"Gemini CLI failed: {e}. Falling back to API"
                )

        # Fallback to API
        try:
            result = self._research_with_api(
                topic, language, max_competitors, include_content_analysis
            )
            logger.info("Competitor research completed using API fallback")

            # Save to cache if requested
            if save_to_cache and self.cache_manager:
                self._save_to_cache(topic, result)

            return result
        except Exception as e:
            logger.error(f"Competitor research failed: {e}")
            raise CompetitorResearchError(
                f"Competitor research failed: {e}"
            ) from e

    def _research_with_cli(
        self,
        topic: str,
        language: str,
        max_competitors: int,
        include_content_analysis: bool
    ) -> Dict[str, Any]:
        """
        Perform competitor research using Gemini CLI.

        Args:
            topic: Research topic
            language: Content language
            max_competitors: Maximum competitors
            include_content_analysis: Include content analysis

        Returns:
            Parsed competitor data

        Raises:
            Exception: If CLI fails or returns invalid data
        """
        # Build Gemini CLI command with specific instructions
        language_hint = f" in {language}" if language != "en" else ""
        analysis_hint = " with content strategy analysis" if include_content_analysis else ""

        search_query = (
            f"Find top {max_competitors} competitors for {topic}{language_hint}. "
            f"Include company names, websites, social media handles{analysis_hint}. "
            f"Identify content gaps and trending topics. Return JSON format."
        )

        command = [
            "gemini",
            "search",
            search_query,
            "--format", "json"
        ]

        logger.info(f"Running Gemini CLI for competitor research")

        # Run subprocess with timeout
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.cli_timeout
            )
        except subprocess.TimeoutExpired as e:
            raise Exception(
                f"Gemini CLI timeout after {self.cli_timeout}s"
            ) from e
        except subprocess.SubprocessError as e:
            raise Exception(f"Gemini CLI subprocess error: {e}") from e

        # Check return code
        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            raise Exception(
                f"Gemini CLI failed (code {result.returncode}): {error_msg}"
            )

        # Parse JSON response
        if not result.stdout or not result.stdout.strip():
            raise Exception("Empty response from Gemini CLI")

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON from Gemini CLI: {e}") from e

        # Validate and normalize data
        return self._normalize_competitor_data(data)

    def _research_with_api(
        self,
        topic: str,
        language: str,
        max_competitors: int,
        include_content_analysis: bool
    ) -> Dict[str, Any]:
        """
        Perform competitor research using Gemini API via OpenRouter.

        Args:
            topic: Research topic
            language: Content language
            max_competitors: Maximum competitors
            include_content_analysis: Include content analysis

        Returns:
            Parsed competitor data

        Raises:
            AgentError: If API call fails
        """
        language_name = self._get_language_name(language)

        system_prompt = (
            f"You are a competitive intelligence analyst. Research competitors in a given industry/niche "
            f"and return results in JSON format.\n\n"
            f"Language: {language_name}\n\n"
            f"Required JSON structure:\n"
            f"{{\n"
            f'  "competitors": [\n'
            f'    {{\n'
            f'      "name": "Company Name",\n'
            f'      "website": "https://example.com",\n'
            f'      "description": "Brief description",\n'
            f'      "social_handles": {{\n'
            f'        "linkedin": "handle",\n'
            f'        "twitter": "handle",\n'
            f'        "facebook": "handle",\n'
            f'        "instagram": "handle"\n'
            f'      }},\n'
            f'      "content_strategy": {{\n'
            f'        "topics": ["topic1", "topic2"],\n'
            f'        "posting_frequency": "frequency",\n'
            f'        "content_types": ["blog", "video"],\n'
            f'        "strengths": ["strength1"],\n'
            f'        "weaknesses": ["weakness1"]\n'
            f'      }}\n'
            f'    }}\n'
            f'  ],\n'
            f'  "content_gaps": ["gap1", "gap2"],\n'
            f'  "trending_topics": ["topic1", "topic2"],\n'
            f'  "recommendation": "Strategic recommendation"\n'
            f"}}\n\n"
            f"IMPORTANT: Return valid JSON only, no additional text."
        )

        content_hint = "Include detailed content strategy analysis." if include_content_analysis else ""

        user_prompt = (
            f"Research topic: {topic}\n"
            f"Find top {max_competitors} competitors in this space.\n"
            f"{content_hint}\n\n"
            f"Return comprehensive competitor analysis in JSON format."
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
        return self._normalize_competitor_data(data)

    def _normalize_competitor_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and validate competitor data.

        Args:
            data: Raw competitor data

        Returns:
            Normalized data with all required fields
        """
        competitors = data.get('competitors', [])

        # Normalize each competitor
        normalized_competitors = []
        for comp in competitors:
            normalized_comp = {
                'name': comp.get('name', 'Unknown'),
                'website': comp.get('website', ''),
                'description': comp.get('description', ''),
                'social_handles': {
                    'linkedin': comp.get('social_handles', {}).get('linkedin', ''),
                    'twitter': comp.get('social_handles', {}).get('twitter', ''),
                    'facebook': comp.get('social_handles', {}).get('facebook', ''),
                    'instagram': comp.get('social_handles', {}).get('instagram', '')
                },
                'content_strategy': {
                    'topics': comp.get('content_strategy', {}).get('topics', []),
                    'posting_frequency': comp.get('content_strategy', {}).get('posting_frequency', 'Unknown'),
                    'content_types': comp.get('content_strategy', {}).get('content_types', []),
                    'strengths': comp.get('content_strategy', {}).get('strengths', []),
                    'weaknesses': comp.get('content_strategy', {}).get('weaknesses', [])
                }
            }
            normalized_competitors.append(normalized_comp)

        return {
            'competitors': normalized_competitors,
            'content_gaps': data.get('content_gaps', []),
            'trending_topics': data.get('trending_topics', []),
            'recommendation': data.get('recommendation', 'No recommendation available')
        }

    def _save_to_cache(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Save competitor research to cache.

        Args:
            topic: Research topic
            data: Competitor data to cache
        """
        if not self.cache_manager:
            return

        # Create slug from topic
        slug = self._create_slug(topic)

        # Save to cache/research/competitors_{slug}.json
        cache_path = Path(self.cache_manager.cache_dir) / "research"
        cache_path.mkdir(parents=True, exist_ok=True)

        file_path = cache_path / f"competitors_{slug}.json"

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved competitor research to cache: {file_path}")

    def _create_slug(self, topic: str) -> str:
        """
        Create URL-safe slug from topic.

        Args:
            topic: Topic string

        Returns:
            Slug string
        """
        # Convert to lowercase
        slug = topic.lower()

        # Replace spaces and special chars with hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', slug)

        # Remove leading/trailing hyphens
        slug = slug.strip('-')

        # Limit length
        slug = slug[:50]

        return slug

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
