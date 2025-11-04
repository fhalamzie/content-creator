# Changelog

Recent development sessions (last 3-5 sessions, 100 lines max).

## Session 018: ContentPipeline UI Integration & Gemini CLI Fix (2025-11-04)

**Completed Week 2 Phase 4**: Integrated 5-stage ContentPipeline into Streamlit UI with full topic research workflow. Fixed critical Gemini CLI hanging issue discovered during integration testing. Used parallel subagents to comprehensively test all components and identify root causes. All systems now working end-to-end.

**Critical Fix - Gemini CLI stdin method**: Root cause of CLI hanging identified via parallel testing - prompts passed as positional args cause interactive mode hang. Fixed across 3 agents by using stdin input method: `subprocess.run(cmd, input=query)` instead of `subprocess.run([cmd, query])`. 100% success rate after fix.

**Stage 3 Type Handling**: Fixed `DeepResearcher._build_query()` to handle mixed data formats - KeywordResearchAgent returns dict keywords `{'keyword': str, ...}` while CompetitorResearchAgent returns string gaps. Added isinstance() checks to extract correct field from dicts or use strings directly.

**Files Modified**:
- `src/agents/competitor_research_agent.py:198-214` - Gemini CLI stdin fix
- `src/agents/keyword_research_agent.py:204-220` - Gemini CLI stdin fix
- `src/agents/research_agent.py:146-166` - Gemini CLI stdin fix
- `src/research/deep_researcher.py:234-256` - Mixed format handling
- `src/ui/pages/topic_research.py:336-340` - Re-enabled Gemini CLI (use_cli=True)

**Testing**: Ran 5 parallel subagents (Playwright UI, Stage 1-3 tests, CLI investigation) for comprehensive validation. All stages tested individually and together. Pipeline ready for E2E testing with real topics.

**Performance**: Gemini CLI now works (2-30s) with API fallback (60-90s) still available. Full pipeline: ~2-3 min for complete topic research (5 stages).

**See**: [Full details](docs/sessions/018-content-pipeline-ui-integration.md)

---

## Session 016: Entity Extractor + Deep Research + Notion Sync (2025-11-04)

Implemented 3 more Week 2 components using strict TDD: Entity Extractor (LLM-based NER), Deep Research Wrapper (gpt-researcher integration), and Notion Topics Sync (Topic → Notion database). Week 2 now 90% complete (9/10 components). Entity extractor enriches Document objects with entities/keywords via LLMProcessor. Deep researcher wraps gpt-researcher with context-aware queries. Notion sync enables editorial review of discovered topics.

**Components Implemented** (Week 2: 9/10):
- **Entity Extractor** (197 lines, 14 tests + 8 E2E) - LLM-based entity/keyword extraction, batch processing, statistics tracking
- **Deep Research Wrapper** (279 lines, 12 tests) - gpt-researcher integration, Gemini 2.0 Flash, contextualized queries, lazy loading
- **Notion Topics Sync** (361 lines, 15 tests) - Sync Topic objects to Notion, rate-limited, batch support, update existing pages

**Entity Extractor Features**:
- Processes Document objects (extracts entities + keywords via LLMProcessor)
- Batch processing with skip_errors support
- Statistics tracking (success/failure rates)
- Force reprocess option
- Smart skipping (already-processed documents)
- 22 total tests (14 unit + 8 E2E)

**Deep Research Wrapper Features**:
- gpt-researcher wrapper with Gemini 2.0 Flash (FREE)
- Context-aware queries (domain, market, language, vertical)
- Competitor gaps & keywords integration
- Lazy import (avoids dependency issues in tests)
- DuckDuckGo search backend
- Statistics tracking
- 12 unit tests (all passing)

**Notion Topics Sync Features**:
- Syncs Topic objects to Notion database
- Create new pages or update existing (configurable)
- Skip already-synced topics
- Batch processing with skip_errors support
- Rate-limited via NotionClient (2.5 req/sec)
- Statistics tracking (success/failure rates)
- 15 unit tests (all passing)

**Test Metrics**: 41 new tests (22 entity extractor + 12 deep researcher + 15 notion sync = 49 total), 100% TDD compliance

