# Phase 0: Collectors Component Deep Review
## FastAPI Migration Readiness Assessment

**Review Date:** 2025-11-23
**Reviewers:** Claude (Sonnet 4.5)
**Scope:** Complete analysis of `/home/user/content-creator/src/collectors/` for FastAPI + Huey migration
**Status:** ✅ COMPLETE

---

## Executive Summary

### Overview
The collectors component consists of **6 data ingestion modules** responsible for gathering content from diverse sources (RSS, Reddit, Google Trends, Autocomplete, News APIs, and Feed Discovery). All collectors follow a consistent pattern using the unified `Document` model and share common dependencies (deduplicator, database manager, market config).

### Critical Finding: Mixed Sync/Async Architecture
- **1 collector is already async** (TheNewsAPICollector)
- **5 collectors are fully synchronous** with blocking I/O
- **All collectors use time.sleep()** for rate limiting (blocking)
- **Migration complexity: MEDIUM-HIGH** due to deep sync dependencies

### Data Ingestion Scale
- **Target:** 500 feeds/day across all collectors
- **Storage:** SQLite (WAL mode, optimized for single-writer)
- **Deduplication:** MinHash/LSH with <5% duplicate rate target
- **Test Coverage:** 139 test functions, ~4,040 lines of test code

---

## 1. Collector Inventory & Architecture Analysis

### 1.1 RSSCollector (`rss_collector.py`)
**Lines:** 621 | **Status:** ❌ Fully Synchronous | **Priority:** 🔴 HIGH

#### Architecture
```python
class RSSCollector:
    """RSS/Atom feed collector with content extraction"""

    # Dependencies
    - feedparser (RSS parsing) - SYNC
    - trafilatura (content extraction) - BLOCKING I/O
    - time.sleep() for rate limiting - BLOCKING
```

#### Data Flow
1. **Input:** Feed URL → feedparser.parse()
2. **Conditional GET:** ETag/Last-Modified headers (bandwidth optimization)
3. **Content Extraction:** trafilatura.fetch_url() → trafilatura.extract() (BLOCKING)
4. **Output:** List[Document] with full-text content

#### External Dependencies
- **RSS/Atom feeds** (no API keys required)
- **HTTP requests** via feedparser (sync, no timeout config exposed)
- **trafilatura** fetches article HTML (blocking, 30s timeout default)

#### Rate Limiting
```python
# Per-host rate limiting: 2.0 req/sec default
def _apply_rate_limit(self, feed_url: str):
    # ... calculate sleep time ...
    time.sleep(sleep_time)  # ❌ BLOCKING
```

#### Error Handling
- ✅ **Feed health tracking** (consecutive failures, adaptive polling)
- ✅ **Graceful degradation** (malformed feeds, network errors)
- ✅ **Statistics** (feeds collected, failures, duplicates skipped)
- ⚠️ **No circuit breaker** for persistently failing feeds

#### Async Conversion Needs
- **CRITICAL:** Replace `trafilatura.fetch_url()` with async HTTP client
- **CRITICAL:** Replace `time.sleep()` with `asyncio.sleep()`
- **MEDIUM:** Make `feedparser.parse()` async-compatible (CPU-bound, use executor)
- **LOW:** Cache operations are file-based (use aiofiles or keep sync)

---

### 1.2 RedditCollector (`reddit_collector.py`)
**Lines:** 524 | **Status:** ❌ Fully Synchronous | **Priority:** 🟡 MEDIUM

#### Architecture
```python
class RedditCollector:
    """Reddit community content collector via PRAW"""

    # Dependencies
    - PRAW (official Reddit API) - SYNC only
    - time.sleep() for rate limiting - BLOCKING
```

#### Data Flow
1. **Authentication:** PRAW with client_id/secret from .env
2. **Collection:** subreddit.hot/new/top/rising (lazy generators)
3. **Optional:** Comment extraction (configurable depth)
4. **Output:** List[Document] with post + comments

#### External Dependencies
- **Reddit API** (60 req/min rate limit, enforced by Reddit)
- **API Keys:** REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET (from .env)
- **PRAW:** No official async support (sync only)

#### Rate Limiting
```python
# Reddit API: 60 req/min default
def _apply_rate_limit(self):
    # ... calculate sleep time ...
    time.sleep(sleep_time)  # ❌ BLOCKING
```

#### Error Handling
- ✅ **Subreddit health tracking** (forbidden, not found, banned)
- ✅ **Graceful error handling** (deleted accounts, removed comments)
- ✅ **Quality filtering** (min score, min content length)

#### Async Conversion Needs
- **CRITICAL:** PRAW has NO async version → Must use `asyncio.to_thread()` or `run_in_executor()`
- **CRITICAL:** Replace `time.sleep()` with `asyncio.sleep()`
- **ALTERNATIVE:** Consider asyncpraw (unofficial, less maintained) or keep PRAW in executor

#### Background Task Suitability
- ✅ **Perfect for Huey tasks** (long-running, rate-limited)
- ✅ **Schedule:** Every 4-6 hours per subreddit
- ✅ **Retry:** 3 attempts with exponential backoff

---

### 1.3 TrendsCollector (`trends_collector.py`)
**Lines:** 799 | **Status:** ⚠️ Hybrid (Gemini API) | **Priority:** 🟡 MEDIUM

#### Architecture
```python
class TrendsCollector:
    """Google Trends via Gemini API (Nov 2025 migration)"""

    # Dependencies
    - GeminiAgent (may be async/sync) - NEEDS VERIFICATION
    - In-memory + disk caching (JSON files) - SYNC I/O
```

#### Data Flow
1. **Trending Searches:** Gemini API with web grounding → structured JSON
2. **Related Queries:** Gemini API → keyword expansion
3. **Interest Over Time:** Gemini API → trend analysis
4. **Output:** List[Document] with trend metadata

