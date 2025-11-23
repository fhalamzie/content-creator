# FastAPI Backend Migration Plan

**Project:** Content Creator - Production Architecture Upgrade
**Version:** 1.1 (Aligned)
**Status:** Planning Phase - Ready for Implementation
**Date:** 2025-11-23
**Estimated Duration:** 6-8 weeks
**Domain:** übergabeprotokoll24.de

---

## 🎯 Executive Summary

Migrate from Streamlit MVP to production-grade architecture with:
- **FastAPI** REST API backend (strict type safety, async-first)
- **PostgreSQL 16** database (fully normalized, ACID-compliant, full-text search)
- **95%+ test coverage** (100% on critical paths: services, repositories, API)
- **CI/CD** via GitHub Actions (automated testing, deployment to VPS)
- **Docker** containerization (VPS deployment via GitHub)
- **Huey + Redis** for background tasks
- **Caddy** for SSL/reverse proxy
- **React** frontend (Phase 2 - separate plan)

**Migration Strategy:** Direct cutover to Postgres (no dual-write needed - MVP with no production users)

---

## ✅ Architecture Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Migration** | Direct Postgres cutover | MVP stage, no production users, faster implementation |
| **API Design** | Thin API + Rich Services | Testable, reusable business logic |
| **Background Jobs** | Huey + Redis | Simple, already in use, sufficient for MVP |
| **Test Coverage** | 95%+ overall, 100% critical | Pragmatic balance of speed vs quality |
| **Type Safety** | mypy --strict | Maximum compile-time error detection |
| **Database Schema** | Fully normalized | Strict schema, foreign keys, complex queries |
| **Authentication** | Designed but not enforced | API ready for auth, add later when needed |
| **Deployment** | VPS via GitHub Actions | Docker on VPS, Caddy SSL, domain ready |

---

## 📊 Current State Analysis

### Architecture (Monolithic Streamlit)

```
streamlit_app.py
    ↓
├─ UI Pages (Streamlit)
│   ├─ Dashboard
│   ├─ Generate
│   ├─ Topic Research
│   └─ Settings
│
├─ Agents (Business Logic)
│   ├─ CompetitorResearchAgent
│   ├─ KeywordResearchAgent
│   ├─ ContentPipeline
│   └─ HybridResearchOrchestrator
│
├─ Collectors (Data Sources)
│   ├─ RSSCollector
│   ├─ RedditCollector
│   ├─ TrendsCollector
│   └─ AutocompleteCollector
│
├─ Research (Deep Research)
│   ├─ DeepResearcher (multi-backend)
│   ├─ ContentSynthesizer
│   └─ MultiStageReranker
│
├─ Processors (Data Processing)
│   ├─ Deduplicator
│   ├─ TopicClusterer
│   └─ EntityExtractor
│
├─ Database (SQLite)
│   └─ sqlite_manager.py
│
└─ Notion Integration
    └─ TopicsSync
```

**Problems:**
1. ❌ **Tight coupling**: UI directly calls business logic
2. ❌ **No API layer**: Can't integrate with external systems
3. ❌ **SQLite limitations**: Single-writer, no concurrent access
4. ❌ **No type safety at boundaries**: Runtime errors slip through
5. ❌ **Manual testing**: No CI/CD, deployment is manual
6. ❌ **Monolithic**: Can't scale components independently

### Current Tech Stack

| Component | Technology | Status |
|-----------|-----------|--------|
| **UI** | Streamlit | ⚠️ Needs replacement |
| **Backend** | Python functions | ⚠️ Needs API layer |
| **Database** | SQLite | ⚠️ Needs Postgres |
| **Models** | Pydantic 2.9.1 | ✅ Keep (upgrade to latest) |
| **Testing** | pytest 8.3.3 | ✅ Keep (add coverage) |
| **Queue** | Huey + SQLite | ⚠️ Upgrade to Huey + Redis |
| **Logging** | structlog | ✅ Keep |
| **CI/CD** | None | ❌ Needs GitHub Actions |
| **Containerization** | None | ❌ Needs Docker |

---

## 🏗️ Target Architecture

### Modern 3-Tier Architecture

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (Phase 2)                                     │
│  React + TypeScript + Vite                              │
│  - Dashboard, Topic Discovery, Content Browser          │
│  - Real-time updates (WebSockets)                       │
└─────────────────────────────────────────────────────────┘
                    ↓ HTTP/REST
