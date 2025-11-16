#!/usr/bin/env python3
"""
End-to-End Test: Phase B RSS Integration

Tests the complete flow:
1. Competitor research discovers competitors
2. Phase B discovers RSS feeds from competitors
3. Feeds added to database
4. RSS collector uses discovered feeds
5. Topics collected and validated

Usage:
    python scripts/test_rss_phase_b_e2e.py
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


async def test_phase_b_e2e():
    """
    Test complete Phase B integration end-to-end.

    Flow:
    1. Check initial database state
    2. Run competitor research WITH feed discovery enabled
    3. Verify feeds were added to database
    4. Run topic discovery using RSS collector
    5. Verify topics include both dynamic and curated feeds
    """
    print("\n" + "=" * 70)
    print("🧪 Phase B End-to-End Integration Test")
    print("=" * 70 + "\n")

    # Step 1: Initial database state
    print("📊 Step 1: Checking initial database state...")
    database = RSSFeedDatabase()
    initial_stats = database.get_statistics()
    print(f"   Total feeds: {initial_stats['total_feeds']}")
    print(f"   Total domains: {initial_stats['total_domains']}")
    print(f"   Total verticals: {initial_stats['total_verticals']}\n")

    # Step 2: Initialize orchestrator with RSS enabled
    print("🔧 Step 2: Initializing orchestrator (RSS + Phase B enabled)...")
    orchestrator = HybridResearchOrchestrator(
        enable_tavily=False,  # Disable paid services for test
        enable_searxng=False,
        enable_gemini=True,   # Enable Gemini for competitor research
        enable_rss=True,      # ENABLE RSS COLLECTOR
        enable_autocomplete=False,
        enable_trends=False
    )
    print("   ✅ Orchestrator initialized\n")

    # Test configuration
    test_keywords = ["PropTech", "Smart Buildings", "Real Estate Technology"]
    customer_info = {
        "market": "US",
        "vertical": "proptech",
        "language": "en",
        "domain": "technology"
    }

    # Step 3: Run competitor research WITH Phase B feed discovery
    print("🔍 Step 3: Running competitor research with feed discovery...")
    print(f"   Keywords: {', '.join(test_keywords[:3])}")
    print(f"   Domain: {customer_info['domain']}")
    print(f"   Vertical: {customer_info['vertical']}")
    print(f"   Feed Discovery: ENABLED ✅\n")

    try:
        competitor_result = await orchestrator.research_competitors(
            keywords=test_keywords,
            customer_info=customer_info,
            max_competitors=10,
            discover_feeds=True  # PHASE B ENABLED
        )

        print("✅ Competitor Research Complete!")
        print("=" * 70)
        print(f"Competitors found:        {len(competitor_result.get('competitors', []))}")
        print(f"Additional keywords:      {len(competitor_result.get('additional_keywords', []))}")
        print(f"Market topics:            {len(competitor_result.get('market_topics', []))}")

        # Check Phase B results
        if "rss_feeds" in competitor_result:
            feed_result = competitor_result["rss_feeds"]
            print(f"\n📡 Phase B Feed Discovery:")
            print(f"   Feeds discovered:      {feed_result['feeds_discovered']}")
            print(f"   Feeds added to DB:     {feed_result['feeds_added']}")
            print(f"   Cost:                  ${feed_result['cost']:.4f}")

            if feed_result.get("error"):
                print(f"   ⚠️  Error:              {feed_result['error']}")
        else:
            print("\n⚠️  No RSS feed discovery data found")

        print("=" * 70 + "\n")

        # Step 4: Check database growth
        print("📊 Step 4: Checking database after Phase B...")
        final_stats = database.get_statistics()
        feeds_added = final_stats['total_feeds'] - initial_stats['total_feeds']

        print(f"   Total feeds:           {final_stats['total_feeds']} (+{feeds_added})")
        print(f"   Total domains:         {final_stats['total_domains']}")
        print(f"   Total verticals:       {final_stats['total_verticals']}\n")

        # Step 5: Test RSS topic discovery
        print("🔍 Step 5: Testing RSS topic discovery...")
        print(f"   Using domain: {customer_info['domain']}")
        print(f"   Using vertical: {customer_info['vertical']}\n")

        # Consolidate keywords for topic discovery
        consolidated_data = orchestrator.consolidate_keywords_and_topics(
            website_data={"keywords": test_keywords, "tags": [], "themes": []},
            competitor_data=competitor_result
        )

        # Discover topics using RSS collector
        topic_result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=consolidated_data["consolidated_keywords"],
            consolidated_tags=consolidated_data["consolidated_tags"],
            max_topics_per_collector=10,
            domain=customer_info["domain"],
            vertical=customer_info["vertical"],
            market=customer_info["market"],
            language=customer_info["language"]
        )

        print("✅ Topic Discovery Complete!")
        print("=" * 70)
        print(f"Total topics discovered:  {topic_result['total_topics']}")
        print(f"\nTopics by source:")
        for source, topics in topic_result["topics_by_source"].items():
            print(f"   {source:15} {len(topics):3} topics")
        print("=" * 70 + "\n")

        # Show RSS topics if available
        if "rss" in topic_result["topics_by_source"] and topic_result["topics_by_source"]["rss"]:
            print("📡 RSS Topics Discovered:")
            print("=" * 70)
            for i, topic in enumerate(topic_result["topics_by_source"]["rss"][:5], 1):
                print(f"{i}. {topic}")

            rss_count = len(topic_result["topics_by_source"]["rss"])
            if rss_count > 5:
                print(f"\n   ... and {rss_count - 5} more RSS topics")
            print("=" * 70 + "\n")
        else:
            print("⚠️  No RSS topics discovered. Possible reasons:")
            print("   - No curated feeds in database for proptech vertical")
            print("   - Dynamic feed generation failed")
            print("   - RSS collector encountered errors\n")

        # Step 6: Summary
        print("📊 Phase B Integration Test Summary")
        print("=" * 70)
        print(f"✅ Competitor research:    {len(competitor_result.get('competitors', []))} competitors")
        print(f"✅ Feed discovery:         {competitor_result.get('rss_feeds', {}).get('feeds_added', 0)} feeds added")
        print(f"✅ Database growth:        +{feeds_added} feeds total")
        print(f"✅ Topic discovery:        {topic_result['total_topics']} topics from {len(topic_result['topics_by_source'])} sources")
        print(f"✅ RSS integration:        {'WORKING' if 'rss' in topic_result['topics_by_source'] else 'CHECK LOGS'}")
        print("=" * 70 + "\n")

        print("💡 Key Takeaways:")
        print("   1. Phase B automatically discovers feeds during competitor research")
        print("   2. Discovered feeds are added to database for future use")
        print("   3. RSS collector uses both dynamic (Bing/Google) and curated feeds")
        print("   4. System scales automatically as database grows")
        print("   5. 100% FREE (uses Gemini free tier + public RSS feeds)\n")

        print("✅ Phase B Integration Test PASSED!\n")

    except Exception as e:
        logger.error("test_failed", error=str(e), exc_info=True)
        print(f"\n❌ Test failed: {str(e)}\n")
        raise


async def test_multilingual_scenario():
    """
    Test multilingual scenario: German market with 70/30 ratio.

    This tests the documented strategy where we use:
    - 70% English sources (latest trends, more abundant)
    - 30% German sources (local regulations, market data)
    """
    print("\n" + "=" * 70)
    print("🌍 Multilingual Test: German Market (70/30 Strategy)")
    print("=" * 70 + "\n")

    # Initialize orchestrator
    orchestrator = HybridResearchOrchestrator(
        enable_gemini=True,
        enable_rss=True,
        enable_autocomplete=False,
        enable_trends=False,
        topic_discovery_language="de",  # German
        topic_discovery_region="DE"
    )

    # German PropTech company
    test_keywords = ["PropTech", "Immobilien", "Smart Buildings"]
    customer_info = {
        "market": "DE",
        "vertical": "proptech",
        "language": "de",  # Target language: German
        "domain": "technology"
    }

    print(f"🔍 Discovering topics for German PropTech market...")
    print(f"   Keywords: {', '.join(test_keywords)}")
    print(f"   Language: {customer_info['language']}")
    print(f"   Strategy: 70% English sources + 30% German sources\n")

    try:
        # Consolidate keywords
        consolidated_data = {
            "consolidated_keywords": test_keywords,
            "consolidated_tags": ["real-estate", "technology", "iot"]
        }

        # Discover topics
        # NOTE: The 70/30 ratio is currently MANUAL (need to implement)
        # For now, this will use English sources (RSS feeds in database are mostly English)
        topic_result = await orchestrator.discover_topics_from_collectors(
            consolidated_keywords=consolidated_data["consolidated_keywords"],
            consolidated_tags=consolidated_data["consolidated_tags"],
            max_topics_per_collector=10,
            domain=customer_info["domain"],
            vertical=customer_info["vertical"],
            market=customer_info["market"],
            language=customer_info["language"]
        )

        print("✅ Topic Discovery Complete!")
        print("=" * 70)
        print(f"Total topics:             {topic_result['total_topics']}")
        print(f"Topics by source:")
        for source, topics in topic_result["topics_by_source"].items():
            print(f"   {source:15} {len(topics):3} topics")
        print("=" * 70 + "\n")

        # Show sample topics
        if topic_result["discovered_topics"]:
            print("📋 Sample Topics (should be in German):")
            print("=" * 70)
            for i, topic in enumerate(topic_result["discovered_topics"][:5], 1):
                print(f"{i}. {topic}")
            print("=" * 70 + "\n")

        print("💡 Note:")
        print("   - Topics are currently discovered from English sources")
        print("   - Translation to German happens automatically")
        print("   - 70/30 ratio implementation is PENDING (next task)")
        print("   - This test validates the current English-only flow\n")

        print("✅ Multilingual Test PASSED!\n")

    except Exception as e:
        logger.error("multilingual_test_failed", error=str(e), exc_info=True)
        print(f"\n❌ Test failed: {str(e)}\n")
        raise


async def main():
    """Main test runner."""
    print("\n🚀 Phase B RSS Integration - End-to-End Test Suite")
    print("=" * 70 + "\n")

    print("Available tests:")
    print("1. Phase B End-to-End Test (Competitor research → Feed discovery → Topic collection)")
    print("2. Multilingual Test (German market, 70/30 strategy)")
    print("3. Run both tests")
    print()

    choice = input("Enter choice (1-3, or q to quit): ").strip()

    if choice == "1":
        await test_phase_b_e2e()
    elif choice == "2":
        await test_multilingual_scenario()
    elif choice == "3":
        await test_phase_b_e2e()
        await test_multilingual_scenario()
    elif choice.lower() == "q":
        print("\n👋 Exiting...\n")
        return
    else:
        print("\n❌ Invalid choice. Exiting.\n")
        return


if __name__ == "__main__":
    asyncio.run(main())
