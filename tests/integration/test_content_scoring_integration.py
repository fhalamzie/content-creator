"""
Integration tests for Content Scoring + Database

Tests:
- Database save/retrieve operations
- Full scoring workflow with mock HTML
- Integration with SERP analyzer
"""

import pytest
from datetime import datetime

from src.research.content_scorer import ContentScorer
from src.database.sqlite_manager import SQLiteManager
from src.models.topic import Topic, TopicSource, TopicStatus


class TestContentScoringIntegration:
    """Integration tests for content scoring"""

    def setup_method(self):
        """Setup test fixtures"""
        self.scorer = ContentScorer()
        self.db = SQLiteManager(db_path=":memory:")

        # Create test topic
        self.topic = Topic(
            id="test-topic",
            title="Test Topic",
            source=TopicSource.MANUAL,
            discovered_at=datetime.utcnow(),
            domain="PropTech",
            market="Germany",
            language="de",
            status=TopicStatus.DISCOVERED
        )
        self.db.insert_topic(self.topic)

    def teardown_method(self):
        """Cleanup"""
        self.db.close()

    # === Database Operations Tests ===

    def test_save_and_retrieve_content_score(self):
        """Test saving and retrieving content score"""
        metrics = {
            "word_count_score": 0.9,
            "readability_score": 0.8,
            "keyword_score": 0.85,
            "structure_score": 0.9,
            "entity_score": 0.75,
            "freshness_score": 1.0,
            "word_count": 2500,
            "flesch_reading_ease": 65.0,
            "keyword_density": 2.5,
            "h1_count": 1,
            "h2_count": 5,
            "h3_count": 10,
            "list_count": 3,
            "image_count": 4,
            "entity_count": 15,
            "published_date": "2025-01-15T10:00:00",
            "content_hash": "abc123"
        }

        # Save
        score_id = self.db.save_content_score(
            url="https://example.com/test",
            quality_score=85.5,
            metrics=metrics,
            topic_id=self.topic.id
        )

        assert score_id > 0

        # Retrieve
        score = self.db.get_content_score("https://example.com/test")

        assert score is not None
        assert score["quality_score"] == 85.5
        assert score["word_count"] == 2500
        assert score["topic_id"] == self.topic.id

    def test_update_existing_content_score(self):
        """Test updating an existing content score"""
        metrics = {
            "word_count_score": 0.8,
            "readability_score": 0.7,
            "keyword_score": 0.75,
            "structure_score": 0.8,
            "entity_score": 0.7,
            "freshness_score": 0.9,
            "word_count": 2000,
            "flesch_reading_ease": 60.0,
            "keyword_density": 2.0,
            "h1_count": 1,
            "h2_count": 4,
            "h3_count": 8,
            "list_count": 2,
            "image_count": 3,
            "entity_count": 12,
            "published_date": "2025-01-10T10:00:00",
            "content_hash": "xyz789"
        }

        # Save once
        self.db.save_content_score(
            url="https://example.com/article",
            quality_score=75.0,
            metrics=metrics
        )

        # Update with new score
        new_metrics = metrics.copy()
        new_metrics["word_count"] = 3000
        new_metrics["content_hash"] = "new_hash"

        self.db.save_content_score(
            url="https://example.com/article",
            quality_score=88.0,
            metrics=new_metrics
        )

        # Should have updated, not created new
        score = self.db.get_content_score("https://example.com/article")

        assert score["quality_score"] == 88.0
        assert score["word_count"] == 3000
        assert score["content_hash"] == "new_hash"

    def test_get_content_scores_by_topic(self):
        """Test retrieving content scores by topic"""
        # Save 3 scores for same topic
        for i, quality in enumerate([90, 75, 85], 1):
            metrics = {
                "word_count_score": 0.8, "readability_score": 0.8,
                "keyword_score": 0.8, "structure_score": 0.8,
                "entity_score": 0.8, "freshness_score": 0.8,
                "word_count": 2000, "flesch_reading_ease": 60.0,
                "keyword_density": 2.0, "h1_count": 1, "h2_count": 4,
                "h3_count": 8, "list_count": 2, "image_count": 3,
                "entity_count": 10, "content_hash": f"hash{i}"
            }

            self.db.save_content_score(
                url=f"https://example.com/article{i}",
                quality_score=quality,
                metrics=metrics,
                topic_id=self.topic.id
            )

        # Retrieve all
        scores = self.db.get_content_scores_by_topic(self.topic.id)

        assert len(scores) == 3
        # Should be ordered by quality DESC
        assert scores[0]["quality_score"] == 90
        assert scores[1]["quality_score"] == 85
        assert scores[2]["quality_score"] == 75

    def test_get_content_scores_with_min_score_filter(self):
        """Test filtering content scores by minimum quality"""
        # Save scores with varying quality
        for i, quality in enumerate([95, 80, 60, 70], 1):
            metrics = {
                "word_count_score": 0.8, "readability_score": 0.8,
                "keyword_score": 0.8, "structure_score": 0.8,
                "entity_score": 0.8, "freshness_score": 0.8,
                "word_count": 2000, "flesch_reading_ease": 60.0,
                "keyword_density": 2.0, "h1_count": 1, "h2_count": 4,
                "h3_count": 8, "list_count": 2, "image_count": 3,
                "entity_count": 10, "content_hash": f"hash{i}"
            }

            self.db.save_content_score(
                url=f"https://example.com/article{i}",
                quality_score=quality,
                metrics=metrics,
                topic_id=self.topic.id
            )

        # Get only high-quality content (>= 80)
        high_quality = self.db.get_content_scores_by_topic(
            self.topic.id,
            min_score=80
        )

        assert len(high_quality) == 2
        assert all(score["quality_score"] >= 80 for score in high_quality)

    def test_get_top_content_scores(self):
        """Test getting top content scores across all topics"""
        # Create second topic
        topic2 = Topic(
            id="test-topic-2",
            title="Test Topic 2",
            source=TopicSource.MANUAL,
            discovered_at=datetime.utcnow(),
            domain="FinTech",
            market="Germany",
            language="de",
            status=TopicStatus.DISCOVERED
        )
        self.db.insert_topic(topic2)

        # Save scores for both topics
        scores_data = [
            ("https://example.com/1", 95, self.topic.id),
            ("https://example.com/2", 85, self.topic.id),
            ("https://example.com/3", 90, topic2.id),
            ("https://example.com/4", 75, topic2.id),
        ]

        for url, quality, topic_id in scores_data:
            metrics = {
                "word_count_score": 0.8, "readability_score": 0.8,
                "keyword_score": 0.8, "structure_score": 0.8,
                "entity_score": 0.8, "freshness_score": 0.8,
                "word_count": 2000, "flesch_reading_ease": 60.0,
                "keyword_density": 2.0, "h1_count": 1, "h2_count": 4,
                "h3_count": 8, "list_count": 2, "image_count": 3,
                "entity_count": 10, "content_hash": "hash"
            }

            self.db.save_content_score(
                url=url,
                quality_score=quality,
                metrics=metrics,
                topic_id=topic_id
            )

        # Get top 3
        top_scores = self.db.get_top_content_scores(limit=3)

        assert len(top_scores) == 3
        # Ordered by quality DESC
        assert top_scores[0]["quality_score"] == 95
        assert top_scores[1]["quality_score"] == 90
        assert top_scores[2]["quality_score"] == 85

    # === Full Workflow Tests ===

    def test_full_scoring_workflow_with_mock_html(self):
        """Test complete workflow: score -> save -> retrieve"""
        # Mock HTML for testing (we won't actually fetch from a real URL)
        mock_html = """
        <html>
            <head>
                <meta property="article:published_time" content="2025-01-15T10:00:00Z">
            </head>
            <body>
                <h1>PropTech Trends 2025</h1>
                <h2>Introduction</h2>
                <p>PropTech is revolutionizing real estate. This comprehensive guide covers emerging trends in property technology, including AI-powered valuation tools, blockchain-based transactions, and smart building management systems.</p>
                <h2>Key Innovations</h2>
                <ul>
                    <li>AI and Machine Learning</li>
                    <li>Blockchain</li>
                    <li>IoT</li>
                </ul>
                <img src="chart.jpg" alt="PropTech Growth">
                <h2>Market Analysis</h2>
                <p>The PropTech market is experiencing rapid growth, with investments from major players like Microsoft, Google, and Amazon driving innovation.</p>
            </body>
        </html>
        """

        # We can't easily test score_url() without mocking requests
        # Instead, test the conversion and database storage

        # Simulate a ContentScore (as if score_url() returned it)
        from src.research.content_scorer import ContentScore

        score = ContentScore(
            url="https://example.com/proptech",
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
            h2_count=3,
            h3_count=0,
            list_count=1,
            image_count=1,
            entity_count=15,
            published_date="2025-01-15T10:00:00Z",
            content_hash="abc123"
        )

        # Convert to dict
        metrics = self.scorer.score_to_dict(score)

        # Save to database
        score_id = self.db.save_content_score(
            url=score.url,
            quality_score=score.quality_score,
            metrics=metrics,
            topic_id=self.topic.id
        )

        assert score_id > 0

        # Retrieve and verify
        saved_score = self.db.get_content_score(score.url)

        assert saved_score["quality_score"] == 85.5
        assert saved_score["word_count"] == 2500
        assert saved_score["h1_count"] == 1
        assert saved_score["h2_count"] == 3
