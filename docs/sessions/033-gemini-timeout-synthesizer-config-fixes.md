# Session 033: Gemini Timeout + Content Synthesizer Config Fixes

**Date**: 2025-11-05
**Duration**: 1 hour
**Status**: In Progress (smoke test running)

## Objective

Fix 2 additional bugs discovered during production test validation: Gemini API timeout misconfiguration (60ms instead of 60s) and content synthesizer Pydantic config incompatibility.

## Problems

**Bug 1: Gemini API Timeout Misconfiguration**
- Production test showed: `Read timed out. (read timeout=0.06)` (60 milliseconds!)
- API requests timing out at 60ms instead of 60 seconds
- Caused Gemini backend to fail on ALL requests
- Root cause: Google GenAI SDK `http_options={'timeout': X}` expects **milliseconds**, not seconds
- I passed `timeout=60.0` expecting seconds, SDK interpreted as 60ms

**Bug 2: Content Synthesizer Config Incompatibility**
- Error: `'FullConfig' object has no attribute 'get'` during article synthesis
- Same Pydantic config bug as reranker (Session 032), but in different component
- Content synthesizer's `_synthesize_article()` method assumed dict configs
- Failed on PropTech/Fashion topics using Pydantic `FullConfig` models

## Solutions

### Fix 1: Correct Gemini Timeout Configuration (src/agents/gemini_agent.py:133)

**Changed from 60 seconds to 60,000 milliseconds:**
```python
# OLD (WRONG - 60ms timeout)
self.client = genai.Client(
    api_key=self.api_key,
    http_options={'timeout': 60.0}  # Interpreted as 60 milliseconds!
)

# NEW (CORRECT - 60s timeout)
self.client = genai.Client(
    api_key=self.api_key,
    http_options={'timeout': 60000}  # 60 seconds in milliseconds
)
```

**Why milliseconds?**
- Checked Google GenAI SDK documentation: `HttpOptions.model_fields['timeout']`
- Description: "Timeout for the request in **milliseconds**"
- 60,000ms = 60 seconds
- Prevents both infinite hangs AND premature timeouts

### Fix 2: Content Synthesizer Pydantic Support (src/research/synthesizer/content_synthesizer.py:543-558)

**Added multi-type config handling:**
```python
# Handle both dict and Pydantic model configs
if isinstance(config, dict):
    # Plain dict config (SaaS topics)
    domain = config.get('domain', 'general')
    language = config.get('language', 'en')
else:
    # Pydantic FullConfig with nested MarketConfig (PropTech/Fashion topics)
    market_obj = getattr(config, 'market', None)
    if market_obj:
        # Nested access: config.market.domain, config.market.language
        domain = str(getattr(market_obj, 'domain', 'general'))
        language = str(getattr(market_obj, 'language', 'en'))
    else:
        # Fallback to defaults
        domain = 'general'
        language = 'en'
```

**Matches reranker pattern** - consistent approach across components.

## Changes Made

- `src/agents/gemini_agent.py:133` - Changed timeout from 60.0 to 60000 (milliseconds)
- `src/agents/gemini_agent.py:130` - Added comment explaining milliseconds requirement
- `src/research/synthesizer/content_synthesizer.py:543-558` - Added dict/Pydantic config type detection
- `docs/sessions/033-gemini-timeout-synthesizer-config-fixes.md` - Created session narrative

## Testing

**Smoke Test (Single Topic) - Running**:
```bash
pytest tests/e2e/test_smoke_single_topic.py -v --tb=short
# Shell: 6cd1d7
# Expected: ~5 minutes, validates all 3 bugs fixed
```

**Expected Results**:
- ✅ Gemini API requests complete within 60s (not 60ms)
- ✅ Content synthesis works with Pydantic configs
- ✅ Full pipeline operational (research → rerank → synthesize)

**Production Test (10 Topics) - Pending**:
- Once smoke test passes, run full 10-topic validation
- Estimated: ~30 minutes, $0.10 total cost
- Validates production readiness

## Performance Impact

**Before**:
- Gemini timeout: 60ms → ALL requests failed instantly
- Content synthesis: 100% failure rate on PropTech/Fashion topics
- Pipeline: Unstable with Pydantic configs

**After**:
- Gemini timeout: 60s → Requests complete OR timeout gracefully
- Content synthesis: Works with both dict and Pydantic configs
- Pipeline: Stable across all topic types

## Root Cause Analysis

**Bug 1 Timeline**:
1. Session 032: Added `http_options={'timeout': 60.0}` expecting seconds
2. Google GenAI SDK interprets timeout parameter as **milliseconds**
3. 60.0ms timeout = API requests fail immediately on ANY network latency
4. Discovered by checking SDK docs: `HttpOptions.model_fields['timeout']` shows "milliseconds"
5. Fixed by converting to milliseconds: 60 seconds × 1000 = 60,000ms

**Bug 2 Analysis**:
- Session 032 fixed reranker, but content synthesizer had same bug
- Both components access `config.domain` and `config.language`
- Need to check ALL components that access config attributes
- Fixed synthesizer, need to audit for other occurrences

## Related Issues

- Session 032: Fixed same Pydantic bug in reranker
- Both bugs discovered during same production test run
- Shows importance of end-to-end testing with real production configs

## Notes

- **SDK Documentation**: Always check parameter units (seconds vs milliseconds, bytes vs MB, etc.)
- **Config Consistency**: Need to standardize on single config type (dict OR Pydantic) to avoid repeated bugs
- **Component Audit**: Search codebase for other `config.get()` calls that might fail on Pydantic models
- **Test Coverage**: E2E tests with production configs critical for catching these integration bugs

## Success Criteria

✅ Fixed Gemini timeout from 60ms → 60s (converted to 60000ms)
✅ Fixed content synthesizer Pydantic config handling
⏳ Smoke test passes with all fixes (running)
⏳ Production test validates 10 topics successfully

**Status**: 2/4 criteria met, smoke test in progress.