┌─────────────────────────────────────────────────────────┐
│  API LAYER (FastAPI)                                    │
│  ├─ Routes (HTTP handlers)                              │
│  ├─ Dependencies (auth, DB sessions, rate limits)       │
│  ├─ Request/Response Models (Pydantic)                  │
│  └─ Middleware (CORS, logging, error handling)          │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  SERVICE LAYER (Business Logic)                         │
│  ├─ TopicService (discovery, research, validation)      │
│  ├─ ContentService (generation, synthesis)              │
│  ├─ CompetitorService (research, analysis)              │
│  ├─ KeywordService (research, scoring)                  │
│  └─ CollectionService (RSS, Reddit, Trends)             │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  DATA ACCESS LAYER (Repositories)                       │
│  ├─ TopicRepository (CRUD, queries)                     │
│  ├─ DocumentRepository (storage, search)                │
│  ├─ CollectionRepository (feed management)              │
│  └─ CacheRepository (Redis for hot data)                │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  DATABASE LAYER                                         │
│  ├─ Postgres (primary data store)                       │
│  │   ├─ Topics (id, title, status, metadata)            │
│  │   ├─ Documents (raw collected content)               │
│  │   ├─ Collections (feed configs, schedules)           │
│  │   └─ FTS (full-text search with tsvector)            │
│  ├─ Redis (cache, queue, sessions)                      │
│  └─ S3/MinIO (image storage - optional)                 │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│  BACKGROUND WORKERS (Celery/Huey)                       │
│  ├─ CollectionWorker (RSS/Reddit polling)               │
│  ├─ ResearchWorker (deep research jobs)                 │
│  ├─ SynthesisWorker (content generation)                │
│  └─ NotionSyncWorker (bidirectional sync)               │
└─────────────────────────────────────────────────────────┘
```

### Technology Stack (Target)

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **API Framework** | FastAPI 0.115+ | Async-first, OpenAPI, Pydantic native |
| **ASGI Server** | Uvicorn | High performance, WebSocket support |
| **Database** | PostgreSQL 16+ | ACID, full-text search, JSONB, pgvector |
| **ORM** | SQLAlchemy 2.0+ | Type-safe, async support, migrations |
| **Migrations** | Alembic | Schema versioning, rollback support |
| **Cache/Queue** | Redis 7+ | In-memory speed, pub/sub, Celery backend |
| **Task Queue** | Huey + Redis | Simple, lightweight, sufficient for MVP |
| **Validation** | Pydantic 2.10+ | Runtime validation, strict types |
| **Testing** | pytest + pytest-asyncio | Async support, fixtures, parametrize |
| **Coverage** | coverage.py + pytest-cov | 95%+ overall, 100% critical paths |
| **Mocking** | pytest-mock + responses | HTTP mocking, API stubbing |
| **CI/CD** | GitHub Actions | Free for public repos, matrix builds |
| **Linting** | Ruff + mypy | Fast linting, strict type checking |
| **Formatting** | Ruff | Black-compatible, fast |
| **Containerization** | Docker + Docker Compose | Multi-stage builds, dev/prod parity |
| **Reverse Proxy** | Caddy 2+ | Automatic SSL, simple config |
| **Monitoring** | Prometheus + Grafana | Metrics, dashboards, alerts |
| **Logging** | structlog + JSON | Structured, searchable, ELK-ready |

---

## 🗄️ Database Migration Strategy

### Migration Approach: Direct Cutover

**Strategy**: Since we're in MVP stage with no production users, we'll do a **direct migration** from SQLite to PostgreSQL:

1. ✅ Design normalized Postgres schema
2. ✅ Create migration scripts (Alembic)
3. ✅ Write data export from SQLite
4. ✅ Import to Postgres with validation
5. ✅ Update connection strings
6. ✅ Test thoroughly in local dev
7. ✅ Deploy to VPS

**Timeline**: 1 week (Phase 1)

---

### Postgres Schema Design (Fully Normalized)

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Fuzzy search
CREATE EXTENSION IF NOT EXISTS "pgvector";   -- Vector similarity (future)

-- ============================================================================
-- TOPICS (Primary Entity)
-- ============================================================================
CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    description TEXT,

    -- Discovery metadata
    source VARCHAR(50) NOT NULL,  -- rss, reddit, trends, autocomplete
    source_url TEXT,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Classification
    domain VARCHAR(100) NOT NULL,
    market VARCHAR(10) NOT NULL,
    language VARCHAR(10) NOT NULL,
    intent VARCHAR(50),  -- informational, commercial, transactional

    -- Scoring
    engagement_score INTEGER DEFAULT 0,
    trending_score NUMERIC(5,2) DEFAULT 0.0,
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),

    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'discovered',

    -- Research results
    research_report TEXT,

    -- Content metadata
    word_count INTEGER,
    content_score NUMERIC(5,2),

    -- Images (normalized in separate table)
    hero_image_url TEXT,

    -- Notion sync
    notion_id VARCHAR(100) UNIQUE,
    notion_synced_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT topics_status_check CHECK (status IN ('discovered', 'validated', 'researched', 'drafted', 'published', 'archived'))
);

-- ============================================================================
-- CITATIONS (Normalized)
-- ============================================================================
CREATE TABLE citations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title VARCHAR(500),
    source VARCHAR(200),
    cited_at TIMESTAMPTZ DEFAULT NOW(),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(topic_id, url)
);

CREATE INDEX idx_citations_topic_id ON citations(topic_id);

-- ============================================================================
-- COMPETITORS (Normalized)
-- ============================================================================
CREATE TABLE competitors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,

    -- Competitor info
    name VARCHAR(200) NOT NULL,
    website TEXT,
    description TEXT,

    -- Social handles
    linkedin_url TEXT,
    twitter_url TEXT,
    facebook_url TEXT,

    -- Analysis
    content_strategy TEXT,
    posting_frequency VARCHAR(100),
    strengths TEXT,
    weaknesses TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_competitors_topic_id ON competitors(topic_id);

-- ============================================================================
-- CONTENT GAPS (Normalized)
-- ============================================================================
CREATE TABLE content_gaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,

    gap_description TEXT NOT NULL,
    opportunity_score NUMERIC(3,2) DEFAULT 0.5,  -- 0.0 to 1.0

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_content_gaps_topic_id ON content_gaps(topic_id);

-- ============================================================================
-- KEYWORDS (Normalized)
-- ============================================================================
CREATE TABLE keywords (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,

    keyword VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- primary, secondary, long_tail

    -- Metrics
    search_volume VARCHAR(50),  -- "1K-10K", "10K-100K", etc.
    competition VARCHAR(20),    -- Low, Medium, High
    difficulty INTEGER CHECK (difficulty BETWEEN 0 AND 100),
    intent VARCHAR(50),         -- Informational, Commercial, Transactional

    -- Trends
    trending BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(topic_id, keyword)
);

CREATE INDEX idx_keywords_topic_id ON keywords(topic_id);
CREATE INDEX idx_keywords_type ON keywords(type);

-- ============================================================================
-- SUPPORTING IMAGES (Normalized)
-- ============================================================================
CREATE TABLE supporting_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,

    url TEXT NOT NULL,
    alt_text VARCHAR(500),
    size VARCHAR(20),      -- "1024x1024", "2048x2048", etc.
    quality VARCHAR(20),   -- "standard", "hd", "ultra"
    position INTEGER,      -- Order in article

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_supporting_images_topic_id ON supporting_images(topic_id);

-- Indexes for performance
CREATE INDEX idx_topics_status ON topics(status);
CREATE INDEX idx_topics_domain_market ON topics(domain, market);
CREATE INDEX idx_topics_priority_desc ON topics(priority DESC, discovered_at DESC);
CREATE INDEX idx_topics_notion_id ON topics(notion_id) WHERE notion_id IS NOT NULL;

-- Full-text search (Postgres native)
ALTER TABLE topics ADD COLUMN search_vector tsvector;
CREATE INDEX idx_topics_search ON topics USING GIN(search_vector);

-- Auto-update search vector
CREATE OR REPLACE FUNCTION topics_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.research_report, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER topics_search_vector_trigger
    BEFORE INSERT OR UPDATE ON topics
    FOR EACH ROW EXECUTE FUNCTION topics_search_vector_update();

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER topics_updated_at_trigger
    BEFORE UPDATE ON topics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Documents (collected content)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Content
    title VARCHAR(1000) NOT NULL,
    content TEXT,
    summary TEXT,
    url TEXT NOT NULL,
    canonical_url TEXT,

    -- Source
    source VARCHAR(50) NOT NULL,
    source_metadata JSONB DEFAULT '{}',

    -- Classification
    domain VARCHAR(100) NOT NULL,
    market VARCHAR(10) NOT NULL,
    language VARCHAR(10) NOT NULL,

    -- Deduplication
    content_hash VARCHAR(64) NOT NULL,  -- SHA256 hash

    -- Metadata
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    author VARCHAR(500),

    -- Quality
    reliability_score NUMERIC(3,2) DEFAULT 0.5,
    paywall BOOLEAN DEFAULT FALSE,

    -- Processing
    status VARCHAR(50) DEFAULT 'new',
    processed_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT documents_status_check CHECK (status IN ('new', 'processed', 'rejected'))
);

-- Indexes
CREATE INDEX idx_documents_hash ON documents(content_hash);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_domain_market ON documents(domain, market);
CREATE INDEX idx_documents_published_at_desc ON documents(published_at DESC NULLS LAST);

-- Full-text search for documents
ALTER TABLE documents ADD COLUMN search_vector tsvector;
CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);

CREATE TRIGGER documents_search_vector_trigger
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION topics_search_vector_update();

CREATE TRIGGER documents_updated_at_trigger
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Collections (feed management)
CREATE TABLE collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Feed info
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- rss, reddit, twitter
    url TEXT NOT NULL,

    -- Configuration
    domain VARCHAR(100) NOT NULL,
    market VARCHAR(10) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,

    -- Polling
    poll_interval_minutes INTEGER DEFAULT 60,
    last_polled_at TIMESTAMPTZ,
    next_poll_at TIMESTAMPTZ,

    -- Health
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_error TEXT,

    -- ETag/Last-Modified (HTTP caching)
    etag VARCHAR(200),
    last_modified TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(type, url, domain, market)
);

-- Indexes
CREATE INDEX idx_collections_enabled ON collections(enabled, next_poll_at) WHERE enabled = TRUE;
CREATE INDEX idx_collections_domain_market ON collections(domain, market);

CREATE TRIGGER collections_updated_at_trigger
    BEFORE UPDATE ON collections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### SQLite to Postgres Data Migration

**Approach**: Simple export/import (no need for dual-write since MVP has no production users)

```bash
# 1. Export from SQLite
python scripts/export_sqlite.py --output data/export.json

