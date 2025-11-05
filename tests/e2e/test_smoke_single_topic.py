"""
Smoke Test: Single Topic Pipeline Validation

Quick validation that the full pipeline works end-to-end.
Cost: ~$0.01, Duration: ~20 seconds

Use this before running the full 30-topic test.
"""

import pytest
import os
import asyncio
from datetime import datetime

from src.research.deep_researcher_refactored import DeepResearcher
from src.research.reranker.multi_stage_reranker import MultiStageReranker
from src.research.synthesizer.content_synthesizer import (
    ContentSynthesizer,
    PassageExtractionStrategy
)


# Skip if API keys not available
pytestmark = pytest.mark.skipif(
    not all([
        os.getenv('TAVILY_API_KEY'),
        os.getenv('GEMINI_API_KEY'),
        os.getenv('VOYAGE_API_KEY')
    ]),
    reason="Required API keys not set"
)


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.smoke
async def test_smoke_single_topic_pipeline():
    """
    Smoke test: Single topic through full pipeline

    Validates:
    - All components initialize correctly
    - Pipeline executes end-to-end
    - Output format is correct
    - Cost and latency are reasonable

    Cost: ~$0.01, Duration: ~20s
    """
    print("\n" + "=" * 60)
    print("SMOKE TEST: Single Topic Pipeline")
    print("=" * 60)

    # Configuration
    config = {
        'domain': 'Tech',
        'market': 'USA',
        'language': 'en',
        'vertical': 'Tech'
    }

    topic = "Artificial Intelligence trends 2025"

    # Initialize components
    print("\n1. Initializing components...")
    researcher = DeepResearcher(
        enable_tavily=True,
        enable_searxng=True,
        enable_gemini=True,
        enable_rss=False,
        enable_thenewsapi=False
    )

    reranker = MultiStageReranker(
        enable_voyage=True,
        stage3_final_count=25
    )

    synthesizer = ContentSynthesizer(
        strategy=PassageExtractionStrategy.BM25_LLM,
        max_article_words=1000
    )

    print("   ✓ All components initialized")

    # Step 1: Research
    print("\n2. Collecting sources (3 backends)...")
    start_time = datetime.now()

    search_results = []
    for backend_name, backend in researcher.backends.items():
        results = await backend.search(topic, max_results=10)
        search_results.extend(results)
        print(f"   - {backend_name}: {len(results)} results")

    print(f"   ✓ Total sources: {len(search_results)}")
    assert len(search_results) >= 10, "Should collect at least 10 sources"

    # Step 2: Rerank
    print("\n3. Reranking sources (3 stages)...")
    reranked_sources = await reranker.rerank(
        sources=search_results,
        query=topic,
        config=config
    )

    print(f"   ✓ Reranked to top {len(reranked_sources)} sources")
    assert len(reranked_sources) >= 10, "Should have at least 10 reranked sources"
    assert all('final_score' in s for s in reranked_sources), "All sources should have scores"

    # Step 3: Synthesize
    print("\n4. Synthesizing article...")
    result = await synthesizer.synthesize(
        sources=reranked_sources[:10],  # Use top 10 for speed
        query=topic,
        config=config
    )

    duration = (datetime.now() - start_time).total_seconds()

    # Verify output
    print("\n5. Validating output...")
    assert 'article' in result, "Should have article"
    assert 'citations' in result, "Should have citations"
    assert 'metadata' in result, "Should have metadata"

    article = result['article']
    citations = result['citations']
    metadata = result['metadata']

    print(f"   - Article length: {len(article)} chars, {metadata['article_words']} words")
    print(f"   - Citations: {len(citations)}")
    print(f"   - Duration: {duration:.1f}s")
    print(f"   - Strategy: {metadata['strategy']}")

    # Quality checks
    assert len(article) > 200, "Article should be substantial"
    assert metadata['article_words'] >= 100, "Should have meaningful content"
    assert len(citations) >= 3, "Should cite multiple sources"
    assert '[Source' in article, "Should have inline citations"
    assert duration < 60, "Should complete in reasonable time (<60s)"

    # Cost estimation
    estimated_cost = 0.01  # $0.002 collection + $0.005 reranker + $0.003 synthesizer
    print(f"   - Estimated cost: ${estimated_cost:.3f}")

    print("\n6. Sample output...")
    print(f"   Article preview: {article[:200]}...")
    print(f"\n   Citations:")
    for citation in citations[:3]:
        print(f"     [{citation['id']}] {citation['title'][:60]}...")

    print("\n" + "=" * 60)
    print("✓ SMOKE TEST PASSED")
    print("=" * 60)
    print("\nPipeline is operational. Ready for full 30-topic test.")
    print("Run: pytest tests/e2e/test_production_pipeline_30_topics.py")


if __name__ == "__main__":
    """Run test standalone"""
    asyncio.run(test_smoke_single_topic_pipeline())
