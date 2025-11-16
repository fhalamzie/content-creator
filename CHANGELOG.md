# Changelog

Recent development sessions (last 3 sessions, <100 lines).

## Session 064: Pipeline Stage 2 Async Fix (2025-11-16)

**BUGFIX (2 hours, awaiting verification)** - Fixed Stage 2 hang using run_in_executor() instead of asyncio.to_thread()

**Objective**: Fix "Discover Topics" pipeline hanging at Stage 2 (33% progress) during competitor research with Gemini API grounding.

**Root Cause**: Nested event loop deadlock - Streamlit's `asyncio.run()` + `asyncio.to_thread()` + Gemini SDK HTTP timeout caused threading incompatibility.

**Solutions**:
- ✅ **Async Pattern Fix** (`hybrid_research_orchestrator.py:630-643`) - Replaced `asyncio.to_thread()` with `loop.run_in_executor()` for better compatibility with `asyncio.run()`
- ✅ **Fresh Agent Instances** (`hybrid_research_orchestrator.py:621-628`) - Create fresh `GeminiAgent` per call (not lazy-loaded) to avoid initialization deadlocks
- ✅ **Enhanced Logging** (`gemini_agent.py:222-232`, `hybrid_research_orchestrator.py:629-643`) - Track async execution flow for debugging
- ✅ **JSON Parser Fix** (`json_parser.py:60-104`) - Balanced brace-matching for deeply nested arrays
- ✅ **Timeout Safety** (`pipeline_automation.py:242-275`) - 30s timeout + skip checkbox as fallback

**Evidence**: Direct Gemini API tests proved API works perfectly (3s simple, 4.4s grounded). Issue was async/threading pattern, not Gemini.

**Impact**: Stage 2 should now complete in 5-10s. Pipeline can discover topics without hanging. User verification pending.

**Files**: 2 modified (hybrid_research_orchestrator.py +27, gemini_agent.py +3), 1 enhanced (json_parser.py from earlier), 30 total lines.

**See**: [Full details](docs/sessions/064-pipeline-stage2-async-fix.md)

---

## Session 063: S3 Storage Integration for All Images (2025-11-16)

**INFRASTRUCTURE UPGRADE (1.5 hours, 100%)** - Centralized ALL images on S3 with structured folders, SaaS-ready, $0.0849/article (+0.5% cost)

**Objective**: Replace Replicate CDN URLs and base64 data URLs with permanent S3 URLs for all generated images, enabling full storage control and multi-tenant folder structure.

**Solutions**:
- ✅ **Structured S3 Paths** - `{user_id}/{article-slug}/{type}/{filename}` (hero, supporting/, comparison/, platform/)
- ✅ **Slug Generation** (`image_generator.py:224-262`) - URL-safe slugs with German umlaut support (ä→ae, ö→oe, ü→ue)
- ✅ **Download-Upload Helper** (`image_generator.py:264-344`) - Downloads from Replicate, uploads to S3, returns public URL
- ✅ **Hero Images** - S3 upload after Flux 1.1 Pro Ultra generation (`image_generator.py:767-792`)
- ✅ **Supporting Images** - S3 upload after Flux Dev generation with aspect hash (`image_generator.py:843-880`)
- ✅ **Platform OG Images** - S3 upload for Pillow-generated images (`platform_image_generator.py:245-356`)
- ✅ **Comparison Images** - Already S3 (Session 062), now with structured paths (`image_generator.py:997-1047`)

**Features**: Permanent S3 URLs (<120 chars, Notion-compatible), graceful fallback to Replicate/base64 on S3 failure, multi-tenant folder structure (user_id placeholder), German/international character support in slugs, centralized storage for future logo/asset uploads.

**Impact**: Full control over image storage (no Replicate CDN dependency), SaaS-ready folder structure (replace "default" with user_id), all Notion image URLs <2000 chars, permanent URLs that never expire, +$0.001/article (~0.5%) for S3 bandwidth/storage.

**Files**: 2 modified (image_generator.py +124, platform_image_generator.py +95), 219 total lines added.

**Storage**: First 10GB free on Backblaze B2 (~5000 blog posts), negligible bandwidth cost ($0.01/GB).

**See**: [Full details](docs/sessions/063-s3-storage-integration.md)

---

## Session 062: Repurposing Agent Phases 4-5 - Notion Sync + Streamlit UI (2025-11-16)

**PRODUCTION READY (4 hours, 100%)** - Full end-to-end social automation with Notion sync, Streamlit UI, 30 passing tests, $0.0066/blog social cost

**Objective**: Complete Repurposing Agent by adding Notion sync (Phase 4) and Streamlit UI integration (Phase 5) for full social media automation.

**Solutions**:
- ✅ **SocialPostsSync Class** (353 lines, 22 tests) - Single/batch sync, property mapping (title, platform, content, hashtags, media URL, blog relation), rate limiting (2.5 req/sec), statistics tracking
- ✅ **Quick Create Integration** (+80 lines) - Added social posts checkbox, 5-stage pipeline (research→writing→blog images→**social posts**→Notion), cost estimates ($0.0092 social), 4 preview tabs (💼 LinkedIn, 👥 Facebook, 📸 Instagram, 🎵 TikTok)
- ✅ **E2E Pipeline Tests** (535 lines, 8 tests) - Full pipeline (text/images/Notion), partial failure handling, multilingual (de/en), cost breakdown verification, error handling

**Features**: Full end-to-end automation (blog→social→Notion), platform-specific tabs with content/hashtags/images/costs, smart OG reuse (50% savings), backward compatible (optional social posts), batch Notion sync with retry logic.

**Impact**: Users can generate complete blog + 4 social bundles with one click, preview all content, sync to Notion automatically. Full social automation now production-ready with $0.072-$0.082 total cost per article.

**Files**: 3 new (social_posts_sync.py 353, test_social_posts_sync.py 580, test_repurposing_pipeline_e2e.py 535), 1 modified (quick_create.py +80), 1,548 total lines.

**Testing**: 30 tests (22 unit + 8 E2E), 100% pass rate, 13.8s total execution, verified cost tracking ($0.0066 social posts).

**Cost**: $0.0066/blog social (LinkedIn $0.00015, Facebook $0.00015, Instagram $0.00315, TikTok $0.00315), $0.072-$0.082 total per article with all features.

**See**: [Full details](docs/sessions/062-repurposing-phases4-5-notion-ui.md)

---

*Older sessions (061-063) archived in `docs/sessions/` directory*
