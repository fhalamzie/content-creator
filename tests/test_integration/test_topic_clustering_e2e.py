"""
Topic Clustering E2E Test

Tests the full topic clustering pipeline on a realistic dataset:
- TF-IDF feature extraction
- HDBSCAN clustering
- LLM-based label generation
- Statistics tracking

No mocks - tests actual clustering behavior on diverse documents.
"""

import pytest
from datetime import datetime
from pathlib import Path

from src.processors.topic_clusterer import TopicClusterer, ClusteringError
from src.models.document import Document


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory"""
    cache_dir = tmp_path / "clustering_e2e"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def realistic_documents():
    """
    Create realistic document set with diverse topics

    Topics: PropTech (3 docs), Cloud Computing (3 docs),
            GDPR/Privacy (2 docs), AI/ML (2 docs)

    Total: 10 documents across 4 semantic topics
    """
    docs = [
        # PropTech cluster (3 docs)
        Document(
            id="proptech_1",
            source="rss",
            source_url="https://proptech.ai/articles/smart-building-iot",
            title="Smart Building IoT Solutions for Property Management",
            content="Smart building technology integrates IoT sensors for energy management, "
                   "occupancy tracking, and predictive maintenance. PropTech startups are "
                   "revolutionizing property management with real-time data analytics.",
            language="en",
            domain="PropTech",
            market="Germany",
            vertical="PropTech",
            content_hash="hash_proptech_1",
            canonical_url="https://proptech.ai/articles/smart-building-iot",
            published_at=datetime(2025, 11, 1),
            fetched_at=datetime.now()
        ),
        Document(
            id="proptech_2",
            source="rss",
            source_url="https://proptech.ai/articles/digital-twins",
            title="Digital Twin Technology in Real Estate Development",
            content="Digital twins create virtual replicas of buildings for simulation and optimization. "
                   "Property developers use digital twin platforms to reduce construction costs and "
                   "improve energy efficiency in new developments.",
            language="en",
            domain="PropTech",
            market="Germany",
            vertical="PropTech",
            content_hash="hash_proptech_2",
            canonical_url="https://proptech.ai/articles/digital-twins",
            published_at=datetime(2025, 11, 2),
            fetched_at=datetime.now()
        ),
        Document(
            id="proptech_3",
            source="rss",
            source_url="https://proptech.ai/articles/blockchain-real-estate",
            title="Blockchain Applications in Property Transactions",
            content="Blockchain technology enables transparent property ownership records and "
                   "streamlined real estate transactions. Smart contracts automate escrow and "
                   "reduce transaction costs in property transfers.",
            language="en",
            domain="PropTech",
            market="Germany",
            vertical="PropTech",
            content_hash="hash_proptech_3",
            canonical_url="https://proptech.ai/articles/blockchain-real-estate",
            published_at=datetime(2025, 11, 3),
            fetched_at=datetime.now()
        ),

        # Cloud Computing cluster (3 docs)
        Document(
            id="cloud_1",
            source="rss",
            source_url="https://cloud.com/aws-vs-azure",
            title="AWS vs Azure: Enterprise Cloud Platform Comparison",
            content="Comparing AWS and Azure for enterprise workloads. AWS offers broader service "
                   "portfolio while Azure integrates better with Microsoft ecosystem. Cloud migration "
                   "strategies differ based on existing infrastructure.",
            language="en",
            domain="SaaS",
            market="US",
            vertical="Cloud",
            content_hash="hash_cloud_1",
            canonical_url="https://cloud.com/aws-vs-azure",
            published_at=datetime(2025, 11, 4),
            fetched_at=datetime.now()
        ),
        Document(
            id="cloud_2",
            source="rss",
            source_url="https://cloud.com/kubernetes-best-practices",
            title="Kubernetes Container Orchestration Best Practices",
            content="Kubernetes orchestrates containerized applications across cloud infrastructure. "
                   "Best practices include resource limits, health checks, and horizontal pod autoscaling. "
                   "Docker containers deployed on Kubernetes clusters provide scalability.",
            language="en",
            domain="SaaS",
            market="US",
            vertical="Cloud",
            content_hash="hash_cloud_2",
            canonical_url="https://cloud.com/kubernetes-best-practices",
            published_at=datetime(2025, 11, 5),
            fetched_at=datetime.now()
        ),
        Document(
            id="cloud_3",
            source="rss",
            source_url="https://cloud.com/serverless-architecture",
            title="Serverless Computing: Lambda vs Cloud Functions",
            content="Serverless architecture eliminates infrastructure management. AWS Lambda and "
                   "Google Cloud Functions enable event-driven computing with automatic scaling. "
                   "Cost optimization through pay-per-invocation pricing model.",
            language="en",
            domain="SaaS",
            market="US",
            vertical="Cloud",
            content_hash="hash_cloud_3",
            canonical_url="https://cloud.com/serverless-architecture",
            published_at=datetime(2025, 11, 6),
            fetched_at=datetime.now()
        ),

        # GDPR/Privacy cluster (2 docs)
        Document(
            id="gdpr_1",
            source="rss",
            source_url="https://privacy.com/gdpr-compliance",
            title="GDPR Compliance Requirements for SaaS Companies",
            content="GDPR mandates data protection and privacy regulations for EU companies. "
                   "SaaS providers must implement consent management, data portability, and "
                   "right to erasure. Privacy impact assessments required for high-risk processing.",
            language="en",
            domain="SaaS",
            market="Germany",
            vertical="Compliance",
            content_hash="hash_gdpr_1",
            canonical_url="https://privacy.com/gdpr-compliance",
            published_at=datetime(2025, 11, 7),
            fetched_at=datetime.now()
        ),
        Document(
            id="gdpr_2",
            source="rss",
            source_url="https://privacy.com/cookie-consent",
            title="Cookie Consent Management Under GDPR",
            content="Cookie consent banners must comply with GDPR requirements. Users need clear "
                   "opt-in for non-essential cookies. Privacy policies should explain data collection "
                   "purposes and third-party data sharing.",
            language="en",
            domain="SaaS",
            market="Germany",
            vertical="Compliance",
            content_hash="hash_gdpr_2",
            canonical_url="https://privacy.com/cookie-consent",
            published_at=datetime(2025, 11, 8),
            fetched_at=datetime.now()
        ),

        # AI/ML cluster (2 docs)
        Document(
            id="ai_1",
            source="rss",
            source_url="https://ai.com/llm-applications",
            title="Large Language Models in Enterprise Applications",
            content="LLMs like GPT-4 and Claude enable natural language interfaces for business software. "
                   "Applications include customer support automation, content generation, and code assistance. "
                   "Fine-tuning models on domain-specific data improves accuracy.",
            language="en",
            domain="AI",
            market="US",
            vertical="AI/ML",
            content_hash="hash_ai_1",
            canonical_url="https://ai.com/llm-applications",
            published_at=datetime(2025, 11, 9),
            fetched_at=datetime.now()
        ),
        Document(
            id="ai_2",
            source="rss",
            source_url="https://ai.com/computer-vision",
            title="Computer Vision for Quality Control in Manufacturing",
            content="Computer vision systems detect defects in manufacturing processes. Deep learning "
                   "models trained on labeled images achieve high accuracy in quality inspection. "
                   "Edge deployment enables real-time defect detection on production lines.",
            language="en",
            domain="AI",
            market="US",
            vertical="AI/ML",
            content_hash="hash_ai_2",
            canonical_url="https://ai.com/computer-vision",
            published_at=datetime(2025, 11, 10),
            fetched_at=datetime.now()
        ),
    ]

    return docs


# ==================== E2E Tests ====================

@pytest.mark.integration
def test_full_clustering_pipeline_e2e(temp_cache_dir, realistic_documents):
    """
    E2E Test: Full clustering pipeline on realistic dataset

    Tests:
    - TF-IDF feature extraction on diverse topics
    - HDBSCAN clustering produces semantically coherent clusters
    - LLM generates meaningful cluster labels
    - Statistics tracking works correctly
    - Noise handling (some documents may be outliers)

    Expected: 3-4 clusters (PropTech, Cloud, GDPR, AI/ML)
    """
    # Initialize clusterer with realistic settings
    clusterer = TopicClusterer(
        cache_dir=temp_cache_dir,
        min_cluster_size=2,  # At least 2 docs per cluster
        min_samples=1,       # Relaxed for small dataset
        max_features=1000,   # Sufficient for 10 documents
        model="qwen/qwen-2.5-7b-instruct"
    )

    # Run clustering
    clusters = clusterer.cluster_documents(realistic_documents)

    # Validate results
    assert len(clusters) >= 2, "Should find at least 2 semantic clusters"
    assert len(clusters) <= 5, "Should not create too many clusters for 10 documents"

    # Check cluster properties
    total_clustered_docs = sum(cluster.size for cluster in clusters)
    assert total_clustered_docs >= 6, "Should cluster majority of documents (at least 60%)"
    assert total_clustered_docs <= 10, "Cannot cluster more than total documents"

    # Verify cluster structure
    for cluster in clusters:
        assert cluster.cluster_id >= 0, "Cluster IDs should be non-negative"
        assert len(cluster.label) > 0, "Cluster should have a label"
        assert cluster.size >= 2, "Each cluster should have minimum size"
        assert len(cluster.document_ids) == cluster.size, "Document count mismatch"
        assert len(cluster.topic_titles) == cluster.size, "Topic count mismatch"
        assert cluster.representative_title in cluster.topic_titles, "Representative should be from cluster"

    # Check statistics
    stats = clusterer.last_stats
    assert stats["total_documents"] == 10
    assert stats["total_clusters"] == len(clusters)
    assert stats["noise_count"] >= 0
    assert stats["noise_count"] <= 10
    assert 0.0 <= stats["noise_ratio"] <= 1.0
    assert stats["largest_cluster_size"] >= 2

    print("\n" + "="*80)
    print("CLUSTERING RESULTS")
    print("="*80)
    print(f"Total Documents: {stats['total_documents']}")
    print(f"Clusters Found: {stats['total_clusters']}")
    print(f"Noise Points: {stats['noise_count']} ({stats['noise_ratio']:.1%})")
    print(f"Largest Cluster: {stats['largest_cluster_size']} documents")
    print("\nCluster Details:")
    for cluster in sorted(clusters, key=lambda c: c.size, reverse=True):
        print(f"\n  [{cluster.label}] ({cluster.size} documents)")
        for title in cluster.topic_titles:
            print(f"    - {title}")
    print("="*80)


@pytest.mark.integration
def test_clustering_semantic_quality_e2e(temp_cache_dir, realistic_documents):
    """
    E2E Test: Validate semantic clustering quality

    Checks that semantically similar documents are clustered together:
    - PropTech docs should cluster together (IoT, Digital Twins, Blockchain)
    - Cloud docs should cluster together (AWS/Azure, Kubernetes, Serverless)
    - GDPR docs should cluster together (GDPR compliance, Cookie consent)
    """
    clusterer = TopicClusterer(
        cache_dir=temp_cache_dir,
        min_cluster_size=2,
        min_samples=1,
        max_features=1000
    )

    clusters = clusterer.cluster_documents(realistic_documents)

    # Create mapping: doc_id -> cluster_id
    doc_to_cluster = {}
    for cluster in clusters:
        for doc_id in cluster.document_ids:
            doc_to_cluster[doc_id] = cluster.cluster_id

    # Validate semantic coherence

    # PropTech documents should cluster together (if not noise)
    proptech_ids = ["proptech_1", "proptech_2", "proptech_3"]
    proptech_clusters = [doc_to_cluster[doc_id] for doc_id in proptech_ids if doc_id in doc_to_cluster]
    if len(proptech_clusters) >= 2:
        # Check if at least 2 PropTech docs are in same cluster
        assert len(set(proptech_clusters)) <= 2, "PropTech docs should cluster together"

    # Cloud documents should cluster together (if not noise)
    cloud_ids = ["cloud_1", "cloud_2", "cloud_3"]
    cloud_clusters = [doc_to_cluster[doc_id] for doc_id in cloud_ids if doc_id in doc_to_cluster]
    if len(cloud_clusters) >= 2:
        assert len(set(cloud_clusters)) <= 2, "Cloud docs should cluster together"

    # GDPR documents should cluster together (if not noise)
    gdpr_ids = ["gdpr_1", "gdpr_2"]
    gdpr_clusters = [doc_to_cluster[doc_id] for doc_id in gdpr_ids if doc_id in doc_to_cluster]
    if len(gdpr_clusters) == 2:
        assert len(set(gdpr_clusters)) == 1, "GDPR docs should cluster together"

    # Documents from different semantic topics should NOT be in same cluster
    # (unless very small dataset forces them together)
    if len(clusters) >= 3:
        # If we have 3+ clusters, semantic separation should be clear
        for cluster in clusters:
            doc_ids = set(cluster.document_ids)

            # Count how many topic categories are in this cluster
            categories_present = 0
            if any(doc_id in doc_ids for doc_id in proptech_ids):
                categories_present += 1
            if any(doc_id in doc_ids for doc_id in cloud_ids):
                categories_present += 1
            if any(doc_id in doc_ids for doc_id in gdpr_ids):
                categories_present += 1

            # Each cluster should primarily contain one semantic category
            assert categories_present <= 2, f"Cluster should not mix 3+ semantic categories: {cluster.label}"


@pytest.mark.integration
def test_clustering_with_minimum_documents(temp_cache_dir):
    """
    E2E Test: Clustering with exactly 2 documents (edge case)
    """
    docs = [
        Document(
            id="doc1",
            source="test",
            source_url="https://test.com/1",
            title="Cloud Computing Best Practices",
            content="AWS, Azure, and GCP provide scalable cloud infrastructure.",
            language="en",
            domain="SaaS",
            market="US",
            vertical="Cloud",
            content_hash="hash1",
            canonical_url="https://test.com/1",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        ),
        Document(
            id="doc2",
            source="test",
            source_url="https://test.com/2",
            title="Kubernetes Container Orchestration",
            content="Kubernetes orchestrates containers across cloud clusters.",
            language="en",
            domain="SaaS",
            market="US",
            vertical="Cloud",
            content_hash="hash2",
            canonical_url="https://test.com/2",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        ),
    ]

    clusterer = TopicClusterer(
        cache_dir=temp_cache_dir,
        min_cluster_size=2,
        min_samples=1
    )

    # Should handle 2 documents (may create 1 cluster or mark as noise)
    clusters = clusterer.cluster_documents(docs)

    # Either creates 1 cluster of 2 docs, or both are noise (0 clusters)
    assert len(clusters) <= 1
    if len(clusters) == 1:
        assert clusters[0].size == 2


@pytest.mark.integration
def test_clustering_fails_with_single_document(temp_cache_dir):
    """
    E2E Test: Clustering with < 2 documents should raise error
    """
    docs = [
        Document(
            id="doc1",
            source="test",
            source_url="https://test.com/1",
            title="Single Document",
            content="Only one document provided.",
            language="en",
            domain="SaaS",
            market="US",
            vertical="Test",
            content_hash="hash1",
            canonical_url="https://test.com/1",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        ),
    ]

    clusterer = TopicClusterer(cache_dir=temp_cache_dir)

    with pytest.raises(ClusteringError, match="at least 2 documents"):
        clusterer.cluster_documents(docs)


@pytest.mark.integration
def test_clustering_statistics_tracking(temp_cache_dir, realistic_documents):
    """
    E2E Test: Validate statistics tracking during clustering
    """
    clusterer = TopicClusterer(
        cache_dir=temp_cache_dir,
        min_cluster_size=2,
        min_samples=1
    )

    clusters = clusterer.cluster_documents(realistic_documents)

    stats = clusterer.last_stats

    # Validate statistics
    assert stats["total_documents"] == len(realistic_documents)
    assert stats["total_clusters"] == len(clusters)

    # Noise count + clustered docs should equal total
    clustered_count = sum(cluster.size for cluster in clusters)
    assert stats["noise_count"] + clustered_count == len(realistic_documents)

    # Noise ratio should be consistent
    expected_noise_ratio = stats["noise_count"] / len(realistic_documents)
    assert abs(stats["noise_ratio"] - expected_noise_ratio) < 0.01

    # Largest cluster should match actual largest
    actual_largest = max((cluster.size for cluster in clusters), default=0)
    assert stats["largest_cluster_size"] == actual_largest


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
