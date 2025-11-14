# Changelog

Recent development sessions (last 3 sessions, <100 lines).

## Session 049: Image Generation Optimization & Chutes.ai Integration (2025-11-12, verified 2025-11-15)

**OPTIMIZATION + VERIFICATION (4 hours)** - Flux prompt optimization, Chutes.ai model comparison, FactChecker API migration, full production testing

**Problems**: FactChecker using Gemini CLI (30s timeout hangs), only 3 Flux images (no comparison), Flux prompts not following best practices (keyword-heavy), poor Chutes model quality (dreamshaper-xl, schnell).

**Solutions**:
- ✅ **FactChecker Migration**: Gemini CLI → API (60s timeout, better error handling, same FREE cost)
- ✅ **Chutes.ai Integration**: 2 optimized models (JuggernautXL 25 steps, qwen-image 35 steps)
- ✅ **Parameter Tuning**: guidance_scale 7.5-8.0, negative prompts, professional photography keywords
- ✅ **Flux Prompt Optimization**: Natural language structure (Subject → Background → Lighting → Camera), specific equipment (Canon EOS R5, Sony A7R IV), 40-60 words (vs 100-150), output_quality: 90
- ✅ **Model Comparison**: 5 images total (3 Flux + 2 Chutes), photorealistic quality
- ✅ **Full Testing** (2025-11-15): Programmatic verification with `/tmp/full_generation_test.py`, all 5 images successful, all optimizations confirmed in production

**Cost** (Verified): $0.20/article (Blog $0.0056 + Flux Ultra $0.06 + 2x Flux Dev $0.006 + JuggernautXL $0.025 + qwen-image $0.105). +18% vs old config but +100% quality.

**Performance** (Measured): Blog 142s, Images 77s total (Flux Ultra 13s, Flux Dev 10-15s each, JuggernautXL 5s, qwen-image 34s). qwen-image: 35 steps (↑75% from old 20).

**Quality** (Verified): All images photorealistic. Flux (sharper, better composition, camera specs in prompts), JuggernautXL (cinematic, 122KB), qwen-image (high detail, 100KB). Natural language prompts working, negative prompts preventing artifacts.

**See**: [Full details](docs/sessions/049-image-generation-optimization.md)

---

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

*Older sessions (044-048) archived in `docs/sessions/` directory*
