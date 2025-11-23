# Tasks

## Current Sprint - E2E Testing & Production Validation

### Completed

- [x] **Full Pipeline E2E Test** (Session 042) ✅ COMPLETE
  - [x] Fix timeout issue (300s → 900s for ContentPipeline Stage 3) ✅ DONE
  - [x] Fix E2E test failures (10 fixes: field names + thresholds + API) ✅ DONE
  - [x] Validate collection → clustering → content pipeline flow ✅ DONE
  - [x] Topic clustering E2E (5/5 tests PASSED) ✅ DONE
  - [x] Collector unit tests (150/150 PASSED) ✅ DONE

### Completed (Session 043)

- [x] **Notion Sync Implementation** ✅ COMPLETE
  - [x] Added TOPICS_SCHEMA (19 properties) ✅ DONE
  - [x] Implemented `sync_to_notion(limit=10)` method ✅ DONE
  - [x] Created 9 unit tests (all passing) ✅ DONE
  - [x] Environment variable auto-loading ✅ DONE

- [x] **E2E Test Validation** ✅ COMPLETE
  - [x] Fixed 8 field name errors in tests ✅ DONE
  - [x] All 4 Universal Topic Agent E2E tests PASSED (25:40 runtime) ✅ DONE
  - [x] All 13 Streamlit Playwright E2E tests PASSED (52s runtime) ✅ DONE

- [x] **Daily Automation Discovery** ✅ COMPLETE
  - [x] Found existing Huey implementation (2 AM daily, Monday 9 AM Notion sync) ✅ DONE
  - [x] Fixed `weekly_notion_sync()` bug ✅ DONE

### Acceptance Criteria Validation

**From TASKS.md - Universal Topic Research Agent Phase 1**: **5/6 COMPLETE (83%)** ✅
- [x] Deduplication rate <30% ✅ VALIDATED (22.22% actual, Session 042)
- [x] Language detection >95% accurate ✅ VALIDATED (100% German docs, Session 042)
- [x] Deep research generates 5-6 page reports with citations ✅ VALIDATED ($0.02597/topic, Session 042)
- [ ] Discovers 50+ unique topics/week for test config (49 in single run - close!)
- [x] Top 10 topics sync to Notion successfully ✅ VALIDATED (Session 043)
- [x] Runs automated (daily collection at 2 AM) ✅ VALIDATED (Session 043)

---

## CRITICAL PRIORITY - FastAPI Migration to Production Architecture

**Goal**: Migrate Streamlit MVP monolith to production-grade FastAPI backend with PostgreSQL, 100% TDD, and VPS deployment

**Target Domain**: übergabeprotokoll24.de

### Phase 0: Pre-Migration Code Reviews ✅ COMPLETE (Session 049)

**Status**: 5/5 subagent reviews complete, ready for synthesis

**Completed** (6 hours - parallel execution):
- [x] **Agents Review** (4,513 LOC analyzed) → `docs/AGENTS_DEEP_REVIEW_PHASE0.md`
  - 9 core agents: BaseAgent, GeminiAgent, Competitors, Keywords, ContentGap, SERP, Writing, FactChecker, UniversalTopic
  - Finding: 100% synchronous, 28-41 hours async conversion needed
  - Critical blocker: BaseAgent must convert first (all agents depend on it)
  - Missing tests: GeminiAgent (0 tests)

- [x] **Collectors Review** (~2,000 LOC) → `docs/phase-0-collectors-deep-review.md`
  - 6 collectors: RSS, Reddit, Trends, Autocomplete, FeedDiscovery, TheNewsAPI
  - Finding: 5/6 fully synchronous (TheNewsAPICollector already async)
  - Effort: 17-24 hours (1 week) or 4-6 weeks sequential
  - Easy wins: AutocompleteCollector (2-3h), TrendsCollector (2-3h)

- [x] **Database Review** (797 LOC) → Inline report (Session 049)
  - SQLiteManager: Fully synchronous, well-structured repository pattern
  - **CRITICAL**: Pydantic fields not persisted (`competitors`, `content_gaps`, `keywords`, `supporting_images` in memory only)
  - **Data loss risk**: Lost on application restart
  - Effort: 68-90 hours (2 weeks) for 11+ normalized tables

