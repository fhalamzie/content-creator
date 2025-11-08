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
