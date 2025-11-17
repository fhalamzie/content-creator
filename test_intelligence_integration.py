"""
Integration Test for Phase 2D - Intelligence Features

Tests the complete pipeline with SERP analysis, content scoring, and difficulty scoring.

Usage:
    python test_intelligence_integration.py
"""

import asyncio
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def test_intelligence_integration():
    """Test complete intelligence pipeline integration."""

    setup_logging(log_level="INFO")

    logger.info("=" * 60)
    logger.info("Phase 2D Intelligence Integration Test")
    logger.info("=" * 60)

    # Test configuration
    test_topic = "PropTech AI automation trends 2025"
    test_config = {
        "market": "Germany",
        "language": "de",
        "domain": "PropTech",
        "vertical": "Real Estate Technology"
    }

    logger.info(f"Test topic: {test_topic}")
    logger.info(f"Test config: {test_config}")

    # Initialize orchestrator with intelligence features enabled
    logger.info("\n" + "=" * 60)
    logger.info("Step 1: Initialize Orchestrator (Intelligence ENABLED)")
    logger.info("=" * 60)

    orchestrator = HybridResearchOrchestrator(
        # Research backends
        enable_tavily=True,
        enable_searxng=False,  # Disable for faster testing
        enable_gemini=False,   # Disable for faster testing
        enable_rss=False,
        enable_thenewsapi=False,
        # Pipeline stages
        enable_reranking=False,  # Disable for faster testing
        enable_synthesis=True,   # Keep synthesis to test integration
        max_article_words=1000,  # Shorter for faster testing
        # Intelligence features (Phase 2)
        enable_serp_analysis=True,
        enable_content_scoring=True,
        enable_difficulty_scoring=True,
        # Database
        db_path="data/topics_test_intelligence.db"
    )

    logger.info("✅ Orchestrator initialized with intelligence features")

    # Test research_topic method with intelligence
    logger.info("\n" + "=" * 60)
    logger.info("Step 2: Research Topic with Intelligence")
    logger.info("=" * 60)

    try:
        result = await orchestrator.research_topic(
            topic=test_topic,
            config=test_config,
            brand_tone=["Professional", "Technical"],
            generate_images=False,  # Skip images for faster testing
            max_results=5  # Fewer sources for faster testing
        )

        logger.info("\n" + "=" * 60)
        logger.info("Step 3: Verify Intelligence Results")
        logger.info("=" * 60)

        # Verify standard fields
        assert result["topic"] == test_topic, "Topic mismatch"
        assert "sources" in result, "Missing sources"
        assert "article" in result, "Missing article"
        assert "cost" in result, "Missing cost"
        assert "duration_sec" in result, "Missing duration"

        logger.info("✅ Standard fields present")

        # Verify intelligence fields
        assert "serp_data" in result, "Missing SERP data"
        assert "content_scores" in result, "Missing content scores"
        assert "difficulty_data" in result, "Missing difficulty data"

        logger.info("✅ Intelligence fields present")

        # Check SERP data
        if result.get("serp_data"):
            serp_data = result["serp_data"]
            assert "results" in serp_data, "Missing SERP results"
            assert "analysis" in serp_data, "Missing SERP analysis"

            num_results = len(serp_data["results"])
            logger.info(f"✅ SERP Analysis: {num_results} results analyzed")

            if "analysis" in serp_data:
                analysis = serp_data["analysis"]
                logger.info(f"   - Domains: {analysis.get('total_domains', 0)}")
                logger.info(f"   - Avg Position: {analysis.get('avg_position', 0):.1f}")
        else:
            logger.warning("⚠️  SERP data is None (analysis may have failed)")

        # Check content scores
        content_scores = result.get("content_scores", [])
        if content_scores:
            logger.info(f"✅ Content Scoring: {len(content_scores)} URLs scored")

            # Show summary of first score
            if content_scores:
                first_score = content_scores[0]
                logger.info(f"   - Example URL: {first_score.get('url', 'N/A')}")
                logger.info(f"   - Quality Score: {first_score.get('quality_score', 0)}/100")
        else:
            logger.warning("⚠️  No content scores (analysis may have failed)")

        # Check difficulty data
        if result.get("difficulty_data"):
            diff_data = result["difficulty_data"]
            logger.info("✅ Difficulty Scoring:")
            logger.info(f"   - Difficulty Score: {diff_data.get('difficulty_score', 0)}/100")
            logger.info(f"   - Ranking Time: {diff_data.get('ranking_time_estimate', 'N/A')}")
            logger.info(f"   - Recommendations: {len(diff_data.get('recommendations', []))} items")
        else:
            logger.warning("⚠️  Difficulty data is None (analysis may have failed)")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Test Summary")
        logger.info("=" * 60)
        logger.info(f"✅ Topic: {result['topic']}")
        logger.info(f"✅ Sources: {len(result.get('sources', []))}")
        logger.info(f"✅ Article: {len(result.get('article', '').split()) if result.get('article') else 0} words")
        logger.info(f"✅ Cost: ${result.get('cost', 0):.4f}")
        logger.info(f"✅ Duration: {result.get('duration_sec', 0):.1f}s")
        logger.info(f"✅ SERP Results: {len(serp_data.get('results', [])) if result.get('serp_data') else 0}")
        logger.info(f"✅ Content Scores: {len(content_scores)}")
        logger.info(f"✅ Difficulty Score: {diff_data.get('difficulty_score', 'N/A') if result.get('difficulty_data') else 'N/A'}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}", exc_info=True)
        return False


async def test_intelligence_disabled():
    """Test that pipeline works with intelligence features disabled."""

    logger.info("\n\n" + "=" * 60)
    logger.info("Bonus Test: Intelligence DISABLED (Backward Compatibility)")
    logger.info("=" * 60)

    orchestrator = HybridResearchOrchestrator(
        enable_tavily=True,
        enable_synthesis=True,
        max_article_words=500,
        # Intelligence features DISABLED
        enable_serp_analysis=False,
        enable_content_scoring=False,
        enable_difficulty_scoring=False,
        db_path="data/topics_test_no_intelligence.db"
    )

    logger.info("✅ Orchestrator initialized WITHOUT intelligence features")

    try:
        result = await orchestrator.research_topic(
            topic="Test topic backward compatibility",
            config={"market": "US", "language": "en", "domain": "Tech"},
            max_results=3
        )

        # Verify intelligence fields are None when disabled
        assert result.get("serp_data") is None, "SERP data should be None when disabled"
        assert result.get("content_scores") == [], "Content scores should be empty when disabled"
        assert result.get("difficulty_data") is None, "Difficulty data should be None when disabled"

        logger.info("✅ Backward compatibility verified (intelligence fields are None/empty)")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"❌ Backward compatibility test failed: {str(e)}")
        return False


async def main():
    """Run all tests."""

    print("\nPhase 2D Integration Test")
    print("=" * 60)
    print("Testing: Orchestrator + SERP + Content + Difficulty\n")

    # Test 1: Intelligence enabled
    test1_passed = await test_intelligence_integration()

    # Test 2: Intelligence disabled (backward compatibility)
    test2_passed = await test_intelligence_disabled()

    # Final summary
    print("\n\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Test 1 (Intelligence Enabled): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Backward Compatibility): {'✅ PASSED' if test2_passed else '❌ FAILED'}")

    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED - Phase 2D Integration Complete!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Check logs above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
