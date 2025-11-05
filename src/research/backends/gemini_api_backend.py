"""
Gemini API Backend - Trend Analysis (TRENDS Horizon)

Uses Gemini API with google_search grounding for trend analysis and emerging patterns.

Features:
- Google Search grounding (real-time web data)
- FREE (1,500 grounded queries/day)
- Trend analysis, expert opinions, emerging developments
- Focus: Trends, predictions, market shifts
"""

import traceback
from typing import List, Optional
import os

from src.research.backends.base import (
    SearchBackend,
    SearchHorizon,
    BackendHealth,
    SearchResult
)
from src.research.backends.exceptions import (
    BackendUnavailableError,
    AuthenticationError
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Lazy import to avoid dependency issues
GeminiAgent = None


class GeminiAPIBackend(SearchBackend):
    """
    Gemini API backend for TRENDS horizon

    Specialization: Trend analysis, expert opinions, emerging developments
    Cost: $0 (FREE tier: 1,500 grounded queries/day)
    Quality: Good for trends, predictions, recent developments
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        enable_grounding: bool = True
    ):
        """
        Initialize Gemini API backend

        Args:
            api_key: Gemini API key (auto-loads from env if not provided)
            model: Model to use (default: gemini-2.5-flash)
            enable_grounding: Enable google_search grounding (default: True)

        Raises:
            BackendUnavailableError: If GeminiAgent not available
            AuthenticationError: If API key missing
        """
        super().__init__(backend_name="gemini")

        # Lazy import GeminiAgent
        global GeminiAgent
        if GeminiAgent is None:
            try:
                from src.agents.gemini_agent import GeminiAgent as _GeminiAgent
                GeminiAgent = _GeminiAgent
            except ImportError as e:
                raise BackendUnavailableError(
                    f"GeminiAgent not available: {e}",
                    backend_name=self.backend_name
                )

        # Load API key
        self.api_key = api_key or self._load_api_key()
        if not self.api_key:
            raise AuthenticationError(
                "GEMINI_API_KEY not found in environment",
                backend_name=self.backend_name
            )

        # Initialize GeminiAgent
        try:
            self.agent = GeminiAgent(
                model=model,
                api_key=self.api_key,
                enable_grounding=enable_grounding
            )
            logger.info(
                "gemini_backend_initialized",
                model=model,
                grounding=enable_grounding
            )
        except Exception as e:
            logger.error(
                "gemini_init_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise BackendUnavailableError(
                f"Failed to initialize GeminiAgent: {e}",
                backend_name=self.backend_name
            )

    def _load_api_key(self) -> Optional[str]:
        """Load Gemini API key from environment"""
        # Check environment variable
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            return api_key

        # Check /home/envs/gemini.env
        env_file = "/home/envs/gemini.env"
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'GEMINI_API_KEY':
                                logger.info("gemini_key_loaded_from_file", file=env_file)
                                return value.strip()
            except Exception as e:
                logger.warning("failed_to_load_gemini_key", error=str(e))

        return None

    async def search(
        self,
        query: str,
        max_results: int = 12,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search with Gemini API grounding for trend analysis

        GRACEFUL DEGRADATION: Returns empty list on any error, never raises.

        Args:
            query: Search query (should emphasize trends/emerging patterns)
            max_results: Maximum results (default 12)
            **kwargs: Additional options

        Returns:
            List of SearchResult dicts (empty on failure)
        """
        try:
            logger.info(
                "gemini_search_start",
                query=query[:100],
                max_results=max_results
            )

            # Build trend-focused prompt
            prompt = f"""Research current trends and emerging developments about:

{query}

Focus on:
- Trending discussions and expert opinions
- Recent statistics and data points
- Market shifts and adoption patterns
- Expert predictions and analysis
- Emerging technologies/approaches

Provide {max_results} diverse sources with clear relevance to the topic.
For each source, include:
- URL
- Title
- Brief explanation of relevance to the trend/development

Format your response as a JSON array of sources."""

            # Execute with GeminiAgent
            # Note: GeminiAgent.generate() handles grounding automatically
            response = self.agent.generate(
                prompt=prompt,
                response_schema={
                    "type": "object",
                    "properties": {
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "url": {"type": "string"},
                                    "title": {"type": "string"},
                                    "relevance": {"type": "string"}
                                },
                                "required": ["url", "title"]
                            }
                        }
                    },
                    "required": ["sources"]
                }
            )

            # Extract sources from response
            sources_data = response.get('sources', [])

            # Also extract from grounding metadata if available
            grounding_sources = []
            if hasattr(response, 'grounding_metadata'):
                # Extract additional sources from grounding metadata
                # (Implementation depends on Gemini API response structure)
                pass

            # Transform to standard format
            results = []
            for item in sources_data:
                result = SearchResult.create(
                    url=item.get('url', ''),
                    title=item.get('title', ''),
                    snippet=item.get('relevance', ''),
                    backend=self.backend_name,
                    grounding=True  # Mark as grounded search result
                )
                results.append(result)

            # Limit to max_results
            results = results[:max_results]

            logger.info(
                "gemini_search_success",
                query=query[:100],
                results_count=len(results)
            )

            return results

        except Exception as e:
            # GRACEFUL DEGRADATION: Log error, return empty, don't raise
            logger.error(
                "gemini_search_failed",
                query=query[:100],
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
                note="Check quota (1,500/day free tier) and API key"
            )
            return []

    async def health_check(self) -> BackendHealth:
        """
        Check Gemini API availability and quota

        Returns:
            BackendHealth status
        """
        try:
            # Run minimal test query
            results = await self.search("test health check trends", max_results=1)

            if len(results) > 0:
                logger.debug("gemini_health_check_success")
                return BackendHealth.SUCCESS
            else:
                logger.warning(
                    "gemini_health_check_degraded",
                    reason="no_results",
                    note="May have hit quota (1,500/day) or API issue"
                )
                return BackendHealth.DEGRADED

        except Exception as e:
            logger.error(
                "gemini_health_check_failed",
                error=str(e),
                note="Check API key and quota limits"
            )
            return BackendHealth.FAILED

    @property
    def horizon(self) -> SearchHorizon:
        """Gemini specializes in TRENDS (emerging patterns, predictions)"""
        return SearchHorizon.TRENDS

    @property
    def cost_per_query(self) -> float:
        """Gemini is FREE (1,500 grounded queries/day)"""
        return 0.0

    @property
    def supports_citations(self) -> bool:
        """Gemini provides grounded sources with URLs"""
        return True
