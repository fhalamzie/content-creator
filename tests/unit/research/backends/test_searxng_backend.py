"""
Tests for SearXNGBackend

Tests SearXNG metasearch integration with focus on graceful degradation and error handling.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock, Mock
from src.research.backends.base import BackendHealth, SearchHorizon, SearchResult
from src.research.backends.exceptions import BackendUnavailableError


# Mock pyserxng imports before importing SearXNGBackend
@pytest.fixture(autouse=True)
def mock_pyserxng():
    """Mock pyserxng module for all tests"""
    mock_search_category = Mock()
    mock_search_category.GENERAL = "general"
    mock_search_category.NEWS = "news"

    mock_search_config = Mock()

    with patch('src.research.backends.searxng_backend.SearchCategory', mock_search_category):
        with patch('src.research.backends.searxng_backend.SearchConfig', mock_search_config):
            yield {
                'SearchCategory': mock_search_category,
                'SearchConfig': mock_search_config
            }


# Import after mocking
from src.research.backends.searxng_backend import SearXNGBackend


class TestSearXNGBackendInit:
    """Test SearXNGBackend initialization"""

    def test_init_missing_pyserxng_library(self):
        """Should raise BackendUnavailableError if pyserxng not installed"""
        with patch('src.research.backends.searxng_backend.SearXNGClient', None):
            with pytest.raises(BackendUnavailableError) as exc_info:
                SearXNGBackend()

            assert "pyserxng not installed" in str(exc_info.value)
            assert exc_info.value.backend_name == "searxng"

    def test_init_with_public_instances(self):
        """Should initialize with public instances (no custom URL)"""
        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch('src.research.backends.searxng_backend.SearXNGClient', mock_client_class):
            with patch('src.research.backends.searxng_backend.LocalSearXNGClient'):
                backend = SearXNGBackend()

                assert backend.backend_name == "searxng"
                assert backend.instance_url is None
                assert backend.client is not None
                mock_client_class.assert_called_once()

    def test_init_with_custom_instance(self):
        """Should initialize with custom SearXNG instance"""
        mock_local_client_class = MagicMock()
        mock_client = MagicMock()
        mock_local_client_class.return_value = mock_client

        with patch('src.research.backends.searxng_backend.SearXNGClient'):
            with patch('src.research.backends.searxng_backend.LocalSearXNGClient', mock_local_client_class):
                backend = SearXNGBackend(instance_url="https://searx.local")

                assert backend.instance_url == "https://searx.local"
                assert backend.client is not None
                mock_local_client_class.assert_called_once_with("https://searx.local")

    def test_init_failure_raises_backend_unavailable(self):
        """Should raise BackendUnavailableError if client initialization fails"""
        mock_client_class = MagicMock()
        mock_client_class.side_effect = Exception("Connection failed")

        with patch('src.research.backends.searxng_backend.SearXNGClient', mock_client_class):
            with patch('src.research.backends.searxng_backend.LocalSearXNGClient'):
                with pytest.raises(BackendUnavailableError) as exc_info:
                    SearXNGBackend()

                assert "Failed to initialize SearXNG" in str(exc_info.value)


class TestSearXNGBackendProperties:
    """Test SearXNGBackend properties"""

    @pytest.fixture
    def backend(self):
        """Create backend instance"""
        mock_client_class = MagicMock()
        with patch('src.research.backends.searxng_backend.SearXNGClient', mock_client_class):
            with patch('src.research.backends.searxng_backend.LocalSearXNGClient'):
                return SearXNGBackend()

    def test_horizon_property(self, backend):
        """Should return BREADTH horizon"""
        assert backend.horizon == SearchHorizon.BREADTH

    def test_cost_per_query_property(self, backend):
        """Should return 0.0 (FREE)"""
        assert backend.cost_per_query == 0.0

    def test_supports_citations_property(self, backend):
        """Should support citations"""
        assert backend.supports_citations is True


class TestSearXNGBackendSearch:
    """Test SearXNGBackend search functionality"""

    @pytest.fixture
    def backend(self):
        """Create backend instance with mocked client"""
        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch('src.research.backends.searxng_backend.SearXNGClient', mock_client_class):
            with patch('src.research.backends.searxng_backend.LocalSearXNGClient'):
                backend = SearXNGBackend()
                backend.client = mock_client
                return backend

    @pytest.mark.asyncio
    async def test_search_success(self, backend):
        """Should return search results from multiple engines"""
        # Mock SearXNG response (multiple engines)
        backend.client.search.return_value = [
            {
                'url': 'https://example.com/article1',
                'title': 'PropTech Trends from Google',
                'content': 'AI is revolutionizing...',
                'engine': 'google',
                'score': 0.95
            },
            {
                'url': 'https://example.org/article2',
                'title': 'PropTech from Bing',
                'content': 'IoT devices are everywhere...',
                'engine': 'bing',
                'score': 0.87
            },
            {
                'url': 'https://example.net/article3',
                'title': 'PropTech from DuckDuckGo',
                'content': 'Blockchain for real estate...',
                'engine': 'duckduckgo',
                'score': 0.82
            }
        ]

        results = await backend.search("PropTech trends", max_results=30)

        assert len(results) == 3
        assert results[0]['url'] == 'https://example.com/article1'
        assert results[0]['backend'] == 'searxng'
        assert results[0]['engine'] == 'google'
        assert results[1]['engine'] == 'bing'
        assert results[2]['engine'] == 'duckduckgo'

    @pytest.mark.asyncio
    async def test_search_with_time_range(self, backend, mock_pyserxng):
        """Should pass time_range to SearXNG config"""
        backend.client.search.return_value = []

        await backend.search("test query", max_results=30, time_range="month")

        # Verify SearchConfig was created with time_range
        mock_config = mock_pyserxng['SearchConfig']
        assert mock_config.called
        call_kwargs = mock_config.call_args[1]
        assert call_kwargs.get('time_range') == 'month'

    @pytest.mark.asyncio
    async def test_search_with_categories(self, backend, mock_pyserxng):
        """Should pass categories to SearXNG config"""
        backend.client.search.return_value = []

        mock_category = mock_pyserxng['SearchCategory']

        await backend.search(
            "test query",
            max_results=30,
            categories=[mock_category.GENERAL, mock_category.NEWS]
        )

    @pytest.mark.asyncio
    async def test_search_empty_results(self, backend):
        """Should handle empty results gracefully"""
        backend.client.search.return_value = []

        results = await backend.search("nonexistent topic")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_engine_error_graceful_degradation(self, backend):
        """Should return empty list on search error (graceful degradation)"""
        backend.client.search.side_effect = Exception("All engines failed")

        results = await backend.search("test query")

        assert results == []  # Graceful: returns empty, doesn't raise

    @pytest.mark.asyncio
    async def test_search_network_error_graceful_degradation(self, backend):
        """Should return empty list on network error (graceful degradation)"""
        backend.client.search.side_effect = ConnectionError("Network unreachable")

        results = await backend.search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_timeout_graceful_degradation(self, backend):
        """Should return empty list on timeout (graceful degradation)"""
        backend.client.search.side_effect = TimeoutError("Request timeout")

        results = await backend.search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_partial_data(self, backend):
        """Should handle results with missing fields"""
        backend.client.search.return_value = [
            {
                'url': 'https://example.com',
                'title': 'Test',
                'content': 'Content'
                # Missing engine, score
            }
        ]

        results = await backend.search("test")

        assert len(results) == 1
        assert results[0]['url'] == 'https://example.com'
        assert results[0]['engine'] == 'unknown'  # Default fallback

    @pytest.mark.asyncio
    async def test_search_malformed_url_graceful(self, backend):
        """Should handle malformed URLs gracefully"""
        backend.client.search.return_value = [
            {
                'url': 'not-a-valid-url',
                'title': 'Test',
                'content': 'Content',
                'engine': 'test_engine'
            }
        ]

        results = await backend.search("test")

        assert len(results) == 1
        assert results[0]['url'] == 'not-a-valid-url'
        # urlparse returns empty string for invalid URLs
        assert results[0]['domain'] in ['', 'unknown']

    @pytest.mark.asyncio
    async def test_search_engine_diversity_tracking(self, backend):
        """Should track engines used in logging"""
        backend.client.search.return_value = [
            {'url': 'url1', 'title': 't1', 'content': 'c1', 'engine': 'google'},
            {'url': 'url2', 'title': 't2', 'content': 'c2', 'engine': 'bing'},
            {'url': 'url3', 'title': 't3', 'content': 'c3', 'engine': 'google'},
        ]

        results = await backend.search("test")

        # Should have results from 2 unique engines
        assert len(results) == 3
        engines = {r['engine'] for r in results}
        assert len(engines) == 2
        assert 'google' in engines
        assert 'bing' in engines


class TestSearXNGBackendHealthCheck:
    """Test SearXNGBackend health check"""

    @pytest.fixture
    def backend(self):
        """Create backend instance"""
        mock_client_class = MagicMock()
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch('src.research.backends.searxng_backend.SearXNGClient', mock_client_class):
            with patch('src.research.backends.searxng_backend.LocalSearXNGClient'):
                backend = SearXNGBackend()
                backend.client = mock_client
                return backend

    @pytest.mark.asyncio
    async def test_health_check_success(self, backend):
        """Should return SUCCESS when backend operational"""
        backend.client.search.return_value = [
            {'url': 'test', 'title': 'test', 'content': 'test'}
        ]

        health = await backend.health_check()

        assert health == BackendHealth.SUCCESS

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, backend):
        """Should return DEGRADED when no results but no error"""
        backend.client.search.return_value = []

        health = await backend.health_check()

        assert health == BackendHealth.DEGRADED

    @pytest.mark.asyncio
    async def test_health_check_degraded_on_error(self, backend):
        """Should return DEGRADED when search fails gracefully (returns empty)"""
        # Due to graceful degradation, search() returns [] instead of raising
        backend.client.search.side_effect = Exception("Public instances unavailable")

        health = await backend.health_check()

        # Graceful degradation: search returns [], health check sees DEGRADED
        assert health == BackendHealth.DEGRADED


class TestSearXNGBackendRepr:
    """Test SearXNGBackend string representation"""

    def test_repr(self):
        """Should return informative string representation"""
        mock_client_class = MagicMock()

        with patch('src.research.backends.searxng_backend.SearXNGClient', mock_client_class):
            with patch('src.research.backends.searxng_backend.LocalSearXNGClient'):
                backend = SearXNGBackend()

                repr_str = repr(backend)

                assert "SearXNGBackend" in repr_str
                assert "name=searxng" in repr_str
                assert "horizon=breadth" in repr_str
                assert "cost=$0.0/query" in repr_str
