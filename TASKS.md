# Tasks

## 🔥 URGENT - Next Steps

- [ ] **Enable Stage 3 (Deep Research) in ContentPipeline** - Abstraction layer ready
  - Change `enable_deep_research=False` to `True` in `src/agents/content_pipeline.py:73`
  - Abstraction layer fixes all 3 gpt-researcher bugs (Session 020 continuation)
  - Primary method: gpt-researcher with OpenAI (gpt-4o-mini, $0.006/research)
  - Fallback: Gemini CLI (when quota resets tomorrow 2025-11-05)
  - Test with: `python /tmp/test_gpt_researcher_fixed.py`
  - Verify full 5-stage pipeline works end-to-end
  - Optional: Configure TAVILY_API_KEY for web search (not required)

## High Priority (Universal Topic Research Agent - Phase 1)

**See**: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for complete plan (1,400+ lines)

**Week 1: Foundation** ✅ **COMPLETE** (7/7, 100%):
- [x] Central logging system (`src/utils/logger.py` with structlog) ✅
- [x] Unified `Document` model (`src/models/document.py`) ✅
- [x] Configuration system (`src/utils/config_loader.py`) ✅
- [x] Example configs (`config/markets/proptech_de.yaml`, `fashion_fr.yaml`) ✅
- [x] SQLite schema (documents, topics, research_reports tables) ✅
- [x] LLM processor (`src/processors/llm_processor.py` - qwen-turbo via OpenRouter) ✅
- [x] Deduplicator (`src/processors/deduplicator.py` - MinHash/LSH) ✅
- [x] Huey task queue setup (`src/tasks/huey_tasks.py`) ✅

**Week 1 Metrics**: 160 tests passing, 94.67% coverage, 100% TDD compliance

**Week 2: Core Collectors** ✅ **COMPLETE** (10/10, 100%):
- [x] Feed discovery (`src/collectors/feed_discovery.py`) - 558 lines, 21 tests, 92.69% coverage ✅
- [x] RSS collector (`src/collectors/rss_collector.py`) - 606 lines, 26 tests, 90.23% coverage ✅
- [x] Reddit collector (`src/collectors/reddit_collector.py`) - 517 lines, 21 tests, 85.71% coverage ✅
- [x] **Trends collector** (`src/collectors/trends_collector.py`) - 782 lines, 26 tests ✅ **MIGRATED to Gemini CLI** (Nov 2025)
- [x] Autocomplete collector (`src/collectors/autocomplete_collector.py`) - 454 lines, 23 tests, 93.30% coverage ✅
- [x] **Topic clustering** (`src/processors/topic_clusterer.py`) - 343 lines, 22 tests ✅ **NEW** (TF-IDF + HDBSCAN + LLM)
- [x] **Entity extractor** (`src/processors/entity_extractor.py`) - 197 lines, 14 tests ✅ **NEW** (LLM-based NER)
- [x] **Deep research wrapper** (`src/research/deep_researcher.py`) - 279 lines, 12 tests ✅ **NEW** (gpt-researcher + Gemini)
- [x] **Notion topics sync** (`src/notion_integration/topics_sync.py`) - 327 lines, 15 tests ✅ **NEW** (rate-limited sync)
- [x] **5-stage content pipeline** (`src/agents/content_pipeline.py`) - 572 lines, 19 tests, 94.41% coverage ✅ **INTEGRATED** (UI + Gemini CLI fixes)

**Week 2: E2E Testing** (Required for ALL components):
- [x] Feed Discovery E2E - Integration test with real config ✅
- [x] RSS Collector E2E - 13 integration tests with real feeds (Heise.de, GitHub Atom) ✅
- [x] Reddit Collector E2E - 11 integration tests with real subreddits (r/de, r/Python) ✅
- [x] **Trends Collector E2E** - 11 integration tests ✅ **Gemini CLI backend** (no rate limits!)
- [x] Autocomplete Collector E2E - 12 integration tests (alphabet, questions, prepositions, multi-keyword) ✅
- [ ] Topic clustering E2E - Test clustering on real document set (optional - unit tests comprehensive)
- [ ] Full Pipeline E2E - Feed Discovery → RSS Collection → Dedup → Clustering → Deep Research → Notion Sync
- [x] **ContentPipeline UI Integration** - Streamlit Topic Research page with 5-stage processing ✅ **NEW** (Session 018)
- [ ] Playwright E2E (if UI components exist) - Test Streamlit UI for topic review
- [ ] API Endpoint E2E - Test Huey task queue endpoints (daily collection, sync)

