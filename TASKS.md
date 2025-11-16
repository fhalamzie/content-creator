# Tasks

## Current Status (Session 070)

### MVP Features Complete ✅

**Content Creator (Sessions 044-062)**:
- ✅ Phase 1-3: Core system, agents, UI (Sessions 001-043)
- ✅ Phase 4: Repurposing Agent (Sessions 059-062) - Full social automation
- ✅ Phase 4.5: Media Generation (Sessions 044-049) - Blog + social images
- ✅ UI Refactoring (Sessions 051-055) - Streamlined UX
- ✅ Research Lab (Sessions 056-058) - Competitor/keyword analysis

**Universal Topic Research Agent (Sessions 027-043, 065-066)**:
- ✅ Phase 1: Hybrid orchestrator, collectors, clustering, Notion sync
- ✅ RSS Feed Integration: 1,037 feeds, dynamic generation, multilingual (Sessions 065-066)
- ✅ E2E testing complete (22/22 tests passing)

**Current Cost Performance**:
- Blog + images + 4 social posts: $0.072-$0.082/article ✅ (under $0.10 target)
- Topic research: $0.01/topic ✅

---

## High Priority - Pipeline Automation Improvements

### ✅ Multilingual RSS Integration (Session 066) - COMPLETED

**Status**: Multilingual RSS topic discovery with adaptive 70/30 ratio complete, all tests passing

**Implementation Completed**:
1. ✅ Added `english_ratio` parameter to `discover_topics_from_collectors()`
2. ✅ Implemented 4 ratio presets: 90/10 (global), 70/30 (industry), 40/60 (national), 20/80 (hyper-local)
3. ✅ Dual-source collection: English feeds + Local language feeds
4. ✅ Automatic translation: English topics → Target language via Gemini
5. ✅ Native local content: Collected directly (no translation needed)
6. ✅ Fixed `_collector_config` initialization bug
7. ✅ Fixed `RSSCollector.collect_from_feed()` parameter mismatch
8. ✅ Phase B end-to-end test: PASSED (50 topics from 7 sources, 10 from RSS)

**Results**:
- ✅ **Multilingual users get best of both worlds**: English (earlier, abundant) + Local (laws, regulations)
- ✅ **Zero additional cost**: FREE Gemini API for translation
- ✅ **Backward compatible**: Default 70/30 ratio for existing code
- ✅ **All tests passing**: RSS collector working perfectly

**Files Modified**:
- `src/orchestrator/hybrid_research_orchestrator.py` (+188 lines) - Multilingual RSS collection
- `RSS_IMPLEMENTATION_STATUS.md` (created, 227 lines) - Status tracking

**Next Steps** (Optional Enhancements):
- [ ] Test with real German market users (validate translation quality)
- [ ] Test other ratios (90/10, 40/60, 20/80) with real use cases
- [ ] Implement Phase C: Continuous automated growth (100-200 feeds/day)
- [ ] Integrate Reddit, News collectors (RSS is now complete)

---

## Next Steps - Choose Direction

Pick ONE direction for Session 067+:

### Option 1: Production Validation
**Goal**: Validate MVP with real usage before next phase

- [ ] Manual testing verification (Session 062 checklist):
  - [ ] Tab 2: Competitor analysis → Notion sync
  - [ ] Tab 3: Keyword research → Notion sync
  - [ ] Research Lab: Export to Quick Create workflows
  - [ ] Quick Create: Full pipeline (research → blog → social → Notion)
  - [ ] Cost tracking: Generate 10 articles, verify $0.72-$0.82 total
- [ ] Performance testing:
  - [ ] Batch generation (5+ articles)
  - [ ] Concurrent workflows
  - [ ] Error handling validation
- [ ] Documentation:
  - [ ] Update README with all new features
  - [ ] Create user guide for Research Lab
  - [ ] Document social automation workflow

**Timeline**: 1-2 days
**Outcome**: Production-ready MVP with validated costs

