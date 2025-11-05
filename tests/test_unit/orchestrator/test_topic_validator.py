"""
Unit tests for TopicValidator

Tests the 5-metric scoring system for topic validation:
1. Keyword relevance (30%) - Jaccard similarity
2. Source diversity (25%) - Collector count / 5
3. Freshness (20%) - Exponential decay
4. Search volume (15%) - Autocomplete position + length
5. Novelty (10%) - MinHash distance

TDD: Tests written BEFORE implementation
"""

import pytest
from datetime import datetime, timedelta
from src.orchestrator.topic_validator import (
    TopicValidator,
    ScoredTopic,
    TopicMetadata
)


class TestTopicValidatorInit:
    """Test TopicValidator initialization"""

    def test_init_default_weights(self):
        """Test initialization with default metric weights"""
        validator = TopicValidator()

        assert validator.weights["relevance"] == 0.30
        assert validator.weights["diversity"] == 0.25
        assert validator.weights["freshness"] == 0.20
        assert validator.weights["volume"] == 0.15
        assert validator.weights["novelty"] == 0.10

        # Weights should sum to 1.0
        assert abs(sum(validator.weights.values()) - 1.0) < 0.001

    def test_init_custom_weights(self):
        """Test initialization with custom weights"""
        custom_weights = {
            "relevance": 0.5,
            "diversity": 0.2,
            "freshness": 0.1,
            "volume": 0.1,
            "novelty": 0.1
        }
        validator = TopicValidator(weights=custom_weights)

        assert validator.weights == custom_weights
        assert abs(sum(validator.weights.values()) - 1.0) < 0.001

    def test_init_invalid_weights_sum(self):
        """Test that invalid weights (not summing to 1.0) raise error"""
        invalid_weights = {
            "relevance": 0.5,
            "diversity": 0.5,
            "freshness": 0.5,
            "volume": 0.5,
            "novelty": 0.5
        }

        with pytest.raises(ValueError, match="must sum to 1.0"):
            TopicValidator(weights=invalid_weights)


class TestKeywordRelevance:
    """Test keyword relevance scoring (Jaccard similarity)"""

    def test_relevance_exact_match(self):
        """Test relevance when topic exactly matches all keywords"""
        validator = TopicValidator()
        keywords = ["PropTech", "Smart Building", "IoT"]
        topic = "PropTech Smart Building IoT solutions"
        metadata = TopicMetadata(source="autocomplete", timestamp=datetime.now())

        score = validator.calculate_relevance(topic, keywords, metadata)

        # Exact match should score high (>= 0.8)
        assert score >= 0.8
        assert score <= 1.0

    def test_relevance_partial_match(self):
        """Test relevance with partial keyword match"""
        validator = TopicValidator()
        keywords = ["PropTech", "Smart Building", "IoT", "Energy", "Automation"]
        topic = "PropTech Smart Building solutions"  # Only 2/5 keywords
        metadata = TopicMetadata(source="autocomplete", timestamp=datetime.now())

        score = validator.calculate_relevance(topic, keywords, metadata)

        # Partial match should score medium (0.3-0.7)
        assert 0.3 <= score <= 0.7

    def test_relevance_no_match(self):
        """Test relevance with no keyword matches"""
        validator = TopicValidator()
        keywords = ["PropTech", "Smart Building", "IoT"]
        topic = "Fashion design trends 2025"
        metadata = TopicMetadata(source="autocomplete", timestamp=datetime.now())

        score = validator.calculate_relevance(topic, keywords, metadata)

        # No match should score low (<= 0.2)
        assert score <= 0.2
        assert score >= 0.0

    def test_relevance_case_insensitive(self):
        """Test that relevance scoring is case-insensitive"""
        validator = TopicValidator()
        keywords = ["PropTech", "SMART BUILDING"]
        topic1 = "proptech smart building"
        topic2 = "PROPTECH SMART BUILDING"
        metadata = TopicMetadata(source="autocomplete", timestamp=datetime.now())

        score1 = validator.calculate_relevance(topic1, keywords, metadata)
        score2 = validator.calculate_relevance(topic2, keywords, metadata)

        assert score1 == score2


class TestSourceDiversity:
    """Test source diversity scoring"""

    def test_diversity_all_sources(self):
        """Test diversity when topic appears in all 5 collectors"""
        validator = TopicValidator()
        sources = ["autocomplete", "trends", "reddit", "rss", "news"]

        score = validator.calculate_diversity(sources)

        # All 5 sources = max score (1.0)
        assert score == 1.0

    def test_diversity_single_source(self):
        """Test diversity with only 1 source"""
        validator = TopicValidator()
        sources = ["autocomplete"]

        score = validator.calculate_diversity(sources)

        # 1/5 sources = 0.2
        assert score == 0.2

    def test_diversity_duplicate_sources(self):
        """Test that duplicate sources are counted once"""
        validator = TopicValidator()
        sources = ["autocomplete", "autocomplete", "autocomplete"]

        score = validator.calculate_diversity(sources)

        # Should count unique sources only (1/5 = 0.2)
        assert score == 0.2

    def test_diversity_empty_sources(self):
        """Test diversity with no sources"""
        validator = TopicValidator()
        sources = []

        score = validator.calculate_diversity(sources)

        assert score == 0.0


