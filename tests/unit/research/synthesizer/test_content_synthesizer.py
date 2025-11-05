"""
Unit tests for ContentSynthesizer

Tests the 2-stage passage extraction and article synthesis:
- Stage 1: BM25 pre-filter (22 → 10 paragraphs per source)
- Stage 2: Gemini Flash selects top 3 passages from 10
- Article synthesis with inline citations [Source N]
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.research.synthesizer.content_synthesizer import (
    ContentSynthesizer,
    SynthesisError,
    PassageExtractionStrategy
)
from src.research.backends.base import SearchResult


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini API client"""
    client = MagicMock()
    model = MagicMock()

    # Mock generate_content response
    response = MagicMock()
    response.text = "Generated article with [Source 1] citation"
    model.generate_content_async = AsyncMock(return_value=response)

    client.models.get = Mock(return_value=model)
    return client


@pytest.fixture
def sample_sources():
    """Sample reranked sources for testing"""
    return [
        SearchResult.create(
            url="https://example.com/article1",
            title="Article 1",
            snippet="First article about PropTech",
            backend="tavily",
            content=None,  # Will be fetched
            published_date=datetime(2025, 1, 1),
            final_score=0.95
        ),
        SearchResult.create(
            url="https://example.com/article2",
            title="Article 2",
            snippet="Second article about AI",
            backend="searxng",
            content=None,
            published_date=datetime(2025, 1, 2),
            final_score=0.90
        ),
    ]


class TestContentSynthesizerInit:
    """Test ContentSynthesizer initialization"""

    def test_init_with_gemini_key(self, mock_gemini_client):
        """Test initialization with Gemini API key"""
        with patch('src.research.synthesizer.content_synthesizer.genai') as mock_genai:
            mock_genai.Client.return_value = mock_gemini_client

            synthesizer = ContentSynthesizer(gemini_api_key="test_key")

            assert synthesizer.gemini_api_key == "test_key"
            assert synthesizer.strategy == PassageExtractionStrategy.BM25_LLM
            assert synthesizer.passages_per_source == 3
            assert synthesizer.max_article_words == 2000
            mock_genai.configure.assert_called_once_with(api_key="test_key")

    def test_init_loads_from_env(self):
        """Test initialization loads API key from environment"""
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'env_key'}):
            with patch('src.research.synthesizer.content_synthesizer.genai'):
                synthesizer = ContentSynthesizer()
                assert synthesizer.gemini_api_key == "env_key"

    def test_init_fallback_strategy(self):
        """Test initialization with fallback strategy"""
        with patch('src.research.synthesizer.content_synthesizer.genai'):
            synthesizer = ContentSynthesizer(
                gemini_api_key="test_key",
                strategy=PassageExtractionStrategy.LLM_ONLY
            )
            assert synthesizer.strategy == PassageExtractionStrategy.LLM_ONLY


class TestContentExtraction:
    """Test full content extraction with trafilatura"""

    @pytest.mark.asyncio
    async def test_extract_content_success(self, sample_sources):
        """Test successful content extraction"""
        with patch('src.research.synthesizer.content_synthesizer.genai'):
            synthesizer = ContentSynthesizer(gemini_api_key="test_key")

            # Mock trafilatura fetch and extract
            mock_html = "<html><body><p>Full article content here.</p></body></html>"
            mock_content = "Full article content here.\n\nThis is paragraph 2.\n\nParagraph 3."

            with patch('src.research.synthesizer.content_synthesizer.fetch_url', return_value=mock_html):
                with patch('src.research.synthesizer.content_synthesizer.extract', return_value=mock_content):
                    result = await synthesizer._extract_content(sample_sources[0], source_id=1)

                    assert result['url'] == sample_sources[0]['url']
                    assert result['content'] == mock_content
                    assert result['paragraphs'] == ['Full article content here.', 'This is paragraph 2.', 'Paragraph 3.']
                    assert result['source_id'] == 1

    @pytest.mark.asyncio
    async def test_extract_content_failure_graceful(self, sample_sources):
        """Test graceful handling when content extraction fails"""
        with patch('src.research.synthesizer.content_synthesizer.genai'):
            synthesizer = ContentSynthesizer(gemini_api_key="test_key")

            # Mock trafilatura failure
            with patch('src.research.synthesizer.content_synthesizer.fetch_url', side_effect=Exception("Network error")):
                result = await synthesizer._extract_content(sample_sources[0], source_id=1)

                # Should fallback to snippet
                assert result['url'] == sample_sources[0]['url']
                assert result['content'] == sample_sources[0]['snippet']
                assert result['source_id'] == 1
                assert len(result['paragraphs']) > 0


