"""
Cluster Manager

Manages content clusters for Hub + Spoke SEO strategy.

A cluster consists of:
- 1 Hub article: Comprehensive pillar content (3000 words)
- 7 Spoke articles: Specific angles (1500-2500 words)
- Internal linking map: Bidirectional links (hub ↔ spokes)

Benefits:
- Topical authority (own a niche)
- Internal linking boost (SEO rankings)
- 2-5x organic traffic (6 months)
"""

import json
from typing import List, Dict, Optional
from datetime import datetime

from src.database.sqlite_manager import SQLiteManager
from src.synthesis.cross_topic_synthesizer import CrossTopicSynthesizer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ClusterPlan:
    """
    Cluster planning template.

    Defines the hub topic and spoke topics for a content cluster.
    """

    def __init__(
        self,
        cluster_id: str,
        hub_topic: str,
        spoke_topics: List[str],
        target_keywords: List[str],
        description: str = ""
    ):
        """
        Initialize cluster plan.

        Args:
            cluster_id: Unique cluster identifier (e.g., "proptech-automation-2025")
            hub_topic: Main topic for hub article (comprehensive pillar)
            spoke_topics: List of 7 specific angle topics for spoke articles
            target_keywords: Primary keywords to target across cluster
            description: Optional description of cluster strategy
        """
        self.cluster_id = cluster_id
        self.hub_topic = hub_topic
        self.spoke_topics = spoke_topics
        self.target_keywords = target_keywords
        self.description = description
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "cluster_id": self.cluster_id,
            "hub_topic": self.hub_topic,
            "spoke_topics": self.spoke_topics,
            "target_keywords": self.target_keywords,
            "description": self.description,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClusterPlan":
        """Create from dictionary."""
        plan = cls(
            cluster_id=data["cluster_id"],
            hub_topic=data["hub_topic"],
            spoke_topics=data["spoke_topics"],
            target_keywords=data["target_keywords"],
            description=data.get("description", "")
        )
        if "created_at" in data:
            plan.created_at = datetime.fromisoformat(data["created_at"])
        return plan


class InternalLink:
    """
    Internal link suggestion.

    Represents a suggested link between articles in a cluster.
    """

    def __init__(
        self,
        title: str,
        slug: str,
        anchor_text: str,
        context: str,
        cluster_id: Optional[str] = None
    ):
        """
        Initialize internal link.

        Args:
            title: Target article title
            slug: Target article slug (URL-friendly)
            anchor_text: Suggested anchor text for link
            context: Context sentence where link should appear
            cluster_id: Cluster this link belongs to (optional)
        """
        self.title = title
        self.slug = slug
        self.anchor_text = anchor_text
        self.context = context
        self.cluster_id = cluster_id

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "slug": self.slug,
            "anchor_text": self.anchor_text,
            "context": self.context,
            "cluster_id": self.cluster_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InternalLink":
        """Create from dictionary."""
        return cls(
            title=data["title"],
            slug=data["slug"],
            anchor_text=data["anchor_text"],
            context=data["context"],
            cluster_id=data.get("cluster_id")
        )