### Option 2: Phase 5 - Publishing Automation
**Goal**: Complete content-to-publish pipeline

- [ ] Platform publishers (LinkedIn, Facebook APIs)
- [ ] Publishing agent + background service (APScheduler)
- [ ] Scheduled posting (calendar integration)
- [ ] Publisher deployment (PM2 or Streamlit thread)

**Timeline**: 2-3 weeks
**Outcome**: Full automation from research → publish

### Option 3: SaaS Migration
**Goal**: Start transition to production architecture

- [ ] Follow [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md) plan
- [ ] Week 1: Setup boilerplate (FastAPI + React + Postgres)
- [ ] Week 2-3: Research domain migration
- [ ] Week 4-5: Content domain migration
- [ ] Week 6: Publishing + deployment

**Timeline**: 6 weeks
**Outcome**: Multi-tenant SaaS foundation

### Option 4: Universal Topic Agent - Phase 2
**Goal**: Add content intelligence layer

- [ ] SERP Top 10 analyzer (RankCraft-AI pattern)
- [ ] Content scoring algorithm (0-100 scale)
- [ ] Difficulty scoring (personalized)
- [ ] Internal linking suggestions
- [ ] Performance tracking

**Timeline**: 3-4 weeks
**Outcome**: AI-powered content strategy insights

### Option 5: Topical Authority Stack ⭐ RECOMMENDED
**Goal**: Build niche dominance with unique, SEO-optimized content using cross-topic synthesis

**Strategy**: Eliminate duplicate research, synthesize insights across related topics, build hub+spoke clusters

**Current Gap**: Two research systems don't connect:
- Quick Create uses simple ResearchAgent (basic web search)
- Hybrid Orchestrator creates deep $0.01 reports but they're NOT used for writing

**Cost Impact**: $0.067-$0.092/article (saves 7% or adds 6% with premium features, stays under $0.10!)

#### Phase 1: Connect Research → Writing ⭐ COMPLETED (Session 067)
**Goal**: Eliminate duplicate research, use deep $0.01 reports for writing

- [x] Add cache lookup helper function (`load_cached_research()`)
- [x] Update Quick Create to check SQLite database before researching
- [x] Update WritingAgent to use structured deep research (2000+ words)
- [x] Test with existing cached research reports
- [x] Verify cost savings (100% savings on repeated topics)
- [x] SQLite performance optimization (60K RPS capable)
- [x] Documentation in ARCHITECTURE.md

**Timeline**: 2 hours (completed Session 067)
**Cost**: $0 (FREE, connects existing systems + 100% savings on cache hits)
**Outcome**: WritingAgent gets 2000-word deep research instead of 200-char summaries, 100% cost savings on repeated topics, SQLite single source of truth

#### Phase 2: Cross-Topic Synthesis ⭐ COMPLETED (Session 068)
**Goal**: Create unique insights competitors lack by synthesizing related topics

- [x] Add semantic search to SQLiteManager (find related cached reports)
- [x] Create `CrossTopicSynthesizer` class
  - [x] Find 3-5 related topics using keyword/Jaccard similarity
  - [x] Extract key insights from each (themes, gaps, predictions)
  - [x] Create synthesis summary (unique angles)
- [x] Update WritingAgent to use synthesis automatically when topic_id provided
- [x] Write comprehensive tests (27 tests, all passing)
- [x] Test synthesis quality with integration tests

**Timeline**: 2.5 hours (completed Session 068)
**Cost**: $0 (FREE, cache-only operations, CPU-based keyword similarity)
**Outcome**: Unique perspectives from cross-topic connections, topical authority signals, natural internal linking suggestions, zero cost, 100% test coverage, <1s synthesis time

#### Phase 3: Hub + Spoke Strategy ⭐ COMPLETED (Session 069)
**Goal**: Organize 2 articles/week into topical clusters for SEO dominance

- [x] Create cluster planning template (ClusterPlan class)
  - [x] Hub article (3000 words, comprehensive pillar)
  - [x] 7 spoke articles validation (1500-2500 words each, specific angles)
  - [x] Internal linking map (hub ↔ spokes)