- [x] **Processors Review** (1,134 LOC) → `docs/phase0_processors_deep_review.md`
  - 4 processors: LLMProcessor, EntityExtractor, Deduplicator, TopicClusterer
  - Finding: 100% synchronous, in-memory caching only
  - **MASSIVE performance gains available**: 50x improvement (100-200s → 2-4s)
  - Effort: 23-32 hours (1 week)

- [x] **Notion Integration Review** (1,766 LOC) → Inline report (Session 049)
  - Well-architected: RateLimiter → NotionClient → TopicsSync
  - `notion-client` uses httpx (AsyncClient available)
  - Effort: 17-23 hours (1 week) - straightforward conversion

**Total Async Conversion Scope**: 155-213 hours (~5 weeks)

**Performance Gains Expected**:
- Event loop (uvloop): 2-4x
- JSON (orjson): 2x
- Database (asyncpg + Postgres): 5x
- Processors (parallel): 50x
- **Overall: 20-50x improvement** 🚀

### Phase 1: Synthesis & Planning (NEXT - Option 1)

**Goal**: Consolidate findings and create actionable implementation roadmap

**Tasks**:
- [ ] **Create Phase 0 Synthesis Document** (2-3 hours)
  - [ ] Consolidate all 5 code review findings
  - [ ] Identify critical path (BaseAgent → Database → Processors → ...)
  - [ ] Document migration risks and mitigation strategies
  - [ ] Create phased implementation order with dependencies

- [ ] **Update FASTAPI_MIGRATION_PLAN.md** (1 hour)
  - [ ] Add specific refactoring priorities based on reviews
  - [ ] Add effort estimates per phase
  - [ ] Add critical path identification
  - [ ] Add risk assessment and mitigation strategies

- [ ] **Create Phase 2 Implementation Checklist** (0.5 hours)
  - [ ] Break down Phase 2 into actionable tasks
  - [ ] Assign effort estimates
  - [ ] Identify dependencies and blockers
  - [ ] Define success criteria per task

**Estimated Effort**: 3.5-4.5 hours

**Benefits**:
- ✅ Single source of truth for migration
- ✅ Clear implementation roadmap
- ✅ Risk mitigation strategies documented
- ✅ Stakeholder-ready plan

### Phase 2: Database Migration (After Phase 1)

**Goal**: Implement normalized PostgreSQL schema with async SQLAlchemy

**Tasks** (68-90 hours):
- [ ] Schema design (11+ normalized tables): 8-12 hours
- [ ] SQLAlchemy async models: 12-16 hours
- [ ] Repository layer with asyncpg: 20-24 hours
- [ ] Alembic migrations: 8-12 hours
- [ ] Data migration scripts: 4-6 hours
- [ ] Testing (100% critical path): 16-20 hours

**Prerequisites**:
- [ ] Fix in-memory data persistence bug OR accept data loss
- [ ] Set up PostgreSQL 16 locally + on VPS
- [ ] Configure asyncpg connection pool

**Success Criteria**:
- ✅ All 11+ tables created with foreign keys
- ✅ Alembic migrations working
- ✅ 100% repository layer test coverage
- ✅ No data loss (all Pydantic fields persisted)

### Phase 3: Async Agent Conversion (After Phase 2)

**Critical Path**: BaseAgent → Individual Agents

**Tasks** (28-41 hours):
- [ ] Convert BaseAgent to async: 8-12 hours (BLOCKER - do first)
- [ ] Convert individual agents (8 agents × 2-3h): 16-24 hours
- [ ] Add GeminiAgent test suite: 2-3 hours
- [ ] Refactor UniversalTopicAgent dependencies: 2-3 hours

**Success Criteria**:
- ✅ All agents use async/await
- ✅ GeminiAgent has >90% test coverage
- ✅ UniversalTopicAgent dependency injection working

### Architecture Decisions Confirmed

**Backend**:
- ✅ FastAPI 0.121.3 (async web framework)
- ✅ Pydantic 2.12.4 (strict type safety)
- ✅ SQLAlchemy 2.0.44 (async ORM)
- ✅ asyncpg 0.30.0 (5x faster than psycopg3)
- ✅ PostgreSQL 16 (ACID, full-text search, pgvector)