class ClusterManager:
    """
    Manages content clusters for Hub + Spoke SEO strategy.

    Handles:
    - Cluster creation and planning
    - Finding articles in a cluster
    - Generating internal linking suggestions
    - Cluster metadata and stats
    """

    def __init__(self, db_manager: SQLiteManager):
        """
        Initialize cluster manager.

        Args:
            db_manager: SQLite database manager instance
        """
        self.db = db_manager
        self.synthesizer = CrossTopicSynthesizer(db_manager)
        logger.info("cluster_manager_initialized")

    def create_cluster_plan(
        self,
        cluster_id: str,
        hub_topic: str,
        spoke_topics: List[str],
        target_keywords: List[str],
        description: str = ""
    ) -> ClusterPlan:
        """
        Create a cluster plan.

        Args:
            cluster_id: Unique cluster identifier (e.g., "proptech-automation-2025")
            hub_topic: Main topic for hub article
            spoke_topics: List of 7 spoke topics
            target_keywords: Primary keywords to target
            description: Optional description

        Returns:
            ClusterPlan instance

        Raises:
            ValueError: If spoke_topics is not exactly 7 topics
        """
        if len(spoke_topics) != 7:
            raise ValueError(f"Hub + Spoke requires exactly 7 spoke topics, got {len(spoke_topics)}")

        plan = ClusterPlan(
            cluster_id=cluster_id,
            hub_topic=hub_topic,
            spoke_topics=spoke_topics,
            target_keywords=target_keywords,
            description=description
        )

        logger.info(
            "cluster_plan_created",
            cluster_id=cluster_id,
            hub_topic=hub_topic,
            spoke_count=len(spoke_topics)
        )

        return plan

    def get_cluster_articles(
        self,
        cluster_id: str,
        include_content: bool = False
    ) -> Dict[str, List[dict]]:
        """
        Get all articles in a cluster.

        Args:
            cluster_id: Cluster identifier
            include_content: Whether to include full content (default: False)

        Returns:
            Dictionary with 'hub' and 'spokes' lists of articles
            Each article: {id, slug, title, content (optional), cluster_role}
        """
        with self.db._get_connection(readonly=True) as conn:
            cursor = conn.cursor()

            # Build SELECT fields
            fields = "id, slug, title, cluster_role"
            if include_content:
                fields += ", content"

            # Get hub article
            cursor.execute(
                f"SELECT {fields} FROM blog_posts WHERE cluster_id = ? AND cluster_role = 'Hub'",
                (cluster_id,)
            )
            hub_row = cursor.fetchone()
            hub = None
            if hub_row:
                hub = {
                    "id": hub_row[0],
                    "slug": hub_row[1],
                    "title": hub_row[2],
                    "cluster_role": hub_row[3]
                }
                if include_content:
                    hub["content"] = hub_row[4]

            # Get spoke articles
            cursor.execute(
                f"SELECT {fields} FROM blog_posts WHERE cluster_id = ? AND cluster_role = 'Spoke'",
                (cluster_id,)
            )
            spokes = []
            for row in cursor.fetchall():
                spoke = {
                    "id": row[0],
                    "slug": row[1],
                    "title": row[2],
                    "cluster_role": row[3]
                }
                if include_content:
                    spoke["content"] = row[4]
                spokes.append(spoke)

        logger.info(
            "cluster_articles_retrieved",
            cluster_id=cluster_id,
            hub_found=hub is not None,
            spoke_count=len(spokes)
        )

        return {
            "hub": hub,
            "spokes": spokes
        }

    def suggest_internal_links(
        self,
        topic_id: str,
        cluster_id: Optional[str] = None,
        max_links: int = 5
    ) -> List[InternalLink]:
        """
        Generate internal linking suggestions for an article.

        Strategy:
        1. If article is in a cluster:
           - Link to hub (if this is a spoke)
           - Link to related spokes (if this is hub or spoke)
        2. Find related topics using CrossTopicSynthesizer
        3. Generate natural anchor text suggestions

        Args:
            topic_id: Topic ID of the article
            cluster_id: Cluster ID (if article is in a cluster)
            max_links: Maximum number of link suggestions (default: 5)

        Returns:
            List of InternalLink suggestions
        """
        suggestions = []

        # Strategy 1: Cluster-based links
        if cluster_id:
            cluster_articles = self.get_cluster_articles(cluster_id)

            # Get current article's role
            with self.db._get_connection(readonly=True) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT cluster_role, title FROM blog_posts WHERE id = ?",
                    (topic_id,)
                )
                row = cursor.fetchone()
                current_role = row[0] if row else None
                current_title = row[1] if row else ""

            # If spoke, always link to hub
            if current_role == "Spoke" and cluster_articles["hub"]:
                hub = cluster_articles["hub"]
                suggestions.append(InternalLink(
                    title=hub["title"],
                    slug=hub["slug"],
                    anchor_text=f"comprehensive guide to {self._extract_main_keyword(hub['title'])}",
                    context=f"For a complete overview, see our {hub['title']}.",
                    cluster_id=cluster_id
                ))

            # Link to related spokes (exclude self)
            for spoke in cluster_articles["spokes"]:
                if spoke["id"] != topic_id and len(suggestions) < max_links:
                    suggestions.append(InternalLink(
                        title=spoke["title"],
                        slug=spoke["slug"],
                        anchor_text=self._extract_main_keyword(spoke["title"]),
                        context=f"Related topic: {spoke['title']}",
                        cluster_id=cluster_id
                    ))

        # Strategy 2: Related topics (if space left)
        if len(suggestions) < max_links:
            # Get topic title for synthesis
            with self.db._get_connection(readonly=True) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title FROM topics WHERE id = ?", (topic_id,))
                row = cursor.fetchone()
                topic_title = row[0] if row else topic_id

            # Use CrossTopicSynthesizer to find related topics
            synthesis = self.synthesizer.synthesize_related_topics(
                topic=topic_title,
                topic_id=topic_id,
                max_related=max_links - len(suggestions)
            )

            if synthesis and synthesis.get('related_topics'):
                for related in synthesis['related_topics']:
                    # Check if already linked (avoid duplicates)
                    if not any(s.title == related.title for s in suggestions):
                        # Get slug from database
                        with self.db._get_connection(readonly=True) as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "SELECT slug FROM blog_posts WHERE title = ?",
                                (related.title,)
                            )
                            row = cursor.fetchone()
                            if row:
                                suggestions.append(InternalLink(
                                    title=related.title,
                                    slug=row[0],
                                    anchor_text=self._extract_main_keyword(related.title),
                                    context=f"See also: {related.title}",
                                    cluster_id=None
                                ))

        logger.info(
            "internal_links_suggested",
            topic_id=topic_id,
            cluster_id=cluster_id,
            link_count=len(suggestions)
        )

        return suggestions[:max_links]

    def _extract_main_keyword(self, title: str) -> str:
        """
        Extract main keyword from title for anchor text.

        Args:
            title: Article title

        Returns:
            Main keyword phrase (lowercased)
        """
        # Simple heuristic: take last 2-3 words (usually the main topic)
        words = title.lower().split()
        if len(words) <= 3:
            return " ".join(words)
        else:
            return " ".join(words[-3:])

    def get_cluster_stats(self, cluster_id: str) -> dict:
        """
        Get cluster statistics.

        Args:
            cluster_id: Cluster identifier

        Returns:
            Statistics dict with counts and metadata
        """
        articles = self.get_cluster_articles(cluster_id)

        stats = {
            "cluster_id": cluster_id,
            "has_hub": articles["hub"] is not None,
            "spoke_count": len(articles["spokes"]),
            "total_articles": (1 if articles["hub"] else 0) + len(articles["spokes"]),
            "completion_percentage": ((1 if articles["hub"] else 0) + len(articles["spokes"])) / 8 * 100
        }

        logger.info("cluster_stats_calculated", **stats)

        return stats