**Acceptance Criteria** (Validated via E2E Tests):
- [ ] Discovers 50+ unique topics/week for test config (E2E: Full pipeline)
- [ ] Deduplication rate <5% (E2E: RSS collector with known duplicates)
- [ ] Language detection >95% accurate (E2E: Multi-language document set)
- [ ] Deep research generates 5-6 page reports with citations (E2E: Real topic research)
- [ ] Top 10 topics sync to Notion successfully (E2E: Notion API integration)
- [ ] Runs automated (daily collection at 2 AM) (E2E: Huey cron trigger test)

## High Priority (Content Creator - Phase 4: Repurposing Agent)

- [ ] Write tests + implement `src/agents/repurposing_agent.py`
- [ ] Social post templates (LinkedIn, Facebook, TikTok, Instagram)
- [ ] Hashtag generation (platform-specific)
- [ ] Media suggestions (image descriptions for DALL-E 3)
- [ ] Integration with generate page (auto-create social posts)
- [ ] Test social post sync to Notion

## Completed

**Universal Topic Research Agent - Week 1 Foundation (Complete)** ✅ (Session 010):
- [x] Huey Task Queue (82.19% coverage, 36 tests, SQLite backend, DLQ)
- [x] Background tasks: collect_all_sources, daily_collection, weekly_notion_sync
- [x] Dead-letter queue with retry logic (exponential backoff)
- [x] Periodic task scheduling (crontab integration)
- [x] 160 total tests, 94.67% overall coverage (Week 1)
- [x] TDD compliance 100%
- [x] **Week 1: 7/7 components complete (100%)**

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

- **ContentPipeline Stage 3 disabled temporarily** - Abstraction layer ready, awaiting enable
  - Currently disabled: `enable_deep_research=False` (default in ContentPipeline)
  - ✅ **FIXED**: Abstraction layer successfully works around all 3 gpt-researcher bugs
  - Primary: gpt-researcher with OpenAI (gpt-4o-mini, $0.006/research)
  - Fallback: Gemini CLI (when quota resets 2025-11-05)
  - See: Session 020 continuation for abstraction layer implementation
  - Impact: Ready to enable, stages 1,2,4,5 fully functional
- **gpt-researcher bugs workaround via abstraction layer** - ✅ FIXED in Session 020 continuation
  - Bug 1 (Duplicate parameter): Fixed by minimal initialization (only query + report_type)
  - Bug 2 (Missing OPENAI_API_KEY): Fixed by auto-loader from `/home/envs/openai.env`
  - Bug 3 (Langchain conflicts): Fixed by defaulting to openai provider (not google_genai)
  - Solution: Abstraction layer in DeepResearcher.__init__() + simplified GPTResearcher initialization
  - Test: `python /tmp/test_gpt_researcher_fixed.py` (generates 2500+ word reports)
  - See: `src/research/deep_researcher.py:100-124` (OPENAI_API_KEY loader), lines 186-195 (minimal config)
- **LangChain version pinned to <1.0** - Required for current gpt-researcher 0.14.4
  - Breaking change in langchain 1.0 removed `langchain.docstore` module
  - Version pins in `requirements-topic-research.txt` prevent upgrade
  - Abstraction layer avoids google_genai provider (no langchain-google-genai conflict)
  - Will be resolved when gpt-researcher adds langchain 1.0 support
- Notion API limitation: Relation properties require manual configuration in UI
  - Blog Posts → Project (relation)
  - Social Posts → Blog Post (relation)
  - Research Data → Blog Post (relation)
- WritingAgent wraps content in ` ```markdown...``` ` fence (workaround: strip before parsing)
- ~~f-string syntax error in settings.py:282~~ ✅ Fixed (Session 007)
- ~~pytrends Google 404/429 errors~~ ✅ Fixed (Session 015 - migrated to Gemini CLI)
- ~~Gemini CLI hanging issue~~ ✅ Fixed (Session 018 - use stdin input method)

## Technical Debt

- [ ] Fix or upgrade gpt-researcher for Stage 3 (Deep Research) functionality
- [ ] Upgrade langchain to 1.0+ when gpt-researcher supports it
- [ ] Add disk space monitoring for cache directory
- [ ] Test Notion client with pagination (large result sets, >100 pages)
- [x] ~~Remove pytrends dependency~~ ✅ Done (Session 015 - migrated to Gemini CLI)
- [ ] Test German content quality with native speakers
- [ ] Add secret rotation mechanism for API keys
- [ ] Consider cache cleanup strategy (auto-delete old posts)
- [ ] Add retry logic to cache operations (handle disk full errors)
- [x] ~~Gemini CLI hanging issue~~ ✅ Fixed (Session 018 - use stdin input method)
- [x] ~~langchain.docstore import error~~ ✅ Fixed (Session 019 - downgraded to langchain<1.0)

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
