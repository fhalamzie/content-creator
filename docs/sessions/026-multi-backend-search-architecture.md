# Session 026: Multi-Backend Search Architecture (Phase 1-2 Complete)

**Date**: 2025-11-05
**Duration**: 2 hours
**Status**: In Progress (Phase 1-2 Complete, Phase 3-4 Pending)

## Objective

Implement fault-tolerant parallel multi-backend research system with graceful degradation to improve source diversity (from 8-10 to 20-25 sources per report) while maintaining cost ($0.02/topic) and eliminating silent failures.

## Problem

**Current State**:
- Single backend (gpt-researcher + Tavily API)
- 8-10 sources per report
- $0.02 per topic
- Limited source diversity (only Tavily's index)
- Gemini CLI fallback (being phased out, no citations)

**Requirements**:
1. More diverse sources (academic + web + trends)
2. No cost increase ($0.02 target maintained)
3. Graceful degradation (continue if ≥1 backend succeeds)
4. Zero silent failures (all errors logged comprehensively)
5. Replace Gemini CLI fallback with Gemini API (grounding)

## Solution

Implemented **parallel complementary multi-backend architecture** with specialized search horizons:

### Architecture Design

```
DeepResearcher (Orchestrator)
├── TavilyBackend    → DEPTH (academic/authoritative)    $0.02/query
├── SearXNGBackend   → BREADTH (245 engines)             FREE
└── GeminiAPIBackend → TRENDS (grounded analysis)        FREE
         ↓
   asyncio.gather(return_exceptions=True)
         ↓
   Source Fusion + Diversity Scoring
         ↓
   20-25 sources per report (vs 8-10)
```

**Key Insight**: Instead of replacement or fallback, use backends in **parallel** with **complementary specializations**:
- **Tavily**: Academic rigor (Grand View Research, IEEE, industry reports)
- **SearXNG**: Wide coverage (245 engines, recent content, diverse perspectives)
- **Gemini**: Trends (expert opinions, emerging patterns, predictions)

### Backend Abstraction Layer

Created comprehensive abstraction (`src/research/backends/`):

**Base Classes** (`base.py`, 219 lines):
```python
class SearchBackend(ABC):
    """
    Graceful Degradation Contract:
    - search() NEVER raises exceptions externally
    - All errors caught internally, logged, return []
    - Allows parallel execution to continue if one fails
    """
    @abstractmethod
    async def search(query, max_results) -> List[SearchResult]:
        # Returns empty list on failure, never raises
        pass

    @property
    def horizon(self) -> SearchHorizon:  # DEPTH/BREADTH/TRENDS
    @property
    def cost_per_query(self) -> float:
    @property
    def supports_citations(self) -> bool:
```

**Enums**:
- `SearchHorizon`: DEPTH (academic), BREADTH (wide), TRENDS (emerging)
- `BackendHealth`: SUCCESS, DEGRADED, FAILED
- `SearchResult`: Standardized format (url, title, snippet, backend)

**Exceptions** (`exceptions.py`, 99 lines):
- `BackendError` with full context tracking
- `RateLimitError`, `BackendUnavailableError`, `InsufficientResultsError`
- `AuthenticationError`, `TimeoutError`

### Three Backend Implementations

#### 1. TavilyBackend - DEPTH Horizon (`tavily_backend.py`, 225 lines)

**Specialization**: Academic papers, industry reports, authoritative sources

**Features**:
- Uses `tavily-python` library (TavilyClient)
- API key auto-loading from env or `/home/envs/tavily.env`
- Graceful error handling (catches all exceptions, returns empty list)
- Health check via test query
- Citation-quality sources

**Cost**: $0.02 per query

**Example sources**: Grand View Research, Fortune Business Insights, IEEE papers, Gartner reports

#### 2. SearXNGBackend - BREADTH Horizon (`searxng_backend.py`, 234 lines)

**Specialization**: Wide coverage, recent content, diverse perspectives

**Features**:
- Uses `pyserxng` library (245 search engines)
- Public instances (FREE) or self-hosted option
- Automatic failover across engines
- Tracks which engines succeeded per query
- Time-based filtering (recent content emphasis)
- Domain diversity tracking

**Cost**: $0 (public instances) or $10-20/month (self-hosted VPS)

**Engines**: Google, Bing, DuckDuckGo, Qwant, + 241 others (academic, news, code repositories, etc.)

**Why SearXNG over DDGS**:
- 245 engines vs 10 (24x more diversity)
- Better rate limit resilience (spread across engines)
- Production-ready with automatic failover
- Legitimate metasearch (vs scraping gray area)
- Public instances available (no infrastructure needed)

#### 3. GeminiAPIBackend - TRENDS Horizon (`gemini_api_backend.py`, 247 lines)

**Specialization**: Trend analysis, expert opinions, emerging developments

**Features**:
- Uses existing `GeminiAgent` with `google_search` grounding
- **Replaces Gemini CLI fallback** (Session 022-024 migration)
- Structured JSON output via `response_schema`
- Grounding metadata extraction
- API key auto-loading from env or `/home/envs/gemini.env`

**Cost**: $0 (FREE tier: 1,500 grounded queries/day)

**Focus**: Trending discussions, expert predictions, market shifts, emerging technologies

### Graceful Degradation Design

**No Silent Failures**:
```python
async def search(self, query, max_results):
    try:
        # Execute search logic
        results = self._do_search(query)
        logger.info("search_success", results_count=len(results))
        return results
    except Exception as e:
        # GRACEFUL: Log with full context, return empty, don't raise
        logger.error(
            "search_failed",
            query=query,
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc()
        )
        return []  # Continue execution
```

**Benefits**:
- Parallel execution continues if one backend fails
- All errors logged with full context (query, error type, traceback)
- Health monitoring via `backend_health` status
- Quality score calculation based on successful backends

## Changes Made

### New Files Created (6 files, 1,101 lines)

**Backend Infrastructure**:
- `src/research/backends/__init__.py:1-77` - Package exports for all backends
- `src/research/backends/base.py:1-219` - SearchBackend base class, enums, SearchResult
- `src/research/backends/exceptions.py:1-99` - Custom exceptions with context
- `src/research/backends/tavily_backend.py:1-225` - Tavily Search API (DEPTH)
- `src/research/backends/searxng_backend.py:1-234` - SearXNG metasearch (BREADTH)
- `src/research/backends/gemini_api_backend.py:1-247` - Gemini API grounding (TRENDS)

### Dependencies Added

**Updated `requirements-topic-research.txt`**:
- Line 45-46: Added `tavily-python==0.7.12` (already installed)
- Line 47-50: Added `pyserxng==0.1.0` with feature notes

**Installed**:
```bash
pip install pyserxng==0.1.0  # ✅ SUCCESS (25 kB)
```

### TASKS.md Updated

**Added Session 026 section** (lines 30-109):
- Architecture overview
- 4-phase implementation plan (40 tasks)
- Success criteria (99%+ reliability, 20-25 sources, $0.02 cost)

## Testing

**Phase 1-2 Validation**:
- ✅ All backends import successfully
- ✅ Package exports working (`from src.research.backends import *`)
- ✅ No syntax errors
- ✅ Dependencies installed correctly

**Pending Testing** (Phase 4):
- Unit tests for each backend (health checks, graceful failure)
- Integration tests (parallel execution, 1/2/3 backend failures)
- E2E test with 30 real topics (10 PropTech, 10 SaaS, 10 Fashion)
- Performance benchmarking (time, cost, quality)

## Performance Impact

**Expected Outcomes** (to be validated in Phase 3-4):

| Metric | Current | Target | Method |
|--------|---------|--------|--------|
| **Sources per report** | 8-10 | 20-25 | Parallel 3-backend fusion |
| **Cost per topic** | $0.02 | $0.02 | Only Tavily costs money |
| **Reliability** | ~95% | 99%+ | ≥1 backend succeeds |
| **Source diversity** | Single index | 3 horizons | Tavily + SearXNG + Gemini |
| **Silent failures** | Possible | 0 | Comprehensive logging |
| **Execution time** | 60-90s | 60-90s | Parallel (no sequential delay) |

**Cost Breakdown**:
- Tavily API: $0.02/query
- SearXNG: $0 (public instances)
- Gemini API: $0 (1,500/day free tier)
- **Total**: $0.02/topic (unchanged)

## Architecture Decision

**Decision**: Complementary Parallel Backends (not replacement or fallback)

**Context**: Initial proposal was to replace Tavily with free alternatives (DDGS). User insight: "why eliminate and replace, why not complement?!"

**Decision**: Use all three backends in parallel with specialized horizons

**Rationale**:
1. **Diversity**: Each backend specializes in different source types
   - Tavily: Academic rigor (peer-reviewed, industry reports)
   - SearXNG: Breadth (245 engines, recent content, diverse outlets)
   - Gemini: Trends (expert opinions, emerging patterns)

2. **Cost-Effective**: Only Tavily costs money, others FREE
   - Same $0.02/topic cost
   - 2-3x more sources (20-25 vs 8-10)

3. **Resilience**: Graceful degradation if any backend fails
   - Continue with successful backends
   - No single point of failure

4. **Quality**: Multi-perspective synthesis
   - Combine authoritative + diverse + trending sources
   - Better coverage than any single backend

**Alternatives Considered**:
- **Replacement** (DDGS only): Would save $0.02 but lose academic sources, unknown quality
- **Tiered** (free first, paid if needed): Complex logic, unpredictable costs
- **Cascading fallback**: Sequential (slower), treats Gemini API as last resort (wrong!)

**Consequences**:
- **Positive**: More sources, better diversity, same cost, higher reliability
- **Negative**: More code complexity, 3 dependencies vs 1
- **Neutral**: Execution time unchanged (parallel, not sequential)

## Next Steps (Phase 3-4)

### Phase 3: Orchestrator Refactoring (Days 6-7)

**Remaining Tasks**:
1. Refactor `DeepResearcher.__init__()` - Initialize 3 backends
2. Implement `research_topic()` - Parallel execution with `asyncio.gather(return_exceptions=True)`
3. Implement `_search_with_logging()` - Comprehensive error logging wrapper
4. Build specialized query builders:
   - `_build_depth_query()` - Academic/authoritative focus
   - `_build_breadth_query()` - Recent content, diverse perspectives
   - `_build_trends_query()` - Emerging patterns, predictions
5. Implement `_merge_with_diversity()` - Source fusion + deduplication
6. Implement `_calculate_quality_score()` - Sources + backend health + domain diversity
7. Add `backend_stats` tracking - Success/failure rates per backend
8. Add `get_backend_statistics()` - Health monitoring API

### Phase 4: Testing & Configuration (Days 8-10)

9. Write unit tests for all 3 backends (graceful failure, health checks)
10. Write integration tests:
    - All backends succeed
    - One backend fails (graceful continuation)
    - Two backends fail (minimum threshold)
    - All backends fail (appropriate error)
    - Logging verification (no silent failures)
11. Update configuration schema in `config/markets/*.yaml`
12. Run E2E test with 30 real topics (10 PropTech, 10 SaaS, 10 Fashion)
13. Measure: backend success rates, sources/topic, quality scores, cost, time

### Configuration Schema (To Be Added)

```yaml
# config/markets/proptech_de.yaml
deep_research:
  min_successful_backends: 1  # Continue if ≥1 succeeds
  require_paid_backend: false  # Force Tavily success if true

  backends:
    tavily:
      enabled: true
      horizon: "depth"
      max_results: 10

    searxng:
      enabled: true
      horizon: "breadth"
      max_results: 30
      instance_url: null  # Use public instances

    gemini_api:
      enabled: true
      horizon: "trends"
      max_results: 12
      model: "gemini-2.5-flash"
```

## Related Issues

**Replaced**:
- Gemini CLI fallback (`_gemini_cli_fallback()` in `deep_researcher.py:374-456`)
- Now using Gemini API with `google_search` grounding (Session 024 migration)

**Addressed**:
- User requirement: "design it in a way, that even if a service fails (plan proper logging to avoid failing silently) it should graciously continue working"
- Solution: All backends return empty list on failure, comprehensive logging, health status tracking

## Notes

**Token Usage**: 110k / 200k tokens (55% used)

**Files Structure**:
```
src/research/backends/
├── __init__.py               (77 lines, exports)
├── base.py                   (219 lines, base classes)
├── exceptions.py             (99 lines, custom exceptions)
├── tavily_backend.py         (225 lines, DEPTH)
├── searxng_backend.py        (234 lines, BREADTH)
└── gemini_api_backend.py     (247 lines, TRENDS)
```

**Why This Matters**:
- **For Users**: More comprehensive research reports with diverse sources
- **For System**: Higher reliability, no silent failures, better monitoring
- **For Cost**: Same $0.02/topic, but 2-3x more sources
- **For Quality**: Multi-perspective synthesis (academic + web + trends)

**Learning**: User's insight to use "complementary" instead of "replacement" led to superior architecture. Original proposal would have saved $0.02 but sacrificed academic sources. Parallel approach gives best of all worlds.
