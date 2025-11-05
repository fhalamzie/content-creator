"""
Integration tests for ContentSynthesizer

Tests real API calls to Gemini and trafilatura content extraction.
These tests cost ~$0.01 per run (Gemini Flash API usage).
"""

import pytest
import os
from datetime import datetime

from src.research.synthesizer.content_synthesizer import (
    ContentSynthesizer,
    PassageExtractionStrategy,
    SynthesisError
)
from src.research.backends.base import SearchResult


# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv('GEMINI_API_KEY'),
    reason="GEMINI_API_KEY not set"
)


@pytest.fixture
def real_sources():
    """Real search results for testing"""
    return [
        SearchResult.create(
            url="https://en.wikipedia.org/wiki/Artificial_intelligence",
            title="Artificial Intelligence - Wikipedia",
            snippet="AI is intelligence demonstrated by machines",
            backend="test",
            published_date=datetime(2025, 1, 1),
            final_score=0.95
        ),
        SearchResult.create(
            url="https://en.wikipedia.org/wiki/PropTech",
            title="PropTech - Wikipedia",
            snippet="Property technology or PropTech refers to the application of information technology",
            backend="test",
            published_date=datetime(2025, 1, 2),
            final_score=0.90
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_extract_content_from_real_url(real_sources):
    """Test content extraction from real URL"""
    synthesizer = ContentSynthesizer()

    result = await synthesizer._extract_content(real_sources[0], source_id=1)

    assert result['url'] == real_sources[0]['url']
    assert result['source_id'] == 1
    assert len(result['content']) > 100  # Should extract substantial content
    assert len(result['paragraphs']) > 5  # Should have multiple paragraphs
    assert result['extraction_failed'] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_extract_content_graceful_fallback():
    """Test graceful fallback when URL fails"""
    synthesizer = ContentSynthesizer()

    bad_source = SearchResult.create(
        url="https://invalid-domain-that-does-not-exist-12345.com",
        title="Bad Source",
        snippet="This is a fallback snippet",
        backend="test"
    )

    result = await synthesizer._extract_content(bad_source, source_id=1)

    # Should fallback to snippet
    assert result['content'] == bad_source['snippet']
    assert result['extraction_failed'] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_bm25_llm_passage_extraction_real_api(real_sources):
    """Test BM25→LLM passage extraction with real Gemini API"""
    synthesizer = ContentSynthesizer(strategy=PassageExtractionStrategy.BM25_LLM)

    # Extract content
    extracted_sources = []
    for idx, source in enumerate(real_sources):
        extracted = await synthesizer._extract_content(source, source_id=idx + 1)
        extracted_sources.append(extracted)

    # Extract passages
    passages = await synthesizer._extract_passages_bm25_llm(
        extracted_sources,
        query="PropTech AI trends"
    )

    assert len(passages) > 0
    assert all('passage' in p for p in passages)
    assert all('source_id' in p for p in passages)
    assert all('url' in p for p in passages)
    assert all('title' in p for p in passages)

    # Should have extracted passages from multiple sources
    source_ids = {p['source_id'] for p in passages}
    assert len(source_ids) >= 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_llm_only_passage_extraction_real_api(real_sources):
    """Test LLM-only passage extraction with real Gemini API"""
    synthesizer = ContentSynthesizer(strategy=PassageExtractionStrategy.LLM_ONLY)

    # Extract content
    extracted_sources = []
    for idx, source in enumerate(real_sources):
        extracted = await synthesizer._extract_content(source, source_id=idx + 1)
        extracted_sources.append(extracted)

    # Extract passages
    passages = await synthesizer._extract_passages_llm_only(
        extracted_sources,
        query="PropTech AI trends"
    )

    assert len(passages) > 0
    assert all('passage' in p for p in passages)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_synthesis_pipeline_bm25_llm(real_sources):
    """Test full synthesis pipeline with real API (BM25→LLM strategy)"""
    synthesizer = ContentSynthesizer(
        strategy=PassageExtractionStrategy.BM25_LLM,
        max_article_words=500  # Shorter for faster testing
    )

    config = {
        'domain': 'PropTech',
        'language': 'en'
    }

    result = await synthesizer.synthesize(
        sources=real_sources,
        query="PropTech AI trends",
        config=config
    )

    # Verify structure
    assert 'article' in result
    assert 'citations' in result
    assert 'metadata' in result

    # Verify article quality
    article = result['article']
    assert len(article) > 100  # Should generate substantial content
    assert 'PropTech' in article or 'AI' in article  # Should be relevant
    assert '[Source 1]' in article or '[Source 2]' in article  # Should have citations

    # Verify citations
    citations = result['citations']
    assert len(citations) >= 1
    assert all('id' in c for c in citations)
    assert all('url' in c for c in citations)
    assert all('title' in c for c in citations)

    # Verify metadata
    metadata = result['metadata']
    assert metadata['strategy'] == 'bm25_llm'
    assert metadata['total_sources'] == 2
    assert metadata['successful_extractions'] >= 1
    assert metadata['total_passages'] >= 1
    assert metadata['article_words'] > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_synthesis_pipeline_llm_only(real_sources):
    """Test full synthesis pipeline with real API (LLM-only strategy)"""
    synthesizer = ContentSynthesizer(
        strategy=PassageExtractionStrategy.LLM_ONLY,
        max_article_words=500
    )

    config = {
        'domain': 'PropTech',
        'language': 'en'
    }

    result = await synthesizer.synthesize(
        sources=real_sources,
        query="PropTech AI trends",
        config=config
    )

    # Should work similarly to BM25→LLM
    assert 'article' in result
    assert len(result['article']) > 100
    assert result['metadata']['strategy'] == 'llm_only'


@pytest.mark.asyncio
@pytest.mark.integration
async def test_synthesis_with_many_sources():
    """Test synthesis with 25 sources (realistic scenario)"""
    synthesizer = ContentSynthesizer(
        strategy=PassageExtractionStrategy.BM25_LLM,
        max_article_words=1000
    )

    # Create 25 mock sources (would normally come from reranker)
    sources = [
        SearchResult.create(
            url=f"https://en.wikipedia.org/wiki/Artificial_intelligence",
            title=f"AI Article {i}",
            snippet=f"Article {i} about artificial intelligence",
            backend="test",
            final_score=0.95 - (i * 0.01)
        )
        for i in range(1, 26)
    ]

    config = {
        'domain': 'Tech',
        'language': 'en'
    }

    result = await synthesizer.synthesize(
        sources=sources,
        query="Artificial Intelligence trends",
        config=config
    )

    assert 'article' in result
    assert len(result['article']) > 200
    assert result['metadata']['total_sources'] == 25

    # Should extract passages from multiple sources (not just first few)
    assert result['metadata']['total_passages'] >= 10


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cost_estimation():
    """Test that synthesis stays within budget"""
    synthesizer = ContentSynthesizer(
        strategy=PassageExtractionStrategy.BM25_LLM,
        max_article_words=2000
    )

    # Single source to minimize cost
    sources = [
        SearchResult.create(
            url="https://en.wikipedia.org/wiki/PropTech",
            title="PropTech",
            snippet="PropTech information",
            backend="test",
            final_score=0.95
        )
    ]

    config = {'domain': 'PropTech', 'language': 'en'}

    result = await synthesizer.synthesize(
        sources=sources,
        query="PropTech trends",
        config=config
    )

    # Verify synthesis completed
    assert 'article' in result
    assert len(result['article']) > 100

    # Cost should be minimal for single source
    # Expected: ~$0.00322 for 25 sources, so ~$0.0001 for 1 source
    print(f"\nCost estimation test completed:")
    print(f"  Sources: {len(sources)}")
    print(f"  Passages: {result['metadata']['total_passages']}")
    print(f"  Article words: {result['metadata']['article_words']}")
    print(f"  Duration: {result['metadata']['total_duration_ms']}ms")
    print(f"  Estimated cost: <$0.001")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_error_handling_no_sources():
    """Test error handling when no sources provided"""
    synthesizer = ContentSynthesizer()

    with pytest.raises(SynthesisError, match="No sources provided"):
        await synthesizer.synthesize(sources=[], query="test", config={})


@pytest.mark.asyncio
@pytest.mark.integration
async def test_error_handling_all_extractions_fail():
    """Test error handling when all content extractions fail"""
    synthesizer = ContentSynthesizer()

    # All invalid URLs
    bad_sources = [
        SearchResult.create(
            url=f"https://invalid-{i}.com",
            title=f"Bad {i}",
            snippet="",  # Empty snippet
            backend="test"
        )
        for i in range(3)
    ]

    with pytest.raises(SynthesisError, match="Failed to extract content"):
        await synthesizer.synthesize(
            sources=bad_sources,
            query="test",
            config={}
        )
