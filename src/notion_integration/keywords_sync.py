"""
Notion Keywords Sync

Syncs keyword research data from KeywordResearchAgent to Notion database.

Example:
    from src.notion_integration.keywords_sync import KeywordsSync

    sync = KeywordsSync(
        notion_token="secret_token",
        database_id="db_123"
    )

    # Sync single keyword
    result = sync.sync_keyword(keyword_data, "Primary", "PropTech Trends")
    print(f"Synced: {result['action']}")

    # Sync complete keyword set (primary + secondary + long-tail)
    result = sync.sync_keyword_set(research_result, "PropTech Trends")
    print(f"Synced {result['total']} keywords")
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from src.notion_integration.notion_client import NotionClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KeywordsSyncError(Exception):
    """Raised when keyword sync fails"""
    pass


class KeywordsSync:
    """
    Sync keyword research data to Notion database

    Features:
    - Syncs primary, secondary, and long-tail keywords
    - Maps keyword types to Notion select options
    - Normalizes competition levels and search intent
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
        Initialize keywords sync

        Args:
            notion_token: Notion integration token
            database_id: Notion database ID for keywords
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

        logger.info("keywords_sync_initialized", database_id=database_id, rate_limit=rate_limit)

    def sync_keyword(
        self,
        keyword_data: Dict[str, Any],
        keyword_type: str,
        source_topic: str,
        opportunity_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Sync single keyword to Notion

        Args:
            keyword_data: Keyword data dict from KeywordResearchAgent
            keyword_type: Type of keyword (Primary, Secondary, Long-tail, Question)
            source_topic: The topic this keyword came from
            opportunity_score: Optional opportunity score (0-100)

        Returns:
            Dictionary with:
            - id: Notion page ID
            - action: 'created'
            - keyword: Keyword text
            - url: Notion page URL

        Raises:
            KeywordsSyncError: If sync fails
        """
        if not self.database_id:
            raise KeywordsSyncError("Database ID not set. Provide database_id in constructor.")

        try:
            keyword_text = keyword_data.get('keyword', 'Unknown')

            # Build Notion properties from keyword data
            properties = self._build_keyword_properties(
                keyword_data=keyword_data,
                keyword_type=keyword_type,
                source_topic=source_topic,
                opportunity_score=opportunity_score
            )

            # Create new page
            logger.info("creating_new_keyword", keyword=keyword_text, type=keyword_type)

            response = self.notion_client.create_page(
                parent_database_id=self.database_id,
                properties=properties,
                retry=True
            )

            self.total_synced += 1

            return {
                'id': response['id'],
                'action': 'created',
                'keyword': keyword_text,
                'url': response.get('url')
            }

        except Exception as e:
            self.failed_syncs += 1
            keyword_text = keyword_data.get('keyword', 'Unknown')
            logger.error("keyword_sync_failed", keyword=keyword_text, error=str(e))
            raise KeywordsSyncError(f"Failed to sync keyword '{keyword_text}': {e}")

    def sync_keyword_set(
        self,
        research_result: Dict[str, Any],
        source_topic: str,
        skip_errors: bool = False
    ) -> Dict[str, Any]:
        """
        Sync complete keyword research set (primary + secondary + long-tail)

        Args:
            research_result: Complete result from KeywordResearchAgent
            source_topic: The topic this keyword research came from
            skip_errors: If True, skip failed syncs and continue

        Returns:
            Dictionary with:
            - total: Total keywords synced
            - primary: Primary keywords synced
            - secondary: Secondary keywords synced
            - long_tail: Long-tail keywords synced
            - failed: Failed syncs

        Raises:
            KeywordsSyncError: If skip_errors=False and any sync fails
        """
        results = {
            'total': 0,
            'primary': 0,
            'secondary': 0,
            'long_tail': 0,
            'failed': 0
        }

        # Sync primary keyword
        primary = research_result.get('primary_keyword')
        if primary:
            try:
                self.sync_keyword(primary, "Primary", source_topic)
                results['primary'] += 1
                results['total'] += 1
            except KeywordsSyncError as e:
                if not skip_errors:
                    raise
                results['failed'] += 1
                logger.warning("primary_keyword_sync_skipped", error=str(e))

        # Sync secondary keywords
        secondary = research_result.get('secondary_keywords', [])
        for kw in secondary:
            try:
                self.sync_keyword(kw, "Secondary", source_topic)
                results['secondary'] += 1
                results['total'] += 1
            except KeywordsSyncError as e:
                if not skip_errors:
                    raise
                results['failed'] += 1
                logger.warning("secondary_keyword_sync_skipped", keyword=kw.get('keyword'), error=str(e))

        # Sync long-tail keywords
        long_tail = research_result.get('long_tail_keywords', [])
        for kw in long_tail:
            try:
                self.sync_keyword(kw, "Long-tail", source_topic)
                results['long_tail'] += 1
                results['total'] += 1
            except KeywordsSyncError as e:
                if not skip_errors:
                    raise
                results['failed'] += 1
                logger.warning("long_tail_keyword_sync_skipped", keyword=kw.get('keyword'), error=str(e))

        logger.info(
            "keyword_set_sync_complete",
            total=results['total'],
            primary=results['primary'],
            secondary=results['secondary'],
            long_tail=results['long_tail'],
            failed=results['failed']
        )

        return results

    def _build_keyword_properties(
        self,
        keyword_data: Dict[str, Any],
        keyword_type: str,
        source_topic: str,
        opportunity_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Build Notion properties dictionary from keyword data

        Args:
            keyword_data: Keyword data dict
            keyword_type: Type of keyword (Primary, Secondary, Long-tail, Question)
            source_topic: The topic this keyword came from
            opportunity_score: Optional opportunity score (0-100)

        Returns:
            Notion properties dictionary
        """
        properties = {
            'Keyword': {
                'title': [
                    {
                        'text': {
                            'content': keyword_data.get('keyword', 'Unknown')
                        }
                    }
                ]
            },
            'Search Volume': {
                'rich_text': [
                    {
                        'text': {
                            'content': keyword_data.get('search_volume', 'Unknown')
                        }
                    }
                ]
            },
            'Keyword Type': {
                'select': {
                    'name': keyword_type
                }
            },
            'Source Topic': {
                'rich_text': [
                    {
                        'text': {
                            'content': source_topic
                        }
                    }
                ]
            }
        }

        # Normalize competition level (Low, Medium, High)
        competition = keyword_data.get('competition', 'Medium')
        competition_normalized = competition.capitalize()
        if competition_normalized not in ['Low', 'Medium', 'High']:
            competition_normalized = 'Medium'

        properties['Competition'] = {
            'select': {
                'name': competition_normalized
            }
        }

        # Difficulty score (0-100)
        difficulty = keyword_data.get('difficulty', 50)
        properties['Difficulty'] = {
            'number': difficulty
        }

        # Search intent (Informational, Commercial, Transactional, Navigational)
        intent = keyword_data.get('intent', 'Informational')
        intent_normalized = intent.capitalize()
        if intent_normalized not in ['Informational', 'Commercial', 'Transactional', 'Navigational']:
            intent_normalized = 'Informational'

        properties['Intent'] = {
            'select': {
                'name': intent_normalized
            }
        }

        # Relevance (0-1, optional for secondary keywords)
        if 'relevance' in keyword_data:
            properties['Relevance'] = {
                'number': keyword_data['relevance']
            }

        # Opportunity score (0-100, optional, set by OpportunityScorer)
        if opportunity_score is not None:
            properties['Opportunity Score'] = {
                'number': opportunity_score
            }

        # Dates
        now = datetime.now(timezone.utc)

        properties['Research Date'] = {
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
