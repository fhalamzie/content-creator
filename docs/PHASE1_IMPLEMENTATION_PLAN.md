# Phase 1 Implementation Plan - Platform Content Optimization

**Status**: Ready for Implementation
**Duration**: Week 1-2 (8-10 development hours)
**Goal**: Generate platform-optimized text content from blog posts using parallel subagents
**Cost per Blog**: $0.003 (4 platforms × 500 tokens × $0.0016/1K)

---

## Executive Summary

Phase 1 focuses on **text generation only** (no images). We'll implement:
1. Platform profiles (LinkedIn, Facebook, Instagram, TikTok)
2. RepurposingAgent core with Qwen3-Max integration
3. Hashtag generation logic
4. Cache integration
5. Comprehensive testing (30 tests: 20 unit + 10 integration)

**Parallel Execution Strategy**: 5 subagents working concurrently on different components.

---

## Implementation Architecture

### Directory Structure (NEW)

```
src/agents/
├── repurposing_agent.py           # NEW - Main agent class (300 lines)
├── platform_profiles.py            # NEW - Platform configurations (150 lines)
└── base_agent.py                   # EXISTS - Inherit from this

config/prompts/
└── repurpose_de.md                 # NEW - German social post template (200 lines)

tests/unit/agents/
└── test_repurposing_agent.py      # NEW - 20 unit tests (400 lines)

tests/integration/agents/
└── test_repurposing_integration.py # NEW - 10 integration tests (300 lines)
```

**Total**: ~1,350 new lines of code

---

## Parallel Subagent Workflow

### Subagent 1: Platform Profiles Module (Haiku, 1.5 hours)

**Task**: Create `src/agents/platform_profiles.py`

**Responsibilities**:
- Define `PLATFORM_PROFILES` dict with 4 platforms
- Create `PlatformConfig` dataclass with validation
- Implement `get_platform_config(platform: str)` helper
- Add `VALID_PLATFORMS` constant
- Write 5 unit tests

**Dependencies**: None (can start immediately)

**Deliverables**:
```python
# src/agents/platform_profiles.py (150 lines)

@dataclass
class PlatformConfig:
    name: str
    max_chars: int
    optimal_chars: int
    tone: str
    hashtag_limit: int
    emoji_usage: str
    cta_style: str
    format: str

PLATFORM_PROFILES = {
    "LinkedIn": PlatformConfig(...),
    "Facebook": PlatformConfig(...),
    "Instagram": PlatformConfig(...),
    "TikTok": PlatformConfig(...)
}

def get_platform_config(platform: str) -> PlatformConfig:
    """Get validated platform configuration"""
    if platform not in VALID_PLATFORMS:
        raise ValueError(f"Invalid platform: {platform}")
    return PLATFORM_PROFILES[platform]
```

**Tests**: 5 unit tests
- `test_platform_config_dataclass` - Validate dataclass fields
- `test_get_platform_config_valid` - Get each platform config
- `test_get_platform_config_invalid` - Raise error on unknown platform
- `test_platform_limits` - Verify character limits match spec
- `test_valid_platforms_constant` - Verify all 4 platforms exist

---

### Subagent 2: German Prompt Template (Haiku, 1 hour)

**Task**: Create `config/prompts/repurpose_de.md`

**Responsibilities**:
- Write German social post generation template
- Include platform-specific instructions
- Add tone/style guidance
- Format instructions (hashtags, emojis, CTAs)
- Variables: `{topic}`, `{excerpt}`, `{platform}`, `{tone}`, `{max_chars}`

**Dependencies**: None (can start immediately)

**Deliverables**:
```markdown
# config/prompts/repurpose_de.md (200 lines)

Du bist ein Social Media Experte für {platform} mit Fokus auf deutschen Markt.

## Aufgabe
Erstelle einen optimierten {platform}-Post aus dem folgenden Blog-Artikel.

## Blog-Artikel
**Titel**: {topic}
**Zusammenfassung**: {excerpt}
**Keywords**: {keywords}

## {platform} Anforderungen
- **Ton**: {tone}
- **Länge**: Optimal {optimal_chars} Zeichen (Maximum: {max_chars})
- **Format**: {format}
- **Hashtags**: Maximal {hashtag_limit}
- **Emojis**: {emoji_usage}
- **CTA**: {cta_style}

## Ausgabeformat
Generiere NUR den Post-Text, KEINE Erklärungen oder Metadaten.
Der Post muss direkt veröffentlichbar sein.

---

WICHTIG: Halte den Post prägnant, authentisch und plattformgerecht.
```

