"""
Unit tests for Content Scorer

Tests:
- Word count scoring
- Readability scoring
- Keyword density
- Structure analysis
- Entity extraction
- Freshness scoring
- Overall score calculation
"""

import pytest
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from src.research.content_scorer import ContentScorer, WEIGHTS


class TestContentScorer:
    """Test Content Scorer functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.scorer = ContentScorer()

    # === Word Count Scoring Tests ===

    def test_score_word_count_very_low(self):
        """Test word count scoring for very short content"""
        score = self.scorer._score_word_count(300)
        assert score == 0.3  # Below 500 words

    def test_score_word_count_low(self):
        """Test word count scoring for short content"""
        score = self.scorer._score_word_count(1000)
        # 500-1500 range: linear 0.3 to 0.9
        # 1000 is halfway: 0.3 + (500/1000)*0.6 = 0.6
        assert 0.5 <= score <= 0.7

    def test_score_word_count_optimal(self):
        """Test word count scoring for optimal range"""
        score = self.scorer._score_word_count(2000)
        assert score == 1.0  # 1500-3000 is optimal

    def test_score_word_count_high(self):
        """Test word count scoring for long content"""
        score = self.scorer._score_word_count(4000)
        # 3000-5000 range: diminishing returns
        assert 0.85 <= score < 1.0

    def test_score_word_count_very_high(self):
        """Test word count scoring for very long content"""
        score = self.scorer._score_word_count(6000)
        assert score == 0.8  # Above 5000

    # === Readability Scoring Tests ===

    def test_score_readability_very_difficult(self):
        """Test readability scoring for very difficult text"""
        score = self.scorer._score_readability(20.0)
        assert score == 0.4  # Below 30

    def test_score_readability_difficult(self):
        """Test readability scoring for difficult text"""
        score = self.scorer._score_readability(45.0)
        # 30-50 range: 0.6 to 0.9
        assert 0.7 <= score <= 0.9

    def test_score_readability_optimal(self):
        """Test readability scoring for optimal range"""
        score = self.scorer._score_readability(70.0)
        assert score == 1.0  # 60-80 is optimal

    def test_score_readability_easy(self):
        """Test readability scoring for easy text"""
        score = self.scorer._score_readability(85.0)
        # 80-90 range: 1.0 to 0.8
        assert 0.8 <= score < 1.0

    def test_score_readability_very_easy(self):
        """Test readability scoring for very easy text"""
        score = self.scorer._score_readability(95.0)
        assert score == 0.7  # Above 90

    # === Keyword Density Tests ===

    def test_calculate_keyword_density_basic(self):
        """Test keyword density calculation"""
        text = "PropTech is the future. PropTech innovations are transforming real estate. PropTech solutions."
        # 3 occurrences of "PropTech" in 12 words = 25%
        density = self.scorer._calculate_keyword_density(text, "PropTech")
        assert density == 25.0

    def test_calculate_keyword_density_case_insensitive(self):
        """Test keyword density is case-insensitive"""
        text = "proptech is PROPTECH and PropTech"
        # 3 occurrences in 5 words = 60%
        density = self.scorer._calculate_keyword_density(text, "PropTech")
        assert density == 60.0

    def test_score_keyword_density_under_optimized(self):
        """Test keyword density scoring for under-optimized content"""
        score = self.scorer._score_keyword_density(0.3)
        assert score == 0.4  # Below 0.5%

    def test_score_keyword_density_optimal(self):
        """Test keyword density scoring for optimal range"""
        score = self.scorer._score_keyword_density(2.0)
        assert score == 1.0  # 1.5-2.5% is optimal

    def test_score_keyword_density_high(self):
        """Test keyword density scoring for high density"""
        score = self.scorer._score_keyword_density(3.5)
        # 2.5-4.0 range: diminishing returns
        assert 0.65 <= score < 1.0

    def test_score_keyword_density_stuffing(self):
        """Test keyword density scoring for keyword stuffing"""
        score = self.scorer._score_keyword_density(5.0)
        assert score == 0.5  # Above 4%

    # === Structure Analysis Tests ===

    def test_analyze_structure_basic(self):
        """Test basic structure analysis"""
        html = """
        <html>
            <body>
                <h1>Title</h1>
                <h2>Section 1</h2>
                <p>Content</p>
                <h2>Section 2</h2>
                <ul><li>Item</li></ul>
                <img src="test.jpg">
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'lxml')
        h1, h2, h3, lists, images = self.scorer._analyze_structure(soup)

        assert h1 == 1
        assert h2 == 2
        assert h3 == 0
        assert lists == 1
        assert images == 1

    def test_score_structure_optimal(self):
        """Test structure scoring for well-structured content"""
        # 2000 words, 1 H1, 5 H2s, 2 H3s, 3 lists, 4 images
        score = self.scorer._score_structure(2000, 1, 5, 2, 3, 4)
        # Should score well:
        # - 1 H1: +0.25
        # - 5 H2s for 2000 words (expected ~5): +0.25
        # - 2 H3s: +0.15
        # - 3 lists: +0.20
        # - 4 images for 2000 words (expected ~4): +0.15
        # Total: 1.0
        assert score == 1.0

    def test_score_structure_no_h1(self):
        """Test structure scoring for content missing H1"""
        score = self.scorer._score_structure(1000, 0, 3, 1, 2, 2)
        # Missing H1 is bad (0 instead of 0.25)
        assert score < 1.0

    def test_score_structure_multiple_h1(self):
        """Test structure scoring for content with multiple H1s"""
        score = self.scorer._score_structure(1000, 3, 3, 1, 2, 2)
        # Multiple H1s is not ideal (0.1 instead of 0.25)
        assert score < 1.0

    # === Entity Extraction Tests ===

    def test_extract_entities_basic(self):
        """Test basic entity extraction"""
        text = "John Smith works at Microsoft in Seattle. He met Sarah Johnson at Amazon."
        entities = self.scorer._extract_entities(text)

        # Should find: John, Smith, Microsoft, Seattle, Sarah, Johnson, Amazon
        # Filtering: He (pronoun)
        assert len(entities) >= 5  # At least proper nouns

    def test_extract_entities_filters_common_words(self):
        """Test entity extraction filters common words"""
        text = "The company is in London. This is great."
        entities = self.scorer._extract_entities(text)

        # Should find: London
        # Should NOT find: The, This
        assert "London" in entities or "company" in entities
        assert "The" not in entities
        assert "This" not in entities

    def test_score_entity_coverage_low(self):
        """Test entity scoring for low coverage"""
        score = self.scorer._score_entity_coverage(5, 1000)
        # 5 entities in 1000 words = 0.5 per 100 words
        assert score == 0.4  # Below 0.5 per 100

    def test_score_entity_coverage_optimal(self):
        """Test entity scoring for optimal coverage"""
        score = self.scorer._score_entity_coverage(15, 1000)
        # 15 entities in 1000 words = 1.5 per 100 words
        assert score == 1.0  # 1.0-2.0 per 100 is optimal

    def test_score_entity_coverage_high(self):
        """Test entity scoring for high coverage"""
        score = self.scorer._score_entity_coverage(50, 1000)
        # 50 entities in 1000 words = 5.0 per 100 words
        assert score == 0.7  # Above 4 per 100

    # === Freshness Scoring Tests ===

    def test_score_freshness_recent(self):
        """Test freshness scoring for recent content"""
        # 1 month ago
        date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        score = self.scorer._score_freshness(date)
        assert score == 1.0  # <3 months

    def test_score_freshness_medium(self):
        """Test freshness scoring for medium-age content"""
        # 5 months ago
        date = (datetime.now(timezone.utc) - timedelta(days=150)).isoformat()
        score = self.scorer._score_freshness(date)
        assert score == 0.9  # 3-6 months

    def test_score_freshness_old(self):
        """Test freshness scoring for old content"""
        # 2 years ago
        date = (datetime.now(timezone.utc) - timedelta(days=730)).isoformat()
        score = self.scorer._score_freshness(date)
        assert score == 0.4  # >2 years

    def test_score_freshness_unknown(self):
        """Test freshness scoring for unknown date"""
        score = self.scorer._score_freshness(None)
        assert score == 0.5  # Neutral

    def test_extract_published_date_meta_tag(self):
        """Test published date extraction from meta tag"""
        html = '<meta property="article:published_time" content="2025-01-15T10:00:00Z">'
        soup = BeautifulSoup(html, 'lxml')
        date = self.scorer._extract_published_date(soup)
        assert date == "2025-01-15T10:00:00Z"

    def test_extract_published_date_time_tag(self):
        """Test published date extraction from time tag"""
        html = '<time itemprop="datePublished" datetime="2025-01-15">January 15, 2025</time>'
        soup = BeautifulSoup(html, 'lxml')
        date = self.scorer._extract_published_date(soup)
        assert date == "2025-01-15"

    # === Text Extraction Tests ===

    def test_extract_text_removes_scripts(self):
        """Test text extraction removes scripts"""
        html = "<html><script>alert('hi')</script><p>Content</p></html>"
        soup = BeautifulSoup(html, 'lxml')
        text = self.scorer._extract_text(soup)
        assert "alert" not in text
        assert "Content" in text

    def test_extract_text_removes_nav(self):
        """Test text extraction removes navigation"""
        html = "<html><nav>Menu</nav><p>Content</p></html>"
        soup = BeautifulSoup(html, 'lxml')
        text = self.scorer._extract_text(soup)
        assert "Menu" not in text
        assert "Content" in text

    def test_count_words_basic(self):
        """Test word counting"""
        text = "This is a test sentence with seven words."
        count = self.scorer._count_words(text)
        assert count == 8

    # === Score to Dict Conversion Tests ===

    def test_score_to_dict(self):
        """Test converting ContentScore to dict"""
        from src.research.content_scorer import ContentScore

        score = ContentScore(
            url="https://example.com",
            quality_score=85.5,
            word_count_score=0.9,
            readability_score=0.8,
            keyword_score=0.85,
            structure_score=0.9,
            entity_score=0.75,
            freshness_score=1.0,
            word_count=2500,
            flesch_reading_ease=65.0,
            keyword_density=2.5,
            h1_count=1,
            h2_count=5,
            h3_count=10,
            list_count=3,
            image_count=4,
            entity_count=15,
            published_date="2025-01-15T10:00:00",
            content_hash="abc123"
        )

        score_dict = self.scorer.score_to_dict(score)

        assert score_dict["word_count_score"] == 0.9
        assert score_dict["readability_score"] == 0.8
        assert score_dict["keyword_score"] == 0.85
        assert score_dict["structure_score"] == 0.9
        assert score_dict["entity_score"] == 0.75
        assert score_dict["freshness_score"] == 1.0
        assert score_dict["word_count"] == 2500
        assert score_dict["h1_count"] == 1

    # === Weights Validation Test ===

    def test_weights_sum_to_one(self):
        """Test that all weights sum to 1.0"""
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001  # Allow small floating point error
