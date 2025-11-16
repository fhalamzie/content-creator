"""
Integration Tests for ClusterManager

Tests with real SQLite database.
"""

import pytest
import tempfile
import os
from datetime import datetime

from src.synthesis.cluster_manager import ClusterManager, ClusterPlan
from src.database.sqlite_manager import SQLiteManager


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db = SQLiteManager(db_path=path)

    yield db

    # Cleanup
    try:
        os.unlink(path)
    except:
        pass


@pytest.fixture
def cluster_manager(temp_db):
    """Create ClusterManager with real database."""
    return ClusterManager(temp_db)


# ============================================================================
# Integration Tests
# ============================================================================

def test_create_and_retrieve_cluster_plan(cluster_manager):
    """Test creating cluster plan and saving to file."""
    plan = cluster_manager.create_cluster_plan(
        cluster_id="integration-test-cluster",
        hub_topic="Integration Test Hub",
        spoke_topics=[
            "Spoke 1", "Spoke 2", "Spoke 3", "Spoke 4",
            "Spoke 5", "Spoke 6", "Spoke 7"
        ],
        target_keywords=["test", "integration"],
        description="Integration test cluster"
    )

    assert plan.cluster_id == "integration-test-cluster"
    assert len(plan.spoke_topics) == 7

    # Test serialization
    data = plan.to_dict()
    restored = ClusterPlan.from_dict(data)

    assert restored.cluster_id == plan.cluster_id
    assert restored.hub_topic == plan.hub_topic


def test_cluster_with_real_articles(cluster_manager, temp_db):
    """Test cluster operations with real articles in database."""
    cluster_id = "real-articles-cluster"

    # Insert hub article
    with temp_db._get_connection() as conn:
        conn.execute("""
            INSERT INTO blog_posts (
                id, slug, title, content, cluster_id, cluster_role, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "hub-1",
            "hub-article",
            "Hub Article Title",
            "Hub article content",
            cluster_id,
            "Hub",
            "draft"
        ))

        # Insert 3 spoke articles
        for i in range(1, 4):
            conn.execute("""
                INSERT INTO blog_posts (
                    id, slug, title, content, cluster_id, cluster_role, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"spoke-{i}",
                f"spoke-{i}",
                f"Spoke {i} Title",
                f"Spoke {i} content",
                cluster_id,
                "Spoke",
                "draft"
            ))

    # Get cluster articles
    articles = cluster_manager.get_cluster_articles(cluster_id)

    assert articles["hub"] is not None
    assert articles["hub"]["title"] == "Hub Article Title"
    assert len(articles["spokes"]) == 3
    assert articles["spokes"][0]["title"] == "Spoke 1 Title"


