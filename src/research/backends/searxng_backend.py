"""
SearXNG Backend - Broad Coverage (BREADTH Horizon)

Uses SearXNG metasearch engine (245 search engines) for wide source diversity.

Features:
- 245 search engines (Google, Bing, DuckDuckGo, academic, news, etc.)
- Public instances (FREE) or self-hosted
- Automatic failover between engines
- Cost: $0 (public instances)
- Focus: Breadth, recency, diverse perspectives
"""

import traceback
from typing import List, Optional
from urllib.parse import urlparse

try:
    from pyserxng import SearXNGClient, LocalSearXNGClient, SearchConfig, SearchCategory
except ImportError:
    SearXNGClient = None
    LocalSearXNGClient = None
    SearchConfig = None
    SearchCategory = None

from src.research.backends.base import (
    SearchBackend,
    SearchHorizon,
    BackendHealth,
    SearchResult
)
from src.research.backends.exceptions import BackendUnavailableError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SearXNGBackend(SearchBackend):
    """
    SearXNG metasearch backend for BREADTH horizon

    Specialization: Wide coverage, recent content, diverse perspectives
    Cost: $0 (public instances) or $10-20/month (self-hosted)
    Coverage: 245 search engines with automatic failover
    """

    def __init__(self, instance_url: Optional[str] = None):
        """
        Initialize SearXNG backend

        Args:
            instance_url: Custom SearXNG instance URL, or None for public instances

        Raises:
            BackendUnavailableError: If pyserxng not installed
        """
        super().__init__(backend_name="searxng")

        # Check pyserxng installed
        if SearXNGClient is None:
            raise BackendUnavailableError(
                "pyserxng not installed. Install with: pip install pyserxng",
                backend_name=self.backend_name
            )

        self.instance_url = instance_url
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize pyserxng client with error handling"""
        try:
            if self.instance_url:
                # Use custom instance
                self.client = LocalSearXNGClient(self.instance_url)
                logger.info(
                    "searxng_initialized",
                    type="local",
                    url=self.instance_url
                )
            else:
                # Use public instances with auto-discovery
                self.client = SearXNGClient()
                logger.info(
                    "searxng_initialized",
                    type="public_instances",
                    note="Auto-discovering public SearXNG instances"
                )

        except Exception as e:
            logger.error(
                "searxng_init_failed",
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc()
            )
            raise BackendUnavailableError(
                f"Failed to initialize SearXNG: {e}",
                backend_name=self.backend_name
            )

    async def search(
        self,
        query: str,
        max_results: int = 30,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search with SearXNG across 245 engines

        GRACEFUL DEGRADATION: Returns empty list on any error, never raises.

        Args:
            query: Search query (should emphasize recency and diversity)
            max_results: Maximum results (default 30 for breadth)
            **kwargs: Additional options (time_range, categories, etc.)

        Returns:
            List of SearchResult dicts (empty on failure)
        """
        try:
            logger.info(
                "searxng_search_start",
                query=query[:100],
                max_results=max_results,
                instance_type="local" if self.instance_url else "public"
            )

            # Configure search
            # Prioritize recent content (last year) for breadth/recency
            time_range = kwargs.get('time_range', 'year')
            categories = kwargs.get('categories', [SearchCategory.GENERAL])

            config = SearchConfig(
                categories=categories,
                time_range=time_range,
                safesearch=0  # No filtering for research
            )

            # Execute search
            search_results = self.client.search(
                query=query,
                config=config,
                max_results=max_results
            )

            # Transform to standard format
            results = []
            engines_used = set()

            for item in search_results:
                # Extract engine name if available
                engine = item.get('engine', 'unknown')
                engines_used.add(engine)

                # Parse domain from URL
                try:
                    domain = urlparse(item.get('url', '')).netloc
                except Exception:
                    domain = 'unknown'

                result = SearchResult.create(
                    url=item.get('url', ''),
                    title=item.get('title', ''),
                    snippet=item.get('content', ''),
                    backend=self.backend_name,
                    engine=engine,
                    domain=domain,
                    score=item.get('score', 0.0),
                    published_date=item.get('publishedDate')
                )
                results.append(result)

            logger.info(
                "searxng_search_success",
                query=query[:100],
                results_count=len(results),
                engines_used=len(engines_used),
                top_engines=list(engines_used)[:5] if engines_used else []
            )

            return results

        except Exception as e:
            # GRACEFUL DEGRADATION: Log error, return empty, don't raise
            logger.error(
                "searxng_search_failed",
                query=query[:100],
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
                note="This may be due to public instance availability - consider self-hosting"
            )
            return []

    async def health_check(self) -> BackendHealth:
        """
        Check SearXNG availability

        Returns:
            BackendHealth status
        """
        try:
            # Run minimal test query
            results = await self.search("test health check", max_results=1)

            if len(results) > 0:
                logger.debug("searxng_health_check_success")
                return BackendHealth.SUCCESS
            else:
                logger.warning(
                    "searxng_health_check_degraded",
                    reason="no_results",
                    note="Public instances may be temporarily unavailable"
                )
                return BackendHealth.DEGRADED

        except Exception as e:
            logger.error(
                "searxng_health_check_failed",
                error=str(e),
                note="Consider checking instance availability or self-hosting"
            )
            return BackendHealth.FAILED

    @property
    def horizon(self) -> SearchHorizon:
        """SearXNG specializes in BREADTH (wide coverage, diverse sources)"""
        return SearchHorizon.BREADTH

    @property
    def cost_per_query(self) -> float:
        """SearXNG is FREE (public instances or self-hosted)"""
        return 0.0

    @property
    def supports_citations(self) -> bool:
        """SearXNG provides URLs for citations"""
        return True
