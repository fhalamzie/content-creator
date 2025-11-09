# Changelog

Recent development sessions (last 3 sessions, <100 lines).

## Session 047: Flux Migration & Image Quality Improvements (2025-11-10)

**CRITICAL FIX (2 hours)** - Migrated from DALL-E 3 to Flux 1.1 Pro Ultra RAW MODE, fixed image quality + supporting image relevance

**Problem**: DALL-E 3 producing "3D comic-style" images despite optimization attempts (style="natural", German prompts, Qwen expansion), supporting images using generic aspects instead of article sections, writing agent failing with empty responses.

**Solutions**:
- ✅ **Flux Migration**: Switched to Flux 1.1 Pro Ultra with RAW MODE via Replicate API for authentic photorealism ($0.04/image, same cost)
- ✅ **Writing Agent Fix**: Changed model from `qwen3-235b-a22b` → `qwen3-235b-a22b-2507` (non-reasoning variant, no empty responses)
- ✅ **Topic Extraction Fix**: Added `topic` parameter to `generate_supporting_images()`, passed directly from UI to avoid markdown parsing errors
- ✅ **Section-Based Aspects**: 4-tier extraction (H2 → H3 → paragraphs → topic+context), supporting images now use actual article headings instead of "key benefits"
- ✅ **Streamlit Restart Discipline**: Established restart workflow (critical - cached code was preventing improvements from taking effect)

**Quality Impact**: User feedback progression: "still total shit" → "much better!!" (Flux), supporting images now article-specific.

**Technical Details**: Replicate client, 2048x2048 resolution (up from 1792x1024), PNG output, 8-10s generation, RAW MODE for authentic photography aesthetic.

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

## Session 044: Media Generation - Phase 1-2 (Config + Tone Propagation) (2025-11-08)

**Phase 1-2 of 7 Complete (3.5/18.5 hours)** - Image generation foundation established

**Implementation**:
- ✅ Added 4 image config fields to MarketConfig: `brand_tone`, `enable_image_generation` (default ON), `image_quality` (hd/standard), `image_style_preferences`
- ✅ Tone propagation: Stage 1 website analysis → Stage 5 synthesis (brand_tone parameter flows through pipeline)
- ✅ 3-tier control system: Market config (default ON) → Python API (optional override) → Streamlit UI (final say, pending Phase 5)
- ✅ Updated `research_topic()` + `synthesize()` signatures with `brand_tone` and `generate_images` parameters
- ✅ Config inheritance: `generate_images=None` inherits from `enable_image_generation` market setting

**Key Discovery**: Tone analysis already exists in Stage 1! No need to build separate analyzer - just propagate existing data.

**Test Results**: ✅ 26/26 tests passing (23 config + 3 tone propagation), no regressions

**Status**: Phase 1-2 COMPLETE, Phase 3-7 pending (ImageGenerator, Synthesizer integration, UI, Notion sync, E2E tests)

**Cost**: $0.17/topic when enabled (1 HD hero $0.08 + 2 standard supporting $0.08, exceeds $0.10 budget but opt-in)

**See**: [Full details](docs/sessions/044-media-generation-phase1-2-config-tone.md)

---

*Older sessions (038-045) archived in `docs/sessions/` directory*
