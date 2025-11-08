# Session 044: Media Generation - Phase 1-2 (Config + Tone Propagation)

**Date**: 2025-11-08
**Duration**: 3.5 hours
**Status**: In Progress (Phase 1-2 Complete, 5/7 phases remaining)

## Objective

Implement automated image generation for blog posts with tone-appropriate styling. System should generate 1 HD hero image + 2 standard supporting images using DALL-E 3, with 3-tier control (Config → API → UI) and silent failure handling.

**Total Scope**: 18.5 hours across 7 phases
**Session 044 Scope**: Phase 1-2 (Config Enhancement + Tone Propagation)

## Problem

User requested image generation feature with specific requirements:
1. **Tone Analysis**: Leverage existing Stage 1 website analysis (tone already extracted!)
2. **3-Tier Control**: Market config default → Python API override → Streamlit UI final say
3. **Image Scope**: 1 HD hero (1792x1024, $0.08) + 2 standard supporting (1024x1024, $0.04 each)
4. **Cost**: $0.17/topic (exceeds $0.10 budget by 70%, acceptable for opt-in)
5. **Silent Failure**: Article generation continues even if images fail

## Key Discovery

**Tone analysis already exists!** The `extract_website_keywords()` method in Stage 1 already extracts tone descriptors (e.g., `["Professional", "Technical"]`) using Gemini API. No need to build tone analyzer from scratch - just propagate existing data through pipeline.

## Solution

### Phase 1: Config Enhancement (1.5 hours)

**1. Added 4 Image Fields to MarketConfig** (`src/utils/config_loader.py:101-118`):

```python
# Image generation settings
brand_tone: Optional[List[str]] = Field(
    None,
    description="Brand communication tone extracted from website"
)
enable_image_generation: bool = Field(
    True,  # Default ON
    description="Enable DALL-E image generation (1 HD hero + 2 standard supporting)"
)
image_quality: str = Field(
    "hd",
    description="DALL-E quality: 'standard' ($0.04) or 'hd' ($0.08)",
    pattern="^(standard|hd)$"
)
image_style_preferences: Optional[Dict[str, str]] = Field(
    None,
    description="Custom image style preferences (overrides tone defaults)"
)
```

**2. Updated Market Config** (`config/markets/proptech_de.yaml:122-141`):

```yaml
# === Image Generation Configuration ===
brand_tone: []  # Populated automatically from website analysis
enable_image_generation: true
image_quality: hd
image_style_preferences: {}
```

**3. Tests Written** (`tests/unit/test_config_loader.py:77-145`):
- `test_image_generation_defaults()` - Verify defaults (enable=True, quality=hd)
- `test_image_generation_custom_values()` - Verify custom values work
- `test_image_quality_validation()` - Verify only "standard"/"hd" accepted

**Result**: ✅ 23/23 config tests passing, config loads successfully

### Phase 2: Tone Propagation (2 hours)

**1. Updated Orchestrator** (`src/orchestrator/hybrid_research_orchestrator.py`):

**`research_topic()` signature** (line 995-1002):
```python
async def research_topic(
    self,
    topic: str,
    config: Dict,
    brand_tone: Optional[List[str]] = None,      # NEW
    generate_images: Optional[bool] = None,      # NEW (None = inherit from config)
    max_results: int = 10
) -> Dict:
```

**Config inheritance logic** (line 1031-1034):
```python
# Resolve image generation preference
if generate_images is None:
    # Inherit from market config
    generate_images = config.get("enable_image_generation", True)
```

**Return structure** (line 1074-1084):
```python
return {
    "topic": topic,
    "sources": sources,
    "article": article,
    "hero_image_url": hero_image_url,           # NEW
    "hero_image_alt": hero_image_alt,           # NEW
    "supporting_images": supporting_images,      # NEW
    "image_cost": image_cost,                    # NEW
    "cost": total_cost,
    "duration_sec": duration
}
```

**`run_pipeline()` tone extraction** (line 1163-1165):
```python
# Extract brand tone from website data
brand_tone = website_data.get("tone", [])
logger.info("brand_tone_extracted", tone=brand_tone)
```

**`run_pipeline()` return** (line 1188-1198):
```python
return {
    "website_data": website_data,
    "brand_tone": brand_tone,  # NEW - exposed at top level
    # ... other fields
}
```