def test_cluster_stats_real_database(cluster_manager, temp_db):
    """Test cluster statistics with real database."""
    cluster_id = "stats-test-cluster"

    # Insert hub
    with temp_db._get_connection() as conn:
        conn.execute("""
            INSERT INTO blog_posts (
                id, slug, title, content, cluster_id, cluster_role
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ("hub-1", "hub", "Hub", "Content", cluster_id, "Hub"))

        # Insert 5 spokes
        for i in range(5):
            conn.execute("""
                INSERT INTO blog_posts (
                    id, slug, title, content, cluster_id, cluster_role
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (f"spoke-{i}", f"spoke-{i}", f"Spoke {i}", "Content", cluster_id, "Spoke"))

    # Get stats
    stats = cluster_manager.get_cluster_stats(cluster_id)

    assert stats["cluster_id"] == cluster_id
    assert stats["has_hub"] is True
    assert stats["spoke_count"] == 5
    assert stats["total_articles"] == 6
    assert stats["completion_percentage"] == 75.0  # 6/8 * 100


def test_internal_link_suggestions_real_database(cluster_manager, temp_db):
    """Test internal link suggestions with real database and topics."""
    cluster_id = "link-test-cluster"

    # Insert topics first
    with temp_db._get_connection() as conn:
        # Hub topic
        conn.execute("""
            INSERT INTO topics (
                id, title, status, domain, language, source
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ("hub-topic", "Hub Topic", "researched", "tech", "en", "manual"))

        # Spoke topic
        conn.execute("""
            INSERT INTO topics (
                id, title, status, domain, language, source
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ("spoke-topic", "Spoke Topic", "researched", "tech", "en", "manual"))

        # Insert blog posts
        conn.execute("""
            INSERT INTO blog_posts (
                id, slug, title, content, cluster_id, cluster_role, research_topic_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("hub-1", "hub-article", "Hub Article", "Content", cluster_id, "Hub", "hub-topic"))

        conn.execute("""
            INSERT INTO blog_posts (
                id, slug, title, content, cluster_id, cluster_role, research_topic_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("spoke-1", "spoke-article", "Spoke Article", "Content", cluster_id, "Spoke", "spoke-topic"))

    # Get suggestions for spoke (should link to hub)
    suggestions = cluster_manager.suggest_internal_links(
        topic_id="spoke-1",
        cluster_id=cluster_id,
        max_links=5
    )

    # Should have at least hub link
    assert len(suggestions) > 0

    # First suggestion should be hub (for spoke articles)
    hub_link = suggestions[0]
    assert hub_link.title == "Hub Article"
    assert hub_link.slug == "hub-article"
    assert cluster_id in str(hub_link.cluster_id) or hub_link.cluster_id == cluster_id


def test_empty_cluster(cluster_manager):
    """Test operations on non-existent cluster."""
    articles = cluster_manager.get_cluster_articles("non-existent-cluster")

    assert articles["hub"] is None
    assert len(articles["spokes"]) == 0

    stats = cluster_manager.get_cluster_stats("non-existent-cluster")

    assert stats["has_hub"] is False
    assert stats["spoke_count"] == 0
    assert stats["total_articles"] == 0
    assert stats["completion_percentage"] == 0.0


def test_multiple_clusters(cluster_manager, temp_db):
    """Test managing multiple clusters simultaneously."""
    # Create two clusters
    for cluster_num in [1, 2]:
        cluster_id = f"cluster-{cluster_num}"

        with temp_db._get_connection() as conn:
            # Hub
            conn.execute("""
                INSERT INTO blog_posts (
                    id, slug, title, content, cluster_id, cluster_role
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (f"hub-{cluster_num}", f"hub-{cluster_num}", f"Hub {cluster_num}", "Content", cluster_id, "Hub"))

            # 2 spokes each
            for i in range(2):
                conn.execute("""
                    INSERT INTO blog_posts (
                        id, slug, title, content, cluster_id, cluster_role
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    f"spoke-{cluster_num}-{i}",
                    f"spoke-{cluster_num}-{i}",
                    f"Spoke {cluster_num}-{i}",
                    "Content",
                    cluster_id,
                    "Spoke"
                ))

    # Get articles for each cluster
    cluster1 = cluster_manager.get_cluster_articles("cluster-1")
    cluster2 = cluster_manager.get_cluster_articles("cluster-2")

    assert cluster1["hub"]["title"] == "Hub 1"
    assert cluster2["hub"]["title"] == "Hub 2"
    assert len(cluster1["spokes"]) == 2
    assert len(cluster2["spokes"]) == 2


def test_standalone_articles_not_in_cluster(cluster_manager, temp_db):
    """Test that standalone articles are not included in clusters."""
    cluster_id = "exclusive-cluster"

    with temp_db._get_connection() as conn:
        # Cluster article
        conn.execute("""
            INSERT INTO blog_posts (
                id, slug, title, content, cluster_id, cluster_role
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ("hub-1", "hub", "Hub", "Content", cluster_id, "Hub"))

        # Standalone article (no cluster)
        conn.execute("""
            INSERT INTO blog_posts (
                id, slug, title, content, cluster_role
            ) VALUES (?, ?, ?, ?, ?)
        """, ("standalone", "standalone", "Standalone", "Content", "Standalone"))

    articles = cluster_manager.get_cluster_articles(cluster_id)

    assert articles["hub"] is not None
    assert len(articles["spokes"]) == 0  # Standalone not included


def test_cluster_plan_validation():
    """Test cluster plan validation."""
    # Valid plan (7 spokes)
    with pytest.raises(ValueError):
        # Too few spokes
        ClusterManager(SQLiteManager(":memory:")).create_cluster_plan(
            cluster_id="test",
            hub_topic="Hub",
            spoke_topics=["S1", "S2"],  # Only 2
            target_keywords=["kw"]
        )

    with pytest.raises(ValueError):
        # Too many spokes
        ClusterManager(SQLiteManager(":memory:")).create_cluster_plan(
            cluster_id="test",
            hub_topic="Hub",
            spoke_topics=["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],  # 8 spokes
            target_keywords=["kw"]
        )


def test_get_cluster_articles_with_content(cluster_manager, temp_db):
    """Test retrieving cluster articles with full content."""
    cluster_id = "content-test-cluster"

    hub_content = "This is the full hub article content with 100+ words..."
    spoke_content = "This is spoke content..."

    with temp_db._get_connection() as conn:
        conn.execute("""
            INSERT INTO blog_posts (
                id, slug, title, content, cluster_id, cluster_role
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ("hub-1", "hub", "Hub", hub_content, cluster_id, "Hub"))

        conn.execute("""
            INSERT INTO blog_posts (
                id, slug, title, content, cluster_id, cluster_role
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, ("spoke-1", "spoke", "Spoke", spoke_content, cluster_id, "Spoke"))

    # Get with content
    articles = cluster_manager.get_cluster_articles(cluster_id, include_content=True)

    assert "content" in articles["hub"]
    assert articles["hub"]["content"] == hub_content
    assert articles["spokes"][0]["content"] == spoke_content

    # Get without content
    articles_no_content = cluster_manager.get_cluster_articles(cluster_id, include_content=False)

    assert "content" not in articles_no_content["hub"]
    assert "content" not in articles_no_content["spokes"][0]