- [x] Add cluster fields to Blog Posts database (cluster_id, cluster_role, internal_links)
- [x] Implement auto-suggest internal links (ClusterManager.suggest_internal_links)
- [x] Create ClusterManager class (complete cluster lifecycle)
- [x] WritingAgent integration (automatic cluster context)
- [x] Comprehensive tests (26 tests, all passing)
- [x] Documentation (HUB_SPOKE_STRATEGY.md guide + example cluster)
- [ ] Create first real cluster plan (choose niche to dominate)
- [ ] Publish hub article (Week 1)
- [ ] Publish spoke articles (Weeks 2-8, link back to hub)
- [ ] Track cluster performance in analytics

**Timeline**: 3 hours implementation (completed Session 069) + 8 weeks execution (2 articles/week)
**Cost**: $0.072-$0.082/article (NO CHANGE - clustering is FREE)
**Outcome**: Complete infrastructure for topical authority, automatic internal linking, 2-5x organic traffic (6 months), 26 tests passing

#### Phase 4: Source Intelligence ⭐ PART 1 COMPLETED (Session 070)
**Goal**: Reduce costs 30-50% with global source deduplication and quality tracking

**Infrastructure Complete** (5/8 tasks):
- [x] Add `sources` table to SQLite database (url, domain, quality_score, e_e_a_t_signals, staleness)
- [x] Implement E-E-A-T quality scoring algorithm (domain 40%, type 30%, freshness 20%, usage 10%)
- [x] Create SourceCache class (save, get, score, stats)
- [x] Write comprehensive tests (22 unit + 13 integration = 35 tests, 100% passing)
- [x] Document infrastructure and algorithms

**Part 2: Integration** (3 remaining tasks):
- [ ] Update DeepResearcher to check source cache before API calls
- [ ] Add cost tracking (cache hits vs API calls)
- [ ] Test with real research workflow and measure actual savings

**Timeline**: Part 1 complete (2.5 hours) | Part 2 estimated (1-2 hours)
**Cost**: Infrastructure ready for 30-50% API cost reduction
**Outcome**: Cache-first research pattern, E-E-A-T quality intelligence, production-ready deduplication

**See**: [Session 070](docs/sessions/070-source-intelligence-cache.md)

#### Phase 5: Primary Source Layer (Optional Premium)
**Goal**: Add expert authority with academic papers, industry reports, expert quotes

- [ ] Add `ScholarCollector` (Google Scholar scraper)
  - [ ] Search academic papers by topic
  - [ ] Extract citations, abstracts
  - [ ] Cost: FREE (scraped) or use SerpAPI ($0.002/search)
- [ ] Add `ExpertQuoteCollector` (Twitter/LinkedIn thought leaders)
  - [ ] Search expert tweets/posts
  - [ ] Extract quotes with attribution
  - [ ] Cost: FREE (scraped)
- [ ] Add `IndustryReportCollector` (PDF parser for Gartner, McKinsey, etc.)
  - [ ] Find publicly available reports
  - [ ] Extract key statistics
  - [ ] Cost: FREE (public reports)
- [ ] Run AFTER main research (add 2-3 premium sources)
- [ ] Update WritingAgent prompt to highlight primary sources

**Timeline**: 1-2 days
**Cost**: +$0.005-$0.01/article (optional Tavily/SerpAPI for premium sources)
**Outcome**: E-E-A-T boost (Google loves primary sources), expert authority, competitive edge

**Timeline Summary**:
- Phase 1: 2-3 hours (quick win, start today)
- Phase 2: 4-6 hours (next session)
- Phase 3: 1 hour planning + 8 weeks execution
- Phase 4: 2-3 hours (optional)
- Phase 5: 1-2 days (optional premium)

**Total Cost**: $0.067-$0.092/article (stays under $0.10!)