**Tests**: Manual validation (check template loads, variables valid)

---

### Subagent 3: RepurposingAgent Core (Sonnet, 3 hours)

**Task**: Create `src/agents/repurposing_agent.py`

**Responsibilities**:
- Extend `BaseAgent` with `agent_type="repurposing"`
- Implement `generate_social_posts(blog_post, platforms, brand_tone, generate_images=False)`
- Implement `_generate_platform_content(blog_post, platform, brand_tone)`
- Implement `_generate_hashtags(keywords, platform)`
- Implement `_calculate_cost(results)`
- Cache integration using `CacheManager.write_social_post()`
- Error handling with `RepurposingError`

**Dependencies**: Subagent 1 (platform_profiles.py), Subagent 2 (repurpose_de.md)

**Deliverables**:
```python
# src/agents/repurposing_agent.py (300 lines)

from src.agents.base_agent import BaseAgent, AgentError
from src.agents.platform_profiles import get_platform_config, VALID_PLATFORMS
from src.cache_manager import CacheManager
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RepurposingError(AgentError):
    """Raised when repurposing fails"""
    pass

class RepurposingAgent(BaseAgent):
    """
    Generates platform-optimized social media content from blog posts

    Features:
    - Platform-specific text optimization (tone, length, format)
    - Hashtag generation with trending analysis
    - Cost tracking per platform
    - Batch generation (4 platforms in parallel)
    """

    def __init__(
        self,
        api_key: str,
        cache_dir: Optional[str] = None,
        custom_config: Optional[Dict] = None
    ):
        super().__init__(agent_type="repurposing", api_key=api_key, custom_config=custom_config)
        self.cache_manager = CacheManager(cache_dir) if cache_dir else None
        logger.info("repurposing_agent_initialized", cache_dir=cache_dir)

    async def generate_social_posts(
        self,
        blog_post: Dict[str, Any],
        platforms: List[str] = ["LinkedIn", "Facebook", "Instagram", "TikTok"],
        brand_tone: List[str] = ["Professional"],
        save_to_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate social posts for all platforms

        Args:
            blog_post: {title, content, excerpt, keywords, slug}
            platforms: Platforms to generate for (default: all 4)
            brand_tone: Brand voice settings
            save_to_cache: Save to cache/social_posts/

        Returns:
            List of dicts: [{platform, content, hashtags, character_count, cost}, ...]

        Raises:
            RepurposingError: On generation failures
        """
        # Validate platforms
        # Load prompt template
        # Generate for each platform (sequential for now, parallel later)
        # Calculate total cost
        # Save to cache (if enabled)
        # Return results
        pass

    async def _generate_platform_content(
        self,
        blog_post: Dict[str, Any],
        platform: str,
        brand_tone: List[str]
    ) -> Dict[str, Any]:
        """Generate platform-optimized content using Qwen3-Max"""
        pass

    def _generate_hashtags(
        self,
        keywords: List[str],
        platform: str
    ) -> List[str]:
        """Generate platform-specific hashtags"""
        pass
```

**Tests**: Covered by Subagent 4 (unit tests) and Subagent 5 (integration tests)

---

### Subagent 4: Unit Tests (Haiku, 2 hours)

**Task**: Create `tests/unit/agents/test_repurposing_agent.py`

**Responsibilities**:
- Write 20 unit tests covering all methods
- Mock OpenRouter API calls
- Test error conditions
- Test cache integration (optional)
- Validate character limits

**Dependencies**: Subagent 1, Subagent 2, Subagent 3