# 2. Validate export
python scripts/validate_export.py --input data/export.json

# 3. Import to Postgres
python scripts/import_postgres.py --input data/export.json

# 4. Verify data integrity
python scripts/verify_migration.py

# 5. Run test suite against Postgres
pytest tests/ --db=postgresql
```

**Data Mapping** (SQLite → Postgres normalized tables):
- Topics table → topics, citations, keywords, competitors, content_gaps, supporting_images
- Documents table → documents (1:1)
- Collections table → collections (1:1)

**Timeline**: 2-3 days (scripting + validation)

---

## 🔌 API Design

### RESTful Endpoints

#### Topics API

```
POST   /api/v1/topics                    # Create topic (manual entry)
GET    /api/v1/topics                    # List topics (pagination, filters)
GET    /api/v1/topics/{id}               # Get topic details
PATCH  /api/v1/topics/{id}               # Update topic
DELETE /api/v1/topics/{id}               # Delete topic

POST   /api/v1/topics/discover           # Trigger topic discovery
POST   /api/v1/topics/{id}/research      # Run deep research
POST   /api/v1/topics/{id}/synthesize    # Generate content
POST   /api/v1/topics/{id}/validate      # Validate topic quality

GET    /api/v1/topics/{id}/competitors   # Get competitor analysis
GET    /api/v1/topics/{id}/keywords      # Get keyword research
```

#### Collections API (Feed Management)

```
POST   /api/v1/collections               # Add feed
GET    /api/v1/collections               # List feeds
GET    /api/v1/collections/{id}          # Get feed details
PATCH  /api/v1/collections/{id}          # Update feed config
DELETE /api/v1/collections/{id}          # Remove feed

POST   /api/v1/collections/{id}/poll     # Trigger immediate poll
GET    /api/v1/collections/{id}/health   # Get feed health stats
```

#### Documents API (Collected Content)

```
GET    /api/v1/documents                 # List documents
GET    /api/v1/documents/{id}            # Get document
DELETE /api/v1/documents/{id}            # Delete document