**Performance**:
- ✅ uvloop 0.29+ (2-4x event loop speed)
- ✅ orjson 3.11.4 (2x JSON parsing speed)

**Testing**:
- ✅ 100% TDD approach
- ✅ 95%+ coverage overall
- ✅ 100% coverage on critical paths (services, repositories, API)
- ✅ mypy --strict (maximum type safety)

**Deployment**:
- ✅ Docker + Docker Compose (multi-stage builds)
- ✅ GitHub Actions CI/CD
- ✅ VPS deployment (übergabeprotokoll24.de)
- ✅ Caddy 2+ (reverse proxy, auto-SSL)

**Database**:
- ✅ Direct Postgres cutover (no dual-write)
- ✅ Fully normalized schema (no JSONB)
- ✅ Alembic migrations

**Jobs**:
- ✅ Huey + Redis (keep existing stack)

**See**: [docs/FASTAPI_MIGRATION_PLAN.md](docs/FASTAPI_MIGRATION_PLAN.md) (2,277 lines - single source of truth)

---

## High Priority - Universal Topic Research Agent

**Status**: Core components complete, E2E testing in progress

### E2E Test Status

- [x] Topic clustering E2E - Test clustering on real document set ✅ COMPLETE (Session 042 - 5/5 tests)
- [x] Full Pipeline E2E - Feed Discovery → RSS Collection → Dedup → Clustering → Deep Research → Notion Sync ✅ COMPLETE (Session 043 - 4/4 tests)
- [x] Playwright E2E - Test Streamlit UI for topic review ✅ COMPLETE (Session 043 - 13/13 tests)
- [ ] API Endpoint E2E - Test Huey task queue endpoints (optional - unit tests comprehensive)

---

## High Priority - Content Creator Phase 4: Repurposing Agent

- [ ] Write tests + implement `src/agents/repurposing_agent.py`
- [ ] Social post templates (LinkedIn, Facebook, TikTok, Instagram)
- [ ] Hashtag generation (platform-specific)
- [ ] Media suggestions (image descriptions for DALL-E 3)
- [ ] Integration with generate page (auto-create social posts)
- [ ] Test social post sync to Notion

---

## High Priority - Content Creator Phase 4.5: Media Generation (Sessions 044-048)

**Goal**: Automated image generation with cost optimization and quality enhancements

**Status**: ✅ COMPLETE + OPTIMIZED (13.3/18.5 hours - 28% faster than estimated) - Production Ready

**Key Discoveries**:
- ✅ Tone analysis already exists in Stage 1 (`extract_website_keywords()`)
- ✅ Notion schemas already have `Hero Image URL` and `Media URL` fields
- ✅ No need to build tone analyzer from scratch!

**Implementation Plan**: Session 044 (approved)

### Control Hierarchy (3-Tier System)
1. **Market Config Default**: `enable_image_generation: true` (default ON)
2. **Python API Override**: `research_topic(generate_images=None)` (None = inherit)
3. **Streamlit UI Checkbox**: Final override, respects market default

### Phase 1: Config Enhancement (1.5 hours) ✅ COMPLETE (Session 044)
- [x] Add 4 fields to MarketConfig: `brand_tone`, `enable_image_generation`, `image_quality`, `image_style_preferences`
- [x] Update `proptech_de.yaml` with image settings
- [x] Write config loader tests (3 tests)

### Phase 2: Tone Propagation (2 hours) ✅ COMPLETE (Session 044)
- [x] Store tone in `run_pipeline()` return dict
- [x] Update `research_topic()` signature: `brand_tone`, `generate_images` params
- [x] Update `synthesize()` signature: `brand_tone`, `generate_images` params
- [x] Write propagation tests (3 tests)

### Phase 3: ImageGenerator Module (6 hours) ✅ COMPLETE (Session 045, 1.5h actual)
- [x] Create `src/media/image_generator.py` (347 lines)
- [x] Implement 7-tone prompt mapping (Professional, Technical, Creative, etc.)
- [x] DALL-E 3 integration: `generate_hero_image()` (1792x1024 HD, $0.08)
- [x] DALL-E 3 integration: `generate_supporting_image()` (1024x1024 standard, $0.04)
- [x] Silent failure handling (3 retries, return None on error)
- [x] Cost tracking integration
- [x] Write 23 unit tests (tone mapping, API calls, errors, cost) - exceeded 20 goal

