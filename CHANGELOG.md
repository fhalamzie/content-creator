# Changelog

Recent development sessions (last 3 sessions, <100 lines).

## Session 048: Image Quality Enhancements & Multilingual Architecture (2025-11-11)

**OPTIMIZATION (3.5 hours)** - Improved image quality, 60% cost reduction via mixed models, dynamic supporting images, multilingual system prompts

**Problem**: RAW mode producing dull images, high costs ($0.19/article), fixed 2 supporting images, unpredictable safety tolerance (6), no German text specification.

**Solutions**:
- ✅ **RAW Mode Disabled**: Changed `raw: False` (was `True`) → polished, vibrant images (not dull candid style)
- ✅ **Safety Tolerance**: Reduced 6 → 4 (good diversity, professional predictability, prevents inappropriate styles)
- ✅ **Mixed Models**: Hero = Flux Ultra ($0.06), Supporting = Flux Dev ($0.003, 95% cheaper)
- ✅ **Dynamic Supporting Images**: 0-2 based on H2 section count (≤3 sections → 0, 4-5 → 1, 6+ → 2)
- ✅ **German Text in Images**: Explicit language requirement for UI elements, captions, signs
- ✅ **Multilingual Architecture**: English system prompts + language parameter (industry standard, scalable to N languages)
- ✅ **Correct Pricing**: Updated $0.04 → $0.06 per Flux Ultra image (Replicate official pricing)

**Cost Impact**: 60% reduction - Short articles $0.07 (was $0.19), Medium $0.073, Long $0.076. Monthly (10 articles): $0.75 (was $1.90).

**Quality**: Premium hero (4MP Ultra), good supporting (2MP Dev), more polished/predictable style, German language support.

**Architecture**: Multilingual ready - add languages via config (`language: es`) without code changes.

**See**: [Full details](docs/sessions/048-image-quality-enhancements-multilingual-architecture.md)

---

## Session 047: Flux Migration & Image Quality Improvements (2025-11-10)

**CRITICAL FIX (2.5 hours)** - Migrated from DALL-E 3 to Flux 1.1 Pro Ultra RAW MODE, fixed image quality + Notion sync

**Problem**: DALL-E 3 producing "3D comic-style" images despite optimization attempts, supporting images using generic aspects, writing agent failing with empty responses, Notion sync failing on blog posts >100 blocks.

**Solutions**:
- ✅ **Flux Migration**: Switched to Flux 1.1 Pro Ultra with RAW MODE via Replicate API for authentic photorealism ($0.04/image, same cost)
- ✅ **Writing Agent Fix**: Changed model from `qwen3-235b-a22b` → `qwen3-235b-a22b-2507` (non-reasoning variant, no empty responses)
- ✅ **Topic Extraction Fix**: Added `topic` parameter to `generate_supporting_images()`, passed directly from UI to avoid markdown parsing errors
- ✅ **Section-Based Aspects**: 4-tier extraction (H2 → H3 → paragraphs → topic+context), supporting images now use actual article headings instead of "key benefits"
- ✅ **RAW Photography Prompts**: Enhanced Qwen prompts with "RAW + CRISP + IMPERFEKT", balanced subject matter (not always humans), 3 diverse examples
- ✅ **Safety Tolerance**: Increased from 2 → 5 (more diverse/raw outputs)
- ✅ **Notion Block Chunking**: Automatic chunking for blog posts >100 blocks (103-block post now works)
- ✅ **Streamlit Restart Discipline**: Established restart workflow (critical - cached code was preventing improvements from taking effect)

**Quality Impact**: User feedback: "still total shit" → "much better!!" → "more crisp and raw results" (continuation improvements).

**Technical Details**: Replicate client, 2048x2048 resolution, PNG output, 8-10s generation, safety_tolerance: 5, Notion auto-chunking at 100 blocks.

**See**: [Full details](docs/sessions/047-flux-migration-image-quality-improvements.md)

---

## Session 046: Media Generation - Phases 4-7 (Integration & E2E Testing) (2025-11-08)

**Feature COMPLETE (2.3/10.5 hours)** - 78% faster than estimated, production ready with 100% E2E coverage

**Implementation**:
- ✅ Phase 4 (Synthesizer): `_generate_article_images()` method with hero + 2 supporting images, silent failure on errors
- ✅ Phase 5 (Streamlit UI): 5-tab display (Hero, Support 1-2, Sources, Article), image generation checkbox, cost breakdown ($0.16 images + $0.01 synthesis)
- ✅ Phase 6 (Notion): Added `hero_image_url` (URL) + `supporting_images` (JSON) fields to Topic model + TOPICS_SCHEMA, TopicsSync mapping
- ✅ Phase 7 (E2E Tests): 4 comprehensive tests (2 live API with skip markers, 2 fully mocked), complete pipeline validation

**Test Results**: ✅ 4/4 E2E tests passing, ✅ 41/41 total tests (no regressions), ✅ Live validation: 544 words + 3 images in 62s for $0.16

**TDD Success**: Tests written before implementation, mocked tests always runnable (CI/CD safe), live tests with conditional skip markers

**Live Validation**: Images enabled (544 words, 3 images, $0.16, 62s) ✅, Images disabled (583 words, 0 images, $0.00, 13s) ✅, Silent failure handling ✅, Notion sync ✅

**Status**: ✅ ALL 7 PHASES COMPLETE - Feature production ready, full pipeline validated (research → images → synthesis → UI → Notion)

**See**: [Full details](docs/sessions/046-media-generation-phase4-7-integration.md)

---

## Session 045: Media Generation - Phase 3 (ImageGenerator Module) (2025-11-08)

**Phase 3 of 7 Complete (5/18.5 hours)** - DALL-E 3 integration with 7-tone prompt mapping

**Implementation**:
- ✅ ImageGenerator class (347 lines): DALL-E 3 integration, 7-tone mapping, retry logic, cost tracking
- ✅ 7-tone prompt system: Professional, Technical, Creative, Casual, Authoritative, Innovative, Friendly
- ✅ Hero image: 1792x1024 HD ($0.08), Supporting: 1024x1024 Standard ($0.04)
- ✅ Silent failure: 3 retries with 2s delay, returns None on error (research continues)
- ✅ API key loading from `/home/envs/openai.env` with environment variable fallback
- ✅ Full async support using AsyncOpenAI client

**Test Results**: ✅ 23/23 tests passing (115% of 20-test goal), ✅ 26/26 existing tests (no regressions)

**TDD Success**: Tests written first, zero bugs on first full run, comprehensive coverage

**Status**: Phase 3 COMPLETE (1.5h vs 6h estimated - 75% faster), Phase 4-7 pending (Synthesizer integration, UI, Notion sync, E2E)

**See**: [Full details](docs/sessions/045-media-generation-phase3-image-generator.md)

---

*Older sessions (044-047) archived in `docs/sessions/` directory*