#### External Dependencies
- **Gemini API** (1,500 grounded queries/day FREE tier)
- **API Key:** GEMINI_API_KEY (from .env)
- **Response Schema:** Pydantic-validated structured output

#### Caching Strategy
- ✅ **Trending searches:** 1 hour TTL (in-memory + disk)
- ✅ **Related queries:** 24 hour TTL
- ✅ **Interest over time:** 24 hour TTL
- ⚠️ **Disk I/O:** JSON file operations (sync, could be async with aiofiles)

#### Error Handling
- ✅ **Query health tracking** (consecutive failures)
- ✅ **Graceful degradation** (Gemini API errors)
- ⚠️ **No circuit breaker** for API quota exhaustion

#### Async Conversion Needs
- **CRITICAL:** Verify if GeminiAgent is async (check agent implementation)
- **MEDIUM:** Replace disk cache I/O with aiofiles
- **LOW:** In-memory cache is already async-safe (dict operations)

---

### 1.4 AutocompleteCollector (`autocomplete_collector.py`)
**Lines:** 483 | **Status:** ⚠️ httpx (sync mode) | **Priority:** 🟢 LOW

#### Architecture
```python
class AutocompleteCollector:
    """Google Autocomplete for keyword expansion"""

    # Dependencies
    - httpx (SYNC mode currently) - ✅ Async-ready!
    - time.sleep() for rate limiting - BLOCKING
```

#### Data Flow
1. **Expansion Types:** Questions (default), Alphabet, Prepositions
2. **API Call:** httpx.get() to Google Autocomplete API
3. **Caching:** 30-day TTL (in-memory + disk JSON)
4. **Output:** List[Document] with autocomplete suggestions

#### External Dependencies
- **Google Autocomplete API** (no auth, 10 req/sec lenient limit)
- **No API key required**

#### Rate Limiting
```python
# 10 req/sec default (Google is lenient)
def _enforce_rate_limit(self):
    # ... calculate sleep time ...
    time.sleep(sleep_time)  # ❌ BLOCKING
```

#### Async Conversion Needs
- **EASY:** Replace `httpx.get()` with `httpx.AsyncClient()`
- **EASY:** Replace `time.sleep()` with `asyncio.sleep()`
- **MEDIUM:** Make cache I/O async (aiofiles)

#### Migration Priority: ✅ EASY WIN
This collector is the **easiest to convert** to async. Use as reference implementation.

---

### 1.5 FeedDiscoveryCollector (`feed_discovery.py`)
**Lines:** 595 | **Status:** ❌ Fully Synchronous | **Priority:** 🟡 MEDIUM

#### Architecture
```python
class FeedDiscovery:
    """2-Stage intelligent feed discovery"""

    # Dependencies
    - subprocess (Gemini CLI) - BLOCKING
    - requests (HTTP) - BLOCKING
    - feedfinder2 (RSS detection) - BLOCKING
```

#### Data Flow
1. **Stage 1:** OPML seeds + Gemini CLI keyword expansion
2. **Stage 2:** SerpAPI search → feedfinder2 auto-detection
3. **Output:** List[DiscoveredFeed] with metadata

#### External Dependencies
- **SerpAPI** (100 free/month, 3 req/day circuit breaker enforced)
- **Gemini CLI** (subprocess calls, retry logic 2x)
- **feedfinder2** (HTTP requests to discover feeds)
- **API Key:** SERPAPI_API_KEY (from .env)

#### Circuit Breaker
```python
# Hard limit: 3 SerpAPI requests/day
def _check_daily_limit(self):
    if self._serpapi_requests_today >= self.serpapi_daily_limit:
        raise FeedDiscoveryError("Daily limit reached")
```

#### Error Handling
- ✅ **30-day SERP caching** (avoids duplicate API calls)
- ✅ **Gemini CLI retry** (2 attempts, fallback to basic keywords)
- ✅ **Domain blacklist** (Wikipedia, etc.)
- ✅ **Timeout protection** (feedfinder2 has 15s total timeout)

#### Async Conversion Needs
- **CRITICAL:** Replace `requests` with `httpx.AsyncClient`
- **CRITICAL:** Replace `subprocess.run()` with `asyncio.create_subprocess_exec()`
- **MEDIUM:** Make feedfinder2 async (or run in executor)
- **MEDIUM:** Make cache I/O async

---

### 1.6 TheNewsAPICollector (`thenewsapi_collector.py`)
**Lines:** 390 | **Status:** ✅ ALREADY ASYNC | **Priority:** ✅ REFERENCE

#### Architecture
```python
class TheNewsAPICollector:
    """Real-time news via TheNewsAPI.com - ASYNC!"""

    # Dependencies
    - httpx.AsyncClient - ✅ ALREADY ASYNC
    - No blocking I/O - ✅ CLEAN
```

#### Data Flow
1. **Authentication:** API key from env
2. **API Call:** `async with httpx.AsyncClient()` → `/v1/news/all`
3. **Parsing:** JSON → Document model
4. **Output:** List[Document]

#### External Dependencies
- **TheNewsAPI.com** (100 req/day FREE, 300 articles/request)
- **API Key:** THENEWSAPI_API_KEY (from .env)

#### Error Handling
- ✅ **Graceful degradation** (returns empty list on errors)
- ✅ **Zero silent failures** (all errors logged)
- ⚠️ **No retry logic** (could add with tenacity)

#### Migration Status
**✅ ALREADY COMPATIBLE WITH FASTAPI** - Use as reference for other collectors!

---

## 2. Data Flow Analysis

### 2.1 Unified Data Ingestion Pattern

All collectors follow this pattern:

```python
# 1. Initialize with config, db_manager, deduplicator
collector = Collector(config, db_manager, deduplicator)

# 2. Collect data from source
documents = collector.collect_from_source(params)

# 3. For each item:
#    - Parse to Document model
#    - Check deduplication (URL + content hash)
#    - Return non-duplicates

# 4. Return List[Document]
```

