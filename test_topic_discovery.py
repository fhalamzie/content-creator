"""
Test Script: Topic Discovery Integration
Tests the improvement in topic diversity with real collectors.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator


async def test_topic_discovery():
    """Test topic discovery with and without collectors."""

    # Test URL (PropTech example)
    test_url = "https://www.propstack.de"

    print("=" * 80)
    print("🧪 TOPIC DISCOVERY INTEGRATION TEST")
    print("=" * 80)
    print(f"\n📍 Test URL: {test_url}")
    print(f"🎯 Goal: Compare topic diversity with/without collectors\n")

    # ===== TEST 1: WITHOUT COLLECTORS (Baseline) =====
    print("\n" + "=" * 80)
    print("📊 TEST 1: WITHOUT COLLECTORS (Baseline)")
    print("=" * 80)

    orchestrator_baseline = HybridResearchOrchestrator(
        enable_autocomplete=False,
        enable_trends=False,
        enable_tavily=False
    )

    try:
        print("\n⏳ Stage 1: Extracting keywords from website...")
        stage1 = await orchestrator_baseline.extract_website_keywords(test_url, max_keywords=50)

        if "error" in stage1:
            print(f"❌ Stage 1 failed: {stage1['error']}")
            print("\n⚠️  Using fallback keywords for testing...")
            keywords = ["PropTech", "Immobilienverwaltung", "Digitalisierung", "SaaS", "Software"]
            tags = ["B2B", "Enterprise", "Property Management"]
        else:
            keywords = stage1.get("keywords", [])
            tags = stage1.get("tags", [])
            print(f"✅ Found {len(keywords)} keywords, {len(tags)} tags")

        print("\n⏳ Stage 4: Discovering topics (WITHOUT collectors)...")
        baseline_topics = await orchestrator_baseline.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags,
            max_topics_per_collector=10
        )

        print(f"\n📈 BASELINE RESULTS:")
        print(f"   Total Topics: {baseline_topics['total_topics']}")
        print(f"\n   Topics by Source:")
        for source, topics in baseline_topics['topics_by_source'].items():
            print(f"   - {source}: {len(topics)} topics")

        print(f"\n   Sample Topics (first 10):")
        for i, topic in enumerate(baseline_topics['discovered_topics'][:10], 1):
            print(f"   {i}. {topic}")

    except Exception as e:
        print(f"\n❌ Baseline test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return

    # ===== TEST 2: WITH COLLECTORS (Improved) =====
    print("\n\n" + "=" * 80)
    print("🚀 TEST 2: WITH COLLECTORS (Improved)")
    print("=" * 80)

    orchestrator_improved = HybridResearchOrchestrator(
        enable_autocomplete=True,
        enable_trends=True,
        topic_discovery_language="de",  # German for PropTech
        topic_discovery_region="DE",
        enable_tavily=False
    )

    try:
        print("\n⏳ Stage 4: Discovering topics (WITH collectors)...")
        improved_topics = await orchestrator_improved.discover_topics_from_collectors(
            consolidated_keywords=keywords,
            consolidated_tags=tags,
            max_topics_per_collector=10
        )

        print(f"\n📈 IMPROVED RESULTS:")
        print(f"   Total Topics: {improved_topics['total_topics']}")
        print(f"\n   Topics by Source:")
        for source, topics in improved_topics['topics_by_source'].items():
            print(f"   - {source}: {len(topics)} topics")

        print(f"\n   Sample Topics (first 15):")
        for i, topic in enumerate(improved_topics['discovered_topics'][:15], 1):
            print(f"   {i}. {topic}")

        # Show autocomplete-specific topics
        if 'autocomplete' in improved_topics['topics_by_source']:
            autocomplete_topics = improved_topics['topics_by_source']['autocomplete']
            if autocomplete_topics:
                print(f"\n   🔍 Autocomplete Topics (Questions):")
                for i, topic in enumerate(autocomplete_topics[:10], 1):
                    print(f"   {i}. {topic}")

        # Show trends-specific topics
        if 'trends' in improved_topics['topics_by_source']:
            trends_topics = improved_topics['topics_by_source']['trends']
            if trends_topics:
                print(f"\n   📈 Trends Topics (Related Queries):")
                for i, topic in enumerate(trends_topics[:10], 1):
                    print(f"   {i}. {topic}")

    except Exception as e:
        print(f"\n❌ Improved test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return

    # ===== COMPARISON =====
    print("\n\n" + "=" * 80)
    print("📊 COMPARISON")
    print("=" * 80)

    baseline_count = baseline_topics['total_topics']
    improved_count = improved_topics['total_topics']
    improvement = ((improved_count - baseline_count) / baseline_count * 100) if baseline_count > 0 else 0

    print(f"\n   Baseline Topics:  {baseline_count}")
    print(f"   Improved Topics:  {improved_count}")
    print(f"   Improvement:      +{improvement:.1f}%")
    print(f"   Multiplier:       {improved_count / baseline_count:.1f}x" if baseline_count > 0 else "   Multiplier:       N/A")

    # New topics from collectors
    baseline_set = set(baseline_topics['discovered_topics'])
    improved_set = set(improved_topics['discovered_topics'])
    new_topics = improved_set - baseline_set

    print(f"\n   New Topics from Collectors: {len(new_topics)}")
    if new_topics:
        print(f"\n   Sample New Topics (first 10):")
        for i, topic in enumerate(list(new_topics)[:10], 1):
            print(f"   {i}. {topic}")

    # Success criteria
    print("\n\n" + "=" * 80)
    print("✅ SUCCESS CRITERIA")
    print("=" * 80)

    success = True

    if improved_count > baseline_count:
        print(f"   ✅ More topics generated ({improved_count} vs {baseline_count})")
    else:
        print(f"   ❌ No improvement in topic count")
        success = False

    if 'autocomplete' in improved_topics['topics_by_source'] and improved_topics['topics_by_source']['autocomplete']:
        print(f"   ✅ Autocomplete collector working ({len(improved_topics['topics_by_source']['autocomplete'])} topics)")
    else:
        print(f"   ⚠️  Autocomplete collector returned no topics (may be rate limited)")

    if 'trends' in improved_topics['topics_by_source'] and improved_topics['topics_by_source']['trends']:
        print(f"   ✅ Trends collector working ({len(improved_topics['topics_by_source']['trends'])} topics)")
    else:
        print(f"   ⚠️  Trends collector returned no topics (may be rate limited or no data)")

    if improvement >= 50:
        print(f"   ✅ Significant improvement ({improvement:.1f}% increase)")
    elif improvement > 0:
        print(f"   ⚠️  Moderate improvement ({improvement:.1f}% increase)")
    else:
        print(f"   ❌ No improvement")
        success = False

    print("\n" + "=" * 80)
    if success:
        print("🎉 TEST PASSED: Topic discovery integration successful!")
    else:
        print("⚠️  TEST WARNING: Integration working but with limited improvement")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_topic_discovery())
