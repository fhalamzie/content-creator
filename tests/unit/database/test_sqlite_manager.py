"""
Tests for SQLiteManager

Following TDD approach:
1. Write failing tests
2. Implement minimum code to pass
3. Refactor
"""

import pytest
import sqlite3
from datetime import datetime
from src.database.sqlite_manager import SQLiteManager
from src.models.document import Document
from src.models.topic import Topic, TopicSource, TopicStatus


class TestSQLiteManagerInit:
    """Test SQLite manager initialization and schema creation"""

    def test_init_creates_database_file(self, tmp_path):
        """Should create database file on initialization"""
        db_path = tmp_path / "test.db"
        SQLiteManager(db_path=str(db_path))

        assert db_path.exists()
        assert db_path.is_file()

    def test_init_creates_documents_table(self, tmp_path):
        """Should create documents table with correct schema"""
        db_path = tmp_path / "test.db"
        SQLiteManager(db_path=str(db_path))

        # Check table exists
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
            )
            assert cursor.fetchone() is not None

    def test_init_creates_topics_table(self, tmp_path):
        """Should create topics table with correct schema"""
        db_path = tmp_path / "test.db"
        SQLiteManager(db_path=str(db_path))

        # Check table exists
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='topics'"
            )
            assert cursor.fetchone() is not None

    def test_init_creates_research_reports_table(self, tmp_path):
        """Should create research_reports table with correct schema"""
        db_path = tmp_path / "test.db"
        SQLiteManager(db_path=str(db_path))

        # Check table exists
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='research_reports'"
            )
            assert cursor.fetchone() is not None

    def test_init_creates_indexes(self, tmp_path):
        """Should create required indexes for performance"""
        db_path = tmp_path / "test.db"
        SQLiteManager(db_path=str(db_path))

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = {row[0] for row in cursor.fetchall()}

            # Check required indexes exist
            assert "idx_documents_hash" in indexes
            assert "idx_documents_lang" in indexes
            assert "idx_documents_status" in indexes
            assert "idx_topics_priority" in indexes
            assert "idx_topics_status" in indexes

    def test_init_creates_fts_table(self, tmp_path):
        """Should create FTS5 virtual table for full-text search"""
        db_path = tmp_path / "test.db"
        SQLiteManager(db_path=str(db_path))

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='documents_fts'"
            )
            assert cursor.fetchone() is not None

    def test_init_idempotent(self, tmp_path):
        """Should be safe to initialize multiple times"""
        db_path = tmp_path / "test.db"
        SQLiteManager(db_path=str(db_path))
        SQLiteManager(db_path=str(db_path))

        # Should not raise error
        assert db_path.exists()


