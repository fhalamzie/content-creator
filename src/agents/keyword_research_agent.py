"""
KeywordResearchAgent - SEO Keyword Research with Gemini CLI

Performs keyword research using Gemini CLI (FREE Google Search) with fallback to API.

Design Principles:
- Gemini CLI first (FREE), API fallback (also FREE)
- Subprocess management with timeout
- JSON response parsing with validation
- Comprehensive error handling
- Structured keyword data output
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


class KeywordResearchError(Exception):
    """Base exception for keyword research errors"""
    pass


class KeywordResearchAgent(BaseAgent):
    """
    Keyword research agent using Gemini CLI with API fallback.

    Features:
    - Gemini CLI integration (FREE Google Search)
    - Automatic fallback to Gemini API via OpenRouter
    - JSON response parsing and validation
    - Subprocess error handling
    - Structured keyword data output
    - Keyword difficulty calculation
    - Cache integration

    Usage:
        agent = KeywordResearchAgent(api_key="sk-xxx")
        result = agent.research_keywords(
            topic="content marketing",
            language="de",
            target_audience="German small businesses",
            keyword_count=10
        )
        print(result['primary_keyword'])
        print(result['secondary_keywords'])
    """

    def __init__(
        self,
        api_key: str,
        use_cli: bool = True,
        cli_timeout: int = 60,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize KeywordResearchAgent.

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
            f"KeywordResearchAgent initialized: "
            f"use_cli={use_cli}, timeout={cli_timeout}s, cache={cache_dir is not None}"
        )

    def research_keywords(
        self,
        topic: str,
        language: str = "en",
        target_audience: Optional[str] = None,
        keyword_count: int = 10,
        save_to_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Perform keyword research on topic.

        Args:
            topic: Content topic
            language: Content language (ISO 639-1 code, default: en)
            target_audience: Target audience description (optional)
            keyword_count: Number of keywords to return (default: 10)
            save_to_cache: Save results to cache (default: False)

        Returns:
            Dict with:
                - primary_keyword: Best keyword to target
                - secondary_keywords: Supporting keywords
                - long_tail_keywords: Specific long-tail phrases
                - related_questions: Related search questions
                - search_trends: Trending keywords data
                - recommendation: Strategic recommendation

        Raises:
            KeywordResearchError: If research fails
        """
        # Validate input
        if not topic or not topic.strip():
            raise KeywordResearchError("Topic is required")

        topic = topic.strip()

        logger.info(
            f"Starting keyword research: topic='{topic}', "
            f"language={language}, count={keyword_count}"
        )

        # Try Gemini CLI first (if enabled)
        if self.use_cli:
            try:
                result = self._research_with_cli(
                    topic, language, target_audience, keyword_count
                )
                logger.info("Keyword research completed using Gemini CLI")

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
                topic, language, target_audience, keyword_count
            )
            logger.info("Keyword research completed using API fallback")

            # Save to cache if requested
            if save_to_cache and self.cache_manager:
                self._save_to_cache(topic, result)

            return result
        except Exception as e:
            logger.error(f"Keyword research failed: {e}")
            raise KeywordResearchError(
                f"Keyword research failed: {e}"
            ) from e

    def _research_with_cli(
        self,
        topic: str,
        language: str,
        target_audience: Optional[str],
        keyword_count: int
    ) -> Dict[str, Any]:
        """
        Perform keyword research using Gemini CLI.

        Args:
            topic: Content topic
            language: Content language
            target_audience: Target audience
            keyword_count: Number of keywords

        Returns:
            Parsed keyword data

        Raises:
            Exception: If CLI fails or returns invalid data
        """
        # Build Gemini CLI command with specific instructions
        language_hint = f" in {language}" if language != "en" else ""
        audience_hint = f" for {target_audience}" if target_audience else ""

        search_query = (
            f"Perform SEO keyword research for '{topic}'{language_hint}{audience_hint}. "
            f"Find {keyword_count} keywords including primary keyword, secondary keywords, "
            f"long-tail keywords (3-5 words), related questions, and search trends. "
            f"Include search volume estimates, competition level, keyword difficulty (0-100), "
            f"and search intent. Return JSON format."
        )

        command = [
            "gemini",
            "--output-format", "json"
        ]

        logger.info("Running Gemini CLI for keyword research")

        # Run subprocess with timeout
        # IMPORTANT: Pass prompt via stdin, not as positional arg (prevents hanging)
        try:
            result = subprocess.run(
                command,
                input=search_query,  # Pass query via stdin instead of positional arg
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
        return self._normalize_keyword_data(data)

    def _research_with_api(
        self,
        topic: str,
        language: str,
        target_audience: Optional[str],
        keyword_count: int
    ) -> Dict[str, Any]:
        """
        Perform keyword research using Gemini API via OpenRouter.

        Args:
            topic: Content topic
            language: Content language
            target_audience: Target audience
            keyword_count: Number of keywords

        Returns:
            Parsed keyword data

        Raises:
            AgentError: If API call fails
        """
        language_name = self._get_language_name(language)
        audience_hint = f"\nTarget Audience: {target_audience}" if target_audience else ""

        system_prompt = (
            f"You are an SEO keyword research specialist. Research keywords for a given topic "
            f"and return results in JSON format.\n\n"
            f"Language: {language_name}{audience_hint}\n\n"
            f"Required JSON structure:\n"
            f"{{\n"
            f'  "primary_keyword": {{\n'
            f'    "keyword": "main keyword phrase",\n'
            f'    "search_volume": "1K-10K",\n'
            f'    "competition": "Low/Medium/High",\n'
            f'    "difficulty": 0-100,\n'
            f'    "intent": "Informational/Commercial/Navigational"\n'
            f'  }},\n'
            f'  "secondary_keywords": [\n'
            f'    {{\n'
            f'      "keyword": "supporting keyword",\n'
            f'      "search_volume": "100-1K",\n'
            f'      "competition": "Low",\n'
            f'      "difficulty": 0-100,\n'
            f'      "relevance": 0.0-1.0\n'
            f'    }}\n'
            f'  ],\n'
            f'  "long_tail_keywords": [\n'
            f'    {{\n'
            f'      "keyword": "specific long phrase",\n'
            f'      "search_volume": "10-100",\n'
            f'      "competition": "Low",\n'
            f'      "difficulty": 0-100\n'
            f'    }}\n'
            f'  ],\n'
            f'  "related_questions": ["question1", "question2"],\n'
            f'  "search_trends": {{\n'
            f'    "trending_up": ["keyword1"],\n'
            f'    "trending_down": ["keyword2"],\n'
            f'    "seasonal": true/false\n'
            f'  }},\n'
            f'  "recommendation": "Strategic recommendation"\n'
            f"}}\n\n"
            f"IMPORTANT: Return valid JSON only, no additional text."
        )

        user_prompt = (
            f"Research topic: {topic}\n"
            f"Find {keyword_count} keywords for this topic.\n\n"
            f"Return comprehensive keyword research in JSON format."
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
        return self._normalize_keyword_data(data)

    def _normalize_keyword_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and validate keyword data.

        Args:
            data: Raw keyword data

        Returns:
            Normalized data with all required fields
        """
        # Normalize primary keyword
        primary = data.get('primary_keyword', {})
        normalized_primary = {
            'keyword': primary.get('keyword', ''),
            'search_volume': primary.get('search_volume', 'Unknown'),
            'competition': primary.get('competition', 'Medium'),
            'difficulty': primary.get('difficulty', 50),
            'intent': primary.get('intent', 'Informational')
        }

        # Normalize secondary keywords
        secondary = data.get('secondary_keywords', [])
        normalized_secondary = []
        for kw in secondary:
            normalized_kw = {
                'keyword': kw.get('keyword', ''),
                'search_volume': kw.get('search_volume', 'Unknown'),
                'competition': kw.get('competition', 'Medium'),
                'difficulty': kw.get('difficulty', 50),
                'relevance': kw.get('relevance', 0.5)
            }
            normalized_secondary.append(normalized_kw)

        # Normalize long-tail keywords
        long_tail = data.get('long_tail_keywords', [])
        normalized_long_tail = []
        for kw in long_tail:
            normalized_kw = {
                'keyword': kw.get('keyword', ''),
                'search_volume': kw.get('search_volume', 'Unknown'),
                'competition': kw.get('competition', 'Low'),
                'difficulty': kw.get('difficulty', 30)
            }
            normalized_long_tail.append(normalized_kw)

        # Normalize search trends
        trends = data.get('search_trends', {})
        normalized_trends = {
            'trending_up': trends.get('trending_up', []),
            'trending_down': trends.get('trending_down', []),
            'seasonal': trends.get('seasonal', False)
        }

        return {
            'primary_keyword': normalized_primary,
            'secondary_keywords': normalized_secondary,
            'long_tail_keywords': normalized_long_tail,
            'related_questions': data.get('related_questions', []),
            'search_trends': normalized_trends,
            'recommendation': data.get('recommendation', 'No recommendation available')
        }

    def _calculate_keyword_difficulty(
        self,
        search_volume: str,
        competition: str
    ) -> int:
        """
        Calculate keyword difficulty score based on volume and competition.

        Args:
            search_volume: Search volume range (e.g., "1K-10K")
            competition: Competition level (Low/Medium/High)

        Returns:
            Difficulty score (0-100)
        """
        # Parse volume
        volume_score = 0
        if "100K+" in search_volume or "1M+" in search_volume:
            volume_score = 40
        elif "10K-100K" in search_volume:
            volume_score = 30
        elif "1K-10K" in search_volume:
            volume_score = 20
        elif "100-1K" in search_volume:
            volume_score = 10
        else:
            volume_score = 5

        # Parse competition
        competition_score = 0
        if competition.lower() == "high":
            competition_score = 50
        elif competition.lower() == "medium":
            competition_score = 30
        else:  # low
            competition_score = 10

        # Combined difficulty
        difficulty = volume_score + competition_score

        return min(difficulty, 100)

    def _rank_keywords_by_relevance(
        self,
        keywords: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sort keywords by relevance score (descending).

        Args:
            keywords: List of keyword dicts with 'relevance' field

        Returns:
            Sorted list of keywords
        """
        return sorted(
            keywords,
            key=lambda k: k.get('relevance', 0),
            reverse=True
        )

    def _save_to_cache(self, topic: str, data: Dict[str, Any]) -> None:
        """
        Save keyword research to cache.

        Args:
            topic: Research topic
            data: Keyword data to cache
        """
        if not self.cache_manager:
            return

        # Create slug from topic
        slug = self._create_slug(topic)

        # Save to cache/research/keywords_{slug}.json
        cache_path = Path(self.cache_manager.cache_dir) / "research"
        cache_path.mkdir(parents=True, exist_ok=True)

        file_path = cache_path / f"keywords_{slug}.json"

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved keyword research to cache: {file_path}")

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
