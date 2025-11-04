# Tasks

## High Priority (Universal Topic Research Agent - Phase 1)

**See**: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for complete plan (1,400+ lines)

**Week 1: Foundation** (Current Focus - 6/7 Complete, 85.7%):
- [x] Central logging system (`src/utils/logger.py` with structlog) ✅
- [x] Unified `Document` model (`src/models/document.py`) ✅
- [x] Configuration system (`src/utils/config_loader.py`) ✅
- [x] Example configs (`config/markets/proptech_de.yaml`, `fashion_fr.yaml`) ✅
- [x] SQLite schema (documents, topics, research_reports tables) ✅
- [x] LLM processor (`src/processors/llm_processor.py` - qwen-turbo via OpenRouter) ✅
- [x] Deduplicator (`src/processors/deduplicator.py` - MinHash/LSH) ✅
- [ ] Huey task queue setup (`src/tasks/huey_tasks.py`)

**Week 2: Core Collectors**:
- [ ] RSS collector (`src/collectors/rss_collector.py` - feedparser + trafilatura)
- [ ] Reddit collector (`src/collectors/reddit_collector.py` - PRAW)
- [ ] Trends collector (`src/collectors/trends_collector.py` - pytrends)
- [ ] Autocomplete collector (`src/collectors/autocomplete_collector.py`)
- [ ] Intelligent feed discovery (`src/collectors/feed_discovery.py` - DuckDuckGo SERP)
- [ ] Topic clustering (qwen-turbo batch call)
- [ ] Entity extraction (qwen-turbo)
- [ ] Deep research wrapper (`src/research/deep_researcher.py` - gpt-researcher)
- [ ] 5-stage content pipeline (`src/agents/content_pipeline.py`)
- [ ] Notion sync for topics

**Acceptance Criteria**:
- [ ] Discovers 50+ unique topics/week for test config
- [ ] Deduplication rate <5%
- [ ] Language detection >95% accurate
- [ ] Deep research generates 5-6 page reports with citations
- [ ] Top 10 topics sync to Notion successfully
- [ ] Runs automated (daily collection at 2 AM)

## High Priority (Content Creator - Phase 4: Repurposing Agent)

- [ ] Write tests + implement `src/agents/repurposing_agent.py`
- [ ] Social post templates (LinkedIn, Facebook, TikTok, Instagram)
- [ ] Hashtag generation (platform-specific)
- [ ] Media suggestions (image descriptions for DALL-E 3)
- [ ] Integration with generate page (auto-create social posts)
- [ ] Test social post sync to Notion

## Completed

**Universal Topic Research Agent - Week 1 Foundation (Part 2)** ✅ (Session 009):
- [x] SQLite Manager (97.96% coverage, 22 tests, FTS5, transactions)
- [x] LLM Processor (89.90% coverage, 19 tests, replaces 5GB NLP stack)
- [x] Deduplicator (94.37% coverage, 23 tests, MinHash/LSH)
- [x] 64 total tests, 94.67% overall coverage
- [x] TDD compliance 100%

**Universal Topic Research Agent - Week 1 Foundation (Part 1)** ✅ (Session 008):
- [x] Central Logging System (100% coverage, 20 tests, structlog)
- [x] Document Model (100% coverage, 20 tests, Pydantic V2)
- [x] Configuration System (93.94% coverage, 20 tests, YAML + validation)
- [x] Example configs (proptech_de.yaml, fashion_fr.yaml)
- [x] Config documentation (README.md)
- [x] TDD workflow established (test-first, 96.23% overall coverage)

**Universal Topic Research Agent - Planning** ✅ (Session 008):
- [x] Synthesize 7 planning documents into single IMPLEMENTATION_PLAN.md (1,400+ lines)
- [x] LLM-first strategy design (replace 5GB NLP dependencies with qwen-turbo)
- [x] Intelligent feed discovery architecture (4-stage, zero manual input)
- [x] Modular architecture design (layered, no import circles, DI pattern)
- [x] Central logging system design (structlog)
- [x] Integrate competitor & keyword research agents (already implemented)
- [x] Enhanced 5-stage content pipeline design
- [x] Update requirements-topic-research.txt (LLM-first dependencies)
- [x] Delete redundant planning docs (7 files, ~150KB)
- [x] Document phase 1-3 implementation roadmap

**Research Agents** ✅ (Session 007):
- [x] Write tests + implement `src/agents/competitor_research_agent.py` (100% coverage, 24 tests)
- [x] Write tests + implement `src/agents/keyword_research_agent.py` (100% coverage, 27 tests)
- [x] Create competitor research spec (docs/competitor_research_agent_spec.md)
- [x] Create keyword research spec (docs/keyword_research_agent_spec.md)
- [x] Integrate both agents into generation pipeline (5-stage pipeline)
- [x] Update UI to show enhanced stats (8 metrics: competitors, keywords, gaps)
- [x] Add research data to blog post metadata (competitor + keyword insights)
- [x] Document agent reasoning in README.md (AI Agent Architecture section)