### 2.2 Document Model (Pydantic)

```python
class Document(BaseModel):
    """Universal data model for all sources"""

    # ✅ FastAPI-compatible (Pydantic)
    # ✅ Supports both sync and async operations
    # ✅ Validation built-in
```

**Fields:**
- **Identity:** id, source, source_url
- **Content:** title, content, summary
- **Classification:** language, domain, market, vertical
- **Deduplication:** content_hash, canonical_url
- **Metadata:** published_at, fetched_at, author
- **Enrichment:** entities, keywords (added later)
- **Status:** new → processed → rejected

### 2.3 Data Storage (SQLite)

**Current Implementation:**
```python
class SQLiteManager:
    """Synchronous SQLite operations"""

    # ❌ All operations are SYNC
    # ❌ Uses sqlite3 (blocking)
```

**Migration Needs:**
- **Option 1:** Keep SQLite sync, use `asyncio.to_thread()` for queries
- **Option 2:** Migrate to `aiosqlite` (async SQLite)
- **Option 3:** Migrate to PostgreSQL + asyncpg (production-ready)

**Recommendation:** Start with Option 1 (minimal changes), migrate to Option 3 for production.

### 2.4 Deduplication Flow

```python
class Deduplicator:
    """MinHash/LSH deduplication"""

    # ✅ In-memory operations (async-safe)
    # ❌ No async methods (but easily adaptable)
```

**Deduplication Steps:**
1. **Canonical URL check** (fast, O(1) set lookup)
2. **Content similarity** (MinHash/LSH query)
3. **Add to index** if unique

**Migration:** Minimal changes needed (in-memory operations are already thread-safe).

---

## 3. Async Conversion Readiness Matrix

| Collector | Current State | HTTP Client | Blocking Ops | Conversion Complexity | Priority |
|-----------|--------------|-------------|--------------|----------------------|----------|
| **TheNewsAPICollector** | ✅ ASYNC | httpx (async) | None | ✅ DONE | Reference |
| **AutocompleteCollector** | ⚠️ Sync | httpx (sync) | time.sleep, disk I/O | 🟢 EASY | High |
| **TrendsCollector** | ⚠️ Hybrid | Gemini API | Disk I/O | 🟡 MEDIUM | Medium |
| **FeedDiscoveryCollector** | ❌ Sync | requests | subprocess, requests, disk I/O | 🟡 MEDIUM | Medium |
| **RSSCollector** | ❌ Sync | feedparser + trafilatura | HTTP, parsing, disk I/O | 🔴 HARD | High |
| **RedditCollector** | ❌ Sync | PRAW (sync only) | PRAW calls, time.sleep | 🔴 HARD | Medium |

### 3.1 Blocking I/O Inventory

#### Critical Blocking Operations
1. **time.sleep()** - Found in 3 collectors (RSS, Reddit, Autocomplete)
2. **trafilatura.fetch_url()** - Synchronous HTTP fetch (RSSCollector)
3. **feedparser.parse()** - CPU-bound parsing (RSSCollector)
4. **PRAW API calls** - No async version available (RedditCollector)
5. **subprocess.run()** - Gemini CLI calls (FeedDiscoveryCollector)
6. **requests.get()** - Synchronous HTTP (FeedDiscoveryCollector)

#### Disk I/O Operations
- **JSON cache** (all collectors): read/write feed metadata
- **OPML parsing** (FeedDiscoveryCollector): XML file parsing
- **SQLite queries** (all collectors): database operations

---

## 4. External API Dependencies Catalog

| Service | Collector | Auth Method | Rate Limit | Free Tier | Migration Notes |
|---------|-----------|-------------|------------|-----------|-----------------|
| **RSS Feeds** | RSSCollector | None | Per-host (2 req/sec) | ✅ Unlimited | ETag/Last-Modified optimization |
| **Reddit API** | RedditCollector | OAuth (client_id/secret) | 60 req/min | ✅ Yes | PRAW has no async version |
| **Gemini API** | TrendsCollector | API key | 1,500 grounded/day | ✅ Yes | Check if agent is async |
| **Google Autocomplete** | AutocompleteCollector | None | ~10 req/sec (lenient) | ✅ Yes | No auth required |
| **SerpAPI** | FeedDiscoveryCollector | API key | 100/month | ✅ Yes | Circuit breaker @ 3/day |
| **TheNewsAPI** | TheNewsAPICollector | API key | 100 req/day | ✅ Yes | Already async |

### 4.1 API Key Management
All API keys are loaded from `.env`:
- ✅ REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
- ✅ GEMINI_API_KEY
- ✅ SERPAPI_API_KEY
- ✅ THENEWSAPI_API_KEY

**FastAPI Integration:**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    reddit_client_id: str
    reddit_client_secret: str
    gemini_api_key: str
    serpapi_api_key: str
    thenewsapi_api_key: str

    class Config:
        env_file = ".env"
```

---

## 5. Technical Debt Assessment

### 5.1 Code Quality
- ✅ **No TODO/FIXME markers** found in collector code
- ✅ **Consistent error handling** patterns
- ✅ **Well-documented** (docstrings, type hints)
- ✅ **Statistics tracking** in all collectors

### 5.2 Hardcoded Values

#### Configuration
- ⚠️ **Rate limits:** Hardcoded in constructors (should be in config)
- ⚠️ **Cache TTLs:** Hardcoded (30 days, 1 hour, 24 hours)
- ⚠️ **Timeouts:** Hardcoded (30s, 10s, 15s)

**Recommendation:** Extract to YAML config or environment variables.

#### URLs
- ✅ **Google Autocomplete URL:** Constant (OK)
- ✅ **TheNewsAPI URL:** Constant (OK)
- ✅ **SerpAPI URL:** Constant (OK)

### 5.3 Error Handling Patterns

#### Current State
```python
# Pattern 1: Try/except with logging
try:
    documents = self.collect_from_feed(feed_url)
