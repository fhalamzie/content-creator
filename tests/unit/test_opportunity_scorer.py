"""
Tests for OpportunityScorer class

Tests 4-algorithm opportunity scoring for keywords with AI recommendations.
"""

import pytest
from unittest.mock import Mock, patch
from src.scoring.opportunity_scorer import OpportunityScorer, OpportunityScorerError


@pytest.fixture
def high_opportunity_keyword():
    """High opportunity keyword (low difficulty, high volume)"""
    return {
        'keyword': 'PropTech Tipps für Anfänger',
        'search_volume': '10K-100K/month',
        'competition': 'Low',
        'difficulty': 25,
        'intent': 'Informational'
    }


@pytest.fixture
def medium_opportunity_keyword():
    """Medium opportunity keyword"""
    return {
        'keyword': 'Immobilien Software',
        'search_volume': '1K-10K/month',
        'competition': 'Medium',
        'difficulty': 55,
        'intent': 'Commercial'
    }


@pytest.fixture
def low_opportunity_keyword():
    """Low opportunity keyword (high difficulty, low volume)"""
    return {
        'keyword': 'PropTech',
        'search_volume': '100-1K/month',
        'competition': 'High',
        'difficulty': 85,
        'intent': 'Navigational'
    }


class TestOpportunityScorerInitialization:
    """Test OpportunityScorer initialization"""

    def test_init_with_default_weights(self):
        """Test initialization with default weights"""
        scorer = OpportunityScorer()

        # Default weights should sum to 1.0
        assert scorer.weights['seo_opportunity'] == 0.30
        assert scorer.weights['gap_score'] == 0.25
        assert scorer.weights['intent_alignment'] == 0.25
        assert scorer.weights['trending_momentum'] == 0.20

        total_weight = sum(scorer.weights.values())
        assert abs(total_weight - 1.0) < 0.01  # Allow small float error

    def test_init_with_custom_weights(self):
        """Test initialization with custom weights"""
        custom_weights = {
            'seo_opportunity': 0.5,
            'gap_score': 0.2,
            'intent_alignment': 0.2,
            'trending_momentum': 0.1
        }

        scorer = OpportunityScorer(weights=custom_weights)

        assert scorer.weights == custom_weights

    def test_init_with_invalid_weights_raises_error(self):
        """Test initialization with weights that don't sum to 1.0"""
        invalid_weights = {
            'seo_opportunity': 0.5,
            'gap_score': 0.5,
            'intent_alignment': 0.5,
            'trending_momentum': 0.5
        }  # Sum = 2.0

        with pytest.raises(OpportunityScorerError, match="Weights must sum to 1.0"):
            OpportunityScorer(weights=invalid_weights)


class TestSEOOpportunityScore:
    """Test _calculate_seo_opportunity method"""

    def test_seo_opportunity_high_volume_low_difficulty(self, high_opportunity_keyword):
        """Test SEO opportunity for easy keyword with high volume"""
        scorer = OpportunityScorer()
        score = scorer._calculate_seo_opportunity(high_opportunity_keyword)

        # Low difficulty (25) + High volume (10K-100K) = Good opportunity
        # Formula: (100-25)/100 * 0.75 * 100 = 56.25
        assert score >= 50  # Should be good opportunity

    def test_seo_opportunity_low_volume_high_difficulty(self, low_opportunity_keyword):
        """Test SEO opportunity for difficult keyword with low volume"""
        scorer = OpportunityScorer()
        score = scorer._calculate_seo_opportunity(low_opportunity_keyword)

        # High difficulty (85) + Low volume (100-1K) = Low opportunity
        assert score < 30  # Should be low opportunity

    def test_seo_opportunity_formula(self):
        """Test SEO opportunity calculation formula"""
        scorer = OpportunityScorer()

        keyword = {
            'difficulty': 40,  # (100 - 40) = 60
            'search_volume': '10K-100K/month'  # Normalized to ~0.75
        }

        score = scorer._calculate_seo_opportunity(keyword)

        # Score should be in range (difficulty inverse * volume normalized)
        assert 0 <= score <= 100


