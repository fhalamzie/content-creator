"""
Integration tests for Difficulty Scoring + Database

Tests:
- Database save/retrieve operations
- Full difficulty calculation workflow
- Integration with SERP + Content scoring
"""

import pytest
from datetime import datetime
from src.research.difficulty_scorer import DifficultyScorer
from src.database.sqlite_manager import SQLiteManager
from src.models.topic import Topic, TopicSource, TopicStatus


class TestDifficultyIntegration:
    """Integration tests for difficulty scoring"""

    def setup_method(self):
        """Setup test fixtures"""
        self.scorer = DifficultyScorer()
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

    def test_save_and_retrieve_difficulty_score(self):
        """Test saving and retrieving difficulty score"""
        metrics = {
            "content_quality_score": 0.7,
            "domain_authority_score": 0.6,
            "content_length_score": 0.5,
            "freshness_score": 0.4,
            "target_word_count": 2500,
            "target_h2_count": 6,
            "target_image_count": 5,
            "target_quality_score": 85.0,
            "avg_competitor_quality": 80.0,
            "avg_competitor_word_count": 2300,
            "high_authority_percentage": 60.0,
            "freshness_requirement": "< 6 months",
            "estimated_ranking_time": "6-9 months",
            "analyzed_at": datetime.utcnow().isoformat()
        }

        # Save
        score_id = self.db.save_difficulty_score(
            topic_id=self.topic.id,
            difficulty_score=65.5,
            metrics=metrics
        )

        assert score_id > 0

        # Retrieve
        score = self.db.get_difficulty_score(self.topic.id)

        assert score is not None
        assert score["difficulty_score"] == 65.5
        assert score["target_word_count"] == 2500
        assert score["topic_id"] == self.topic.id

    def test_update_existing_difficulty_score(self):
        """Test updating an existing difficulty score"""
        metrics1 = {
            "content_quality_score": 0.6,
            "domain_authority_score": 0.5,
            "content_length_score": 0.5,
            "freshness_score": 0.4,
            "target_word_count": 2000,
            "target_h2_count": 5,
            "target_image_count": 4,
            "target_quality_score": 80.0,
            "avg_competitor_quality": 75.0,
            "avg_competitor_word_count": 1900,
            "high_authority_percentage": 50.0,
            "freshness_requirement": "< 12 months",
            "estimated_ranking_time": "4-6 months",
            "analyzed_at": datetime.utcnow().isoformat()
        }

        # Save once
        self.db.save_difficulty_score(
            topic_id=self.topic.id,
            difficulty_score=55.0,
            metrics=metrics1
        )

        # Update with new metrics
        metrics2 = metrics1.copy()
        metrics2["target_word_count"] = 2500
        metrics2["avg_competitor_quality"] = 82.0

        self.db.save_difficulty_score(
            topic_id=self.topic.id,
            difficulty_score=62.0,
            metrics=metrics2
        )

        # Should have updated, not created new
        score = self.db.get_difficulty_score(self.topic.id)

        assert score["difficulty_score"] == 62.0
        assert score["target_word_count"] == 2500
        assert score["avg_competitor_quality"] == 82.0

    def test_get_difficulty_scores_by_range_easy(self):
        """Test retrieving easy topics by difficulty range"""
        # Create 3 topics with varying difficulty
        topics_data = [
            ("easy-1", 30.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("easy-2", 35.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("hard-1", 75.0, {"analyzed_at": datetime.utcnow().isoformat()})
        ]

        for topic_id, difficulty, metrics in topics_data:
            # Create topic
            topic = Topic(
                id=topic_id,
                title=f"Topic {topic_id}",
                source=TopicSource.MANUAL,
                discovered_at=datetime.utcnow(),
                domain="Test",
                market="Germany",
                language="de",
                status=TopicStatus.DISCOVERED
            )
            self.db.insert_topic(topic)

            # Save difficulty score
            self.db.save_difficulty_score(
                topic_id=topic_id,
                difficulty_score=difficulty,
                metrics=metrics
            )

        # Get only easy topics (< 40)
        easy_topics = self.db.get_difficulty_scores_by_range(max_difficulty=40)

        assert len(easy_topics) == 2
        assert all(score["difficulty_score"] <= 40 for score in easy_topics)

    def test_get_difficulty_scores_by_range_hard(self):
        """Test retrieving hard topics by difficulty range"""
        # Create 3 topics
        topics_data = [
            ("easy-1", 35.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("hard-1", 72.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("hard-2", 85.0, {"analyzed_at": datetime.utcnow().isoformat()})
        ]

        for topic_id, difficulty, metrics in topics_data:
            topic = Topic(
                id=topic_id,
                title=f"Topic {topic_id}",
                source=TopicSource.MANUAL,
                discovered_at=datetime.utcnow(),
                domain="Test",
                market="Germany",
                language="de",
                status=TopicStatus.DISCOVERED
            )
            self.db.insert_topic(topic)

            self.db.save_difficulty_score(
                topic_id=topic_id,
                difficulty_score=difficulty,
                metrics=metrics
            )

        # Get only hard topics (>= 70)
        hard_topics = self.db.get_difficulty_scores_by_range(min_difficulty=70)

        assert len(hard_topics) == 2
        assert all(score["difficulty_score"] >= 70 for score in hard_topics)
        # Ordered by difficulty DESC
        assert hard_topics[0]["difficulty_score"] == 85.0
        assert hard_topics[1]["difficulty_score"] == 72.0

    def test_get_difficulty_scores_by_range_medium(self):
        """Test retrieving medium difficulty topics"""
        # Create topics across all ranges
        topics_data = [
            ("easy-1", 30.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("medium-1", 50.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("medium-2", 60.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("hard-1", 80.0, {"analyzed_at": datetime.utcnow().isoformat()})
        ]

        for topic_id, difficulty, metrics in topics_data:
            topic = Topic(
                id=topic_id,
                title=f"Topic {topic_id}",
                source=TopicSource.MANUAL,
                discovered_at=datetime.utcnow(),
                domain="Test",
                market="Germany",
                language="de",
                status=TopicStatus.DISCOVERED
            )
            self.db.insert_topic(topic)

            self.db.save_difficulty_score(
                topic_id=topic_id,
                difficulty_score=difficulty,
                metrics=metrics
            )

        # Get medium topics (40-70)
        medium_topics = self.db.get_difficulty_scores_by_range(
            min_difficulty=40,
            max_difficulty=70
        )

        assert len(medium_topics) == 2
        assert all(40 <= score["difficulty_score"] <= 70 for score in medium_topics)

    def test_get_all_difficulty_scores_by_difficulty(self):
        """Test retrieving all difficulty scores ordered by difficulty"""
        # Create 3 topics
        topics_data = [
            ("topic-1", 90.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("topic-2", 45.0, {"analyzed_at": datetime.utcnow().isoformat()}),
            ("topic-3", 65.0, {"analyzed_at": datetime.utcnow().isoformat()})
        ]

        for topic_id, difficulty, metrics in topics_data:
            topic = Topic(
                id=topic_id,
                title=f"Topic {topic_id}",
                source=TopicSource.MANUAL,
                discovered_at=datetime.utcnow(),
                domain="Test",
                market="Germany",
                language="de",
                status=TopicStatus.DISCOVERED
            )
            self.db.insert_topic(topic)

            self.db.save_difficulty_score(
                topic_id=topic_id,
                difficulty_score=difficulty,
                metrics=metrics
            )

        # Get all ordered by difficulty
        all_scores = self.db.get_all_difficulty_scores(order_by="difficulty")

        assert len(all_scores) == 3
        # Ordered DESC
        assert all_scores[0]["difficulty_score"] == 90.0
        assert all_scores[1]["difficulty_score"] == 65.0
        assert all_scores[2]["difficulty_score"] == 45.0

    # === Full Workflow Tests ===

    def test_full_difficulty_workflow(self):
        """Test complete workflow: calculate -> save -> retrieve"""
        # Mock SERP results
        serp_results = [
            {"domain_authority": "High"} for _ in range(5)
        ] + [
            {"domain_authority": "Medium"} for _ in range(5)
        ]

        # Mock content scores
        content_scores = [
            {
                "quality_score": 85,
                "word_count": 2500,
                "h2_count": 6,
                "image_count": 5,
                "freshness_score": 0.9
            }
            for _ in range(10)
        ]

        # 1. Calculate difficulty
        difficulty = self.scorer.calculate_difficulty(
            topic_id=self.topic.id,
            serp_results=serp_results,
            content_scores=content_scores
        )

        assert difficulty.difficulty_score > 0
        assert difficulty.topic_id == self.topic.id
        assert difficulty.target_word_count > 0
        assert difficulty.estimated_ranking_time is not None

        # 2. Convert to dict
        metrics = self.scorer.score_to_dict(difficulty)

        # 3. Save to database
        score_id = self.db.save_difficulty_score(
            topic_id=difficulty.topic_id,
            difficulty_score=difficulty.difficulty_score,
            metrics=metrics
        )

        assert score_id > 0

        # 4. Retrieve and verify
        saved_score = self.db.get_difficulty_score(self.topic.id)

        assert saved_score["difficulty_score"] == difficulty.difficulty_score
        assert saved_score["target_word_count"] == difficulty.target_word_count
        assert saved_score["estimated_ranking_time"] == difficulty.estimated_ranking_time

    def test_full_workflow_with_recommendations(self):
        """Test complete workflow including recommendations"""
        # Mock data for medium difficulty topic
        serp_results = [
            {"domain_authority": "High" if i < 3 else "Low"}
            for i in range(10)
        ]

        content_scores = [
            {
                "quality_score": 75,
                "word_count": 1800,
                "h2_count": 5,
                "image_count": 3,
                "freshness_score": 0.8
            }
            for _ in range(10)
        ]

        # Calculate difficulty
        difficulty = self.scorer.calculate_difficulty(
            topic_id=self.topic.id,
            serp_results=serp_results,
            content_scores=content_scores
        )

        # Generate recommendations
        recommendations = self.scorer.generate_recommendations(difficulty)

        assert len(recommendations) >= 4
        # Should have different priorities
        priorities = [r.priority for r in recommendations]
        assert "high" in priorities or "medium" in priorities

        # Save to database
        metrics = self.scorer.score_to_dict(difficulty)
        score_id = self.db.save_difficulty_score(
            topic_id=self.topic.id,
            difficulty_score=difficulty.difficulty_score,
            metrics=metrics
        )

        assert score_id > 0

        # Verify saved
        saved_score = self.db.get_difficulty_score(self.topic.id)
        assert saved_score is not None

    def test_workflow_easy_vs_hard_topics(self):
        """Test comparing easy vs hard topics"""
        # Create easy topic
        easy_topic = Topic(
            id="easy-topic",
            title="Easy Topic",
            source=TopicSource.MANUAL,
            discovered_at=datetime.utcnow(),
            domain="Test",
            market="Germany",
            language="de",
            status=TopicStatus.DISCOVERED
        )
        self.db.insert_topic(easy_topic)

        # Create hard topic
        hard_topic = Topic(
            id="hard-topic",
            title="Hard Topic",
            source=TopicSource.MANUAL,
            discovered_at=datetime.utcnow(),
            domain="Test",
            market="Germany",
            language="de",
            status=TopicStatus.DISCOVERED
        )
        self.db.insert_topic(hard_topic)

        # Easy topic data (low quality, low DA)
        easy_serp = [{"domain_authority": "Low"} for _ in range(10)]
        easy_content = [
            {
                "quality_score": 60,
                "word_count": 1000,
                "h2_count": 3,
                "image_count": 2,
                "freshness_score": 0.5
            }
            for _ in range(10)
        ]

        # Hard topic data (high quality, high DA)
        hard_serp = [{"domain_authority": "High"} for _ in range(10)]
        hard_content = [
            {
                "quality_score": 92,
                "word_count": 4000,
                "h2_count": 10,
                "image_count": 8,
                "freshness_score": 1.0
            }
            for _ in range(10)
        ]

        # Calculate both
        easy_diff = self.scorer.calculate_difficulty("easy-topic", easy_serp, easy_content)
        hard_diff = self.scorer.calculate_difficulty("hard-topic", hard_serp, hard_content)

        # Save both
        self.db.save_difficulty_score(
            topic_id="easy-topic",
            difficulty_score=easy_diff.difficulty_score,
            metrics=self.scorer.score_to_dict(easy_diff)
        )

        self.db.save_difficulty_score(
            topic_id="hard-topic",
            difficulty_score=hard_diff.difficulty_score,
            metrics=self.scorer.score_to_dict(hard_diff)
        )

        # Easy should be much lower difficulty
        assert easy_diff.difficulty_score < hard_diff.difficulty_score
        assert easy_diff.difficulty_score < 50
        assert hard_diff.difficulty_score > 70

        # Verify retrieval
        easy_scores = self.db.get_difficulty_scores_by_range(max_difficulty=50)
        hard_scores = self.db.get_difficulty_scores_by_range(min_difficulty=70)

        assert len(easy_scores) >= 1
        assert len(hard_scores) >= 1