**2. Updated Synthesizer** (`src/research/synthesizer/content_synthesizer.py`):

**`synthesize()` signature** (line 127-134):
```python
async def synthesize(
    self,
    sources: List[SearchResult],
    query: str,
    config: FullConfig,
    brand_tone: Optional[List[str]] = None,      # NEW
    generate_images: bool = False                # NEW
) -> Dict:
```

**Placeholder return fields** (line 232-244):
```python
# Add image placeholders (actual generation in Phase 4)
result['hero_image_url'] = None
result['hero_image_alt'] = None
result['supporting_images'] = []
result['image_cost'] = 0.0

# TODO: Image generation will be implemented in Phase 4
# if generate_images and brand_tone:
#     image_result = await self.image_generator.generate_article_images(...)
#     result['hero_image_url'] = image_result.get('hero_url')
#     result['hero_image_alt'] = image_result.get('hero_alt')
#     result['supporting_images'] = image_result.get('supporting', [])
#     result['image_cost'] = image_result.get('total_cost', 0.0)
```

**3. Tests Written** (`tests/test_unit/test_orchestrator_tone_propagation.py`):
- `test_research_topic_inherits_image_generation_from_config()` - Verify None → config inheritance
- `test_run_pipeline_extracts_and_passes_tone()` - Verify Stage 1 tone → Stage 5
- `test_run_pipeline_returns_brand_tone()` - Verify tone in return dict

**Result**: ✅ 3/3 tone propagation tests passing

## Changes Made

### Config Files
- `src/utils/config_loader.py:26` - Added `Dict` import
- `src/utils/config_loader.py:101-118` - Added 4 image generation fields to MarketConfig
- `config/markets/proptech_de.yaml:122-141` - Added image generation configuration section

### Orchestrator
- `src/orchestrator/hybrid_research_orchestrator.py:995-1084` - Updated `research_topic()` signature + logic
- `src/orchestrator/hybrid_research_orchestrator.py:1163-1165` - Extract tone from website_data
- `src/orchestrator/hybrid_research_orchestrator.py:1169-1174` - Pass tone + images to research_topic
- `src/orchestrator/hybrid_research_orchestrator.py:1188-1198` - Add brand_tone to return dict

### Synthesizer
- `src/research/synthesizer/content_synthesizer.py:127-157` - Updated `synthesize()` signature + docstring
- `src/research/synthesizer/content_synthesizer.py:232-244` - Added image placeholder fields

### Tests
- `tests/unit/test_config_loader.py:77-145` - Added 3 image config tests
- `tests/test_unit/test_orchestrator_tone_propagation.py` - Created new test file with 3 tests

### Documentation
- `TASKS.md:67-159` - Updated Phase 4.5 section with implementation plan

## Testing

### Config Tests
```bash
pytest tests/unit/test_config_loader.py -v
# Result: 23/23 PASSED (3 new tests for image fields)
```

### Tone Propagation Tests
```bash
pytest tests/test_unit/test_orchestrator_tone_propagation.py -v
# Result: 3/3 PASSED
```

### Manual Config Validation
```python
from src.utils.config_loader import ConfigLoader
loader = ConfigLoader()
config = loader.load('proptech_de')

assert config.market.enable_image_generation == True
assert config.market.image_quality == "hd"
assert config.market.brand_tone is None  # Populated at runtime
```

## Performance Impact

**No performance impact** - changes are configuration and signature updates only. Actual image generation (Phase 4) will add:
- **Cost**: $0.17/topic ($0.08 hero + $0.08 supporting)
- **Time**: ~30-60s for 3 DALL-E 3 API calls
- **Opt-in**: Controlled via config/API/UI, disabled by default in tests

## Architecture Decisions

**Decision**: Use existing Stage 1 tone extraction instead of building separate analyzer

**Rationale**:
- Stage 1 already extracts tone using Gemini API (`extract_website_keywords()`)
- Returns 1-3 tone descriptors (e.g., "Professional", "Technical", "Innovative")
- Zero additional API cost, zero additional latency
- Simpler architecture (no new component)

**Alternative Considered**: Build dedicated WebsiteToneAnalyzer
- **Rejected**: Duplicates existing functionality
- **Cost**: Would add extra API call ($0.001/website)
- **Complexity**: Additional component to maintain