except CollectorError as e:
    logger.error("collection_failed", error=str(e))
    raise  # or return []

# Pattern 2: Health tracking
def record_failure(self):
    self.consecutive_failures += 1
    if self.consecutive_failures >= max_failures:
        # Skip this source in future runs
```

#### Missing Patterns
- ❌ **No retry logic** (should use `tenacity`)
- ❌ **No circuit breakers** (except FeedDiscoveryCollector)
- ❌ **No timeout enforcement** (some collectors lack timeouts)

**Recommendation:** Add `tenacity` for retries, implement circuit breakers.

### 5.4 Retry Logic Gap

**Current State:**
- FeedDiscoveryCollector: 2 retries for Gemini CLI
- Others: No retry logic

**Needed:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    reraise=True
)
async def collect_with_retry(self, ...):
    ...
```

---

## 6. Test Coverage Analysis

### 6.1 Test Statistics
- **Total test files:** 8
- **Total test functions:** 139
- **Total test code:** ~4,040 lines
- **Coverage types:** Unit, E2E, Integration

### 6.2 Test Breakdown by Collector

| Collector | Unit Tests | E2E Tests | Integration Tests | Test File Size |
|-----------|------------|-----------|-------------------|----------------|
| RSSCollector | ✅ Yes | ❌ No | ✅ Yes | 19K |
| RedditCollector | ✅ Yes | ❌ No | ✅ Yes | 18K |
| TrendsCollector | ✅ Yes | ✅ Yes | ❌ No | 20K + 12K |
| AutocompleteCollector | ✅ Yes | ✅ Yes | ❌ No | 20K + 12K |
| FeedDiscoveryCollector | ✅ Yes | ❌ No | ❌ No | 17K |
| TheNewsAPICollector | ✅ Yes | ❌ No | ❌ No | 18K |

### 6.3 Test Coverage Gaps

#### Missing Integration Tests
- ❌ **TrendsCollector:** No integration tests (only unit + E2E)
- ❌ **AutocompleteCollector:** No integration tests (only unit + E2E)
- ❌ **FeedDiscoveryCollector:** No E2E or integration tests
- ❌ **TheNewsAPICollector:** No E2E or integration tests

#### Missing Async Tests
- ❌ **No async test patterns** (except TheNewsAPICollector tests use pytest-asyncio)
- ❌ **No async rate limiting tests**
- ❌ **No async deduplication tests**

**Recommendation:**
1. Add `pytest-asyncio` to all collector tests
2. Add E2E tests for FeedDiscoveryCollector and TheNewsAPICollector
3. Add integration tests for Trends and Autocomplete collectors

### 6.4 Mocking Strategies

#### Current Patterns
```python
# Mock external HTTP calls
@patch('httpx.get')
def test_collect(mock_get):
    mock_get.return_value.json.return_value = {...}
    ...

# Mock PRAW
@patch('praw.Reddit')
def test_reddit_collect(mock_reddit):
    ...

# Mock feedparser
@patch('feedparser.parse')
def test_rss_collect(mock_parse):
    ...
```

✅ **Good:** External dependencies are mocked
⚠️ **Warning:** No async mock patterns yet

---

## 7. Background Task Design (Huey Integration)

### 7.1 Current Huey Setup

```python
# src/tasks/huey_tasks.py
from huey import SqliteHuey, crontab

huey = SqliteHuey(filename="tasks.db")

@huey.task(retries=3, retry_delay=60)
def collect_all_sources(config_path: str) -> Dict[str, int]:
    """Background task for all collectors"""
    ...

@huey.periodic_task(crontab(hour=2, minute=0))
def daily_collection():
    """Scheduled daily collection at 2 AM"""
    ...
```

**Issues:**
- ❌ **Calls sync collectors** (blocks Huey worker)
- ❌ **No per-collector tasks** (all-or-nothing)
- ❌ **No async support** (Huey 2.5.0 is sync-only)

### 7.2 Recommended Task Design

#### Per-Collector Tasks
```python
@huey.task(retries=3, retry_delay=60)
async def collect_rss_feeds(feed_urls: List[str]) -> Dict[str, int]:
    """Collect from RSS feeds"""
    collector = RSSCollector(...)
    return await collector.collect_from_feeds_async(feed_urls)

@huey.task(retries=3, retry_delay=120)
async def collect_reddit_posts(subreddits: List[str]) -> Dict[str, int]:
    """Collect from Reddit"""
    collector = RedditCollector(...)
    return await collector.collect_from_subreddits_async(subreddits)

# ... etc for each collector
```

#### Scheduling Recommendations

| Collector | Schedule | Reasoning |
|-----------|----------|-----------|
| RSSCollector | Every 4 hours | Most feeds update 2-6 times/day |
| RedditCollector | Every 6 hours | Rate limit conservation |
| TrendsCollector | Daily at 8 AM | Trending topics change daily |
| AutocompleteCollector | Weekly | Autocomplete stable, low churn |
| FeedDiscoveryCollector | Weekly | Expensive (SerpAPI quota) |
| TheNewsAPICollector | Every 2 hours | Real-time news |

### 7.3 Error Recovery Strategy

#### Current DLQ (Dead Letter Queue)
```python
def log_to_dlq(task_name: str, error: str, timestamp: datetime):
    """Log failed tasks to SQLite DLQ"""
    ...
```

✅ **Good:** Basic DLQ implemented
⚠️ **Missing:**
- No retry from DLQ
- No alerting on DLQ entries
- No automatic recovery

#### Recommended Improvements
```python
# Add retry from DLQ
@huey.task()
async def retry_from_dlq(dlq_id: int):
    """Retry failed task from DLQ"""
    entry = get_dlq_entry(dlq_id)
    # Re-execute original task
    ...

# Add monitoring task
@huey.periodic_task(crontab(hour='*/6'))
async def check_dlq_health():
    """Alert if DLQ has too many entries"""
    count = get_dlq_count()
    if count > 50:
        send_alert(f"DLQ has {count} failed tasks")
```