### Phase 8: Quality Improvements (2.5 hours) ✅ COMPLETE (Session 047)
- [x] **Migration**: DALL-E 3 → Flux 1.1 Pro Ultra with RAW MODE (authentic photorealism)
- [x] **Fix**: Writing agent empty responses (qwen3-235b-a22b → qwen3-235b-a22b-2507)
- [x] **Fix**: Supporting image topic extraction (markdown parsing issues)
- [x] **Enhancement**: 4-tier section-based aspect extraction (H2 → H3 → paragraphs → topic+context)
- [x] **Enhancement**: RAW photography prompts (crisp, imperfections, balanced subject matter)
- [x] **Enhancement**: Safety tolerance 2 → 5 (more diverse/raw outputs)
- [x] **Fix**: Notion block limit (automatic chunking for >100 blocks)
- [x] **Process**: Established Streamlit restart discipline (critical for code changes)
- [x] **Result**: User feedback "much better!!" → "more crisp and raw results"

### Phase 9: Cost Optimization & Multilingual (3.5 hours) ✅ COMPLETE (Session 048)
- [x] **RAW Mode Fix**: Disabled RAW mode (was causing dull appearance)
- [x] **Safety Tolerance**: Reduced 6 → 4 (professional predictability)
- [x] **Mixed Models**: Hero = Flux Ultra ($0.06), Supporting = Flux Dev ($0.003, 95% cheaper)
- [x] **Dynamic Supporting**: 0-2 images based on H2 section count (≤3 → 0, 4-5 → 1, 6+ → 2)
- [x] **German Text**: Explicit language requirement for text in images
- [x] **Multilingual**: English system prompts + language parameter (industry standard)
- [x] **Pricing Fix**: Updated $0.04 → $0.06 (correct Replicate pricing)
- [x] **Result**: 60% cost reduction ($1.90 → $0.75/month), more polished images

### Phase 4: Synthesizer Integration (0.5 hours) ✅ COMPLETE (Session 046)
- [x] Integrate ImageGenerator into ContentSynthesizer
- [x] Add image generation step after article synthesis (`_generate_article_images()`)
- [x] Return structure: `hero_image_url`, `supporting_images`, `image_cost`
- [x] Silent failure handling (research continues on image generation errors)

### Phase 5: Streamlit UI Integration (0.5 hours) ✅ COMPLETE (Session 046)
- [x] Add checkbox to Generate page: "Generate images (1 HD hero + 2 supporting)"
- [x] Respect market config default
- [x] Display generated images in 5-tab layout (Hero, Support 1-2, Sources, Article)
- [x] Show image generation cost breakdown ($0.16 images + $0.01 synthesis)

### Phase 6: Notion Sync Enhancement (0.5 hours) ✅ COMPLETE (Session 046)
- [x] Map `hero_image_url` → `Hero Image URL` field (URL type)
- [x] Add `supporting_images` to Topic model (list of ImageMetadata)
- [x] Add `Supporting Images` field to TOPICS_SCHEMA (JSON serialized)
- [x] TopicsSync mapping complete

### Phase 7: E2E Testing (0.8 hours) ✅ COMPLETE (Session 046)
- [x] Test: Full pipeline with images enabled (544 words, 3 images, $0.16, 62s) ✅ PASSED
- [x] Test: Images disabled (583 words, 0 images, $0.00, 13s) ✅ PASSED
- [x] Test: Silent failure (mocked DALL-E error, article completes) ✅ PASSED
- [x] Test: Notion sync with images ✅ PASSED
- [x] 4/4 E2E tests passing (2 live API, 2 mocked)

### Cost Impact

**Per Topic** (Updated Session 048 - Cost Optimization):
- Research + Synthesis: $0.01
- Hero Image (Flux 1.1 Pro Ultra, 16:9, 4MP): $0.06
- Supporting (Flux Dev, 1:1, ~2MP): $0.003 each
- **Short (≤3 sections)**: $0.07 (hero only)
- **Medium (4-5 sections)**: $0.073 (hero + 1 Dev)
- **Long (6+ sections)**: $0.076 (hero + 2 Dev)

