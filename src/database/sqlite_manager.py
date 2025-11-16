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
            self._apply_pragmas(self._persistent_conn)
            logger.info("created_persistent_in_memory_connection")

        # Create schema
        self._create_schema()

        logger.info("sqlite_manager_initialized", db_path=str(self.db_path))

    def _apply_pragmas(self, conn: sqlite3.Connection):
        """
        Apply performance PRAGMAs to a connection.

        Based on: https://x.com/meln1k/status/1813314113705062774
        These settings enable 60K RPS on a $5 VPS.
        """
        # 1. WAL mode: Reads don't block writes (and vice versa)
        conn.execute("PRAGMA journal_mode = WAL")

        # 2. Wait 5s for locks before SQLITE_BUSY errors
        conn.execute("PRAGMA busy_timeout = 5000")

        # 3. Sync less frequently (safe with WAL mode)
        conn.execute("PRAGMA synchronous = NORMAL")

        # 4. 20MB memory cache (-20000 = 20MB in KB)
        conn.execute("PRAGMA cache_size = -20000")

        # 5. Enable foreign keys (disabled by default for historical reasons)
        conn.execute("PRAGMA foreign_keys = ON")

        # 6. Store temp tables in RAM (huge performance boost)
        conn.execute("PRAGMA temp_store = memory")

        # Note: Do NOT use cache=shared (causes SQLITE_BUSY errors)

    def _create_schema(self):
        """Create database schema (idempotent)"""
        # Use persistent connection for in-memory databases
        if self._persistent_conn:
            conn = self._persistent_conn
        else:
            conn = sqlite3.connect(self.db_path)
            self._apply_pragmas(conn)

        try:

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

            # Blog posts table (single source of truth before Notion sync)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blog_posts (
                    id TEXT PRIMARY KEY,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    excerpt TEXT,

                    -- SEO
                    meta_description TEXT,
                    keywords TEXT,  -- JSON array
                    primary_keyword TEXT,

                    -- Content metadata
                    word_count INTEGER,
                    language TEXT DEFAULT 'de',
                    brand_voice TEXT DEFAULT 'Professional',
                    target_audience TEXT,

                    -- Images
                    hero_image_url TEXT,
                    hero_image_alt TEXT,
                    supporting_images TEXT,  -- JSON array

                    -- Research reference
                    research_topic_id TEXT,

                    -- Cluster (Hub + Spoke strategy for topical authority)
                    cluster_id TEXT,
                    cluster_role TEXT DEFAULT 'Standalone',  -- Hub, Spoke, or Standalone
                    internal_links TEXT,  -- JSON array of suggested links [{title, slug, anchor_text, context}]

                    -- Notion sync
                    notion_id TEXT,
                    notion_synced_at TIMESTAMP,

                    -- Status
                    status TEXT DEFAULT 'draft',

                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP,

                    FOREIGN KEY (research_topic_id) REFERENCES topics(id) ON DELETE SET NULL
                )
            """)

            # Social posts table (single source of truth before Notion sync)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS social_posts (
                    id TEXT PRIMARY KEY,
                    blog_post_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    content TEXT NOT NULL,

                    -- Media
                    image_url TEXT,
                    image_provider TEXT,  -- 'og' or 'ai'

                    -- Metadata
                    hashtags TEXT,  -- JSON array
                    character_count INTEGER,
                    language TEXT DEFAULT 'de',

                    -- Notion sync
                    notion_id TEXT,
                    notion_synced_at TIMESTAMP,

                    -- Status
                    status TEXT DEFAULT 'draft',

                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP,
                    scheduled_at TIMESTAMP,

                    FOREIGN KEY (blog_post_id) REFERENCES blog_posts(id) ON DELETE CASCADE
                )
            """)

            # Indexes for blog posts
            conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_slug ON blog_posts(slug)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_status ON blog_posts(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_created_at ON blog_posts(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_cluster_id ON blog_posts(cluster_id)")

            # Indexes for social posts
            conn.execute("CREATE INDEX IF NOT EXISTS idx_social_posts_blog_post_id ON social_posts(blog_post_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_social_posts_platform ON social_posts(platform)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_social_posts_status ON social_posts(status)")

            conn.commit()
        finally:
            # Only close if not using persistent connection
            if not self._persistent_conn:
                conn.close()

        logger.info("schema_created", tables=["documents", "topics", "research_reports", "blog_posts", "social_posts"])

        # Run migrations for existing databases
        self._run_migrations()

    def _run_migrations(self):
        """
        Run database migrations for existing databases.

        Adds columns if they don't exist (safe for new and existing databases).
        """
        # Use persistent connection for in-memory databases
        if self._persistent_conn:
            conn = self._persistent_conn
        else:
            conn = sqlite3.connect(self.db_path)
            self._apply_pragmas(conn)

        try:
            cursor = conn.cursor()

            # Migration 1: Add cluster fields to blog_posts table
            # Check if cluster_id column exists
            cursor.execute("PRAGMA table_info(blog_posts)")
            columns = {row[1] for row in cursor.fetchall()}

            if 'cluster_id' not in columns:
                logger.info("migration_adding_cluster_fields")
                cursor.execute("ALTER TABLE blog_posts ADD COLUMN cluster_id TEXT")
                cursor.execute("ALTER TABLE blog_posts ADD COLUMN cluster_role TEXT DEFAULT 'Standalone'")
                cursor.execute("ALTER TABLE blog_posts ADD COLUMN internal_links TEXT")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_blog_posts_cluster_id ON blog_posts(cluster_id)")
                conn.commit()
                logger.info("migration_cluster_fields_added")

        finally:
            # Only close if not using persistent connection
            if not self._persistent_conn:
                conn.close()

    @contextmanager
    def _get_connection(self, readonly: bool = False):
        """
        Context manager for database connections with performance optimizations.

        For in-memory databases, yields the persistent connection without closing.
        For file-based databases, creates a new connection and closes it on exit.

        Args:
            readonly: If True, open connection in read-only mode (allows concurrent reads)

        Yields:
            sqlite3.Connection
        """
        if self._persistent_conn:
            # Use persistent connection for in-memory databases
            # Don't close it on exit
            try:
                # Use BEGIN IMMEDIATE for write transactions (prevents SQLITE_BUSY)
                if not readonly:
                    self._persistent_conn.execute("BEGIN IMMEDIATE")
                yield self._persistent_conn
                self._persistent_conn.commit()
            except Exception:
                self._persistent_conn.rollback()
                raise
        else:
            # Create new connection for file-based databases
            # Apply performance PRAGMAs
            uri = f"file:{self.db_path}?mode=ro" if readonly else f"file:{self.db_path}?mode=rwc"
            conn = sqlite3.connect(uri, uri=True)

            # Apply PRAGMAs for this connection (60K RPS optimization)
            self._apply_pragmas(conn)

            try:
                # Use BEGIN IMMEDIATE for write transactions
                if not readonly:
                    conn.execute("BEGIN IMMEDIATE")
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
        with self._get_connection(readonly=True) as conn:
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
        with self._get_connection(readonly=True) as conn:
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
        with self._get_connection(readonly=True) as conn:
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
        with self._get_connection(readonly=True) as conn:
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
        with self._get_connection(readonly=True) as conn:
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
        with self._get_connection(readonly=True) as conn:
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
        with self._get_connection(readonly=True) as conn:
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
        with self._get_connection(readonly=True) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM topics ORDER BY priority DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()

            return [self._row_to_topic(row) for row in rows]

    def find_related_topics(
        self,
        topic_id: str,
        limit: int = 5,
        min_similarity: float = 0.2
    ) -> List[tuple[Topic, float]]:
        """
        Find related topics using keyword similarity.

        Uses Jaccard similarity on title keywords to find semantically related topics.
        Only returns topics that have research reports (research_report IS NOT NULL).

        Args:
            topic_id: Topic ID to find related topics for
            limit: Maximum number of related topics to return (default: 5)
            min_similarity: Minimum similarity score (0.0-1.0, default: 0.2)

        Returns:
            List of (Topic, similarity_score) tuples, ordered by similarity descending

        Example:
            >>> related = db.find_related_topics("proptech-trends-2025", limit=3)
            >>> for topic, score in related:
            ...     print(f"{topic.title}: {score:.2f}")
            PropTech Investment Strategies: 0.45
            Real Estate Technology: 0.38
            Smart Building Automation: 0.32
        """
        # Get source topic
        source_topic = self.get_topic(topic_id)
        if not source_topic:
            logger.warning("source_topic_not_found", topic_id=topic_id)
            return []

        # Extract keywords from source topic title
        source_keywords = self._extract_keywords(source_topic.title)

        logger.info(
            "finding_related_topics",
            topic_id=topic_id,
            source_keywords=len(source_keywords),
            limit=limit
        )

        # Get all topics with research reports (excluding source topic)
        with self._get_connection(readonly=True) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM topics
                WHERE id != ? AND research_report IS NOT NULL AND research_report != ''
                """,
                (topic_id,)
            )
            rows = cursor.fetchall()

        # Calculate similarity scores
        scored_topics = []
        for row in rows:
            candidate_topic = self._row_to_topic(row)
            candidate_keywords = self._extract_keywords(candidate_topic.title)

            # Calculate Jaccard similarity: |A ∩ B| / |A ∪ B|
            similarity = self._jaccard_similarity(source_keywords, candidate_keywords)

            if similarity >= min_similarity:
                scored_topics.append((candidate_topic, similarity))

        # Sort by similarity descending
        scored_topics.sort(key=lambda x: x[1], reverse=True)

        # Return top N
        result = scored_topics[:limit]

        logger.info(
            "found_related_topics",
            topic_id=topic_id,
            total_candidates=len(rows),
            matched_topics=len(scored_topics),
            returned_topics=len(result)
        )

        return result

    def _extract_keywords(self, text: str) -> set:
        """
        Extract keywords from text for similarity comparison.

        Converts to lowercase, removes common German/English stop words,
        splits on whitespace and special characters.

        Args:
            text: Text to extract keywords from

        Returns:
            Set of normalized keywords
        """
        # Common stop words (German + English)
        stop_words = {
            # German
            'der', 'die', 'das', 'und', 'oder', 'in', 'von', 'zu', 'mit',
            'für', 'auf', 'im', 'an', 'am', 'dem', 'den', 'des', 'ein', 'eine',
            'ist', 'sind', 'werden', 'wurde', 'haben', 'hat', 'bei', 'nach',
            # English
            'the', 'and', 'or', 'in', 'of', 'to', 'with', 'for', 'on', 'at',
            'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
            'by', 'from', 'a', 'an',
            # Common numbers
            '2024', '2025', '2026'
        }

        # Normalize to lowercase
        text = text.lower()

        # Remove special characters, keep alphanumeric and spaces
        import re
        text = re.sub(r'[^\w\s-]', ' ', text)

        # Split into words
        words = text.split()

        # Filter stop words and short words
        keywords = {
            word for word in words
            if len(word) > 2 and word not in stop_words
        }

        return keywords

    def _jaccard_similarity(self, set_a: set, set_b: set) -> float:
        """
        Calculate Jaccard similarity between two sets.

        Formula: |A ∩ B| / |A ∪ B|

        Args:
            set_a: First set
            set_b: Second set

        Returns:
            Similarity score (0.0-1.0)
        """
        if not set_a or not set_b:
            return 0.0

        intersection = len(set_a & set_b)
        union = len(set_a | set_b)

        if union == 0:
            return 0.0

        return intersection / union

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
