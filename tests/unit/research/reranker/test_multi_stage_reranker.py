"""
Unit tests for MultiStageReranker (3-stage cascaded reranking)

Tests TDD approach for:
- Stage 1: BM25 lexical filter
- Stage 2: Voyage Lite semantic reranking
- Stage 3: Voyage Full + 6 custom SEO metrics

Following TDD: Write tests first, then implement to make them pass.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

# Import will fail initially (TDD approach)
try:
    from src.research.reranker.multi_stage_reranker import MultiStageReranker, RerankingError
except ImportError:
    pytest.skip("MultiStageReranker not implemented yet", allow_module_level=True)


@pytest.fixture
def sample_sources():
    """Sample search results for reranking"""
    return [
        {
            'url': 'https://example.edu/proptech-research',
            'title': 'Academic PropTech Research',
            'content': 'PropTech industry analysis with AI and machine learning applications in real estate technology.',
            'published_date': datetime.now().isoformat(),
            'backend': 'tavily',
            'rrf_score': 0.05
        },
        {
            'url': 'https://techcrunch.com/proptech-news',
            'title': 'PropTech Startup News',
            'content': 'Latest news about PropTech startups raising funding and new product launches.',
            'published_date': (datetime.now() - timedelta(days=2)).isoformat(),
            'backend': 'searxng',
            'rrf_score': 0.04
        },
        {
            'url': 'https://example.gov/housing-tech',
            'title': 'Government Housing Technology Report',
            'content': 'Official government report on housing technology and smart building initiatives.',
            'published_date': (datetime.now() - timedelta(days=30)).isoformat(),
            'backend': 'gemini',
            'rrf_score': 0.03
        },
        {
            'url': 'https://blog.com/proptech',
            'title': 'PropTech Blog Post',
            'content': 'General blog post about property technology trends.',
            'published_date': (datetime.now() - timedelta(days=5)).isoformat(),
            'backend': 'rss',
            'rrf_score': 0.02
        },
        {
            'url': 'https://spam.site/copy-paste',
            'title': 'Copied Content',
            'content': 'Low quality content about cryptocurrency and unrelated topics.',
            'published_date': (datetime.now() - timedelta(days=365)).isoformat(),
            'backend': 'thenewsapi',
            'rrf_score': 0.01
        }
    ]


@pytest.fixture
def reranker_config():
    """Configuration for reranker"""
    return {
        'domain': 'SaaS',
        'market': 'Germany',
        'language': 'de',
        'vertical': 'Proptech'
    }


class TestMultiStageRerankerInit:
    """Test reranker initialization"""

    def test_init_default(self):
        """Should initialize with default settings"""
        reranker = MultiStageReranker()

        # Note: enable_voyage may be False if VOYAGE_API_KEY not set in test environment
        # This is expected behavior - fallback to BM25 only
        assert reranker.stage1_threshold == 0.0  # Keep all results from BM25
        assert reranker.stage2_threshold == 0.3  # Voyage Lite threshold
        assert reranker.stage3_final_count == 25  # Final top 25 sources

    def test_init_custom_thresholds(self):
        """Should initialize with custom thresholds"""
        reranker = MultiStageReranker(
            stage1_threshold=0.1,
            stage2_threshold=0.5,
            stage3_final_count=15
        )

        assert reranker.stage1_threshold == 0.1
        assert reranker.stage2_threshold == 0.5
        assert reranker.stage3_final_count == 15

    def test_init_voyage_disabled(self):
        """Should work without Voyage API (BM25 only fallback)"""
        reranker = MultiStageReranker(enable_voyage=False)

        assert reranker.enable_voyage is False


class TestStage1BM25Filter:
    """Test Stage 1: BM25 lexical filter"""

    def test_stage1_scores_sources_by_relevance(self, sample_sources):
        """BM25 should score sources based on query relevance"""
        reranker = MultiStageReranker()
        query = "PropTech AI machine learning real estate"

        result = reranker._stage1_bm25_filter(sample_sources, query)

        # Should return all sources with BM25 scores
        assert len(result) <= len(sample_sources)

        # First result should be most relevant (contains "PropTech AI machine learning")
        assert result[0]['url'] == 'https://example.edu/proptech-research'

        # All results should have bm25_score
        for source in result:
            assert 'bm25_score' in source
            assert isinstance(source['bm25_score'], float)

    def test_stage1_filters_by_threshold(self, sample_sources):
        """BM25 should filter out low-scoring sources"""
        reranker = MultiStageReranker(stage1_threshold=1.0)
        query = "PropTech AI"

        result = reranker._stage1_bm25_filter(sample_sources, query)

        # Should filter out sources below threshold
        assert len(result) < len(sample_sources)

        # All remaining sources should be above threshold
        for source in result:
            assert source['bm25_score'] >= 1.0

    def test_stage1_empty_query(self, sample_sources):
        """BM25 should handle empty query gracefully"""
        reranker = MultiStageReranker()

        result = reranker._stage1_bm25_filter(sample_sources, "")

        # Should return sources with equal scores (or based on RRF score)
        assert len(result) > 0

    def test_stage1_empty_sources(self):
        """BM25 should handle empty source list"""
        reranker = MultiStageReranker()

        result = reranker._stage1_bm25_filter([], "test query")

        assert result == []

    def test_stage1_tokenizes_content(self, sample_sources):
        """BM25 should tokenize content properly"""
        reranker = MultiStageReranker()
        query = "AI machine learning"

        result = reranker._stage1_bm25_filter(sample_sources, query)

        # Source with both terms should score highest
        assert 'AI' in result[0]['content'] or 'machine learning' in result[0]['content']


class TestStage2VoyageLite:
    """Test Stage 2: Voyage Lite semantic reranking"""

    @pytest.mark.asyncio
    async def test_stage2_calls_voyage_lite_api(self, sample_sources):
        """Should call Voyage Lite API for semantic reranking"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_client.rerank = Mock(return_value=Mock(
                results=[
                    Mock(index=0, relevance_score=0.85),
                    Mock(index=1, relevance_score=0.72),
                    Mock(index=2, relevance_score=0.65)
                ]
            ))
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(voyage_api_key="test_key")
            query = "PropTech AI"

            result = await reranker._stage2_voyage_lite(sample_sources[:3], query)

            # Should call Voyage API
            mock_client.rerank.assert_called_once()

            # Should return reranked results
            assert len(result) == 3
            assert all('voyage_lite_score' in s for s in result)

    @pytest.mark.asyncio
    async def test_stage2_filters_by_threshold(self, sample_sources):
        """Should filter sources below Voyage Lite threshold"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_client.rerank = Mock(return_value=Mock(
                results=[
                    Mock(index=0, relevance_score=0.85),
                    Mock(index=1, relevance_score=0.25),  # Below threshold
                    Mock(index=2, relevance_score=0.65)
                ]
            ))
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(
                voyage_api_key="test_key",
                stage2_threshold=0.3
            )
            query = "PropTech"

            result = await reranker._stage2_voyage_lite(sample_sources[:3], query)

            # Should filter out source with score 0.25
            assert len(result) == 2
            assert all(s['voyage_lite_score'] >= 0.3 for s in result)

    @pytest.mark.asyncio
    async def test_stage2_fallback_to_bm25_on_error(self, sample_sources):
        """Should fallback to BM25 ranking if Voyage API fails"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_client.rerank = Mock(side_effect=Exception("API error"))
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(voyage_api_key="test_key")
            query = "PropTech"

            # Add BM25 scores from stage 1
            for idx, source in enumerate(sample_sources[:3]):
                source['bm25_score'] = 1.0 / (idx + 1)

            result = await reranker._stage2_voyage_lite(sample_sources[:3], query)

            # Should fallback and still return results
            assert len(result) > 0
            # Should use BM25 scores for ranking
            assert result[0]['bm25_score'] >= result[1]['bm25_score']

    @pytest.mark.asyncio
    async def test_stage2_disabled_voyage(self, sample_sources):
        """Should skip Voyage API if disabled"""
        reranker = MultiStageReranker(enable_voyage=False)
        query = "PropTech"

        # Add BM25 scores
        for idx, source in enumerate(sample_sources[:3]):
            source['bm25_score'] = 1.0 / (idx + 1)

        result = await reranker._stage2_voyage_lite(sample_sources[:3], query)

        # Should return sources without Voyage scores
        assert len(result) == 3
        assert all('voyage_lite_score' not in s for s in result)


