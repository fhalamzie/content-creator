"""
Search Backend Base Class

Abstract base class for all search backends with graceful degradation support.

Design Principles:
- All backends must implement search() that NEVER raises exceptions externally
- Internal errors must be caught, logged, and return empty list
- Health checks must be implemented for monitoring
- Each backend specializes in a specific "search horizon"
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from enum import Enum


class SearchHorizon(Enum):
    """Search specialization focus"""
    DEPTH = "depth"      # Academic, authoritative, peer-reviewed sources
    BREADTH = "breadth"  # Wide coverage, recent content, diverse perspectives
    TRENDS = "trends"    # Emerging patterns, predictions, trend analysis


class BackendHealth(Enum):
    """Backend operational status"""
    SUCCESS = "success"      # Fully operational
    DEGRADED = "degraded"    # Partially operational (e.g., low results)
    FAILED = "failed"        # Not operational


class SearchResult(dict):
    """
    Standardized search result format

    Required fields:
    - url: Source URL
    - title: Result title
    - snippet: Short description/excerpt
    - backend: Backend name that produced this result

    Optional fields:
    - content: Full content (if scraped)
    - engine: Specific search engine used (for metasearch backends)
    - score: Relevance score
    - published_date: Publication timestamp
    - domain: Extracted domain name
    - grounding: Whether result is from grounded search
    """

    @classmethod
    def create(
        cls,
        url: str,
        title: str,
        snippet: str,
        backend: str,
        **kwargs
    ) -> "SearchResult":
        """
        Create standardized search result

        Args:
            url: Source URL
            title: Result title
            snippet: Short description
            backend: Backend name
            **kwargs: Optional fields (content, engine, score, etc.)

        Returns:
            SearchResult instance
        """
        result = cls({
            'url': url,
            'title': title,
            'snippet': snippet,
            'backend': backend,
            **kwargs
        })
        return result


class SearchBackend(ABC):
    """
    Abstract base class for all search backends

    All backends must:
    1. Implement search() that handles errors gracefully (returns empty, not raises)
    2. Implement health_check() for monitoring
    3. Define their search horizon (depth/breadth/trends)
    4. Report cost per query

    Graceful Degradation Contract:
    - search() must NEVER raise exceptions to the caller
    - All errors must be caught internally, logged, and return []
    - This allows parallel execution to continue if one backend fails
    """

    def __init__(self, backend_name: str):
        """
        Initialize search backend

        Args:
            backend_name: Unique identifier for this backend
        """
        self.backend_name = backend_name

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> List[SearchResult]:
        """
        Execute search and return standardized results

        IMPORTANT: This method must handle all exceptions internally.
        Never raise exceptions to the caller. Return empty list on failure.

        Args:
            query: Search query (may be contextualized)
            max_results: Maximum results to return
            **kwargs: Backend-specific options

        Returns:
            List of SearchResult dicts (empty list on failure)

        Example:
            try:
                # Execute search
                results = await self._do_search(query)
                return [SearchResult.create(...) for r in results]
            except Exception as e:
                logger.error("search_failed", backend=self.backend_name, error=str(e))
                return []  # GRACEFUL: Don't raise
        """
        pass

    @abstractmethod
    async def health_check(self) -> BackendHealth:
        """
        Check if backend is operational

        Returns:
            BackendHealth status (SUCCESS/DEGRADED/FAILED)

        Example:
            try:
                results = await self.search("test", max_results=1)
                return BackendHealth.SUCCESS if len(results) > 0 else BackendHealth.DEGRADED
            except Exception:
                return BackendHealth.FAILED
        """
        pass

    @property
    @abstractmethod
    def horizon(self) -> SearchHorizon:
        """
        Search specialization

        Returns:
            SearchHorizon enum (DEPTH/BREADTH/TRENDS)
        """
        pass

    @property
    @abstractmethod
    def cost_per_query(self) -> float:
        """
        Cost in USD per query (0.0 for free backends)

        Returns:
            Cost as float (e.g., 0.02 for Tavily, 0.0 for SearXNG)
        """
        pass

    @property
    @abstractmethod
    def supports_citations(self) -> bool:
        """
        Whether this backend provides citation-quality sources

        Returns:
            True if results include proper citations/URLs
        """
        pass

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"{self.__class__.__name__}("
            f"name={self.backend_name}, "
            f"horizon={self.horizon.value}, "
            f"cost=${self.cost_per_query}/query)"
        )