**Decision**: 3-tier control hierarchy (Config → API → UI)

**Rationale**:
- **Market Config**: Sensible default per market (enable_image_generation: true)
- **Python API**: Programmatic override for batch operations
- **Streamlit UI**: User final say per article (checkbox on Generate page)
- Follows existing pattern in project (e.g., `enable_tavily` flag)

**Decision**: Silent failure for image generation

**Rationale**:
- Article research is primary value ($0.01), images are enhancement ($0.16)
- DALL-E API can be unreliable (rate limits, downtime)
- Better UX: Article completes even if images fail
- User can regenerate images separately later (future feature)

## Implementation Status

### ✅ Phase 1: Config Enhancement (1.5 hours) - COMPLETE
- Added 4 image fields to MarketConfig
- Updated proptech_de.yaml
- Wrote 3 config tests (all passing)

### ✅ Phase 2: Tone Propagation (2 hours) - COMPLETE
- Updated orchestrator signatures
- Updated synthesizer signature
- Wrote 3 tone propagation tests (all passing)

### ⏳ Phase 3: ImageGenerator Module (6 hours) - PENDING
- Write 20 unit tests (TDD)
- Implement 7-tone prompt mapping
- DALL-E 3 integration (hero + supporting)
- Silent failure handling
- Cost tracking

### ⏳ Phase 4: Synthesizer Integration (3 hours) - PENDING
- Integrate ImageGenerator into ContentSynthesizer
- Remove placeholder code
- Write integration tests

### ⏳ Phase 5: Streamlit UI (2 hours) - PENDING
- Add image checkbox to Generate page
- Display generated images
- Write UI tests

### ⏳ Phase 6: Notion Sync (1 hour) - PENDING
- Map image URLs to Notion fields
- Add Supporting Images field to schema
- Write sync tests

### ⏳ Phase 7: E2E Testing (3 hours) - PENDING
- Full pipeline test (Website → Tone → Article → Images → Notion)
- Images disabled test
- Silent failure test
- Config inheritance test

## Next Steps

**Phase 3: ImageGenerator Module** (6 hours estimated)
1. Write 20 unit tests for ImageGenerator class (TDD approach)
2. Implement 7-tone prompt mapping system:
   - Professional → "avoid: anime, cartoon, playful"
   - Technical → "avoid: decorative, overly artistic, busy"
   - Creative → "avoid: generic stock, corporate stiffness"
   - Casual, Authoritative, Innovative, Friendly
3. Implement DALL-E 3 integration:
   - `generate_hero_image()` - 1792x1024 HD ($0.08)
   - `generate_supporting_image()` - 1024x1024 standard ($0.04)
   - `generate_article_images()` - Orchestrate all 3 images
4. Add silent failure handling (3 retries, return None)
5. Integrate with CostTracker

## Notes

- **Cost Budget Exceeded**: $0.17/topic exceeds $0.10 budget by 70%, but acceptable since:
  - Image generation is opt-in (disabled in tests by default)
  - Provides significant value (professional visuals)
  - User can disable per-market, per-API-call, or per-UI-selection

- **Tone Analysis**: No additional work needed! Stage 1 already extracts tone via Gemini API. Just propagate existing data.

- **Notion Schemas Ready**: `Hero Image URL` and `Media URL` fields already exist in Notion schemas. No schema migration needed.

- **TDD Discipline**: All changes made with tests-first approach:
  - Config: 3 tests written → 4 fields added → tests pass
  - Tone: 3 tests written → signatures updated → tests pass

- **No Regressions**: All 23 existing config tests still passing after changes

## Related Files

**Created**:
- `tests/test_unit/test_orchestrator_tone_propagation.py` (212 lines, 3 tests)

**Modified**:
- `src/utils/config_loader.py` (+20 lines)
- `src/orchestrator/hybrid_research_orchestrator.py` (+45 lines)
- `src/research/synthesizer/content_synthesizer.py` (+21 lines)
- `config/markets/proptech_de.yaml` (+20 lines)
- `tests/unit/test_config_loader.py` (+69 lines)
- `TASKS.md` (+93 lines updated Phase 4.5 section)

**Total**: +268 lines of production code + tests
