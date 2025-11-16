"""
Unit Tests for ClusterManager

Tests cluster planning, internal linking, and cluster operations.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from src.synthesis.cluster_manager import (
    ClusterManager,
    ClusterPlan,
    InternalLink
)


# ============================================================================
# ClusterPlan Tests
# ============================================================================

def test_cluster_plan_creation():
    """Test ClusterPlan initialization."""
    plan = ClusterPlan(
        cluster_id="test-cluster",
        hub_topic="Hub Topic",
        spoke_topics=["Spoke 1", "Spoke 2", "Spoke 3", "Spoke 4", "Spoke 5", "Spoke 6", "Spoke 7"],
        target_keywords=["keyword1", "keyword2"],
        description="Test cluster"
    )

    assert plan.cluster_id == "test-cluster"
    assert plan.hub_topic == "Hub Topic"
    assert len(plan.spoke_topics) == 7
    assert plan.target_keywords == ["keyword1", "keyword2"]
    assert plan.description == "Test cluster"
    assert isinstance(plan.created_at, datetime)


def test_cluster_plan_to_dict():
    """Test ClusterPlan serialization."""
    plan = ClusterPlan(
        cluster_id="test-cluster",
        hub_topic="Hub Topic",
        spoke_topics=["Spoke 1", "Spoke 2", "Spoke 3", "Spoke 4", "Spoke 5", "Spoke 6", "Spoke 7"],
        target_keywords=["keyword1"],
        description="Test"
    )

    data = plan.to_dict()

    assert data["cluster_id"] == "test-cluster"
    assert data["hub_topic"] == "Hub Topic"
    assert len(data["spoke_topics"]) == 7
    assert "created_at" in data


def test_cluster_plan_from_dict():
    """Test ClusterPlan deserialization."""
    data = {
        "cluster_id": "test-cluster",
        "hub_topic": "Hub Topic",
        "spoke_topics": ["Spoke 1", "Spoke 2", "Spoke 3", "Spoke 4", "Spoke 5", "Spoke 6", "Spoke 7"],
        "target_keywords": ["keyword1"],
        "description": "Test",
        "created_at": "2025-11-16T22:00:00.000000"
    }

    plan = ClusterPlan.from_dict(data)

    assert plan.cluster_id == "test-cluster"
    assert plan.hub_topic == "Hub Topic"
    assert len(plan.spoke_topics) == 7
    assert isinstance(plan.created_at, datetime)


# ============================================================================
# InternalLink Tests
# ============================================================================

def test_internal_link_creation():
    """Test InternalLink initialization."""
    link = InternalLink(
        title="Test Article",
        slug="test-article",
        anchor_text="test article",
        context="See the test article for more info.",
        cluster_id="test-cluster"
    )

    assert link.title == "Test Article"
    assert link.slug == "test-article"
    assert link.anchor_text == "test article"
    assert link.context == "See the test article for more info."
    assert link.cluster_id == "test-cluster"


def test_internal_link_to_dict():
    """Test InternalLink serialization."""
    link = InternalLink(
        title="Test Article",
        slug="test-article",
        anchor_text="test article",
        context="Context",
        cluster_id="test-cluster"
    )

    data = link.to_dict()

    assert data["title"] == "Test Article"
    assert data["slug"] == "test-article"
    assert data["anchor_text"] == "test article"
    assert data["context"] == "Context"
    assert data["cluster_id"] == "test-cluster"


def test_internal_link_from_dict():
    """Test InternalLink deserialization."""
    data = {
        "title": "Test Article",
        "slug": "test-article",
        "anchor_text": "test article",
        "context": "Context",
        "cluster_id": "test-cluster"
    }

    link = InternalLink.from_dict(data)

    assert link.title == "Test Article"
    assert link.slug == "test-article"


# ============================================================================
# ClusterManager Tests (Mocked)
# ============================================================================

@pytest.fixture
def mock_db_manager():
    """Create mock database manager."""
    db = Mock()
    db._get_connection = MagicMock()
    return db


@pytest.fixture
def cluster_manager(mock_db_manager):
    """Create ClusterManager with mocked database."""
    with patch('src.synthesis.cluster_manager.CrossTopicSynthesizer'):
        return ClusterManager(mock_db_manager)


def test_cluster_manager_initialization(cluster_manager):
    """Test ClusterManager initialization."""
    assert cluster_manager.db is not None
    assert cluster_manager.synthesizer is not None


def test_create_cluster_plan_valid(cluster_manager):
    """Test creating valid cluster plan."""
    plan = cluster_manager.create_cluster_plan(
        cluster_id="test-cluster",
        hub_topic="Hub Topic",
        spoke_topics=["S1", "S2", "S3", "S4", "S5", "S6", "S7"],
        target_keywords=["kw1", "kw2"],
        description="Test"
    )

    assert isinstance(plan, ClusterPlan)
    assert plan.cluster_id == "test-cluster"
    assert len(plan.spoke_topics) == 7


def test_create_cluster_plan_invalid_spoke_count(cluster_manager):
    """Test creating cluster plan with wrong spoke count."""
    with pytest.raises(ValueError, match="exactly 7 spoke topics"):
        cluster_manager.create_cluster_plan(
            cluster_id="test-cluster",
            hub_topic="Hub Topic",
            spoke_topics=["S1", "S2", "S3"],  # Only 3 spokes
            target_keywords=["kw1"],
            description="Test"
        )


def test_get_cluster_articles_with_hub_and_spokes(cluster_manager, mock_db_manager):
    """Test getting cluster articles when hub and spokes exist."""
    # Mock database connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Mock hub query result
    mock_cursor.fetchone.return_value = ("hub-id", "hub-slug", "Hub Title", "Hub")

    # Mock spokes query result
    mock_cursor.fetchall.return_value = [
        ("spoke-1", "spoke-1-slug", "Spoke 1", "Spoke"),
        ("spoke-2", "spoke-2-slug", "Spoke 2", "Spoke")
    ]

    mock_db_manager._get_connection.return_value.__enter__.return_value = mock_conn

    # Get cluster articles
    articles = cluster_manager.get_cluster_articles("test-cluster")

    assert articles["hub"] is not None
    assert articles["hub"]["title"] == "Hub Title"
    assert len(articles["spokes"]) == 2
    assert articles["spokes"][0]["title"] == "Spoke 1"


def test_get_cluster_articles_no_hub(cluster_manager, mock_db_manager):
    """Test getting cluster articles when hub doesn't exist."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # No hub
    mock_cursor.fetchone.return_value = None

    # Spokes exist
    mock_cursor.fetchall.return_value = [
        ("spoke-1", "spoke-1-slug", "Spoke 1", "Spoke")
    ]

    mock_db_manager._get_connection.return_value.__enter__.return_value = mock_conn

    articles = cluster_manager.get_cluster_articles("test-cluster")

    assert articles["hub"] is None
    assert len(articles["spokes"]) == 1


