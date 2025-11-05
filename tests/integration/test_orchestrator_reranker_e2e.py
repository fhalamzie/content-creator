"""
E2E Integration Tests for DeepResearcher Orchestrator + MultiStageReranker

Tests the complete pipeline from source collection through reranking:
1. 5 sources (Tavily + SearXNG + Gemini + RSS + TheNewsAPI)
2. RRF Fusion + MinHash Deduplication
3. 3-Stage Cascaded Reranker (BM25 + Voyage Lite + Voyage Full + 6 metrics)

Validates:
- Full pipeline execution
- Graceful degradation scenarios
- Reranker integration
- SEO metrics calculation
- Cost and latency targets
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.research.deep_researcher_refactored import DeepResearcher
from src.research.reranker.multi_stage_reranker import MultiStageReranker
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
def comprehensive_search_results():
    """Comprehensive search results from all 5 sources with varying quality"""
    base_time = datetime.now()
    return [
        # Tavily (DEPTH) - High quality academic
        {
            'url': 'https://mit.edu/proptech/ai-research',
            'title': 'AI and Machine Learning in PropTech: Academic Review',
            'content': 'PropTech industry leverages artificial intelligence and machine learning algorithms for property valuation, predictive analytics, and automated decision-making in real estate technology applications.',
            'published_date': base_time.isoformat(),
            'backend': 'tavily'
        },
        {
            'url': 'https://stanford.edu/proptech/trends-2025',
            'title': 'PropTech Trends 2025: Research Paper',
            'content': 'Emerging trends in property technology include blockchain for transactions, IoT for smart buildings, and AI-powered property management systems.',
            'published_date': (base_time - timedelta(days=5)).isoformat(),
            'backend': 'tavily'
        },
        # SearXNG (BREADTH) - Mixed quality
        {
            'url': 'https://techcrunch.com/proptech-funding',
            'title': 'PropTech Startups Raise $2B in Funding',
            'content': 'Property technology startups secured record funding in Q4 2024, with AI-powered platforms leading the investment surge.',
            'published_date': (base_time - timedelta(days=2)).isoformat(),
            'backend': 'searxng'
        },
        {
            'url': 'https://blog.example.com/proptech',
            'title': 'PropTech Blog Post',
            'content': 'General overview of property technology trends.',
            'published_date': (base_time - timedelta(days=10)).isoformat(),
            'backend': 'searxng'
        },
        # Gemini (TRENDS) - Future-focused
        {
            'url': 'https://weforum.org/proptech-future',
            'title': 'Future of PropTech: WEF Report',
            'content': 'World Economic Forum analysis of property technology future trends, including sustainability and digital transformation.',
            'published_date': (base_time - timedelta(days=1)).isoformat(),
            'backend': 'gemini'
        },
        # RSS (CURATED) - Industry news
        {
            'url': 'https://heise.de/proptech/ki-immobilien',
            'title': 'KI revolutioniert Immobilienbranche',
            'content': 'Künstliche Intelligenz transformiert die deutsche Immobilienwirtschaft mit automatisierten Bewertungen und Predictive Analytics.',
            'published_date': (base_time - timedelta(days=3)).isoformat(),
            'backend': 'rss'
        },
        {
            'url': 't3n.de/proptech/saas-platforms',
            'title': 'SaaS-Plattformen für Immobilienverwaltung',
            'content': 'Cloud-basierte Software revolutioniert Property Management in Deutschland.',
            'published_date': (base_time - timedelta(days=7)).isoformat(),
            'backend': 'rss'
        },
        # TheNewsAPI (BREAKING) - Recent news
        {
            'url': 'https://reuters.com/proptech-acquisition',
            'title': 'Breaking: Major PropTech Acquisition Announced',
            'content': 'Leading property technology company acquires AI startup for $500M.',
            'published_date': (base_time - timedelta(hours=6)).isoformat(),
            'backend': 'thenewsapi'
        },
        # Duplicate content (should be filtered by MinHash)
        {
            'url': 'https://copy-site.com/duplicate',
            'title': 'PropTech AI Copy',
            'content': 'PropTech industry leverages artificial intelligence and machine learning algorithms for property valuation, predictive analytics, and automated decision-making in real estate technology applications.',  # Duplicate of MIT article
            'published_date': (base_time - timedelta(days=30)).isoformat(),
            'backend': 'searxng'
        },
        # Low quality spam (should score low in reranker)
        {
            'url': 'https://spam.site/unrelated',
            'title': 'Click Here For Crypto',
            'content': 'Buy cryptocurrency blockchain bitcoin ethereum unrelated content.',
            'published_date': (base_time - timedelta(days=365)).isoformat(),
            'backend': 'thenewsapi'
        }
    ]


class TestFullPipelineE2E:
    """E2E tests for complete orchestrator + reranker pipeline"""

    @pytest.mark.asyncio
    async def test_full_pipeline_5_sources_to_reranked_results(
        self,
        mock_config,
        mock_db_manager,
        mock_deduplicator,
        comprehensive_search_results
    ):
        """
        E2E: Complete pipeline from 5 sources through reranking

        Pipeline:
        1. 5 sources collect data (10 results total)
        2. RRF fusion merges ranked lists
        3. MinHash removes duplicates (9 unique)
        4. Stage 1 BM25 filters by relevance
        5. Stage 2 Voyage Lite semantic ranking (or BM25 fallback)
        6. Stage 3 Voyage Full + 6 metrics (final top 25)
        """
        with patch('src.research.deep_researcher_refactored.TavilyBackend') as MockTavily, \
             patch('src.research.deep_researcher_refactored.SearXNGBackend') as MockSearXNG, \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend') as MockGemini, \
             patch('src.research.deep_researcher_refactored.RSSCollector') as MockRSS, \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector') as MockTheNewsAPI:

            # Mock search backend responses (3 sources)
            mock_tavily = AsyncMock()
            mock_tavily.search = AsyncMock(return_value=comprehensive_search_results[0:2])
            MockTavily.return_value = mock_tavily

            mock_searxng = AsyncMock()
            mock_searxng.search = AsyncMock(return_value=comprehensive_search_results[2:4])
            MockSearXNG.return_value = mock_searxng

            mock_gemini = AsyncMock()
            mock_gemini.search = AsyncMock(return_value=[comprehensive_search_results[4]])
            MockGemini.return_value = mock_gemini

            # Mock collector responses (2 sources)
            sample_rss_docs = [
                Document(
                    id="rss_1",
                    source="rss_heise",
                    source_url=comprehensive_search_results[5]['url'],
                    title=comprehensive_search_results[5]['title'],
                    content=comprehensive_search_results[5]['content'],
                    language="de",
                    domain="SaaS",
                    market="Germany",
                    vertical="Proptech",
                    content_hash="hash5",
                    canonical_url=comprehensive_search_results[5]['url'],
                    published_at=datetime.fromisoformat(comprehensive_search_results[5]['published_date']),
                    fetched_at=datetime.now(),
                    status="new"
                ),
                Document(
                    id="rss_2",
                    source="rss_t3n",
                    source_url=comprehensive_search_results[6]['url'],
                    title=comprehensive_search_results[6]['title'],
                    content=comprehensive_search_results[6]['content'],
                    language="de",
                    domain="SaaS",
                    market="Germany",
                    vertical="Proptech",
                    content_hash="hash6",
                    canonical_url=comprehensive_search_results[6]['url'],
                    published_at=datetime.fromisoformat(comprehensive_search_results[6]['published_date']),
                    fetched_at=datetime.now(),
                    status="new"
                )
            ]

            mock_rss = Mock()
            mock_rss.collect_from_feeds = Mock(return_value=sample_rss_docs)
            MockRSS.return_value = mock_rss

            sample_news_docs = [
                Document(
                    id="news_1",
                    source="thenewsapi_reuters",
                    source_url=comprehensive_search_results[7]['url'],
                    title=comprehensive_search_results[7]['title'],
                    content=comprehensive_search_results[7]['content'],
                    language="en",
                    domain="SaaS",
                    market="Germany",
                    vertical="Proptech",
                    content_hash="hash7",
                    canonical_url=comprehensive_search_results[7]['url'],
                    published_at=datetime.fromisoformat(comprehensive_search_results[7]['published_date']),
                    fetched_at=datetime.now(),
                    status="new"
                ),
                # Duplicate and spam
                Document(
                    id="news_2",
                    source="thenewsapi_copy",
                    source_url=comprehensive_search_results[8]['url'],
                    title=comprehensive_search_results[8]['title'],
                    content=comprehensive_search_results[8]['content'],
                    language="en",
                    domain="SaaS",
                    market="Germany",
                    vertical="Proptech",
                    content_hash="hash8",
                    canonical_url=comprehensive_search_results[8]['url'],
                    published_at=datetime.fromisoformat(comprehensive_search_results[8]['published_date']),
                    fetched_at=datetime.now(),
                    status="new"
                ),
                Document(
                    id="news_3",
                    source="thenewsapi_spam",
                    source_url=comprehensive_search_results[9]['url'],
                    title=comprehensive_search_results[9]['title'],
                    content=comprehensive_search_results[9]['content'],
                    language="en",
                    domain="SaaS",
                    market="Germany",
                    vertical="Proptech",
                    content_hash="hash9",
                    canonical_url=comprehensive_search_results[9]['url'],
                    published_at=datetime.fromisoformat(comprehensive_search_results[9]['published_date']),
                    fetched_at=datetime.now(),
                    status="new"
                )
            ]

            mock_thenewsapi = Mock()
            mock_thenewsapi.collect = AsyncMock(return_value=sample_news_docs)
            MockTheNewsAPI.return_value = mock_thenewsapi

            # Create orchestrator
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

            # Execute orchestrator (includes RRF + MinHash)
            research_result = await researcher.research_topic(
                "PropTech AI machine learning trends",
                config_dict
            )

            # Verify orchestrator results
            assert 'sources' in research_result
            assert len(research_result['sources']) > 0  # Should have sources after dedup
            assert 'backend_stats' in research_result
            assert research_result['backend_stats']['successful'] == ['tavily', 'searxng', 'gemini', 'rss', 'thenewsapi']

            # Now apply reranker to orchestrator results
            # Reconstruct source dicts from URLs for reranker
            reranker_sources = []
            for url in research_result['sources']:
                # Find matching source from comprehensive_search_results
                matching_source = next(
                    (s for s in comprehensive_search_results if s['url'] == url),
                    None
                )
                if matching_source:
                    reranker_sources.append(matching_source)

            # Create reranker (will fallback to BM25 if no Voyage API key)
            reranker = MultiStageReranker(enable_voyage=False)  # Use BM25 only for tests

            # Execute reranker
            reranked_results = await reranker.rerank(
                reranker_sources,
                "PropTech AI machine learning trends",
                config_dict
            )

            # Verify reranker results
            assert len(reranked_results) > 0
            assert len(reranked_results) <= 25  # Top 25 limit

            # Verify quality ranking (.edu should score high)
            top_result = reranked_results[0]
            assert 'bm25_score' in top_result
            assert 'final_score' in top_result
            assert 'metrics' in top_result

            # Verify metrics are present
            metrics = top_result['metrics']
            assert 'relevance' in metrics
            assert 'novelty' in metrics
            assert 'authority' in metrics
            assert 'freshness' in metrics
            assert 'diversity' in metrics
            assert 'locality' in metrics

            # Verify .edu/.gov domains score high on authority
            edu_sources = [s for s in reranked_results if '.edu' in s['url'] or '.gov' in s['url']]
            if edu_sources:
                assert edu_sources[0]['metrics']['authority'] > 0.7

            # Verify recent sources score high on freshness
            recent_sources = [
                s for s in reranked_results
                if 'published_date' in s and
                (datetime.now() - datetime.fromisoformat(s['published_date'])).days < 7
            ]
            if recent_sources:
                assert recent_sources[0]['metrics']['freshness'] > 0.8

            # Verify German sources (.de) score higher on locality for German market
            de_sources = [s for s in reranked_results if '.de' in s['url']]
            if de_sources:
                assert de_sources[0]['metrics']['locality'] >= 0.5

            # Verify final scores are sorted descending
            scores = [s['final_score'] for s in reranked_results]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_pipeline_with_one_source_failure(
        self,
        mock_config,
        mock_db_manager,
        mock_deduplicator,
        comprehensive_search_results
    ):
        """E2E: Pipeline continues gracefully when one source fails"""
        with patch('src.research.deep_researcher_refactored.TavilyBackend') as MockTavily, \
             patch('src.research.deep_researcher_refactored.SearXNGBackend') as MockSearXNG, \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend') as MockGemini, \
             patch('src.research.deep_researcher_refactored.RSSCollector') as MockRSS, \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector') as MockTheNewsAPI:

            # Tavily fails
            mock_tavily = AsyncMock()
            mock_tavily.search = AsyncMock(side_effect=Exception("Tavily API error"))
            MockTavily.return_value = mock_tavily

            # Others succeed
            mock_searxng = AsyncMock()
            mock_searxng.search = AsyncMock(return_value=comprehensive_search_results[2:4])
            MockSearXNG.return_value = mock_searxng

            mock_gemini = AsyncMock()
            mock_gemini.search = AsyncMock(return_value=[comprehensive_search_results[4]])
            MockGemini.return_value = mock_gemini

            mock_rss = Mock()
            mock_rss.collect_from_feeds = Mock(return_value=[])
            MockRSS.return_value = mock_rss

            mock_thenewsapi = Mock()
            mock_thenewsapi.collect = AsyncMock(return_value=[])
            MockTheNewsAPI.return_value = mock_thenewsapi

            config_dict = {
                'domain': 'SaaS',
                'market': 'Germany',
                'language': 'de',
                'vertical': 'Proptech',
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
            research_result = await researcher.research_topic("PropTech", config_dict)

            # Verify graceful degradation
            assert 'tavily' in research_result['backend_stats']['failed']
            assert len(research_result['backend_stats']['successful']) >= 2
            assert len(research_result['sources']) > 0

            # Reranker should still work with fewer sources
            reranker = MultiStageReranker(enable_voyage=False)

            # Reconstruct sources
            reranker_sources = [
                s for s in comprehensive_search_results[2:5]
            ]

            reranked = await reranker.rerank(reranker_sources, "PropTech", config_dict)

            assert len(reranked) > 0
            assert all('final_score' in s for s in reranked)

    @pytest.mark.asyncio
    async def test_reranker_metric_calculations(self, comprehensive_search_results):
        """E2E: Verify all 6 SEO metrics calculate correctly"""
        reranker = MultiStageReranker(enable_voyage=False)

        config = {
            'domain': 'SaaS',
            'market': 'Germany',
            'language': 'de',
            'vertical': 'Proptech'
        }

        # Use subset with diverse characteristics
        test_sources = comprehensive_search_results[:6]

        reranked = await reranker.rerank(test_sources, "PropTech AI", config)

        # Verify all sources have metrics
        for source in reranked:
            assert 'metrics' in source
            metrics = source['metrics']

            # All metrics present
            assert 'relevance' in metrics
            assert 'novelty' in metrics
            assert 'authority' in metrics
            assert 'freshness' in metrics
            assert 'diversity' in metrics
            assert 'locality' in metrics

            # All metrics in valid range [0,1]
            for metric_name, metric_value in metrics.items():
                assert 0 <= metric_value <= 1, f"{metric_name} = {metric_value} out of range"

            # Final score is weighted sum
            expected_score = sum(
                metrics[m] * reranker.WEIGHTS[m]
                for m in reranker.WEIGHTS
            )
            assert abs(source['final_score'] - expected_score) < 0.001

        # Verify specific metric behaviors
        # .edu should have high authority
        edu_source = next((s for s in reranked if '.edu' in s['url']), None)
        if edu_source:
            assert edu_source['metrics']['authority'] > 0.7

        # Recent sources should have high freshness
        now = datetime.now()
        for source in reranked:
            if 'published_date' in source:
                pub_date = datetime.fromisoformat(source['published_date'])
                age_days = (now - pub_date).days

                if age_days < 7:
                    assert source['metrics']['freshness'] > 0.8
                elif age_days > 180:
                    assert source['metrics']['freshness'] < 0.3

        # .de domains should have higher locality for German market
        de_sources = [s for s in reranked if '.de' in s['url']]
        non_de_sources = [s for s in reranked if '.de' not in s['url'] and '.edu' not in s['url']]

        if de_sources and non_de_sources:
            avg_de_locality = sum(s['metrics']['locality'] for s in de_sources) / len(de_sources)
            avg_non_de_locality = sum(s['metrics']['locality'] for s in non_de_sources) / len(non_de_sources)
            assert avg_de_locality >= avg_non_de_locality

    @pytest.mark.asyncio
    async def test_pipeline_removes_duplicates(
        self,
        mock_config,
        mock_db_manager,
        mock_deduplicator
    ):
        """E2E: Verify MinHash removes near-duplicate content"""
        # Create sources with duplicate content
        duplicate_sources = [
            {
                'url': 'https://original.com/article',
                'title': 'Original Article',
                'content': 'PropTech industry leverages artificial intelligence and machine learning for automated property valuation and predictive analytics in real estate.',
                'published_date': datetime.now().isoformat(),
                'backend': 'tavily'
            },
            {
                'url': 'https://copy1.com/stolen',
                'title': 'Copied Article 1',
                'content': 'PropTech industry leverages artificial intelligence and machine learning for automated property valuation and predictive analytics in real estate.',  # Exact duplicate
                'published_date': datetime.now().isoformat(),
                'backend': 'searxng'
            },
            {
                'url': 'https://copy2.com/plagiarized',
                'title': 'Copied Article 2',
                'content': 'PropTech sector uses AI and machine learning for automatic property valuations and predictive analytics in real estate.',  # Near duplicate (80%+ similar)
                'published_date': datetime.now().isoformat(),
                'backend': 'gemini'
            },
            {
                'url': 'https://unique.com/different',
                'title': 'Unique Article',
                'content': 'Blockchain technology enables secure peer-to-peer cryptocurrency transactions with decentralized validation.',
                'published_date': datetime.now().isoformat(),
                'backend': 'rss'
            }
        ]

        # Mock orchestrator to return these sources
        with patch('src.research.deep_researcher_refactored.TavilyBackend') as MockTavily, \
             patch('src.research.deep_researcher_refactored.SearXNGBackend') as MockSearXNG, \
             patch('src.research.deep_researcher_refactored.GeminiAPIBackend') as MockGemini, \
             patch('src.research.deep_researcher_refactored.RSSCollector') as MockRSS, \
             patch('src.research.deep_researcher_refactored.TheNewsAPICollector') as MockTheNewsAPI:

            mock_tavily = AsyncMock()
            mock_tavily.search = AsyncMock(return_value=[duplicate_sources[0]])
            MockTavily.return_value = mock_tavily

            mock_searxng = AsyncMock()
            mock_searxng.search = AsyncMock(return_value=[duplicate_sources[1]])
            MockSearXNG.return_value = mock_searxng

            mock_gemini = AsyncMock()
            mock_gemini.search = AsyncMock(return_value=[duplicate_sources[2]])
            MockGemini.return_value = mock_gemini

            mock_rss = Mock()
            mock_rss.collect_from_feeds = Mock(return_value=[])
            MockRSS.return_value = mock_rss

            mock_thenewsapi = Mock()
            mock_thenewsapi.collect = AsyncMock(return_value=[])
            MockTheNewsAPI.return_value = mock_thenewsapi

            researcher = DeepResearcher(
                tavily_api_key="test_tavily",
                gemini_api_key="test_gemini",
                thenewsapi_api_key="test_thenewsapi",
                config=mock_config,
                db_manager=mock_db_manager,
                deduplicator=mock_deduplicator
            )

            config_dict = {
                'domain': 'SaaS',
                'collectors': {'custom_feeds': []}
            }

            result = await researcher.research_topic("PropTech AI", config_dict)

            # After MinHash deduplication, should have fewer sources
            # Original: 3 PropTech sources (1 original + 2 duplicates)
            # After dedup: 1-2 sources (duplicates removed)
            assert len(result['sources']) <= 2

            # Verify duplicate URLs are not both present
            urls = result['sources']
            proptech_urls = [u for u in urls if 'proptech' in u.lower() or 'original' in u or 'copy' in u]

            # Should have removed at least one duplicate
            assert len(proptech_urls) < 3


class TestRerankingSEOOptimization:
    """Test SEO optimization capabilities of reranker"""

    @pytest.mark.asyncio
    async def test_reranker_prioritizes_authoritative_sources(self):
        """Verify reranker ranks .edu/.gov sources higher"""
        sources = [
            {
                'url': 'https://example.com/blog',
                'title': 'Blog Post',
                'content': 'PropTech trends and analysis.',
                'published_date': datetime.now().isoformat(),
                'backend': 'searxng'
            },
            {
                'url': 'https://mit.edu/proptech/research',
                'title': 'MIT Research',
                'content': 'PropTech academic research study.',
                'published_date': datetime.now().isoformat(),
                'backend': 'tavily'
            },
            {
                'url': 'https://spam.site/random',
                'title': 'Random Spam',
                'content': 'Unrelated content.',
                'published_date': (datetime.now() - timedelta(days=365)).isoformat(),
                'backend': 'thenewsapi'
            }
        ]

        reranker = MultiStageReranker(enable_voyage=False)
        config = {'domain': 'SaaS', 'market': 'US', 'language': 'en'}

        reranked = await reranker.rerank(sources, "PropTech research", config)

        # .edu should rank first due to high authority
        assert '.edu' in reranked[0]['url']
        assert reranked[0]['metrics']['authority'] > 0.7

    @pytest.mark.asyncio
    async def test_reranker_prioritizes_fresh_content(self):
        """Verify reranker ranks recent content higher"""
        base_time = datetime.now()
        sources = [
            {
                'url': 'https://old.com/article',
                'title': 'Old PropTech Article',
                'content': 'PropTech analysis real estate technology from last year.',
                'published_date': (base_time - timedelta(days=365)).isoformat(),
                'backend': 'searxng'
            },
            {
                'url': 'https://recent.com/breaking',
                'title': 'Breaking PropTech News',
                'content': 'PropTech breaking news real estate technology today.',
                'published_date': base_time.isoformat(),
                'backend': 'thenewsapi'
            },
            {
                'url': 'https://medium.com/month-old',
                'title': 'Month Old PropTech Article',
                'content': 'PropTech analysis real estate technology from last month.',
                'published_date': (base_time - timedelta(days=30)).isoformat(),
                'backend': 'rss'
            }
        ]

        reranker = MultiStageReranker(enable_voyage=False, stage1_threshold=-1.0)  # Don't filter by BM25
        config = {'domain': 'SaaS', 'market': 'US', 'language': 'en'}

        reranked = await reranker.rerank(sources, "PropTech", config)

        # Should have all 3 sources
        assert len(reranked) == 3

        # Recent content should rank higher
        assert reranked[0]['metrics']['freshness'] > reranked[-1]['metrics']['freshness']

        # Breaking news should have freshness close to 1.0
        breaking_news = next(s for s in reranked if 'breaking' in s['title'].lower())
        assert breaking_news['metrics']['freshness'] > 0.95

    @pytest.mark.asyncio
    async def test_reranker_enforces_domain_diversity(self):
        """Verify reranker limits sources per domain"""
        sources = [
            {
                'url': 'https://example.com/article1',
                'title': 'Article 1',
                'content': 'PropTech content.',
                'published_date': datetime.now().isoformat(),
                'backend': 'searxng'
            },
            {
                'url': 'https://example.com/article2',
                'title': 'Article 2',
                'content': 'More PropTech content.',
                'published_date': datetime.now().isoformat(),
                'backend': 'searxng'
            },
            {
                'url': 'https://example.com/article3',
                'title': 'Article 3',
                'content': 'Even more PropTech content.',
                'published_date': datetime.now().isoformat(),
                'backend': 'searxng'
            },
            {
                'url': 'https://different.com/article',
                'title': 'Different Source',
                'content': 'PropTech from different domain.',
                'published_date': datetime.now().isoformat(),
                'backend': 'tavily'
            }
        ]

        reranker = MultiStageReranker(enable_voyage=False)
        config = {'domain': 'SaaS', 'market': 'US', 'language': 'en'}

        reranked = await reranker.rerank(sources, "PropTech", config)

        # Check diversity scores
        # First source from example.com should have diversity = 1.0
        # Second should have diversity = 0.5
        # Third should have diversity = 0.0
        example_com_sources = [s for s in reranked if 'example.com' in s['url']]

        if len(example_com_sources) >= 2:
            # Later sources from same domain should have lower diversity scores
            assert example_com_sources[0]['metrics']['diversity'] >= example_com_sources[-1]['metrics']['diversity']
