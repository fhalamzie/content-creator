"""
Notion Competitors Sync

Syncs competitor data from CompetitorResearchAgent to Notion database.

Example:
    from src.notion_integration.competitors_sync import CompetitorsSync

    sync = CompetitorsSync(
        notion_token="secret_token",
        database_id="db_123"
    )

    # Sync single competitor
    result = sync.sync_competitor(competitor_data)
    print(f"Synced: {result['action']}")

    # Batch sync
    results = sync.sync_batch(competitors, skip_errors=True)
    print(sync.get_statistics())
"""

from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timezone
from src.notion_integration.notion_client import NotionClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CompetitorsSyncError(Exception):
    """Raised when competitor sync fails"""
    pass


class CompetitorsSync:
    """
    Sync competitor data to Notion database

    Features:
    - Creates new Notion pages for competitors
    - Skips duplicates (by company name)
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
        Initialize competitors sync

        Args:
            notion_token: Notion integration token
            database_id: Notion database ID for competitors
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

        logger.info("competitors_sync_initialized", database_id=database_id, rate_limit=rate_limit)

    def sync_competitor(
        self,
        competitor: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sync single competitor to Notion

        Args:
            competitor: Competitor data dict from CompetitorResearchAgent

        Returns:
            Dictionary with:
            - id: Notion page ID
            - action: 'created' or 'skipped'
            - competitor_name: Company name
            - url: Notion page URL (if created)
            - reason: Reason for skip (if skipped)

        Raises:
            CompetitorsSyncError: If sync fails
        """
        if not self.database_id:
            raise CompetitorsSyncError("Database ID not set. Provide database_id in constructor.")

        try:
            competitor_name = competitor.get('name', 'Unknown')

            # Build Notion properties from competitor data
            properties = self._build_properties(competitor)

            # Create new page
            logger.info("creating_new_competitor", competitor_name=competitor_name)

            response = self.notion_client.create_page(
                parent_database_id=self.database_id,
                properties=properties,
                retry=True
            )

            self.total_synced += 1

            return {
                'id': response['id'],
                'action': 'created',
                'competitor_name': competitor_name,
                'url': response.get('url')
            }

        except Exception as e:
            self.failed_syncs += 1
            competitor_name = competitor.get('name', 'Unknown')
            logger.error("competitor_sync_failed", competitor_name=competitor_name, error=str(e))
            raise CompetitorsSyncError(f"Failed to sync competitor '{competitor_name}': {e}")

    def sync_batch(
        self,
        competitors: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Sync multiple competitors in batch

        Args:
            competitors: List of competitor data dicts
            skip_errors: If True, skip failed syncs and continue

        Returns:
            List of sync results (see sync_competitor for format)

        Raises:
            CompetitorsSyncError: If skip_errors=False and any sync fails
        """
        if not competitors:
            logger.info("sync_batch_empty")
            return []

        results = []

        for competitor in competitors:
            try:
                result = self.sync_competitor(competitor)
                results.append(result)
            except CompetitorsSyncError as e:
                if not skip_errors:
                    raise
                logger.warning("batch_competitor_skipped", competitor_name=competitor.get('name'), error=str(e))

        logger.info(
            "batch_sync_complete",
            total=len(competitors),
            synced=len(results),
            failed=len(competitors) - len(results)
        )

        return results

    def _build_properties(self, competitor: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Notion properties dictionary from competitor data

        Args:
            competitor: Competitor data dict

        Returns:
            Notion properties dictionary
        """
        properties = {
            'Company Name': {
                'title': [
                    {
                        'text': {
                            'content': competitor.get('name', 'Unknown')
                        }
                    }
                ]
            }
        }

        # Website (optional)
        if competitor.get('website'):
            properties['Website'] = {
                'url': competitor['website']
            }

        # Description (optional, truncate to 2000 chars)
        if competitor.get('description'):
            properties['Description'] = {
                'rich_text': [
                    {
                        'text': {
                            'content': competitor['description'][:2000]
                        }
                    }
                ]
            }

        # Social handles
        social_handles = competitor.get('social_handles', {})

        if social_handles.get('linkedin'):
            properties['LinkedIn URL'] = {
                'url': social_handles['linkedin']
            }

        if social_handles.get('facebook'):
            properties['Facebook URL'] = {
                'url': social_handles['facebook']
            }

        if social_handles.get('instagram'):
            properties['Instagram Handle'] = {
                'rich_text': [
                    {
                        'text': {
                            'content': social_handles['instagram']
                        }
                    }
                ]
            }

        if social_handles.get('twitter'):
            properties['TikTok Handle'] = {
                'rich_text': [
                    {
                        'text': {
                            'content': social_handles['twitter']
                        }
                    }
                ]
            }

        # Content strategy
        content_strategy = competitor.get('content_strategy', {})

        # Map posting frequency to Notion select options
        posting_freq = content_strategy.get('posting_frequency', 'Unknown')
        if posting_freq == 'Unknown':
            posting_freq = 'Occasional'

        # Ensure posting frequency matches Notion schema options
        valid_frequencies = ['Daily', '3-4x/week', '1-2x/week', 'Occasional']
        if posting_freq not in valid_frequencies:
            posting_freq = 'Occasional'

        properties['Posting Frequency'] = {
            'select': {
                'name': posting_freq
            }
        }

        # Serialize content strategy to JSON (topics, types, strengths, weaknesses)
        strategy_json = json.dumps({
            'topics': content_strategy.get('topics', []),
            'content_types': content_strategy.get('content_types', []),
            'strengths': content_strategy.get('strengths', []),
            'weaknesses': content_strategy.get('weaknesses', [])
        })

        properties['Content Strategy'] = {
            'rich_text': [
                {
                    'text': {
                        'content': strategy_json[:2000]  # Notion limit
                    }
                }
            ]
        }

        # Dates
        now = datetime.now(timezone.utc)

        properties['Last Analyzed'] = {
            'date': {
                'start': now.isoformat()
            }
        }

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