class TestBM25PassageFilter:
    """Test BM25 passage pre-filtering (Stage 1)"""

    def test_bm25_filter_paragraphs(self):
        """Test BM25 filters 22 → 10 paragraphs"""
        with patch('src.research.synthesizer.content_synthesizer.genai'):
            synthesizer = ContentSynthesizer(gemini_api_key="test_key")

            # Create 22 paragraphs
            paragraphs = [f"Paragraph {i} about PropTech AI" for i in range(22)]
            query = "PropTech AI trends"

            # Mock BM25Okapi
            with patch('src.research.synthesizer.content_synthesizer.BM25Okapi') as mock_bm25:
                mock_instance = MagicMock()
                mock_instance.get_scores.return_value = list(range(22, 0, -1))  # Descending scores
                mock_bm25.return_value = mock_instance

                filtered = synthesizer._bm25_filter_passages(paragraphs, query, top_k=10)

                assert len(filtered) == 10
                # Should return top 10 by score
                assert all(isinstance(p, str) for p in filtered)

    def test_bm25_filter_fewer_than_top_k(self):
        """Test BM25 filter when fewer paragraphs than top_k"""
        with patch('src.research.synthesizer.content_synthesizer.genai'):
            synthesizer = ContentSynthesizer(gemini_api_key="test_key")

            paragraphs = ["Para 1", "Para 2"]
            query = "test"

            with patch('src.research.synthesizer.content_synthesizer.BM25Okapi') as mock_bm25:
                mock_instance = MagicMock()
                mock_instance.get_scores.return_value = [2, 1]
                mock_bm25.return_value = mock_instance

                filtered = synthesizer._bm25_filter_passages(paragraphs, query, top_k=10)

                assert len(filtered) == 2  # Returns all available


class TestLLMPassageSelection:
    """Test LLM passage selection with Gemini Flash (Stage 2)"""

    @pytest.mark.asyncio
    async def test_llm_select_passages_success(self, mock_gemini_client):
        """Test LLM selects top 3 passages from 10"""
        with patch('src.research.synthesizer.content_synthesizer.genai') as mock_genai:
            mock_genai.Client.return_value = mock_gemini_client

            synthesizer = ContentSynthesizer(gemini_api_key="test_key")
            synthesizer.client = mock_gemini_client

            paragraphs = [f"Passage {i}" for i in range(10)]
            query = "PropTech AI"

            # Mock Gemini response with passage indices
            response = MagicMock()
            response.text = '{"selected_passages": [0, 2, 5]}'
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(return_value=response)
            synthesizer.client.models.get = Mock(return_value=mock_model)

            selected = await synthesizer._llm_select_passages(paragraphs, query, top_k=3)

            assert len(selected) == 3
            assert selected == ["Passage 0", "Passage 2", "Passage 5"]

    @pytest.mark.asyncio
    async def test_llm_select_passages_fallback(self, mock_gemini_client):
        """Test LLM selection fallback to first N passages on error"""
        with patch('src.research.synthesizer.content_synthesizer.genai') as mock_genai:
            mock_genai.Client.return_value = mock_gemini_client

            synthesizer = ContentSynthesizer(gemini_api_key="test_key")
            synthesizer.client = mock_gemini_client

            paragraphs = [f"Passage {i}" for i in range(10)]
            query = "PropTech AI"

            # Mock Gemini error
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(side_effect=Exception("API error"))
            synthesizer.client.models.get = Mock(return_value=mock_model)

            selected = await synthesizer._llm_select_passages(paragraphs, query, top_k=3)

            # Should fallback to first 3
            assert len(selected) == 3
            assert selected == ["Passage 0", "Passage 1", "Passage 2"]


class TestArticleSynthesis:
    """Test article synthesis with Gemini 2.5 Flash"""

    @pytest.mark.asyncio
    async def test_synthesize_article_success(self, mock_gemini_client, sample_sources):
        """Test successful article synthesis with citations"""
        with patch('src.research.synthesizer.content_synthesizer.genai') as mock_genai:
            mock_genai.Client.return_value = mock_gemini_client

            synthesizer = ContentSynthesizer(gemini_api_key="test_key")
            synthesizer.client = mock_gemini_client

            passages_with_sources = [
                {'passage': 'Passage 1', 'source_id': 1, 'url': 'https://example.com/1', 'title': 'Article 1'},
                {'passage': 'Passage 2', 'source_id': 2, 'url': 'https://example.com/2', 'title': 'Article 2'},
            ]

            query = "PropTech AI trends"
            config = {'domain': 'SaaS', 'language': 'de'}

            # Mock Gemini response
            response = MagicMock()
            response.text = "Article about PropTech [Source 1] and AI [Source 2]."
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(return_value=response)
            synthesizer.client.models.get = Mock(return_value=mock_model)

            result = await synthesizer._synthesize_article(passages_with_sources, query, config)

            assert 'article' in result
            assert 'citations' in result
            assert 'metadata' in result
            assert '[Source 1]' in result['article']
            assert '[Source 2]' in result['article']

    @pytest.mark.asyncio
    async def test_synthesize_article_error_raises(self, mock_gemini_client):
        """Test article synthesis raises SynthesisError on failure"""
        with patch('src.research.synthesizer.content_synthesizer.genai') as mock_genai:
            mock_genai.Client.return_value = mock_gemini_client

            synthesizer = ContentSynthesizer(gemini_api_key="test_key")
            synthesizer.client = mock_gemini_client

            passages_with_sources = [
                {'passage': 'Passage 1', 'source_id': 1, 'url': 'https://example.com/1', 'title': 'Article 1'},
            ]

            # Mock Gemini error
            mock_model = MagicMock()
            mock_model.generate_content_async = AsyncMock(side_effect=Exception("API error"))
            synthesizer.client.models.get = Mock(return_value=mock_model)

            with pytest.raises(SynthesisError, match="Failed to synthesize article"):
                await synthesizer._synthesize_article(passages_with_sources, "query", {})


