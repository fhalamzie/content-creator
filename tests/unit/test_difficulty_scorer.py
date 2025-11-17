"""
Unit tests for Difficulty Scorer

Tests:
- Content quality scoring
- Domain authority scoring
- Content length scoring
- Freshness requirement scoring
- Overall difficulty calculation
- Target calculations (word count, H2, images, quality)
- Ranking time estimation
- Recommendations generation
"""

import pytest
from datetime import datetime, timezone
from src.research.difficulty_scorer import (
    DifficultyScorer,
    DifficultyScore,
    Recommendation,
    DIFFICULTY_WEIGHTS
)


class TestDifficultyScorer:
    """Test Difficulty Scorer functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.scorer = DifficultyScorer()

    # === Content Quality Scoring Tests ===

    def test_score_content_quality_low(self):
        """Test content quality scoring for low quality competitors"""
        content_scores = [
            {"quality_score": 60},
            {"quality_score": 65},
            {"quality_score": 68}
        ]

        score, avg = self.scorer._score_content_quality(content_scores)

        assert avg < 70
        assert score == 0.3  # Low quality = easy difficulty

    def test_score_content_quality_medium(self):
        """Test content quality scoring for medium quality competitors"""
        content_scores = [
            {"quality_score": 75},
            {"quality_score": 76},
            {"quality_score": 74}
        ]

        score, avg = self.scorer._score_content_quality(content_scores)

        assert 70 <= avg < 80
        assert 0.3 <= score <= 0.5  # Medium quality

    def test_score_content_quality_high(self):
        """Test content quality scoring for high quality competitors"""
        content_scores = [
            {"quality_score": 85},
            {"quality_score": 83},
            {"quality_score": 87}
        ]

        score, avg = self.scorer._score_content_quality(content_scores)

        assert 80 <= avg < 90
        assert 0.5 <= score <= 0.7  # High quality

    def test_score_content_quality_very_high(self):
        """Test content quality scoring for very high quality competitors"""
        content_scores = [
            {"quality_score": 92},
            {"quality_score": 94},
            {"quality_score": 96}
        ]

        score, avg = self.scorer._score_content_quality(content_scores)

        assert avg >= 90
        assert 0.7 <= score <= 0.9  # Very high quality

    # === Domain Authority Scoring Tests ===

    def test_score_domain_authority_low(self):
        """Test domain authority scoring with few high-authority domains"""
        serp_results = [
            {"domain_authority": "Low"},
            {"domain_authority": "Medium"},
            {"domain_authority": "Low"},
            {"domain_authority": "Low"}
        ]

        score, high_pct = self.scorer._score_domain_authority(serp_results)

        assert high_pct < 20
        assert score == 0.2  # Low DA = easy

    def test_score_domain_authority_medium(self):
        """Test domain authority scoring with medium mix"""
        serp_results = [
            {"domain_authority": "High"},
            {"domain_authority": "Medium-High"},
            {"domain_authority": "High"},
            {"domain_authority": "Low"},
            {"domain_authority": "Low"}
        ]

        score, high_pct = self.scorer._score_domain_authority(serp_results)

        assert 40 <= high_pct < 80  # 3/5 = 60%
        assert 0.4 <= score < 0.8  # Medium-hard

    def test_score_domain_authority_high(self):
        """Test domain authority scoring with mostly high-authority domains"""
        serp_results = [
            {"domain_authority": "High"},
            {"domain_authority": "High"},
            {"domain_authority": "Medium-High"},
            {"domain_authority": "High"},
            {"domain_authority": "High"}
        ]

        score, high_pct = self.scorer._score_domain_authority(serp_results)

        assert high_pct >= 80  # 5/5 = 100%
        assert score >= 0.8  # Very hard

    def test_score_domain_authority_empty(self):
        """Test domain authority scoring with empty results"""
        serp_results = []

        score, high_pct = self.scorer._score_domain_authority(serp_results)

        assert score == 0.5  # Neutral
        assert high_pct == 0.0

    # === Content Length Scoring Tests ===

    def test_score_content_length_short(self):
        """Test content length scoring for short content"""
        content_scores = [
            {"word_count": 800},
            {"word_count": 850},
            {"word_count": 750}
        ]

        score, avg = self.scorer._score_content_length(content_scores)

        assert avg < 1000
        assert score == 0.2  # Short = easy

    def test_score_content_length_medium(self):
        """Test content length scoring for medium content"""
        content_scores = [
            {"word_count": 1500},
            {"word_count": 1600},
            {"word_count": 1400}
        ]

        score, avg = self.scorer._score_content_length(content_scores)

        assert 1000 <= avg < 2000
        assert 0.2 <= score <= 0.4  # Medium

    def test_score_content_length_long(self):
        """Test content length scoring for long content"""
        content_scores = [
            {"word_count": 3500},
            {"word_count": 3800},
            {"word_count": 3200}
        ]

        score, avg = self.scorer._score_content_length(content_scores)

        assert 3000 <= avg < 4000
        assert 0.6 <= score <= 0.8  # Hard

    def test_score_content_length_very_long(self):
        """Test content length scoring for very long content"""
        content_scores = [
            {"word_count": 5000},
            {"word_count": 5500},
            {"word_count": 4800}
        ]

        score, avg = self.scorer._score_content_length(content_scores)

        assert avg >= 4000
        assert 0.8 <= score <= 1.0  # Very hard

    def test_score_content_length_no_data(self):
        """Test content length scoring with no word count data"""
        content_scores = [
            {},
            {},
            {}
        ]

        score, avg = self.scorer._score_content_length(content_scores)

        assert avg == 0
        assert score == 0.5  # Neutral

    # === Freshness Requirement Scoring Tests ===

    def test_score_freshness_very_fresh(self):
        """Test freshness scoring when most content is very fresh"""
        content_scores = [
            {"freshness_score": 1.0},  # < 3 months
            {"freshness_score": 1.0},
            {"freshness_score": 0.9},  # < 6 months
            {"freshness_score": 1.0}
        ]

        score, req = self.scorer._score_freshness_requirement(content_scores)

        # 3/4 = 75% very fresh
        assert score == 0.8
        assert req == "< 3 months"

    def test_score_freshness_fresh(self):
        """Test freshness scoring when most content is fresh"""
        content_scores = [
            {"freshness_score": 0.9},  # < 6 months
            {"freshness_score": 0.9},
            {"freshness_score": 0.8},
            {"freshness_score": 0.9}
        ]

        score, req = self.scorer._score_freshness_requirement(content_scores)

        # 3/4 = 75% >= 0.9
        assert score == 0.8
        assert req == "< 3 months"

    def test_score_freshness_medium(self):
        """Test freshness scoring for medium freshness requirements"""
        content_scores = [
            {"freshness_score": 0.9},
            {"freshness_score": 0.8},
            {"freshness_score": 0.6},
            {"freshness_score": 0.5}
        ]

        score, req = self.scorer._score_freshness_requirement(content_scores)

        # 1/4 = 25% >= 0.9 (only one is 0.9, others are below)
        # < 30% fresh = 0.2 difficulty
        assert score == 0.2
        assert req == "< 24 months"

    def test_score_freshness_old(self):
        """Test freshness scoring when old content is acceptable"""
        content_scores = [
            {"freshness_score": 0.6},
            {"freshness_score": 0.5},
            {"freshness_score": 0.4},
            {"freshness_score": 0.5}
        ]

        score, req = self.scorer._score_freshness_requirement(content_scores)

        # 0/4 = 0% >= 0.9
        assert score == 0.2
        assert req == "< 24 months"

    # === Target Calculations Tests ===

    def test_calculate_target_word_count(self):
        """Test target word count calculation (beat avg by 10%)"""
        content_scores = [
            {"word_count": 2000},
            {"word_count": 2200},
            {"word_count": 2100}
        ]

        target = self.scorer._calculate_target_word_count(content_scores)

        # Avg = 2100, +10% = 2310, rounded to 2300
        assert target == 2300

    def test_calculate_target_word_count_no_data(self):
        """Test target word count with no data"""
        content_scores = [{}]

        target = self.scorer._calculate_target_word_count(content_scores)

        assert target == 2000  # Default

    def test_calculate_target_h2_count(self):
        """Test target H2 count calculation (beat avg)"""
        content_scores = [
            {"h2_count": 5},
            {"h2_count": 6},
            {"h2_count": 5}
        ]

        target = self.scorer._calculate_target_h2_count(content_scores)

        # Avg = 5.33, rounded + 1 = 6
        assert target == 6

    def test_calculate_target_h2_count_no_data(self):
        """Test target H2 count with no data"""
        content_scores = [{}]

        target = self.scorer._calculate_target_h2_count(content_scores)

        assert target == 5  # Default

    def test_calculate_target_image_count(self):
        """Test target image count calculation (beat avg)"""
        content_scores = [
            {"image_count": 3},
            {"image_count": 4},
            {"image_count": 3}
        ]

        target = self.scorer._calculate_target_image_count(content_scores)

        # Avg = 3.33, rounded + 1 = 4
        assert target == 4

    def test_calculate_target_image_count_no_data(self):
        """Test target image count with no data"""
        content_scores = [{}]

        target = self.scorer._calculate_target_image_count(content_scores)

        assert target == 3  # Default

    def test_calculate_target_quality(self):
        """Test target quality calculation (beat top 3 avg by 5)"""
        content_scores = [
            {"quality_score": 90},
            {"quality_score": 85},
            {"quality_score": 88},
            {"quality_score": 75},
            {"quality_score": 80}
        ]

        target = self.scorer._calculate_target_quality(content_scores)

        # Top 3: 90, 88, 85 → avg = 87.67, +5 = 92.67
        assert 92.0 <= target < 93.0

    def test_calculate_target_quality_max_capped(self):
        """Test target quality is capped at 100"""
        content_scores = [
            {"quality_score": 96},
            {"quality_score": 97},
            {"quality_score": 98}
        ]

        target = self.scorer._calculate_target_quality(content_scores)

        assert target == 100.0  # Capped

    # === Ranking Time Estimation Tests ===

    def test_estimate_ranking_time_easy(self):
        """Test ranking time for easy topics"""
        time = self.scorer._estimate_ranking_time(difficulty_score=30, avg_quality=70)
        assert time == "2-4 months"

    def test_estimate_ranking_time_medium(self):
        """Test ranking time for medium topics"""
        time = self.scorer._estimate_ranking_time(difficulty_score=55, avg_quality=75)
        assert time == "4-6 months"

    def test_estimate_ranking_time_hard(self):
        """Test ranking time for hard topics"""
        time = self.scorer._estimate_ranking_time(difficulty_score=70, avg_quality=85)
        assert time == "6-9 months"

    def test_estimate_ranking_time_very_hard(self):
        """Test ranking time for very hard topics"""
        time = self.scorer._estimate_ranking_time(difficulty_score=80, avg_quality=90)
        assert time == "9-12 months"

    def test_estimate_ranking_time_extreme(self):
        """Test ranking time for extreme difficulty"""
        time = self.scorer._estimate_ranking_time(difficulty_score=90, avg_quality=95)
        assert time == "12-18 months"

    # === Overall Difficulty Calculation Tests ===

    def test_calculate_difficulty_easy(self):
        """Test difficulty calculation for easy topic"""
        serp_results = [
            {"domain_authority": "Low"} for _ in range(10)
        ]

        content_scores = [
            {
                "quality_score": 65,
                "word_count": 1000,
                "h2_count": 3,
                "image_count": 2,
                "freshness_score": 0.5
            }
            for _ in range(10)
        ]

        difficulty = self.scorer.calculate_difficulty(
            topic_id="test-easy",
            serp_results=serp_results,
            content_scores=content_scores
        )

        assert difficulty.difficulty_score < 40  # Easy
        assert difficulty.topic_id == "test-easy"
        assert difficulty.estimated_ranking_time == "2-4 months"

    def test_calculate_difficulty_medium(self):
        """Test difficulty calculation for medium topic"""
        serp_results = [
            {"domain_authority": "High" if i < 5 else "Low"}
            for i in range(10)
        ]

        content_scores = [
            {
                "quality_score": 78,
                "word_count": 2200,
                "h2_count": 5,
                "image_count": 3,
                "freshness_score": 0.9
            }
            for _ in range(10)
        ]

        difficulty = self.scorer.calculate_difficulty(
            topic_id="test-medium",
            serp_results=serp_results,
            content_scores=content_scores
        )

        assert 40 <= difficulty.difficulty_score < 70  # Medium
        assert difficulty.estimated_ranking_time in ["4-6 months", "6-9 months"]

    def test_calculate_difficulty_hard(self):
        """Test difficulty calculation for hard topic"""
        serp_results = [
            {"domain_authority": "High"} for _ in range(8)
        ] + [
            {"domain_authority": "Low"} for _ in range(2)
        ]

        content_scores = [
            {
                "quality_score": 88,
                "word_count": 3200,
                "h2_count": 8,
                "image_count": 6,
                "freshness_score": 1.0
            }
            for _ in range(10)
        ]

        difficulty = self.scorer.calculate_difficulty(
            topic_id="test-hard",
            serp_results=serp_results,
            content_scores=content_scores
        )

        assert difficulty.difficulty_score >= 65  # Hard
        assert difficulty.estimated_ranking_time in ["6-9 months", "9-12 months", "12-18 months"]

    def test_calculate_difficulty_validates_inputs(self):
        """Test that calculate_difficulty validates inputs"""
        with pytest.raises(ValueError, match="SERP results required"):
            self.scorer.calculate_difficulty("test", [], [{"quality_score": 80}])

        with pytest.raises(ValueError, match="Content scores required"):
            self.scorer.calculate_difficulty("test", [{"domain": "test"}], [])

    # === Recommendations Generation Tests ===

    def test_generate_recommendations_easy_topic(self):
        """Test recommendations for easy topic"""
        difficulty_score = DifficultyScore(
            topic_id="test-easy",
            difficulty_score=35.0,
            content_quality_score=0.3,
            domain_authority_score=0.2,
            content_length_score=0.3,
            freshness_score=0.2,
            target_word_count=1500,
            target_h2_count=4,
            target_image_count=3,
            target_quality_score=75.0,
            avg_competitor_quality=70.0,
            avg_competitor_word_count=1400,
            high_authority_percentage=20.0,
            freshness_requirement="< 12 months",
            estimated_ranking_time="2-4 months",
            analyzed_at=datetime.utcnow()
        )

        recommendations = self.scorer.generate_recommendations(difficulty_score)

        assert len(recommendations) >= 4
        # Should have: overall, content length, structure, quality, timing
        assert recommendations[0].category == "quality"  # Overall assessment first
        assert recommendations[0].priority == "medium"  # Easy = medium priority
        assert "Moderate difficulty" in recommendations[0].message

    def test_generate_recommendations_hard_topic(self):
        """Test recommendations for hard topic"""
        difficulty_score = DifficultyScore(
            topic_id="test-hard",
            difficulty_score=78.0,
            content_quality_score=0.7,
            domain_authority_score=0.8,
            content_length_score=0.7,
            freshness_score=0.6,
            target_word_count=3500,
            target_h2_count=8,
            target_image_count=7,
            target_quality_score=93.0,
            avg_competitor_quality=88.0,
            avg_competitor_word_count=3200,
            high_authority_percentage=75.0,
            freshness_requirement="< 3 months",
            estimated_ranking_time="9-12 months",
            analyzed_at=datetime.utcnow()
        )

        recommendations = self.scorer.generate_recommendations(difficulty_score)

        assert len(recommendations) >= 6
        # Should have critical warnings (difficulty > 75 = very high)
        assert recommendations[0].priority == "critical"  # Very high difficulty (>75)
        assert "Very high difficulty" in recommendations[0].message
        # Should warn about high DA
        critical_recs = [r for r in recommendations if r.priority == "critical"]
        assert len(critical_recs) >= 3  # Very high difficulty + long content + high DA warnings

    def test_generate_recommendations_very_hard_topic(self):
        """Test recommendations for very hard topic"""
        difficulty_score = DifficultyScore(
            topic_id="test-very-hard",
            difficulty_score=85.0,
            content_quality_score=0.85,
            domain_authority_score=0.9,
            content_length_score=0.8,
            freshness_score=0.8,
            target_word_count=4000,
            target_h2_count=10,
            target_image_count=8,
            target_quality_score=98.0,
            avg_competitor_quality=93.0,
            avg_competitor_word_count=3800,
            high_authority_percentage=85.0,
            freshness_requirement="< 3 months",
            estimated_ranking_time="12-18 months",
            analyzed_at=datetime.utcnow()
        )

        recommendations = self.scorer.generate_recommendations(difficulty_score)

        # Should have "Very high difficulty" as first recommendation
        assert recommendations[0].priority == "critical"
        assert "Very high difficulty" in recommendations[0].message
        assert "exceptional content" in recommendations[0].message.lower()

    # === Score to Dict Conversion Test ===

    def test_score_to_dict(self):
        """Test converting DifficultyScore to dict"""
        now = datetime.utcnow()

        difficulty_score = DifficultyScore(
            topic_id="test-topic",
            difficulty_score=65.5,
            content_quality_score=0.6,
            domain_authority_score=0.5,
            content_length_score=0.7,
            freshness_score=0.4,
            target_word_count=2500,
            target_h2_count=6,
            target_image_count=5,
            target_quality_score=85.0,
            avg_competitor_quality=80.0,
            avg_competitor_word_count=2300,
            high_authority_percentage=50.0,
            freshness_requirement="< 6 months",
            estimated_ranking_time="6-9 months",
            analyzed_at=now
        )

        score_dict = self.scorer.score_to_dict(difficulty_score)

        assert score_dict["topic_id"] == "test-topic"
        assert score_dict["difficulty_score"] == 65.5
        assert score_dict["content_quality_score"] == 0.6
        assert score_dict["target_word_count"] == 2500
        assert score_dict["target_h2_count"] == 6
        assert score_dict["analyzed_at"] == now.isoformat()

    # === Weights Validation Test ===

    def test_weights_sum_to_one(self):
        """Test that all difficulty weights sum to 1.0"""
        total = sum(DIFFICULTY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001  # Allow small floating point error
