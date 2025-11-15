"""
Tests for CompetitorsSync class

Tests sync of competitor data from CompetitorResearchAgent to Notion database.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from src.notion_integration.competitors_sync import CompetitorsSync, CompetitorsSyncError


@pytest.fixture
def valid_competitor():
    """Valid competitor data fixture"""
    return {
        'name': 'PropTech Competitor Inc',
        'website': 'https://example.com',
        'description': 'Leading proptech company in Germany',
        'social_handles': {
            'linkedin': 'https://linkedin.com/company/example',
            'twitter': 'https://twitter.com/example',
            'facebook': 'https://facebook.com/example',
            'instagram': 'https://instagram.com/example'
        },
        'content_strategy': {
            'topics': ['Real Estate Tech', 'Property Management'],
            'posting_frequency': '3-4x/week',
            'content_types': ['Blog posts', 'Videos'],
            'strengths': ['High engagement', 'Professional imagery'],
            'weaknesses': ['Irregular posting']
        }
    }


@pytest.fixture
def minimal_competitor():
    """Minimal competitor data (only required fields)"""
    return {
        'name': 'Minimal Competitor',
        'website': '',
        'description': '',
        'social_handles': {
            'linkedin': '',
            'twitter': '',
            'facebook': '',
            'instagram': ''
        },
        'content_strategy': {
            'topics': [],
            'posting_frequency': 'Unknown',
            'content_types': [],
            'strengths': [],
            'weaknesses': []
        }
    }


@pytest.fixture
def notion_response():
    """Mock Notion API response"""
    return {
        'id': 'notion_page_123',
        'url': 'https://notion.so/page_123'
    }


class TestCompetitorsSyncInitialization:
    """Test CompetitorsSync initialization"""

    def test_init_with_valid_params(self):
        """Test initialization with valid parameters"""
        sync = CompetitorsSync(
            notion_token="secret_token",
            database_id="db_123",
            rate_limit=2.5
        )

        assert sync.database_id == "db_123"
        assert sync.total_synced == 0
        assert sync.failed_syncs == 0

    def test_init_without_database_id(self):
        """Test initialization without database_id (can be set later)"""
        sync = CompetitorsSync(notion_token="secret_token")

        assert sync.database_id is None

    def test_init_with_empty_token(self):
        """Test initialization with empty token raises ValueError"""
        with pytest.raises(ValueError, match="Notion token cannot be empty"):
            CompetitorsSync(notion_token="")

    def test_init_with_whitespace_token(self):
        """Test initialization with whitespace-only token raises ValueError"""
        with pytest.raises(ValueError, match="Notion token cannot be empty"):
            CompetitorsSync(notion_token="   ")


class TestBuildProperties:
    """Test _build_properties method"""

    def test_build_properties_with_full_competitor(self, valid_competitor):
        """Test property building with all fields populated"""
        sync = CompetitorsSync(notion_token="token", database_id="db")
        properties = sync._build_properties(valid_competitor)

        # Required fields
        assert properties['Company Name']['title'][0]['text']['content'] == 'PropTech Competitor Inc'
        assert properties['Website']['url'] == 'https://example.com'
        assert 'Description' in properties
        assert properties['Description']['rich_text'][0]['text']['content'] == 'Leading proptech company in Germany'

        # Social handles
        assert properties['LinkedIn URL']['url'] == 'https://linkedin.com/company/example'
        assert properties['Facebook URL']['url'] == 'https://facebook.com/example'
        assert properties['Instagram Handle']['rich_text'][0]['text']['content'] == 'https://instagram.com/example'
        assert properties['TikTok Handle']['rich_text'][0]['text']['content'] == 'https://twitter.com/example'

        # Content strategy
        assert properties['Posting Frequency']['select']['name'] == '3-4x/week'

        # JSON-serialized content strategy
        import json
        strategy = json.loads(properties['Content Strategy']['rich_text'][0]['text']['content'])
        assert strategy['topics'] == ['Real Estate Tech', 'Property Management']
        assert strategy['content_types'] == ['Blog posts', 'Videos']
        assert strategy['strengths'] == ['High engagement', 'Professional imagery']
        assert strategy['weaknesses'] == ['Irregular posting']

        # Dates
        assert 'Last Analyzed' in properties
        assert 'Created' in properties

    def test_build_properties_with_minimal_competitor(self, minimal_competitor):
        """Test property building with minimal fields"""
        sync = CompetitorsSync(notion_token="token", database_id="db")
        properties = sync._build_properties(minimal_competitor)

        # Required fields should still be present
        assert properties['Company Name']['title'][0]['text']['content'] == 'Minimal Competitor'

        # Optional fields should be omitted or empty
        assert 'Website' not in properties or properties['Website']['url'] == ''

        # Posting frequency should default to 'Occasional'
        assert properties['Posting Frequency']['select']['name'] == 'Occasional'

    def test_build_properties_truncates_long_description(self):
        """Test that descriptions >2000 chars are truncated"""
        sync = CompetitorsSync(notion_token="token", database_id="db")
        competitor = {
            'name': 'Test',
            'website': '',
            'description': 'A' * 3000,  # 3000 chars
            'social_handles': {'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': ''},
            'content_strategy': {
                'topics': [],
                'posting_frequency': 'Unknown',
                'content_types': [],
                'strengths': [],
                'weaknesses': []
            }
        }

        properties = sync._build_properties(competitor)

        # Should be truncated to 2000 chars
        assert len(properties['Description']['rich_text'][0]['text']['content']) == 2000

    def test_build_properties_maps_posting_frequency(self):
        """Test posting frequency mapping to Notion select options"""
        sync = CompetitorsSync(notion_token="token", database_id="db")

        frequencies = {
            'Daily': 'Daily',
            '3-4x/week': '3-4x/week',
            '1-2x/week': '1-2x/week',
            'Occasional': 'Occasional',
            'Unknown': 'Occasional'  # Default
        }

        for agent_freq, notion_freq in frequencies.items():
            competitor = {
                'name': 'Test',
                'website': '',
                'description': '',
                'social_handles': {'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': ''},
                'content_strategy': {
                    'topics': [],
                    'posting_frequency': agent_freq,
                    'content_types': [],
                    'strengths': [],
                    'weaknesses': []
                }
            }

            properties = sync._build_properties(competitor)
            assert properties['Posting Frequency']['select']['name'] == notion_freq


class TestSyncCompetitor:
    """Test sync_competitor method"""

    @patch('src.notion_integration.competitors_sync.NotionClient')
    def test_sync_competitor_creates_new_page(self, mock_notion, valid_competitor, notion_response):
        """Test syncing creates new Notion page"""
        mock_client = Mock()
        mock_client.create_page.return_value = notion_response
        mock_notion.return_value = mock_client

        sync = CompetitorsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        result = sync.sync_competitor(valid_competitor)

        # Check create_page was called
        assert mock_client.create_page.called
        call_args = mock_client.create_page.call_args
        assert call_args[1]['parent_database_id'] == 'db_123'
        assert call_args[1]['retry'] is True

        # Check result
        assert result['id'] == 'notion_page_123'
        assert result['action'] == 'created'
        assert result['url'] == 'https://notion.so/page_123'
        assert sync.total_synced == 1
        assert sync.failed_syncs == 0

    @patch('src.notion_integration.competitors_sync.NotionClient')
    def test_sync_competitor_without_database_id_raises_error(self, mock_notion, valid_competitor):
        """Test syncing without database_id raises error"""
        sync = CompetitorsSync(notion_token="token")  # No database_id

        with pytest.raises(CompetitorsSyncError, match="Database ID not set"):
            sync.sync_competitor(valid_competitor)

    @patch('src.notion_integration.competitors_sync.NotionClient')
    def test_sync_competitor_handles_notion_api_error(self, mock_notion, valid_competitor):
        """Test sync handles Notion API errors"""
        mock_client = Mock()
        mock_client.create_page.side_effect = Exception("Notion API error")
        mock_notion.return_value = mock_client

        sync = CompetitorsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        with pytest.raises(CompetitorsSyncError, match="Failed to sync competitor"):
            sync.sync_competitor(valid_competitor)

        assert sync.failed_syncs == 1


class TestSyncBatch:
    """Test sync_batch method"""

    @patch('src.notion_integration.competitors_sync.NotionClient')
    def test_sync_batch_syncs_all_competitors(self, mock_notion, valid_competitor, notion_response):
        """Test batch sync of multiple competitors"""
        mock_client = Mock()
        mock_client.create_page.return_value = notion_response
        mock_notion.return_value = mock_client

        sync = CompetitorsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        competitors = [valid_competitor, valid_competitor, valid_competitor]
        results = sync.sync_batch(competitors)

        assert len(results) == 3
        assert all(r['action'] == 'created' for r in results)
        assert sync.total_synced == 3

    @patch('src.notion_integration.competitors_sync.NotionClient')
    def test_sync_batch_with_empty_list(self, mock_notion):
        """Test batch sync with empty list returns empty results"""
        sync = CompetitorsSync(notion_token="token", database_id="db_123")

        results = sync.sync_batch([])

        assert results == []

    @patch('src.notion_integration.competitors_sync.NotionClient')
    def test_sync_batch_skip_errors_continues_on_failure(self, mock_notion, valid_competitor, notion_response):
        """Test batch sync with skip_errors=True continues after failures"""
        mock_client = Mock()
        # First call fails, second succeeds
        mock_client.create_page.side_effect = [
            Exception("Error"),
            notion_response,
            notion_response
        ]
        mock_notion.return_value = mock_client

        sync = CompetitorsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        competitors = [valid_competitor, valid_competitor, valid_competitor]
        results = sync.sync_batch(competitors, skip_errors=True)

        # Should have 2 successful results (skipped the first failure)
        assert len(results) == 2
        assert sync.total_synced == 2
        assert sync.failed_syncs == 1

    @patch('src.notion_integration.competitors_sync.NotionClient')
    def test_sync_batch_without_skip_errors_raises_on_failure(self, mock_notion, valid_competitor):
        """Test batch sync without skip_errors raises on first failure"""
        mock_client = Mock()
        mock_client.create_page.side_effect = Exception("Notion API error")
        mock_notion.return_value = mock_client

        sync = CompetitorsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        competitors = [valid_competitor, valid_competitor]

        with pytest.raises(CompetitorsSyncError):
            sync.sync_batch(competitors, skip_errors=False)


class TestGetStatistics:
    """Test get_statistics method"""

    @patch('src.notion_integration.competitors_sync.NotionClient')
    def test_get_statistics_returns_correct_counts(self, mock_notion, valid_competitor, notion_response):
        """Test statistics tracking"""
        mock_client = Mock()
        mock_client.create_page.side_effect = [
            notion_response,
            Exception("Error"),
            notion_response
        ]
        mock_notion.return_value = mock_client

        sync = CompetitorsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        # Sync 2 successfully, 1 fails
        competitors = [valid_competitor, valid_competitor, valid_competitor]
        try:
            sync.sync_batch(competitors, skip_errors=True)
        except:
            pass

        stats = sync.get_statistics()

        assert stats['total_synced'] == 2
        assert stats['failed_syncs'] == 1
        assert stats['success_rate'] == 2 / 3
