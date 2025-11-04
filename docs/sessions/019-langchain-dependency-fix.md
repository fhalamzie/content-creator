# Session 019: LangChain Dependency Fix & Pipeline Testing

**Date**: 2025-11-04
**Duration**: ~1.5 hours
**Status**: Completed

## Objective

Fix Topic Research Pipeline breaking error: `No module named 'langchain.docstore'` when running ContentPipeline UI integration.

## Problem

User reported complete pipeline failure with error:
```
Pipeline failed: Stage 3 failed: Research failed for 'Proptech Trends 2025':
gpt-researcher not installed. Install with: pip install gpt-researcher==0.14.4.
Error: No module named 'langchain.docstore'
```

**Root Cause**: gpt-researcher 0.14.4 requires langchain<1.0, but langchain 1.0.3 was installed. The langchain 1.0 release removed the `langchain.docstore.document` module that gpt-researcher depends on.

## Solution

### 1. Downgraded LangChain Dependencies

**Command**:
```bash
pip install 'langchain<1.0' 'langchain-core<1.0' 'langchain-community<1.0' \
  'langchain-text-splitters<1.0' 'langchain-openai<1.0'
```

**Result**: Successfully downgraded to compatible versions (langchain 0.3.27).

### 2. Updated Requirements File

**File**: `requirements-topic-research.txt:86-94`

Added version constraints with documentation:
```python
# Deep Research (LLM-powered)
gpt-researcher==0.14.4            # Deep research with citations
# Note: Requires OPENAI_API_KEY or other LLM provider
# IMPORTANT: gpt-researcher 0.14.4 requires langchain<1.0
langchain<1.0                     # Pin to pre-1.0 for gpt-researcher compatibility
langchain-core<1.0
langchain-community<1.0
langchain-text-splitters<1.0
langchain-openai<1.0
```

### 3. Verified Import

```bash
python -c "from gpt_researcher import GPTResearcher; print('Success!')"
# Output: Success!
```

### 4. Tested Pipeline (Stages 1,2,4,5)

Created comprehensive test with proper object initialization:
- Created `Topic` object (from `src.models.topic`)
- Created `MarketConfig` object (from `src.models.config`)
- Loaded environment files (`.env`, `/home/envs/openrouter.env`)
- Disabled Stage 3 temporarily due to gpt-researcher 0.14.4 bug

**Test Result**: ✅ SUCCESS (12 seconds total)
- Stage 1 (Competitor Research): 6s ✅
- Stage 2 (Keyword Research): 6s ✅
- Stage 3 (Deep Research): SKIPPED (gpt-researcher bug)
- Stage 4 (Content Optimization): <1s ✅
- Stage 5 (Scoring & Ranking): <1s ✅ (priority_score: 0.32)

## Changes Made

- `requirements-topic-research.txt:86-94` - Added langchain version constraints with detailed comments

## Testing

**Test Command**:
```python
# Initialize with proper objects
topic = Topic(
    title="PropTech Trends 2025",
    source=TopicSource.MANUAL,
    domain="SaaS", market="Germany", language="de",
    engagement_score=50, trending_score=50.0
)

market_config = MarketConfig(
    domain="SaaS", market="Germany", language="de",
    vertical="PropTech", seed_keywords=["proptech", "immobilien"]
)

# Create pipeline with Stage 3 disabled
pipeline = ContentPipeline(..., enable_deep_research=False)
result = await pipeline.process_topic(topic, market_config)
```

**Evidence**:
```
2025-11-04 13:49:20 [info] pipeline_started
2025-11-04 13:49:20 [info] stage1_started
2025-11-04 13:49:26 [info] stage1_completed (competitors_found=0, content_gaps=0)
2025-11-04 13:49:26 [info] stage2_started
2025-11-04 13:49:32 [info] stage2_completed
2025-11-04 13:49:32 [info] stage3_skipped (reason=deep_research_disabled)
2025-11-04 13:49:32 [info] stage4_completed
2025-11-04 13:49:32 [info] stage5_completed (priority_score=0.3175)
2025-11-04 13:49:32 [info] pipeline_completed
```

## Performance Impact

- **Stages 1-2-4-5 Execution Time**: 12 seconds (down from failure)
- **Dependency Resolution**: No conflicts after langchain downgrade
- **Memory**: No change (same dependency tree depth)

## Known Issues

### Stage 3 (Deep Research) Disabled

**Issue**: gpt-researcher 0.14.4 has bug passing `llm_provider` parameter twice:
```
TypeError: gpt_researcher.utils.llm.create_chat_completion()
got multiple values for keyword argument 'llm_provider'
```

**Workaround**: Set `enable_deep_research=False` in ContentPipeline initialization

**Permanent Fix Options**:
1. Upgrade to gpt-researcher 0.15+ (if compatible with langchain<1.0)
2. Use alternative research library (e.g., direct Gemini API calls)
3. Patch gpt-researcher locally
4. Wait for gpt-researcher maintainers to fix

**Environment Files Needed**:
- `/home/envs/gemini.env` - For GEMINI_API_KEY (used by gpt-researcher embeddings)
- `/home/envs/openai.env` - For OPENAI_API_KEY (alternative to Gemini)

## Related Issues

- Gemini CLI hanging issue ✅ Fixed in Session 018 (stdin method)
- Type handling in DeepResearcher ✅ Fixed in Session 018 (isinstance checks)

## Notes

### Dependency Conflict Resolution

The langchain ecosystem had a breaking change in 1.0:
- **Before (0.3.x)**: `from langchain.docstore.document import Document`
- **After (1.0.x)**: Module removed, moved to `langchain_core.documents`

gpt-researcher 0.14.4 still uses the old import path, requiring langchain<1.0.

### Future Migration Path

When gpt-researcher adds langchain 1.0 support:
1. Remove version pins from `requirements-topic-research.txt`
2. Upgrade: `pip install --upgrade gpt-researcher langchain`
3. Re-enable Stage 3: `enable_deep_research=True`
4. Test full 5-stage pipeline

### Testing Strategy Used

Parallel subagent approach (from Session 018):
- Ran multiple test scripts simultaneously
- Isolated each stage for faster diagnosis
- Used background bash jobs to monitor progress
- Validated each fix incrementally

## Success Criteria

- ✅ gpt-researcher imports successfully
- ✅ No langchain.docstore import errors
- ✅ Stages 1, 2, 4, 5 complete successfully
- ✅ Pipeline processes topics end-to-end (with Stage 3 disabled)
- ⏸️ Stage 3 (Deep Research) working - blocked by upstream bug

## Follow-Up Actions

1. Monitor gpt-researcher releases for langchain 1.0 support
2. Test Streamlit UI with fixed pipeline
3. Create E2E test for full pipeline (all 5 stages)
4. Update TASKS.md to track Stage 3 fix
5. Document workaround in README.md troubleshooting section
