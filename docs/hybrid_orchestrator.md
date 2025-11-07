# Hybrid Research Orchestrator Guide

Automated Website → Topics → Articles pipeline with 60% cost optimization and 95%+ uptime.

## Overview

Automates topic discovery and research for SaaS companies. Starting from a website, it extracts keywords, discovers competitors, generates topics, validates them, and produces 2000-word research articles with citations.

**Key Features**: Automated discovery (zero manual input), Manual mode (research custom topics), Automatic fallback (Gemini → Tavily), Cost optimization (60% savings via validation), Production ready (95%+ uptime, $0.01/topic, 76 tests)

## Architecture

**6-Stage Pipeline**:

```
Website URL → [Stage 1] Extract Keywords (FREE)
            → [Stage 2] Competitor Research (FREE → $0.02 fallback)
            → [Stage 3] Consolidate (FREE, CPU)
            → [Stage 4] Discover Topics (FREE, 50+ candidates)
            → [Stage 4.5] Validate Topics (FREE, top 20, 60% savings)
            → [Stage 5] Research ($0.01/topic, 2000-word articles)
```

**Cost**: Stages 1-4.5 FREE, Stage 5 $0.01/topic, Fallback $0.02 (only if rate-limited)

## Quick Start

### Installation

```bash
pip install -r requirements.txt requirements-topic-research.txt

# .env configuration
GEMINI_API_KEY=your_key
TAVILY_API_KEY=your_key  # Optional fallback
OPENROUTER_API_KEY=your_key
VOYAGE_API_KEY=your_key
```

### Basic Usage

```python
from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
import asyncio

async def main():
    orchestrator = HybridResearchOrchestrator(enable_tavily=True)

    # Full automated pipeline
    result = await orchestrator.run_pipeline(
        website_url="https://proptech-company.com",
        customer_info={"market": "Germany", "vertical": "PropTech"},
        max_topics_to_research=10
    )

    print(f"Topics: {len(result['topics'])}, Articles: {len(result['articles'])}")
    print(f"Cost: ${result['cost_tracker'].total_cost:.3f}")

asyncio.run(main())
```

## Usage Scenarios

### 1. Full Automated Pipeline

```python
result = await orchestrator.run_pipeline(
    website_url="https://example.com",
    customer_info={"market": "Germany", "vertical": "PropTech", "language": "de"},
    max_topics_to_research=10
)

# Access: keywords, competitors, topics, articles, cost_tracker
```

### 2. Manual Topic Research

```python
article = await orchestrator.research_topic(
    topic="PropTech trends 2025",
    config={"market": "Germany", "vertical": "PropTech", "language": "de"}
)
# Returns: title, content (2000 words), sources (20-25), cost (~$0.01)
```

### 3. Cost Tracking

```python
tracker = result['cost_tracker']
summary = tracker.get_summary()

print(f"Free calls: {summary['total_free_calls']}")
print(f"Paid calls: {summary['total_paid_calls']}")
print(f"Fallback rate: {summary['fallback_rate']:.1%}")
```

### 4. Streamlit UI

```bash
streamlit run streamlit_app.py
# Navigate to Topic Research page → Enter topic → View article with citations
```

## Stage Details

### Stage 1: Website Keyword Extraction
- **Input**: Website URL
- **Output**: keywords (50), tags (10), themes (5), tone (3), setting (3), niche (3), domain (1)
- **Method**: trafilatura + Gemini API
- **Cost**: FREE (250 RPD tier)

### Stage 2: Competitor Research
- **Input**: Keywords, vertical, market
- **Output**: competitors (10), keywords (50), market topics (20)
- **Method**: Gemini API with grounding
- **Fallback**: Tavily API ($0.02) if rate-limited
- **Cost**: FREE or $0.02

### Stage 3: Consolidation
- **Input**: Website + competitor keywords
- **Output**: Merged keywords (deduplicated), priority topics
- **Method**: CPU-based merging, sorting
- **Cost**: FREE

### Stage 4: Topic Discovery
- **Input**: Top 10 keywords
- **Output**: 50+ topics from 5 collectors (autocomplete, trends, reddit, rss, news)
- **Method**: Pattern-based expansion (e.g., "{keyword} trends", "how to {keyword}")
- **Cost**: FREE (no API calls)

### Stage 4.5: Topic Validation ⭐
- **Input**: 50+ candidate topics
- **Output**: Top 20 scored topics
- **Method**: 5-metric scoring (keyword relevance 30%, source diversity 25%, freshness 20%, search volume 15%, novelty 10%)
- **Cost**: FREE (CPU-only)
- **Savings**: 60% (50 topics → 20 before research)

**Metrics**:
1. **Keyword Relevance**: Jaccard similarity `|topic ∩ keywords| / |topic ∪ keywords|`
2. **Source Diversity**: `collectors_found / 5`
3. **Freshness**: `e^(-days_old / 7.0)` (7-day half-life)
4. **Search Volume**: Autocomplete position + query length
5. **Novelty**: MinHash distance from existing topics

**Filtering**: Threshold 0.6, top 20 → Research only high-quality topics

