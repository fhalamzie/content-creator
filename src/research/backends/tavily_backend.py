"""
Tavily Backend - Academic/Authoritative Sources (DEPTH Horizon)

Uses Tavily Search API directly for high-quality, citation-worthy sources.

Features:
- Academic papers, industry reports, authoritative sources
- Real citations with URLs
- Cost: ~$0.02 per query
- Focus: Depth and quality over breadth
"""

import os
import traceback
from typing import List, Optional

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

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


class TavilyBackend(SearchBackend):
    """
    Tavily Search API backend for DEPTH horizon

    Specialization: Academic, authoritative, citation-quality sources
    Cost: ~$0.02 per query
    Quality: High (peer-reviewed, industry reports, established sources)
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Tavily backend

        Args:
            api_key: Tavily API key (auto-loads from env if not provided)

        Raises:
            BackendUnavailableError: If tavily-python not installed
            AuthenticationError: If API key missing
        """
        super().__init__(backend_name="tavily")

        # Check tavily-python installed
        if TavilyClient is None:
            raise BackendUnavailableError(
                "tavily-python not installed. Install with: pip install tavily-python",
                backend_name=self.backend_name
            )

        # Load API key
        self.api_key = api_key or self._load_api_key()
        if not self.api_key:
            raise AuthenticationError(
                "TAVILY_API_KEY not found in environment",
                backend_name=self.backend_name
            )

        # Initialize client
        try:
            self.client = TavilyClient(api_key=self.api_key)
            logger.info("tavily_backend_initialized", api_key_set=bool(self.api_key))
        except Exception as e:
            logger.error("tavily_init_failed", error=str(e), error_type=type(e).__name__)
            raise BackendUnavailableError(
                f"Failed to initialize Tavily client: {e}",
                backend_name=self.backend_name
            )

    def _load_api_key(self) -> Optional[str]:
        """Load Tavily API key from environment"""
        # Check environment variable
        api_key = os.getenv("TAVILY_API_KEY")
        if api_key:
            return api_key

        # Check /home/envs/tavily.env
        env_file = "/home/envs/tavily.env"
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'TAVILY_API_KEY':
                                logger.info("tavily_key_loaded_from_file", file=env_file)
                                return value.strip()
            except Exception as e:
                logger.warning("failed_to_load_tavily_key", error=str(e))

        return None

    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search with Tavily API for academic/authoritative sources

        GRACEFUL DEGRADATION: Returns empty list on any error, never raises.

        Args:
            query: Search query (should emphasize academic/authoritative focus)
            max_results: Maximum results (default 10)
            **kwargs: Additional options (search_depth, include_domains, etc.)

        Returns:
            List of SearchResult dicts (empty on failure)
        """
        try:
            logger.info(
                "tavily_search_start",
                query=query[:100],
                max_results=max_results
            )

            # Execute Tavily search
            # search_depth="advanced" for better quality (costs more)
            search_depth = kwargs.get('search_depth', 'basic')
            include_domains = kwargs.get('include_domains', [])
            exclude_domains = kwargs.get('exclude_domains', [])

            response = self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_domains=include_domains if include_domains else None,
                exclude_domains=exclude_domains if exclude_domains else None
            )

            # Transform to standard format
            results = []
            for item in response.get('results', []):
                # Use raw_content as primary content source (falls back to snippet)
                content = item.get('raw_content') or item.get('content', '')

                result = SearchResult.create(
                    url=item.get('url', ''),
                    title=item.get('title', ''),
                    snippet=item.get('content', ''),
                    content=content,  # Full content for MinHash/synthesis
                    backend=self.backend_name,
                    score=item.get('score', 0.0),
                    published_date=item.get('published_date')
                )
                results.append(result)

            logger.info(
                "tavily_search_success",
                query=query[:100],
                results_count=len(results),
                search_depth=search_depth
            )

            return results

        except Exception as e:
            # GRACEFUL DEGRADATION: Log error, return empty, don't raise
            logger.error(
                "tavily_search_failed",
                query=query[:100],
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc()
            )
            return []

    async def health_check(self) -> BackendHealth:
        """
        Check Tavily API availability

        Returns:
            BackendHealth status
        """
        try:
            # Run minimal test query
            results = await self.search("test health check", max_results=1)

            if len(results) > 0:
                logger.debug("tavily_health_check_success")
                return BackendHealth.SUCCESS
            else:
                logger.warning("tavily_health_check_degraded", reason="no_results")
                return BackendHealth.DEGRADED

        except Exception as e:
            logger.error("tavily_health_check_failed", error=str(e))
            return BackendHealth.FAILED

    @property
    def horizon(self) -> SearchHorizon:
        """Tavily specializes in DEPTH (academic/authoritative)"""
        return SearchHorizon.DEPTH

    @property
    def cost_per_query(self) -> float:
        """Tavily costs approximately $0.02 per query"""
        return 0.02

    @property
    def supports_citations(self) -> bool:
        """Tavily provides high-quality citations"""
        return True