class TestGapScore:
    """Test _calculate_gap_score method"""

    def test_gap_score_with_high_gaps(self):
        """Test gap score with many content gaps"""
        scorer = OpportunityScorer()

        content_gaps = [
            "No beginner guides",
            "Missing comparison content",
            "No case studies",
            "Weak local SEO",
            "No video content"
        ]

        score = scorer._calculate_gap_score(content_gaps)

        # 5 gaps = high opportunity
        assert score >= 70

    def test_gap_score_with_low_gaps(self):
        """Test gap score with few content gaps"""
        scorer = OpportunityScorer()

        content_gaps = ["Minor technical details missing"]

        score = scorer._calculate_gap_score(content_gaps)

        # 1 gap = lower opportunity
        assert score < 50

    def test_gap_score_with_no_gaps(self):
        """Test gap score with no content gaps"""
        scorer = OpportunityScorer()

        content_gaps = []

        score = scorer._calculate_gap_score(content_gaps)

        # 0 gaps = no opportunity from gaps
        assert score == 0


class TestIntentAlignment:
    """Test _calculate_intent_alignment method"""

    def test_intent_alignment_transactional(self):
        """Test intent alignment for transactional keywords (highest value)"""
        scorer = OpportunityScorer()

        keyword = {'intent': 'Transactional'}

        score = scorer._calculate_intent_alignment(keyword)

        assert score == 100  # Transactional = 1.0 * 100

    def test_intent_alignment_commercial(self):
        """Test intent alignment for commercial keywords"""
        scorer = OpportunityScorer()

        keyword = {'intent': 'Commercial'}

        score = scorer._calculate_intent_alignment(keyword)

        assert score == 100  # Commercial = 1.0 * 100

    def test_intent_alignment_informational(self):
        """Test intent alignment for informational keywords"""
        scorer = OpportunityScorer()

        keyword = {'intent': 'Informational'}

        score = scorer._calculate_intent_alignment(keyword)

        assert score == 60  # Informational = 0.6 * 100

    def test_intent_alignment_navigational(self):
        """Test intent alignment for navigational keywords (lowest value)"""
        scorer = OpportunityScorer()

        keyword = {'intent': 'Navigational'}

        score = scorer._calculate_intent_alignment(keyword)

        assert score == 30  # Navigational = 0.3 * 100


class TestTrendingMomentum:
    """Test _calculate_trending_momentum method"""

    def test_trending_momentum_up(self):
        """Test trending momentum for trending up keywords"""
        scorer = OpportunityScorer()

        keyword = {'keyword': 'AI PropTech'}
        trending_topics = ['AI PropTech', 'Smart Buildings', 'IoT Real Estate']

        score = scorer._calculate_trending_momentum(keyword, trending_topics)

        assert score == 100  # Trending up = 1.0 * 100

    def test_trending_momentum_not_trending(self):
        """Test trending momentum for stable keywords"""
        scorer = OpportunityScorer()

        keyword = {'keyword': 'Real Estate'}
        trending_topics = ['AI PropTech', 'Smart Buildings']

        score = scorer._calculate_trending_momentum(keyword, trending_topics)

        assert score == 50  # Stable = 0.5 * 100

    def test_trending_momentum_no_trending_data(self):
        """Test trending momentum with no trending data"""
        scorer = OpportunityScorer()

        keyword = {'keyword': 'PropTech'}
        trending_topics = []

        score = scorer._calculate_trending_momentum(keyword, trending_topics)

        assert score == 50  # Default to stable


