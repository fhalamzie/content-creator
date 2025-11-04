# Changelog

Recent development sessions (last 3-5 sessions, 100 lines max).

## Session 012: RSS & Reddit Collectors - Week 2 Complete (2025-11-04)

Implemented two Week 2 collectors (RSS & Reddit) using strict TDD. Built RSS collector with trafilatura content extraction and ETag caching. Built Reddit collector with PRAW integration, multi-sort support, and comment extraction. Achieved 90.23% RSS coverage (26 tests) and 85.71% Reddit coverage (21 tests).

**Components Implemented** (Week 2: 3/10):
- **RSS Collector** (606 lines, 90.23% coverage, 26 tests) - feedparser + trafilatura, conditional GET, feed health, per-host rate limiting
- **Reddit Collector** (517 lines, 85.71% coverage, 21 tests) - PRAW integration, hot/new/top/rising sorting, comment extraction, subreddit health

**RSS Collector Features**:
- Multi-format support (RSS 1.0, RSS 2.0, Atom)
- Conditional GET with ETag/Last-Modified (bandwidth optimization)
- Full content extraction via trafilatura (fallback to summary)
- Feed health tracking (success/failure counts, consecutive failures)
- Per-host rate limiting (2.0 req/sec default)
- 30-day cache TTL for feed metadata
- 13 E2E integration tests (Heise.de, GitHub Atom)

**Reddit Collector Features**:
- PRAW integration (Reddit API authentication)
- Multiple sorting methods (hot, new, top with time filters, rising)
- Comment extraction (configurable depth, top comments only)
- Quality filtering (min score, min content length, engagement)
- Subreddit health tracking (success/failure, consecutive failures)
- Rate limiting (60 req/min = 1 req/sec)
- Error handling (private subreddits, banned, not found)
- 11 E2E integration tests (r/de, r/Python, various sort methods)

**Test Metrics**: 47 unit tests passing (RSS: 26, Reddit: 21), 24 E2E integration tests (RSS: 13, Reddit: 11)

**See**: [Full details](docs/sessions/012-rss-reddit-collectors.md)

---

## Session 011: Feed Discovery Component - Week 2 Phase 1 Complete (2025-11-04)

Implemented first Week 2 collector (Feed Discovery) using strict TDD. Built 2-stage intelligent pipeline: OPML seeds + Gemini expansion → SerpAPI + feedfinder2. Configured Reddit API and SerpAPI, established E2E testing strategy for all Week 2 components. Achieved 92.69% coverage with 21 unit tests.

**Component Implemented** (Week 2: 1/10):
- **Feed Discovery** (558 lines, 92.69% coverage, 21 tests) - 2-stage pipeline, circuit breaker (3 req/day SerpAPI), 30-day caching, retry logic

**Key Features**:
- Stage 1: OPML seeds + Gemini CLI expansion + custom feeds (7 feeds from config)
- Stage 2: SerpAPI search + feedfinder2 auto-detection (10 domains → 10-30 feeds estimated)
- Circuit breaker enforces 3 requests/day SerpAPI limit (safety margin on 100/month free tier)
- 30-day SERP caching reduces duplicate queries
- 2-retry logic with fallback when Gemini CLI fails
- Feed deduplication across stages

**See**: [Full details](docs/sessions/011-feed-discovery-component.md)

---

## Session 010: Universal Topic Research Agent - Week 1 Complete (2025-11-04)

Completed final Week 1 component (Huey Task Queue) achieving 100% Week 1 Foundation completion. Implemented background task processing with SQLite backend, dead-letter queue, retry logic, and periodic scheduling. All 7 foundation components now ready for Week 2.

**Component Implemented** (7/7 ✅):
- **Huey Task Queue** (73 lines, 82.19% coverage, 36 tests) - SQLite backend, DLQ, exponential backoff (3 retries @ 60s base), periodic tasks (daily 2 AM, weekly Monday 9 AM)

**Week 1 Final Metrics**: 160 tests passing, 94.67% overall coverage, 100% TDD compliance, 7/7 components complete

**See**: [Full details](docs/sessions/010-week1-huey-task-queue.md)

---

## Session 009: Universal Topic Research Agent - Week 1 Foundation (Part 2) (2025-11-04)

Completed 3 more Week 1 foundation components using strict TDD: SQLite Manager, LLM Processor, and Deduplicator. Week 1 now 6/7 complete (85.7%) with 94.67% test coverage across 64 tests.

**Components Implemented** (3/7):
- **SQLite Manager** (147 lines, 97.96% coverage, 22 tests) - 3 tables (documents, topics, research_reports), FTS5 search, transaction support
- **LLM Processor** (99 lines, 89.90% coverage, 19 tests) - Replaces 5GB NLP stack (fasttext, BERTopic, spaCy) with qwen-turbo, 30-day caching, $0.003/month
- **Deduplicator** (71 lines, 94.37% coverage, 23 tests) - MinHash/LSH similarity detection, canonical URL normalization, <5% duplicate rate target

**See**: [Full details](docs/sessions/009-topic-research-week1-part2.md)

---

*Older sessions archived in `docs/sessions/` directory*
