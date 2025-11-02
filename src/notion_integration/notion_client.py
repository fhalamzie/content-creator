"""
Notion Client Wrapper

Wraps notion-client SDK with automatic rate limiting and error handling.

Design Principles:
- Automatic rate limiting (2.5 req/sec default)
- Comprehensive error handling
- Retry logic for transient errors
- Statistics tracking
- Simple, facade-like interface
"""

import time
import logging
from typing import Dict, List, Any, Optional
from notion_client import Client, APIResponseError
from src.notion_integration.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class NotionError(Exception):
    """Base exception for Notion client errors"""
    pass


class NotionClient:
    """
    Notion API client with rate limiting and error handling.

    Usage:
        client = NotionClient(token="secret_token")

        # Query database
        results = client.query_database("db-id")

        # Create page
        page = client.create_page(
            parent_database_id="db-id",
            properties={"Title": {...}}
        )

        # Update page
        client.update_page(
            page_id="page-id",
            properties={"Status": {"select": {"name": "Published"}}}
        )
    """

    def __init__(self, token: str, rate_limit: float = 2.5, database_ids_path: str = "cache/database_ids.json"):
        """
        Initialize Notion client.

        Args:
            token: Notion integration token
            rate_limit: Requests per second (default: 2.5)
            database_ids_path: Path to database IDs JSON file

        Raises:
            ValueError: If token is empty or None
        """
        if not token:
            raise ValueError("Token cannot be empty")

        self._client = Client(auth=token)
        self.rate_limiter = RateLimiter(rate=rate_limit)
        self._total_api_calls = 0

        # Load database IDs from cache
        self.database_ids = self._load_database_ids(database_ids_path)

        logger.info(f"NotionClient initialized with rate_limit={rate_limit}")

    def _load_database_ids(self, path: str) -> Dict[str, str]:
        """Load database IDs from cache file."""
        import json
        from pathlib import Path

        cache_path = Path(path)
        if not cache_path.exists():
            logger.warning(f"Database IDs file not found: {path}, returning empty dict")
            return {}

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
                return data.get('databases', {})
        except Exception as e:
            logger.error(f"Failed to load database IDs from {path}: {e}")
            return {}

    # ==================== Database Operations ====================

    def query_database(
        self,
        database_id: str,
        filter: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, str]]] = None,
        retry: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Query a Notion database.

        Args:
            database_id: Database ID
            filter: Filter object (optional)
            sorts: Sort objects (optional)
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts

        Returns:
            Query results with 'results' and 'has_more' keys

        Raises:
            NotionError: On API errors
        """
        kwargs = {"database_id": database_id}
        if filter:
            kwargs["filter"] = filter
        if sorts:
            kwargs["sorts"] = sorts

        return self._call_with_rate_limit(
            self._client.databases.query,
            retry=retry,
            max_retries=max_retries,
            **kwargs
        )

    def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: Dict[str, Any],
        retry: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Create a new database.

        Args:
            parent_page_id: Parent page ID
            title: Database title
            properties: Database properties schema
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts

        Returns:
            Created database object

        Raises:
            NotionError: On API errors
        """
        return self._call_with_rate_limit(
            self._client.databases.create,
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties=properties,
            retry=retry,
            max_retries=max_retries
        )

    # ==================== Page Operations ====================

    def create_page(
        self,
        parent_database_id: str,
        properties: Dict[str, Any],
        children: Optional[List[Dict[str, Any]]] = None,
        retry: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Create a new page in a database.

        Args:
            parent_database_id: Parent database ID
            properties: Page properties
            children: Page content blocks (optional)
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts

        Returns:
            Created page object

        Raises:
            NotionError: On API errors
        """
        kwargs = {
            "parent": {"database_id": parent_database_id},
            "properties": properties
        }
        if children:
            kwargs["children"] = children

        return self._call_with_rate_limit(
            self._client.pages.create,
            retry=retry,
            max_retries=max_retries,
            **kwargs
        )

    def update_page(
        self,
        page_id: str,
        properties: Dict[str, Any],
        retry: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Update page properties.

        Args:
            page_id: Page ID
            properties: Properties to update
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts

        Returns:
            Updated page object

        Raises:
            NotionError: On API errors
        """
        return self._call_with_rate_limit(
            self._client.pages.update,
            page_id=page_id,
            properties=properties,
            retry=retry,
            max_retries=max_retries
        )

    def retrieve_page(
        self,
        page_id: str,
        retry: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Retrieve a page by ID.

        Args:
            page_id: Page ID
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts

        Returns:
            Page object

        Raises:
            NotionError: On API errors
        """
        return self._call_with_rate_limit(
            self._client.pages.retrieve,
            page_id=page_id,
            retry=retry,
            max_retries=max_retries
        )

    def archive_page(
        self,
        page_id: str,
        retry: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Archive (soft delete) a page.

        Args:
            page_id: Page ID
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts

        Returns:
            Updated page object with archived=True

        Raises:
            NotionError: On API errors
        """
        return self._call_with_rate_limit(
            self._client.pages.update,
            page_id=page_id,
            archived=True,
            retry=retry,
            max_retries=max_retries
        )

    # ==================== Block Operations ====================

    def append_blocks(
        self,
        block_id: str,
        children: List[Dict[str, Any]],
        retry: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Append blocks to a page or block.

        Args:
            block_id: Parent block/page ID
            children: Block objects to append
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts

        Returns:
            Response with appended blocks

        Raises:
            NotionError: On API errors
        """
        return self._call_with_rate_limit(
            self._client.blocks.children.append,
            block_id=block_id,
            children=children,
            retry=retry,
            max_retries=max_retries
        )

    def retrieve_block_children(
        self,
        block_id: str,
        retry: bool = False,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Retrieve child blocks of a block/page.

        Args:
            block_id: Parent block/page ID
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts

        Returns:
            Response with child blocks

        Raises:
            NotionError: On API errors
        """
        return self._call_with_rate_limit(
            self._client.blocks.children.list,
            block_id=block_id,
            retry=retry,
            max_retries=max_retries
        )

    # ==================== Statistics ====================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get client statistics.

        Returns:
            Dict with keys:
                - total_api_calls: Total API calls made
                - rate_limiter: Rate limiter stats
        """
        return {
            "total_api_calls": self._total_api_calls,
            "rate_limiter": self.rate_limiter.get_stats()
        }

    def reset_stats(self) -> None:
        """Reset statistics counters"""
        self._total_api_calls = 0
        self.rate_limiter.reset()
        logger.info("NotionClient statistics reset")

    # ==================== Internal Methods ====================

    def _call_with_rate_limit(
        self,
        func,
        retry: bool = False,
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """
        Execute API call with rate limiting and error handling.

        Args:
            func: API function to call
            retry: Enable retry on transient errors
            max_retries: Maximum retry attempts
            **kwargs: Arguments to pass to function

        Returns:
            API response

        Raises:
            NotionError: On API errors (after retries if enabled)
        """
        attempts = 0
        last_error = None

        while attempts <= (max_retries if retry else 0):
            try:
                # Acquire rate limit
                with self.rate_limiter:
                    self._total_api_calls += 1
                    result = func(**kwargs)
                    func_name = getattr(func, '__name__', 'unknown')
                    logger.debug(f"API call successful: {func_name}")
                    return result

            except APIResponseError as e:
                last_error = e
                attempts += 1

                # Categorize error
                status = getattr(e, 'status', None)
                if status is None and hasattr(e, 'response'):
                    status = getattr(e.response, 'status', None)

                if status == 401:
                    # Auth errors are not retryable
                    raise NotionError(f"Authentication failed: {str(e)}") from e
                elif status == 404:
                    # Not found errors are not retryable
                    raise NotionError(f"Resource not found: {str(e)}") from e
                elif status == 429:
                    # Rate limit (should not happen with our rate limiter, but handle it)
                    logger.warning(f"Rate limited by Notion API: {str(e)}")
                    if not retry or attempts > max_retries:
                        raise NotionError(f"Rate limited: {str(e)}") from e
                    # Wait and retry
                    time.sleep(2 ** attempts)  # Exponential backoff
                elif status in [500, 502, 503, 504]:
                    # Transient server errors - retry if enabled
                    logger.warning(f"Transient error (status {status}): {str(e)}")
                    if not retry or attempts > max_retries:
                        raise NotionError(f"Notion API error: {str(e)}") from e
                    # Wait and retry
                    time.sleep(2 ** attempts)  # Exponential backoff
                else:
                    # Other errors - not retryable
                    raise NotionError(f"Notion API error: {str(e)}") from e

        # Max retries exceeded
        raise NotionError(f"Max retries exceeded: {str(last_error)}") from last_error