class TestCalculateOpportunityScore:
    """Test calculate_opportunity_score method (weighted combination)"""

    def test_calculate_opportunity_score_high(self, high_opportunity_keyword):
        """Test overall score for high opportunity keyword"""
        scorer = OpportunityScorer()

        content_gaps = ["No beginner content", "Missing visuals", "Weak local SEO"]
        trending_topics = ['PropTech Tipps für Anfänger']

        score = scorer.calculate_opportunity_score(
            keyword_data=high_opportunity_keyword,
            content_gaps=content_gaps,
            trending_topics=trending_topics
        )

        # Should be high opportunity (low difficulty, high volume, trending, gaps)
        assert score >= 60
        assert score <= 100

    def test_calculate_opportunity_score_low(self, low_opportunity_keyword):
        """Test overall score for low opportunity keyword"""
        scorer = OpportunityScorer()

        content_gaps = []  # No gaps
        trending_topics = []  # Not trending

        score = scorer.calculate_opportunity_score(
            keyword_data=low_opportunity_keyword,
            content_gaps=content_gaps,
            trending_topics=trending_topics
        )

        # Should be low opportunity (high difficulty, low volume, not trending, no gaps)
        assert score < 40

    def test_calculate_opportunity_score_returns_correct_range(self):
        """Test that scores are always in 0-100 range"""
        scorer = OpportunityScorer()

        keywords = [
            {'keyword': 'Test 1', 'difficulty': 10, 'search_volume': '1M+/month', 'intent': 'Transactional'},
            {'keyword': 'Test 2', 'difficulty': 90, 'search_volume': '10-100/month', 'intent': 'Navigational'},
            {'keyword': 'Test 3', 'difficulty': 50, 'search_volume': '1K-10K/month', 'intent': 'Informational'}
        ]

        for kw in keywords:
            score = scorer.calculate_opportunity_score(kw, [], [])
            assert 0 <= score <= 100


class TestExplainOpportunity:
    """Test explain_opportunity method (AI recommendation)"""

    @patch('src.scoring.opportunity_scorer.genai.GenerativeModel')
    def test_explain_opportunity_returns_recommendation(self, mock_gemini, high_opportunity_keyword):
        """Test AI explanation for high opportunity keyword"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "This keyword scores 75/100. Best for beginner-focused content. Focus on creating comprehensive guides with visuals."
        mock_model.generate_content.return_value = mock_response
        mock_gemini.return_value = mock_model

        scorer = OpportunityScorer()

        explanation = scorer.explain_opportunity(
            keyword_data=high_opportunity_keyword,
            opportunity_score=75,
            content_gaps=["No beginner content"],
            trending_topics=['PropTech Tipps']
        )

        # Should return explanation from Gemini
        assert "75/100" in explanation
        assert len(explanation) > 20  # Should be a meaningful explanation

    @patch('src.scoring.opportunity_scorer.genai.GenerativeModel')
    def test_explain_opportunity_handles_api_error(self, mock_gemini, high_opportunity_keyword):
        """Test AI explanation handles Gemini API errors"""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API error")
        mock_gemini.return_value = mock_model

        scorer = OpportunityScorer()

        explanation = scorer.explain_opportunity(
            keyword_data=high_opportunity_keyword,
            opportunity_score=75,
            content_gaps=[],
            trending_topics=[]
        )

        # Should return fallback explanation
        assert "Score: 75/100" in explanation
        assert "opportunity" in explanation.lower()


class TestCalculateCustomScore:
    """Test calculate_custom_score method"""

    def test_calculate_custom_score_with_custom_weights(self, medium_opportunity_keyword):
        """Test custom score with user-defined weights"""
        scorer = OpportunityScorer()

        custom_weights = {
            'seo_opportunity': 0.8,  # Prioritize SEO
            'gap_score': 0.1,
            'intent_alignment': 0.05,
            'trending_momentum': 0.05
        }

        score = scorer.calculate_custom_score(
            keyword_data=medium_opportunity_keyword,
            content_gaps=[],
            trending_topics=[],
            weights=custom_weights
        )

        # Should use custom weights
        assert 0 <= score <= 100

    def test_calculate_custom_score_validates_weights(self, medium_opportunity_keyword):
        """Test custom score validates weight sum"""
        scorer = OpportunityScorer()

        invalid_weights = {
            'seo_opportunity': 0.5,
            'gap_score': 0.5,
            'intent_alignment': 0.5,
            'trending_momentum': 0.5
        }  # Sum = 2.0

        with pytest.raises(OpportunityScorerError, match="Weights must sum to 1.0"):
            scorer.calculate_custom_score(
                keyword_data=medium_opportunity_keyword,
                content_gaps=[],
                trending_topics=[],
                weights=invalid_weights
            )
