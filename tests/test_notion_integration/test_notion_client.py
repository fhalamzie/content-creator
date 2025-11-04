"""
Tests for notion_client.py

TDD approach: Write tests first, then implement.
Coverage target: 100% (critical path component)

Notion client wraps notion-client SDK with:
- Automatic rate limiting (2.5 req/sec)
- Error handling (rate limits, auth, network)
- CRUD operations for databases and pages
- Retry logic with exponential backoff
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from notion_client import APIResponseError
from src.notion_integration.notion_client import NotionClient, NotionError


@pytest.fixture
def mock_notion_sdk():
    """Create mock Notion SDK client"""
    mock = MagicMock()
    return mock


@pytest.fixture
def notion_client(mock_notion_sdk):
    """Create NotionClient with mocked SDK"""
    with patch('src.notion_integration.notion_client.Client', return_value=mock_notion_sdk):
        client = NotionClient(token="test_token")
        client._client = mock_notion_sdk  # Inject mock
        return client


class TestNotionClientInitialization:
    """Test Notion client initialization"""

    def test_creates_with_token(self):
        with patch('src.notion_integration.notion_client.Client') as mock_client_class:
            NotionClient(token="secret_token")
            mock_client_class.assert_called_once_with(auth="secret_token")

    def test_creates_with_custom_rate_limit(self):
        with patch('src.notion_integration.notion_client.Client'):
            client = NotionClient(token="test_token", rate_limit=5.0)
            assert client.rate_limiter.rate == 5.0

    def test_validates_token_not_empty(self):
        with pytest.raises(ValueError, match="Token cannot be empty"):
            NotionClient(token="")

    def test_validates_token_not_none(self):
        with pytest.raises(ValueError, match="Token cannot be empty"):
            NotionClient(token=None)


class TestDatabaseQueries:
    """Test database query operations"""

    def test_query_database_returns_results(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.databases.query.return_value = {
            "results": [
                {"id": "page-1", "properties": {"Title": {"title": [{"text": {"content": "Test"}}]}}},
                {"id": "page-2", "properties": {"Title": {"title": [{"text": {"content": "Test 2"}}]}}}
            ],
            "has_more": False
        }

        results = notion_client.query_database("db-123")

        assert len(results["results"]) == 2
        mock_notion_sdk.databases.query.assert_called_once_with(database_id="db-123")

    def test_query_database_with_filter(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.databases.query.return_value = {"results": [], "has_more": False}

        filter_obj = {"property": "Status", "select": {"equals": "Published"}}
        notion_client.query_database("db-123", filter=filter_obj)

        mock_notion_sdk.databases.query.assert_called_once_with(
            database_id="db-123",
            filter=filter_obj
        )

    def test_query_database_with_sorts(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.databases.query.return_value = {"results": [], "has_more": False}

        sorts = [{"property": "Created", "direction": "descending"}]
        notion_client.query_database("db-123", sorts=sorts)

        mock_notion_sdk.databases.query.assert_called_once_with(
            database_id="db-123",
            sorts=sorts
        )

    def test_query_database_respects_rate_limit(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.databases.query.return_value = {"results": [], "has_more": False}

        # Query multiple times and check rate limiter was used
        notion_client.query_database("db-123")
        notion_client.query_database("db-123")

        stats = notion_client.rate_limiter.get_stats()
        assert stats["total_requests"] == 2


class TestPageOperations:
    """Test page CRUD operations"""

    def test_create_page_in_database(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.pages.create.return_value = {
            "id": "page-new",
            "properties": {}
        }

        properties = {
            "Title": {"title": [{"text": {"content": "New Page"}}]},
            "Status": {"select": {"name": "Draft"}}
        }

        result = notion_client.create_page(parent_database_id="db-123", properties=properties)

        assert result["id"] == "page-new"
        mock_notion_sdk.pages.create.assert_called_once()

    def test_update_page_properties(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.pages.update.return_value = {
            "id": "page-123",
            "properties": {}
        }

        properties = {"Status": {"select": {"name": "Published"}}}
        result = notion_client.update_page(page_id="page-123", properties=properties)

        assert result["id"] == "page-123"
        mock_notion_sdk.pages.update.assert_called_once_with(
            page_id="page-123",
            properties=properties
        )

    def test_retrieve_page(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.pages.retrieve.return_value = {
            "id": "page-123",
            "properties": {"Title": {"title": [{"text": {"content": "Test Page"}}]}}
        }

        result = notion_client.retrieve_page(page_id="page-123")

        assert result["id"] == "page-123"
        mock_notion_sdk.pages.retrieve.assert_called_once_with(page_id="page-123")

    def test_archive_page(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.pages.update.return_value = {
            "id": "page-123",
            "archived": True
        }

        result = notion_client.archive_page(page_id="page-123")

        assert result["archived"] is True
        mock_notion_sdk.pages.update.assert_called_once_with(
            page_id="page-123",
            archived=True
        )


class TestBlockOperations:
    """Test block operations (content)"""

    def test_append_blocks_to_page(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.blocks.children.append.return_value = {
            "results": [{"id": "block-1"}, {"id": "block-2"}]
        }

        blocks = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Test"}}]}},
            {"type": "heading_1", "heading_1": {"rich_text": [{"text": {"content": "Header"}}]}}
        ]

        result = notion_client.append_blocks(block_id="page-123", children=blocks)

        assert len(result["results"]) == 2
        mock_notion_sdk.blocks.children.append.assert_called_once_with(
            block_id="page-123",
            children=blocks
        )

    def test_retrieve_block_children(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.blocks.children.list.return_value = {
            "results": [{"id": "block-1", "type": "paragraph"}]
        }

        result = notion_client.retrieve_block_children(block_id="page-123")

        assert len(result["results"]) == 1
        mock_notion_sdk.blocks.children.list.assert_called_once_with(block_id="page-123")


class TestErrorHandling:
    """Test error handling and retry logic"""

    def test_handles_rate_limit_error(self, notion_client, mock_notion_sdk):
        # Simulate rate limit error from Notion API
        error_response = Mock()
        error_response.status = 429
        error_response.json.return_value = {"message": "Rate limited"}

        api_error = APIResponseError(
            response=error_response,
            message="Rate limited",
            code="rate_limited"
        )
        api_error.status = 429  # Set status on error object
        mock_notion_sdk.databases.query.side_effect = api_error

        with pytest.raises(NotionError, match="Rate limited"):
            notion_client.query_database("db-123")

    def test_handles_auth_error(self, notion_client, mock_notion_sdk):
        error_response = Mock()
        error_response.status = 401
        error_response.json.return_value = {"message": "Unauthorized"}

        api_error = APIResponseError(
            response=error_response,
            message="Unauthorized",
            code="unauthorized"
        )
        api_error.status = 401
        mock_notion_sdk.databases.query.side_effect = api_error

        with pytest.raises(NotionError, match="Authentication failed"):
            notion_client.query_database("db-123")

    def test_handles_not_found_error(self, notion_client, mock_notion_sdk):
        error_response = Mock()
        error_response.status = 404
        error_response.json.return_value = {"message": "Not found"}

        api_error = APIResponseError(
            response=error_response,
            message="Not found",
            code="object_not_found"
        )
        api_error.status = 404
        mock_notion_sdk.databases.query.side_effect = api_error

        with pytest.raises(NotionError, match="Resource not found"):
            notion_client.query_database("db-123")

    def test_handles_generic_api_error(self, notion_client, mock_notion_sdk):
        error_response = Mock()
        error_response.status = 500
        error_response.json.return_value = {"message": "Internal error"}

        api_error = APIResponseError(
            response=error_response,
            message="Internal error",
            code="internal_error"
        )
        api_error.status = 500
        mock_notion_sdk.databases.query.side_effect = api_error

        with pytest.raises(NotionError, match="Notion API error"):
            notion_client.query_database("db-123")

    def test_retries_on_transient_errors(self, notion_client, mock_notion_sdk):
        # First call fails (500), second succeeds
        error_response = Mock()
        error_response.status = 500
        error_response.json.return_value = {"message": "Temporary error"}

        api_error = APIResponseError(response=error_response, message="Error", code="internal_error")
        api_error.status = 500

        mock_notion_sdk.databases.query.side_effect = [
            api_error,
            {"results": [], "has_more": False}
        ]

        # Should succeed after retry
        result = notion_client.query_database("db-123", retry=True, max_retries=2)
        assert result["results"] == []

    def test_gives_up_after_max_retries(self, notion_client, mock_notion_sdk):
        error_response = Mock()
        error_response.status = 500
        error_response.json.return_value = {"message": "Persistent error"}

        # Always fails
        api_error = APIResponseError(
            response=error_response,
            message="Error",
            code="internal_error"
        )
        api_error.status = 500
        mock_notion_sdk.databases.query.side_effect = api_error

        with pytest.raises(NotionError, match="Notion API error"):
            notion_client.query_database("db-123", retry=True, max_retries=2)


class TestDatabaseCreation:
    """Test database creation"""

    def test_create_database(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.databases.create.return_value = {
            "id": "db-new",
            "title": [{"text": {"content": "New Database"}}]
        }

        properties = {
            "Title": {"title": {}},
            "Status": {"select": {"options": [{"name": "Draft"}, {"name": "Published"}]}}
        }

        result = notion_client.create_database(
            parent_page_id="page-123",
            title="New Database",
            properties=properties
        )

        assert result["id"] == "db-new"
        mock_notion_sdk.databases.create.assert_called_once()


class TestStatistics:
    """Test client statistics"""

    def test_tracks_api_call_statistics(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.databases.query.return_value = {"results": [], "has_more": False}
        mock_notion_sdk.pages.retrieve.return_value = {"id": "page-123"}

        notion_client.query_database("db-123")
        notion_client.retrieve_page("page-123")

        stats = notion_client.get_stats()
        assert stats["total_api_calls"] == 2
        assert stats["rate_limiter"]["total_requests"] == 2

    def test_reset_statistics(self, notion_client, mock_notion_sdk):
        mock_notion_sdk.databases.query.return_value = {"results": [], "has_more": False}

        notion_client.query_database("db-123")
        notion_client.reset_stats()

        stats = notion_client.get_stats()
        assert stats["total_api_calls"] == 0
