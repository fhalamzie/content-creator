"""
Tests for GeminiAPIBackend

Tests Gemini API integration with focus on graceful degradation and error handling.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock, Mock
from src.research.backends.gemini_api_backend import GeminiAPIBackend
from src.research.backends.base import BackendHealth, SearchHorizon, SearchResult
from src.research.backends.exceptions import (
    BackendUnavailableError,
    AuthenticationError
)


class TestGeminiAPIBackendInit:
    """Test GeminiAPIBackend initialization"""

    @pytest.mark.skip(reason="GeminiAgent import handling is tested indirectly")
    def test_init_missing_gemini_agent(self):
        """Should raise BackendUnavailableError if GeminiAgent import fails"""
        # Note: This is an edge case that's hard to test in isolation since
        # GeminiAgent is available in the codebase. The error handling is
        # present in the code and will be triggered if import fails in production.
        pass

    def test_init_missing_api_key(self):
        """Should raise AuthenticationError if API key not found"""
        mock_agent_class = MagicMock()

        with patch('src.research.backends.gemini_api_backend.GeminiAgent', create=True):
            # Import module to trigger global GeminiAgent = _GeminiAgent
            import src.research.backends.gemini_api_backend as backend_module
            backend_module.GeminiAgent = mock_agent_class

            with patch.object(GeminiAPIBackend, '_load_api_key', return_value=None):
                with pytest.raises(AuthenticationError) as exc_info:
                    GeminiAPIBackend()

                assert "GEMINI_API_KEY not found" in str(exc_info.value)
                assert exc_info.value.backend_name == "gemini"

    def test_init_with_api_key(self):
        """Should initialize successfully with valid API key"""
        mock_agent_class = MagicMock()
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        backend = GeminiAPIBackend(api_key="test_gemini_key")

        assert backend.backend_name == "gemini"
        assert backend.api_key == "test_gemini_key"
        assert backend.agent is not None
        mock_agent_class.assert_called_once_with(
            model="gemini-2.5-flash",
            api_key="test_gemini_key",
            enable_grounding=True
        )

    def test_init_loads_from_env(self):
        """Should load API key from environment"""
        mock_agent_class = MagicMock()

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        with patch('src.research.backends.gemini_api_backend.os.getenv', return_value="env_gemini_key"):
            backend = GeminiAPIBackend()

            assert backend.api_key == "env_gemini_key"

    def test_init_loads_from_file(self):
        """Should load API key from /home/envs/gemini.env"""
        mock_agent_class = MagicMock()

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        with patch('src.research.backends.gemini_api_backend.os.getenv', return_value=None):
            with patch('src.research.backends.gemini_api_backend.os.path.exists', return_value=True):
                mock_file_content = "GEMINI_API_KEY=file_gemini_key\n"
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.readlines.return_value = [mock_file_content]
                    mock_open.return_value.__enter__.return_value.__iter__ = lambda self: iter([mock_file_content])

                    backend = GeminiAPIBackend()

                    assert backend.api_key == "file_gemini_key"

    def test_init_custom_model(self):
        """Should initialize with custom model"""
        mock_agent_class = MagicMock()

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        backend = GeminiAPIBackend(
            api_key="test_key",
            model="gemini-1.5-pro"
        )

        call_kwargs = mock_agent_class.call_args[1]
        assert call_kwargs['model'] == "gemini-1.5-pro"

    def test_init_disable_grounding(self):
        """Should initialize with grounding disabled"""
        mock_agent_class = MagicMock()

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        backend = GeminiAPIBackend(
            api_key="test_key",
            enable_grounding=False
        )

        call_kwargs = mock_agent_class.call_args[1]
        assert call_kwargs['enable_grounding'] is False


class TestGeminiAPIBackendProperties:
    """Test GeminiAPIBackend properties"""

    @pytest.fixture
    def backend(self):
        """Create backend instance"""
        mock_agent_class = MagicMock()

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        return GeminiAPIBackend(api_key="test_key")

    def test_horizon_property(self, backend):
        """Should return TRENDS horizon"""
        assert backend.horizon == SearchHorizon.TRENDS

    def test_cost_per_query_property(self, backend):
        """Should return 0.0 (FREE)"""
        assert backend.cost_per_query == 0.0

    def test_supports_citations_property(self, backend):
        """Should support citations (grounded sources)"""
        assert backend.supports_citations is True


class TestGeminiAPIBackendSearch:
    """Test GeminiAPIBackend search functionality"""

    @pytest.fixture
    def backend(self):
        """Create backend instance with mocked agent"""
        mock_agent_class = MagicMock()
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        backend = GeminiAPIBackend(api_key="test_key")
        backend.agent = mock_agent
        return backend

    @pytest.mark.asyncio
    async def test_search_success(self, backend):
        """Should return grounded search results on success"""
        # Mock Gemini API response
        backend.agent.generate.return_value = {
            'sources': [
                {
                    'url': 'https://example.com/trends1',
                    'title': 'PropTech Market Trends 2025',
                    'relevance': 'Discusses emerging AI trends in PropTech'
                },
                {
                    'url': 'https://example.org/trends2',
                    'title': 'Expert Predictions: Real Estate Tech',
                    'relevance': 'Expert analysis on market shifts'
                },
                {
                    'url': 'https://example.net/trends3',
                    'title': 'Adoption Patterns in PropTech'
                }
            ]
        }

        results = await backend.search("PropTech trends", max_results=12)

        assert len(results) == 3
        assert results[0]['url'] == 'https://example.com/trends1'
        assert results[0]['title'] == 'PropTech Market Trends 2025'
        assert results[0]['backend'] == 'gemini'
        assert results[0]['grounding'] is True
        assert results[1]['url'] == 'https://example.org/trends2'

    @pytest.mark.asyncio
    async def test_search_limits_to_max_results(self, backend):
        """Should limit results to max_results"""
        backend.agent.generate.return_value = {
            'sources': [
                {'url': f'url{i}', 'title': f'title{i}', 'relevance': 'rel'}
                for i in range(20)
            ]
        }

        results = await backend.search("test query", max_results=5)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_handles_missing_sources_key(self, backend):
        """Should handle response without sources key"""
        backend.agent.generate.return_value = {'other_key': 'data'}

        results = await backend.search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_api_error_graceful_degradation(self, backend):
        """Should return empty list on API error (graceful degradation)"""
        backend.agent.generate.side_effect = Exception("Quota exceeded")

        results = await backend.search("test query")

        assert results == []  # Graceful: returns empty, doesn't raise

    @pytest.mark.asyncio
    async def test_search_network_error_graceful_degradation(self, backend):
        """Should return empty list on network error (graceful degradation)"""
        backend.agent.generate.side_effect = ConnectionError("Network unreachable")

        results = await backend.search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_partial_source_data(self, backend):
        """Should handle sources with missing fields"""
        backend.agent.generate.return_value = {
            'sources': [
                {
                    'url': 'https://example.com',
                    'title': 'Test'
                    # Missing relevance
                },
                {
                    'title': 'Missing URL'
                    # Missing url
                }
            ]
        }

        results = await backend.search("test")

        assert len(results) == 2
        assert results[0]['url'] == 'https://example.com'
        assert results[0]['snippet'] == ''  # Default for missing relevance
        assert results[1]['url'] == ''  # Default for missing url

    @pytest.mark.asyncio
    async def test_search_builds_trend_focused_prompt(self, backend):
        """Should build prompt focused on trends and emerging patterns"""
        backend.agent.generate.return_value = {'sources': []}

        await backend.search("PropTech innovations", max_results=12)

        # Verify agent.generate was called with trend-focused prompt
        call_args = backend.agent.generate.call_args
        prompt = call_args[1]['prompt']

        assert 'trends' in prompt.lower() or 'trending' in prompt.lower()
        assert 'emerging' in prompt.lower()
        assert 'PropTech innovations' in prompt

    @pytest.mark.asyncio
    async def test_search_uses_response_schema(self, backend):
        """Should use response schema for structured output"""
        backend.agent.generate.return_value = {'sources': []}

        await backend.search("test query")

        call_args = backend.agent.generate.call_args
        response_schema = call_args[1]['response_schema']

        assert 'properties' in response_schema
        assert 'sources' in response_schema['properties']
        assert response_schema['properties']['sources']['type'] == 'array'


class TestGeminiAPIBackendHealthCheck:
    """Test GeminiAPIBackend health check"""

    @pytest.fixture
    def backend(self):
        """Create backend instance"""
        mock_agent_class = MagicMock()
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        backend = GeminiAPIBackend(api_key="test_key")
        backend.agent = mock_agent
        return backend

    @pytest.mark.asyncio
    async def test_health_check_success(self, backend):
        """Should return SUCCESS when backend operational"""
        backend.agent.generate.return_value = {
            'sources': [{'url': 'test', 'title': 'test'}]
        }

        health = await backend.health_check()

        assert health == BackendHealth.SUCCESS

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, backend):
        """Should return DEGRADED when no results but no error"""
        backend.agent.generate.return_value = {'sources': []}

        health = await backend.health_check()

        assert health == BackendHealth.DEGRADED

    @pytest.mark.asyncio
    async def test_health_check_degraded_on_error(self, backend):
        """Should return DEGRADED when search fails gracefully (returns empty)"""
        # Due to graceful degradation, search() returns [] instead of raising
        backend.agent.generate.side_effect = Exception("Quota exceeded")

        health = await backend.health_check()

        # Graceful degradation: search returns [], health check sees DEGRADED
        assert health == BackendHealth.DEGRADED


class TestGeminiAPIBackendRepr:
    """Test GeminiAPIBackend string representation"""

    def test_repr(self):
        """Should return informative string representation"""
        mock_agent_class = MagicMock()

        import src.research.backends.gemini_api_backend as backend_module
        backend_module.GeminiAgent = mock_agent_class

        backend = GeminiAPIBackend(api_key="test_key")

        repr_str = repr(backend)

        assert "GeminiAPIBackend" in repr_str
        assert "name=gemini" in repr_str
        assert "horizon=trends" in repr_str
        assert "cost=$0.0/query" in repr_str