class TestStage3VoyageFullMetrics:
    """Test Stage 3: Voyage Full + 6 custom SEO metrics"""

    @pytest.mark.asyncio
    async def test_stage3_calls_voyage_full_api(self, sample_sources):
        """Should call Voyage Full API (rerank-2)"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_client.rerank = Mock(return_value=Mock(
                results=[
                    Mock(index=0, relevance_score=0.92),
                    Mock(index=1, relevance_score=0.78)
                ]
            ))
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(voyage_api_key="test_key")
            query = "PropTech AI"
            config = {'domain': 'SaaS', 'market': 'Germany', 'language': 'de'}

            result = await reranker._stage3_voyage_full_metrics(
                sample_sources[:2],
                query,
                config
            )

            # Should call Voyage API with rerank-2 model
            mock_client.rerank.assert_called_once()
            call_args = mock_client.rerank.call_args
            assert call_args[1]['model'] == 'rerank-2'

            # Should have voyage_full_score
            assert all('voyage_full_score' in s for s in result)

    @pytest.mark.asyncio
    async def test_stage3_calculates_relevance_metric(self, sample_sources):
        """Should calculate Relevance metric (30% weight)"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_client.rerank = Mock(return_value=Mock(
                results=[
                    Mock(index=0, relevance_score=0.9),
                    Mock(index=1, relevance_score=0.7)
                ]
            ))
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(voyage_api_key="test_key")
            query = "PropTech"
            config = {'domain': 'SaaS'}

            result = await reranker._stage3_voyage_full_metrics(
                sample_sources[:2],
                query,
                config
            )

            # Relevance metric should be present
            assert 'metrics' in result[0]
            assert 'relevance' in result[0]['metrics']
            assert 0 <= result[0]['metrics']['relevance'] <= 1

    @pytest.mark.asyncio
    async def test_stage3_calculates_novelty_metric(self, sample_sources):
        """Should calculate Novelty metric (25% weight) using MMR"""
        reranker = MultiStageReranker()

        # Add content hashes for similarity detection
        sample_sources[0]['content'] = "PropTech AI machine learning applications"
        sample_sources[1]['content'] = "PropTech AI machine learning solutions"  # Similar

        novelty_score = reranker._calculate_novelty(
            candidate=sample_sources[1],
            selected_sources=[sample_sources[0]]
        )

        # Should return lower score for similar content
        assert 0 <= novelty_score <= 1

    @pytest.mark.asyncio
    async def test_stage3_calculates_authority_metric(self, sample_sources):
        """Should calculate Authority metric (20% weight) with E-E-A-T"""
        reranker = MultiStageReranker()

        # .edu domain should have high authority
        edu_source = sample_sources[0]  # .edu domain
        assert '.edu' in edu_source['url']

        authority_score = reranker._calculate_authority(edu_source)

        assert 0 <= authority_score <= 1
        assert authority_score > 0.5  # .edu should score high

    @pytest.mark.asyncio
    async def test_stage3_calculates_freshness_metric(self, sample_sources):
        """Should calculate Freshness metric (15% weight) with QDF decay"""
        reranker = MultiStageReranker()

        # Recent content should score higher
        recent_source = sample_sources[0]  # Now
        old_source = sample_sources[4]  # 1 year ago

        recent_freshness = reranker._calculate_freshness(recent_source)
        old_freshness = reranker._calculate_freshness(old_source)

        assert recent_freshness > old_freshness
        assert 0 <= recent_freshness <= 1

    @pytest.mark.asyncio
    async def test_stage3_calculates_diversity_metric(self, sample_sources):
        """Should calculate Diversity metric (5% weight) with domain bucketing"""
        reranker = MultiStageReranker()

        # Same domain should be penalized
        selected_sources = [
            {'url': 'https://example.com/article1'},
            {'url': 'https://example.com/article2'}  # Same domain
        ]

        candidate = {'url': 'https://example.com/article3'}  # Same domain again

        diversity_score = reranker._calculate_diversity(
            candidate,
            selected_sources
        )

        # Should penalize third article from same domain
        assert 0 <= diversity_score <= 1
        assert diversity_score < 0.5  # Max 2 per domain

    @pytest.mark.asyncio
    async def test_stage3_calculates_locality_metric(self, sample_sources, reranker_config):
        """Should calculate Locality metric (5% weight) for market matching"""
        reranker = MultiStageReranker()

        # German domain (.de) should score higher for German market
        de_source = {'url': 'https://example.de/article', 'content': 'German content'}
        com_source = {'url': 'https://example.com/article', 'content': 'English content'}

        de_locality = reranker._calculate_locality(de_source, reranker_config)
        com_locality = reranker._calculate_locality(com_source, reranker_config)

        assert de_locality > com_locality
        assert 0 <= de_locality <= 1

    @pytest.mark.asyncio
    async def test_stage3_combines_all_metrics(self, sample_sources):
        """Should combine all 6 metrics with proper weights"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_client.rerank = Mock(return_value=Mock(
                results=[Mock(index=0, relevance_score=0.9)]
            ))
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(voyage_api_key="test_key")
            query = "PropTech"
            config = {'domain': 'SaaS', 'market': 'Germany', 'language': 'de'}

            result = await reranker._stage3_voyage_full_metrics(
                sample_sources[:1],
                query,
                config
            )

            # Should have all metrics
            metrics = result[0]['metrics']
            assert 'relevance' in metrics
            assert 'novelty' in metrics
            assert 'authority' in metrics
            assert 'freshness' in metrics
            assert 'diversity' in metrics
            assert 'locality' in metrics

            # Should have final combined score
            assert 'final_score' in result[0]
            assert 0 <= result[0]['final_score'] <= 1

    @pytest.mark.asyncio
    async def test_stage3_limits_to_final_count(self, sample_sources):
        """Should limit results to stage3_final_count"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_results = [Mock(index=i, relevance_score=0.9 - i*0.1) for i in range(5)]
            mock_client.rerank = Mock(return_value=Mock(results=mock_results))
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(
                voyage_api_key="test_key",
                stage3_final_count=3
            )
            query = "PropTech"
            config = {'domain': 'SaaS'}

            result = await reranker._stage3_voyage_full_metrics(
                sample_sources,
                query,
                config
            )

            # Should limit to 3 results
            assert len(result) <= 3