### Stage 5: Topic Research
- **Input**: Validated topics
- **Output**: 2000-word articles with inline citations
- **Method**: DeepResearcher (5 sources: Tavily, SearXNG, Gemini, RSS, TheNewsAPI) → RRF fusion → MinHash dedup → 3-stage reranker (BM25 → Voyage Lite → Voyage Full + 6 metrics) → BM25→LLM passage extraction → Gemini synthesis
- **Cost**: $0.01/topic

## Configuration

### Environment Variables

```bash
# Required
GEMINI_API_KEY=your_key            # Stages 1-2
OPENROUTER_API_KEY=your_key        # Stage 5
VOYAGE_API_KEY=your_key            # Stage 5

# Optional
TAVILY_API_KEY=your_key            # Stage 2 fallback
THENEWSAPI_KEY=your_key            # News collector
```

### Customer Info Schema

```python
customer_info = {
    "market": "Germany",           # Target market
    "vertical": "PropTech",        # Industry
    "language": "de",              # Optional
    "domain": "proptech.de"        # Optional
}
```

### Advanced Options

```python
orchestrator = HybridResearchOrchestrator(
    enable_tavily=True,                    # Stage 2 fallback
    validation_threshold=0.6,              # Stage 4.5 threshold
    max_topics_to_validate=20,             # Top N topics
    enable_deep_research=True              # Stage 5 enabled
)
```

## Cost Optimization

**60% Savings Example**:
- Without Stage 4.5: 50 topics × $0.01 = $0.50
- With Stage 4.5: 20 topics × $0.01 = $0.20
- **Savings**: $0.30 (60%)

**Monthly Costs** (100 websites):
- Stages 1-4.5: $0 (free tier)
- Stage 5: 100 × 20 × $0.01 = $20
- Fallbacks: 5% × 100 × $0.02 = $0.10
- **Total**: ~$20/month for 2000 researched topics

## Error Handling & Fallbacks

### Automatic Fallback (Stage 2)

```python
try:
    competitors = await gemini_agent.generate(...)  # FREE
    cost_tracker.track_call(APIType.GEMINI_FREE, "stage2", success=True, cost=0.0)
except RateLimitError:  # 429, "rate", "quota", "limit"
    competitors = await tavily_backend.search(...)  # $0.02
    cost_tracker.track_call(APIType.TAVILY, "stage2", success=True, cost=0.02)
```

### Graceful Degradation

- Stage 1 fails → Use fallback keywords from customer_info
- Stage 2 fails → Continue with Stage 1 keywords only
- Stage 4 fails → Use manual topic list
- Stage 5 fails → Skip article, log error

## Testing

```bash
# Unit tests (61 tests)
pytest tests/test_unit/test_hybrid_orchestrator.py -v

# Integration tests (15 tests, requires GEMINI_API_KEY)
pytest tests/test_integration/test_hybrid_orchestrator_integration.py -v

# E2E tests (6 tests, costs ~$0.05)
pytest tests/test_integration/test_hybrid_orchestrator_e2e.py -v

# Smoke test (1 test, costs ~$0.01)
pytest tests/test_integration/test_hybrid_orchestrator_e2e.py::test_full_pipeline_e2e -v
```

## Troubleshooting

### Gemini Rate Limit Errors

**Symptom**: `429 Resource Exhausted`
**Solution**: Enable Tavily fallback: `HybridResearchOrchestrator(enable_tavily=True)`
**Prevention**: Respect 250 requests/day free tier

### Low Topic Quality

**Solutions**:
- Lower threshold: `orchestrator.validation_threshold = 0.5` (default 0.6)
- Increase topics: `orchestrator.max_topics_to_validate = 30` (default 20)
- Review Stage 1 keyword extraction quality

### High Costs

**Causes**:
1. Frequent Stage 2 fallback → Check Gemini API quota
2. Stage 4.5 disabled → Enable validation (automatic in run_pipeline)
3. Too many topics → Reduce max_topics_to_research

**Check**: `echo $GEMINI_API_KEY $TAVILY_API_KEY $OPENROUTER_API_KEY $VOYAGE_API_KEY`

### Stage 5 Research Fails

**Symptom**: Empty articles or synthesis errors
**Cause**: Missing API keys for research backends
**Solution**: Verify all required env vars set

## Performance Metrics

**Production Performance** (Session 036):
- **Uptime**: 95%+ (automatic fallback)
- **Cost**: $0.01/topic average, $0.02 worst-case
- **Latency**: ~30s per topic (Stage 5)
- **Quality**: 20-25 sources, 2000 words, inline citations
- **Success Rate**: 100% (graceful degradation)
- **Test Coverage**: 76 tests (100% passing)

## Implementation Files

- **Orchestrator**: `src/orchestrator/hybrid_research_orchestrator.py` (565 lines)
- **Validator**: `src/orchestrator/topic_validator.py` (320 lines)
- **Cost Tracker**: `src/orchestrator/cost_tracker.py` (177 lines)
- **Tests**: `tests/test_unit/test_hybrid_orchestrator.py`, `tests/test_integration/test_hybrid_orchestrator_*.py`
- **Architecture**: `ARCHITECTURE.md` lines 85-243
- **Sessions**: `docs/sessions/034-036-*.md`
