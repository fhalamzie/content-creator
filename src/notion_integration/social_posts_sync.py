"""
Notion Social Posts Sync

Syncs social media posts from RepurposingAgent to Notion database.

Example:
    from src.notion_integration.social_posts_sync import SocialPostsSync

    sync = SocialPostsSync(
        notion_token="secret_token",
        social_posts_db_id="db_123",
        blog_posts_db_id="db_456"
    )

    # Sync single social post
    result = sync.sync_social_post(
        social_post=post_data,
        blog_title="PropTech Trends 2025",
        blog_post_id="page_789"
    )
    print(f"Synced: {result['action']}")

    # Sync complete batch (4 platforms)
    result = sync.sync_social_posts_batch(
        social_posts=all_posts,
        blog_title="PropTech Trends 2025",
        blog_post_id="page_789"
    )
    print(f"Synced {result['total']} posts")
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from src.notion_integration.notion_client import NotionClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SocialPostsSyncError(Exception):
    """Raised when social post sync fails"""
    pass


class SocialPostsSync:
    """
    Sync social media posts to Notion database

    Features:
    - Syncs posts for LinkedIn, Facebook, Instagram, TikTok
    - Maps platform names to Notion select options
    - Handles hashtags as multi_select
    - Links to blog post via relation
    - Batch processing with skip_errors support
    - Statistics tracking
    - Rate-limited via NotionClient
    """

    def __init__(
        self,
        notion_token: str,
        social_posts_db_id: Optional[str] = None,
        blog_posts_db_id: Optional[str] = None,
        rate_limit: float = 2.5
    ):
        """
        Initialize social posts sync

        Args:
            notion_token: Notion integration token
            social_posts_db_id: Notion database ID for social posts
            blog_posts_db_id: Notion database ID for blog posts (for relations)
            rate_limit: Requests per second (default 2.5)

        Raises:
            ValueError: If token is empty
        """
        if not notion_token or len(notion_token.strip()) == 0:
            raise ValueError("Notion token cannot be empty")

        self.notion_client = NotionClient(token=notion_token, rate_limit=rate_limit)
        self.social_posts_db_id = social_posts_db_id
        self.blog_posts_db_id = blog_posts_db_id

        # Statistics
        self.total_synced = 0
        self.failed_syncs = 0

        logger.info(
            "social_posts_sync_initialized",
            social_posts_db_id=social_posts_db_id,
            blog_posts_db_id=blog_posts_db_id,
            rate_limit=rate_limit
        )

    def sync_social_post(
        self,
        social_post: Dict[str, Any],
        blog_title: str,
        blog_post_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync single social post to Notion

        Args:
            social_post: Post data from RepurposingAgent.generate_social_posts()
                        Expected keys: platform, content, hashtags, character_count,
                                      image (optional), cost, tokens
            blog_title: Title of the source blog post (for title generation)
            blog_post_id: Optional Notion page ID for blog post relation

        Returns:
            Dictionary with:
            - id: Notion page ID
            - action: 'created'
            - platform: Platform name
            - url: Notion page URL

        Raises:
            SocialPostsSyncError: If sync fails
        """
        if not self.social_posts_db_id:
            raise SocialPostsSyncError(
                "Social posts database ID not set. Provide social_posts_db_id in constructor."
            )

        try:
            platform = social_post.get('platform', 'Unknown')

            # Build Notion properties from social post data
            properties = self._build_social_post_properties(
                social_post=social_post,
                blog_title=blog_title,
                blog_post_id=blog_post_id
            )

            # Create new page
            logger.info("creating_social_post", platform=platform, blog_title=blog_title)

            response = self.notion_client.create_page(
                parent_database_id=self.social_posts_db_id,
                properties=properties,
                retry=True
            )

            self.total_synced += 1

            return {
                'id': response['id'],
                'action': 'created',
                'platform': platform,
                'url': response.get('url')
            }

        except Exception as e:
            self.failed_syncs += 1
            platform = social_post.get('platform', 'Unknown')
            logger.error("social_post_sync_failed", platform=platform, error=str(e))
            raise SocialPostsSyncError(f"Failed to sync {platform} post: {e}")

    def sync_social_posts_batch(
        self,
        social_posts: List[Dict[str, Any]],
        blog_title: str,
        blog_post_id: Optional[str] = None,
        skip_errors: bool = False
    ) -> Dict[str, Any]:
        """
        Sync complete batch of social posts (typically 4 platforms)

        Args:
            social_posts: List of post data from RepurposingAgent
            blog_title: Title of the source blog post
            blog_post_id: Optional Notion page ID for blog post relation
            skip_errors: If True, skip failed syncs and continue

        Returns:
            Dictionary with:
            - total: Total posts synced
            - by_platform: Dict of {platform: count}
            - failed: Failed syncs

        Raises:
            SocialPostsSyncError: If skip_errors=False and any sync fails
        """
        results = {
            'total': 0,
            'by_platform': {},
            'failed': 0
        }

        for social_post in social_posts:
            platform = social_post.get('platform', 'Unknown')

            try:
                self.sync_social_post(
                    social_post=social_post,
                    blog_title=blog_title,
                    blog_post_id=blog_post_id
                )
                results['total'] += 1
                results['by_platform'][platform] = results['by_platform'].get(platform, 0) + 1

            except SocialPostsSyncError as e:
                if not skip_errors:
                    raise
                results['failed'] += 1
                logger.warning("social_post_sync_skipped", platform=platform, error=str(e))

        logger.info(
            "social_posts_batch_sync_complete",
            total=results['total'],
            by_platform=results['by_platform'],
            failed=results['failed']
        )

        return results

    def _build_social_post_properties(
        self,
        social_post: Dict[str, Any],
        blog_title: str,
        blog_post_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build Notion properties dictionary from social post data

        Args:
            social_post: Social post data from RepurposingAgent
            blog_title: Title of the source blog post
            blog_post_id: Optional Notion page ID for blog post relation

        Returns:
            Notion properties dictionary
        """
        platform = social_post.get('platform', 'Unknown')
        content = social_post.get('content', '')
        hashtags = social_post.get('hashtags', [])
        character_count = social_post.get('character_count', len(content))
        image_data = social_post.get('image', {})

        # Title: "{Blog Title} - {Platform}"
        title = f"{blog_title} - {platform}"

        properties = {
            'Title': {
                'title': [
                    {
                        'text': {
                            'content': title
                        }
                    }
                ]
            },
            'Platform': {
                'select': {
                    'name': platform
                }
            },
            'Content': {
                'rich_text': [
                    {
                        'text': {
                            'content': content[:2000]  # Notion rich_text limit
                        }
                    }
                ]
            },
            'Character Count': {
                'number': character_count
            },
            'Status': {
                'select': {
                    'name': 'Draft'
                }
            }
        }

        # Add media URL if image was generated
        if image_data and image_data.get('url'):
            properties['Media URL'] = {
                'url': image_data['url']
            }

        # Add hashtags as multi_select
        if hashtags:
            # Remove # prefix for Notion (Notion adds it automatically in display)
            hashtag_names = [tag.lstrip('#') for tag in hashtags]
            properties['Hashtags'] = {
                'multi_select': [
                    {'name': name} for name in hashtag_names
                ]
            }

        # Add blog post relation if provided
        if blog_post_id and self.blog_posts_db_id:
            properties['Blog Post'] = {
                'relation': [
                    {'id': blog_post_id}
                ]
            }

        # Dates
        now = datetime.now(timezone.utc)

        properties['Created'] = {
            'date': {
                'start': now.isoformat()
            }
        }

        return properties

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get sync statistics

        Returns:
            Dictionary with total_synced, failed_syncs, success_rate
        """
        total_attempts = self.total_synced + self.failed_syncs
        success_rate = self.total_synced / total_attempts if total_attempts > 0 else 0.0

        return {
            'total_synced': self.total_synced,
            'failed_syncs': self.failed_syncs,
            'success_rate': success_rate
        }
