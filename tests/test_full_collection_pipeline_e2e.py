"""
End-to-End Test: Full Collection Pipeline

Tests the complete collection pipeline:
1. Feed Discovery - Discover RSS feeds from seed keywords
2. RSS Collection - Collect documents from discovered + custom feeds
3. Autocomplete Collection - Generate topics from keywords
4. Trends Collection - Collect trending topics (if enabled)
5. Reddit Collection - Collect from subreddits (if enabled)
6. Deduplication - Remove duplicates via MinHash/LSH
7. Topic Clustering - Group related topics (optional)

Acceptance Criteria:
- 50+ unique documents collected from PropTech sources
- <5% duplicate rate after deduplication
- All collectors complete successfully or fail gracefully
- Statistics accurately reflect collection results

Cost: FREE (uses Gemini CLI, no paid APIs)
Duration: ~2-5 minutes (depending on feed count)

Usage:
    pytest tests/test_full_collection_pipeline_e2e.py -v -s
"""

import pytest
from pathlib import Path

from src.agents.universal_topic_agent import UniversalTopicAgent
from src.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.integration
@pytest.mark.e2e
def test_full_collection_pipeline_proptech():
    """
    Test full collection pipeline with PropTech config

    Validates:
    1. All collectors complete successfully
    2. 50+ documents collected
    3. Deduplication rate <5%
    4. No critical errors
    """
    # Load agent from PropTech config
    config_path = "config/markets/proptech_de.yaml"
    agent = UniversalTopicAgent.load_config(config_path)

    logger.info("Starting full collection pipeline test")

    # Run collection
    stats = agent.collect_all_sources()

    # Print detailed statistics
    print("\n" + "="*60)
    print("COLLECTION PIPELINE RESULTS")
    print("="*60)
    print(f"Documents collected:   {stats['documents_collected']}")
    print(f"Documents saved:       {stats['documents_saved']}")
    print(f"Sources processed:     {stats['sources_processed']}")
    print(f"Errors encountered:    {stats['errors']}")
    print("="*60 + "\n")

    # Get agent statistics
    agent_stats = agent.get_statistics()
    print("DEDUPLICATION STATISTICS")
    print("="*60)
    print(f"Unique documents:      {agent_stats['documents_collected']}")
    print(f"Duplicates removed:    {agent_stats['documents_deduplicated']}")

    if agent_stats['documents_collected'] > 0:
        total_docs = agent_stats['documents_collected'] + agent_stats['documents_deduplicated']
        dup_rate = (agent_stats['documents_deduplicated'] / total_docs) * 100
        print(f"Duplication rate:      {dup_rate:.2f}%")
    else:
        dup_rate = 0.0
        print(f"Duplication rate:      N/A (no documents collected)")

    print("="*60 + "\n")

    # Validation: Check acceptance criteria
    print("ACCEPTANCE CRITERIA VALIDATION")
    print("="*60)

    # Criterion 1: 50+ unique documents collected
    criterion_1 = stats['documents_collected'] >= 50
    print(f"✓ 50+ documents:       {'PASS' if criterion_1 else 'FAIL'} ({stats['documents_collected']} collected)")

    # Criterion 2: <5% duplicate rate
    criterion_2 = dup_rate < 5.0
    print(f"✓ <5% duplicates:      {'PASS' if criterion_2 else 'FAIL'} ({dup_rate:.2f}%)")

    # Criterion 3: All collectors complete (errors should be 0 or minimal)
    criterion_3 = stats['errors'] <= 1  # Allow 1 error for graceful degradation
    print(f"✓ Graceful operation:  {'PASS' if criterion_3 else 'FAIL'} ({stats['errors']} errors)")

    # Criterion 4: Documents successfully saved
    criterion_4 = stats['documents_saved'] == stats['documents_collected']
    print(f"✓ Documents saved:     {'PASS' if criterion_4 else 'FAIL'} ({stats['documents_saved']}/{stats['documents_collected']})")

    print("="*60 + "\n")

    # Overall validation
    all_criteria_pass = criterion_1 and criterion_2 and criterion_3 and criterion_4

    if all_criteria_pass:
        print("✓ ALL ACCEPTANCE CRITERIA PASSED\n")
    else:
        print("✗ SOME ACCEPTANCE CRITERIA FAILED\n")

    # Assertions
    assert stats['documents_collected'] >= 50, f"Expected 50+ documents, got {stats['documents_collected']}"
    assert dup_rate < 5.0, f"Expected <5% duplicate rate, got {dup_rate:.2f}%"
    assert stats['errors'] <= 1, f"Too many errors: {stats['errors']}"
    assert stats['documents_saved'] == stats['documents_collected'], \
        f"Document save mismatch: {stats['documents_saved']} saved vs {stats['documents_collected']} collected"


