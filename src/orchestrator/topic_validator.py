"""
Topic Validator with 5-metric scoring system

Scores topics based on:
1. Keyword relevance (30%) - Jaccard similarity
2. Source diversity (25%) - Collector count / 5
3. Freshness (20%) - Exponential decay
4. Search volume (15%) - Autocomplete position + length
5. Novelty (10%) - MinHash distance

Used in Stage 4.5 of Hybrid Research Orchestrator to filter discovered topics
before expensive research operations.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from datasketch import MinHash

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TopicMetadata:
    """
    Metadata for a discovered topic.

    Used to calculate scoring metrics.
    """
    source: str  # Which collector discovered it (autocomplete, trends, reddit, rss, news)
    timestamp: datetime  # When it was discovered
    sources: List[str] = field(default_factory=list)  # All sources that found this topic
    autocomplete_position: Optional[int] = None  # Position in autocomplete (1-10)
    autocomplete_query_length: Optional[int] = None  # Length of the autocomplete query


@dataclass
class ScoredTopic:
    """
    A topic with calculated scores.
    """
    topic: str
    total_score: float
    metric_scores: Dict[str, float]
    metadata: TopicMetadata

    def __repr__(self) -> str:
        return f"ScoredTopic(topic='{self.topic[:50]}...', score={self.total_score:.3f})"


class TopicValidator:
    """
    Validates and scores topics using 5 metrics.

    Usage:
        validator = TopicValidator()
        scored = validator.score_topic(
            topic="PropTech smart building automation",
            keywords=["PropTech", "IoT", "Building"],
            metadata=TopicMetadata(source="autocomplete", timestamp=datetime.now()),
            existing_topics=["Fashion trends", "Cooking recipes"]
        )
        print(f"Score: {scored.total_score:.2f}")
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        freshness_half_life_days: float = 7.0
    ):
        """
        Initialize validator.

        Args:
            weights: Custom metric weights (must sum to 1.0)
            freshness_half_life_days: Half-life for freshness decay (default: 7 days)
        """
        # Default weights
        self.weights = weights or {
            "relevance": 0.30,
            "diversity": 0.25,
            "freshness": 0.20,
            "volume": 0.15,
            "novelty": 0.10
        }

        # Validate weights sum to 1.0
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.001:
            raise ValueError(
                f"Metric weights must sum to 1.0 (got {weight_sum:.3f}). "
                f"Weights: {self.weights}"
            )

        self.freshness_half_life_days = freshness_half_life_days

        logger.info(
            "topic_validator_initialized",
            weights=self.weights,
            freshness_half_life=freshness_half_life_days
        )

    def calculate_relevance(
        self,
        topic: str,
        keywords: List[str],
        metadata: TopicMetadata
    ) -> float:
        """
        Calculate keyword relevance using Jaccard similarity.

        Args:
            topic: The topic text
            keywords: Seed keywords from customer site/competitors
            metadata: Topic metadata (unused here, for API consistency)

        Returns:
            Relevance score (0.0 - 1.0)
        """
        # Normalize to lowercase and create word sets
        topic_words = set(topic.lower().split())
        keyword_words = set()
        for keyword in keywords:
            keyword_words.update(keyword.lower().split())

        # Jaccard similarity: intersection / union
        if not keyword_words:
            return 0.0

        intersection = topic_words & keyword_words
        union = topic_words | keyword_words

        if not union:
            return 0.0

        similarity = len(intersection) / len(union)

        return min(similarity, 1.0)

    def calculate_diversity(self, sources: List[str]) -> float:
        """
        Calculate source diversity.

        Args:
            sources: List of source names (may contain duplicates)

        Returns:
            Diversity score (0.0 - 1.0)
        """
        if not sources:
            return 0.0

        # Count unique sources (max 5: autocomplete, trends, reddit, rss, news)
        unique_sources = set(sources)
        max_sources = 5

        diversity = len(unique_sources) / max_sources

        return min(diversity, 1.0)

    def calculate_freshness(self, timestamp: datetime) -> float:
        """
        Calculate freshness using exponential decay.

        Args:
            timestamp: When the topic was discovered

        Returns:
            Freshness score (0.0 - 1.0)
        """
        now = datetime.now()

        # Handle timezone-aware vs naive datetimes
        if timestamp.tzinfo is not None and now.tzinfo is None:
            # Make now aware
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        elif timestamp.tzinfo is None and now.tzinfo is not None:
            # Make timestamp aware
            from datetime import timezone
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        age_seconds = (now - timestamp).total_seconds()
        age_days = age_seconds / 86400  # Seconds per day

        # Exponential decay: score = 0.5 ^ (age / half_life)
        decay = 0.5 ** (age_days / self.freshness_half_life_days)

        return min(decay, 1.0)

    def calculate_volume(self, metadata: TopicMetadata) -> float:
        """
        Calculate search volume estimate.

        For autocomplete sources: higher position + longer query = higher volume
        For other sources: return default 0.5

        Args:
            metadata: Topic metadata

        Returns:
            Volume score (0.0 - 1.0)
        """
        # Only autocomplete sources have volume signals
        if metadata.source != "autocomplete":
            return 0.5

        if metadata.autocomplete_position is None:
            return 0.5

        # Position score: 1.0 for position 1, decreases to 0.1 for position 10
        position = metadata.autocomplete_position
        position_score = 1.0 - ((position - 1) / 10)  # 1.0, 0.9, 0.8, ..., 0.1

        # Length score: longer queries suggest more specific/popular searches
        query_length = metadata.autocomplete_query_length or 10
        length_score = min(query_length / 50, 1.0)  # Max at 50 chars

        # Combine: 70% position, 30% length
        volume = 0.7 * position_score + 0.3 * length_score

        return min(volume, 1.0)

    def calculate_novelty(self, topic: str, existing_topics: List[str]) -> float:
        """
        Calculate novelty using MinHash similarity.

        Args:
            topic: The topic text
            existing_topics: Previously discovered topics

        Returns:
            Novelty score (0.0 - 1.0)
        """
        if not existing_topics:
            return 1.0

        # Create MinHash for the topic
        topic_minhash = self._create_minhash(topic)

        # Calculate similarity to each existing topic
        max_similarity = 0.0
        for existing in existing_topics:
            existing_minhash = self._create_minhash(existing)
            similarity = topic_minhash.jaccard(existing_minhash)
            max_similarity = max(max_similarity, similarity)

        # Novelty is inverse of similarity
        novelty = 1.0 - max_similarity

        return novelty

    def _create_minhash(self, text: str, num_perm: int = 128) -> MinHash:
        """
        Create MinHash signature for text.

        Args:
            text: Text to hash
            num_perm: Number of permutations (default: 128)

        Returns:
            MinHash object
        """
        minhash = MinHash(num_perm=num_perm)

        # Tokenize into words and add to MinHash
        words = text.lower().split()
        for word in words:
            minhash.update(word.encode('utf-8'))

        return minhash

    def score_topic(
        self,
        topic: str,
        keywords: List[str],
        metadata: TopicMetadata,
        existing_topics: Optional[List[str]] = None
    ) -> ScoredTopic:
        """
        Calculate complete score for a topic.

        Args:
            topic: The topic text
            keywords: Seed keywords from customer site/competitors
            metadata: Topic metadata
            existing_topics: Previously discovered topics (for novelty)

        Returns:
            ScoredTopic with total score and individual metric scores
        """
        existing_topics = existing_topics or []

        # Calculate all metrics
        relevance = self.calculate_relevance(topic, keywords, metadata)
        diversity = self.calculate_diversity(metadata.sources or [metadata.source])
        freshness = self.calculate_freshness(metadata.timestamp)
        volume = self.calculate_volume(metadata)
        novelty = self.calculate_novelty(topic, existing_topics)

        # Store individual scores
        metric_scores = {
            "relevance": relevance,
            "diversity": diversity,
            "freshness": freshness,
            "volume": volume,
            "novelty": novelty
        }

        # Calculate weighted total
        total_score = (
            self.weights["relevance"] * relevance +
            self.weights["diversity"] * diversity +
            self.weights["freshness"] * freshness +
            self.weights["volume"] * volume +
            self.weights["novelty"] * novelty
        )

        return ScoredTopic(
            topic=topic,
            total_score=total_score,
            metric_scores=metric_scores,
            metadata=metadata
        )

    def filter_topics(
        self,
        topics: List[Tuple[str, TopicMetadata]],
        keywords: List[str],
        threshold: float = 0.6,
        top_n: Optional[int] = None,
        existing_topics: Optional[List[str]] = None
    ) -> List[ScoredTopic]:
        """
        Score and filter topics.

        Args:
            topics: List of (topic, metadata) tuples
            keywords: Seed keywords from customer site/competitors
            threshold: Minimum score threshold (0.0 - 1.0)
            top_n: Maximum number of topics to return (None = no limit)
            existing_topics: Previously discovered topics (for novelty)

        Returns:
            List of ScoredTopic, sorted by score (descending), filtered by threshold and top_n
        """
        existing_topics = existing_topics or []

        # Score all topics
        scored_topics = []
        for topic, metadata in topics:
            scored = self.score_topic(
                topic=topic,
                keywords=keywords,
                metadata=metadata,
                existing_topics=existing_topics
            )
            scored_topics.append(scored)

        # Filter by threshold
        filtered = [st for st in scored_topics if st.total_score >= threshold]

        # Sort by score (descending), then by source diversity (more sources = better), then alphabetically
        filtered.sort(key=lambda st: (
            -st.total_score,  # Primary: Higher score first (negative for descending)
            -len(st.metadata.sources),  # Secondary: More sources = better (tie-breaker)
            st.topic.lower()  # Tertiary: Alphabetical (stable sort)
        ))

        # Limit to top N
        if top_n is not None:
            filtered = filtered[:top_n]

        logger.info(
            "topics_filtered",
            total=len(topics),
            passed_threshold=len(filtered),
            threshold=threshold,
            top_n=top_n
        )

        return filtered
