"""
SyncManager - Cache to Notion Sync with Rate Limiting

Syncs cached content to Notion databases with rate limiting and progress tracking.

Design Principles:
- Batch operations with progress callbacks
- Rate limiting (2.5 req/sec for Notion API)
- ETA calculation for UI
- Retry logic with exponential backoff
- Comprehensive error handling
- Detailed logging
"""

import logging
import time
from typing import Dict, Any, List, Optional, Callable

from src.cache_manager import CacheManager
from src.notion_integration.notion_client import NotionClient
from src.notion_integration.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class SyncError(Exception):
    """Base exception for sync errors"""
    pass


class SyncManager:
    """
    Manages syncing cached content to Notion databases.

    Features:
    - Batch blog post sync
    - Batch social posts sync
    - Rate limiting (configurable)
    - Progress callbacks with ETA
    - Retry logic
    - Error handling

    Usage:
        sync_manager = SyncManager()

        # Sync all blog posts with progress
        def progress(data):
            print(f"Progress: {data['current']}/{data['total']} (ETA: {data['eta_seconds']}s)")

        results = sync_manager.sync_all_blog_posts(progress_callback=progress)
        print(f"Synced {results['successful']}/{results['total']} posts")
    """

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        notion_client: Optional[NotionClient] = None,
        rate_limiter: Optional[RateLimiter] = None,
        max_retries: int = 3
    ):
        """
        Initialize SyncManager.

        Args:
            cache_manager: Optional CacheManager instance
            notion_client: Optional NotionClient instance
            rate_limiter: Optional RateLimiter instance
            max_retries: Maximum retry attempts (default: 3)
        """
        self.cache_manager = cache_manager or CacheManager()
        self.notion_client = notion_client or NotionClient()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_retries = max_retries

        logger.info(
            f"SyncManager initialized: "
            f"rate_limit={self.rate_limiter.rate} req/sec, "
            f"max_retries={max_retries}"
        )

    def sync_blog_post(
        self,
        blog_data: Dict[str, Any],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync single blog post to Notion.

        Args:
            blog_data: Blog post data (content, metadata)
            progress_callback: Optional progress callback

        Returns:
            Dict with:
                - success: bool
                - page_id: Notion page ID
                - url: Notion page URL

        Raises:
            SyncError: If sync fails after retries
        """
        slug = blog_data.get('slug', 'unknown')

        logger.info(f"Syncing blog post: {slug}")

        # Call progress callback (start)
        if progress_callback:
            progress_callback({
                'current': 0,
                'total': 1,
                'eta_seconds': self.calculate_eta(1),
                'message': f'Syncing {slug}...'
            })

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Acquire rate limit token
                self.rate_limiter.acquire()

                # Create Notion page
                properties = self._build_blog_properties(blog_data)
                page = self.notion_client.create_page(
                    database_id=self.notion_client.database_ids['blog_posts'],
                    properties=properties
                )

                logger.info(f"Synced blog post successfully: {slug} → {page['id']}")

                # Call progress callback (complete)
                if progress_callback:
                    progress_callback({
                        'current': 1,
                        'total': 1,
                        'eta_seconds': 0,
                        'message': f'Synced {slug}'
                    })

                return {
                    'success': True,
                    'page_id': page['id'],
                    'url': page['url']
                }

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} "
                        f"after {backoff}s: {e}"
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Failed to sync blog post after {self.max_retries} retries: {e}")

        # All retries exhausted
        raise SyncError(
            f"Failed to sync blog post '{slug}' after {self.max_retries} retries: {last_error}"
        ) from last_error

    def sync_all_blog_posts(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync all cached blog posts to Notion.

        Args:
            progress_callback: Optional progress callback

        Returns:
            Dict with:
                - total: Total posts processed
                - successful: Number of successful syncs
                - failed: Number of failed syncs
                - errors: List of error messages
        """
        logger.info("Starting batch blog post sync")

        # Get cached blog posts
        cached_posts = self.cache_manager.get_cached_blog_posts()
        total = len(cached_posts)

        if total == 0:
            logger.info("No cached blog posts to sync")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }

        logger.info(f"Found {total} cached blog posts to sync")

        # Sync each post
        successful = 0
        failed = 0
        errors = []

        for idx, post_data in enumerate(cached_posts):
            current = idx + 1
            remaining = total - current
            eta = self.calculate_eta(remaining)

            # Call progress callback
            if progress_callback:
                progress_callback({
                    'current': current,
                    'total': total,
                    'eta_seconds': eta,
                    'message': f"Syncing {post_data.get('slug', 'unknown')} ({current}/{total})"
                })

            try:
                self.sync_blog_post(post_data, progress_callback=None)  # Don't double-call callback
                successful += 1
            except SyncError as e:
                failed += 1
                errors.append(str(e))
                logger.error(f"Failed to sync post: {e}")

        logger.info(
            f"Batch blog post sync complete: "
            f"{successful} successful, {failed} failed"
        )

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'errors': errors
        }

    def sync_all_social_posts(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Sync all cached social posts to Notion.

        Args:
            progress_callback: Optional progress callback

        Returns:
            Dict with:
                - total: Total posts processed
                - successful: Number of successful syncs
                - failed: Number of failed syncs
                - errors: List of error messages
        """
        logger.info("Starting batch social post sync")

        # Get cached social posts
        cached_posts = self.cache_manager.get_cached_social_posts()
        total = len(cached_posts)

        if total == 0:
            logger.info("No cached social posts to sync")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }

        logger.info(f"Found {total} cached social posts to sync")

        # Sync each post
        successful = 0
        failed = 0
        errors = []

        for idx, post_data in enumerate(cached_posts):
            current = idx + 1
            remaining = total - current
            eta = self.calculate_eta(remaining)

            # Call progress callback
            if progress_callback:
                progress_callback({
                    'current': current,
                    'total': total,
                    'eta_seconds': eta,
                    'message': f"Syncing {post_data.get('platform', 'unknown')} post ({current}/{total})"
                })

            try:
                # Acquire rate limit token
                self.rate_limiter.acquire()

                # Create Notion page
                properties = self._build_social_properties(post_data)
                page = self.notion_client.create_page(
                    database_id=self.notion_client.database_ids['social_posts'],
                    properties=properties
                )

                successful += 1
                logger.info(f"Synced social post: {post_data.get('platform')} → {page['id']}")

            except Exception as e:
                failed += 1
                errors.append(str(e))
                logger.error(f"Failed to sync social post: {e}")

        logger.info(
            f"Batch social post sync complete: "
            f"{successful} successful, {failed} failed"
        )

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'errors': errors
        }

    def calculate_eta(self, num_items: int) -> float:
        """
        Calculate estimated time to sync items.

        Args:
            num_items: Number of items to sync

        Returns:
            Estimated time in seconds
        """
        if num_items == 0:
            return 0.0

        # ETA = num_items / rate (req/sec)
        return num_items / self.rate_limiter.rate

    def _build_blog_properties(self, blog_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Notion properties for blog post.

        Args:
            blog_data: Blog post data

        Returns:
            Dict of Notion properties
        """
        metadata = blog_data.get('metadata', {})

        return {
            'Title': {
                'title': [
                    {
                        'text': {
                            'content': metadata.get('topic', 'Untitled')
                        }
                    }
                ]
            },
            'Content': {
                'rich_text': [
                    {
                        'text': {
                            'content': blog_data.get('content', '')[:2000]  # Notion limit
                        }
                    }
                ]
            },
            'Word Count': {
                'number': metadata.get('word_count', 0)
            },
            'Language': {
                'select': {
                    'name': metadata.get('language', 'de')
                }
            },
            'Status': {
                'select': {
                    'name': 'Draft'
                }
            }
        }

    def _build_social_properties(self, social_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Notion properties for social post.

        Args:
            social_data: Social post data

        Returns:
            Dict of Notion properties
        """
        return {
            'Platform': {
                'select': {
                    'name': social_data.get('platform', 'unknown').capitalize()
                }
            },
            'Content': {
                'rich_text': [
                    {
                        'text': {
                            'content': social_data.get('content', '')[:2000]  # Notion limit
                        }
                    }
                ]
            },
            'Status': {
                'select': {
                    'name': 'Draft'
                }
            }
        }
