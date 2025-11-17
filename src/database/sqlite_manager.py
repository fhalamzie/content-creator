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
from typing import List, Optional, Dict
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

            # Sources table (global source cache with quality tracking)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    url TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    title TEXT,
                    content_preview TEXT,  -- First 500 chars for quick relevance check

                    -- Fetch tracking
                    first_fetched_at TIMESTAMP NOT NULL,
                    last_fetched_at TIMESTAMP NOT NULL,
                    fetch_count INTEGER DEFAULT 1,

                    -- Usage tracking (how many topics used this source)
                    topic_ids TEXT,  -- JSON array of topic IDs
                    usage_count INTEGER DEFAULT 0,

                    -- Quality metrics (E-E-A-T signals)
                    quality_score REAL DEFAULT 0.5,  -- 0-1 scale
                    e_e_a_t_signals TEXT,  -- JSON: {domain_authority, publication_type, freshness_decay}

                    -- Metadata
                    author TEXT,
                    published_at TIMESTAMP,

                    -- Status
                    is_stale BOOLEAN DEFAULT 0,  -- TRUE if > 7 days old

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

            # Indexes for sources
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_quality ON sources(quality_score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_freshness ON sources(last_fetched_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_stale ON sources(is_stale)")

            # SERP results table (SERP analysis for content intelligence)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS serp_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id TEXT NOT NULL,
                    search_query TEXT NOT NULL,

                    -- SERP position data
                    position INTEGER NOT NULL,  -- 1-10
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    snippet TEXT,
                    domain TEXT NOT NULL,

                    -- Metadata
                    searched_at TIMESTAMP NOT NULL,

                    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
                )
            """)

            # Indexes for SERP results
            conn.execute("CREATE INDEX IF NOT EXISTS idx_serp_topic_id ON serp_results(topic_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_serp_query ON serp_results(search_query)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_serp_searched_at ON serp_results(searched_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_serp_domain ON serp_results(domain)")

            # Content scores table (quality analysis of top-ranking content)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    topic_id TEXT,

                    -- Overall score (0-100)
                    quality_score REAL NOT NULL,

                    -- Individual metric scores (0-1 scale, weighted in quality_score)
                    word_count_score REAL,
                    readability_score REAL,
                    keyword_score REAL,
                    structure_score REAL,
                    entity_score REAL,
                    freshness_score REAL,

                    -- Metadata
                    word_count INTEGER,
                    flesch_reading_ease REAL,
                    keyword_density REAL,
                    h1_count INTEGER,
                    h2_count INTEGER,
                    h3_count INTEGER,
                    list_count INTEGER,
                    image_count INTEGER,
                    entity_count INTEGER,
                    published_date TIMESTAMP,

                    -- Content tracking
                    content_hash TEXT,

                    -- Fetch tracking
                    fetched_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE SET NULL
                )
            """)

            # Indexes for content scores
            conn.execute("CREATE INDEX IF NOT EXISTS idx_content_scores_url ON content_scores(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_content_scores_topic_id ON content_scores(topic_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_content_scores_quality ON content_scores(quality_score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_content_scores_fetched_at ON content_scores(fetched_at DESC)")

            # Difficulty scores table (competitive difficulty analysis)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS difficulty_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id TEXT UNIQUE NOT NULL,

                    -- Overall difficulty (0-100, easy→hard)
                    difficulty_score REAL NOT NULL,

                    -- Component scores (0-1 scale, weighted in difficulty_score)
                    content_quality_score REAL,
                    domain_authority_score REAL,
                    content_length_score REAL,
                    freshness_score REAL,

                    -- Recommendations
                    target_word_count INTEGER,
                    target_h2_count INTEGER,
                    target_image_count INTEGER,
                    target_quality_score REAL,

                    -- Competitive metadata
                    avg_competitor_quality REAL,
                    avg_competitor_word_count INTEGER,
                    high_authority_percentage REAL,
                    freshness_requirement TEXT,

                    -- Timing estimates
                    estimated_ranking_time TEXT,

                    -- Analysis tracking
                    analyzed_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
                )
            """)

            # Indexes for difficulty scores
            conn.execute("CREATE INDEX IF NOT EXISTS idx_difficulty_scores_topic_id ON difficulty_scores(topic_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_difficulty_scores_difficulty ON difficulty_scores(difficulty_score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_difficulty_scores_analyzed_at ON difficulty_scores(analyzed_at DESC)")

            conn.commit()
        finally:
            # Only close if not using persistent connection
            if not self._persistent_conn:
                conn.close()

        logger.info("schema_created", tables=["documents", "topics", "research_reports", "blog_posts", "social_posts", "sources", "serp_results", "content_scores"])

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

    # === SERP Results Operations ===

    def save_serp_results(
        self,
        topic_id: str,
        search_query: str,
        results: List[dict]
    ) -> int:
        """
        Save SERP results for a topic.

        Args:
            topic_id: Topic ID to associate results with
            search_query: Search query used
            results: List of SERP results, each containing:
                - position: int (1-10)
                - url: str
                - title: str
                - snippet: str (optional)
                - domain: str

        Returns:
            Number of results saved

        Example:
            >>> results = [
            ...     {
            ...         "position": 1,
            ...         "url": "https://example.com/article",
            ...         "title": "PropTech Trends 2025",
            ...         "snippet": "The future of real estate technology...",
            ...         "domain": "example.com"
            ...     },
            ...     ...
            ... ]
            >>> count = db.save_serp_results("proptech-trends-2025", "PropTech trends", results)
        """
        if not results:
            logger.warning("no_serp_results_to_save", topic_id=topic_id, query=search_query)
            return 0

        searched_at = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            for result in results:
                conn.execute(
                    """
                    INSERT INTO serp_results (
                        topic_id, search_query, position, url, title, snippet, domain, searched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        search_query,
                        result["position"],
                        result["url"],
                        result["title"],
                        result.get("snippet", ""),
                        result["domain"],
                        searched_at
                    )
                )
            conn.commit()

        logger.info(
            "serp_results_saved",
            topic_id=topic_id,
            query=search_query,
            count=len(results),
            searched_at=searched_at
        )

        return len(results)

    def get_serp_results(
        self,
        topic_id: str,
        search_query: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Get SERP results for a topic.

        Args:
            topic_id: Topic ID
            search_query: Optional search query to filter by
            limit: Maximum number of results to return

        Returns:
            List of SERP results, each containing:
                - id: int
                - topic_id: str
                - search_query: str
                - position: int
                - url: str
                - title: str
                - snippet: str
                - domain: str
                - searched_at: str (ISO timestamp)

        Example:
            >>> results = db.get_serp_results("proptech-trends-2025")
            >>> print(f"Found {len(results)} SERP results")
        """
        with self._get_connection(readonly=True) as conn:
            conn.row_factory = sqlite3.Row

            if search_query:
                if limit:
                    cursor = conn.execute(
                        """
                        SELECT * FROM serp_results
                        WHERE topic_id = ? AND search_query = ?
                        ORDER BY searched_at DESC, position ASC
                        LIMIT ?
                        """,
                        (topic_id, search_query, limit)
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM serp_results
                        WHERE topic_id = ? AND search_query = ?
                        ORDER BY searched_at DESC, position ASC
                        """,
                        (topic_id, search_query)
                    )
            else:
                if limit:
                    cursor = conn.execute(
                        """
                        SELECT * FROM serp_results
                        WHERE topic_id = ?
                        ORDER BY searched_at DESC, position ASC
                        LIMIT ?
                        """,
                        (topic_id, limit)
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM serp_results
                        WHERE topic_id = ?
                        ORDER BY searched_at DESC, position ASC
                        """,
                        (topic_id,)
                    )

            rows = cursor.fetchall()

        results = [
            {
                "id": row["id"],
                "topic_id": row["topic_id"],
                "search_query": row["search_query"],
                "position": row["position"],
                "url": row["url"],
                "title": row["title"],
                "snippet": row["snippet"],
                "domain": row["domain"],
                "searched_at": row["searched_at"]
            }
            for row in rows
        ]

        logger.info(
            "serp_results_retrieved",
            topic_id=topic_id,
            query=search_query,
            count=len(results)
        )

        return results

    def get_latest_serp_snapshot(
        self,
        topic_id: str,
        search_query: Optional[str] = None
    ) -> Optional[dict]:
        """
        Get the most recent SERP snapshot for a topic.

        Returns all results from the most recent search (up to 10 results).

        Args:
            topic_id: Topic ID
            search_query: Optional search query to filter by

        Returns:
            Dict containing:
                - searched_at: str (ISO timestamp)
                - search_query: str
                - results: List[dict] (up to 10 results)

        Example:
            >>> snapshot = db.get_latest_serp_snapshot("proptech-trends-2025")
            >>> if snapshot:
            ...     print(f"Latest snapshot from {snapshot['searched_at']}")
            ...     print(f"Found {len(snapshot['results'])} results")
        """
        # First, get the most recent searched_at timestamp
        with self._get_connection(readonly=True) as conn:
            conn.row_factory = sqlite3.Row

            if search_query:
                cursor = conn.execute(
                    """
                    SELECT MAX(searched_at) as latest_search, search_query
                    FROM serp_results
                    WHERE topic_id = ? AND search_query = ?
                    GROUP BY search_query
                    """,
                    (topic_id, search_query)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT MAX(searched_at) as latest_search, search_query
                    FROM serp_results
                    WHERE topic_id = ?
                    GROUP BY search_query
                    ORDER BY latest_search DESC
                    LIMIT 1
                    """,
                    (topic_id,)
                )

            row = cursor.fetchone()

            if not row or not row["latest_search"]:
                logger.info("no_serp_snapshot_found", topic_id=topic_id, query=search_query)
                return None

            latest_search = row["latest_search"]
            query = row["search_query"]

            # Get all results from that timestamp
            cursor = conn.execute(
                """
                SELECT * FROM serp_results
                WHERE topic_id = ? AND search_query = ? AND searched_at = ?
                ORDER BY position ASC
                """,
                (topic_id, query, latest_search)
            )

            rows = cursor.fetchall()

        results = [
            {
                "id": row["id"],
                "position": row["position"],
                "url": row["url"],
                "title": row["title"],
                "snippet": row["snippet"],
                "domain": row["domain"]
            }
            for row in rows
        ]

        snapshot = {
            "searched_at": latest_search,
            "search_query": query,
            "results": results
        }

        logger.info(
            "latest_serp_snapshot_retrieved",
            topic_id=topic_id,
            query=query,
            searched_at=latest_search,
            count=len(results)
        )

        return snapshot

    def get_serp_history(
        self,
        topic_id: str,
        search_query: Optional[str] = None,
        limit: int = 10
    ) -> List[dict]:
        """
        Get historical SERP snapshots for trend analysis.

        Groups results by searched_at timestamp to show how rankings changed over time.

        Args:
            topic_id: Topic ID
            search_query: Optional search query to filter by
            limit: Maximum number of snapshots to return (default: 10)

        Returns:
            List of snapshots, each containing:
                - searched_at: str (ISO timestamp)
                - search_query: str
                - results: List[dict] (up to 10 results)

        Example:
            >>> history = db.get_serp_history("proptech-trends-2025", limit=5)
            >>> for snapshot in history:
            ...     print(f"Snapshot from {snapshot['searched_at']}: {len(snapshot['results'])} results")
        """
        with self._get_connection(readonly=True) as conn:
            conn.row_factory = sqlite3.Row

            # Get distinct timestamps
            if search_query:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT searched_at, search_query
                    FROM serp_results
                    WHERE topic_id = ? AND search_query = ?
                    ORDER BY searched_at DESC
                    LIMIT ?
                    """,
                    (topic_id, search_query, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT DISTINCT searched_at, search_query
                    FROM serp_results
                    WHERE topic_id = ?
                    ORDER BY searched_at DESC
                    LIMIT ?
                    """,
                    (topic_id, limit)
                )

            timestamps = cursor.fetchall()

        # For each timestamp, get all results
        snapshots = []
        for ts_row in timestamps:
            searched_at = ts_row["searched_at"]
            query = ts_row["search_query"]

            with self._get_connection(readonly=True) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM serp_results
                    WHERE topic_id = ? AND search_query = ? AND searched_at = ?
                    ORDER BY position ASC
                    """,
                    (topic_id, query, searched_at)
                )
                rows = cursor.fetchall()

            results = [
                {
                    "id": row["id"],
                    "position": row["position"],
                    "url": row["url"],
                    "title": row["title"],
                    "snippet": row["snippet"],
                    "domain": row["domain"]
                }
                for row in rows
            ]

            snapshots.append({
                "searched_at": searched_at,
                "search_query": query,
                "results": results
            })

        logger.info(
            "serp_history_retrieved",
            topic_id=topic_id,
            query=search_query,
            snapshots=len(snapshots)
        )

        return snapshots

    # === Content Scores Operations ===

    def save_content_score(
        self,
        url: str,
        quality_score: float,
        metrics: dict,
        topic_id: Optional[str] = None
    ) -> int:
        """
        Save content quality score for a URL.

        Args:
            url: URL of the content
            quality_score: Overall quality score (0-100)
            metrics: Dict containing:
                - word_count_score: float (0-1)
                - readability_score: float (0-1)
                - keyword_score: float (0-1)
                - structure_score: float (0-1)
                - entity_score: float (0-1)
                - freshness_score: float (0-1)
                - word_count: int
                - flesch_reading_ease: float
                - keyword_density: float
                - h1_count: int
                - h2_count: int
                - h3_count: int
                - list_count: int
                - image_count: int
                - entity_count: int
                - published_date: str (ISO timestamp, optional)
                - content_hash: str
            topic_id: Optional topic ID to associate with

        Returns:
            Content score ID

        Example:
            >>> score_id = db.save_content_score(
            ...     url="https://example.com/article",
            ...     quality_score=85.5,
            ...     metrics={
            ...         "word_count_score": 0.9,
            ...         "readability_score": 0.8,
            ...         "keyword_score": 0.85,
            ...         "structure_score": 0.9,
            ...         "entity_score": 0.75,
            ...         "freshness_score": 1.0,
            ...         "word_count": 2500,
            ...         "flesch_reading_ease": 65.0,
            ...         "keyword_density": 2.5,
            ...         "h1_count": 1,
            ...         "h2_count": 5,
            ...         "h3_count": 10,
            ...         "list_count": 3,
            ...         "image_count": 4,
            ...         "entity_count": 15,
            ...         "published_date": "2025-01-15T10:00:00",
            ...         "content_hash": "abc123..."
            ...     },
            ...     topic_id="proptech-trends-2025"
            ... )
        """
        fetched_at = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            # Check if URL already exists
            cursor = conn.execute(
                "SELECT id FROM content_scores WHERE url = ?",
                (url,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing score
                conn.execute(
                    """
                    UPDATE content_scores SET
                        topic_id = ?,
                        quality_score = ?,
                        word_count_score = ?,
                        readability_score = ?,
                        keyword_score = ?,
                        structure_score = ?,
                        entity_score = ?,
                        freshness_score = ?,
                        word_count = ?,
                        flesch_reading_ease = ?,
                        keyword_density = ?,
                        h1_count = ?,
                        h2_count = ?,
                        h3_count = ?,
                        list_count = ?,
                        image_count = ?,
                        entity_count = ?,
                        published_date = ?,
                        content_hash = ?,
                        fetched_at = ?,
                        updated_at = ?
                    WHERE url = ?
                    """,
                    (
                        topic_id,
                        quality_score,
                        metrics.get("word_count_score"),
                        metrics.get("readability_score"),
                        metrics.get("keyword_score"),
                        metrics.get("structure_score"),
                        metrics.get("entity_score"),
                        metrics.get("freshness_score"),
                        metrics.get("word_count"),
                        metrics.get("flesch_reading_ease"),
                        metrics.get("keyword_density"),
                        metrics.get("h1_count"),
                        metrics.get("h2_count"),
                        metrics.get("h3_count"),
                        metrics.get("list_count"),
                        metrics.get("image_count"),
                        metrics.get("entity_count"),
                        metrics.get("published_date"),
                        metrics.get("content_hash"),
                        fetched_at,
                        fetched_at,
                        url
                    )
                )
                score_id = existing[0]
                logger.info(
                    "content_score_updated",
                    url=url,
                    quality_score=quality_score,
                    score_id=score_id
                )
            else:
                # Insert new score
                cursor = conn.execute(
                    """
                    INSERT INTO content_scores (
                        url, topic_id, quality_score,
                        word_count_score, readability_score, keyword_score,
                        structure_score, entity_score, freshness_score,
                        word_count, flesch_reading_ease, keyword_density,
                        h1_count, h2_count, h3_count,
                        list_count, image_count, entity_count,
                        published_date, content_hash, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        url,
                        topic_id,
                        quality_score,
                        metrics.get("word_count_score"),
                        metrics.get("readability_score"),
                        metrics.get("keyword_score"),
                        metrics.get("structure_score"),
                        metrics.get("entity_score"),
                        metrics.get("freshness_score"),
                        metrics.get("word_count"),
                        metrics.get("flesch_reading_ease"),
                        metrics.get("keyword_density"),
                        metrics.get("h1_count"),
                        metrics.get("h2_count"),
                        metrics.get("h3_count"),
                        metrics.get("list_count"),
                        metrics.get("image_count"),
                        metrics.get("entity_count"),
                        metrics.get("published_date"),
                        metrics.get("content_hash"),
                        fetched_at
                    )
                )
                score_id = cursor.lastrowid
                logger.info(
                    "content_score_saved",
                    url=url,
                    quality_score=quality_score,
                    score_id=score_id
                )

            conn.commit()

        return score_id

    def get_content_score(self, url: str) -> Optional[dict]:
        """
        Get content score by URL.

        Args:
            url: URL to lookup

        Returns:
            Dict with score data or None if not found

        Example:
            >>> score = db.get_content_score("https://example.com/article")
            >>> if score:
            ...     print(f"Quality: {score['quality_score']}/100")
        """
        with self._get_connection(readonly=True) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM content_scores WHERE url = ?",
                (url,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return dict(row)

    def get_content_scores_by_topic(
        self,
        topic_id: str,
        min_score: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Get all content scores for a topic.

        Args:
            topic_id: Topic ID
            min_score: Minimum quality score filter (0-100)
            limit: Maximum number of results

        Returns:
            List of content score dicts, ordered by quality_score DESC

        Example:
            >>> scores = db.get_content_scores_by_topic("proptech-trends", min_score=80)
            >>> print(f"Found {len(scores)} high-quality articles")
        """
        with self._get_connection(readonly=True) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT * FROM content_scores WHERE topic_id = ?"
            params = [topic_id]

            if min_score is not None:
                query += " AND quality_score >= ?"
                params.append(min_score)

            query += " ORDER BY quality_score DESC"

            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_top_content_scores(
        self,
        limit: int = 10,
        min_score: Optional[float] = None
    ) -> List[dict]:
        """
        Get top-scoring content across all topics.

        Useful for learning from the best content.

        Args:
            limit: Maximum number of results (default: 10)
            min_score: Minimum quality score filter

        Returns:
            List of content score dicts, ordered by quality_score DESC

        Example:
            >>> top_content = db.get_top_content_scores(limit=5, min_score=90)
            >>> for content in top_content:
            ...     print(f"{content['url']}: {content['quality_score']}/100")
        """
        with self._get_connection(readonly=True) as conn:
            conn.row_factory = sqlite3.Row

            if min_score is not None:
                cursor = conn.execute(
                    """
                    SELECT * FROM content_scores
                    WHERE quality_score >= ?
                    ORDER BY quality_score DESC
                    LIMIT ?
                    """,
                    (min_score, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM content_scores
                    ORDER BY quality_score DESC
                    LIMIT ?
                    """,
                    (limit,)
                )

            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    # === Difficulty Score Methods ===

    def save_difficulty_score(
        self,
        topic_id: str,
        difficulty_score: float,
        metrics: Dict,
    ) -> int:
        """
        Save or update difficulty score for a topic.

        Args:
            topic_id: Topic identifier
            difficulty_score: Overall difficulty (0-100, easy→hard)
            metrics: Dict with component scores and recommendations

        Returns:
            Difficulty score ID

        Example:
            >>> metrics = {
            ...     "content_quality_score": 0.7,
            ...     "domain_authority_score": 0.6,
            ...     "content_length_score": 0.5,
            ...     "freshness_score": 0.4,
            ...     "target_word_count": 2500,
            ...     "target_h2_count": 6,
            ...     "target_image_count": 5,
            ...     "target_quality_score": 85.0,
            ...     "avg_competitor_quality": 80.0,
            ...     "avg_competitor_word_count": 2300,
            ...     "high_authority_percentage": 60.0,
            ...     "freshness_requirement": "< 6 months",
            ...     "estimated_ranking_time": "6-9 months",
            ...     "analyzed_at": "2025-01-17T10:00:00"
            ... }
            >>> score_id = db.save_difficulty_score("proptech-2025", 65.5, metrics)
        """
        logger.info(
            "saving_difficulty_score",
            topic_id=topic_id,
            difficulty=difficulty_score
        )

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO difficulty_scores (
                    topic_id,
                    difficulty_score,
                    content_quality_score,
                    domain_authority_score,
                    content_length_score,
                    freshness_score,
                    target_word_count,
                    target_h2_count,
                    target_image_count,
                    target_quality_score,
                    avg_competitor_quality,
                    avg_competitor_word_count,
                    high_authority_percentage,
                    freshness_requirement,
                    estimated_ranking_time,
                    analyzed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic_id) DO UPDATE SET
                    difficulty_score = excluded.difficulty_score,
                    content_quality_score = excluded.content_quality_score,
                    domain_authority_score = excluded.domain_authority_score,
                    content_length_score = excluded.content_length_score,
                    freshness_score = excluded.freshness_score,
                    target_word_count = excluded.target_word_count,
                    target_h2_count = excluded.target_h2_count,
                    target_image_count = excluded.target_image_count,
                    target_quality_score = excluded.target_quality_score,
                    avg_competitor_quality = excluded.avg_competitor_quality,
                    avg_competitor_word_count = excluded.avg_competitor_word_count,
                    high_authority_percentage = excluded.high_authority_percentage,
                    freshness_requirement = excluded.freshness_requirement,
                    estimated_ranking_time = excluded.estimated_ranking_time,
                    analyzed_at = excluded.analyzed_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    topic_id,
                    difficulty_score,
                    metrics.get("content_quality_score"),
                    metrics.get("domain_authority_score"),
                    metrics.get("content_length_score"),
                    metrics.get("freshness_score"),
                    metrics.get("target_word_count"),
                    metrics.get("target_h2_count"),
                    metrics.get("target_image_count"),
                    metrics.get("target_quality_score"),
                    metrics.get("avg_competitor_quality"),
                    metrics.get("avg_competitor_word_count"),
                    metrics.get("high_authority_percentage"),
                    metrics.get("freshness_requirement"),
                    metrics.get("estimated_ranking_time"),
                    metrics.get("analyzed_at")
                )
            )

            conn.commit()

            logger.info(
                "difficulty_score_saved",
                topic_id=topic_id,
                score_id=cursor.lastrowid
            )

            return cursor.lastrowid

    def get_difficulty_score(self, topic_id: str) -> Optional[dict]:
        """
        Get difficulty score for a topic.

        Args:
            topic_id: Topic identifier

        Returns:
            Difficulty score dict or None if not found

        Example:
            >>> score = db.get_difficulty_score("proptech-2025")
            >>> if score:
            ...     print(f"Difficulty: {score['difficulty_score']}/100")
            ...     print(f"Target: {score['target_word_count']} words")
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM difficulty_scores WHERE topic_id = ?",
                (topic_id,)
            )

            row = cursor.fetchone()

            return dict(row) if row else None

    def get_difficulty_scores_by_range(
        self,
        min_difficulty: Optional[float] = None,
        max_difficulty: Optional[float] = None,
        limit: int = 50
    ) -> List[dict]:
        """
        Get difficulty scores within a difficulty range.

        Args:
            min_difficulty: Minimum difficulty (inclusive)
            max_difficulty: Maximum difficulty (inclusive)
            limit: Maximum number of results (default: 50)

        Returns:
            List of difficulty score dicts, ordered by difficulty DESC

        Example:
            >>> # Get easy topics (difficulty < 40)
            >>> easy_topics = db.get_difficulty_scores_by_range(max_difficulty=40)
            >>>
            >>> # Get hard topics (difficulty > 70)
            >>> hard_topics = db.get_difficulty_scores_by_range(min_difficulty=70)
            >>>
            >>> # Get medium topics (40-70)
            >>> medium_topics = db.get_difficulty_scores_by_range(
            ...     min_difficulty=40,
            ...     max_difficulty=70
            ... )
        """
        with self._get_connection() as conn:
            # Build query based on filters
            conditions = []
            params = []

            if min_difficulty is not None:
                conditions.append("difficulty_score >= ?")
                params.append(min_difficulty)

            if max_difficulty is not None:
                conditions.append("difficulty_score <= ?")
                params.append(max_difficulty)

            params.append(limit)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            cursor = conn.execute(
                f"""
                SELECT * FROM difficulty_scores
                WHERE {where_clause}
                ORDER BY difficulty_score DESC
                LIMIT ?
                """,
                params
            )

            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_all_difficulty_scores(
        self,
        limit: int = 100,
        order_by: str = "difficulty"
    ) -> List[dict]:
        """
        Get all difficulty scores.

        Args:
            limit: Maximum number of results (default: 100)
            order_by: Sort order - "difficulty", "analyzed_at" (default: "difficulty")

        Returns:
            List of difficulty score dicts

        Example:
            >>> # Get 10 hardest topics
            >>> hardest = db.get_all_difficulty_scores(limit=10, order_by="difficulty")
            >>>
            >>> # Get 10 most recently analyzed
            >>> recent = db.get_all_difficulty_scores(limit=10, order_by="analyzed_at")
        """
        with self._get_connection() as conn:
            if order_by == "analyzed_at":
                order_clause = "analyzed_at DESC"
            else:
                order_clause = "difficulty_score DESC"

            cursor = conn.execute(
                f"""
                SELECT * FROM difficulty_scores
                ORDER BY {order_clause}
                LIMIT ?
                """,
                (limit,)
            )

            rows = cursor.fetchall()

            return [dict(row) for row in rows]

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
