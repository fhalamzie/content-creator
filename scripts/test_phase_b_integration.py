#!/usr/bin/env python3
"""
Test Phase B Integration: Competitor Feed Discovery

Demonstrates how Phase B automatically discovers RSS feeds during
competitor research in the Hybrid Research Orchestrator.

Usage:
    python scripts/test_phase_b_integration.py
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
from src.collectors.rss_feed_database import RSSFeedDatabase
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_phase_b_integration():
    """
    Test Phase B: Discover feeds from competitors during research.

    Flow:
    1. Get current feed count
    2. Run competitor research with discover_feeds=True
    3. Show discovered feeds
    4. Show updated feed count
    """
    print("\n" + "=" * 60)
    print("🧪 Testing Phase B: Competitor Feed Discovery Integration")
    print("=" * 60 + "\n")

    # Get initial feed count
    database = RSSFeedDatabase()
    initial_stats = database.get_statistics()
    print(f"📊 Initial Database Stats:")
    print(f"   Total feeds: {initial_stats['total_feeds']}")
    print(f"   Total domains: {initial_stats['total_domains']}")
    print(f"   Total verticals: {initial_stats['total_verticals']}\n")

    # Initialize orchestrator
    print("🔧 Initializing Hybrid Research Orchestrator...")
    orchestrator = HybridResearchOrchestrator(
        enable_tavily=False,  # Disable paid services for test
        enable_searxng=False,
        enable_gemini=True,   # Enable Gemini for competitor research
        enable_autocomplete=False,
        enable_trends=False
    )
    print("   ✅ Orchestrator initialized\n")

    # Test data: PropTech niche
    test_keywords = ["PropTech", "Smart Buildings", "IoT", "Real Estate Technology"]
    customer_info = {
        "market": "US",
        "vertical": "proptech",
        "language": "en",
        "domain": "technology"
    }

    print(f"🔍 Running competitor research...")
    print(f"   Keywords: {', '.join(test_keywords[:3])}")
    print(f"   Market: {customer_info['market']}")
    print(f"   Vertical: {customer_info['vertical']}")
    print(f"   Feed Discovery: ENABLED\n")

    try:
        # Run competitor research with feed discovery enabled
        result = await orchestrator.research_competitors(
            keywords=test_keywords,
            customer_info=customer_info,
            max_competitors=10,
            discover_feeds=True  # ENABLE PHASE B
        )

        # Display results
        print("✅ Competitor Research Complete!")
        print("=" * 60)
        print(f"Competitors found:     {len(result.get('competitors', []))}")
        print(f"Additional keywords:   {len(result.get('additional_keywords', []))}")
        print(f"Market topics:         {len(result.get('market_topics', []))}")
        print("=" * 60 + "\n")

        # Check if feeds were discovered
        if "rss_feeds" in result:
            feed_result = result["rss_feeds"]

            print("🔍 RSS Feed Discovery Results:")
            print("=" * 60)
            print(f"Feeds discovered:      {feed_result['feeds_discovered']}")
            print(f"Feeds added to DB:     {feed_result['feeds_added']}")
            print(f"Cost:                  ${feed_result['cost']:.4f}")

            if feed_result.get("error"):
                print(f"⚠️  Error:              {feed_result['error']}")

            print("=" * 60 + "\n")

            # Show discovered feeds
            if feed_result['feeds']:
                print("📡 Discovered Feeds:")
                print("=" * 60)
                for i, feed in enumerate(feed_result['feeds'][:5], 1):
                    print(f"{i}. {feed.title}")
                    print(f"   URL: {feed.url}")
                    print(f"   Quality: {feed.quality_score:.2f}")
                    print()

                if len(feed_result['feeds']) > 5:
                    print(f"   ... and {len(feed_result['feeds']) - 5} more feeds\n")
        else:
            print("⚠️  Feed discovery was not enabled or returned no results\n")

        # Get updated feed count
        final_stats = database.get_statistics()
        feeds_added = final_stats['total_feeds'] - initial_stats['total_feeds']

        print("📊 Final Database Stats:")
        print("=" * 60)
        print(f"Total feeds:           {final_stats['total_feeds']} (+{feeds_added})")
        print(f"Total domains:         {final_stats['total_domains']}")
        print(f"Total verticals:       {final_stats['total_verticals']}")
        print("=" * 60 + "\n")

        # Show some competitors
        if result.get('competitors'):
            print("🏢 Discovered Competitors:")
            print("=" * 60)
            for i, comp in enumerate(result['competitors'][:5], 1):
                print(f"{i}. {comp.get('name', 'Unknown')}")
                print(f"   URL: {comp.get('url', 'N/A')}")
                print(f"   Topics: {', '.join(comp.get('topics', [])[:3])}")
                print()

            if len(result['competitors']) > 5:
                print(f"   ... and {len(result['competitors']) - 5} more competitors\n")

        print("✅ Phase B Integration Test Complete!")
        print("\n💡 Key Takeaways:")
        print("   - Competitor research now automatically discovers RSS feeds")
        print("   - Feeds are auto-categorized and added to the database")
        print("   - Database grows continuously as you research new niches")
        print("   - 100% FREE (uses Gemini free tier)\n")

    except Exception as e:
        logger.error("test_failed", error=str(e), exc_info=True)
        print(f"\n❌ Test failed: {str(e)}\n")


async def test_manual_feed_discovery():
    """
    Test manual feed discovery from specific competitor URLs.

    Useful when you want to discover feeds without running full
    competitor research.
    """
    print("\n" + "=" * 60)
    print("🧪 Testing Manual Feed Discovery")
    print("=" * 60 + "\n")

    # Initialize orchestrator
    orchestrator = HybridResearchOrchestrator(
        enable_gemini=True
    )

    # Test with a few well-known tech blogs
    competitor_urls = [
        "https://techcrunch.com",
        "https://venturebeat.com",
        "https://thenextweb.com"
    ]

    print(f"🔍 Discovering feeds from {len(competitor_urls)} websites...")
    for url in competitor_urls:
        print(f"   - {url}")
    print()

    try:
        result = await orchestrator.discover_competitor_feeds(
            competitor_urls=competitor_urls,
            hint_domain="technology",
            hint_vertical="general"
        )

        print("✅ Discovery Complete!")
        print("=" * 60)
        print(f"Feeds discovered:      {result['feeds_discovered']}")
        print(f"Feeds added to DB:     {result['feeds_added']}")
        print("=" * 60 + "\n")

        if result['feeds']:
            print("📡 Discovered Feeds:")
            for i, feed in enumerate(result['feeds'], 1):
                print(f"{i}. {feed.title}")
                print(f"   URL: {feed.url}")
                print(f"   Quality: {feed.quality_score:.2f}")
                print()

        print("✅ Manual Discovery Test Complete!\n")

    except Exception as e:
        logger.error("manual_test_failed", error=str(e), exc_info=True)
        print(f"\n❌ Test failed: {str(e)}\n")


async def main():
    """Main entry point."""
    print("\n🚀 Phase B Integration Test Suite")
    print("=" * 60 + "\n")

    print("Select test to run:")
    print("1. Full Integration Test (competitor research + feed discovery)")
    print("2. Manual Feed Discovery Test (specific URLs)")
    print("3. Run both tests")
    print()

    choice = input("Enter choice (1-3, or q to quit): ").strip()

    if choice == "1":
        await test_phase_b_integration()
    elif choice == "2":
        await test_manual_feed_discovery()
    elif choice == "3":
        await test_phase_b_integration()
        await test_manual_feed_discovery()
    elif choice.lower() == "q":
        print("\n👋 Exiting...\n")
        return
    else:
        print("\n❌ Invalid choice. Exiting.\n")
        return


if __name__ == "__main__":
    asyncio.run(main())