GET    /api/v1/documents/search          # Full-text search
GET    /api/v1/documents/duplicates      # Find near-duplicates
```

#### Research API

```
POST   /api/v1/research/competitor       # Run competitor research
POST   /api/v1/research/keyword          # Run keyword research
POST   /api/v1/research/deep             # Run deep research (gpt-researcher)
```

#### Admin API

```
GET    /api/v1/admin/health              # Health check
GET    /api/v1/admin/metrics             # Prometheus metrics
GET    /api/v1/admin/config              # Get system config
PATCH  /api/v1/admin/config              # Update config (feature flags)
```

### Request/Response Models (Pydantic)

```python
# app/api/models/topic.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, ConfigDict

# Request models
class TopicCreateRequest(BaseModel):
    """Request body for creating a topic manually"""
    title: str = Field(..., min_length=3, max_length=500)
    description: Optional[str] = None
    source: str = "manual"
    domain: str
    market: str
    language: str
    priority: int = Field(default=5, ge=1, le=10)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "PropTech trends in Germany 2025",
                "description": "Analysis of emerging PropTech technologies",
                "domain": "proptech",
                "market": "de",
                "language": "de",
                "priority": 8
            }
        }
    )

class TopicUpdateRequest(BaseModel):
    """Request body for updating a topic"""
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    status: Optional[str] = None

    model_config = ConfigDict(extra='forbid')  # Strict: reject unknown fields

class TopicListRequest(BaseModel):
    """Query parameters for listing topics"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    domain: Optional[str] = None
    market: Optional[str] = None
    status: Optional[str] = None
    min_priority: Optional[int] = Field(None, ge=1, le=10)
    search: Optional[str] = None  # Full-text search

# Response models
class TopicResponse(BaseModel):
    """Topic response (full details)"""
    id: UUID
    title: str
    description: Optional[str]

    source: str
    source_url: Optional[HttpUrl]
    discovered_at: datetime

    domain: str
    market: str
    language: str
    intent: Optional[str]

    engagement_score: int
    trending_score: float
    priority: int
    status: str

    research_report: Optional[str]
    citations: List[str]
    competitors: List[dict]
    content_gaps: List[str]
    keywords: dict

    word_count: Optional[int]
    content_score: Optional[float]

    hero_image_url: Optional[HttpUrl]
    supporting_images: List[dict]

    notion_id: Optional[str]
    notion_synced_at: Optional[datetime]

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # ORM mode

class TopicListResponse(BaseModel):
    """Paginated topic list"""
    items: List[TopicResponse]
    total: int
    page: int
    page_size: int
    pages: int

class TopicSummaryResponse(BaseModel):
    """Topic summary (list view)"""
    id: UUID
    title: str
    status: str
    priority: int
    domain: str
    market: str
    discovered_at: datetime
```

### Error Handling

```python
# app/api/errors.py
from fastapi import HTTPException, status
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    """Standardized error response"""
    error_code: str
    message: str
    details: dict = {}

class APIError(HTTPException):
    """Base API error"""
    def __init__(self, error_code: str, message: str, details: dict = {}, status_code: int = 400):
        super().__init__(
            status_code=status_code,
            detail=ErrorDetail(
                error_code=error_code,
                message=message,
                details=details
            ).model_dump()
        )

# Specific errors
class TopicNotFoundError(APIError):
    def __init__(self, topic_id: str):
        super().__init__(
            error_code="TOPIC_NOT_FOUND",
            message=f"Topic {topic_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )

class TopicValidationError(APIError):
    def __init__(self, errors: dict):
        super().__init__(
            error_code="TOPIC_VALIDATION_FAILED",
            message="Topic validation failed",
            details={"errors": errors},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
```

---

## 🧪 Testing Strategy (100% Coverage)

### Test Pyramid

```
         /\
        /  \       E2E Tests (5%)
       /____\      - Full workflow tests
      /      \     - API integration tests
     /        \
    /__________\   Integration Tests (15%)
   /            \  - Database integration
  /              \ - External API mocking
 /________________\
/                  \
|  Unit Tests (80%) |
|  - Business logic |
|  - Validators     |
|  - Utilities      |
```

### Testing Layers

#### 1. Unit Tests (80% of tests)

**Target**: Individual functions, classes, methods

```python
# tests/unit/services/test_topic_service.py
import pytest
from uuid import UUID
from app.services.topic_service import TopicService
from app.models.topic import TopicCreateRequest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def topic_service():
    """Create topic service with mocked dependencies"""
    repo = Mock()
    cache = Mock()
    return TopicService(repository=repo, cache=cache)

@pytest.mark.asyncio
async def test_create_topic_success(topic_service):
    """Test successful topic creation"""
    # Arrange
    request = TopicCreateRequest(
        title="Test Topic",
        domain="proptech",
        market="de",
        language="de"
    )
    topic_service.repository.create = AsyncMock(return_value={"id": UUID("...")})

    # Act
    result = await topic_service.create_topic(request)

    # Assert
    assert result["title"] == "Test Topic"
    topic_service.repository.create.assert_called_once()

@pytest.mark.asyncio
async def test_create_topic_duplicate_title(topic_service):
    """Test topic creation with duplicate title"""
    # Arrange
    request = TopicCreateRequest(title="Duplicate", ...)
    topic_service.repository.exists_by_title = AsyncMock(return_value=True)

    # Act & Assert
    with pytest.raises(TopicValidationError) as exc:
        await topic_service.create_topic(request)

    assert "duplicate" in str(exc.value).lower()
```

#### 2. Integration Tests (15% of tests)

**Target**: Database, external APIs, service interactions

```python
# tests/integration/test_topic_repository.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.db.repositories.topic_repository import TopicRepository
from app.db.models import Topic

@pytest.fixture
async def db_session():
    """Create test database session"""
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost:5433/test_db")
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_topic_repository_create_and_find(db_session):
    """Test topic creation and retrieval"""
    # Arrange
    repo = TopicRepository(db_session)
    topic_data = {
        "title": "Integration Test Topic",
        "domain": "proptech",
        "market": "de",
        "language": "de"
    }

    # Act
    created = await repo.create(topic_data)
    found = await repo.get_by_id(created.id)

    # Assert
    assert found is not None
    assert found.title == topic_data["title"]
    assert found.status == "discovered"

@pytest.mark.asyncio
async def test_topic_full_text_search(db_session):
    """Test Postgres full-text search"""
    repo = TopicRepository(db_session)

    # Create test topics
    await repo.create({"title": "PropTech trends in Germany", ...})
    await repo.create({"title": "Fashion e-commerce in France", ...})

    # Search
    results = await repo.search("PropTech Germany")

    # Assert
    assert len(results) == 1
    assert "proptech" in results[0].title.lower()
```

#### 3. E2E Tests (5% of tests)

**Target**: Full API workflows

```python
# tests/e2e/test_topic_workflow.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_topic_discovery_workflow():
    """Test complete topic discovery workflow"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Create topic
        create_response = await client.post("/api/v1/topics", json={
            "title": "E2E Test Topic",
            "domain": "proptech",
            "market": "de",
            "language": "de"
        })
        assert create_response.status_code == 201
        topic_id = create_response.json()["id"]

        # 2. Run competitor research
        competitor_response = await client.post(
            f"/api/v1/topics/{topic_id}/research/competitor"
        )
        assert competitor_response.status_code == 200

        # 3. Run keyword research
        keyword_response = await client.post(
            f"/api/v1/topics/{topic_id}/research/keyword"
        )
        assert keyword_response.status_code == 200

        # 4. Verify topic updated
        get_response = await client.get(f"/api/v1/topics/{topic_id}")
        topic = get_response.json()
        assert len(topic["competitors"]) > 0
        assert len(topic["keywords"]) > 0
        assert topic["status"] == "researched"