### 7.4 Monitoring Needs

#### Metrics to Track
1. **Collection metrics:**
   - Documents collected per collector
   - Collection duration
   - Failure rate
   - Duplicate rate

2. **API metrics:**
   - API calls per service
   - Rate limit remaining
   - Quota usage (SerpAPI, TheNewsAPI)

3. **Queue metrics:**
   - Pending tasks
   - DLQ size
   - Task duration distribution

#### Implementation
```python
# Add to each collector
from prometheus_client import Counter, Histogram

docs_collected = Counter('collector_documents_total', 'Documents collected', ['source'])
collection_duration = Histogram('collector_duration_seconds', 'Collection duration', ['source'])

async def collect_with_metrics(self):
    with collection_duration.labels(source=self.source).time():
        docs = await self.collect()
        docs_collected.labels(source=self.source).inc(len(docs))
        return docs
```

---

## 8. API Design Implications (FastAPI)

### 8.1 Recommended Endpoint Structure

```python
# FastAPI endpoints for collectors

# 1. Manual trigger endpoints
@app.post("/api/v1/collections/{source}/trigger")
async def trigger_collection(
    source: CollectorType,
    config: Optional[CollectionConfig] = None
) -> CollectionResponse:
    """Manually trigger collection from a specific source"""
    ...

# 2. Status endpoints
@app.get("/api/v1/collections/{collection_id}/status")
async def get_collection_status(collection_id: str) -> CollectionStatus:
    """Get status of a running/completed collection"""
    ...

# 3. Health endpoints
@app.get("/api/v1/collectors/{source}/health")
async def get_collector_health(source: CollectorType) -> HealthResponse:
    """Get health metrics for a collector (failure rate, last success, etc.)"""
    ...

# 4. Configuration endpoints
@app.get("/api/v1/collectors/{source}/config")
async def get_collector_config(source: CollectorType) -> CollectorConfig:
    """Get current configuration for a collector"""
    ...

@app.put("/api/v1/collectors/{source}/config")
async def update_collector_config(
    source: CollectorType,
    config: CollectorConfig
) -> CollectorConfig:
    """Update collector configuration"""
    ...
```

### 8.2 Real-time vs Batch Collection

#### Real-time (Webhook-style)
```python
# Use for: TheNewsAPICollector, AutocompleteCollector
@app.post("/api/v1/collections/news/poll")
async def poll_latest_news(query: str, limit: int = 50):
    """Fetch latest news in real-time"""
    collector = TheNewsAPICollector(...)
    return await collector.collect(query, limit=limit)
```

#### Batch (Background Task)
```python
# Use for: RSSCollector, RedditCollector, TrendsCollector
@app.post("/api/v1/collections/rss/schedule")
async def schedule_rss_collection(feed_urls: List[str]):
    """Schedule RSS collection as background task"""
    task = collect_rss_feeds.schedule(args=(feed_urls,))
    return {"task_id": task.id, "status": "scheduled"}
```

### 8.3 WebSocket Support (Optional)

```python
# For real-time progress updates
@app.websocket("/ws/collections/{collection_id}")
async def collection_progress(websocket: WebSocket, collection_id: str):
    """Stream collection progress in real-time"""
    await websocket.accept()

    async for event in collector.collect_with_progress():
        await websocket.send_json({
            "type": event.type,
            "documents_collected": event.count,
            "progress": event.progress
        })
```

### 8.4 API Response Models

```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class CollectionResponse(BaseModel):
    """Response from collection trigger"""
    collection_id: str
    source: str
    status: str  # "running", "completed", "failed"
    documents_collected: int
    started_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]

class CollectionStatus(BaseModel):
    """Status of a collection"""
    collection_id: str
    status: str
    progress: float  # 0.0 - 1.0
    documents_collected: int
    errors: List[str]

class HealthResponse(BaseModel):
    """Collector health metrics"""
    source: str
    is_healthy: bool
    success_rate: float
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    consecutive_failures: int
```

---

## 9. Async Readiness Assessment

### 9.1 Conversion Priority Matrix

#### Tier 1: Quick Wins (Week 1)
1. **TheNewsAPICollector** ✅ DONE (already async)
2. **AutocompleteCollector** 🟢 EASY
   - Replace `httpx.get()` → `httpx.AsyncClient()`
   - Replace `time.sleep()` → `asyncio.sleep()`
   - Estimated effort: 2-3 hours

#### Tier 2: Medium Effort (Week 2)
3. **TrendsCollector** 🟡 MEDIUM
   - Verify GeminiAgent async support
   - Make cache I/O async (aiofiles)
   - Estimated effort: 4-6 hours

4. **FeedDiscoveryCollector** 🟡 MEDIUM
   - Replace `requests` → `httpx.AsyncClient()`
   - Make `subprocess.run()` async
   - Make feedfinder2 async or use executor
   - Estimated effort: 6-8 hours

#### Tier 3: Complex (Week 3-4)
5. **RSSCollector** 🔴 HARD
   - Replace trafilatura with async HTTP client
   - Make feedparser async (use executor for CPU-bound parsing)
   - Estimated effort: 8-12 hours

6. **RedditCollector** 🔴 HARD
   - Wrap PRAW in `asyncio.to_thread()` or `run_in_executor()`
   - Consider asyncpraw (unofficial, risky)
   - Estimated effort: 8-10 hours

### 9.2 Shared Infrastructure Changes

#### Database Layer
```python
# Option 1: Keep SQLite sync, use to_thread
async def save_document(self, doc: Document):
    await asyncio.to_thread(self.db_manager.save, doc)

# Option 2: Use aiosqlite
import aiosqlite

async def save_document(self, doc: Document):
    async with aiosqlite.connect(self.db_path) as db:
        await db.execute("INSERT INTO documents (...) VALUES (...)", ...)
        await db.commit()
```

