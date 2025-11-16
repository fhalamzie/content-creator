"""
Cross-Topic Synthesizer

Synthesizes insights from multiple related topics to create unique perspectives
that competitors lack. Enables topical authority through cross-topic connections.

Design Goals:
- Find 3-5 related topics using semantic similarity
- Extract key insights: themes, gaps, predictions, unique angles
- Create synthesis summary with unique perspectives
- Enable natural internal linking opportunities
- Zero API costs (CPU-only, cache reads)

Pattern: Cross-reference synthesis (RankCraft-AI pattern)
"""

import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from src.database.sqlite_manager import SQLiteManager
from src.models.topic import Topic

logger = logging.getLogger(__name__)


class CrossTopicSynthesizer:
    """
    Synthesizes insights from related topics.

    Creates unique perspectives by connecting insights across
    semantically related topics in the research cache.

    Features:
    - Semantic similarity search (Jaccard on keywords)
    - Key insight extraction (themes, gaps, predictions)
    - Synthesis summary generation
    - Internal linking suggestions
    - Zero API costs (CPU-only)

    Usage:
        synthesizer = CrossTopicSynthesizer(db_path="data/topics.db")
        synthesis = synthesizer.synthesize_related_topics(
            topic="PropTech Trends 2025",
            topic_id="proptech-trends-2025",
            max_related=3
        )
        print(synthesis['summary'])
        print(synthesis['related_topics'])
        print(synthesis['unique_angles'])
    """

    def __init__(self, db_path_or_manager: Union[str, SQLiteManager] = "data/topics.db"):
        """
        Initialize synthesizer.

        Args:
            db_path_or_manager: Path to SQLite database OR SQLiteManager instance (default: data/topics.db)
        """
        if isinstance(db_path_or_manager, SQLiteManager):
            self.db_manager = db_path_or_manager
            logger.info("cross_topic_synthesizer_initialized_with_manager")
        else:
            self.db_manager = SQLiteManager(db_path=db_path_or_manager)
            logger.info("cross_topic_synthesizer_initialized", db_path=db_path_or_manager)

    def synthesize_related_topics(
        self,
        topic: str,
        topic_id: str,
        max_related: int = 3,
        min_similarity: float = 0.2
    ) -> Dict[str, Any]:
        """
        Synthesize insights from related topics.

        Args:
            topic: Topic title (for display)
            topic_id: Topic ID (slug for lookup)
            max_related: Maximum related topics to analyze (default: 3)
            min_similarity: Minimum similarity threshold (default: 0.2)

        Returns:
            Dict with:
                - related_topics: List[Dict] - Related topic info (title, id, similarity)
                - synthesis_summary: str - Text summary of synthesis
                - unique_angles: List[str] - Unique perspectives from cross-topic analysis
                - themes: List[str] - Common themes across topics
                - internal_links: List[Dict] - Suggested internal links
                - synthesized_at: str - ISO timestamp

        Example:
            >>> synthesis = synthesizer.synthesize_related_topics(
            ...     topic="PropTech Trends 2025",
            ...     topic_id="proptech-trends-2025",
            ...     max_related=3
            ... )
            >>> print(synthesis['synthesis_summary'])
            Synthesizing insights from PropTech Trends 2025 with related topics:
            PropTech Investment Strategies, Real Estate Technology, Smart Buildings...
        """
        logger.info(
            "synthesizing_related_topics",
            topic=topic,
            topic_id=topic_id,
            max_related=max_related
        )

        # Find related topics
        related = self.db_manager.find_related_topics(
            topic_id=topic_id,
            limit=max_related,
            min_similarity=min_similarity
        )

        if not related:
            logger.info("no_related_topics_found", topic_id=topic_id)
            return {
                "related_topics": [],
                "synthesis_summary": "",
                "unique_angles": [],
                "themes": [],
                "internal_links": [],
                "synthesized_at": datetime.utcnow().isoformat()
            }

        logger.info(
            "found_related_topics_for_synthesis",
            topic_id=topic_id,
            count=len(related)
        )

        # Extract related topic info
        related_info = [
            {
                "title": t.title,
                "id": t.id,
                "similarity": round(score, 2),
                "word_count": t.word_count,
                "description": t.description or ""
            }
            for t, score in related
        ]

        # Extract insights from each related topic
        all_insights = []
        for topic_obj, similarity_score in related:
            insights = self._extract_insights(topic_obj)
            all_insights.extend(insights)

        # Identify common themes (keywords appearing in multiple topics)
        themes = self._identify_common_themes(related)

        # Generate unique angles (cross-topic connections)
        unique_angles = self._generate_unique_angles(topic, related)

        # Create synthesis summary
        synthesis_summary = self._create_synthesis_summary(
            topic=topic,
            related_info=related_info,
            themes=themes,
            unique_angles=unique_angles
        )

        # Generate internal linking suggestions
        internal_links = [
            {
                "title": info["title"],
                "id": info["id"],
                "relevance": info["similarity"],
                "suggested_anchor": self._suggest_anchor_text(topic, info["title"])
            }
            for info in related_info
        ]

        result = {
            "related_topics": related_info,
            "synthesis_summary": synthesis_summary,
            "unique_angles": unique_angles,
            "themes": themes,
            "internal_links": internal_links,
            "synthesized_at": datetime.utcnow().isoformat()
        }

        logger.info(
            "synthesis_complete",
            topic_id=topic_id,
            related_count=len(related_info),
            themes_count=len(themes),
            unique_angles_count=len(unique_angles)
        )

        return result

    def _extract_insights(self, topic: Topic) -> List[str]:
        """
        Extract key insights from a topic's research report.

        Simple extraction: First 3-5 sentences or bullet points.
        Future enhancement: Use LLM to extract themes/predictions.

        Args:
            topic: Topic with research_report

        Returns:
            List of insight strings
        """
        if not topic.research_report:
            return []

        # Extract first 500 characters as key insights
        # This is a simple heuristic; could be enhanced with NLP/LLM
        report = topic.research_report[:500]

        # Split into sentences (simple approach)
        import re
        sentences = re.split(r'[.!?]\s+', report)

        # Return first 3 non-empty sentences
        insights = [s.strip() for s in sentences if len(s.strip()) > 20][:3]

        return insights

    def _identify_common_themes(
        self,
        related_topics: List[tuple[Topic, float]]
    ) -> List[str]:
        """
        Identify common themes across related topics.

        Uses keyword frequency analysis to find recurring themes.

        Args:
            related_topics: List of (Topic, similarity_score) tuples

        Returns:
            List of common theme keywords
        """
        if not related_topics:
            return []

        # Extract keywords from all topic titles
        all_keywords = []
        for topic, _ in related_topics:
            keywords = self.db_manager._extract_keywords(topic.title)
            all_keywords.extend(keywords)

        # Count keyword frequency
        from collections import Counter
        keyword_counts = Counter(all_keywords)

        # Return keywords appearing in 2+ topics (common themes)
        common_themes = [
            keyword for keyword, count in keyword_counts.items()
            if count >= 2
        ]

        # Sort by frequency descending
        common_themes.sort(key=lambda k: keyword_counts[k], reverse=True)

        return common_themes[:5]  # Top 5 themes

    def _generate_unique_angles(
        self,
        main_topic: str,
        related_topics: List[tuple[Topic, float]]
    ) -> List[str]:
        """
        Generate unique angles by connecting main topic to related topics.

        Creates synthesis statements that competitors likely lack.

        Args:
            main_topic: Main topic title
            related_topics: List of (Topic, similarity_score) tuples

        Returns:
            List of unique angle descriptions
        """
        if not related_topics:
            return []

        unique_angles = []

        # Generate connection statements
        for topic, similarity in related_topics[:3]:  # Top 3 most similar
            # Extract key concept from related topic (first 3 keywords)
            related_keywords = self.db_manager._extract_keywords(topic.title)
            key_concepts = list(related_keywords)[:3]

            if key_concepts:
                concepts_str = ", ".join(key_concepts[:2])
                angle = f"Connection with {topic.title}: {concepts_str}"
                unique_angles.append(angle)

        return unique_angles

    def _create_synthesis_summary(
        self,
        topic: str,
        related_info: List[Dict],
        themes: List[str],
        unique_angles: List[str]
    ) -> str:
        """
        Create synthesis summary text.

        Args:
            topic: Main topic title
            related_info: Related topic info dicts
            themes: Common themes
            unique_angles: Unique perspectives

        Returns:
            Synthesis summary text
        """
        if not related_info:
            return ""

        # Build summary
        related_titles = [info["title"] for info in related_info]
        related_list = ", ".join(related_titles)

        summary_parts = []

        # Related topics section
        summary_parts.append(
            f"**Related Topics ({len(related_info)})**: {related_list}"
        )

        # Common themes section
        if themes:
            themes_str = ", ".join(themes[:5])
            summary_parts.append(f"**Common Themes**: {themes_str}")

        # Unique angles section
        if unique_angles:
            angles_str = "\n".join(f"- {angle}" for angle in unique_angles)
            summary_parts.append(f"**Unique Perspectives**:\n{angles_str}")

        return "\n\n".join(summary_parts)

    def _suggest_anchor_text(self, main_topic: str, related_topic: str) -> str:
        """
        Suggest anchor text for internal link.

        Extracts key concept from related topic for natural linking.

        Args:
            main_topic: Main topic title
            related_topic: Related topic title

        Returns:
            Suggested anchor text
        """
        # Simple heuristic: use first 3-5 words from related topic
        words = related_topic.split()
        if len(words) <= 5:
            return related_topic
        else:
            return " ".join(words[:5]) + "..."

    def get_related_context_for_writing(
        self,
        topic_id: str,
        max_related: int = 3
    ) -> Optional[str]:
        """
        Get related context formatted for WritingAgent prompt.

        Convenience method that formats synthesis for writing prompts.

        Args:
            topic_id: Topic ID to find related context for
            max_related: Maximum related topics (default: 3)

        Returns:
            Formatted context string, or None if no related topics found

        Example:
            >>> context = synthesizer.get_related_context_for_writing("proptech-trends-2025")
            >>> print(context)
            RELATED CONTEXT (from 3 similar topics):

            1. PropTech Investment Strategies (similarity: 0.45)
               Key insights: ...

            2. Real Estate Technology (similarity: 0.38)
               ...
        """
        # Get synthesis
        synthesis = self.synthesize_related_topics(
            topic="",  # Not needed for this method
            topic_id=topic_id,
            max_related=max_related
        )

        if not synthesis["related_topics"]:
            return None

        # Format for writing prompt
        context_parts = [
            f"RELATED CONTEXT (from {len(synthesis['related_topics'])} similar topics):",
            ""
        ]

        for i, topic_info in enumerate(synthesis["related_topics"], 1):
            context_parts.append(
                f"{i}. {topic_info['title']} (similarity: {topic_info['similarity']})"
            )
            if topic_info["description"]:
                context_parts.append(f"   {topic_info['description'][:150]}...")
            context_parts.append("")

        # Add synthesis summary
        if synthesis["synthesis_summary"]:
            context_parts.append("SYNTHESIS:")
            context_parts.append(synthesis["synthesis_summary"])

        return "\n".join(context_parts)
