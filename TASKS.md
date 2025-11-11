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

## High Priority - Content Creator Phase 4.5: Media Generation (Sessions 044-047)

**Goal**: Automated 3-image generation (1 HD hero + 2 standard supporting) with tone-appropriate styling

**Status**: ✅ COMPLETE + QUALITY FIXES (9.8/18.5 hours - 47% faster than estimated) - Production Ready

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

**Per Topic** (Updated Session 047 - Flux Migration):
- Research + Synthesis: $0.01
- Hero Image (Flux 16:9, 2048x2048): $0.04
- 2 Supporting (Flux 1:1, 2048x2048): $0.08
- **Total: $0.13/topic** ⚠️ (Exceeds $0.10 budget by 30%, but improved from $0.17 with DALL-E 3)

**Monthly (200 topics)**:
- All with images: $26.00 (was $34.00 with DALL-E 3)
- 50% with images: $14.00 (was $18.00)
- 10% with images: $3.40 (was $4.40)

**Quality**: Flux RAW MODE delivers photorealistic images (user: "much better!!") vs DALL-E 3's "3D comic-style"

### Implementation Order (TDD)
- ✅ **Phase 1-2 (3.5h)**: Config + Tone Propagation (Session 044)
- ✅ **Phase 3 (1.5h)**: ImageGenerator Core + DALL-E (Session 045)
- ✅ **Phase 4 (0.5h)**: Synthesizer Integration (Session 046)
- ✅ **Phase 5 (0.5h)**: Streamlit UI (Session 046)
- ✅ **Phase 6 (0.5h)**: Notion Sync (Session 046)
- ✅ **Phase 7 (0.8h)**: E2E Tests (Session 046)
- ✅ **Phase 8 (2.5h)**: Quality Improvements - Flux Migration + RAW Enhancements (Session 047)

**Total**: 18.5 hours estimated → 9.8 hours actual (47% faster) ✅ ALL PHASES COMPLETE + QUALITY FIXES

### Success Criteria
- ✅ Tone extracted from Stage 1 and propagated to synthesis
- ✅ 3 images generated per topic (1 HD hero + 2 standard supporting)
- ✅ Tone-appropriate prompts (no anime on business blogs)
- ✅ Silent failure (research completes even if images fail)
- ✅ 3-tier control: Config → API → UI
- ✅ All images sync to Notion
- ✅ Cost tracking accurate ($0.13/topic with Flux)
- ✅ E2E test validates full flow
- ✅ **NEW (Session 047)**: Photorealistic quality (Flux RAW MODE)
- ✅ **NEW (Session 047)**: Supporting images use actual article sections (not generic aspects)
- ✅ **NEW (Session 047)**: Crisp RAW photography aesthetic (safety_tolerance: 5)
- ✅ **NEW (Session 047)**: Notion sync handles unlimited blog post length (auto-chunked at 100 blocks)

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