class TestFreshness:
    """Test freshness scoring (exponential decay)"""

    def test_freshness_current_timestamp(self):
        """Test freshness for topic discovered right now"""
        validator = TopicValidator()
        timestamp = datetime.now()

        score = validator.calculate_freshness(timestamp)

        # Current timestamp should score 1.0
        assert score >= 0.99  # Allow tiny float precision errors
        assert score <= 1.0

    def test_freshness_one_day_old(self):
        """Test freshness for 1-day-old topic"""
        validator = TopicValidator()
        timestamp = datetime.now() - timedelta(days=1)

        score = validator.calculate_freshness(timestamp)

        # Should have some decay but still relatively high
        assert 0.7 <= score <= 0.95

    def test_freshness_one_week_old(self):
        """Test freshness for 1-week-old topic"""
        validator = TopicValidator()
        timestamp = datetime.now() - timedelta(days=7)

        score = validator.calculate_freshness(timestamp)

        # Should have significant decay
        assert 0.3 <= score <= 0.7

    def test_freshness_one_month_old(self):
        """Test freshness for 1-month-old topic"""
        validator = TopicValidator()
        timestamp = datetime.now() - timedelta(days=30)

        score = validator.calculate_freshness(timestamp)

        # Very old topics should score very low
        assert score <= 0.3
        assert score >= 0.0

    def test_freshness_half_life(self):
        """Test that freshness has expected half-life (default 7 days)"""
        validator = TopicValidator(freshness_half_life_days=7)
        now = datetime.now()
        one_half_life = now - timedelta(days=7)
        two_half_lives = now - timedelta(days=14)

        score_now = validator.calculate_freshness(now)
        score_1hl = validator.calculate_freshness(one_half_life)
        score_2hl = validator.calculate_freshness(two_half_lives)

        # After 1 half-life, score should be ~0.5
        assert 0.45 <= score_1hl <= 0.55

        # After 2 half-lives, score should be ~0.25
        assert 0.20 <= score_2hl <= 0.30


class TestSearchVolume:
    """Test search volume scoring (autocomplete position + length)"""

    def test_volume_top_position_long_query(self):
        """Test volume for top autocomplete position with long query"""
        validator = TopicValidator()
        metadata = TopicMetadata(
            source="autocomplete",
            timestamp=datetime.now(),
            autocomplete_position=1,
            autocomplete_query_length=50
        )

        score = validator.calculate_volume(metadata)

        # Top position + long query = high score
        assert score >= 0.8
        assert score <= 1.0

    def test_volume_bottom_position_short_query(self):
        """Test volume for bottom position with short query"""
        validator = TopicValidator()
        metadata = TopicMetadata(
            source="autocomplete",
            timestamp=datetime.now(),
            autocomplete_position=10,
            autocomplete_query_length=5
        )

        score = validator.calculate_volume(metadata)

        # Bottom position + short query = low score
        assert score <= 0.3

    def test_volume_non_autocomplete_source(self):
        """Test volume for non-autocomplete source (should return 0.5)"""
        validator = TopicValidator()
        metadata = TopicMetadata(source="reddit", timestamp=datetime.now())

        score = validator.calculate_volume(metadata)

        # Non-autocomplete sources get default score
        assert score == 0.5


class TestNovelty:
    """Test novelty scoring (MinHash distance)"""

    def test_novelty_unique_topic(self):
        """Test novelty for completely unique topic"""
        validator = TopicValidator()
        topic = "PropTech AI-powered smart building automation"
        existing_topics = [
            "Fashion trends 2025",
            "Cooking recipes vegetarian",
            "Sports news football"
        ]

        score = validator.calculate_novelty(topic, existing_topics)

        # Completely different = high novelty
        assert score >= 0.8
        assert score <= 1.0

    def test_novelty_duplicate_topic(self):
        """Test novelty for exact duplicate"""
        validator = TopicValidator()
        topic = "PropTech smart building"
        existing_topics = [
            "PropTech smart building",
            "Fashion trends",
            "Cooking recipes"
        ]

        score = validator.calculate_novelty(topic, existing_topics)

        # Exact duplicate = very low novelty
        assert score <= 0.2

    def test_novelty_similar_topic(self):
        """Test novelty for similar but not identical topic"""
        validator = TopicValidator()
        topic = "PropTech IoT building automation"
        existing_topics = [
            "PropTech smart building solutions",
            "IoT building management systems"
        ]

        score = validator.calculate_novelty(topic, existing_topics)

        # Similar = medium novelty
        assert 0.3 <= score <= 0.7

    def test_novelty_empty_existing_topics(self):
        """Test novelty with no existing topics"""
        validator = TopicValidator()
        topic = "PropTech smart building"
        existing_topics = []

        score = validator.calculate_novelty(topic, existing_topics)

        # No existing topics = max novelty
        assert score == 1.0


