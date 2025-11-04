"""
Tests for Notion Topics Sync

Tests syncing Topic objects to Notion database.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from src.notion_integration.topics_sync import TopicsSync, TopicsSyncError
from src.models.topic import Topic, TopicSource, TopicStatus, SearchIntent


class TestTopicsSyncInit:
    """Test TopicsSync initialization"""

    def test_init_with_token(self):
        """Should initialize with Notion token"""
        with patch('src.notion_integration.topics_sync.NotionClient') as mock_notion:
            sync = TopicsSync(notion_token="test_token")

            mock_notion.assert_called_once_with(token="test_token", rate_limit=2.5)
            assert sync.database_id is None
            assert sync.total_synced == 0
            assert sync.failed_syncs == 0

    def test_init_with_database_id(self):
        """Should initialize with database ID"""
        with patch('src.notion_integration.topics_sync.NotionClient'):
            sync = TopicsSync(notion_token="test_token", database_id="db_123")

            assert sync.database_id == "db_123"

    def test_init_without_token(self):
        """Should raise error if token is empty"""
        with pytest.raises(ValueError, match="Notion token cannot be empty"):
            TopicsSync(notion_token="")


class TestTopicsSyncSingle:
    """Test syncing single topic"""

    @pytest.fixture
    def sample_topic(self):
        """Create sample topic"""
        return Topic(
            id="topic_123",
            title="PropTech Trends 2025",
            description="Analysis of PropTech trends",
            source=TopicSource.TRENDS,
            source_url="https://example.com/trends",
            domain="SaaS",
            market="Germany",
            language="de",
            intent=SearchIntent.INFORMATIONAL,
            engagement_score=150,
            trending_score=75.5,
            status=TopicStatus.DISCOVERED,
            priority=8,
            discovered_at=datetime(2025, 11, 4, 10, 0, 0),
            updated_at=datetime(2025, 11, 4, 10, 0, 0)
        )

    @pytest.fixture
    def mock_notion_response(self):
        """Mock Notion API response"""
        return {
            'id': 'notion_page_123',
            'url': 'https://notion.so/page-123',
            'properties': {}
        }

    def test_sync_topic_new(self, sample_topic, mock_notion_response):
        """Should create new Notion page for topic without notion_id"""
        with patch('src.notion_integration.topics_sync.NotionClient') as mock_notion_class:
            mock_notion = Mock()
            mock_notion_class.return_value = mock_notion
            mock_notion.create_page.return_value = mock_notion_response

            sync = TopicsSync(notion_token="test_token", database_id="db_123")
            result = sync.sync_topic(sample_topic)

            # Verify create_page was called
            mock_notion.create_page.assert_called_once()
            call_args = mock_notion.create_page.call_args

            assert call_args[1]['parent_database_id'] == "db_123"
            assert 'properties' in call_args[1]

            # Verify result
            assert result['id'] == 'notion_page_123'
            assert result['action'] == 'created'
            assert result['topic_id'] == 'topic_123'

            # Verify statistics
            assert sync.total_synced == 1
            assert sync.failed_syncs == 0

    def test_sync_topic_update_existing(self, sample_topic, mock_notion_response):
        """Should update existing Notion page if topic has notion_id"""
        # Set notion_id to simulate existing sync
        sample_topic.id = "notion_page_456"

        with patch('src.notion_integration.topics_sync.NotionClient') as mock_notion_class:
            mock_notion = Mock()
            mock_notion_class.return_value = mock_notion
            mock_notion.update_page.return_value = mock_notion_response

            sync = TopicsSync(notion_token="test_token", database_id="db_123")
            result = sync.sync_topic(sample_topic, update_existing=True)

            # Verify update_page was called
            mock_notion.update_page.assert_called_once()
            call_args = mock_notion.update_page.call_args

            assert call_args[1]['page_id'] == "notion_page_456"
            assert 'properties' in call_args[1]

            # Verify result
            assert result['action'] == 'updated'

    def test_sync_topic_skip_existing(self, sample_topic):
        """Should skip topic with notion_id when update_existing=False"""
        sample_topic.id = "notion_page_789"

        with patch('src.notion_integration.topics_sync.NotionClient'):
            sync = TopicsSync(notion_token="test_token", database_id="db_123")
            result = sync.sync_topic(sample_topic, update_existing=False)

            assert result['action'] == 'skipped'
            assert result['reason'] == 'already_synced'

    def test_sync_topic_no_database_id(self, sample_topic):
        """Should raise error if database_id not set"""
        with patch('src.notion_integration.topics_sync.NotionClient'):
            sync = TopicsSync(notion_token="test_token")

            with pytest.raises(TopicsSyncError, match="Database ID not set"):
                sync.sync_topic(sample_topic)

    def test_sync_topic_api_error(self, sample_topic):
        """Should handle Notion API errors"""
        with patch('src.notion_integration.topics_sync.NotionClient') as mock_notion_class:
            mock_notion = Mock()
            mock_notion_class.return_value = mock_notion
            mock_notion.create_page.side_effect = Exception("API error")

            sync = TopicsSync(notion_token="test_token", database_id="db_123")

            with pytest.raises(TopicsSyncError, match="Failed to sync topic"):
                sync.sync_topic(sample_topic)

            assert sync.failed_syncs == 1


class TestTopicsSyncBatch:
    """Test batch syncing topics"""

    @pytest.fixture
    def sample_topics(self):
        """Create list of sample topics"""
        return [
            Topic(
                id=f"topic_{i}",
                title=f"Topic {i}",
                source=TopicSource.TRENDS,
                domain="Tech",
                market="US",
                language="en",
                status=TopicStatus.DISCOVERED,
                priority=5,
                discovered_at=datetime.now(),
                updated_at=datetime.now()
            )
            for i in range(5)
        ]

    def test_sync_batch_success(self, sample_topics):
        """Should sync multiple topics"""
        mock_response = {'id': 'notion_123', 'url': 'https://notion.so/123', 'properties': {}}

        with patch('src.notion_integration.topics_sync.NotionClient') as mock_notion_class:
            mock_notion = Mock()
            mock_notion_class.return_value = mock_notion
            mock_notion.create_page.return_value = mock_response

            sync = TopicsSync(notion_token="test_token", database_id="db_123")
            results = sync.sync_batch(sample_topics)

            # All topics should be synced
            assert len(results) == 5
            assert all(r['action'] == 'created' for r in results)
            assert sync.total_synced == 5
            assert sync.failed_syncs == 0

    def test_sync_batch_partial_failure(self, sample_topics):
        """Should handle partial failures when skip_errors=True"""
        mock_response = {'id': 'notion_123', 'url': 'https://notion.so/123', 'properties': {}}

        with patch('src.notion_integration.topics_sync.NotionClient') as mock_notion_class:
            mock_notion = Mock()
            mock_notion_class.return_value = mock_notion

            # Fail on 3rd topic
            def side_effect(*args, **kwargs):
                if mock_notion.create_page.call_count == 3:
                    raise Exception("API error")
                return mock_response

            mock_notion.create_page.side_effect = side_effect

            sync = TopicsSync(notion_token="test_token", database_id="db_123")
            results = sync.sync_batch(sample_topics, skip_errors=True)

            # 4 successful, 1 failed
            assert len(results) == 4
            assert sync.total_synced == 4
            assert sync.failed_syncs == 1

    def test_sync_batch_empty_list(self):
        """Should handle empty topic list"""
        with patch('src.notion_integration.topics_sync.NotionClient'):
            sync = TopicsSync(notion_token="test_token", database_id="db_123")
            results = sync.sync_batch([])

            assert results == []
            assert sync.total_synced == 0


class TestTopicsSyncProperties:
    """Test Notion properties conversion"""

    def test_build_properties(self):
        """Should build correct Notion properties from Topic"""
        topic = Topic(
            id="topic_123",
            title="Test Topic",
            description="Test description",
            source=TopicSource.RSS,
            source_url="https://example.com",
            domain="Tech",
            market="US",
            language="en",
            intent=SearchIntent.COMMERCIAL,
            engagement_score=100,
            trending_score=50.0,
            status=TopicStatus.VALIDATED,
            priority=7,
            research_report="Research content",
            citations=["url1", "url2"],
            word_count=1500,
            content_score=85.5,
            discovered_at=datetime(2025, 11, 4, 10, 0, 0),
            updated_at=datetime(2025, 11, 4, 11, 0, 0)
        )

        with patch('src.notion_integration.topics_sync.NotionClient'):
            sync = TopicsSync(notion_token="test_token", database_id="db_123")
            properties = sync._build_properties(topic)

            # Verify key properties
            assert properties['Title']['title'][0]['text']['content'] == "Test Topic"
            assert properties['Status']['select']['name'] == "validated"
            assert properties['Priority']['number'] == 7
            assert properties['Domain']['select']['name'] == "Tech"
            assert properties['Market']['select']['name'] == "US"
            assert properties['Language']['select']['name'] == "en"
            assert properties['Source']['select']['name'] == "rss"


class TestTopicsSyncStatistics:
    """Test statistics tracking"""

    def test_get_statistics(self):
        """Should return sync statistics"""
        with patch('src.notion_integration.topics_sync.NotionClient'):
            sync = TopicsSync(notion_token="test_token", database_id="db_123")
            sync.total_synced = 100
            sync.failed_syncs = 5

            stats = sync.get_statistics()

            assert stats['total_synced'] == 100
            assert stats['failed_syncs'] == 5
            assert abs(stats['success_rate'] - 0.95) < 0.01  # Allow floating point imprecision

    def test_get_statistics_no_syncs(self):
        """Should handle statistics when no syncs performed"""
        with patch('src.notion_integration.topics_sync.NotionClient'):
            sync = TopicsSync(notion_token="test_token")

            stats = sync.get_statistics()

            assert stats['total_synced'] == 0
            assert stats['failed_syncs'] == 0
            assert stats['success_rate'] == 0.0

    def test_reset_statistics(self):
        """Should reset all statistics"""
        with patch('src.notion_integration.topics_sync.NotionClient'):
            sync = TopicsSync(notion_token="test_token")
            sync.total_synced = 50
            sync.failed_syncs = 3

            sync.reset_statistics()

            assert sync.total_synced == 0
            assert sync.failed_syncs == 0
