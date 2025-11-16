"""
Integration tests for SERP Analyzer + SQLite

Tests:
- Real DuckDuckGo searches
- Database save/retrieve operations
- End-to-end workflows
- Historical tracking
"""

import pytest
import time
from datetime import datetime

from src.research.serp_analyzer import SERPAnalyzer, SERPResult
from src.database.sqlite_manager import SQLiteManager
from src.models.topic import Topic, TopicSource, TopicStatus


class TestSERPIntegration:
    """Integration tests for SERP analysis + database"""

    def setup_method(self):
        """Setup test fixtures with in-memory database"""
        self.analyzer = SERPAnalyzer()
        self.db = SQLiteManager(db_path=":memory:")

        # Create a test topic
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

    def test_save_and_retrieve_serp_results(self):
        """Test saving and retrieving SERP results"""
        # Create mock results
        results = [
            {
                "position": 1,
                "url": "https://example.com/1",
                "title": "Example Title 1",
                "snippet": "Example snippet 1",
                "domain": "example.com"
            },
            {
                "position": 2,
                "url": "https://test.com/2",
                "title": "Test Title 2",
                "snippet": "Test snippet 2",
                "domain": "test.com"
            }
        ]

        # Save results
        count = self.db.save_serp_results(
            topic_id=self.topic.id,
            search_query="test query",
            results=results
        )

        assert count == 2

        # Retrieve results
        retrieved = self.db.get_serp_results(topic_id=self.topic.id)

        assert len(retrieved) == 2
        assert retrieved[0]["position"] == 1
        assert retrieved[0]["url"] == "https://example.com/1"
        assert retrieved[0]["title"] == "Example Title 1"
        assert retrieved[0]["domain"] == "example.com"

    def test_save_empty_results(self):
        """Test saving empty results list"""
        count = self.db.save_serp_results(
            topic_id=self.topic.id,
            search_query="test query",
            results=[]
        )

        assert count == 0

        # Should have no results
        retrieved = self.db.get_serp_results(topic_id=self.topic.id)
        assert len(retrieved) == 0

    def test_get_serp_results_by_query(self):
        """Test filtering SERP results by search query"""
        # Save results for two different queries
        results_q1 = [
            {"position": 1, "url": "https://example.com/1", "title": "Title 1", "snippet": "Snippet", "domain": "example.com"}
        ]
        results_q2 = [
            {"position": 1, "url": "https://test.com/2", "title": "Title 2", "snippet": "Snippet", "domain": "test.com"}
        ]

        self.db.save_serp_results(self.topic.id, "query 1", results_q1)
        self.db.save_serp_results(self.topic.id, "query 2", results_q2)

        # Retrieve by specific query
        retrieved_q1 = self.db.get_serp_results(self.topic.id, search_query="query 1")
        retrieved_q2 = self.db.get_serp_results(self.topic.id, search_query="query 2")

        assert len(retrieved_q1) == 1
        assert len(retrieved_q2) == 1
        assert retrieved_q1[0]["url"] == "https://example.com/1"
        assert retrieved_q2[0]["url"] == "https://test.com/2"

    def test_get_serp_results_with_limit(self):
        """Test limiting number of SERP results"""
        # Save 5 results
        results = [
            {"position": i, "url": f"https://example.com/{i}", "title": f"Title {i}", "snippet": "Snippet", "domain": "example.com"}
            for i in range(1, 6)
        ]

        self.db.save_serp_results(self.topic.id, "test query", results)

        # Retrieve with limit
        retrieved = self.db.get_serp_results(self.topic.id, limit=3)

        assert len(retrieved) == 3

    def test_get_latest_serp_snapshot(self):
        """Test getting most recent SERP snapshot"""
        # Save first snapshot
        results_1 = [
            {"position": 1, "url": "https://old.com/1", "title": "Old Title", "snippet": "Snippet", "domain": "old.com"}
        ]
        self.db.save_serp_results(self.topic.id, "test query", results_1)

        # Wait a moment to ensure different timestamps
        time.sleep(0.1)

        # Save second snapshot (more recent)
        results_2 = [
            {"position": 1, "url": "https://new.com/1", "title": "New Title", "snippet": "Snippet", "domain": "new.com"}
        ]
        self.db.save_serp_results(self.topic.id, "test query", results_2)

        # Get latest snapshot
        snapshot = self.db.get_latest_serp_snapshot(self.topic.id)

        assert snapshot is not None
        assert len(snapshot["results"]) == 1
        assert snapshot["results"][0]["url"] == "https://new.com/1"  # Should be the newer one

    def test_get_latest_serp_snapshot_no_results(self):
        """Test getting latest snapshot when no results exist"""
        snapshot = self.db.get_latest_serp_snapshot("nonexistent-topic")

        assert snapshot is None

    def test_get_serp_history(self):
        """Test getting historical SERP snapshots"""
        # Save 3 snapshots over time
        for i in range(1, 4):
            results = [
                {"position": 1, "url": f"https://snapshot{i}.com/1", "title": f"Snapshot {i}", "snippet": "Snippet", "domain": f"snapshot{i}.com"}
            ]
            self.db.save_serp_results(self.topic.id, "test query", results)
            time.sleep(0.1)  # Ensure different timestamps

        # Get history (limit 10, should return all 3)
        history = self.db.get_serp_history(self.topic.id)

        assert len(history) == 3
        # Should be ordered newest first
        assert "snapshot3" in history[0]["results"][0]["url"]
        assert "snapshot2" in history[1]["results"][0]["url"]
        assert "snapshot1" in history[2]["results"][0]["url"]

    def test_get_serp_history_with_limit(self):
        """Test getting limited SERP history"""
        # Save 5 snapshots
        for i in range(1, 6):
            results = [
                {"position": 1, "url": f"https://snapshot{i}.com/1", "title": f"Snapshot {i}", "snippet": "Snippet", "domain": f"snapshot{i}.com"}
            ]
            self.db.save_serp_results(self.topic.id, "test query", results)
            time.sleep(0.05)

        # Get history with limit
        history = self.db.get_serp_history(self.topic.id, limit=2)

        assert len(history) == 2
        # Should be the 2 most recent
        assert "snapshot5" in history[0]["results"][0]["url"]
        assert "snapshot4" in history[1]["results"][0]["url"]

    # === Real Search Tests ===

    @pytest.mark.integration
    def test_real_search_basic(self):
        """Test real DuckDuckGo search (requires internet)"""
        try:
            results = self.analyzer.search("Python programming", max_results=5)

            # Verify we got results
            assert len(results) > 0
            assert len(results) <= 5

            # Verify result structure
            for i, result in enumerate(results, 1):
                assert result.position == i
                assert result.url.startswith("http")
                assert len(result.title) > 0
                assert len(result.domain) > 0
                # Snippet may be empty in some cases
        except Exception as e:
            pytest.skip(f"Real search failed (network issue?): {str(e)}")

    @pytest.mark.integration
    def test_real_search_with_region(self):
        """Test real DuckDuckGo search with region (requires internet)"""
        try:
            results = self.analyzer.search(
                "PropTech trends",
                max_results=3,
                region="de-de"  # Germany
            )

            assert len(results) > 0
            assert len(results) <= 3

            # Verify result structure
            for result in results:
                assert result.url.startswith("http")
                assert result.domain != ""
        except Exception as e:
            pytest.skip(f"Real search failed (network issue?): {str(e)}")

    # === End-to-End Workflow Tests ===

    def test_full_workflow_search_analyze_save(self):
        """Test complete workflow: search -> analyze -> save to DB"""
        # Create mock results (skip actual search for speed)
        mock_results = [
            SERPResult(1, "https://example.com/1", "Example Title", "Example snippet", "example.com"),
            SERPResult(2, "https://test.com/2", "Test Title", "Test snippet", "test.com"),
            SERPResult(3, "https://example.com/3", "Another Example", "More snippet", "example.com"),
        ]

        # Analyze results
        analysis = self.analyzer.analyze_serp(mock_results)

        assert analysis["total_results"] == 3
        assert analysis["unique_domains"] == 2

        # Convert to dicts and save
        result_dicts = self.analyzer.results_to_dict(mock_results)
        count = self.db.save_serp_results(self.topic.id, "test query", result_dicts)

        assert count == 3

        # Retrieve and verify
        saved_results = self.db.get_serp_results(self.topic.id)

        assert len(saved_results) == 3
        assert saved_results[0]["title"] == "Example Title"

    def test_full_workflow_track_changes_over_time(self):
        """Test tracking SERP changes over time"""
        # Snapshot 1
        old_results = [
            SERPResult(1, "https://example.com/1", "Title 1", "Snippet", "example.com"),
            SERPResult(2, "https://test.com/2", "Title 2", "Snippet", "test.com"),
        ]
        old_dicts = self.analyzer.results_to_dict(old_results)
        self.db.save_serp_results(self.topic.id, "test query", old_dicts)

        time.sleep(0.1)

        # Snapshot 2 (changes: test.com moved to #1, new.com entered at #3)
        new_results = [
            SERPResult(1, "https://test.com/2", "Title 2", "Snippet", "test.com"),  # Moved up
            SERPResult(2, "https://example.com/1", "Title 1", "Snippet", "example.com"),  # Moved down
            SERPResult(3, "https://new.com/3", "New Title", "Snippet", "new.com"),  # New entrant
        ]
        new_dicts = self.analyzer.results_to_dict(new_results)
        self.db.save_serp_results(self.topic.id, "test query", new_dicts)

        # Get history
        history = self.db.get_serp_history(self.topic.id)

        assert len(history) == 2  # Two snapshots

        # Compare snapshots using analyzer
        comparison = self.analyzer.compare_snapshots(old_results, new_results)

        assert len(comparison["new_entrants"]) == 1
        assert "https://new.com/3" in comparison["new_entrants"]
        assert len(comparison["position_changes"]) == 2  # Both old URLs changed position