**Recommendation:** Start with Option 1, migrate to PostgreSQL + asyncpg later.

#### Deduplicator
```python
# Current (sync)
def is_duplicate(self, doc: Document) -> bool:
    ...

# Async version (minimal changes)
async def is_duplicate_async(self, doc: Document) -> bool:
    # In-memory operations are already async-safe
    return self.is_duplicate(doc)
```

**Recommendation:** Deduplicator changes are minimal (in-memory operations).

---

## 10. Refactoring Priority List

### 🔴 HIGH Priority (Critical for Migration)

1. **Convert AutocompleteCollector to async** (Quick win, reference implementation)
   - Effort: 2-3 hours
   - Blockers: None
   - Dependencies: None

2. **Create async base class for collectors**
   ```python
   class AsyncCollector(ABC):
       """Base class for async collectors"""

       @abstractmethod
       async def collect(self, **kwargs) -> List[Document]:
           """Collect documents from source"""
           pass

       async def collect_with_metrics(self, **kwargs):
           """Collect with automatic metrics tracking"""
           pass
   ```
   - Effort: 4 hours
   - Blockers: None

3. **Add retry logic with tenacity**
   - Effort: 2 hours
   - Blockers: None
   - Benefits: All collectors

4. **Convert RSSCollector to async**
   - Effort: 8-12 hours
   - Blockers: trafilatura replacement
   - Critical: Highest volume collector

### 🟡 MEDIUM Priority (Important but not blocking)

5. **Convert TrendsCollector to async**
   - Effort: 4-6 hours
   - Blockers: Verify GeminiAgent

6. **Convert FeedDiscoveryCollector to async**
   - Effort: 6-8 hours
   - Blockers: feedfinder2 async

7. **Add circuit breakers to all collectors**
   - Effort: 4 hours
   - Pattern: Use pybreaker library

8. **Extract configuration to YAML/env**
   - Effort: 3 hours
   - Benefits: Easier deployment

### 🟢 LOW Priority (Nice to have)

9. **Convert RedditCollector to async**
   - Effort: 8-10 hours
   - Blockers: PRAW has no async version
   - Alternative: Keep sync, run in executor

10. **Add WebSocket support for real-time updates**
    - Effort: 6 hours
    - Dependencies: FastAPI WebSocket

11. **Migrate SQLite to PostgreSQL**
    - Effort: 12-16 hours
    - Blocker: Need production scale first

12. **Add Prometheus metrics**
    - Effort: 4 hours
    - Dependencies: prometheus_client

---

## 11. External Dependencies Migration Plan

### 11.1 HTTP Client Standardization

**Target:** httpx.AsyncClient for all HTTP operations

| Collector | Current | Target | Migration Complexity |
|-----------|---------|--------|---------------------|
| AutocompleteCollector | httpx (sync) | httpx.AsyncClient | 🟢 Trivial |
| TheNewsAPICollector | httpx.AsyncClient | ✅ DONE | N/A |
| FeedDiscoveryCollector | requests | httpx.AsyncClient | 🟡 Medium |
| RSSCollector | trafilatura (requests) | httpx.AsyncClient | 🔴 Complex |

### 11.2 Async Library Additions

```txt
# Add to requirements-topic-research.txt

# Async HTTP client (already added)
httpx==0.27.0

# Async file I/O
aiofiles==23.2.1

# Async SQLite (optional, for Phase 2)
aiosqlite==0.19.0

# Circuit breaker
pybreaker==1.0.2

# Already present:
# tenacity==8.5.0  ✅
# aiolimiter==1.1.0  ✅
```

### 11.3 Breaking Changes to Monitor

1. **feedparser:** No async version exists
   - Solution: Use `asyncio.to_thread()` for parsing

2. **PRAW:** No official async support
   - Solution: Use `asyncio.to_thread()` or asyncpraw (unofficial)

3. **trafilatura:** Synchronous content extraction
   - Solution: Replace with httpx + custom extraction

---

## 12. Testing Strategy for Async Migration

### 12.1 Test Migration Plan

#### Phase 1: Add Async Test Infrastructure
```python
# conftest.py updates
import pytest
import pytest_asyncio

@pytest_asyncio.fixture
async def async_db_manager():
    """Async database manager for tests"""
    manager = await AsyncSQLiteManager.create(":memory:")
    yield manager
    await manager.close()

@pytest_asyncio.fixture
async def async_deduplicator():
    """Async deduplicator for tests"""
    return Deduplicator()
```

#### Phase 2: Convert Tests per Collector
```python
# Example: test_autocomplete_collector.py

# Old (sync)
def test_collect_suggestions(mock_httpx_get):
    collector = AutocompleteCollector(...)
    docs = collector.collect_suggestions(["PropTech"])
    assert len(docs) > 0

# New (async)
@pytest.mark.asyncio
async def test_collect_suggestions_async(mock_httpx_async_client):
    collector = AsyncAutocompleteCollector(...)
    docs = await collector.collect_suggestions(["PropTech"])
    assert len(docs) > 0
```

#### Phase 3: Parallel Test Running
```bash
# Run both sync and async tests during migration
pytest tests/unit/collectors/test_*_sync.py  # Old sync tests
pytest tests/unit/collectors/test_*_async.py  # New async tests
```

### 12.2 Integration Test Updates

#### Mock External Services
```python
# tests/mocks/async_http_mock.py
import httpx
import respx

@pytest.fixture
def mock_google_autocomplete():
    with respx.mock:
        respx.get("https://suggestqueries.google.com/complete/search").mock(
            return_value=httpx.Response(200, json=["query", ["suggestion1", "suggestion2"]])
        )
        yield
```

---

## 13. Production Readiness Checklist