**Phase 3 - Streamlit UI** ✅:
- [x] Create `streamlit_app.py` (main entry point, page routing)
- [x] Setup page (brand voice, target audience, keywords configuration)
- [x] Generate content page (topic input, progress bar, ETA display)
- [x] Content browser (view cached posts, Notion database viewer)
- [x] Fix UI bugs (auto-sync, markdown rendering, JSON mode)
- [x] Settings page (API keys management, rate limits, model selection)
- [x] Dashboard (stats, cost tracking, recent posts)
- [x] Comprehensive UI tests (63 tests, 254 total tests)

**Phase 2 - Core Agents** ✅:
- [x] Create German prompts (blog_de.md, social_de.md) - 2 comprehensive templates
- [x] Write tests + implement `src/agents/base_agent.py` (100% coverage, 25 tests)
- [x] Write tests + implement `src/agents/research_agent.py` (97.06% coverage, 23 tests)
- [x] Write tests + implement `src/agents/writing_agent.py` (97.70% coverage, 22 tests)
- [x] Write tests + implement `src/notion_integration/sync_manager.py` (93.20% coverage, 22 tests)
- [x] Integration tests (11 tests) - Complete pipeline validation
- [x] Enhanced CacheManager (get_cached_blog_posts, get_cached_social_posts, save_blog_post)

**Phase 1 - Foundation** ✅:
- [x] Write tests + implement `src/cache_manager.py` (100% coverage, 24 tests)
- [x] Write tests + implement `src/notion_integration/rate_limiter.py` (100% coverage, 21 tests)
- [x] Write tests + implement `src/notion_integration/notion_client.py` (93.67% coverage, 23 tests)
- [x] Create `config/notion_schemas.py` (5 database schemas, 52 properties)
- [x] Create `config/settings.py` (environment validation, secret masking)
- [x] Implement `setup_notion.py` (5 Notion databases created successfully)
- [x] Test infrastructure (pytest.ini, .coveragerc, 97.70% overall coverage)

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
- [ ] Media creator (DALL-E 3 hero images)
- [ ] Analytics dashboard (performance tracking)
- [ ] Plagiarism checker integration
- [ ] Competitor tracking over time (detect strategy changes)
- [ ] Keyword trend tracking (seasonal patterns)
- [ ] Export competitor analysis to Notion "Competitors" database
- [ ] Export keyword research to Notion "Research Data" database
- [ ] A/B testing for social posts
- [ ] Multi-language support (add blog_en.md)

## Known Issues

- Notion API limitation: Relation properties require manual configuration in UI
  - Blog Posts → Project (relation)
  - Social Posts → Blog Post (relation)
  - Research Data → Blog Post (relation)
- WritingAgent wraps content in ` ```markdown...``` ` fence (workaround: strip before parsing)
- ~~f-string syntax error in settings.py:282~~ ✅ Fixed (Session 007)

## Technical Debt

- [ ] Add disk space monitoring for cache directory
- [ ] Test Notion client with pagination (large result sets, >100 pages)
- [ ] Verify Gemini CLI integration stability (long-term monitoring)
- [ ] Test German content quality with native speakers
- [ ] Add secret rotation mechanism for API keys
- [ ] Consider cache cleanup strategy (auto-delete old posts)
- [ ] Add retry logic to cache operations (handle disk full errors)

## Success Criteria

**Universal Topic Research Agent**:
- **Phase 1 MVP**: Discovers 50+ unique topics/week, <5% duplicates, >95% language accuracy, 5-6 page reports with citations, top 10 topics sync to Notion, automated daily collection
- **Phase 2 Intelligence**: Content scores match commercial tools, 20+ content gaps identified, difficulty scores accurate, 100+ keywords analyzed
- **Phase 3 Production**: Handles 3+ niches simultaneously, Postgres supports 100K+ documents, analytics dashboard shows ROI per source, multi-platform publishing works

**Content Creator**:
- **Phase 1** ✅: All tasks complete, cache system working (100% coverage), Notion connection (rate-limited, 93.67% coverage), 5 databases created, test infrastructure (97.70% coverage)
- **Phase 2** ✅: German prompts created (2 templates), base agent working (100% coverage), research agent (Gemini CLI, 97.06% coverage), writing agent (Qwen3-Max, 97.70% coverage), sync manager (cache → Notion, 93.20% coverage), integration tests passing (11 tests), 171 total tests, 94.87% overall coverage
- **Phase 3** ✅: Streamlit UI functional (all 5 pages: setup, generate, browse, settings, dashboard), progress tracking working, ETA display accurate, cost tracking visible, Notion integration seamless, 254 tests passing
- **Phase 4 MVP**: Generate 10 German blog posts via UI, cache sync to Notion, edit in Notion, 4 social posts per blog (repurposing agent), cost target achieved (~$0.98/bundle), basic publishing working
- **Phase 5 Production**: 100 posts generated/published, logging in place, documentation complete, publisher stable, German quality validated by native speakers, rate limiting working, analytics dashboard functional

## Notes

- **TDD**: Write tests before implementation
- **Coverage**: 80% minimum, 100% for critical paths
- **Cost Targets**:
  - Content Creator: ~$0.98/bundle
  - Topic Research Agent: ~$0.003/month for MVP (LLM-first strategy)

**Detailed Plans**:
- **Universal Topic Research Agent**: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) (1,400+ lines, single source of truth)
- **Content Creator**: [PLAN.md](PLAN.md) (original implementation plan)