```

### Coverage Requirements

```bash
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=95
    --strict-markers
    --asyncio-mode=auto

markers =
    unit: Unit tests (fast, no external dependencies)
    integration: Integration tests (database, external APIs)
    e2e: End-to-end tests (full workflows)
    slow: Slow tests (run separately in CI)
```

**Coverage Targets**:
- Overall: **100%** (strict)
- API routes: 100% (all endpoints covered)
- Services: 100% (all business logic)
- Repositories: 100% (all database operations)
- Models: 100% (all validators)

**Exclusions**:
- `__init__.py` files (imports only)
- Configuration files
- Migrations

---

## 🚀 CI/CD Pipeline (GitHub Actions)

### Workflow Structure

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  PYTHON_VERSION: "3.12"
  POSTGRES_VERSION: "16"

jobs:
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}

      - name: Install dependencies
        run: |
          pip install ruff mypy
          pip install -r requirements-dev.txt

      - name: Run Ruff (linting)
        run: ruff check . --output-format=github

      - name: Run Ruff (formatting)
        run: ruff format --check .

      - name: Run mypy (type checking)
        run: mypy app tests --strict

  test:
    name: Test (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-${{ matrix.python-version }}-pip-${{ hashFiles('**/requirements*.txt') }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run migrations
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test_db
        run: alembic upgrade head

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest \
            --cov=app \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=95 \
            -v

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-umbrella

  security:
    name: Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy (vulnerability scanner)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy results to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Run Bandit (Python security linter)
        run: |
          pip install bandit
          bandit -r app -f json -o bandit-report.json

  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: [lint, test, security]
    if: github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=ref,event=branch
            type=sha,prefix={{branch}}-

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: [build]
    if: github.ref == 'refs/heads/develop'
    steps:
      - name: Deploy to staging
        run: |
          # Add deployment script here
          echo "Deploy to staging environment"
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.2
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, sqlalchemy]

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks
```

---

## 🐳 Docker Architecture

### Multi-Stage Dockerfile

```dockerfile
# Dockerfile
# Stage 1: Base (dependencies)
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Development
FROM base AS development

# Install dev dependencies
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy source code
COPY . .

# Run as non-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 3: Testing
FROM development AS testing

# Run tests
RUN pytest --cov=app --cov-fail-under=100

# Stage 4: Production
FROM base AS production

# Copy only necessary files
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/

# Run as non-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/admin/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.9'

services:
  # PostgreSQL database
  postgres:
    image: postgres:16-alpine
    container_name: content-creator-db
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
      POSTGRES_DB: ${DB_NAME:-content_creator}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend

  # Redis cache/queue
  redis:
    image: redis:7-alpine
    container_name: content-creator-cache
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - backend

  # FastAPI application
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    container_name: content-creator-api
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-postgres}:${DB_PASSWORD:-postgres}@postgres:5432/${DB_NAME:-content_creator}
      REDIS_URL: redis://redis:6379/0
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Celery worker
  worker:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    container_name: content-creator-worker
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-postgres}:${DB_PASSWORD:-postgres}@postgres:5432/${DB_NAME:-content_creator}
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    volumes:
      - .:/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - backend
    command: celery -A app.tasks.celery_app worker --loglevel=info

  # Celery beat (scheduler)
  beat:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    container_name: content-creator-beat
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-postgres}:${DB_PASSWORD:-postgres}@postgres:5432/${DB_NAME:-content_creator}
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    volumes:
      - .:/app
    depends_on:
      - redis
    networks:
      - backend
    command: celery -A app.tasks.celery_app beat --loglevel=info

  # Flower (Celery monitoring)
  flower:
    build:
      context: .
      dockerfile: Dockerfile
      target: development
    container_name: content-creator-flower
    environment:
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    ports:
      - "5555:5555"
    depends_on:
      - redis
    networks:
      - backend
    command: celery -A app.tasks.celery_app flower --port=5555

volumes:
  postgres_data:
  redis_data:

networks:
  backend:
    driver: bridge
```

