"""
Search Backends Package

Multi-backend search system with graceful degradation.

Backends:
- TavilyBackend: Academic/authoritative sources (DEPTH horizon)
- SearXNGBackend: 245 search engines, broad coverage (BREADTH horizon)
- GeminiAPIBackend: Trend analysis with google_search grounding (TRENDS horizon)

Usage:
    from src.research.backends import (
        SearchBackend,
        SearchHorizon,
        BackendHealth,
        SearchResult,
        TavilyBackend,
        SearXNGBackend,
        GeminiAPIBackend
    )

    # Initialize backends
    tavily = TavilyBackend()
    searxng = SearXNGBackend()
    gemini = GeminiAPIBackend()

    # Execute searches in parallel
    results = await asyncio.gather(
        tavily.search("AI safety research"),
        searxng.search("AI safety research"),
        gemini.search("AI safety research"),
        return_exceptions=True
    )
"""

from src.research.backends.base import (
    SearchBackend,
    SearchHorizon,
    BackendHealth,
    SearchResult
)

from src.research.backends.exceptions import (
    BackendError,
    RateLimitError,
    BackendUnavailableError,
    InsufficientResultsError,
    AuthenticationError,
    TimeoutError
)

# Import backends
from src.research.backends.tavily_backend import TavilyBackend
from src.research.backends.searxng_backend import SearXNGBackend
from src.research.backends.gemini_api_backend import GeminiAPIBackend

__all__ = [
    # Base classes
    'SearchBackend',
    'SearchHorizon',
    'BackendHealth',
    'SearchResult',

    # Exceptions
    'BackendError',
    'RateLimitError',
    'BackendUnavailableError',
    'InsufficientResultsError',
    'AuthenticationError',
    'TimeoutError',

    # Backends
    'TavilyBackend',
    'SearXNGBackend',
    'GeminiAPIBackend',
]