def test_extract_main_keyword(cluster_manager):
    """Test keyword extraction from title."""
    # Short title (1-3 words returns all)
    keyword = cluster_manager._extract_main_keyword("AI Tools")
    assert keyword == "ai tools"

    # Medium title (4 words, returns last 3)
    keyword = cluster_manager._extract_main_keyword("Complete Guide to AI")
    assert keyword == "guide to ai"

    # Long title (takes last 3 words)
    keyword = cluster_manager._extract_main_keyword("How to Use AI Tools for Marketing")
    assert keyword == "tools for marketing"


def test_get_cluster_stats_complete(cluster_manager, mock_db_manager):
    """Test cluster statistics for complete cluster."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Hub exists
    mock_cursor.fetchone.return_value = ("hub-id", "hub-slug", "Hub", "Hub")

    # All 7 spokes exist
    mock_cursor.fetchall.return_value = [
        (f"spoke-{i}", f"slug-{i}", f"Spoke {i}", "Spoke")
        for i in range(7)
    ]

    mock_db_manager._get_connection.return_value.__enter__.return_value = mock_conn

    stats = cluster_manager.get_cluster_stats("test-cluster")

    assert stats["cluster_id"] == "test-cluster"
    assert stats["has_hub"] is True
    assert stats["spoke_count"] == 7
    assert stats["total_articles"] == 8
    assert stats["completion_percentage"] == 100.0


def test_get_cluster_stats_partial(cluster_manager, mock_db_manager):
    """Test cluster statistics for partial cluster."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Hub exists
    mock_cursor.fetchone.return_value = ("hub-id", "hub-slug", "Hub", "Hub")

    # Only 3 spokes
    mock_cursor.fetchall.return_value = [
        (f"spoke-{i}", f"slug-{i}", f"Spoke {i}", "Spoke")
        for i in range(3)
    ]

    mock_db_manager._get_connection.return_value.__enter__.return_value = mock_conn

    stats = cluster_manager.get_cluster_stats("test-cluster")

    assert stats["has_hub"] is True
    assert stats["spoke_count"] == 3
    assert stats["total_articles"] == 4
    assert stats["completion_percentage"] == 50.0  # 4/8 * 100


def test_suggest_internal_links_spoke_to_hub(cluster_manager, mock_db_manager):
    """Test internal link suggestions from spoke to hub."""
    # Mock get_cluster_articles
    with patch.object(cluster_manager, 'get_cluster_articles') as mock_get_articles:
        mock_get_articles.return_value = {
            "hub": {
                "id": "hub-id",
                "slug": "hub-slug",
                "title": "Complete Guide to AI",
                "cluster_role": "Hub"
            },
            "spokes": [
                {"id": "spoke-1", "slug": "spoke-1", "title": "Spoke 1", "cluster_role": "Spoke"}
            ]
        }

        # Mock database query for current article
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("Spoke", "Current Spoke Article")

        mock_db_manager._get_connection.return_value.__enter__.return_value = mock_conn

        # Get suggestions
        suggestions = cluster_manager.suggest_internal_links(
            topic_id="current-spoke",
            cluster_id="test-cluster",
            max_links=5
        )

        # Should suggest link to hub
        assert len(suggestions) > 0
        hub_link = suggestions[0]
        assert hub_link.title == "Complete Guide to AI"
        assert hub_link.slug == "hub-slug"
        assert "comprehensive guide" in hub_link.anchor_text.lower()


# ============================================================================
# Edge Cases
# ============================================================================

def test_cluster_plan_json_roundtrip():
    """Test ClusterPlan JSON serialization/deserialization."""
    original = ClusterPlan(
        cluster_id="test",
        hub_topic="Hub",
        spoke_topics=["S1", "S2", "S3", "S4", "S5", "S6", "S7"],
        target_keywords=["kw"],
        description="Test"
    )

    # Serialize
    json_str = json.dumps(original.to_dict())

    # Deserialize
    data = json.loads(json_str)
    restored = ClusterPlan.from_dict(data)

    assert restored.cluster_id == original.cluster_id
    assert restored.hub_topic == original.hub_topic
    assert restored.spoke_topics == original.spoke_topics


def test_internal_link_without_cluster():
    """Test InternalLink without cluster_id."""
    link = InternalLink(
        title="Article",
        slug="article",
        anchor_text="article",
        context="Context"
    )

    assert link.cluster_id is None
    data = link.to_dict()
    assert data["cluster_id"] is None