### 13.1 Pre-Migration
- [ ] ✅ Document current collector behavior
- [ ] ✅ Establish baseline metrics (documents/hour, error rate)
- [ ] ✅ Create rollback plan
- [ ] ⚠️ Add feature flags for gradual rollout

### 13.2 During Migration
- [ ] Convert collectors in priority order (AutocompleteCollector first)
- [ ] Run parallel tests (sync + async)
- [ ] Monitor performance regressions
- [ ] Add async-specific error handling

### 13.3 Post-Migration
- [ ] Validate metrics match baseline
- [ ] Remove sync versions
- [ ] Update documentation
- [ ] Deploy to staging for 1 week soak test
- [ ] Gradual production rollout (10% → 50% → 100%)

---

## 14. Key Recommendations Summary

### Immediate Actions (Week 1)
1. ✅ **Start with AutocompleteCollector** (easiest async conversion)
2. ✅ **Create AsyncCollector base class** (reusable pattern)
3. ✅ **Add tenacity for retries** (all collectors benefit)
4. ✅ **Set up async test infrastructure** (pytest-asyncio, respx)

### Short-term (Weeks 2-4)
5. ✅ **Convert TrendsCollector** (verify GeminiAgent async)
6. ✅ **Convert FeedDiscoveryCollector** (replace requests)
7. ✅ **Convert RSSCollector** (highest priority, most complex)
8. ✅ **Add circuit breakers** (prevent cascade failures)

### Medium-term (Weeks 5-8)
9. ✅ **Convert RedditCollector** (use executor pattern)
10. ✅ **Add Prometheus metrics** (production observability)
11. ✅ **Implement WebSocket updates** (real-time UI)
12. ✅ **Extract config to YAML** (deployment flexibility)

### Long-term (Post-MVP)
13. ⚠️ **Migrate to PostgreSQL** (when >100K docs)
14. ⚠️ **Add async queue** (Huey + Redis or Celery)
15. ⚠️ **Implement caching layer** (Redis for shared state)

---

## 15. Risk Assessment

### 🔴 HIGH Risk

1. **PRAW has no async version**
   - Mitigation: Use `asyncio.to_thread()` wrapper
   - Alternative: asyncpraw (unofficial, less tested)

2. **trafilatura blocking I/O**
   - Mitigation: Replace with httpx + custom extraction
   - Alternative: Run in executor (less efficient)

3. **Database migration complexity**
   - Mitigation: Start with `asyncio.to_thread()`, migrate to asyncpg later
   - Rollback: Keep sync version until async proven stable

### 🟡 MEDIUM Risk

4. **GeminiAgent async status unknown**
   - Mitigation: Verify implementation, add async wrapper if needed

5. **feedfinder2 no async version**
   - Mitigation: Run in executor with timeout protection

6. **Test coverage gaps for async**
   - Mitigation: Add async-specific tests, parallel test running

### 🟢 LOW Risk

7. **httpx migration** (well-documented, proven)
8. **Pydantic models** (already async-compatible)
9. **In-memory deduplication** (no changes needed)

---

## Appendix A: Code Samples

### A.1 Async Collector Base Class

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models.document import Document
from src.utils.logger import get_logger

logger = get_logger(__name__)

class AsyncCollector(ABC):
    """Base class for all async collectors"""

    def __init__(self, config, db_manager, deduplicator):
        self.config = config
        self.db_manager = db_manager
        self.deduplicator = deduplicator

        # Statistics
        self._stats = {
            "total_requests": 0,
            "total_documents": 0,
            "total_failures": 0,
            "total_duplicates": 0
        }

    @abstractmethod
    async def collect(self, **kwargs) -> List[Document]:
        """Collect documents from source (implement in subclass)"""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    async def collect_with_retry(self, **kwargs) -> List[Document]:
        """Collect with automatic retry logic"""
        return await self.collect(**kwargs)

    async def collect_with_metrics(self, **kwargs) -> Dict:
        """Collect with automatic metrics tracking"""
        start_time = datetime.now()

        try:
            documents = await self.collect_with_retry(**kwargs)
            duration = (datetime.now() - start_time).total_seconds()

            # Update stats
            self._stats["total_requests"] += 1
            self._stats["total_documents"] += len(documents)

            logger.info(
                "collection_completed",
                source=self.__class__.__name__,
                documents=len(documents),
                duration=duration
            )

            return {
                "documents": documents,
                "count": len(documents),
                "duration": duration,
                "stats": self.get_statistics()
            }

        except Exception as e:
            self._stats["total_failures"] += 1
            logger.error(
                "collection_failed",
                source=self.__class__.__name__,
                error=str(e)
            )
            raise

    async def _apply_rate_limit_async(self, delay: float):
        """Async rate limiting"""
        await asyncio.sleep(delay)

    def get_statistics(self) -> Dict:
        """Get collection statistics"""
        return self._stats.copy()
```

### A.2 Async AutocompleteCollector

```python
import httpx
import asyncio
from typing import List