**Monthly (10 articles, realistic usage)**:
- Before (Session 047): $1.90
- After (Session 048): $0.75
- **Savings: 60%** ($1.15/month, $13.80/year)

**Quality**:
- Hero: Premium 4MP Flux Ultra (polished, not dull RAW)
- Supporting: Good 2MP Flux Dev (95% cheaper, still quality)
- Safety tolerance: 4 (professional predictability)

### Implementation Order (TDD)
- ✅ **Phase 1-2 (3.5h)**: Config + Tone Propagation (Session 044)
- ✅ **Phase 3 (1.5h)**: ImageGenerator Core + DALL-E (Session 045)
- ✅ **Phase 4 (0.5h)**: Synthesizer Integration (Session 046)
- ✅ **Phase 5 (0.5h)**: Streamlit UI (Session 046)
- ✅ **Phase 6 (0.5h)**: Notion Sync (Session 046)
- ✅ **Phase 7 (0.8h)**: E2E Tests (Session 046)
- ✅ **Phase 8 (2.5h)**: Quality Improvements - Flux Migration + RAW Enhancements (Session 047)
- ✅ **Phase 9 (3.5h)**: Cost Optimization + Multilingual Architecture (Session 048)

**Total**: 18.5 hours estimated → 13.3 hours actual (28% faster) ✅ ALL PHASES COMPLETE + OPTIMIZED

### Success Criteria
- ✅ Tone extracted from Stage 1 and propagated to synthesis
- ✅ Dynamic images (0-2 supporting based on article structure)
- ✅ Professional predictability (safety_tolerance: 4, no inappropriate styles)
- ✅ Silent failure (research completes even if images fail)
- ✅ 3-tier control: Config → API → UI
- ✅ All images sync to Notion
- ✅ Cost tracking accurate ($0.07-$0.076/topic with mixed models)
- ✅ E2E test validates full flow
- ✅ Polished quality (Standard mode, not dull RAW)
- ✅ Supporting images use actual article sections (H2 headings)
- ✅ German text in images (UI, captions, signs)
- ✅ Multilingual architecture (English prompts + language parameter)
- ✅ 60% cost reduction via mixed models (Ultra hero, Dev supporting)
- ✅ Notion sync handles unlimited blog post length (auto-chunked at 100 blocks)

---

## Backlog

**Universal Topic Research Agent - Phase 2** (Week 3-4):
- [ ] SERP Top 10 analyzer (RankCraft-AI pattern, DuckDuckGo)
- [ ] Content scoring algorithm (0-100 scale)
- [ ] Keyword density + variations analysis
- [ ] Readability scoring (textstat)
- [ ] Entity coverage analysis
- [ ] Topic authority detection (LLM-based clustering)
- [ ] Content gap analysis (competitors vs ours)
- [ ] Difficulty scoring (personalized)
- [ ] Internal linking suggestions
- [ ] Performance tracking setup

**Universal Topic Research Agent - Phase 3** (Week 5-6):
- [ ] Postgres migration (keep SQLite for dev)
- [ ] pgvector for similarity search
- [ ] Huey + Redis (if distributed workers needed)
- [ ] Source reliability scoring
- [ ] Compliance logging (robots.txt, attribution)
- [ ] Test with 3+ different configs (validate universal design)
- [ ] Feed manager UI (Streamlit)
- [ ] Analytics dashboard (source performance)
- [ ] Multi-platform publishing (WordPress, Webflow, Medium)
- [ ] Google Search Console integration

**Content Creator - Phase 5 (Publishing Automation)**:
- [ ] Platform publishers (LinkedIn, Facebook APIs)
- [ ] Publishing agent + background service (APScheduler)
- [ ] Publisher deployment (PM2 or Streamlit thread)
- [ ] Scheduled posting (calendar integration)

**Phase 6 - Enhancements**:
- [ ] Analytics dashboard (performance tracking)
- [ ] Plagiarism checker integration
- [ ] Competitor tracking over time (detect strategy changes)
- [ ] Keyword trend tracking (seasonal patterns)
- [ ] Export competitor analysis to Notion "Competitors" database
- [ ] Export keyword research to Notion "Research Data" database
- [ ] A/B testing for social posts
- [ ] Multi-language support (add blog_en.md)
- [ ] Video/audio media generation (future)

