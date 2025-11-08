"""
Unit tests for UniversalTopicAgent Notion sync functionality

Tests the sync_to_notion() method that syncs top topics to Notion.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from src.agents.universal_topic_agent import UniversalTopicAgent, UniversalTopicAgentError
from src.models.topic import Topic, TopicSource, TopicStatus
from src.utils.config_loader import FullConfig, MarketConfig, CollectorsConfig


@pytest.fixture
def sample_topics():
    """Create sample topics for testing"""
    return [
        Topic(
            id=f"topic_{i}",
            title=f"PropTech Trend #{i}",
            description=f"Description {i}",
            source=TopicSource.TRENDS,
            domain="PropTech",
            market="Germany",
            language="de",
            status=TopicStatus.RESEARCHED,
            priority=max(1, min(10, 15 - i)),  # Priority 1-10, descending
            engagement_score=100 + i,
            trending_score=50.0 + i,
            discovered_at=datetime(2025, 11, 8, 10, 0, 0),
            updated_at=datetime(2025, 11, 8, 10, 0, 0)
        )
        for i in range(15)
    ]


@pytest.fixture
def mock_config():
    """Create mock FullConfig"""
    return FullConfig(
        market=MarketConfig(
            domain="PropTech",
            market="Germany",
            language="de",
            vertical="Real Estate Technology",
            seed_keywords=["PropTech"]
        ),
        collectors=CollectorsConfig()
    )


@pytest.fixture
def mock_components():
    """Create mock components for UniversalTopicAgent"""
    return {
        'db_manager': Mock(),
        'feed_discovery': Mock(),
        'rss_collector': Mock(),
        'reddit_collector': None,
        'trends_collector': None,
        'autocomplete_collector': Mock(),
        'deduplicator': Mock(),
        'topic_clusterer': Mock(),
        'content_pipeline': Mock()
    }


class TestSyncToNotionSuccess:
    """Test successful Notion sync scenarios"""

    @pytest.mark.asyncio
    async def test_sync_top_10_topics(self, mock_config, mock_components, sample_topics):
        """Should sync top 10 topics by priority to Notion"""
        # Setup mocks
        mock_db = mock_components['db_manager']
        mock_db.get_topics_by_priority.return_value = sample_topics[:10]

        mock_notion_sync = Mock()
        mock_notion_sync.sync_batch.return_value = [
            {'action': 'created', 'id': f'notion_{i}', 'topic_id': f'topic_{i}'}
            for i in range(10)
        ]

        # Create agent
        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=mock_notion_sync,
            **mock_components
        )

        # Execute sync
        result = await agent.sync_to_notion(limit=10)

        # Verify database call
        mock_db.get_topics_by_priority.assert_called_once_with(limit=10)

        # Verify Notion sync call
        mock_notion_sync.sync_batch.assert_called_once()
        call_args = mock_notion_sync.sync_batch.call_args
        assert len(call_args[0][0]) == 10  # 10 topics passed
        assert call_args[1]['update_existing'] is True
        assert call_args[1]['skip_errors'] is True

        # Verify results
        assert result['topics_synced'] == 10
        assert result['notion_pages_created'] == 10
        assert result['notion_pages_updated'] == 0
        assert len(result['actions']) == 10
        assert agent.stats['topics_synced'] == 10

    @pytest.mark.asyncio
    async def test_sync_with_mixed_actions(self, mock_config, mock_components, sample_topics):
        """Should handle mixed create/update actions"""
        mock_db = mock_components['db_manager']
        mock_db.get_topics_by_priority.return_value = sample_topics[:5]

        mock_notion_sync = Mock()
        mock_notion_sync.sync_batch.return_value = [
            {'action': 'created', 'id': 'notion_0', 'topic_id': 'topic_0'},
            {'action': 'updated', 'id': 'notion_1', 'topic_id': 'topic_1'},
            {'action': 'created', 'id': 'notion_2', 'topic_id': 'topic_2'},
            {'action': 'updated', 'id': 'notion_3', 'topic_id': 'topic_3'},
            {'action': 'created', 'id': 'notion_4', 'topic_id': 'topic_4'},
        ]

        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=mock_notion_sync,
            **mock_components
        )

        result = await agent.sync_to_notion(limit=5)

        assert result['topics_synced'] == 5
        assert result['notion_pages_created'] == 3
        assert result['notion_pages_updated'] == 2

    @pytest.mark.asyncio
    async def test_sync_custom_limit(self, mock_config, mock_components, sample_topics):
        """Should respect custom limit parameter"""
        mock_db = mock_components['db_manager']
        mock_db.get_topics_by_priority.return_value = sample_topics[:3]

        mock_notion_sync = Mock()
        mock_notion_sync.sync_batch.return_value = [
            {'action': 'created', 'id': f'notion_{i}', 'topic_id': f'topic_{i}'}
            for i in range(3)
        ]

        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=mock_notion_sync,
            **mock_components
        )

        result = await agent.sync_to_notion(limit=3)

        mock_db.get_topics_by_priority.assert_called_once_with(limit=3)
        assert result['topics_synced'] == 3


class TestSyncToNotionEdgeCases:
    """Test edge cases for Notion sync"""

    @pytest.mark.asyncio
    async def test_sync_no_topics(self, mock_config, mock_components):
        """Should handle case when no topics exist in database"""
        mock_db = mock_components['db_manager']
        mock_db.get_topics_by_priority.return_value = []

        mock_notion_sync = Mock()

        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=mock_notion_sync,
            **mock_components
        )

        result = await agent.sync_to_notion(limit=10)

        # Should not call Notion sync
        mock_notion_sync.sync_batch.assert_not_called()

        # Should return zero counts
        assert result['topics_synced'] == 0
        assert result['notion_pages_created'] == 0
        assert result['notion_pages_updated'] == 0
        assert result['actions'] == []

    @pytest.mark.asyncio
    async def test_sync_without_notion_configured(self, mock_config, mock_components):
        """Should raise error if Notion sync not configured"""
        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=None,  # No Notion sync configured
            **mock_components
        )

        with pytest.raises(UniversalTopicAgentError, match="Notion sync not configured"):
            await agent.sync_to_notion(limit=10)

    @pytest.mark.asyncio
    async def test_sync_with_partial_failures(self, mock_config, mock_components, sample_topics):
        """Should handle partial failures with skip_errors=True"""
        mock_db = mock_components['db_manager']
        mock_db.get_topics_by_priority.return_value = sample_topics[:5]

        # Only 3 out of 5 succeed (skip_errors=True continues processing)
        mock_notion_sync = Mock()
        mock_notion_sync.sync_batch.return_value = [
            {'action': 'created', 'id': 'notion_0', 'topic_id': 'topic_0'},
            {'action': 'created', 'id': 'notion_2', 'topic_id': 'topic_2'},
            {'action': 'updated', 'id': 'notion_4', 'topic_id': 'topic_4'},
        ]

        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=mock_notion_sync,
            **mock_components
        )

        result = await agent.sync_to_notion(limit=5)

        # Only successful syncs counted
        assert result['topics_synced'] == 3
        assert result['notion_pages_created'] == 2
        assert result['notion_pages_updated'] == 1


class TestSyncToNotionErrors:
    """Test error handling in Notion sync"""

    @pytest.mark.asyncio
    async def test_sync_database_error(self, mock_config, mock_components):
        """Should raise error if database query fails"""
        mock_db = mock_components['db_manager']
        mock_db.get_topics_by_priority.side_effect = Exception("Database connection failed")

        mock_notion_sync = Mock()

        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=mock_notion_sync,
            **mock_components
        )

        with pytest.raises(UniversalTopicAgentError, match="Notion sync failed"):
            await agent.sync_to_notion(limit=10)

    @pytest.mark.asyncio
    async def test_sync_notion_error(self, mock_config, mock_components, sample_topics):
        """Should raise error if Notion sync_batch fails"""
        mock_db = mock_components['db_manager']
        mock_db.get_topics_by_priority.return_value = sample_topics[:5]

        mock_notion_sync = Mock()
        mock_notion_sync.sync_batch.side_effect = Exception("Notion API error")

        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=mock_notion_sync,
            **mock_components
        )

        with pytest.raises(UniversalTopicAgentError, match="Notion sync failed"):
            await agent.sync_to_notion(limit=5)


class TestSyncToNotionStatistics:
    """Test statistics tracking for Notion sync"""

    @pytest.mark.asyncio
    async def test_sync_updates_statistics(self, mock_config, mock_components, sample_topics):
        """Should update agent statistics after sync"""
        mock_db = mock_components['db_manager']
        mock_db.get_topics_by_priority.return_value = sample_topics[:10]

        mock_notion_sync = Mock()
        mock_notion_sync.sync_batch.return_value = [
            {'action': 'created', 'id': f'notion_{i}', 'topic_id': f'topic_{i}'}
            for i in range(10)
        ]

        agent = UniversalTopicAgent(
            config=mock_config,
            notion_sync=mock_notion_sync,
            **mock_components
        )

        # Initial stats
        assert agent.stats['topics_synced'] == 0

        # Sync topics
        await agent.sync_to_notion(limit=10)

        # Stats updated
        assert agent.stats['topics_synced'] == 10

        # Get statistics
        stats = agent.get_statistics()
        assert stats['topics_synced'] == 10
