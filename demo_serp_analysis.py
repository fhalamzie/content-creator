"""
Demo: SERP Analysis with DuckDuckGo

Demonstrates:
1. Real search for a topic
2. Analyze SERP results
3. Save to database
4. Historical tracking
"""

from datetime import datetime
from src.research.serp_analyzer import SERPAnalyzer
from src.database.sqlite_manager import SQLiteManager
from src.models.topic import Topic, TopicSource, TopicStatus


def main():
    print("=" * 60)
    print("SERP Analysis Demo")
    print("=" * 60)

    # Initialize
    analyzer = SERPAnalyzer()
    db = SQLiteManager(db_path="data/topics.db")

    # Create or get a test topic
    topic_id = "proptech-trends-2025"
    topic = db.get_topic(topic_id)

    if not topic:
        print(f"\nCreating new topic: {topic_id}")
        topic = Topic(
            id=topic_id,
            title="PropTech Trends 2025",
            source=TopicSource.MANUAL,
            discovered_at=datetime.utcnow(),
            domain="PropTech",
            market="Germany",
            language="de",
            status=TopicStatus.DISCOVERED
        )
        db.insert_topic(topic)
    else:
        print(f"\nUsing existing topic: {topic.title}")

    # Search DuckDuckGo
    print("\n" + "=" * 60)
    print("Step 1: Search DuckDuckGo")
    print("=" * 60)

    search_query = "PropTech trends 2025"
    print(f"\nQuery: '{search_query}'")
    print("Searching...")

    try:
        results = analyzer.search(search_query, max_results=10)
        print(f"\nFound {len(results)} results!\n")

        # Display first 3 results
        for i, result in enumerate(results[:3], 1):
            print(f"{i}. {result.title}")
            print(f"   Domain: {result.domain}")
            print(f"   URL: {result.url[:60]}...")
            print()

        # Analyze SERP
        print("=" * 60)
        print("Step 2: Analyze SERP")
        print("=" * 60)

        analysis = analyzer.analyze_serp(results)

        print(f"\nTotal results: {analysis['total_results']}")
        print(f"Unique domains: {analysis['unique_domains']}")
        print(f"\nTop 3 domains:")
        for i, domain in enumerate(analysis['top_3_domains'], 1):
            print(f"  {i}. {domain}")

        print(f"\nDomain Authority Estimates:")
        for domain, authority in analysis['domain_authority_estimate'].items():
            print(f"  - {domain}: {authority}")

        print(f"\nAverage title length: {analysis['avg_title_length']} chars")
        print(f"Average snippet length: {analysis['avg_snippet_length']} chars")

        # Save to database
        print("\n" + "=" * 60)
        print("Step 3: Save to Database")
        print("=" * 60)

        result_dicts = analyzer.results_to_dict(results)
        count = db.save_serp_results(topic_id, search_query, result_dicts)

        print(f"\nSaved {count} SERP results to database")

        # Get latest snapshot
        print("\n" + "=" * 60)
        print("Step 4: Retrieve Latest Snapshot")
        print("=" * 60)

        snapshot = db.get_latest_serp_snapshot(topic_id)

        if snapshot:
            print(f"\nLatest snapshot from: {snapshot['searched_at']}")
            print(f"Query: {snapshot['search_query']}")
            print(f"Results: {len(snapshot['results'])}")

        # Get history
        print("\n" + "=" * 60)
        print("Step 5: SERP History")
        print("=" * 60)

        history = db.get_serp_history(topic_id)

        print(f"\nFound {len(history)} historical snapshots")
        for i, snap in enumerate(history, 1):
            print(f"{i}. {snap['searched_at']}: {len(snap['results'])} results")

        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)
        print("\n✅ SERP Analysis infrastructure is working!")
        print("\nNext steps:")
        print("- Run this demo again later to track SERP changes")
        print("- Use compare_snapshots() to detect ranking changes")
        print("- Build Phase 2B: Content Scoring")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nPossible reasons:")
        print("- Network connection issue")
        print("- DuckDuckGo rate limiting")
        print("- Try again in a few minutes")


if __name__ == "__main__":
    main()