class TestFullScoring:
    """Test complete topic scoring"""

    def test_score_topic_high_quality(self):
        """Test scoring for high-quality topic"""
        validator = TopicValidator()
        keywords = ["PropTech", "Smart Building", "IoT"]
        topic = "PropTech Smart Building IoT automation solutions"
        metadata = TopicMetadata(
            source="autocomplete",
            timestamp=datetime.now(),
            autocomplete_position=1,
            autocomplete_query_length=50,
            sources=["autocomplete", "trends", "reddit", "rss", "news"]
        )
        existing_topics = ["Fashion trends 2025", "Cooking recipes"]

        scored_topic = validator.score_topic(
            topic=topic,
            keywords=keywords,
            metadata=metadata,
            existing_topics=existing_topics
        )

        # High-quality topic should score > 0.7
        assert scored_topic.total_score >= 0.7
        assert scored_topic.topic == topic
        assert "relevance" in scored_topic.metric_scores
        assert "diversity" in scored_topic.metric_scores
        assert "freshness" in scored_topic.metric_scores
        assert "volume" in scored_topic.metric_scores
        assert "novelty" in scored_topic.metric_scores

    def test_score_topic_low_quality(self):
        """Test scoring for low-quality topic"""
        validator = TopicValidator()
        keywords = ["PropTech", "Smart Building", "IoT"]
        topic = "Fashion design trends 2025"  # Completely irrelevant
        metadata = TopicMetadata(
            source="rss",
            timestamp=datetime.now() - timedelta(days=30),  # Very old
            sources=["rss"]  # Only 1 source
        )
        existing_topics = [
            "Fashion design trends 2025",  # Duplicate
            "Fashion trends for spring"
        ]

        scored_topic = validator.score_topic(
            topic=topic,
            keywords=keywords,
            metadata=metadata,
            existing_topics=existing_topics
        )

        # Low-quality topic should score < 0.4
        assert scored_topic.total_score <= 0.4


class TestFilterTopics:
    """Test topic filtering"""

    def test_filter_topics_by_threshold(self):
        """Test filtering topics by minimum score threshold"""
        validator = TopicValidator()
        keywords = ["PropTech", "Smart Building"]

        topics = [
            ("PropTech Smart Building automation", TopicMetadata(
                source="autocomplete", timestamp=datetime.now(),
                sources=["autocomplete", "trends", "reddit"]
            )),
            ("Fashion design trends", TopicMetadata(
                source="rss", timestamp=datetime.now() - timedelta(days=30),
                sources=["rss"]
            )),
            ("PropTech IoT solutions", TopicMetadata(
                source="trends", timestamp=datetime.now(),
                sources=["trends", "autocomplete"]
            ))
        ]

        # Filter with threshold=0.5, no limit
        filtered = validator.filter_topics(
            topics=topics,
            keywords=keywords,
            threshold=0.5,
            top_n=None
        )

        # Should keep high-scoring topics, filter low-scoring
        assert len(filtered) >= 2
        assert all(st.total_score >= 0.5 for st in filtered)

    def test_filter_topics_top_n(self):
        """Test filtering topics by top N limit"""
        validator = TopicValidator()
        keywords = ["PropTech"]

        topics = [
            (f"PropTech topic {i}", TopicMetadata(
                source="autocomplete", timestamp=datetime.now(),
                sources=["autocomplete", "trends"]
            ))
            for i in range(10)
        ]

        # Filter top 5 only
        filtered = validator.filter_topics(
            topics=topics,
            keywords=keywords,
            threshold=0.0,
            top_n=5
        )

        assert len(filtered) == 5

    def test_filter_topics_sorted_by_score(self):
        """Test that filtered topics are sorted by score (descending)"""
        validator = TopicValidator()
        keywords = ["PropTech", "Smart Building"]

        topics = [
            ("PropTech Smart Building automation IoT", TopicMetadata(
                source="autocomplete", timestamp=datetime.now(),
                sources=["autocomplete", "trends", "reddit", "rss", "news"]
            )),
            ("PropTech", TopicMetadata(
                source="rss", timestamp=datetime.now() - timedelta(days=20),
                sources=["rss"]
            )),
            ("PropTech Smart Building", TopicMetadata(
                source="trends", timestamp=datetime.now(),
                sources=["trends", "autocomplete", "reddit"]
            ))
        ]

        filtered = validator.filter_topics(
            topics=topics,
            keywords=keywords,
            threshold=0.0,
            top_n=None
        )

        # Verify scores are descending
        for i in range(len(filtered) - 1):
            assert filtered[i].total_score >= filtered[i + 1].total_score