class TestFullPipeline:
    """Test full synthesis pipeline (E2E)"""

    @pytest.mark.asyncio
    async def test_synthesize_full_pipeline_bm25_llm(self, mock_gemini_client, sample_sources):
        """Test full pipeline with BM25→LLM strategy"""
        with patch('src.research.synthesizer.content_synthesizer.genai') as mock_genai:
            mock_genai.Client.return_value = mock_gemini_client

            synthesizer = ContentSynthesizer(
                gemini_api_key="test_key",
                strategy=PassageExtractionStrategy.BM25_LLM
            )
            synthesizer.client = mock_gemini_client

            # Mock content extraction
            mock_content = "Para 1 about PropTech.\n\nPara 2 about AI.\n\nPara 3 about trends."
            with patch('src.research.synthesizer.content_synthesizer.fetch_url', return_value="<html></html>"):
                with patch('src.research.synthesizer.content_synthesizer.extract', return_value=mock_content):
                    # Mock BM25 filtering
                    with patch.object(synthesizer, '_bm25_filter_passages', return_value=["Para 1", "Para 2"]):
                        # Mock LLM selection
                        with patch.object(synthesizer, '_llm_select_passages', return_value=["Para 1"]):
                            # Mock article synthesis
                            mock_response = MagicMock()
                            mock_response.text = "Final article [Source 1]."
                            mock_model = MagicMock()
                            mock_model.generate_content_async = AsyncMock(return_value=mock_response)
                            mock_gemini_client.models.get.return_value = mock_model

                            result = await synthesizer.synthesize(
                                sources=sample_sources,
                                query="PropTech AI",
                                config={'domain': 'SaaS'}
                            )

                            assert 'article' in result
                            assert 'citations' in result
                            assert 'metadata' in result
                            assert result['metadata']['strategy'] == 'bm25_llm'
                            assert result['metadata']['total_sources'] == 2

    @pytest.mark.asyncio
    async def test_synthesize_full_pipeline_llm_only(self, mock_gemini_client, sample_sources):
        """Test full pipeline with LLM-only strategy"""
        with patch('src.research.synthesizer.content_synthesizer.genai') as mock_genai:
            mock_genai.Client.return_value = mock_gemini_client

            synthesizer = ContentSynthesizer(
                gemini_api_key="test_key",
                strategy=PassageExtractionStrategy.LLM_ONLY
            )
            synthesizer.client = mock_gemini_client

            # Mock content extraction
            mock_content = "Para 1.\n\nPara 2.\n\nPara 3."
            with patch('src.research.synthesizer.content_synthesizer.fetch_url', return_value="<html></html>"):
                with patch('src.research.synthesizer.content_synthesizer.extract', return_value=mock_content):
                    # Mock LLM selection (no BM25)
                    with patch.object(synthesizer, '_llm_select_passages', return_value=["Para 1"]):
                        # Mock article synthesis
                        mock_response = MagicMock()
                        mock_response.text = "Final article."
                        mock_model = MagicMock()
                        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
                        mock_gemini_client.models.get.return_value = mock_model

                        result = await synthesizer.synthesize(
                            sources=sample_sources,
                            query="PropTech AI",
                            config={'domain': 'SaaS'}
                        )

                        assert result['metadata']['strategy'] == 'llm_only'

    @pytest.mark.asyncio
    async def test_synthesize_no_sources_raises(self):
        """Test synthesis raises error when no sources provided"""
        with patch('src.research.synthesizer.content_synthesizer.genai'):
            synthesizer = ContentSynthesizer(gemini_api_key="test_key")

            with pytest.raises(SynthesisError, match="No sources provided"):
                await synthesizer.synthesize(sources=[], query="test", config={})
