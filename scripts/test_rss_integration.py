"""
Test RSS Collector Integration

Quick test script to verify RSS collector integration with Hybrid Research Orchestrator.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_rss_integration():
    """Test RSS collector integration."""

    logger.info("=== Testing RSS Collector Integration ===")

    # Initialize orchestrator with RSS enabled
    orchestrator = HybridResearchOrchestrator(
        enable_tavily=False,  # Disable paid services
        enable_autocomplete=False,
        enable_trends=False,
        enable_rss=True,  # ENABLE RSS
        topic_discovery_language="en",
        topic_discovery_region="US"
    )

    logger.info("Orchestrator initialized with RSS enabled")

    # Test with simple keywords
    test_keywords = ["PropTech", "Smart Buildings", "IoT"]
    test_tags = ["Real Estate", "Technology"]

    logger.info("Testing RSS collector with keywords: %s", test_keywords)

    # Call discover_topics_from_collectors
    result = await orchestrator.discover_topics_from_collectors(
        consolidated_keywords=test_keywords,
        consolidated_tags=test_tags,
        max_topics_per_collector=5,
        domain="technology",
        vertical="proptech",
        market="US",
        language="en"
    )

    logger.info("=== Results ===")
    logger.info("Total topics discovered: %d", result["total_topics"])
    logger.info("Topics by source:")
    for source, topics in result["topics_by_source"].items():
        logger.info("  - %s: %d topics", source, len(topics))
        if topics:
            logger.info("    Sample: %s", topics[:3])

    # Check RSS topics specifically
    rss_topics = result["topics_by_source"].get("rss", [])
    if rss_topics:
        logger.info("\n✅ RSS Integration SUCCESSFUL!")
        logger.info("RSS Topics Found: %d", len(rss_topics))
        logger.info("Sample RSS topics:")
        for i, topic in enumerate(rss_topics[:5], 1):
            logger.info("  %d. %s", i, topic)
    else:
        logger.warning("\n⚠️ No RSS topics found. Check if feeds are accessible.")

    return result


if __name__ == "__main__":
    asyncio.run(test_rss_integration())