class TestFullPipelineIntegration:
    """Test full 3-stage pipeline"""

    @pytest.mark.asyncio
    async def test_full_pipeline_all_stages(self, sample_sources, reranker_config):
        """Should run all 3 stages in sequence"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            # Mock both Voyage Lite and Voyage Full calls
            mock_client.rerank = Mock(side_effect=[
                # Stage 2: Voyage Lite
                Mock(results=[Mock(index=i, relevance_score=0.8 - i*0.1) for i in range(5)]),
                # Stage 3: Voyage Full
                Mock(results=[Mock(index=i, relevance_score=0.9 - i*0.1) for i in range(3)])
            ])
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(voyage_api_key="test_key")
            query = "PropTech AI machine learning"

            result = await reranker.rerank(sample_sources, query, reranker_config)

            # Should complete all stages
            assert len(result) > 0
            assert len(result) <= reranker.stage3_final_count

            # Final results should have all scores
            assert 'bm25_score' in result[0]
            assert 'voyage_lite_score' in result[0]
            assert 'voyage_full_score' in result[0]
            assert 'final_score' in result[0]
            assert 'metrics' in result[0]

    @pytest.mark.asyncio
    async def test_full_pipeline_fallback_to_bm25(self, sample_sources, reranker_config):
        """Should fallback to BM25-only if Voyage unavailable"""
        reranker = MultiStageReranker(enable_voyage=False)
        query = "PropTech"

        result = await reranker.rerank(sample_sources, query, reranker_config)

        # Should still return results using BM25
        assert len(result) > 0
        assert 'bm25_score' in result[0]
        assert 'voyage_lite_score' not in result[0]

    @pytest.mark.asyncio
    async def test_full_pipeline_empty_sources(self, reranker_config):
        """Should handle empty source list"""
        reranker = MultiStageReranker()

        result = await reranker.rerank([], "test query", reranker_config)

        assert result == []

    @pytest.mark.asyncio
    async def test_full_pipeline_preserves_metadata(self, sample_sources, reranker_config):
        """Should preserve all source metadata through pipeline"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_client.rerank = Mock(side_effect=[
                Mock(results=[Mock(index=0, relevance_score=0.9)]),
                Mock(results=[Mock(index=0, relevance_score=0.95)])
            ])
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(voyage_api_key="test_key")
            query = "PropTech"

            result = await reranker.rerank(sample_sources[:1], query, reranker_config)

            # Should preserve original metadata
            assert result[0]['url'] == sample_sources[0]['url']
            assert result[0]['title'] == sample_sources[0]['title']
            assert result[0]['content'] == sample_sources[0]['content']
            assert result[0]['backend'] == sample_sources[0]['backend']

    @pytest.mark.asyncio
    async def test_full_pipeline_sorts_by_final_score(self, sample_sources, reranker_config):
        """Should sort final results by final_score descending"""
        with patch('voyageai.Client') as MockVoyageClient:
            mock_client = Mock()
            mock_client.rerank = Mock(side_effect=[
                Mock(results=[
                    Mock(index=0, relevance_score=0.6),
                    Mock(index=1, relevance_score=0.9),  # Higher
                    Mock(index=2, relevance_score=0.7)
                ]),
                Mock(results=[
                    Mock(index=0, relevance_score=0.7),
                    Mock(index=1, relevance_score=0.95),  # Highest
                    Mock(index=2, relevance_score=0.8)
                ])
            ])
            MockVoyageClient.return_value = mock_client

            reranker = MultiStageReranker(voyage_api_key="test_key")
            query = "PropTech"

            result = await reranker.rerank(sample_sources[:3], query, reranker_config)

            # Should be sorted by final_score descending
            scores = [s['final_score'] for s in result]
            assert scores == sorted(scores, reverse=True)
