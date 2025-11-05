"""
Smoke test for Stage 4.5 (Topic Validation) integration

Validates that TopicValidator is properly integrated into HybridResearchOrchestrator
and that the 5-metric scoring system works end-to-end.
"""

import pytest
from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator


class TestStage4_5Integration:
    """Integration test for Stage 4.5 topic validation"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance"""
        return HybridResearchOrchestrator(
            enable_tavily=False,
            enable_searxng=False,
            enable_gemini=False,
            enable_rss=False,
            enable_thenewsapi=False,
            enable_reranking=False,
            enable_synthesis=False
        )

    def test_stage4_5_validate_and_score_topics(self, orchestrator):
        """Test that Stage 4.5 filters topics by relevance score"""
        # Arrange
        discovered_topics = [
            "PropTech Smart Building automation solutions",  # High relevance
            "PropTech IoT sensors for buildings",  # High relevance
            "Smart Building energy management",  # Medium relevance
            "Fashion trends 2025",  # Low relevance (irrelevant)
            "Cooking recipes vegetarian",  # Low relevance (irrelevant)
            "PropTech building management systems",  # High relevance
        ]

        topics_by_source = {
            "autocomplete": [
                "PropTech Smart Building automation solutions",
                "PropTech IoT sensors for buildings"
            ],
            "trends": [
                "Smart Building energy management",
                "PropTech building management systems"
            ],
            "reddit": ["Fashion trends 2025"],
            "rss": ["Cooking recipes vegetarian"]
        }

        consolidated_keywords = ["PropTech", "Smart Building", "IoT", "Building Automation"]

        # Act
        result = orchestrator.validate_and_score_topics(
            discovered_topics=discovered_topics,
            topics_by_source=topics_by_source,
            consolidated_keywords=consolidated_keywords,
            threshold=0.5,
            top_n=10
        )

        # Assert - Structure
        assert "scored_topics" in result
        assert "filtered_count" in result
        assert "rejected_count" in result
        assert "avg_score" in result

        # Assert - Filtering behavior
        assert result["filtered_count"] > 0, "Should have some topics that pass threshold"
        assert result["filtered_count"] <= len(discovered_topics), "Cannot have more topics than input"
        assert result["rejected_count"] >= 0, "Rejected count should be non-negative"

        # Assert - Scoring
        assert result["avg_score"] >= 0.5, "Average score should be above threshold"
        assert result["avg_score"] <= 1.0, "Average score cannot exceed 1.0"

        # Assert - Relevant topics scored higher
        scored_topics = result["scored_topics"]
        if scored_topics:
            # Top scored topic should be PropTech-related
            top_topic = scored_topics[0].topic
            assert "PropTech" in top_topic or "Smart Building" in top_topic or "IoT" in top_topic, \
                f"Top topic should be relevant, got: {top_topic}"

            # Fashion/Cooking topics should be filtered out or score very low
            irrelevant_topics = ["Fashion trends 2025", "Cooking recipes vegetarian"]
            top_topic_texts = [st.topic for st in scored_topics[:3]]
            for irrelevant in irrelevant_topics:
                assert irrelevant not in top_topic_texts, \
                    f"Irrelevant topic '{irrelevant}' should not be in top 3"

        print(f"\n{'='*60}")
        print("Stage 4.5 Validation Results")
        print(f"{'='*60}")
        print(f"Total topics: {len(discovered_topics)}")
        print(f"Filtered topics: {result['filtered_count']}")
        print(f"Rejected topics: {result['rejected_count']}")
        print(f"Average score: {result['avg_score']:.3f}")
        print(f"\nTop 3 scored topics:")
        for i, st in enumerate(scored_topics[:3], 1):
            print(f"{i}. [{st.total_score:.3f}] {st.topic}")
        print(f"{'='*60}\n")

    def test_stage4_5_empty_topics(self, orchestrator):
        """Test Stage 4.5 handles empty topic list gracefully"""
        # Arrange
        discovered_topics = []
        topics_by_source = {}
        consolidated_keywords = ["PropTech", "Smart Building"]

        # Act
        result = orchestrator.validate_and_score_topics(
            discovered_topics=discovered_topics,
            topics_by_source=topics_by_source,
            consolidated_keywords=consolidated_keywords,
            threshold=0.6,
            top_n=10
        )

        # Assert
        assert result["filtered_count"] == 0
        assert result["rejected_count"] == 0
        assert result["avg_score"] == 0.0
        assert result["scored_topics"] == []

    def test_stage4_5_high_threshold_filters_more(self, orchestrator):
        """Test that higher threshold filters out more topics"""
        # Arrange
        discovered_topics = [
            "PropTech Smart Building automation solutions",
            "PropTech IoT sensors",
            "Smart Building energy",
            "Fashion trends 2025"
        ]
        topics_by_source = {
            "autocomplete": discovered_topics
        }
        consolidated_keywords = ["PropTech", "Smart Building"]

        # Act - Low threshold (0.4)
        result_low = orchestrator.validate_and_score_topics(
            discovered_topics=discovered_topics,
            topics_by_source=topics_by_source,
            consolidated_keywords=consolidated_keywords,
            threshold=0.4,
            top_n=10
        )

        # Act - High threshold (0.7)
        result_high = orchestrator.validate_and_score_topics(
            discovered_topics=discovered_topics,
            topics_by_source=topics_by_source,
            consolidated_keywords=consolidated_keywords,
            threshold=0.7,
            top_n=10
        )

        # Assert - Higher threshold should filter more
        assert result_high["filtered_count"] <= result_low["filtered_count"], \
            "Higher threshold should filter out more topics"

        # If any topics passed high threshold, their score should be >= 0.7
        if result_high["scored_topics"]:
            for st in result_high["scored_topics"]:
                assert st.total_score >= 0.7, \
                    f"Topic '{st.topic}' score {st.total_score:.3f} below threshold 0.7"
