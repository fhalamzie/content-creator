"""
Opportunity Scorer

AI-powered opportunity scoring for keywords using 4 weighted algorithms:
1. SEO Opportunity (30%): (100 - difficulty) * (volume_normalized)
2. Gap Score (25%): Count of content gaps vs competitors
3. Intent Alignment (25%): Commercial/Transactional > Informational > Navigational
4. Trending Momentum (20%): Trending up > Stable > Trending down

Example:
    from src.scoring.opportunity_scorer import OpportunityScorer

    scorer = OpportunityScorer()

    # Calculate opportunity score
    score = scorer.calculate_opportunity_score(
        keyword_data={'keyword': 'PropTech', 'difficulty': 45, ...},
        content_gaps=['No beginner content'],
        trending_topics=['PropTech AI']
    )

    # Get AI recommendation
    explanation = scorer.explain_opportunity(keyword_data, score, content_gaps, trending_topics)
"""

from typing import Dict, List, Optional, Any
import os
import google.generativeai as genai
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpportunityScorerError(Exception):
    """Raised when opportunity scoring fails"""
    pass


class OpportunityScorer:
    """
    Calculate opportunity scores for keywords using 4 weighted algorithms

    Features:
    - SEO opportunity based on difficulty and search volume
    - Content gap analysis
    - Search intent alignment scoring
    - Trending momentum detection
    - AI-powered recommendations via Gemini API (FREE)
    - Custom weight configuration for advanced users
    """

    DEFAULT_WEIGHTS = {
        'seo_opportunity': 0.30,
        'gap_score': 0.25,
        'intent_alignment': 0.25,
        'trending_momentum': 0.20
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize opportunity scorer

        Args:
            weights: Optional custom weights for 4 algorithms (must sum to 1.0)

        Raises:
            OpportunityScorerError: If weights don't sum to 1.0
        """
        self.weights = weights if weights else self.DEFAULT_WEIGHTS.copy()

        # Validate weights
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:  # Allow small float error
            raise OpportunityScorerError(f"Weights must sum to 1.0 (got {weight_sum})")

        logger.info("opportunity_scorer_initialized", weights=self.weights)

    def calculate_opportunity_score(
        self,
        keyword_data: Dict[str, Any],
        content_gaps: List[str],
        trending_topics: List[str]
    ) -> float:
        """
        Calculate overall opportunity score using weighted combination

        Args:
            keyword_data: Keyword dict with difficulty, search_volume, intent, keyword
            content_gaps: List of content gaps from competitor analysis
            trending_topics: List of trending topics

        Returns:
            Opportunity score (0-100)
        """
        # Calculate individual scores
        seo_score = self._calculate_seo_opportunity(keyword_data)
        gap_score = self._calculate_gap_score(content_gaps)
        intent_score = self._calculate_intent_alignment(keyword_data)
        trending_score = self._calculate_trending_momentum(keyword_data, trending_topics)

        # Weighted combination
        final_score = (
            seo_score * self.weights['seo_opportunity'] +
            gap_score * self.weights['gap_score'] +
            intent_score * self.weights['intent_alignment'] +
            trending_score * self.weights['trending_momentum']
        )

        logger.info(
            "opportunity_score_calculated",
            keyword=keyword_data.get('keyword'),
            seo_score=seo_score,
            gap_score=gap_score,
            intent_score=intent_score,
            trending_score=trending_score,
            final_score=final_score
        )

        return round(final_score, 1)

    def calculate_custom_score(
        self,
        keyword_data: Dict[str, Any],
        content_gaps: List[str],
        trending_topics: List[str],
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate opportunity score with custom weights (advanced users)

        Args:
            keyword_data: Keyword dict
            content_gaps: List of content gaps
            trending_topics: List of trending topics
            weights: Custom weights (must sum to 1.0)

        Returns:
            Opportunity score (0-100)

        Raises:
            OpportunityScorerError: If weights don't sum to 1.0
        """
        # Validate weights
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            raise OpportunityScorerError(f"Weights must sum to 1.0 (got {weight_sum})")

        # Temporarily use custom weights
        original_weights = self.weights.copy()
        self.weights = weights

        try:
            score = self.calculate_opportunity_score(keyword_data, content_gaps, trending_topics)
            return score
        finally:
            # Restore original weights
            self.weights = original_weights

    def _calculate_seo_opportunity(self, keyword_data: Dict[str, Any]) -> float:
        """
        Calculate SEO opportunity: (100 - difficulty) * (volume_normalized)

        Args:
            keyword_data: Keyword dict with difficulty and search_volume

        Returns:
            SEO opportunity score (0-100)
        """
        difficulty = keyword_data.get('difficulty', 50)
        search_volume = keyword_data.get('search_volume', 'Unknown')

        # Difficulty inverse (lower difficulty = higher opportunity)
        difficulty_inverse = (100 - difficulty) / 100.0

        # Normalize search volume to 0-1 scale
        volume_normalized = self._normalize_search_volume(search_volume)

        # Combined score
        seo_score = difficulty_inverse * volume_normalized * 100

        return round(seo_score, 1)

    def _calculate_gap_score(self, content_gaps: List[str]) -> float:
        """
        Calculate gap score based on number of content gaps

        Args:
            content_gaps: List of content gaps

        Returns:
            Gap score (0-100)
        """
        num_gaps = len(content_gaps)

        # Score based on gap count (more gaps = more opportunity)
        # 0 gaps = 0, 1-2 gaps = 40, 3-4 gaps = 70, 5+ gaps = 100
        if num_gaps == 0:
            return 0
        elif num_gaps <= 2:
            return 40
        elif num_gaps <= 4:
            return 70
        else:
            return 100

    def _calculate_intent_alignment(self, keyword_data: Dict[str, Any]) -> float:
        """
        Calculate intent alignment score

        Intent priority: Transactional/Commercial (1.0) > Informational (0.6) > Navigational (0.3)

        Args:
            keyword_data: Keyword dict with intent

        Returns:
            Intent alignment score (0-100)
        """
        intent = keyword_data.get('intent', 'Informational')

        intent_scores = {
            'Transactional': 1.0,
            'Commercial': 1.0,
            'Informational': 0.6,
            'Navigational': 0.3
        }

        # Case-insensitive lookup
        intent_normalized = intent.capitalize()
        alignment = intent_scores.get(intent_normalized, 0.6)  # Default to informational

        return alignment * 100

    def _calculate_trending_momentum(
        self,
        keyword_data: Dict[str, Any],
        trending_topics: List[str]
    ) -> float:
        """
        Calculate trending momentum

        Trending up (1.0) > Stable (0.5) > Trending down (0.0)

        Args:
            keyword_data: Keyword dict with keyword text
            trending_topics: List of trending topics

        Returns:
            Trending momentum score (0-100)
        """
        keyword = keyword_data.get('keyword', '')

        # Check if keyword is in trending topics
        is_trending = any(keyword.lower() in topic.lower() for topic in trending_topics)

        if is_trending:
            momentum = 1.0  # Trending up
        else:
            momentum = 0.5  # Stable (default)

        return momentum * 100

    def _normalize_search_volume(self, search_volume: str) -> float:
        """
        Normalize search volume to 0-1 scale

        Args:
            search_volume: Volume range (e.g., "1K-10K/month", "100K+/month")

        Returns:
            Normalized volume (0-1)
        """
        volume_map = {
            '1M+': 1.0,
            '100K-1M': 0.9,
            '100K+': 0.85,
            '10K-100K': 0.75,
            '1K-10K': 0.5,
            '100-1K': 0.25,
            '10-100': 0.1,
            'Unknown': 0.3  # Default
        }

        # Find matching range
        for key, value in volume_map.items():
            if key in search_volume:
                return value

        # Default if no match
        return 0.3

    def explain_opportunity(
        self,
        keyword_data: Dict[str, Any],
        opportunity_score: float,
        content_gaps: List[str],
        trending_topics: List[str]
    ) -> str:
        """
        Generate AI-powered explanation of opportunity score using Gemini 2.5 Flash (FREE)

        Args:
            keyword_data: Keyword dict
            opportunity_score: Calculated opportunity score (0-100)
            content_gaps: List of content gaps
            trending_topics: List of trending topics

        Returns:
            2-3 sentence explanation with recommendations
        """
        try:
            # Initialize Gemini
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return self._fallback_explanation(opportunity_score)

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash-exp")

            # Build prompt
            prompt = f"""Analyze this keyword opportunity and provide a 2-3 sentence recommendation:

Keyword: {keyword_data.get('keyword')}
Opportunity Score: {opportunity_score}/100
Difficulty: {keyword_data.get('difficulty')}/100
Search Volume: {keyword_data.get('search_volume')}
Intent: {keyword_data.get('intent')}
Content Gaps: {', '.join(content_gaps[:3]) if content_gaps else 'None identified'}
Trending: {'Yes' if any(keyword_data.get('keyword', '').lower() in t.lower() for t in trending_topics) else 'No'}

Format your response as:
"This keyword scores X/100. [Best for/Challenging because...]. [Focus on/Recommended tactic...]."

Keep it concise and actionable."""

            response = model.generate_content(prompt)

            return response.text.strip()

        except Exception as e:
            logger.warning("gemini_explanation_failed", error=str(e))
            return self._fallback_explanation(opportunity_score)

    def _fallback_explanation(self, opportunity_score: float) -> str:
        """
        Generate fallback explanation when Gemini API is unavailable

        Args:
            opportunity_score: Opportunity score (0-100)

        Returns:
            Simple explanation text
        """
        if opportunity_score >= 70:
            return f"Score: {opportunity_score}/100. High opportunity keyword. Focus on creating comprehensive content to capture this opportunity."
        elif opportunity_score >= 40:
            return f"Score: {opportunity_score}/100. Medium opportunity keyword. Consider if it aligns with your content strategy and resources."
        else:
            return f"Score: {opportunity_score}/100. Low opportunity keyword. May be too competitive or low-volume for current strategy."
