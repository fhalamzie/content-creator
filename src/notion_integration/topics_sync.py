"""
Notion Topics Sync

Syncs Topic objects to Notion database for editorial review and tracking.

Example:
    from src.notion_integration.topics_sync import TopicsSync
    from src.models.topic import Topic

    sync = TopicsSync(
        notion_token="secret_token",
        database_id="db_123"
    )

    # Sync single topic
    result = sync.sync_topic(topic)
    print(f"Synced: {result['action']}")

    # Batch sync
    results = sync.sync_batch(topics, skip_errors=True)
    print(sync.get_statistics())
"""

from typing import Dict, List, Optional, Any
from src.models.topic import Topic
from src.notion_integration.notion_client import NotionClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TopicsSyncError(Exception):
    """Raised when topic sync fails"""
    pass


class TopicsSync:
    """
    Sync Topic objects to Notion database

    Features:
    - Creates new Notion pages for topics
    - Updates existing pages (when update_existing=True)
    - Skips already-synced topics
    - Batch processing with skip_errors support
    - Statistics tracking
    - Rate-limited via NotionClient
    """

    def __init__(
        self,
        notion_token: str,
        database_id: Optional[str] = None,
        rate_limit: float = 2.5
    ):
        """
        Initialize topics sync

        Args:
            notion_token: Notion integration token
            database_id: Notion database ID for topics
            rate_limit: Requests per second (default 2.5)

        Raises:
            ValueError: If token is empty
        """
        if not notion_token or len(notion_token.strip()) == 0:
            raise ValueError("Notion token cannot be empty")

        self.notion_client = NotionClient(token=notion_token, rate_limit=rate_limit)
        self.database_id = database_id

        # Statistics
        self.total_synced = 0
        self.failed_syncs = 0

        logger.info("topics_sync_initialized", database_id=database_id, rate_limit=rate_limit)

    def sync_topic(
        self,
        topic: Topic,
        update_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Sync single topic to Notion

        Args:
            topic: Topic object to sync
            update_existing: If True, update existing pages. If False, skip.

        Returns:
            Dictionary with:
            - id: Notion page ID
            - action: 'created', 'updated', or 'skipped'
            - topic_id: Original topic ID
            - url: Notion page URL (if created/updated)
            - reason: Reason for skip (if skipped)

        Raises:
            TopicsSyncError: If sync fails
        """
        if not self.database_id:
            raise TopicsSyncError("Database ID not set. Provide database_id in constructor.")

        try:
            # Check if topic already synced (has notion_id)
            # In this implementation, we use topic.id as notion page id if it exists
            has_notion_id = topic.id and topic.id.startswith('notion_')

            if has_notion_id and not update_existing:
                logger.info("topic_already_synced_skipping", topic_id=topic.id)
                return {
                    'id': topic.id,
                    'action': 'skipped',
                    'reason': 'already_synced',
                    'topic_id': topic.id
                }

            # Build Notion properties from Topic
            properties = self._build_properties(topic)

            # Update existing page
            if has_notion_id and update_existing:
                logger.info("updating_existing_topic", topic_id=topic.id, notion_id=topic.id)

                response = self.notion_client.update_page(
                    page_id=topic.id,
                    properties=properties,
                    retry=True
                )

                self.total_synced += 1

                return {
                    'id': response['id'],
                    'action': 'updated',
                    'topic_id': topic.id,
                    'url': response.get('url')
                }

            # Create new page
            logger.info("creating_new_topic", topic_title=topic.title)

            response = self.notion_client.create_page(
                parent_database_id=self.database_id,
                properties=properties,
                retry=True
            )

            self.total_synced += 1

            return {
                'id': response['id'],
                'action': 'created',
                'topic_id': topic.id or response['id'],
                'url': response.get('url')
            }

        except Exception as e:
            self.failed_syncs += 1
            logger.error("topic_sync_failed", topic_id=topic.id, error=str(e))
            raise TopicsSyncError(f"Failed to sync topic '{topic.title}': {e}")

    def sync_batch(
        self,
        topics: List[Topic],
        update_existing: bool = True,
        skip_errors: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Sync multiple topics in batch

        Args:
            topics: List of Topic objects
            update_existing: If True, update existing pages
            skip_errors: If True, skip failed syncs and continue

        Returns:
            List of sync results (see sync_topic for format)

        Raises:
            TopicsSyncError: If skip_errors=False and any sync fails
        """
        if not topics:
            logger.info("sync_batch_empty")
            return []

        results = []

        for topic in topics:
            try:
                result = self.sync_topic(topic, update_existing=update_existing)
                results.append(result)
            except TopicsSyncError as e:
                if not skip_errors:
                    raise
                logger.warning("batch_topic_skipped", topic_id=topic.id, error=str(e))

        logger.info(
            "batch_sync_complete",
            total=len(topics),
            synced=len(results),
            failed=len(topics) - len(results)
        )

        return results

    def _build_properties(self, topic: Topic) -> Dict[str, Any]:
        """
        Build Notion properties dictionary from Topic object

        Args:
            topic: Topic object

        Returns:
            Notion properties dictionary
        """
        properties = {
            'Title': {
                'title': [
                    {
                        'text': {
                            'content': topic.title
                        }
                    }
                ]
            },
            'Status': {
                'select': {
                    'name': topic.status.value
                }
            },
            'Priority': {
                'number': topic.priority
            },
            'Domain': {
                'select': {
                    'name': topic.domain
                }
            },
            'Market': {
                'select': {
                    'name': topic.market
                }
            },
            'Language': {
                'select': {
                    'name': topic.language
                }
            },
            'Source': {
                'select': {
                    'name': topic.source.value
                }
            }
        }

        # Optional properties
        if topic.description:
            properties['Description'] = {
                'rich_text': [
                    {
                        'text': {
                            'content': topic.description[:2000]  # Notion limit
                        }
                    }
                ]
            }

        if topic.source_url:
            properties['Source URL'] = {
                'url': str(topic.source_url)
            }

        if topic.intent:
            properties['Intent'] = {
                'select': {
                    'name': topic.intent.value
                }
            }

        properties['Engagement Score'] = {
            'number': topic.engagement_score
        }

        properties['Trending Score'] = {
            'number': topic.trending_score
        }

        if topic.research_report:
            # Truncate to Notion's rich text limit
            properties['Research Report'] = {
                'rich_text': [
                    {
                        'text': {
                            'content': topic.research_report[:2000]
                        }
                    }
                ]
            }

        if topic.word_count:
            properties['Word Count'] = {
                'number': topic.word_count
            }

        if topic.content_score:
            properties['Content Score'] = {
                'number': topic.content_score
            }

        # Image generation
        if topic.hero_image_url:
            properties['Hero Image URL'] = {
                'url': topic.hero_image_url
            }

        if topic.supporting_images:
            # Serialize supporting images to JSON string
            import json
            images_json = json.dumps(topic.supporting_images)
            properties['Supporting Images'] = {
                'rich_text': [
                    {
                        'text': {
                            'content': images_json[:2000]  # Notion limit
                        }
                    }
                ]
            }

        # Dates
        properties['Discovered At'] = {
            'date': {
                'start': topic.discovered_at.isoformat()
            }
        }

        properties['Updated At'] = {
            'date': {
                'start': topic.updated_at.isoformat()
            }
        }

        if topic.published_at:
            properties['Published At'] = {
                'date': {
                    'start': topic.published_at.isoformat()
                }
            }

        return properties

    def get_statistics(self) -> Dict[str, float]:
        """
        Get sync statistics

        Returns:
            Dictionary with:
            - total_synced: Total topics synced
            - failed_syncs: Failed sync attempts
            - success_rate: Ratio of successful to total (0-1)
        """
        total_attempts = self.total_synced + self.failed_syncs
        success_rate = (
            self.total_synced / total_attempts
            if total_attempts > 0
            else 0.0
        )

        return {
            'total_synced': self.total_synced,
            'failed_syncs': self.failed_syncs,
            'success_rate': success_rate
        }

    def reset_statistics(self) -> None:
        """Reset all statistics to zero"""
        self.total_synced = 0
        self.failed_syncs = 0
        logger.info("statistics_reset")