---

## 📋 Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

**Goals**: Set up infrastructure, database, basic API

**Tasks**:
1. ✅ Project structure setup
   - Initialize FastAPI project
   - Create directory structure (app/, tests/, alembic/)
   - Set up configuration management (pydantic-settings)

2. ✅ Database setup
   - Install PostgreSQL 16
   - Create initial schema (topics, documents, collections)
   - Set up Alembic migrations
   - Create SQLAlchemy 2.0 models (async)

3. ✅ Basic API skeleton
   - FastAPI app with CORS middleware
   - Health check endpoint
   - Dependency injection setup
   - Error handling middleware

4. ✅ Testing infrastructure
   - pytest configuration
   - Test database setup
   - Fixtures for common test data
   - Coverage configuration (100% target)

5. ✅ CI/CD setup
   - GitHub Actions workflow
   - Linting (Ruff)
   - Type checking (mypy --strict)
   - Test execution with coverage

**Deliverables**:
- ✅ Running FastAPI app with `/health` endpoint
- ✅ Postgres database with migrations
- ✅ CI/CD pipeline passing
- ✅ Test coverage >95%

---

### Phase 2: Data Layer (Weeks 3-4)

**Goals**: Implement repositories, database operations

**Tasks**:
1. ✅ Repository pattern
   - BaseRepository (CRUD operations)
   - TopicRepository (with full-text search)
   - DocumentRepository (with deduplication)
   - CollectionRepository (with health tracking)

2. ✅ SQLite → Postgres migration
   - Export existing data
   - Import to Postgres
   - Verify data integrity
   - Update indexes

3. ✅ Redis integration
   - Cache layer for hot data
   - Session storage
   - Rate limiting store

4. ✅ Database testing
   - Integration tests for all repositories
   - Transaction rollback in tests
   - Performance benchmarks

**Deliverables**:
- ✅ All repositories implemented with 100% coverage
- ✅ Data migrated from SQLite to Postgres
- ✅ Redis cache working

---

### Phase 3: Service Layer (Weeks 5-6)

**Goals**: Implement business logic services

**Tasks**:
1. ✅ Topic service
   - CRUD operations
   - Discovery workflows
   - Research orchestration
   - Validation logic

2. ✅ Collection service
   - Feed management
   - Polling logic
   - Health monitoring

3. ✅ Research services
   - CompetitorService (existing agent wrapper)
   - KeywordService (existing agent wrapper)
   - DeepResearchService (gpt-researcher wrapper)

4. ✅ Content service
   - ContentPipeline wrapper
   - Image generation
   - Notion sync

**Deliverables**:
- ✅ All services implemented
- ✅ 100% test coverage
- ✅ Service integration tests passing

---

### Phase 4: API Layer (Weeks 7-8)

**Goals**: Implement REST API endpoints

**Tasks**:
1. ✅ Topics API
   - CRUD endpoints
   - List with pagination
   - Full-text search
   - Research triggers

2. ✅ Collections API
   - Feed management
   - Polling triggers
   - Health endpoints

3. ✅ Documents API
   - List/search endpoints
   - Deduplication API

4. ✅ Admin API
   - Health checks
   - Metrics (Prometheus)
   - Configuration

5. ✅ API documentation
   - OpenAPI/Swagger UI
   - Redoc
   - Example requests

**Deliverables**:
- ✅ All API endpoints implemented
- ✅ 100% test coverage
- ✅ OpenAPI documentation complete

---

### Phase 5: Background Workers (Weeks 9-10)

**Goals**: Implement async task processing

**Tasks**:
1. ✅ Celery setup
   - Redis broker
   - Worker configuration
   - Beat scheduler

2. ✅ Collection tasks
   - RSS polling
   - Reddit monitoring
   - Trends collection

3. ✅ Research tasks
   - Deep research jobs
   - Content synthesis
   - Image generation

4. ✅ Notion sync tasks
   - Bidirectional sync
   - Conflict resolution

**Deliverables**:
- ✅ All workers implemented
- ✅ Task monitoring (Flower)
- ✅ Retry logic working

---

### Phase 6: Deployment (Weeks 11-12)

**Goals**: Production deployment

**Tasks**:
1. ✅ Docker optimization
   - Multi-stage builds
   - Image size <200MB
   - Security scanning

2. ✅ Production configuration
   - Environment variables
   - Secrets management
   - Logging configuration

3. ✅ Monitoring setup
   - Prometheus metrics
   - Grafana dashboards
   - Alerting rules

4. ✅ Documentation
   - API documentation
   - Deployment guide
   - Runbook

**Deliverables**:
- ✅ Production-ready Docker images
- ✅ Monitoring dashboards
- ✅ Complete documentation

---

## 📁 Project Structure (Target)