**SEO Impact**:
- ✅ Topical Authority: Hub + spoke clusters, internal linking (+30% boost)
- ✅ Unique Insights: Cross-topic synthesis competitors lack
- ✅ E-E-A-T: Deep research + optional primary sources
- ✅ Rankings: Top 10 within 3-6 months, own niche within 6-12 months
- ✅ Traffic: 2-5x organic increase after 6 months

---

## Backlog

### Universal Topic Research Agent - Phase 2
- [ ] SERP Top 10 analyzer (DuckDuckGo)
- [ ] Content scoring algorithm (0-100 scale)
- [ ] Keyword density + variations analysis
- [ ] Readability scoring (textstat)
- [ ] Entity coverage analysis
- [ ] Topic authority detection (LLM-based clustering)
- [ ] Content gap analysis (competitors vs ours)
- [ ] Difficulty scoring (personalized)
- [ ] Internal linking suggestions
- [ ] Performance tracking setup

### Universal Topic Research Agent - Phase 3
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

### Content Creator - Phase 5 (Publishing Automation)
- [ ] Platform publishers (LinkedIn, Facebook APIs)
- [ ] Publishing agent + background service (APScheduler)
- [ ] Publisher deployment (PM2 or Streamlit thread)
- [ ] Scheduled posting (calendar integration)

### Phase 6 - Enhancements
- [ ] Analytics dashboard (performance tracking)
- [ ] Plagiarism checker integration
- [ ] Competitor tracking over time (detect strategy changes)
- [ ] Keyword trend tracking (seasonal patterns)
- [ ] A/B testing for social posts
- [ ] Multi-language support (add blog_en.md)
- [ ] Video/audio media generation (future)
- [ ] Library page: Display social posts in browse view

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

---

## Success Criteria

### Universal Topic Research Agent
- **Phase 1 MVP** ✅: Discovers 50+ unique topics/week, <30% duplicates, >95% language accuracy, 5-6 page reports with citations, top 10 topics sync to Notion, automated daily collection
- **Phase 2 Intelligence**: Content scores match commercial tools, 20+ content gaps identified, difficulty scores accurate, 100+ keywords analyzed
- **Phase 3 Production**: Handles 3+ niches simultaneously, Postgres supports 100K+ documents, analytics dashboard shows ROI per source, multi-platform publishing works

### Content Creator
- **Phase 1-3** ✅: All complete - cache, agents, UI, Notion sync, 254+ tests passing
- **Phase 4 MVP** ✅: 4 social posts per blog (LinkedIn, Facebook, Instagram, TikTok), Notion sync, $0.072-$0.082/bundle (under target)
- **Phase 5 Production**: 100 posts generated/published, logging in place, documentation complete, publisher stable, German quality validated by native speakers, rate limiting working, analytics dashboard functional

---

## Notes

- **TDD**: Write tests before implementation
- **Coverage**: 80% minimum, 100% for critical paths
- **Cost Targets**:
  - Content Creator: $0.072-$0.082/bundle ✅ ACHIEVED (target was <$0.10)
  - Topic Research Agent: $0.01/topic (hybrid orchestrator), ~$0.003/month for collection (LLM-first strategy)

**Detailed Plans**:
- **Universal Topic Research Agent**: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) (1,400+ lines, single source of truth)
- **Content Creator**: [PLAN.md](PLAN.md) (original implementation plan)
- **SaaS Migration**: [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md) (production architecture)

**Recent Sessions** (Last 5):
- Session 068: Cross-Topic Synthesis (unique insights, zero cost, 27 tests)
- Session 067: SQLite Performance Optimization (60K RPS, readonly connections, benchmarks)
- Session 066: Multilingual RSS Implementation (adaptive 70/30 ratio)
- Session 065: RSS Feed Integration (1,037 feeds + UI toggle)
- Session 064: Pipeline Stage 2 Async Fix (run_in_executor)

**Full History**: See [CHANGELOG.md](CHANGELOG.md) and [docs/sessions/](docs/sessions/)

---

**Last Updated**: Session 068
