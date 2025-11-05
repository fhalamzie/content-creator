"""
Tests for TavilyBackend

Tests Tavily API integration with focus on graceful degradation and error handling.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.research.backends.tavily_backend import TavilyBackend
from src.research.backends.base import BackendHealth, SearchHorizon, SearchResult
from src.research.backends.exceptions import (
    BackendUnavailableError,
    AuthenticationError
)


class TestTavilyBackendInit:
    """Test TavilyBackend initialization"""

    def test_init_missing_tavily_library(self):
        """Should raise BackendUnavailableError if tavily-python not installed"""
        with patch('src.research.backends.tavily_backend.TavilyClient', None):
            with pytest.raises(BackendUnavailableError) as exc_info:
                TavilyBackend()

            assert "tavily-python not installed" in str(exc_info.value)
            assert exc_info.value.backend_name == "tavily"

    def test_init_missing_api_key(self):
        """Should raise AuthenticationError if API key not found"""
        mock_client_class = MagicMock()

        with patch('src.research.backends.tavily_backend.TavilyClient', mock_client_class):
            with patch.object(TavilyBackend, '_load_api_key', return_value=None):
                with pytest.raises(AuthenticationError) as exc_info:
                    TavilyBackend()

                assert "TAVILY_API_KEY not found" in str(exc_info.value)
                assert exc_info.value.backend_name == "tavily"

    def test_init_with_api_key(self):
        """Should initialize successfully with valid API key"""
        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch('src.research.backends.tavily_backend.TavilyClient', mock_client_class):
            backend = TavilyBackend(api_key="test_key_123")

            assert backend.backend_name == "tavily"
            assert backend.api_key == "test_key_123"
            assert backend.client is not None
            mock_client_class.assert_called_once_with(api_key="test_key_123")

    def test_init_loads_from_env(self):
        """Should load API key from environment"""
        mock_client_class = MagicMock()

        with patch('src.research.backends.tavily_backend.TavilyClient', mock_client_class):
            with patch('src.research.backends.tavily_backend.os.getenv', return_value="env_key_456"):
                backend = TavilyBackend()

                assert backend.api_key == "env_key_456"

    def test_init_loads_from_file(self):
        """Should load API key from /home/envs/tavily.env"""
        mock_client_class = MagicMock()

        with patch('src.research.backends.tavily_backend.TavilyClient', mock_client_class):
            with patch('src.research.backends.tavily_backend.os.getenv', return_value=None):
                with patch('src.research.backends.tavily_backend.os.path.exists', return_value=True):
                    mock_file_content = "TAVILY_API_KEY=file_key_789\n"
                    with patch('builtins.open', create=True) as mock_open:
                        mock_open.return_value.__enter__.return_value.readlines.return_value = [mock_file_content]
                        mock_open.return_value.__enter__.return_value.__iter__ = lambda self: iter([mock_file_content])

                        backend = TavilyBackend()

                        assert backend.api_key == "file_key_789"


class TestTavilyBackendProperties:
    """Test TavilyBackend properties"""

    @pytest.fixture
    def backend(self):
        """Create backend instance"""
        mock_client_class = MagicMock()
        with patch('src.research.backends.tavily_backend.TavilyClient', mock_client_class):
            return TavilyBackend(api_key="test_key")

    def test_horizon_property(self, backend):
        """Should return DEPTH horizon"""
        assert backend.horizon == SearchHorizon.DEPTH

    def test_cost_per_query_property(self, backend):
        """Should return correct cost per query"""
        assert backend.cost_per_query == 0.02

    def test_supports_citations_property(self, backend):
        """Should support citations"""
        assert backend.supports_citations is True


class TestTavilyBackendSearch:
    """Test TavilyBackend search functionality"""

    @pytest.fixture
    def backend(self):
        """Create backend instance with mocked client"""
        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch('src.research.backends.tavily_backend.TavilyClient', mock_client_class):
            backend = TavilyBackend(api_key="test_key")
            backend.client = mock_client
            return backend

    @pytest.mark.asyncio
    async def test_search_success(self, backend):
        """Should return search results on success"""
        # Mock Tavily API response
        backend.client.search.return_value = {
            'results': [
                {
                    'url': 'https://example.com/article1',
                    'title': 'PropTech Trends 2025',
                    'content': 'AI is revolutionizing real estate...',
                    'score': 0.95,
                    'published_date': '2025-01-01'
                },
                {
                    'url': 'https://example.com/article2',
                    'title': 'Smart Buildings Overview',
                    'content': 'IoT devices are everywhere...',
                    'score': 0.87
                }
            ]
        }

        results = await backend.search("PropTech trends", max_results=10)

        assert len(results) == 2
        assert results[0]['url'] == 'https://example.com/article1'
        assert results[0]['title'] == 'PropTech Trends 2025'
        assert results[0]['backend'] == 'tavily'
        assert results[0]['score'] == 0.95
        assert results[1]['url'] == 'https://example.com/article2'

    @pytest.mark.asyncio
    async def test_search_with_options(self, backend):
        """Should pass options to Tavily API"""
        backend.client.search.return_value = {'results': []}

        await backend.search(
            "test query",
            max_results=5,
            search_depth="advanced",
            include_domains=["example.com"],
            exclude_domains=["spam.com"]
        )

        backend.client.search.assert_called_once_with(
            query="test query",
            search_depth="advanced",
            max_results=5,
            include_domains=["example.com"],
            exclude_domains=["spam.com"]
        )

    @pytest.mark.asyncio
    async def test_search_empty_results(self, backend):
        """Should handle empty results gracefully"""
        backend.client.search.return_value = {'results': []}

        results = await backend.search("nonexistent topic")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_api_error_graceful_degradation(self, backend):
        """Should return empty list on API error (graceful degradation)"""
        backend.client.search.side_effect = Exception("API Error: Rate limit exceeded")

        results = await backend.search("test query")

        assert results == []  # Graceful: returns empty, doesn't raise

    @pytest.mark.asyncio
    async def test_search_network_error_graceful_degradation(self, backend):
        """Should return empty list on network error (graceful degradation)"""
        backend.client.search.side_effect = ConnectionError("Network unreachable")

        results = await backend.search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_malformed_response_graceful_degradation(self, backend):
        """Should handle malformed API response gracefully"""
        backend.client.search.return_value = {'wrong_key': 'data'}

        results = await backend.search("test query")

        # Should handle missing 'results' key gracefully
        assert results == []

    @pytest.mark.asyncio
    async def test_search_partial_data(self, backend):
        """Should handle results with missing fields"""
        backend.client.search.return_value = {
            'results': [
                {
                    'url': 'https://example.com',
                    'title': 'Test',
                    'content': 'Content'
                    # Missing score, published_date
                }
            ]
        }

        results = await backend.search("test")

        assert len(results) == 1
        assert results[0]['url'] == 'https://example.com'
        assert results[0].get('score') is None or results[0].get('score') == 0.0


class TestTavilyBackendHealthCheck:
    """Test TavilyBackend health check"""

    @pytest.fixture
    def backend(self):
        """Create backend instance"""
        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch('src.research.backends.tavily_backend.TavilyClient', mock_client_class):
            backend = TavilyBackend(api_key="test_key")
            backend.client = mock_client
            return backend

    @pytest.mark.asyncio
    async def test_health_check_success(self, backend):
        """Should return SUCCESS when backend operational"""
        backend.client.search.return_value = {
            'results': [{'url': 'test', 'title': 'test', 'content': 'test'}]
        }

        health = await backend.health_check()

        assert health == BackendHealth.SUCCESS

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, backend):
        """Should return DEGRADED when no results but no error"""
        backend.client.search.return_value = {'results': []}

        health = await backend.health_check()

        assert health == BackendHealth.DEGRADED

    @pytest.mark.asyncio
    async def test_health_check_degraded_on_error(self, backend):
        """Should return DEGRADED when search fails gracefully (returns empty)"""
        # Due to graceful degradation, search() returns [] instead of raising
        backend.client.search.side_effect = Exception("Connection failed")

        health = await backend.health_check()

        # Graceful degradation: search returns [], health check sees DEGRADED
        assert health == BackendHealth.DEGRADED


class TestTavilyBackendRepr:
    """Test TavilyBackend string representation"""

    def test_repr(self):
        """Should return informative string representation"""
        mock_client_class = MagicMock()

        with patch('src.research.backends.tavily_backend.TavilyClient', mock_client_class):
            backend = TavilyBackend(api_key="test_key")

            repr_str = repr(backend)

            assert "TavilyBackend" in repr_str
            assert "name=tavily" in repr_str
            assert "horizon=depth" in repr_str
            assert "cost=$0.02/query" in repr_str