```
content-creator-api/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # CI/CD pipeline
│       └── deploy.yml             # Deployment workflow
│
├── alembic/                       # Database migrations
│   ├── versions/
│   └── env.py
│
├── app/                           # Main application
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   │
│   ├── api/                       # API layer
│   │   ├── __init__.py
│   │   ├── dependencies.py        # Dependency injection
│   │   ├── errors.py              # Error handlers
│   │   │
│   │   ├── v1/                    # API v1
│   │   │   ├── __init__.py
│   │   │   ├── router.py          # Main router
│   │   │   ├── topics.py          # Topics endpoints
│   │   │   ├── collections.py     # Collections endpoints
│   │   │   ├── documents.py       # Documents endpoints
│   │   │   ├── research.py        # Research endpoints
│   │   │   └── admin.py           # Admin endpoints
│   │   │
│   │   └── models/                # Request/response models
│   │       ├── __init__.py
│   │       ├── topic.py           # Topic API models
│   │       ├── collection.py      # Collection API models
│   │       └── common.py          # Shared models
│   │
│   ├── core/                      # Core configuration
│   │   ├── __init__.py
│   │   ├── config.py              # App settings (Pydantic)
│   │   ├── security.py            # Auth/security
│   │   └── logging.py             # Structured logging
│   │
│   ├── db/                        # Database layer
│   │   ├── __init__.py
│   │   ├── session.py             # Async session factory
│   │   ├── models/                # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Base model
│   │   │   ├── topic.py           # Topic model
│   │   │   ├── document.py        # Document model
│   │   │   └── collection.py      # Collection model
│   │   │
│   │   └── repositories/          # Repository pattern
│   │       ├── __init__.py
│   │       ├── base.py            # BaseRepository
│   │       ├── topic.py           # TopicRepository
│   │       ├── document.py        # DocumentRepository
│   │       └── collection.py      # CollectionRepository
│   │
│   ├── services/                  # Business logic
│   │   ├── __init__.py
│   │   ├── topic.py               # TopicService
│   │   ├── collection.py          # CollectionService
│   │   ├── research.py            # ResearchService
│   │   └── content.py             # ContentService
│   │
│   ├── tasks/                     # Background tasks (Celery)
│   │   ├── __init__.py
│   │   ├── celery_app.py          # Celery configuration
│   │   ├── collection.py          # Collection tasks
│   │   ├── research.py            # Research tasks
│   │   └── notion.py              # Notion sync tasks
│   │
│   └── utils/                     # Utilities
│       ├── __init__.py
│       ├── cache.py               # Redis cache helpers
│       └── validators.py          # Custom validators
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   │
│   ├── unit/                      # Unit tests (80%)
│   │   ├── api/
│   │   ├── services/
│   │   └── utils/
│   │
│   ├── integration/               # Integration tests (15%)
│   │   ├── repositories/
│   │   └── external/
│   │
│   └── e2e/                       # E2E tests (5%)
│       └── test_topic_workflow.py
│
├── migrations/                    # SQL migrations
│   └── init.sql
│
├── docker/                        # Docker configs
│   ├── Dockerfile.dev
│   └── Dockerfile.prod
│
├── .env.example                   # Environment template
├── .gitignore
├── .pre-commit-config.yaml
├── alembic.ini                    # Alembic config
├── docker-compose.yml             # Local development
├── pyproject.toml                 # Project metadata
├── pytest.ini                     # Pytest config
├── README.md
├── requirements.txt               # Production deps
└── requirements-dev.txt           # Dev deps
```

---

## 🚀 VPS Deployment Architecture

### Deployment Stack

**Domain**: `übergabeprotokoll24.de`

**Environments**:
- **Local**: Docker Compose (development with hot reload)
- **Staging**: `staging.übergabeprotokoll24.de` (VPS subdomain)
- **Production**: `api.übergabeprotokoll24.de` (VPS main API endpoint)

### VPS Setup

```
VPS (Docker + Caddy)
├── Caddy (Reverse Proxy + SSL)
│   ├── Auto SSL via Let's Encrypt
│   ├── HTTP/2 enabled
│   └── Auto redirect HTTP → HTTPS
│
├── FastAPI (×2-4 instances)
│   └── Load balanced via Caddy
│
├── PostgreSQL 16
│   └── Persistent volume
│
├── Redis 7
│   ├── Cache
│   └── Huey queue backend
│
└── Huey Workers (×2)
    └── Background tasks
```

### Caddyfile Configuration

```caddy
# /etc/caddy/Caddyfile

# Staging environment
staging.übergabeprotokoll24.de {
    reverse_proxy api-staging:8000 {
        lb_policy round_robin
        health_uri /api/v1/admin/health
        health_interval 10s
        health_timeout 5s
    }

    # CORS headers
    header Access-Control-Allow-Origin *
    header Access-Control-Allow-Methods "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    header Access-Control-Allow-Headers "Content-Type, Authorization"

    # Logging
    log {
        output file /var/log/caddy/staging.log
        format json
    }
}

# Production environment
api.übergabeprotokoll24.de {
    reverse_proxy api-prod-1:8000 api-prod-2:8000 {
        lb_policy round_robin
        health_uri /api/v1/admin/health
        health_interval 10s
        health_timeout 5s
    }

    # Rate limiting (optional - can add Caddy module)
    # @ratelimit {
    #     path /api/v1/*
    # }
    # rate_limit @ratelimit {
    #     zone api_zone 10m
    #     rate 100r/m
    # }

    # Security headers
    header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
    header X-Content-Type-Options "nosniff"
    header X-Frame-Options "DENY"
    header X-XSS-Protection "1; mode=block"

    # Logging
    log {
        output file /var/log/caddy/production.log
        format json
    }
}
```

### Docker Compose (Production - VPS)