class AsyncAutocompleteCollector(AsyncCollector):
    """Async Google Autocomplete collector"""

    AUTOCOMPLETE_URL = "https://suggestqueries.google.com/complete/search"

    def __init__(self, config, db_manager, deduplicator,
                 language: str = "en", rate_limit: float = 10.0):
        super().__init__(config, db_manager, deduplicator)
        self.language = language
        self.rate_limit = rate_limit
        self.last_request_time = None

    async def collect(
        self,
        seed_keywords: List[str],
        expansion_types: List[ExpansionType] = None
    ) -> List[Document]:
        """Collect autocomplete suggestions (async)"""

        if expansion_types is None:
            expansion_types = [ExpansionType.QUESTIONS]

        all_documents = []
        seen_suggestions = set()

        async with httpx.AsyncClient(timeout=10) as client:
            for seed_keyword in seed_keywords:
                for expansion_type in expansion_types:
                    # Fetch suggestions
                    suggestions = await self._fetch_suggestions_async(
                        client, seed_keyword, expansion_type
                    )

                    # Create documents
                    for suggestion in suggestions:
                        if suggestion in seen_suggestions:
                            continue

                        seen_suggestions.add(suggestion)

                        doc = self._create_document(suggestion, seed_keyword, expansion_type)

                        # Check duplicates
                        if await asyncio.to_thread(self.deduplicator.is_duplicate, doc):
                            self._stats["total_duplicates"] += 1
                            continue

                        all_documents.append(doc)
                        await asyncio.to_thread(self.deduplicator.add, doc)

        return all_documents

    async def _fetch_suggestions_async(
        self,
        client: httpx.AsyncClient,
        seed_keyword: str,
        expansion_type: ExpansionType
    ) -> List[str]:
        """Fetch suggestions with async HTTP"""

        # Generate queries based on expansion type
        queries = self._generate_queries(seed_keyword, expansion_type)

        # Fetch in parallel with rate limiting
        suggestions = []

        for query in queries:
            # Enforce rate limit
            await self._enforce_rate_limit_async()

            # Fetch autocomplete
            params = {
                'q': query,
                'client': 'firefox',
                'hl': self.language
            }

            try:
                response = await client.get(self.AUTOCOMPLETE_URL, params=params)

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) >= 2:
                        suggestions.extend(data[1])

            except httpx.HTTPError as e:
                logger.warning("autocomplete_request_failed", query=query, error=str(e))

        return list(set(suggestions))  # Deduplicate

    async def _enforce_rate_limit_async(self):
        """Async rate limiting"""
        if self.last_request_time is not None:
            elapsed = asyncio.get_event_loop().time() - self.last_request_time
            required_delay = 1.0 / self.rate_limit

            if elapsed < required_delay:
                await asyncio.sleep(required_delay - elapsed)

        self.last_request_time = asyncio.get_event_loop().time()
```

### A.3 FastAPI Endpoint Example

```python
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

app = FastAPI()

class CollectorType(str, Enum):
    RSS = "rss"
    REDDIT = "reddit"
    TRENDS = "trends"
    AUTOCOMPLETE = "autocomplete"
    NEWS = "news"

class CollectionRequest(BaseModel):
    sources: Optional[List[str]] = None
    limit: Optional[int] = 50

class CollectionResponse(BaseModel):
    collection_id: str
    status: str
    documents_collected: int
    started_at: str

@app.post("/api/v1/collections/{collector}/trigger", response_model=CollectionResponse)
async def trigger_collection(
    collector: CollectorType,
    request: CollectionRequest,
    background_tasks: BackgroundTasks
):
    """Trigger collection from a specific collector"""

    # Create collector instance
    if collector == CollectorType.AUTOCOMPLETE:
        collector_instance = AsyncAutocompleteCollector(
            config=get_config(),
            db_manager=get_db_manager(),
            deduplicator=get_deduplicator()
        )

        # Collect in background
        task_id = str(uuid.uuid4())
        background_tasks.add_task(
            run_collection,
            task_id,
            collector_instance,
            request.sources or ["PropTech"]
        )

        return CollectionResponse(
            collection_id=task_id,
            status="running",
            documents_collected=0,
            started_at=datetime.now().isoformat()
        )

    # ... handle other collectors

    raise HTTPException(status_code=400, detail=f"Unknown collector: {collector}")

async def run_collection(task_id: str, collector: AsyncCollector, keywords: List[str]):
    """Background task for collection"""
    try:
        result = await collector.collect_with_metrics(seed_keywords=keywords)

        # Save to database
        await save_collection_result(task_id, result)

        logger.info("collection_completed", task_id=task_id, **result)

    except Exception as e:
        logger.error("collection_failed", task_id=task_id, error=str(e))
        await save_collection_error(task_id, str(e))
```

---

## Appendix B: Migration Timeline

### Week 1: Foundation
- [ ] Day 1-2: Set up async test infrastructure
- [ ] Day 3-4: Convert AutocompleteCollector to async
- [ ] Day 5: Add tenacity retry logic to all collectors

### Week 2: Medium Complexity
- [ ] Day 1-2: Verify and convert TrendsCollector
- [ ] Day 3-5: Convert FeedDiscoveryCollector

### Week 3: High Complexity
- [ ] Day 1-3: Convert RSSCollector (trafilatura replacement)
- [ ] Day 4-5: Convert RedditCollector (executor pattern)

### Week 4: Integration
- [ ] Day 1-2: Create FastAPI endpoints
- [ ] Day 3-4: Integrate with Huey tasks
- [ ] Day 5: End-to-end testing

### Week 5-6: Production Readiness
- [ ] Week 5: Staging deployment, soak testing
- [ ] Week 6: Gradual production rollout (10% → 50% → 100%)

---

## Conclusion

The collectors component is **well-architected** with consistent patterns, good test coverage, and clean separation of concerns. The main challenge for FastAPI migration is **converting synchronous blocking I/O to async operations**, particularly for:

1. **RSSCollector** (trafilatura content extraction)
2. **RedditCollector** (PRAW has no async version)
3. **Rate limiting** (time.sleep → asyncio.sleep)

**Recommended Approach:**
1. Start with **AutocompleteCollector** (quick win, reference implementation)
2. Convert **TrendsCollector** and **FeedDiscoveryCollector** (medium complexity)
3. Tackle **RSSCollector** and **RedditCollector** (high complexity, use executor pattern)
4. Integrate with **FastAPI + Huey** for production deployment

**Timeline:** 4-6 weeks for full migration, assuming 1 developer working full-time.

**Risk Mitigation:** Parallel testing, gradual rollout, feature flags for easy rollback.

---

**Next Steps:**
- [ ] Review this document with team
- [ ] Prioritize collectors based on business value
- [ ] Set up async test infrastructure
- [ ] Begin AutocompleteCollector conversion (proof of concept)
