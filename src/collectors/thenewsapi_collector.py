"""
TheNewsAPI Collector - Real-Time News Collection

Features:
- Real-time news article collection via TheNewsAPI.com
- 100 free requests/day (300 articles per request)
- Category, language, and date filtering
- Graceful error handling with zero silent failures
- Document model integration
- Deduplication support

API Documentation: https://www.thenewsapi.com/documentation

Usage:
    from src.collectors.thenewsapi_collector import TheNewsAPICollector
    from src.database.sqlite_manager import DatabaseManager
    from src.processors.deduplicator import Deduplicator

    collector = TheNewsAPICollector(
        api_key="your_api_key",
        config=config,
        db_manager=db_manager,
        deduplicator=deduplicator
    )

    documents = await collector.collect(
        query="PropTech",
        categories=["tech", "business"],
        limit=50
    )
"""

import os
import httpx
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse

from src.utils.logger import get_logger
from src.models.document import Document

logger = get_logger(__name__)


class TheNewsAPIError(Exception):
    """TheNewsAPI Collector related errors"""
    pass


class TheNewsAPICollector:
    """
    Real-time news collector using TheNewsAPI.com

    Features:
    - Free tier: 100 requests/day, up to 300 articles per request
    - Category filtering (tech, business, science, etc.)
    - Date range filtering (published_before/after/on)
    - Language support (en, de, fr, es, etc.)
    - Graceful degradation on errors
    - Statistics tracking
    """

    API_BASE_URL = "https://api.thenewsapi.com/v1/news"
    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        config=None,
        db_manager=None,
        deduplicator=None,
        cache_dir: str = "cache/thenewsapi_collector",
        request_timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize TheNewsAPI Collector

        Args:
            api_key: TheNewsAPI API key (loads from env if None)
            config: Market configuration
            db_manager: Database manager instance
            deduplicator: Deduplicator instance
            cache_dir: Directory for caching metadata
            request_timeout: HTTP request timeout in seconds

        Raises:
            TheNewsAPIError: If API key is not provided or found in env
        """
        # Load API key
        self.api_key = api_key or os.getenv("THENEWSAPI_API_KEY")
        if not self.api_key:
            raise TheNewsAPIError(
                "API key required. Provide via api_key parameter or THENEWSAPI_API_KEY env variable."
            )

        self.config = config
        self.db_manager = db_manager
        self.deduplicator = deduplicator
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.request_timeout = request_timeout

        # Statistics
        self._stats = {
            "total_requests": 0,
            "total_documents_collected": 0,
            "total_failures": 0,
            "total_skipped_duplicates": 0
        }

        logger.info(
            "thenewsapi_collector_initialized",
            cache_dir=str(self.cache_dir),
            timeout=request_timeout,
            language=config.language if config else "en"
        )

    async def collect(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        published_after: Optional[str] = None,
        published_before: Optional[str] = None,
        limit: int = 50
    ) -> List[Document]:
        """
        Collect news articles from TheNewsAPI

        Args:
            query: Search query
            categories: List of categories to filter by (tech, business, etc.)
            published_after: Date string (YYYY-MM-DD) for minimum publish date
            published_before: Date string (YYYY-MM-DD) for maximum publish date
            limit: Maximum number of articles (max varies by plan)

        Returns:
            List of Document objects

        Note:
            Returns empty list on errors (graceful degradation)
        """
        self._stats["total_requests"] += 1

        try:
            logger.info(
                "thenewsapi_collection_started",
                query=query,
                categories=categories,
                limit=limit
            )

            # Build query parameters
            params = self._build_query_params(
                query=query,
                categories=categories,
                published_after=published_after,
                published_before=published_before,
                limit=limit
            )

            # Make API request
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.get(
                    f"{self.API_BASE_URL}/all",
                    params=params
                )

                # Check for HTTP errors
                if response.status_code != 200:
                    logger.error(
                        "thenewsapi_http_error",
                        status_code=response.status_code,
                        error=response.text
                    )
                    self._stats["total_failures"] += 1
                    return []

                # Parse JSON response
                try:
                    data = response.json()
                except Exception as e:
                    logger.error("thenewsapi_json_parse_error", error=str(e))
                    self._stats["total_failures"] += 1
                    return []

            # Extract articles
            articles = data.get("data", [])
            meta = data.get("meta", {})

            logger.info(
                "thenewsapi_response_received",
                found=meta.get("found", 0),
                returned=meta.get("returned", 0)
            )

            # Convert articles to Documents
            documents = []
            for article in articles:
                try:
                    doc = self._parse_article_to_document(article)
                    if doc:
                        # Check for duplicates
                        if self.deduplicator and self.deduplicator.is_duplicate(doc):
                            self._stats["total_skipped_duplicates"] += 1
                            continue

                        documents.append(doc)

                except Exception as e:
                    logger.warning(
                        "article_parsing_failed",
                        article_uuid=article.get("uuid", "unknown"),
                        error=str(e)
                    )

            # Update statistics
            self._stats["total_documents_collected"] += len(documents)

            logger.info(
                "thenewsapi_collection_success",
                query=query,
                documents_count=len(documents),
                duplicates_skipped=self._stats["total_skipped_duplicates"]
            )

            return documents

        except Exception as e:
            self._stats["total_failures"] += 1
            logger.error(
                "thenewsapi_collection_failed",
                query=query,
                error=str(e),
                note="Returning empty list (graceful degradation)"
            )
            return []

    def _build_query_params(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        published_after: Optional[str] = None,
        published_before: Optional[str] = None,
        limit: int = 50
    ) -> Dict:
        """
        Build query parameters for API request

        Args:
            query: Search query
            categories: List of categories
            published_after: Minimum publish date
            published_before: Maximum publish date
            limit: Maximum results

        Returns:
            Dictionary of query parameters
        """
        params = {
            "api_token": self.api_key,
            "search": query,
            "limit": limit
        }

        # Add language from config
        if self.config and hasattr(self.config, "language"):
            params["language"] = self.config.language

        # Add category filter
        if categories:
            params["categories"] = ",".join(categories)

        # Add date filters
        if published_after:
            params["published_after"] = published_after
        if published_before:
            params["published_before"] = published_before

        return params

    def _parse_article_to_document(self, article: Dict) -> Optional[Document]:
        """
        Parse TheNewsAPI article to Document model

        Args:
            article: Article dict from API response

        Returns:
            Document object or None if invalid
        """
        # Extract required fields
        url = article.get("url")
        if not url:
            logger.warning("article_missing_url", uuid=article.get("uuid"))
            return None

        title = article.get("title", "Untitled")
        description = article.get("description", "")
        snippet = article.get("snippet", "")
        source_name = article.get("source", "Unknown")
        uuid = article.get("uuid", "")

        # Get canonical URL for deduplication
        canonical_url = url
        if self.deduplicator:
            canonical_url = self.deduplicator.get_canonical_url(url)

        # Parse publication date
        published_at = self._parse_date(article.get("published_at", ""))

        # Generate document ID
        doc_id = f"thenewsapi_{source_name}_{hashlib.md5(url.encode()).hexdigest()[:8]}"

        # Compute content hash
        content_hash = "default_hash"
        if self.deduplicator:
            content_hash = self.deduplicator.compute_content_hash(description or snippet)

        # Extract language (default to config or 'en')
        language = article.get("language", "en")
        if self.config and hasattr(self.config, "language"):
            language = self.config.language

        # Create Document
        document = Document(
            id=doc_id,
            source=f"thenewsapi_{source_name}",
            source_url=url,
            title=title,
            content=description,
            summary=snippet,
            language=language,
            domain=self.config.domain if self.config else "",
            market=self.config.market if self.config else "",
            vertical=self.config.vertical if self.config else "",
            content_hash=content_hash,
            canonical_url=canonical_url,
            published_at=published_at,
            fetched_at=datetime.now(),
            author=None,  # TheNewsAPI doesn't provide author field
            status="new"
        )

        return document

    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse date string from TheNewsAPI format

        Args:
            date_str: Date string (YYYY-MM-DD HH:MM:SS)

        Returns:
            datetime object (defaults to now if parsing fails)
        """
        if not date_str:
            return datetime.now()

        try:
            # TheNewsAPI format: "2025-11-05 10:00:00"
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Try alternative format: "2025-11-05"
                return datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                logger.debug("date_parse_failed", date_str=date_str)
                return datetime.now()

    def get_statistics(self) -> Dict:
        """
        Get collection statistics

        Returns:
            Statistics dictionary
        """
        return self._stats.copy()

    def reset_statistics(self) -> None:
        """Reset statistics to zero"""
        self._stats = {
            "total_requests": 0,
            "total_documents_collected": 0,
            "total_failures": 0,
            "total_skipped_duplicates": 0
        }
        logger.info("statistics_reset")