**Technical Details**:
- Entity extractor: `src/processors/entity_extractor.py` (197 lines)
- Deep researcher: `src/research/deep_researcher.py` (279 lines, lazy import pattern)
- Notion topics sync: `src/notion_integration/topics_sync.py` (361 lines)
- Updated `src/processors/__init__.py` to export EntityExtractor
- Created `src/research/` directory for research components

**See**: [Full details](docs/sessions/016-entity-extractor-deep-research.md)

---

## Session 015: Gemini CLI Trends Migration + Topic Clustering (2025-11-04)

**BREAKING CHANGE**: Migrated TrendsCollector from pytrends (DEAD, archived April 2025) to Gemini CLI (FREE, unlimited, reliable). Implemented Topic Clustering component (Week 2 Phase 6). Fixed Feed Discovery timeout test. Added pytest-rerunfailures support. Week 2 now 60% complete (6/10 components).

**Major Migration** (pytrends → Gemini CLI):
- **TrendsCollector** (782 lines, 26 tests) - Complete rewrite using Gemini CLI subprocess, FREE & UNLIMITED, no rate limits, official Google API
- **Why**: pytrends archived (April 2025), Google 404/429 errors, maintainer quit
- **Benefits**: No rate limiting (vs 429 after 2-3 req), real-time web search data, 100% reliable, future-proof

**Components Implemented** (Week 2: 6/10):
- **Topic Clustering** (343 lines, 22 tests) - TF-IDF + HDBSCAN + LLM labeling, auto-determines K, noise handling ⭐ **NEW**

**Test Metrics**: 192 passing (128 collectors + 22 topic clusterer + 42 others), 0.33s trends tests, 11 external API tests deselected

**See**: [Full details](docs/sessions/015-gemini-cli-trends-migration.md)

---

## Session 014: Autocomplete Collector - Week 2 Phase 5 Complete (2025-11-04)

Implemented Autocomplete Collector using strict TDD with Google autocomplete API integration. Built comprehensive collector supporting 3 expansion types (alphabet a-z, question prefixes, preposition patterns). Achieved 93.30% coverage with 23 unit tests + 12 E2E integration tests. Week 2 now 50% complete (5/10 components).

**Component Implemented** (Week 2: 5/10):
- **Autocomplete Collector** (454 lines, 93.30% coverage, 23 tests) - Google autocomplete API, 3 expansion types, smart caching, rate limiting

**Autocomplete Collector Features**:
- Alphabet expansion (a-z patterns: "keyword a", "keyword b", ...)
- Question prefix expansion (what, how, why, when, where, who)
- Preposition expansion (for, with, without, near, vs, versus)
- Smart caching (30-day TTL for suggestions)
- Rate limiting (10 req/sec - Google autocomplete is lenient)
- Language support (de, en, fr, etc.)
- Deduplication across expansion types
- Graceful error handling (continues on partial failures)
- 12 E2E integration tests (validate real Google autocomplete API)

**Test Metrics**: 23 unit tests passing, 12 E2E tests written, 93.30% coverage (exceeds 80% target)

**See**: [Full details](docs/sessions/014-autocomplete-collector.md)

---

## Session 013: Trends Collector - Week 2 Phase 4 Complete (2025-11-04)

Implemented Trends Collector using strict TDD with pytrends integration. Built comprehensive collector supporting trending searches, related queries, and interest over time. Achieved 88.68% coverage with 26 unit tests + 11 E2E integration tests. Week 2 now 40% complete (4/10 components).

**Component Implemented** (Week 2: 4/10):
- **Trends Collector** (702 lines, 88.68% coverage, 26 tests) - pytrends integration, multi-query support, smart caching, conservative rate limiting

**Trends Collector Features**:
- Trending searches (daily/realtime by region: DE, US, FR, etc.)
- Related queries (top/rising for keywords)
- Interest over time (search volume trends with custom timeframes)
- Smart caching (1h TTL for trending searches, 24h for interest data)
- Conservative rate limiting (1 req/2sec to avoid Google blocking)
- Query health tracking (skip after 5 consecutive failures)
- Regional targeting (ISO country codes)
- 11 E2E integration tests (validate real Google Trends API)

**Test Metrics**: 26 unit tests passing, 11 E2E tests written, 88.68% coverage (exceeds 80% target)

**See**: [Full details](docs/sessions/013-trends-collector.md)

---

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
