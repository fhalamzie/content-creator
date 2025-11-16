# Tasks

## Current Status (Session 066)

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

Pick ONE direction for Session 063+:

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

### Option 5: RSS Feed Discovery System
**Goal**: Build automated RSS feed database for topic discovery

**See [RSS.md](RSS.md) for complete plan**

- [ ] Phase 1: Bootstrap 500 quality feeds from awesome-rss-feeds (GitHub)
- [ ] Phase 2: Scale to 10,000+ feeds from AllTop OPML exports
- [ ] Phase 3: Automated maintenance, validation, and analytics

**Timeline**:
- Phase 1: 1-2 days
- Phase 2: 3-5 days
- Phase 3: Ongoing (1-2 hours/week)

**Cost**: $0 for bootstrap, <$5/month for maintenance

**Outcome**:
- Enable RSS collector with 10K+ curated feeds
- Organize feeds by 100+ verticals (tech/saas, business/marketing, health/medicine, etc.)
- Automatic feed selection based on keywords
- +20-30% topic diversity improvement

### Option 6: Topical Authority Stack ⭐ RECOMMENDED
**Goal**: Build niche dominance with unique, SEO-optimized content using cross-topic synthesis

**Strategy**: Eliminate duplicate research, synthesize insights across related topics, build hub+spoke clusters

**Current Gap**: Two research systems don't connect:
- Quick Create uses simple ResearchAgent (basic web search)
- Hybrid Orchestrator creates deep $0.01 reports but they're NOT used for writing

**Cost Impact**: $0.067-$0.092/article (saves 7% or adds 6% with premium features, stays under $0.10!)

#### Phase 1: Connect Research → Writing ⭐ START HERE
**Goal**: Eliminate duplicate research, use deep $0.01 reports for writing

- [ ] Add cache lookup helper function (`load_cached_research()`)
- [ ] Update Quick Create to check `cache/research/` before researching
- [ ] Fallback to Hybrid Orchestrator if topic not cached
- [ ] Update WritingAgent to use structured deep research better
- [ ] Test with existing cached research reports
- [ ] Verify cost savings (no duplicate research)

**Timeline**: 2-3 hours
**Cost**: $0 (FREE, just connects existing systems)
**Outcome**: Writing agent gets 5-source deep research instead of simple search, better E-E-A-T

#### Phase 2: Cross-Topic Synthesis
**Goal**: Create unique insights competitors lack by synthesizing related topics

- [ ] Add semantic search to DatabaseManager (find related cached reports)
- [ ] Create `CrossTopicSynthesizer` class
  - [ ] Find 3-5 related topics using keyword/MinHash similarity
  - [ ] Extract key insights from each (themes, gaps, predictions)
  - [ ] Create synthesis summary (unique angles)
- [ ] Update WritingAgent prompt template to accept "Related Context"
- [ ] Test synthesis quality (verify unique insights)
- [ ] Measure uniqueness (compare to competitor articles)

**Timeline**: 4-6 hours
**Cost**: $0 (FREE, just cache reads)
**Outcome**: Unique perspectives from cross-topic connections, topical authority signals, natural internal linking

#### Phase 3: Hub + Spoke Strategy
**Goal**: Organize 2 articles/week into topical clusters for SEO dominance

- [ ] Create cluster planning template in Notion
  - [ ] Hub article (3000 words, comprehensive pillar)
  - [ ] 7 spoke articles (1500-2500 words each, specific angles)
  - [ ] Internal linking map (hub ↔ spokes)
- [ ] Add `cluster_id` field to Blog Posts database
- [ ] Implement auto-suggest internal links based on cluster
- [ ] Create first cluster plan (choose niche to dominate)
- [ ] Publish hub article (Week 1)
- [ ] Publish spoke articles (Weeks 2-8, link back to hub)
- [ ] Track cluster performance in analytics

**Timeline**: 1 hour planning + 8 weeks execution (2 articles/week)
**Cost**: Same as current ($0.072-$0.082/article)
**Outcome**: Topical authority, internal linking boost, owned niche, 2-5x organic traffic (6 months)

#### Phase 4: Source Intelligence (Optional)
**Goal**: Reduce costs, improve quality with global source deduplication

- [ ] Add `sources` table to SQLite database
  - [ ] Fields: url, title, content, topics, fetched_at, reliability_score, e_e_a_t_signals
- [ ] Update collectors to check cache before fetching
- [ ] Add quality scoring algorithm
  - [ ] Domain authority signals
  - [ ] Freshness scoring
  - [ ] Citation count
  - [ ] E-E-A-T signals (author expertise, publication authority)
- [ ] Prefer high-quality cached sources in research
- [ ] Track cost savings from deduplication

**Timeline**: 2-3 hours
**Cost**: SAVINGS (fewer API calls, faster research)
**Outcome**: Fetch once, use many times; track source quality; enable richer synthesis

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
- Session 062: Repurposing Agent Phases 4-5 (Notion sync + UI)
- Session 061: Repurposing Agent Phase 3 (Integration complete)
- Session 060: Repurposing Agent Phases 2-3 (OG + Platform images)
- Session 059: Repurposing Agent Phase 1 (Platform content optimization)
- Session 058: Research Lab Phase 4 (Competitor comparison matrix)

**Full History**: See [CHANGELOG.md](CHANGELOG.md) and [docs/sessions/](docs/sessions/)

---

**Last Updated**: Session 066
