"""
SQLite Database Manager

Manages SQLite database for documents, topics, and research reports.
Provides CRUD operations with transaction support.

Pattern: Repository pattern with context manager for transactions.
"""

import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from src.models.document import Document
from src.models.topic import Topic, TopicSource, TopicStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SQLiteManager:
    """
    SQLite database manager for topic research system

    Handles:
    - Schema creation and migrations
    - Document CRUD operations
    - Topic CRUD operations
    - Research report storage
    - Full-text search (FTS5)
    - Transaction management
    """

    def __init__(self, db_path: str = "data/topics.db"):
        """
        Initialize SQLite manager

        Args:
            db_path: Path to SQLite database file

        Creates database file and schema if they don't exist.
        """
        self.db_path = db_path  # Keep as string for in-memory detection
        self._persistent_conn = None  # For in-memory databases

        # For file-based databases, ensure parent directory exists
        if db_path != ':memory:':
            path_obj = Path(db_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)

        logger.info("initializing_sqlite_manager", db_path=str(self.db_path))

        # For in-memory databases, create persistent connection
        if db_path == ':memory:':
            self._persistent_conn = sqlite3.connect(':memory:', check_same_thread=False)
            logger.info("created_persistent_in_memory_connection")

        # Create schema
        self._create_schema()

        logger.info("sqlite_manager_initialized", db_path=str(self.db_path))

    def _create_schema(self):
        """Create database schema (idempotent)"""
        # Use persistent connection for in-memory databases
        conn = self._persistent_conn if self._persistent_conn else sqlite3.connect(self.db_path)

        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")

            # Documents table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_url TEXT,

                    -- Content
                    title TEXT NOT NULL,
                    content TEXT,
                    summary TEXT,

                    -- Classification
                    language TEXT NOT NULL,
                    domain TEXT,
                    market TEXT,
                    vertical TEXT,

                    -- Deduplication
                    content_hash TEXT,
                    canonical_url TEXT,

                    -- Metadata
                    published_at TIMESTAMP,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    author TEXT,

                    -- Enrichment
                    entities TEXT,  -- JSON array
                    keywords TEXT,  -- JSON array

                    -- Provenance
                    reliability_score REAL DEFAULT 0.5,
                    paywall BOOLEAN DEFAULT 0,

                    -- Status
                    status TEXT DEFAULT 'new'
                )
            """)

            # Indexes for documents
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_lang ON documents(language)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)"
            )

            # FTS5 virtual table for full-text search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    title, content,
                    content=documents,
                    tokenize="unicode61 remove_diacritics 2"
                )
            """)

            # Topics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    cluster_label TEXT,

                    -- Discovery metadata
                    source TEXT NOT NULL,
                    source_url TEXT,
                    discovered_at TIMESTAMP,

                    -- Classification
                    domain TEXT,
                    market TEXT,
                    language TEXT,
                    intent TEXT,

                    -- Scores
                    engagement_score INTEGER DEFAULT 0,
                    trending_score REAL DEFAULT 0.0,
                    priority INTEGER DEFAULT 5,
                    content_score REAL,

                    -- Research
                    research_report TEXT,
                    citations TEXT,  -- JSON array
                    word_count INTEGER,

                    -- Deduplication
                    minhash_signature TEXT,

                    -- Status
                    status TEXT DEFAULT 'discovered',
                    notion_id TEXT,

                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP
                )
            """)

            # Indexes for topics
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_topics_priority ON topics(priority DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_topics_status ON topics(status)"
            )

            # Research reports table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    report TEXT NOT NULL,
                    sources TEXT,  -- JSON array
                    word_count INTEGER,
                    research_duration_seconds REAL,
                    source_count INTEGER DEFAULT 0,
                    average_source_quality REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
                )
            """)

            conn.commit()
        finally:
            # Only close if not using persistent connection
            if not self._persistent_conn:
                conn.close()

        logger.info("schema_created", tables=["documents", "topics", "research_reports"])

    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections

        For in-memory databases, yields the persistent connection without closing.
        For file-based databases, creates a new connection and closes it on exit.

        Yields:
            sqlite3.Connection
        """
        if self._persistent_conn:
            # Use persistent connection for in-memory databases
            # Don't close it on exit
            try:
                yield self._persistent_conn
                self._persistent_conn.commit()
            except Exception:
                self._persistent_conn.rollback()
                raise
        else:
            # Create new connection for file-based databases
            conn = sqlite3.connect(self.db_path)
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def close(self):
        """Close persistent connection (for in-memory databases)"""
        if self._persistent_conn:
            self._persistent_conn.close()
            self._persistent_conn = None
            logger.info("closed_persistent_connection")

    # === Document Operations ===

    def insert_document(self, doc: Document) -> None:
        """
        Insert document into database

        Args:
            doc: Document to insert

        Raises:
            ValueError: If document with same ID already exists
        """
        # Check for duplicate
        if self.get_document(doc.id) is not None:
            raise ValueError(f"Document with ID {doc.id} already exists")

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, source, source_url, title, content, summary,
                    language, domain, market, vertical,
                    content_hash, canonical_url,
                    published_at, fetched_at, author,
                    entities, keywords,
                    reliability_score, paywall, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.id,
                    doc.source,
                    doc.source_url,
                    doc.title,
                    doc.content,
                    doc.summary,
                    doc.language,
                    doc.domain,
                    doc.market,
                    doc.vertical,
                    doc.content_hash,
                    doc.canonical_url,
                    doc.published_at.isoformat(),
                    doc.fetched_at.isoformat(),
                    doc.author,
                    json.dumps(doc.entities) if doc.entities else None,
                    json.dumps(doc.keywords) if doc.keywords else None,
                    doc.reliability_score,
                    doc.paywall,
                    doc.status,
                ),
            )

            # Update FTS index
            conn.execute(
                "INSERT INTO documents_fts(rowid, title, content) VALUES ((SELECT rowid FROM documents WHERE id = ?), ?, ?)",
                (doc.id, doc.title, doc.content)
            )

            conn.commit()

        logger.info("document_inserted", doc_id=doc.id, language=doc.language)

    def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get document by ID

        Args:
            doc_id: Document ID

        Returns:
            Document if found, None otherwise
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_document(row)

    def update_document(self, doc: Document) -> None:
        """
        Update existing document

        Args:
            doc: Document with updated fields
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE documents SET
                    source = ?, source_url = ?, title = ?, content = ?, summary = ?,
                    language = ?, domain = ?, market = ?, vertical = ?,
                    content_hash = ?, canonical_url = ?,
                    published_at = ?, fetched_at = ?, author = ?,
                    entities = ?, keywords = ?,
                    reliability_score = ?, paywall = ?, status = ?
                WHERE id = ?
                """,
                (
                    doc.source,
                    doc.source_url,
                    doc.title,
                    doc.content,
                    doc.summary,
                    doc.language,
                    doc.domain,
                    doc.market,
                    doc.vertical,
                    doc.content_hash,
                    doc.canonical_url,
                    doc.published_at.isoformat(),
                    doc.fetched_at.isoformat(),
                    doc.author,
                    json.dumps(doc.entities) if doc.entities else None,
                    json.dumps(doc.keywords) if doc.keywords else None,
                    doc.reliability_score,
                    doc.paywall,
                    doc.status,
                    doc.id,
                ),
            )

            # Update FTS index
            conn.execute(
                "UPDATE documents_fts SET title = ?, content = ? WHERE rowid = (SELECT rowid FROM documents WHERE id = ?)",
                (doc.title, doc.content, doc.id)
            )

            conn.commit()

        logger.info("document_updated", doc_id=doc.id)

    def delete_document(self, doc_id: str) -> None:
        """
        Delete document by ID

        Args:
            doc_id: Document ID
        """
        with self._get_connection() as conn:
            # Delete from FTS first
            conn.execute(
                "DELETE FROM documents_fts WHERE rowid = (SELECT rowid FROM documents WHERE id = ?)",
                (doc_id,)
            )

            # Delete document
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()

        logger.info("document_deleted", doc_id=doc_id)

    def get_documents_by_status(self, status: str) -> List[Document]:
        """
        Get all documents with given status

        Args:
            status: Document status (new, processed, rejected)

        Returns:
            List of documents
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM documents WHERE status = ?", (status,)
            )
            rows = cursor.fetchall()

            return [self._row_to_document(row) for row in rows]

    def get_documents_by_language(self, language: str, limit: Optional[int] = None) -> List[Document]:
        """
        Get all documents in given language

        Args:
            language: ISO 639-1 language code
            limit: Maximum number of documents to return (None = all)

        Returns:
            List of documents
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row

            if limit is not None:
                cursor = conn.execute(
                    "SELECT * FROM documents WHERE language = ? LIMIT ?", (language, limit)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM documents WHERE language = ?", (language,)
                )

            rows = cursor.fetchall()

            return [self._row_to_document(row) for row in rows]

    def find_duplicate_by_hash(self, content_hash: str) -> Optional[Document]:
        """
        Find duplicate document by content hash

        Args:
            content_hash: Content hash to search for

        Returns:
            Document if found, None otherwise
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM documents WHERE content_hash = ?", (content_hash,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_document(row)

    def search_documents(self, query: str, limit: int = 10) -> List[Document]:
        """
        Search documents using full-text search

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching documents
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT d.* FROM documents d
                JOIN documents_fts fts ON d.rowid = fts.rowid
                WHERE documents_fts MATCH ?
                LIMIT ?
                """,
                (query, limit)
            )
            rows = cursor.fetchall()

            return [self._row_to_document(row) for row in rows]

    # === Topic Operations ===

    def insert_topic(self, topic: Topic) -> None:
        """
        Insert topic into database

        Args:
            topic: Topic to insert

        Raises:
            ValueError: If topic with same ID already exists
        """
        # Check for duplicate
        if self.get_topic(topic.id) is not None:
            raise ValueError(f"Topic with ID {topic.id} already exists")

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO topics (
                    id, title, description, cluster_label,
                    source, source_url, discovered_at,
                    domain, market, language, intent,
                    engagement_score, trending_score, priority, content_score,
                    research_report, citations, word_count,
                    minhash_signature,
                    status, notion_id,
                    created_at, updated_at, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    topic.id,
                    topic.title,
                    topic.description,
                    None,  # cluster_label
                    topic.source.value,
                    str(topic.source_url) if topic.source_url else None,
                    topic.discovered_at.isoformat(),
                    topic.domain,
                    topic.market,
                    topic.language,
                    topic.intent.value if topic.intent else None,
                    topic.engagement_score,
                    topic.trending_score,
                    topic.priority,
                    topic.content_score,
                    topic.research_report,
                    json.dumps(topic.citations) if topic.citations else None,
                    topic.word_count,
                    topic.minhash_signature,
                    topic.status.value,
                    None,  # notion_id
                    topic.discovered_at.isoformat(),
                    topic.updated_at.isoformat(),
                    topic.published_at.isoformat() if topic.published_at else None,
                ),
            )
            conn.commit()

        logger.info("topic_inserted", topic_id=topic.id, title=topic.title)

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """
        Get topic by ID

        Args:
            topic_id: Topic ID

        Returns:
            Topic if found, None otherwise
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM topics WHERE id = ?", (topic_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_topic(row)

    def update_topic(self, topic: Topic) -> None:
        """
        Update existing topic

        Args:
            topic: Topic with updated fields
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE topics SET
                    title = ?, description = ?,
                    source = ?, source_url = ?,
                    domain = ?, market = ?, language = ?, intent = ?,
                    engagement_score = ?, trending_score = ?, priority = ?, content_score = ?,
                    research_report = ?, citations = ?, word_count = ?,
                    minhash_signature = ?,
                    status = ?,
                    updated_at = ?, published_at = ?
                WHERE id = ?
                """,
                (
                    topic.title,
                    topic.description,
                    topic.source.value,
                    str(topic.source_url) if topic.source_url else None,
                    topic.domain,
                    topic.market,
                    topic.language,
                    topic.intent.value if topic.intent else None,
                    topic.engagement_score,
                    topic.trending_score,
                    topic.priority,
                    topic.content_score,
                    topic.research_report,
                    json.dumps(topic.citations) if topic.citations else None,
                    topic.word_count,
                    topic.minhash_signature,
                    topic.status.value,
                    datetime.utcnow().isoformat(),
                    topic.published_at.isoformat() if topic.published_at else None,
                    topic.id,
                ),
            )
            conn.commit()

        logger.info("topic_updated", topic_id=topic.id)

    def get_topics_by_status(self, status: TopicStatus) -> List[Topic]:
        """
        Get all topics with given status

        Args:
            status: Topic status

        Returns:
            List of topics
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM topics WHERE status = ?", (status.value,)
            )
            rows = cursor.fetchall()

            return [self._row_to_topic(row) for row in rows]

    def get_topics_by_priority(self, limit: int = 10) -> List[Topic]:
        """
        Get topics ordered by priority (descending)

        Args:
            limit: Maximum number of topics to return

        Returns:
            List of topics ordered by priority
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM topics ORDER BY priority DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()

            return [self._row_to_topic(row) for row in rows]

    # === Transaction Support ===

    @contextmanager
    def transaction(self):
        """
        Context manager for transactions

        Usage:
            with manager.transaction():
                manager.insert_document(doc1)
                manager.insert_document(doc2)

        Note: Currently, CRUD methods create their own connections,
        so this context manager is primarily for explicit transaction control.
        For true transaction support, use the connection directly or
        refactor CRUD methods to accept optional connection parameter.
        """
        conn = sqlite3.connect(self.db_path)
        # Store original connection methods
        old_insert = self.insert_document
        old_update = self.update_document
        old_delete = self.delete_document

        # Create wrapped versions that use the transaction connection
        def wrapped_insert(doc):
            if self.get_document(doc.id) is not None:
                raise ValueError(f"Document with ID {doc.id} already exists")

            conn.execute(
                """
                INSERT INTO documents (
                    id, source, source_url, title, content, summary,
                    language, domain, market, vertical,
                    content_hash, canonical_url,
                    published_at, fetched_at, author,
                    entities, keywords,
                    reliability_score, paywall, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.id, doc.source, doc.source_url, doc.title, doc.content, doc.summary,
                    doc.language, doc.domain, doc.market, doc.vertical,
                    doc.content_hash, doc.canonical_url,
                    doc.published_at.isoformat(), doc.fetched_at.isoformat(), doc.author,
                    json.dumps(doc.entities) if doc.entities else None,
                    json.dumps(doc.keywords) if doc.keywords else None,
                    doc.reliability_score, doc.paywall, doc.status,
                ),
            )
            conn.execute(
                "INSERT INTO documents_fts(rowid, title, content) VALUES ((SELECT rowid FROM documents WHERE id = ?), ?, ?)",
                (doc.id, doc.title, doc.content)
            )
            logger.info("document_inserted", doc_id=doc.id, language=doc.language)

        # Temporarily replace methods
        self.insert_document = wrapped_insert

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("transaction_rollback", error=str(e))
            raise
        finally:
            # Restore original methods
            self.insert_document = old_insert
            self.update_document = old_update
            self.delete_document = old_delete
            conn.close()

    # === Helper Methods ===

    def _row_to_document(self, row: sqlite3.Row) -> Document:
        """Convert database row to Document model"""
        return Document(
            id=row["id"],
            source=row["source"],
            source_url=row["source_url"],
            title=row["title"],
            content=row["content"],
            summary=row["summary"],
            language=row["language"],
            domain=row["domain"],
            market=row["market"],
            vertical=row["vertical"],
            content_hash=row["content_hash"],
            canonical_url=row["canonical_url"],
            published_at=datetime.fromisoformat(row["published_at"]),
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
            author=row["author"],
            entities=json.loads(row["entities"]) if row["entities"] else None,
            keywords=json.loads(row["keywords"]) if row["keywords"] else None,
            reliability_score=row["reliability_score"],
            paywall=bool(row["paywall"]),
            status=row["status"],
        )

    def _row_to_topic(self, row: sqlite3.Row) -> Topic:
        """Convert database row to Topic model"""
        from src.models.topic import SearchIntent

        return Topic(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            source=TopicSource(row["source"]),
            source_url=row["source_url"],
            discovered_at=datetime.fromisoformat(row["discovered_at"]),
            domain=row["domain"],
            market=row["market"],
            language=row["language"],
            intent=SearchIntent(row["intent"]) if row["intent"] else None,
            engagement_score=row["engagement_score"],
            trending_score=row["trending_score"],
            status=TopicStatus(row["status"]),
            priority=row["priority"],
            research_report=row["research_report"],
            citations=json.loads(row["citations"]) if row["citations"] else [],
            word_count=row["word_count"],
            content_score=row["content_score"],
            minhash_signature=row["minhash_signature"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
        )