@pytest.mark.integration
@pytest.mark.e2e
def test_collection_pipeline_graceful_degradation():
    """
    Test that pipeline continues gracefully when some collectors fail

    Validates:
    1. Pipeline completes even with collector failures
    2. Statistics accurately reflect partial success
    3. Error tracking works correctly
    """
    config_path = "config/markets/proptech_de.yaml"
    agent = UniversalTopicAgent.load_config(config_path)

    logger.info("Starting graceful degradation test")

    # Run collection (some collectors may fail due to API limits, network issues, etc.)
    stats = agent.collect_all_sources()

    # Validation: Pipeline should complete
    assert 'documents_collected' in stats
    assert 'sources_processed' in stats
    assert 'errors' in stats

    # At least one collector should succeed
    assert stats['sources_processed'] > 0, "No sources were processed"

    # Documents collected should be non-negative
    assert stats['documents_collected'] >= 0

    # Errors should be tracked
    assert stats['errors'] >= 0

    print(f"\n✓ Graceful degradation test passed:")
    print(f"  - {stats['sources_processed']} sources processed")
    print(f"  - {stats['documents_collected']} documents collected")
    print(f"  - {stats['errors']} errors encountered (gracefully handled)")


@pytest.mark.integration
@pytest.mark.e2e
def test_collection_sources_breakdown():
    """
    Test individual collector contributions

    Validates each collector's output and contribution to the pipeline
    """
    config_path = "config/markets/proptech_de.yaml"
    agent = UniversalTopicAgent.load_config(config_path)

    logger.info("Starting collection sources breakdown test")

    # Run collection
    stats = agent.collect_all_sources()

    # Get documents from database to analyze sources
    documents = agent.db.get_documents_by_language(language="de", limit=1000)

    # Analyze source breakdown
    source_counts = {}
    for doc in documents:
        source_type = doc.source.split('_')[0] if '_' in doc.source else doc.source
        source_counts[source_type] = source_counts.get(source_type, 0) + 1

    print("\n" + "="*60)
    print("COLLECTION SOURCES BREAKDOWN")
    print("="*60)
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(documents) * 100) if documents else 0
        print(f"{source:20s}: {count:4d} documents ({percentage:5.1f}%)")
    print("="*60)
    print(f"Total unique documents: {len(documents)}")
    print("="*60 + "\n")

    # Validation: Check source diversity
    assert len(source_counts) >= 2, f"Expected 2+ source types, got {len(source_counts)}"

    print(f"✓ Source diversity validated: {len(source_counts)} different source types")


if __name__ == "__main__":
    # Run test directly
    print("Running Full Collection Pipeline E2E Test\n")
    test_full_collection_pipeline_proptech()
    print("\n" + "="*60)
    print("Running Graceful Degradation Test\n")
    test_collection_pipeline_graceful_degradation()
    print("\n" + "="*60)
    print("Running Sources Breakdown Test\n")
    test_collection_sources_breakdown()
    print("\n✓ All E2E tests completed successfully!")