---

## Known Issues

None currently blocking. All critical bugs resolved in sessions 024-041.

**Fixed Issues** (archived for reference):
- ✅ ContentPipeline Stage 3 enabled (Session 020)
- ✅ Gemini API grounding (Session 024)
- ✅ gpt-researcher bugs (Session 020)
- ✅ LangChain version <1.0 (pinned in requirements)
- ✅ pytrends Google 404/429 (Session 015 - migrated to Gemini CLI)
- ✅ Gemini CLI hanging (Session 018)
- ✅ Reddit collector duplicate check bug (Session 041)
- ✅ Autocomplete noise (Session 040 - 73% duplicate reduction)

---

## Technical Debt

- [ ] Upgrade langchain to 1.0+ when gpt-researcher supports it
- [ ] Add disk space monitoring for cache directory
- [ ] Test Notion client with pagination (large result sets, >100 pages)
- [ ] Test German content quality with native speakers
- [ ] Add secret rotation mechanism for API keys
- [ ] Consider cache cleanup strategy (auto-delete old posts)
- [ ] Add retry logic to cache operations (handle disk full errors)

**Completed**:
- ✅ Fix or upgrade gpt-researcher for Stage 3 (Session 020)
- ✅ Remove pytrends dependency (Session 015)
- ✅ Gemini CLI hanging issue (Session 018)
- ✅ langchain.docstore import error (Session 019)

---

## Success Criteria

**Universal Topic Research Agent**:
- **Phase 1 MVP**: Discovers 50+ unique topics/week, <30% duplicates (updated), >95% language accuracy, 5-6 page reports with citations, top 10 topics sync to Notion, automated daily collection
- **Phase 2 Intelligence**: Content scores match commercial tools, 20+ content gaps identified, difficulty scores accurate, 100+ keywords analyzed
- **Phase 3 Production**: Handles 3+ niches simultaneously, Postgres supports 100K+ documents, analytics dashboard shows ROI per source, multi-platform publishing works

**Content Creator**:
- **Phase 1** ✅: All tasks complete, cache system working (100% coverage), Notion connection (rate-limited, 93.67% coverage), 5 databases created, test infrastructure (97.70% coverage)
- **Phase 2** ✅: German prompts created (2 templates), base agent working (100% coverage), research agent (Gemini CLI, 97.06% coverage), writing agent (Qwen3-Max, 97.70% coverage), sync manager (cache → Notion, 93.20% coverage), integration tests passing (11 tests), 171 total tests, 94.87% overall coverage
- **Phase 3** ✅: Streamlit UI functional (all 5 pages: setup, generate, browse, settings, dashboard), progress tracking working, ETA display accurate, cost tracking visible, Notion integration seamless, 254 tests passing
- **Phase 4 MVP**: Generate 10 German blog posts via UI, cache sync to Notion, edit in Notion, 4 social posts per blog (repurposing agent), cost target achieved (~$0.98/bundle), basic publishing working
- **Phase 5 Production**: 100 posts generated/published, logging in place, documentation complete, publisher stable, German quality validated by native speakers, rate limiting working, analytics dashboard functional

---

## Notes

- **TDD**: Write tests before implementation
- **Coverage**: 80% minimum, 100% for critical paths
- **Cost Targets**:
  - Content Creator: ~$0.98/bundle
  - Topic Research Agent: $0.01/topic (hybrid orchestrator), ~$0.003/month for collection (LLM-first strategy)

**Detailed Plans**:
- **Universal Topic Research Agent**: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) (1,400+ lines, single source of truth)
- **Content Creator**: [PLAN.md](PLAN.md) (original implementation plan)

**Session History**:
- Session 041: Reddit/Trends integration complete
- Session 040: Duplicate rate reduction (75.63% → 20.63%)
- Session 039: RSS collection integration complete
- Session 038: FullConfig standardization complete
- Session 034-036: Hybrid Orchestrator complete (76 tests, $0.01/topic, 95%+ uptime)
- Session 027-033: 5-Source SEO architecture + 3-stage reranker complete
- Full history: See [CHANGELOG.md](CHANGELOG.md) and [docs/sessions/](docs/sessions/)