**Deliverables**:
```python
# tests/unit/agents/test_repurposing_agent.py (400 lines)

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.agents.repurposing_agent import RepurposingAgent, RepurposingError
from src.agents.platform_profiles import VALID_PLATFORMS

# 20 unit tests:

# Initialization Tests (3)
def test_repurposing_agent_init_success()
def test_repurposing_agent_init_no_api_key()
def test_repurposing_agent_init_with_cache()

# Platform Content Generation (5)
@patch('src.agents.repurposing_agent.BaseAgent.generate')
def test_generate_platform_content_linkedin(mock_generate)
def test_generate_platform_content_facebook(mock_generate)
def test_generate_platform_content_instagram(mock_generate)
def test_generate_platform_content_tiktok(mock_generate)
def test_generate_platform_content_character_limit_enforced(mock_generate)

# Hashtag Generation (5)
def test_generate_hashtags_linkedin_limit()
def test_generate_hashtags_instagram_limit()
def test_generate_hashtags_formatting()
def test_generate_hashtags_german_keywords()
def test_generate_hashtags_empty_keywords()

# Batch Generation (4)
def test_generate_social_posts_all_platforms(mock_generate)
def test_generate_social_posts_single_platform(mock_generate)
def test_generate_social_posts_invalid_platform(mock_generate)
def test_generate_social_posts_cost_calculation(mock_generate)

# Error Handling (3)
def test_generate_fails_after_retries(mock_generate)
def test_generate_raises_repurposing_error(mock_generate)
def test_cache_failure_does_not_fail_generation(mock_cache)
```

**Success Criteria**: All 20 tests passing, >90% coverage

---

### Subagent 5: Integration Tests (Haiku, 1.5 hours)

**Task**: Create `tests/integration/agents/test_repurposing_integration.py`

**Responsibilities**:
- Write 10 integration tests with LIVE API calls (2 tests)
- Write 8 integration tests with MOCKED API calls
- Test full pipeline: blog post → social posts → cache
- Validate cost tracking accuracy
- Test brand tone propagation

**Dependencies**: Subagent 1, Subagent 2, Subagent 3

**Deliverables**:
```python
# tests/integration/agents/test_repurposing_integration.py (300 lines)

import pytest
from src.agents.repurposing_agent import RepurposingAgent
from src.cache_manager import CacheManager
import os

# 10 integration tests:

# Live API Tests (2) - Marked with @pytest.mark.integration
@pytest.mark.integration
def test_generate_linkedin_post_live_api()
def test_generate_all_platforms_live_api()

# Mocked API Tests (8)
def test_cache_integration_saves_to_disk(mock_generate)
def test_cache_integration_reads_from_disk(mock_generate)
def test_brand_tone_propagation(mock_generate)
def test_cost_tracking_accuracy(mock_generate)
def test_batch_generation_order(mock_generate)
def test_platform_specific_prompts(mock_generate)
def test_german_content_generation(mock_generate)
def test_metadata_includes_character_count(mock_generate)
```

**Success Criteria**: 10 tests passing, 2 live API tests cost <$0.01

---

## Dependency Graph

```
Phase 0: Exploration (COMPLETE ✅)
    ↓
┌───────────────────────────────────────────────┐
│  START PHASE 1 (Parallel Execution)           │
└───────────────────────────────────────────────┘
    ↓
┌────────────┐  ┌────────────┐
│ Subagent 1 │  │ Subagent 2 │  (No dependencies, start immediately)
│ Profiles   │  │ Prompt     │
└────────────┘  └────────────┘
    ↓               ↓
    └───────┬───────┘
            ↓
    ┌────────────┐
    │ Subagent 3 │  (Depends on 1 & 2)
    │ Agent Core │
    └────────────┘
            ↓
    ┌───────┴───────┐
    ↓               ↓
┌────────────┐  ┌────────────┐
│ Subagent 4 │  │ Subagent 5 │  (Depends on 3, run in parallel)
│ Unit Tests │  │ Integration│
└────────────┘  └────────────┘
    ↓               ↓
    └───────┬───────┘
            ↓
┌───────────────────────────────────────────────┐
│  PHASE 1 COMPLETE                             │
│  - 30 tests passing                           │
│  - Text generation working for 4 platforms    │
│  - Cost: $0.003/blog post                     │
└───────────────────────────────────────────────┘
```