```yaml
# docker-compose.production.yml
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    container_name: postgres-prod
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: content_creator_prod
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: redis-prod
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - backend
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api-prod-1:
    image: ghcr.io/fhalamzie/content-creator:latest
    container_name: api-prod-1
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/content_creator_prod
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: production
      LOG_LEVEL: INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

  api-prod-2:
    image: ghcr.io/fhalamzie/content-creator:latest
    container_name: api-prod-2
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/content_creator_prod
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: production
      LOG_LEVEL: INFO
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

  worker-1:
    image: ghcr.io/fhalamzie/content-creator:latest
    container_name: worker-prod-1
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/content_creator_prod
      REDIS_URL: redis://redis:6379/0
      HUEY_QUEUE_NAME: content_creator_tasks
      ENVIRONMENT: production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - backend
    command: huey_consumer app.tasks.huey_tasks.huey -w 4

  worker-2:
    image: ghcr.io/fhalamzie/content-creator:latest
    container_name: worker-prod-2
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/content_creator_prod
      REDIS_URL: redis://redis:6379/0
      HUEY_QUEUE_NAME: content_creator_tasks
      ENVIRONMENT: production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - backend
    command: huey_consumer app.tasks.huey_tasks.huey -w 4

  caddy:
    image: caddy:2-alpine
    container_name: caddy-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
      - ./logs:/var/log/caddy
    restart: unless-stopped
    networks:
      - backend

volumes:
  postgres_data:
  redis_data:
  caddy_data:
  caddy_config:

networks:
  backend:
    driver: bridge
```

### GitHub Actions Deployment Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy to VPS

on:
  push:
    branches:
      - main       # Production
      - develop    # Staging

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          target: production

  deploy-staging:
    needs: build-and-push
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'

    steps:
      - name: Deploy to staging VPS
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/content-creator/staging
            docker-compose -f docker-compose.staging.yml pull
            docker-compose -f docker-compose.staging.yml up -d
            docker-compose -f docker-compose.staging.yml logs --tail=100

  deploy-production:
    needs: build-and-push
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://api.übergabeprotokoll24.de

    steps:
      - name: Deploy to production VPS
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/content-creator/production
            docker-compose -f docker-compose.production.yml pull
            docker-compose -f docker-compose.production.yml up -d --no-deps --build api-prod-1
            sleep 10
            docker-compose -f docker-compose.production.yml up -d --no-deps --build api-prod-2
            docker-compose -f docker-compose.production.yml logs --tail=100
```

### VPS Initial Setup (One-Time)

```bash
# SSH to VPS
ssh user@your-vps-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create directories
sudo mkdir -p /opt/content-creator/{staging,production}
sudo chown -R $USER:$USER /opt/content-creator

# Install Caddy (if not using Docker version)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Set up firewall
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# Clone repository (for compose files)
cd /opt/content-creator/production
git clone https://github.com/fhalamzie/content-creator.git .

# Set up environment variables
cp .env.example .env.production
nano .env.production  # Add secrets

# First deployment
docker-compose -f docker-compose.production.yml up -d
```

### Deployment Commands

```bash
# Deploy to staging (manual)
ssh user@vps
cd /opt/content-creator/staging
git pull origin develop
docker-compose -f docker-compose.staging.yml pull
docker-compose -f docker-compose.staging.yml up -d

# Deploy to production (manual)
ssh user@vps
cd /opt/content-creator/production
git pull origin main
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d --no-deps --build api-prod-1
sleep 10  # Wait for first instance
docker-compose -f docker-compose.production.yml up -d --no-deps --build api-prod-2

# View logs
docker-compose logs -f api-prod-1

# Rollback
docker-compose -f docker-compose.production.yml up -d api-prod-1:previous-tag
```

---

## ✅ Success Criteria

### Technical

- [ ] **95%+ test coverage** - All code covered by tests (100% on critical paths)
- [ ] **100% type safety** - mypy --strict passing
- [ ] **Zero security vulnerabilities** - Trivy + Bandit clean
- [ ] **API response time <100ms** - p95 latency
- [ ] **Database queries <50ms** - p95 query time
- [ ] **CI/CD pipeline <5min** - Fast feedback loop

### Functional

- [ ] **All existing features working** - No regressions
- [ ] **API documentation complete** - OpenAPI + examples
- [ ] **Deployment automated** - One-command deploy
- [ ] **Monitoring in place** - Metrics + alerts
- [ ] **VPS deployment working** - Automated CI/CD pipeline

---

## 🎯 Next Steps

### Phase 1: Foundation (Week 1-2)

1. **Set up project structure**
   - Create FastAPI project skeleton
   - Set up Alembic for migrations
   - Configure pytest with 95%+ coverage target

2. **Design and implement normalized Postgres schema**
   - Topics, Citations, Keywords, Competitors, Content Gaps, Supporting Images
   - Documents, Collections tables
   - Full-text search with tsvector
   - Write Alembic migrations

3. **SQLite → Postgres migration scripts**
   - Export script
   - Import script with data transformation
   - Validation script

4. **Basic FastAPI skeleton**
   - Health check endpoint
   - Database connection (async SQLAlchemy)
   - Redis connection
   - Error handling middleware

5. **CI/CD setup**
   - GitHub Actions for tests
   - Ruff + mypy --strict
   - Coverage enforcement (95%+)

**Deliverable**: Working API with health endpoint, Postgres connected, CI passing

---

## 📋 Implementation Checklist (Phase 1)

- [ ] Create `content-creator-api/` directory structure
- [ ] Initialize FastAPI app (`app/main.py`)
- [ ] Set up `pyproject.toml` with dependencies
- [ ] Configure Alembic (`alembic init`)
- [ ] Write normalized schema migrations
- [ ] Create SQLAlchemy models (async)
- [ ] Write SQLite export script
- [ ] Write Postgres import script
- [ ] Configure pytest with async support
- [ ] Set up GitHub Actions CI workflow
- [ ] Add mypy strict configuration
- [ ] Create Docker Compose for local dev
- [ ] Document setup in README

**Ready to start?** Let me know and we'll begin with Phase 1!