class TestSQLiteManagerDocuments:
    """Test document CRUD operations"""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create SQLiteManager for tests"""
        db_path = tmp_path / "test.db"
        return SQLiteManager(db_path=str(db_path))

    @pytest.fixture
    def sample_document(self):
        """Create sample document for tests"""
        return Document(
            id="rss_heise_123",
            source="rss_heise",
            source_url="https://heise.de/article/123",
            title="PropTech Trends 2025",
            content="Article about proptech trends...",
            summary="Summary of proptech trends",
            language="de",
            domain="SaaS",
            market="Germany",
            vertical="Proptech",
            content_hash="abc123xyz",
            canonical_url="https://heise.de/article/123",
            published_at=datetime(2025, 11, 3, 12, 0, 0),
            fetched_at=datetime(2025, 11, 3, 12, 5, 0),
            author="John Doe",
            entities=["Berlin", "PropTech", "IoT"],
            keywords=["SaaS", "PropTech", "Germany"],
            reliability_score=0.8,
            paywall=False,
            status="new"
        )

    def test_insert_document(self, manager, sample_document):
        """Should insert document successfully"""
        manager.insert_document(sample_document)

        # Verify insertion
        doc = manager.get_document(sample_document.id)
        assert doc is not None
        assert doc.id == sample_document.id
        assert doc.title == sample_document.title
        assert doc.language == sample_document.language

    def test_insert_document_duplicate_id_raises_error(self, manager, sample_document):
        """Should raise error when inserting duplicate document ID"""
        manager.insert_document(sample_document)

        with pytest.raises(ValueError, match="already exists"):
            manager.insert_document(sample_document)

    def test_get_document_not_found_returns_none(self, manager):
        """Should return None when document not found"""
        doc = manager.get_document("nonexistent_id")
        assert doc is None

    def test_update_document(self, manager, sample_document):
        """Should update document successfully"""
        manager.insert_document(sample_document)

        # Update document
        sample_document.status = "processed"
        sample_document.entities = ["Berlin", "PropTech", "IoT", "Smart Building"]
        manager.update_document(sample_document)

        # Verify update
        doc = manager.get_document(sample_document.id)
        assert doc.status == "processed"
        assert len(doc.entities) == 4

    def test_delete_document(self, manager, sample_document):
        """Should delete document successfully"""
        manager.insert_document(sample_document)
        manager.delete_document(sample_document.id)

        # Verify deletion
        doc = manager.get_document(sample_document.id)
        assert doc is None

    def test_get_documents_by_status(self, manager, sample_document):
        """Should retrieve documents by status"""
        manager.insert_document(sample_document)

        # Insert another document with different status
        doc2 = sample_document.model_copy(deep=True)
        doc2.id = "rss_heise_124"
        doc2.status = "processed"
        manager.insert_document(doc2)

        # Get documents by status
        new_docs = manager.get_documents_by_status("new")
        assert len(new_docs) == 1
        assert new_docs[0].id == sample_document.id

        processed_docs = manager.get_documents_by_status("processed")
        assert len(processed_docs) == 1
        assert processed_docs[0].id == doc2.id

    def test_get_documents_by_language(self, manager, sample_document):
        """Should retrieve documents by language"""
        manager.insert_document(sample_document)

        # Insert another document with different language
        doc2 = sample_document.model_copy(deep=True)
        doc2.id = "rss_heise_124"
        doc2.language = "en"
        manager.insert_document(doc2)

        # Get documents by language
        de_docs = manager.get_documents_by_language("de")
        assert len(de_docs) == 1
        assert de_docs[0].language == "de"

    def test_find_duplicate_by_hash(self, manager, sample_document):
        """Should find duplicate documents by content hash"""
        manager.insert_document(sample_document)

        # Try to find duplicate
        duplicate = manager.find_duplicate_by_hash(sample_document.content_hash)
        assert duplicate is not None
        assert duplicate.id == sample_document.id

    def test_search_documents_fts(self, manager, sample_document):
        """Should search documents using full-text search"""
        manager.insert_document(sample_document)

        # Search for "proptech"
        results = manager.search_documents("proptech")
        assert len(results) == 1
        assert results[0].id == sample_document.id


class TestSQLiteManagerTopics:
    """Test topic CRUD operations"""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create SQLiteManager for tests"""
        db_path = tmp_path / "test.db"
        return SQLiteManager(db_path=str(db_path))

    @pytest.fixture
    def sample_topic(self):
        """Create sample topic for tests"""
        return Topic(
            id="topic_123",
            title="PropTech in Germany 2025",
            description="Analysis of proptech trends in Germany",
            source=TopicSource.RSS,
            source_url="https://heise.de/article/123",
            domain="proptech",
            market="de",
            language="de",
            status=TopicStatus.DISCOVERED,
            priority=8,
            engagement_score=150,
            trending_score=75.5
        )

    def test_insert_topic(self, manager, sample_topic):
        """Should insert topic successfully"""
        manager.insert_topic(sample_topic)

        # Verify insertion
        topic = manager.get_topic(sample_topic.id)
        assert topic is not None
        assert topic.id == sample_topic.id
        assert topic.title == sample_topic.title

    def test_update_topic(self, manager, sample_topic):
        """Should update topic successfully"""
        manager.insert_topic(sample_topic)

        # Update topic
        sample_topic.status = TopicStatus.RESEARCHED
        sample_topic.research_report = "Research report content..."
        manager.update_topic(sample_topic)

        # Verify update
        topic = manager.get_topic(sample_topic.id)
        assert topic.status == TopicStatus.RESEARCHED
        assert topic.research_report is not None

    def test_get_topics_by_status(self, manager, sample_topic):
        """Should retrieve topics by status"""
        manager.insert_topic(sample_topic)

        # Insert another topic with different status
        topic2 = sample_topic.model_copy(deep=True)
        topic2.id = "topic_124"
        topic2.status = TopicStatus.PUBLISHED
        manager.insert_topic(topic2)

        # Get topics by status
        discovered = manager.get_topics_by_status(TopicStatus.DISCOVERED)
        assert len(discovered) == 1
        assert discovered[0].id == sample_topic.id

    def test_get_topics_by_priority(self, manager, sample_topic):
        """Should retrieve topics ordered by priority"""
        manager.insert_topic(sample_topic)

        # Insert topics with different priorities
        topic2 = sample_topic.model_copy(deep=True)
        topic2.id = "topic_124"
        topic2.priority = 10
        manager.insert_topic(topic2)

        topic3 = sample_topic.model_copy(deep=True)
        topic3.id = "topic_125"
        topic3.priority = 5
        manager.insert_topic(topic3)

        # Get topics by priority (descending)
        topics = manager.get_topics_by_priority(limit=10)
        assert len(topics) == 3
        assert topics[0].priority == 10
        assert topics[1].priority == 8
        assert topics[2].priority == 5


class TestSQLiteManagerTransactions:
    """Test transaction handling"""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create SQLiteManager for tests"""
        db_path = tmp_path / "test.db"
        return SQLiteManager(db_path=str(db_path))

    def test_context_manager_commits_on_success(self, manager):
        """Should commit transaction on successful context exit"""
        doc = Document(
            id="test_doc",
            source="test",
            source_url="https://test.com",
            title="Test",
            content="Test content",
            language="en",
            domain="Test",
            market="Test",
            vertical="Test",
            content_hash="test_hash",
            canonical_url="https://test.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        with manager.transaction():
            manager.insert_document(doc)

        # Verify document was committed
        assert manager.get_document("test_doc") is not None

    def test_context_manager_rolls_back_on_error(self, manager):
        """Should rollback transaction on error"""
        doc = Document(
            id="test_doc",
            source="test",
            source_url="https://test.com",
            title="Test",
            content="Test content",
            language="en",
            domain="Test",
            market="Test",
            vertical="Test",
            content_hash="test_hash",
            canonical_url="https://test.com",
            published_at=datetime.now(),
            fetched_at=datetime.now()
        )

        try:
            with manager.transaction():
                manager.insert_document(doc)
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # Verify document was rolled back
        assert manager.get_document("test_doc") is None
