"""
Integration Tests for Multi-Backend Orchestrator

Tests the DeepResearcher orchestrator with all 3 backends working together.
Verifies graceful degradation, parallel execution, and error handling.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.research.deep_researcher_refactored import DeepResearcher, DeepResearchError
from src.research.backends.base import BackendHealth


class TestOrchestratorAllBackendsSucceed:
    """Test scenario: All backends return results successfully"""

    @pytest.mark.asyncio
    async def test_all_backends_succeed(self):
        """Should merge sources from all 3 backends"""
        # Mock all backends
        mock_tavily = MagicMock()
        mock_tavily.search = AsyncMock(return_value=[
            {'url': 'https://tavily.com/source1', 'title': 'Tavily 1', 'snippet': 'Academic source', 'backend': 'tavily'},
            {'url': 'https://tavily.com/source2', 'title': 'Tavily 2', 'snippet': 'Authoritative', 'backend': 'tavily'}
        ])

        mock_searxng = MagicMock()
        mock_searxng.search = AsyncMock(return_value=[
            {'url': 'https://searxng.com/source1', 'title': 'SearXNG 1', 'snippet': 'Recent content', 'backend': 'searxng'},
            {'url': 'https://searxng.com/source2', 'title': 'SearXNG 2', 'snippet': 'Diverse', 'backend': 'searxng'},
            {'url': 'https://searxng.com/source3', 'title': 'SearXNG 3', 'snippet': 'Wide coverage', 'backend': 'searxng'}
        ])

        mock_gemini = MagicMock()
        mock_gemini.search = AsyncMock(return_value=[
            {'url': 'https://gemini.com/source1', 'title': 'Gemini 1', 'snippet': 'Trend analysis', 'backend': 'gemini'},
            {'url': 'https://gemini.com/source2', 'title': 'Gemini 2', 'snippet': 'Emerging patterns', 'backend': 'gemini'}
        ])

        # Patch backend initialization
        with patch('src.research.deep_researcher_refactored.TavilyBackend', return_value=mock_tavily):
            with patch('src.research.deep_researcher_refactored.SearXNGBackend', return_value=mock_searxng):
                with patch('src.research.deep_researcher_refactored.GeminiAPIBackend', return_value=mock_gemini):
                    researcher = DeepResearcher()

                    config = {'domain': 'SaaS', 'market': 'Germany'}
                    result = await researcher.research_topic("PropTech trends", config)

                    # Verify all backends were called
                    assert mock_tavily.search.called
                    assert mock_searxng.search.called
                    assert mock_gemini.search.called

                    # Verify sources merged (2 + 3 + 2 = 7 unique sources)
                    assert len(result['sources']) == 7

                    # Verify backend stats
                    assert 'tavily' in result['backend_stats']['successful']
                    assert 'searxng' in result['backend_stats']['successful']
                    assert 'gemini' in result['backend_stats']['successful']
                    assert len(result['backend_stats']['failed']) == 0

                    # Verify quality score (all backends succeed = high score)
                    assert result['quality_score'] >= 70  # Should be high with all backends


class TestOrchestratorOneBackendFails:
    """Test scenario: One backend fails, others continue (graceful degradation)"""

    @pytest.mark.asyncio
    async def test_one_backend_fails_graceful_continuation(self):
        """Should continue with remaining backends when one fails"""
        # Mock backends (Tavily fails, others succeed)
        mock_tavily = MagicMock()
        mock_tavily.search = AsyncMock(return_value=[])  # Graceful failure returns empty

        mock_searxng = MagicMock()
        mock_searxng.search = AsyncMock(return_value=[
            {'url': 'https://searxng.com/source1', 'title': 'SearXNG 1', 'snippet': 'Content', 'backend': 'searxng'},
            {'url': 'https://searxng.com/source2', 'title': 'SearXNG 2', 'snippet': 'Content', 'backend': 'searxng'}
        ])

        mock_gemini = MagicMock()
        mock_gemini.search = AsyncMock(return_value=[
            {'url': 'https://gemini.com/source1', 'title': 'Gemini 1', 'snippet': 'Content', 'backend': 'gemini'}
        ])

        with patch('src.research.deep_researcher_refactored.TavilyBackend', return_value=mock_tavily):
            with patch('src.research.deep_researcher_refactored.SearXNGBackend', return_value=mock_searxng):
                with patch('src.research.deep_researcher_refactored.GeminiAPIBackend', return_value=mock_gemini):
                    researcher = DeepResearcher()

                    config = {'domain': 'SaaS'}
                    result = await researcher.research_topic("Test topic", config)

                    # Verify research succeeded despite one backend failing
                    assert len(result['sources']) == 3  # Only from searxng + gemini

                    # Verify backend stats show failure
                    assert 'searxng' in result['backend_stats']['successful']
                    assert 'gemini' in result['backend_stats']['successful']
                    # tavily returned empty, so it's technically successful but with 0 sources

                    # Quality score should be lower but still acceptable
                    assert 50 <= result['quality_score'] < 80


class TestOrchestratorTwoBackendsFail:
    """Test scenario: Two backends fail, minimum threshold met"""

    @pytest.mark.asyncio
    async def test_two_backends_fail_minimum_threshold(self):
        """Should succeed with minimum one backend working"""
        # Mock backends (only Gemini succeeds)
        mock_tavily = MagicMock()
        mock_tavily.search = AsyncMock(return_value=[])

        mock_searxng = MagicMock()
        mock_searxng.search = AsyncMock(return_value=[])

        mock_gemini = MagicMock()
        mock_gemini.search = AsyncMock(return_value=[
            {'url': 'https://gemini.com/source1', 'title': 'Gemini 1', 'snippet': 'Only source', 'backend': 'gemini'},
            {'url': 'https://gemini.com/source2', 'title': 'Gemini 2', 'snippet': 'Second source', 'backend': 'gemini'}
        ])

        with patch('src.research.deep_researcher_refactored.TavilyBackend', return_value=mock_tavily):
            with patch('src.research.deep_researcher_refactored.SearXNGBackend', return_value=mock_searxng):
                with patch('src.research.deep_researcher_refactored.GeminiAPIBackend', return_value=mock_gemini):
                    researcher = DeepResearcher()

                    config = {'domain': 'SaaS'}
                    result = await researcher.research_topic("Test topic", config)

                    # Verify research succeeded with minimum sources
                    assert len(result['sources']) == 2  # Only from gemini

                    # Quality score should be low but research succeeded
                    assert result['quality_score'] < 50


class TestOrchestratorAllBackendsFail:
    """Test scenario: All backends fail, should raise error"""

    @pytest.mark.asyncio
    async def test_all_backends_fail_raises_error(self):
        """Should raise DeepResearchError when all backends fail"""
        # Mock all backends to return empty (graceful failure)
        mock_tavily = MagicMock()
        mock_tavily.search = AsyncMock(return_value=[])

        mock_searxng = MagicMock()
        mock_searxng.search = AsyncMock(return_value=[])

        mock_gemini = MagicMock()
        mock_gemini.search = AsyncMock(return_value=[])

        with patch('src.research.deep_researcher_refactored.TavilyBackend', return_value=mock_tavily):
            with patch('src.research.deep_researcher_refactored.SearXNGBackend', return_value=mock_searxng):
                with patch('src.research.deep_researcher_refactored.GeminiAPIBackend', return_value=mock_gemini):
                    researcher = DeepResearcher()

                    config = {'domain': 'SaaS'}

                    with pytest.raises(DeepResearchError) as exc_info:
                        await researcher.research_topic("Test topic", config)

                    assert "All backends failed" in str(exc_info.value)


class TestOrchestratorLoggingVerification:
    """Test scenario: Verify comprehensive logging (no silent failures)"""

    @pytest.mark.asyncio
    async def test_logging_no_silent_failures(self):
        """Should log all backend operations and failures"""
        # Mock backends with one failure
        mock_tavily = MagicMock()
        mock_tavily.search = AsyncMock(return_value=[])  # Empty result

        mock_searxng = MagicMock()
        mock_searxng.search = AsyncMock(return_value=[
            {'url': 'https://example.com/source1', 'title': 'Source 1', 'snippet': 'Content', 'backend': 'searxng'}
        ])

        mock_gemini = MagicMock()
        mock_gemini.search = AsyncMock(return_value=[
            {'url': 'https://example.com/source2', 'title': 'Source 2', 'snippet': 'Content', 'backend': 'gemini'}
        ])

        # Mock logger to verify logging
        with patch('src.research.deep_researcher_refactored.logger') as mock_logger:
            with patch('src.research.deep_researcher_refactored.TavilyBackend', return_value=mock_tavily):
                with patch('src.research.deep_researcher_refactored.SearXNGBackend', return_value=mock_searxng):
                    with patch('src.research.deep_researcher_refactored.GeminiAPIBackend', return_value=mock_gemini):
                        researcher = DeepResearcher()

                        config = {'domain': 'SaaS'}
                        result = await researcher.research_topic("Test topic", config)

                        # Verify logging calls were made
                        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]

                        # Should log: initialization, research start, backend searches, completion
                        assert 'orchestrator_initialized' in log_calls
                        assert 'research_started' in log_calls
                        assert 'backend_search_start' in log_calls
                        assert 'backend_search_success' in log_calls
                        assert 'search_complete' in log_calls
                        assert 'sources_merged' in log_calls
                        assert 'research_complete' in log_calls

                        # Verify no silent failures
                        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]
                        # No errors should be logged for successful operations
                        assert len(error_calls) == 0


class TestOrchestratorBackendHealth:
    """Test backend health monitoring"""

    @pytest.mark.asyncio
    async def test_backend_health_monitoring(self):
        """Should report health status for all backends"""
        mock_tavily = MagicMock()
        mock_tavily.search = AsyncMock(return_value=[])
        mock_tavily.health_check = AsyncMock(return_value=BackendHealth.SUCCESS)

        mock_searxng = MagicMock()
        mock_searxng.search = AsyncMock(return_value=[])
        mock_searxng.health_check = AsyncMock(return_value=BackendHealth.SUCCESS)

        mock_gemini = MagicMock()
        mock_gemini.search = AsyncMock(return_value=[])
        mock_gemini.health_check = AsyncMock(return_value=BackendHealth.DEGRADED)

        with patch('src.research.deep_researcher_refactored.TavilyBackend', return_value=mock_tavily):
            with patch('src.research.deep_researcher_refactored.SearXNGBackend', return_value=mock_searxng):
                with patch('src.research.deep_researcher_refactored.GeminiAPIBackend', return_value=mock_gemini):
                    researcher = DeepResearcher()

                    health = await researcher.get_backend_health()

                    assert health['tavily'] == BackendHealth.SUCCESS
                    assert health['searxng'] == BackendHealth.SUCCESS
                    assert health['gemini'] == BackendHealth.DEGRADED


class TestOrchestratorStatistics:
    """Test statistics tracking"""

    @pytest.mark.asyncio
    async def test_statistics_tracking(self):
        """Should track backend performance statistics"""
        mock_tavily = MagicMock()
        mock_tavily.search = AsyncMock(return_value=[
            {'url': 'url1', 'title': 't1', 'snippet': 's1', 'backend': 'tavily'}
        ])

        mock_searxng = MagicMock()
        mock_searxng.search = AsyncMock(return_value=[
            {'url': 'url2', 'title': 't2', 'snippet': 's2', 'backend': 'searxng'}
        ])

        mock_gemini = MagicMock()
        mock_gemini.search = AsyncMock(return_value=[
            {'url': 'url3', 'title': 't3', 'snippet': 's3', 'backend': 'gemini'}
        ])

        with patch('src.research.deep_researcher_refactored.TavilyBackend', return_value=mock_tavily):
            with patch('src.research.deep_researcher_refactored.SearXNGBackend', return_value=mock_searxng):
                with patch('src.research.deep_researcher_refactored.GeminiAPIBackend', return_value=mock_gemini):
                    researcher = DeepResearcher()

                    config = {'domain': 'SaaS'}
                    await researcher.research_topic("Test topic", config)

                    stats = researcher.get_backend_statistics()

                    # Verify statistics were tracked
                    assert stats['backend_stats']['tavily']['success'] == 1
                    assert stats['backend_stats']['searxng']['success'] == 1
                    assert stats['backend_stats']['gemini']['success'] == 1

                    assert stats['overall']['total_research'] == 1
                    assert stats['overall']['failed_research'] == 0
                    assert stats['overall']['success_rate'] == 1.0
