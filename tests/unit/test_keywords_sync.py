"""
Tests for KeywordsSync class

Tests sync of keyword research data from KeywordResearchAgent to Notion database.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from src.notion_integration.keywords_sync import KeywordsSync, KeywordsSyncError


@pytest.fixture
def primary_keyword():
    """Primary keyword data fixture"""
    return {
        'keyword': 'PropTech Deutschland',
        'search_volume': '10K-100K/month',
        'competition': 'Medium',
        'difficulty': 55,
        'intent': 'Informational'
    }


@pytest.fixture
def secondary_keyword():
    """Secondary keyword data fixture"""
    return {
        'keyword': 'Immobilien Software',
        'search_volume': '1K-10K/month',
        'competition': 'Low',
        'difficulty': 30,
        'relevance': 0.8
    }


@pytest.fixture
def long_tail_keyword():
    """Long-tail keyword data fixture"""
    return {
        'keyword': 'beste PropTech Lösung für Hausverwaltung',
        'search_volume': '100-1K/month',
        'competition': 'Low',
        'difficulty': 20
    }


@pytest.fixture
def keyword_research_result():
    """Complete keyword research result"""
    return {
        'primary_keyword': {
            'keyword': 'PropTech Deutschland',
            'search_volume': '10K-100K/month',
            'competition': 'Medium',
            'difficulty': 55,
            'intent': 'Informational'
        },
        'secondary_keywords': [
            {
                'keyword': 'Immobilien Software',
                'search_volume': '1K-10K/month',
                'competition': 'Low',
                'difficulty': 30,
                'relevance': 0.8
            },
            {
                'keyword': 'Smart Building Tech',
                'search_volume': '1K-10K/month',
                'competition': 'Medium',
                'difficulty': 45,
                'relevance': 0.7
            }
        ],
        'long_tail_keywords': [
            {
                'keyword': 'beste PropTech Lösung für Hausverwaltung',
                'search_volume': '100-1K/month',
                'competition': 'Low',
                'difficulty': 20
            }
        ],
        'related_questions': [
            'Was ist PropTech?',
            'Wie funktioniert PropTech?'
        ]
    }


@pytest.fixture
def notion_response():
    """Mock Notion API response"""
    return {
        'id': 'notion_keyword_123',
        'url': 'https://notion.so/keyword_123'
    }


class TestKeywordsSyncInitialization:
    """Test KeywordsSync initialization"""

    def test_init_with_valid_params(self):
        """Test initialization with valid parameters"""
        sync = KeywordsSync(
            notion_token="secret_token",
            database_id="db_123",
            rate_limit=2.5
        )

        assert sync.database_id == "db_123"
        assert sync.total_synced == 0
        assert sync.failed_syncs == 0

    def test_init_without_database_id(self):
        """Test initialization without database_id (can be set later)"""
        sync = KeywordsSync(notion_token="secret_token")

        assert sync.database_id is None

    def test_init_with_empty_token(self):
        """Test initialization with empty token raises ValueError"""
        with pytest.raises(ValueError, match="Notion token cannot be empty"):
            KeywordsSync(notion_token="")


class TestBuildKeywordProperties:
    """Test _build_keyword_properties method"""

    def test_build_properties_with_primary_keyword(self, primary_keyword):
        """Test property building for primary keyword"""
        sync = KeywordsSync(notion_token="token", database_id="db")
        properties = sync._build_keyword_properties(
            keyword_data=primary_keyword,
            keyword_type="Primary",
            source_topic="PropTech Trends 2025"
        )

        # Required fields
        assert properties['Keyword']['title'][0]['text']['content'] == 'PropTech Deutschland'
        assert properties['Search Volume']['rich_text'][0]['text']['content'] == '10K-100K/month'
        assert properties['Competition']['select']['name'] == 'Medium'
        assert properties['Difficulty']['number'] == 55
        assert properties['Intent']['select']['name'] == 'Informational'
        assert properties['Keyword Type']['select']['name'] == 'Primary'
        assert properties['Source Topic']['rich_text'][0]['text']['content'] == 'PropTech Trends 2025'

        # Dates
        assert 'Research Date' in properties
        assert 'Created' in properties

    def test_build_properties_with_secondary_keyword(self, secondary_keyword):
        """Test property building for secondary keyword with relevance"""
        sync = KeywordsSync(notion_token="token", database_id="db")
        properties = sync._build_keyword_properties(
            keyword_data=secondary_keyword,
            keyword_type="Secondary",
            source_topic="PropTech Analysis"
        )

        assert properties['Keyword']['title'][0]['text']['content'] == 'Immobilien Software'
        assert properties['Relevance']['number'] == 0.8
        assert properties['Keyword Type']['select']['name'] == 'Secondary'

    def test_build_properties_with_long_tail_keyword(self, long_tail_keyword):
        """Test property building for long-tail keyword"""
        sync = KeywordsSync(notion_token="token", database_id="db")
        properties = sync._build_keyword_properties(
            keyword_data=long_tail_keyword,
            keyword_type="Long-tail",
            source_topic="PropTech Solutions"
        )

        assert properties['Keyword']['title'][0]['text']['content'] == 'beste PropTech Lösung für Hausverwaltung'
        assert properties['Competition']['select']['name'] == 'Low'
        assert properties['Difficulty']['number'] == 20
        assert properties['Keyword Type']['select']['name'] == 'Long-tail'

    def test_build_properties_normalizes_competition_levels(self):
        """Test competition level normalization to Notion select options"""
        sync = KeywordsSync(notion_token="token", database_id="db")

        for comp_level in ['Low', 'Medium', 'High', 'low', 'medium', 'high']:
            keyword = {
                'keyword': 'Test',
                'search_volume': '1K-10K',
                'competition': comp_level,
                'difficulty': 50,
                'intent': 'Informational'
            }

            properties = sync._build_keyword_properties(keyword, "Primary", "Test Topic")
            # Should be capitalized
            assert properties['Competition']['select']['name'] in ['Low', 'Medium', 'High']

    def test_build_properties_normalizes_intent(self):
        """Test intent normalization to Notion select options"""
        sync = KeywordsSync(notion_token="token", database_id="db")

        intents = ['informational', 'Informational', 'Commercial', 'Transactional', 'Navigational']

        for intent in intents:
            keyword = {
                'keyword': 'Test',
                'search_volume': '1K-10K',
                'competition': 'Medium',
                'difficulty': 50,
                'intent': intent
            }

            properties = sync._build_keyword_properties(keyword, "Primary", "Test Topic")
            # Should be capitalized
            assert properties['Intent']['select']['name'] in ['Informational', 'Commercial', 'Transactional', 'Navigational']


class TestSyncKeyword:
    """Test sync_keyword method"""

    @patch('src.notion_integration.keywords_sync.NotionClient')
    def test_sync_keyword_creates_new_page(self, mock_notion, primary_keyword, notion_response):
        """Test syncing keyword creates new Notion page"""
        mock_client = Mock()
        mock_client.create_page.return_value = notion_response
        mock_notion.return_value = mock_client

        sync = KeywordsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        result = sync.sync_keyword(
            keyword_data=primary_keyword,
            keyword_type="Primary",
            source_topic="PropTech Trends"
        )

        # Check create_page was called
        assert mock_client.create_page.called
        call_args = mock_client.create_page.call_args
        assert call_args[1]['parent_database_id'] == 'db_123'
        assert call_args[1]['retry'] is True

        # Check result
        assert result['id'] == 'notion_keyword_123'
        assert result['action'] == 'created'
        assert result['keyword'] == 'PropTech Deutschland'
        assert sync.total_synced == 1

    @patch('src.notion_integration.keywords_sync.NotionClient')
    def test_sync_keyword_without_database_id_raises_error(self, mock_notion, primary_keyword):
        """Test syncing without database_id raises error"""
        sync = KeywordsSync(notion_token="token")  # No database_id

        with pytest.raises(KeywordsSyncError, match="Database ID not set"):
            sync.sync_keyword(primary_keyword, "Primary", "Test Topic")

    @patch('src.notion_integration.keywords_sync.NotionClient')
    def test_sync_keyword_handles_notion_api_error(self, mock_notion, primary_keyword):
        """Test sync handles Notion API errors"""
        mock_client = Mock()
        mock_client.create_page.side_effect = Exception("Notion API error")
        mock_notion.return_value = mock_client

        sync = KeywordsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        with pytest.raises(KeywordsSyncError, match="Failed to sync keyword"):
            sync.sync_keyword(primary_keyword, "Primary", "Test Topic")

        assert sync.failed_syncs == 1


class TestSyncKeywordSet:
    """Test sync_keyword_set method"""

    @patch('src.notion_integration.keywords_sync.NotionClient')
    def test_sync_keyword_set_syncs_all_types(self, mock_notion, keyword_research_result, notion_response):
        """Test syncing complete keyword set (primary + secondary + long-tail)"""
        mock_client = Mock()
        mock_client.create_page.return_value = notion_response
        mock_notion.return_value = mock_client

        sync = KeywordsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        result = sync.sync_keyword_set(
            research_result=keyword_research_result,
            source_topic="PropTech Trends"
        )

        # Should sync: 1 primary + 2 secondary + 1 long-tail = 4 total
        assert result['total'] == 4
        assert result['primary'] == 1
        assert result['secondary'] == 2
        assert result['long_tail'] == 1
        assert sync.total_synced == 4

    @patch('src.notion_integration.keywords_sync.NotionClient')
    def test_sync_keyword_set_with_empty_result(self, mock_notion, notion_response):
        """Test syncing empty keyword set"""
        mock_client = Mock()
        mock_client.create_page.return_value = notion_response
        mock_notion.return_value = mock_client

        sync = KeywordsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        result = sync.sync_keyword_set(
            research_result={
                'primary_keyword': None,
                'secondary_keywords': [],
                'long_tail_keywords': []
            },
            source_topic="Test"
        )

        assert result['total'] == 0
        assert result['primary'] == 0
        assert result['secondary'] == 0
        assert result['long_tail'] == 0

    @patch('src.notion_integration.keywords_sync.NotionClient')
    def test_sync_keyword_set_skip_errors_continues_on_failure(self, mock_notion, keyword_research_result, notion_response):
        """Test keyword set sync with skip_errors=True continues after failures"""
        mock_client = Mock()
        # First call (primary) succeeds, second (secondary 1) fails, third (secondary 2) succeeds, fourth (long-tail) succeeds
        mock_client.create_page.side_effect = [
            notion_response,
            Exception("Error"),
            notion_response,
            notion_response
        ]
        mock_notion.return_value = mock_client

        sync = KeywordsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        result = sync.sync_keyword_set(
            research_result=keyword_research_result,
            source_topic="PropTech Trends",
            skip_errors=True
        )

        # Should have 3 successful syncs (primary + 1 secondary + long-tail)
        assert result['total'] == 3
        assert sync.total_synced == 3
        assert sync.failed_syncs == 1


class TestGetStatistics:
    """Test get_statistics method"""

    @patch('src.notion_integration.keywords_sync.NotionClient')
    def test_get_statistics_returns_correct_counts(self, mock_notion, primary_keyword, notion_response):
        """Test statistics tracking"""
        mock_client = Mock()
        mock_client.create_page.side_effect = [
            notion_response,
            Exception("Error"),
            notion_response
        ]
        mock_notion.return_value = mock_client

        sync = KeywordsSync(notion_token="token", database_id="db_123")
        sync.notion_client = mock_client

        # Sync 2 successfully, 1 fails
        try:
            sync.sync_keyword(primary_keyword, "Primary", "Topic 1")
            sync.sync_keyword(primary_keyword, "Primary", "Topic 2")
        except:
            pass

        try:
            sync.sync_keyword(primary_keyword, "Primary", "Topic 3")
        except:
            pass

        stats = sync.get_statistics()

        assert stats['total_synced'] == 2
        assert stats['failed_syncs'] == 1
        assert stats['success_rate'] == 2 / 3
