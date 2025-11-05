"""
Integration tests for 5-source DeepResearcher orchestrator

Tests the complete orchestrator with all 5 sources:
- SEARCH: Tavily (DEPTH) + SearXNG (BREADTH) + Gemini API (TRENDS)
- CONTENT: RSS Feeds (CURATED) + TheNewsAPI (BREAKING NEWS)

Validates:
- All 5 sources execute in parallel
- Graceful degradation (continues if ≥1 source succeeds)
- Source fusion and deduplication
- Statistics tracking across all sources
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.research.deep_researcher_refactored import DeepResearcher, DeepResearchError
from src.models.document import Document


@pytest.fixture
def mock_config():
    """Mock market configuration"""
    config = Mock()
    config.domain = "SaaS"
    config.market = "Germany"
    config.language = "de"
    config.vertical = "Proptech"
    return config


@pytest.fixture
def mock_db_manager():
    """Mock database manager"""
    return Mock()


@pytest.fixture
def mock_deduplicator():
    """Mock deduplicator"""
    dedup = Mock()
    dedup.is_duplicate = Mock(return_value=False)
    dedup.compute_content_hash = Mock(return_value="hash123")
    dedup.get_canonical_url = Mock(side_effect=lambda url: url)
    return dedup


@pytest.fixture
def sample_search_results():
    """Sample search results from search backends"""
    return [
        {
            'url': 'https://tavily.example.com/article1',
            'title': 'Deep PropTech Analysis',
            'content': 'Academic research on PropTech...',
            'published_date': '2025-11-05T10:00:00',
            'backend': 'tavily'
        },
        {
            'url': 'https://searxng.example.com/article2',
            'title': 'PropTech News Roundup',
            'content': 'Latest PropTech developments...',
            'published_date': '2025-11-05T09:30:00',
            'backend': 'searxng'
        },
        {
            'url': 'https://gemini.example.com/article3',
            'title': 'PropTech Trends 2025',
            'content': 'Emerging trends in PropTech...',
            'published_date': '2025-11-05T09:00:00',
            'backend': 'gemini'
        }
    ]


@pytest.fixture
def sample_rss_documents():
    """Sample documents from RSS collector"""
    return [
        Document(
            id="rss_doc1",
            source="rss_heise",
            source_url="https://heise.de/rss/article1",
            title="German Tech News",
            content="PropTech innovation in Germany...",
            summary="PropTech grows",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="hash1",
            canonical_url="https://heise.de/rss/article1",
            published_at=datetime(2025, 11, 5, 8, 0),
            fetched_at=datetime.now(),
            status="new"
        ),
        Document(
            id="rss_doc2",
            source="rss_t3n",
            source_url="https://t3n.de/rss/article2",
            title="SaaS Platforms for Real Estate",
            content="Cloud solutions for property management...",
            summary="SaaS in real estate",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="hash2",
            canonical_url="https://t3n.de/rss/article2",
            published_at=datetime(2025, 11, 5, 7, 30),
            fetched_at=datetime.now(),
            status="new"
        )
    ]


@pytest.fixture
def sample_thenewsapi_documents():
    """Sample documents from TheNewsAPI collector"""
    return [
        Document(
            id="thenewsapi_doc1",
            source="thenewsapi_TechCrunch",
            source_url="https://techcrunch.com/news/article1",
            title="Breaking: PropTech Startup Raises $50M",
            content="A PropTech startup announced...",
            summary="Startup funding news",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="hash3",
            canonical_url="https://techcrunch.com/news/article1",
            published_at=datetime(2025, 11, 5, 11, 0),
            fetched_at=datetime.now(),
            status="new"
        )
    ]


class TestDeepResearcherInitialization:
    """Test orchestrator initialization with 5 sources"""

    def test_init_all_sources_enabled(self, mock_config, mock_db_manager, mock_deduplicator):
        """Test initialization with all 5 sources enabled"""
        with patch('src.research.deep_researcher_refactored.TavilyBackend'), \
             patch('src.research.deep_researcher_refactored.SearXNGBackend'), \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend'), \
             patch('src.research.deep_researcher_refactored.RSSCollector'), \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector'):

            researcher = DeepResearcher(
                tavily_api_key="test_tavily",
                gemini_api_key="test_gemini",
                thenewsapi_api_key="test_thenewsapi",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator
            )

            # Should have 3 backends + 2 collectors
            assert len(researcher.backends) == 3
            assert len(researcher.collectors) == 2
            assert 'tavily' in researcher.backends
            assert 'searxng' in researcher.backends
            assert 'gemini' in researcher.backends
            assert 'rss' in researcher.collectors
            assert 'thenewsapi' in researcher.collectors

    def test_init_only_search_backends(self, mock_config, mock_db_manager, mock_deduplicator):
        """Test initialization with only search backends (no collectors)"""
        with patch('src.research.deep_researcher_refactored.TavilyBackend'), \
             patch('src.research.deep_researcher_refactored.SearXNGBackend'), \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend'):

            researcher = DeepResearcher(
                tavily_api_key="test_tavily",
                gemini_api_key="test_gemini",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator,
                enable_rss=False,
                enable_thenewsapi=False
            )

            # Should have only backends
            assert len(researcher.backends) == 3
            assert len(researcher.collectors) == 0

    def test_init_only_collectors(self, mock_config, mock_db_manager, mock_deduplicator):
        """Test initialization with only collectors (no search backends)"""
        with patch('src.research.deep_researcher_refactored.RSSCollector'), \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector'):

            researcher = DeepResearcher(
                thenewsapi_api_key="test_thenewsapi",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator,
                enable_tavily=False,
                enable_searxng=False,
                enable_gemini=False
            )

            # Should have only collectors
            assert len(researcher.backends) == 0
            assert len(researcher.collectors) == 2

    def test_init_no_sources_raises_error(self):
        """Test initialization fails if no sources are enabled"""
        with pytest.raises(DeepResearchError, match="No search backends or collectors"):
            DeepResearcher(
                enable_tavily=False,
                enable_searxng=False,
                enable_gemini=False,
                enable_rss=False,
                enable_thenewsapi=False
            )


class TestDeepResearcher5SourceResearch:
    """Test research with all 5 sources"""

    @pytest.mark.asyncio
    async def test_research_all_5_sources_succeed(
        self,
        mock_config,
        mock_db_manager,
        mock_deduplicator,
        sample_search_results,
        sample_rss_documents,
        sample_thenewsapi_documents
    ):
        """Test research when all 5 sources return results"""
        with patch('src.research.deep_researcher_refactored.TavilyBackend') as MockTavily, \
             patch('src.research.deep_researcher_refactored.SearXNGBackend') as MockSearXNG, \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend') as MockGemini, \
             patch('src.research.deep_researcher_refactored.RSSCollector') as MockRSS, \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector') as MockTheNewsAPI:

            # Mock backend search methods
            mock_tavily = AsyncMock()
            mock_tavily.search = AsyncMock(return_value=[sample_search_results[0]])
            MockTavily.return_value = mock_tavily

            mock_searxng = AsyncMock()
            mock_searxng.search = AsyncMock(return_value=[sample_search_results[1]])
            MockSearXNG.return_value = mock_searxng

            mock_gemini = AsyncMock()
            mock_gemini.search = AsyncMock(return_value=[sample_search_results[2]])
            MockGemini.return_value = mock_gemini

            # Mock collector methods
            mock_rss = Mock()
            mock_rss.collect_from_feeds = Mock(return_value=sample_rss_documents)
            MockRSS.return_value = mock_rss

            mock_thenewsapi = Mock()
            mock_thenewsapi.collect = AsyncMock(return_value=sample_thenewsapi_documents)
            MockTheNewsAPI.return_value = mock_thenewsapi

            # Create researcher
            config_dict = {
                'domain': 'SaaS',
                'market': 'Germany',
                'language': 'de',
                'vertical': 'Proptech',
                'collectors': {
                    'custom_feeds': ['https://heise.de/rss', 'https://t3n.de/rss']
                }
            }

            researcher = DeepResearcher(
                tavily_api_key="test_tavily",
                gemini_api_key="test_gemini",
                thenewsapi_api_key="test_thenewsapi",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator
            )

            # Execute research
            result = await researcher.research_topic("PropTech Trends", config_dict)

            # Verify all sources were called
            assert mock_tavily.search.called
            assert mock_searxng.search.called
            assert mock_gemini.search.called
            assert mock_rss.collect_from_feeds.called
            assert mock_thenewsapi.collect.called

            # Verify result structure
            assert 'topic' in result
            assert 'sources' in result
            assert 'backend_stats' in result
            assert result['backend_stats']['successful'] == ['tavily', 'searxng', 'gemini', 'rss', 'thenewsapi']
            assert result['backend_stats']['failed'] == []

            # Should have sources from all 5 sources (3 search + 2 RSS + 1 TheNewsAPI = 6 total)
            assert len(result['sources']) == 6

    @pytest.mark.asyncio
    async def test_research_one_source_fails_gracefully(
        self,
        mock_config,
        mock_db_manager,
        mock_deduplicator,
        sample_search_results
    ):
        """Test graceful degradation when one source fails"""
        with patch('src.research.deep_researcher_refactored.TavilyBackend') as MockTavily, \
             patch('src.research.deep_researcher_refactored.SearXNGBackend') as MockSearXNG, \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend') as MockGemini, \
             patch('src.research.deep_researcher_refactored.RSSCollector') as MockRSS, \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector') as MockTheNewsAPI:

            # Mock backends (Tavily fails)
            mock_tavily = AsyncMock()
            mock_tavily.search = AsyncMock(side_effect=Exception("Tavily API error"))
            MockTavily.return_value = mock_tavily

            mock_searxng = AsyncMock()
            mock_searxng.search = AsyncMock(return_value=[sample_search_results[1]])
            MockSearXNG.return_value = mock_searxng

            mock_gemini = AsyncMock()
            mock_gemini.search = AsyncMock(return_value=[sample_search_results[2]])
            MockGemini.return_value = mock_gemini

            mock_rss = Mock()
            mock_rss.collect_from_feeds = Mock(return_value=[])
            MockRSS.return_value = mock_rss

            mock_thenewsapi = Mock()
            mock_thenewsapi.collect = AsyncMock(return_value=[])
            MockTheNewsAPI.return_value = mock_thenewsapi

            config_dict = {
                'domain': 'SaaS',
                'collectors': {'custom_feeds': []}
            }

            researcher = DeepResearcher(
                tavily_api_key="test_tavily",
                gemini_api_key="test_gemini",
                thenewsapi_api_key="test_thenewsapi",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator
            )

            # Should succeed despite Tavily failure
            result = await researcher.research_topic("PropTech", config_dict)

            # Verify graceful degradation
            assert 'tavily' in result['backend_stats']['failed']
            assert len(result['backend_stats']['successful']) >= 2  # SearXNG + Gemini
            assert len(result['sources']) >= 2

    @pytest.mark.asyncio
    async def test_research_two_sources_fail_continues(
        self,
        mock_config,
        mock_db_manager,
        mock_deduplicator,
        sample_search_results
    ):
        """Test continuation when 2 sources fail"""
        with patch('src.research.deep_researcher_refactored.TavilyBackend') as MockTavily, \
             patch('src.research.deep_researcher_refactored.SearXNGBackend') as MockSearXNG, \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend') as MockGemini, \
             patch('src.research.deep_researcher_refactored.RSSCollector') as MockRSS, \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector') as MockTheNewsAPI:

            # Mock backends (Tavily and SearXNG fail)
            mock_tavily = AsyncMock()
            mock_tavily.search = AsyncMock(side_effect=Exception("Tavily error"))
            MockTavily.return_value = mock_tavily

            mock_searxng = AsyncMock()
            mock_searxng.search = AsyncMock(side_effect=Exception("SearXNG error"))
            MockSearXNG.return_value = mock_searxng

            mock_gemini = AsyncMock()
            mock_gemini.search = AsyncMock(return_value=[sample_search_results[2]])
            MockGemini.return_value = mock_gemini

            mock_rss = Mock()
            mock_rss.collect_from_feeds = Mock(return_value=[])
            MockRSS.return_value = mock_rss

            mock_thenewsapi = Mock()
            mock_thenewsapi.collect = AsyncMock(return_value=[])
            MockTheNewsAPI.return_value = mock_thenewsapi

            config_dict = {
                'domain': 'SaaS',
                'collectors': {'custom_feeds': []}
            }

            researcher = DeepResearcher(
                tavily_api_key="test_tavily",
                gemini_api_key="test_gemini",
                thenewsapi_api_key="test_thenewsapi",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator
            )

            # Should succeed with remaining sources
            result = await researcher.research_topic("PropTech", config_dict)

            # Verify 2 failures but research continues
            assert len(result['backend_stats']['failed']) == 2
            assert 'gemini' in result['backend_stats']['successful']

    @pytest.mark.asyncio
    async def test_research_all_sources_fail_raises_error(
        self,
        mock_config,
        mock_db_manager,
        mock_deduplicator
    ):
        """Test error when all 5 sources fail"""
        with patch('src.research.deep_researcher_refactored.TavilyBackend') as MockTavily, \
             patch('src.research.deep_researcher_refactored.SearXNGBackend') as MockSearXNG, \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend') as MockGemini, \
             patch('src.research.deep_researcher_refactored.RSSCollector') as MockRSS, \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector') as MockTheNewsAPI:

            # All sources fail
            mock_tavily = AsyncMock()
            mock_tavily.search = AsyncMock(side_effect=Exception("Tavily error"))
            MockTavily.return_value = mock_tavily

            mock_searxng = AsyncMock()
            mock_searxng.search = AsyncMock(side_effect=Exception("SearXNG error"))
            MockSearXNG.return_value = mock_searxng

            mock_gemini = AsyncMock()
            mock_gemini.search = AsyncMock(side_effect=Exception("Gemini error"))
            MockGemini.return_value = mock_gemini

            mock_rss = Mock()
            mock_rss.collect_from_feeds = Mock(side_effect=Exception("RSS error"))
            MockRSS.return_value = mock_rss

            mock_thenewsapi = Mock()
            mock_thenewsapi.collect = AsyncMock(side_effect=Exception("TheNewsAPI error"))
            MockTheNewsAPI.return_value = mock_thenewsapi

            config_dict = {
                'domain': 'SaaS',
                'collectors': {'custom_feeds': ['https://example.com/rss']}
            }

            researcher = DeepResearcher(
                tavily_api_key="test_tavily",
                gemini_api_key="test_gemini",
                thenewsapi_api_key="test_thenewsapi",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator
            )

            # Should raise error when all sources fail
            with pytest.raises(DeepResearchError, match="All sources failed"):
                await researcher.research_topic("PropTech", config_dict)


class TestDeepResearcherStatistics:
    """Test statistics tracking across 5 sources"""

    @pytest.mark.asyncio
    async def test_statistics_track_all_sources(
        self,
        mock_config,
        mock_db_manager,
        mock_deduplicator,
        sample_search_results
    ):
        """Test statistics are tracked for all 5 sources"""
        with patch('src.research.deep_researcher_refactored.TavilyBackend') as MockTavily, \
             patch('src.research.deep_researcher_refactored.SearXNGBackend') as MockSearXNG, \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend') as MockGemini, \
             patch('src.research.deep_researcher_refactored.RSSCollector') as MockRSS, \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector') as MockTheNewsAPI:

            # Setup mocks
            for MockBackend, result in [(MockTavily, [sample_search_results[0]]),
                                        (MockSearXNG, [sample_search_results[1]]),
                                        (MockGemini, [sample_search_results[2]])]:
                mock_backend = AsyncMock()
                mock_backend.search = AsyncMock(return_value=result)
                MockBackend.return_value = mock_backend

            mock_rss = Mock()
            mock_rss.collect_from_feeds = Mock(return_value=[])
            MockRSS.return_value = mock_rss

            mock_thenewsapi = Mock()
            mock_thenewsapi.collect = AsyncMock(return_value=[])
            MockTheNewsAPI.return_value = mock_thenewsapi

            config_dict = {'domain': 'SaaS', 'collectors': {'custom_feeds': []}}

            researcher = DeepResearcher(
                tavily_api_key="test_tavily",
                gemini_api_key="test_gemini",
                thenewsapi_api_key="test_thenewsapi",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator
            )

            await researcher.research_topic("PropTech", config_dict)

            # Check statistics
            stats = researcher.get_backend_statistics()

            # All 5 sources should be in stats
            assert 'tavily' in stats['backend_stats']
            assert 'searxng' in stats['backend_stats']
            assert 'gemini' in stats['backend_stats']
            assert 'rss' in stats['backend_stats']
            assert 'thenewsapi' in stats['backend_stats']

            # Verify success/failure counts
            assert stats['backend_stats']['tavily']['success'] == 1
            assert stats['backend_stats']['searxng']['success'] == 1
            assert stats['backend_stats']['gemini']['success'] == 1
