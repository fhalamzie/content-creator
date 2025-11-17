"""
Difficulty Scorer

Calculates personalized difficulty scores for topics based on competitive analysis.

Scoring factors (0-100 scale, easy→hard):
- Average content quality (40%): Higher quality = harder to compete
- Domain authority distribution (30%): More high-authority domains = harder
- Content length requirements (20%): Longer content = harder to produce
- Freshness requirements (10%): Recent content needed = harder to maintain

Pattern: Service class integrating SERP + Content analysis
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)


# Weights for difficulty calculation (must sum to 1.0)
DIFFICULTY_WEIGHTS = {
    "content_quality": 0.40,    # 40% - Average quality of top 10
    "domain_authority": 0.30,   # 30% - Authority distribution
    "content_length": 0.20,     # 20% - Word count requirements
    "freshness": 0.10           # 10% - Recency requirements
}


@dataclass
class DifficultyScore:
    """Topic difficulty score with recommendations"""
    topic_id: str
    difficulty_score: float  # 0-100 (easy→hard)

    # Component scores (0-1 scale)
    content_quality_score: float
    domain_authority_score: float
    content_length_score: float
    freshness_score: float

    # Recommendations
    target_word_count: int
    target_h2_count: int
    target_image_count: int
    target_quality_score: float  # Beat this to rank

    # Metadata
    avg_competitor_quality: float
    avg_competitor_word_count: int
    high_authority_percentage: float  # % of top 10 with high DA
    freshness_requirement: str  # "< 3 months", "< 6 months", etc.

    # Timing estimates
    estimated_ranking_time: str  # "3-6 months", "6-9 months", etc.
    analyzed_at: datetime


@dataclass
class Recommendation:
    """Actionable recommendation"""
    category: str  # "content", "quality", "timing"
    priority: str  # "critical", "high", "medium", "low"
    message: str
    target_value: Optional[float] = None


class DifficultyScorer:
    """
    Calculate topic difficulty based on competitive analysis.

    Uses SERP results + Content scores to determine:
    - How hard is it to rank for this topic?
    - What quality level do I need to achieve?
    - What content length/structure should I target?
    - How fresh does content need to be?
    """

    def __init__(self):
        """Initialize difficulty scorer."""
        logger.info("difficulty_scorer_initialized")

    def calculate_difficulty(
        self,
        topic_id: str,
        serp_results: List[Dict],
        content_scores: List[Dict]
    ) -> DifficultyScore:
        """
        Calculate difficulty score for a topic.

        Args:
            topic_id: Topic identifier
            serp_results: List of SERP results (from SERPAnalyzer)
            content_scores: List of content scores (from ContentScorer)

        Returns:
            DifficultyScore with recommendations

        Raises:
            ValueError: If inputs are invalid
        """
        logger.info(
            "calculating_difficulty",
            topic_id=topic_id,
            serp_count=len(serp_results),
            score_count=len(content_scores)
        )

        # Validate inputs
        if not serp_results:
            raise ValueError("SERP results required for difficulty calculation")

        if not content_scores:
            raise ValueError("Content scores required for difficulty calculation")

        # Calculate component scores
        quality_score, avg_quality = self._score_content_quality(content_scores)
        authority_score, high_da_pct = self._score_domain_authority(serp_results)
        length_score, avg_length = self._score_content_length(content_scores)
        fresh_score, fresh_req = self._score_freshness_requirement(content_scores)

        # Calculate overall difficulty (0-1 scale)
        difficulty = (
            quality_score * DIFFICULTY_WEIGHTS["content_quality"] +
            authority_score * DIFFICULTY_WEIGHTS["domain_authority"] +
            length_score * DIFFICULTY_WEIGHTS["content_length"] +
            fresh_score * DIFFICULTY_WEIGHTS["freshness"]
        )

        # Scale to 0-100
        difficulty_score = difficulty * 100

        # Generate recommendations
        target_word_count = self._calculate_target_word_count(content_scores)
        target_h2_count = self._calculate_target_h2_count(content_scores)
        target_image_count = self._calculate_target_image_count(content_scores)
        target_quality = self._calculate_target_quality(content_scores)
        ranking_time = self._estimate_ranking_time(difficulty_score, avg_quality)

        logger.info(
            "difficulty_calculated",
            topic_id=topic_id,
            difficulty=difficulty_score,
            avg_quality=avg_quality,
            avg_length=avg_length,
            high_da_pct=high_da_pct
        )

        return DifficultyScore(
            topic_id=topic_id,
            difficulty_score=difficulty_score,
            content_quality_score=quality_score,
            domain_authority_score=authority_score,
            content_length_score=length_score,
            freshness_score=fresh_score,
            target_word_count=target_word_count,
            target_h2_count=target_h2_count,
            target_image_count=target_image_count,
            target_quality_score=target_quality,
            avg_competitor_quality=avg_quality,
            avg_competitor_word_count=avg_length,
            high_authority_percentage=high_da_pct,
            freshness_requirement=fresh_req,
            estimated_ranking_time=ranking_time,
            analyzed_at=datetime.utcnow()
        )

    def _score_content_quality(
        self,
        content_scores: List[Dict]
    ) -> Tuple[float, float]:
        """
        Score difficulty based on average competitor quality.

        Higher average quality = harder to compete.

        Returns:
            (difficulty_score, avg_quality)
        """
        qualities = [s["quality_score"] for s in content_scores]
        avg_quality = sum(qualities) / len(qualities)

        # Map quality to difficulty (0-1 scale)
        # 60-70 quality: 0.3 difficulty (easy)
        # 70-80 quality: 0.5 difficulty (medium)
        # 80-90 quality: 0.7 difficulty (hard)
        # 90+ quality: 0.9 difficulty (very hard)
        if avg_quality < 70:
            difficulty = 0.3
        elif avg_quality < 80:
            # Linear 0.3 to 0.5
            difficulty = 0.3 + ((avg_quality - 70) / 10) * 0.2
        elif avg_quality < 90:
            # Linear 0.5 to 0.7
            difficulty = 0.5 + ((avg_quality - 80) / 10) * 0.2
        else:
            # Linear 0.7 to 0.9
            difficulty = 0.7 + ((avg_quality - 90) / 10) * 0.2
            difficulty = min(difficulty, 0.9)

        return difficulty, avg_quality

    def _score_domain_authority(
        self,
        serp_results: List[Dict]
    ) -> Tuple[float, float]:
        """
        Score difficulty based on domain authority distribution.

        More high-authority domains = harder to compete.

        Returns:
            (difficulty_score, high_authority_percentage)
        """
        if not serp_results:
            return 0.5, 0.0

        # Count high-authority domains
        high_authority = sum(
            1 for r in serp_results
            if r.get("domain_authority") in ["High", "Medium-High"]
        )

        high_da_pct = (high_authority / len(serp_results)) * 100

        # Map to difficulty (0-1 scale)
        # 0-20% high DA: 0.2 difficulty (easy)
        # 20-40% high DA: 0.4 difficulty (medium-easy)
        # 40-60% high DA: 0.6 difficulty (medium-hard)
        # 60-80% high DA: 0.8 difficulty (hard)
        # 80-100% high DA: 1.0 difficulty (very hard)
        if high_da_pct < 20:
            difficulty = 0.2
        elif high_da_pct < 40:
            difficulty = 0.2 + ((high_da_pct - 20) / 20) * 0.2
        elif high_da_pct < 60:
            difficulty = 0.4 + ((high_da_pct - 40) / 20) * 0.2
        elif high_da_pct < 80:
            difficulty = 0.6 + ((high_da_pct - 60) / 20) * 0.2
        else:
            difficulty = 0.8 + ((high_da_pct - 80) / 20) * 0.2

        return difficulty, high_da_pct

    def _score_content_length(
        self,
        content_scores: List[Dict]
    ) -> Tuple[float, int]:
        """
        Score difficulty based on average content length.

        Longer content = harder to produce consistently.

        Returns:
            (difficulty_score, avg_word_count)
        """
        word_counts = [s["word_count"] for s in content_scores if s.get("word_count")]

        if not word_counts:
            return 0.5, 0

        avg_length = int(sum(word_counts) / len(word_counts))

        # Map to difficulty (0-1 scale)
        # <1000 words: 0.2 difficulty (easy)
        # 1000-2000: 0.4 difficulty (medium-easy)
        # 2000-3000: 0.6 difficulty (medium-hard)
        # 3000-4000: 0.8 difficulty (hard)
        # >4000: 1.0 difficulty (very hard)
        if avg_length < 1000:
            difficulty = 0.2
        elif avg_length < 2000:
            difficulty = 0.2 + ((avg_length - 1000) / 1000) * 0.2
        elif avg_length < 3000:
            difficulty = 0.4 + ((avg_length - 2000) / 1000) * 0.2
        elif avg_length < 4000:
            difficulty = 0.6 + ((avg_length - 3000) / 1000) * 0.2
        else:
            difficulty = 0.8 + ((avg_length - 4000) / 1000) * 0.2
            difficulty = min(difficulty, 1.0)

        return difficulty, avg_length

    def _score_freshness_requirement(
        self,
        content_scores: List[Dict]
    ) -> Tuple[float, str]:
        """
        Score difficulty based on freshness requirements.

        Recent content needed = harder to maintain.

        Returns:
            (difficulty_score, freshness_requirement_string)
        """
        # Count content by age
        fresh_count = sum(
            1 for s in content_scores
            if s.get("freshness_score", 0) >= 0.9  # < 6 months
        )

        if not content_scores:
            return 0.5, "Unknown"

        fresh_pct = (fresh_count / len(content_scores)) * 100

        # Map to difficulty and requirement
        if fresh_pct >= 70:
            difficulty = 0.8
            requirement = "< 3 months"
        elif fresh_pct >= 50:
            difficulty = 0.6
            requirement = "< 6 months"
        elif fresh_pct >= 30:
            difficulty = 0.4
            requirement = "< 12 months"
        else:
            difficulty = 0.2
            requirement = "< 24 months"

        return difficulty, requirement

    def _calculate_target_word_count(self, content_scores: List[Dict]) -> int:
        """Calculate target word count (beat average by 10%)."""
        word_counts = [s["word_count"] for s in content_scores if s.get("word_count")]

        if not word_counts:
            return 2000  # Default

        avg_length = sum(word_counts) / len(word_counts)

        # Beat average by 10%, round to nearest 100
        target = int((avg_length * 1.1) / 100) * 100

        return target

    def _calculate_target_h2_count(self, content_scores: List[Dict]) -> int:
        """Calculate target H2 count (match or beat average)."""
        h2_counts = [s["h2_count"] for s in content_scores if s.get("h2_count")]

        if not h2_counts:
            return 5  # Default

        avg_h2 = sum(h2_counts) / len(h2_counts)

        # Round up to match or beat
        return int(avg_h2) + 1

    def _calculate_target_image_count(self, content_scores: List[Dict]) -> int:
        """Calculate target image count (match or beat average)."""
        image_counts = [s["image_count"] for s in content_scores if s.get("image_count")]

        if not image_counts:
            return 3  # Default

        avg_images = sum(image_counts) / len(image_counts)

        # Round up to match or beat
        return int(avg_images) + 1

    def _calculate_target_quality(self, content_scores: List[Dict]) -> float:
        """Calculate target quality score (beat top 3 average)."""
        qualities = sorted(
            [s["quality_score"] for s in content_scores],
            reverse=True
        )

        # Average of top 3
        top_3 = qualities[:3]
        avg_top = sum(top_3) / len(top_3)

        # Beat by 5 points
        target = avg_top + 5

        return min(target, 100.0)

    def _estimate_ranking_time(
        self,
        difficulty_score: float,
        avg_quality: float
    ) -> str:
        """
        Estimate time to rank based on difficulty.

        Assumes consistent content production + SEO optimization.
        """
        if difficulty_score < 40:
            return "2-4 months"
        elif difficulty_score < 60:
            return "4-6 months"
        elif difficulty_score < 75:
            return "6-9 months"
        elif difficulty_score < 85:
            return "9-12 months"
        else:
            return "12-18 months"

    def generate_recommendations(
        self,
        difficulty_score: DifficultyScore
    ) -> List[Recommendation]:
        """
        Generate actionable recommendations based on difficulty analysis.

        Args:
            difficulty_score: Calculated difficulty score

        Returns:
            List of prioritized recommendations
        """
        recommendations = []

        # Content length recommendation
        if difficulty_score.target_word_count > 2500:
            recommendations.append(Recommendation(
                category="content",
                priority="critical",
                message=f"Target {difficulty_score.target_word_count:,} words "
                        f"(competitors average {difficulty_score.avg_competitor_word_count:,})",
                target_value=float(difficulty_score.target_word_count)
            ))
        else:
            recommendations.append(Recommendation(
                category="content",
                priority="high",
                message=f"Target {difficulty_score.target_word_count:,} words",
                target_value=float(difficulty_score.target_word_count)
            ))

        # Structure recommendations
        recommendations.append(Recommendation(
            category="content",
            priority="high",
            message=f"Include {difficulty_score.target_h2_count} H2 sections "
                    f"and {difficulty_score.target_image_count} images",
            target_value=float(difficulty_score.target_h2_count)
        ))

        # Quality recommendation
        if difficulty_score.avg_competitor_quality > 85:
            recommendations.append(Recommendation(
                category="quality",
                priority="critical",
                message=f"Target quality score: {difficulty_score.target_quality_score:.1f}/100 "
                        f"(competitors average {difficulty_score.avg_competitor_quality:.1f})",
                target_value=difficulty_score.target_quality_score
            ))
        else:
            recommendations.append(Recommendation(
                category="quality",
                priority="high",
                message=f"Target quality score: {difficulty_score.target_quality_score:.1f}/100",
                target_value=difficulty_score.target_quality_score
            ))

        # Freshness recommendation
        if difficulty_score.freshness_requirement in ["< 3 months", "< 6 months"]:
            recommendations.append(Recommendation(
                category="timing",
                priority="high",
                message=f"Content must be updated every {difficulty_score.freshness_requirement}"
            ))

        # Domain authority warning
        if difficulty_score.high_authority_percentage > 60:
            recommendations.append(Recommendation(
                category="quality",
                priority="critical",
                message=f"High difficulty: {difficulty_score.high_authority_percentage:.0f}% "
                        f"of top results are high-authority domains",
                target_value=difficulty_score.high_authority_percentage
            ))

        # Ranking timeline
        recommendations.append(Recommendation(
            category="timing",
            priority="medium",
            message=f"Estimated ranking time: {difficulty_score.estimated_ranking_time}",
        ))

        # Overall difficulty assessment
        if difficulty_score.difficulty_score > 75:
            recommendations.insert(0, Recommendation(
                category="quality",
                priority="critical",
                message=f"Very high difficulty ({difficulty_score.difficulty_score:.0f}/100) - "
                        f"requires exceptional content quality and SEO",
                target_value=difficulty_score.difficulty_score
            ))
        elif difficulty_score.difficulty_score > 60:
            recommendations.insert(0, Recommendation(
                category="quality",
                priority="high",
                message=f"High difficulty ({difficulty_score.difficulty_score:.0f}/100) - "
                        f"strong content and SEO needed",
                target_value=difficulty_score.difficulty_score
            ))
        else:
            recommendations.insert(0, Recommendation(
                category="quality",
                priority="medium",
                message=f"Moderate difficulty ({difficulty_score.difficulty_score:.0f}/100) - "
                        f"achievable with quality content",
                target_value=difficulty_score.difficulty_score
            ))

        logger.info(
            "recommendations_generated",
            topic_id=difficulty_score.topic_id,
            count=len(recommendations)
        )

        return recommendations

    def score_to_dict(self, score: DifficultyScore) -> Dict:
        """Convert DifficultyScore to dict for database storage."""
        return {
            "topic_id": score.topic_id,
            "difficulty_score": score.difficulty_score,
            "content_quality_score": score.content_quality_score,
            "domain_authority_score": score.domain_authority_score,
            "content_length_score": score.content_length_score,
            "freshness_score": score.freshness_score,
            "target_word_count": score.target_word_count,
            "target_h2_count": score.target_h2_count,
            "target_image_count": score.target_image_count,
            "target_quality_score": score.target_quality_score,
            "avg_competitor_quality": score.avg_competitor_quality,
            "avg_competitor_word_count": score.avg_competitor_word_count,
            "high_authority_percentage": score.high_authority_percentage,
            "freshness_requirement": score.freshness_requirement,
            "estimated_ranking_time": score.estimated_ranking_time,
            "analyzed_at": score.analyzed_at.isoformat()
        }