---

## Execution Timeline

### Parallel Phase (Start Together)
- **Hour 0-1.5**: Subagent 1 (Platform Profiles) + Subagent 2 (Prompt Template)
- **Total Time**: 1.5 hours (parallel)

### Sequential Phase (After Subagents 1-2 Complete)
- **Hour 1.5-4.5**: Subagent 3 (RepurposingAgent Core)
- **Total Time**: 3 hours

### Parallel Phase (After Subagent 3 Complete)
- **Hour 4.5-6.5**: Subagent 4 (Unit Tests) + Subagent 5 (Integration Tests)
- **Total Time**: 2 hours (parallel)

**Total Duration**: 6.5 hours (vs 8 hours sequential) = **19% time savings**

---

## Testing Strategy

### Test Coverage Goals
- **Unit Tests**: >90% coverage (20 tests)
- **Integration Tests**: >85% coverage (10 tests)
- **Critical Paths**: 100% coverage (generate_social_posts, _generate_platform_content)

### Test Pyramid
```
         /\
        /  \  2 Live API Tests (LinkedIn, All Platforms)
       /____\
      /      \
     / Mocked \ 8 Integration Tests (Cache, Cost, Brand Tone)
    /__________\
   /            \
  /  Unit Tests  \ 20 Unit Tests (Profiles, Hashtags, Errors)
 /________________\
```

### Cost Control for Testing
- **Live API Tests**: Only 2 tests × $0.003 = **$0.006 total**
- **Mocked Tests**: 28 tests × $0.00 = **$0.00**
- **Total Testing Cost**: <$0.01

---

## Acceptance Criteria

Phase 1 is complete when:

### Functional
- ✅ All 4 platforms generate unique content (no duplicates)
- ✅ Character limits respected (<1300 LinkedIn, <250 Facebook, etc.)
- ✅ Hashtags formatted correctly (#PropTech, not #prop tech)
- ✅ Hashtag limits enforced (5 LinkedIn, 30 Instagram, etc.)
- ✅ German content generation (no English text)
- ✅ Brand tone propagates correctly

### Technical
- ✅ 30 tests passing (20 unit + 10 integration)
- ✅ >85% test coverage overall
- ✅ Cost tracking accurate (<$0.005/blog post for text)
- ✅ Cache integration working (files saved to cache/social_posts/)
- ✅ Error handling complete (RepurposingError raised on failures)
- ✅ Logging comprehensive (INFO for operations, ERROR for failures)

### Performance
- ✅ Generation time <10s per platform (sequential)
- ✅ Generation time <3s total (parallel implementation in Phase 4)
- ✅ No memory leaks (tested with 100 consecutive generations)

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Qwen3-Max character limit overruns** | Medium | Hard truncation at platform max_chars + ellipsis |
| **German quality issues** | High | Manual review of 10 sample posts + native speaker validation |
| **Hashtag relevance low** | Low | Use blog keywords directly + manual editing in Notion |
| **Cost per post exceeds $0.005** | Low | Monitor token usage, optimize prompt length if needed |
| **Subagent 3 blocks Subagents 4-5** | Medium | Start unit test scaffolding early, fill in after Subagent 3 |

---

## Next Steps After Phase 1

**Immediate (Week 3)**:
- Phase 2: Open Graph Image Generation (Pillow templates)
- Phase 3: Platform-Specific Images (Flux Dev integration)

**Later (Week 4-5)**:
- Phase 4: Notion Sync + Pipeline Integration
- Phase 5: Streamlit UI

---

## Cost Summary

| Component | Cost | Notes |
|-----------|------|-------|
| **Development** | 6.5 hours | With parallel subagents (vs 8 hours sequential) |
| **Testing** | <$0.01 | 2 live API tests only |
| **Per Blog Post** | $0.003 | 4 platforms × 500 tokens × $0.0016/1K |
| **Monthly (10 blogs)** | $0.03 | Text only, no images |

---

**Document Version**: 1.0
**Created**: 2025-11-16 (Session 059)
**Status**: Ready for Execution
**Estimated Completion**: Week 1-2 (6.5 development hours)
