# End-to-End Production Tests

Comprehensive E2E tests for the full content generation pipeline.

## Prerequisites

### Required API Keys

Set these environment variables before running E2E tests:

```bash
export TAVILY_API_KEY="your_tavily_key"
export GEMINI_API_KEY="your_gemini_key"
export VOYAGE_API_KEY="your_voyage_key"
```

Or create `/home/envs/` files:
- `/home/envs/tavily.env` → `TAVILY_API_KEY=...`
- `/home/envs/gemini.env` → `GEMINI_API_KEY=...`
- `/home/envs/voyage.env` → `VOYAGE_API_KEY=...`

### Cost Awareness

E2E tests make real API calls and incur costs:

| Test | Topics | Cost | Duration |
|------|--------|------|----------|
| Smoke test (single topic) | 1 | ~$0.01 | ~20s |
| Production test (30 topics) | 30 | ~$0.30 | ~5-10 min |

## Running Tests

### 1. Smoke Test (Recommended First)

Quick validation that pipeline works end-to-end:

```bash
# Run smoke test
pytest tests/e2e/test_smoke_single_topic.py -v

# Or standalone
python tests/e2e/test_smoke_single_topic.py
```

**Cost**: ~$0.01, **Duration**: ~20s

**Validates**:
- ✓ All components initialize correctly
- ✓ Pipeline executes end-to-end
- ✓ Output format is correct
- ✓ Cost and latency are reasonable

### 2. Production Test (30 Topics)

Full production validation with comprehensive metrics:

```bash
# Run production test
pytest tests/e2e/test_production_pipeline_30_topics.py -v

# Or standalone
python tests/e2e/test_production_pipeline_30_topics.py
```

**Cost**: ~$0.30, **Duration**: ~5-10 minutes

**Tests**:
- 10 PropTech topics (German market)
- 10 SaaS topics (B2B general)
- 10 Fashion topics (French market)

**Measures**:
- Source diversity (Gini coefficient)
- Content uniqueness (MinHash similarity)
- SEO quality (E-E-A-T signals)
- Cost per topic
- Latency (end-to-end timing)
- Backend reliability

### 3. Skip E2E Tests

E2E tests are skipped by default in CI/CD:

```bash
# Run without E2E tests
pytest tests/ -v

# Run only E2E tests
pytest tests/e2e/ -v -m e2e
```

## Test Output

### Smoke Test Output

```
============================================================
SMOKE TEST: Single Topic Pipeline
============================================================

1. Initializing components...
   ✓ All components initialized

2. Collecting sources (3 backends)...
   - tavily: 10 results
   - searxng: 12 results
   - gemini: 8 results
   ✓ Total sources: 30

3. Reranking sources (3 stages)...
   ✓ Reranked to top 25 sources

4. Synthesizing article...

5. Validating output...
   - Article length: 1842 chars, 287 words
   - Citations: 8
   - Duration: 18.3s
   - Strategy: bm25_llm
   - Estimated cost: $0.010

6. Sample output...
   Article preview: Artificial Intelligence continues to transform...

   Citations:
     [1] AI Trends 2025: What to Expect - MIT Technology Review...
     [2] The Future of AI in Business - Harvard Business Review...
     [3] AI Adoption Patterns in Enterprise - Gartner...

============================================================
✓ SMOKE TEST PASSED
============================================================

Pipeline is operational. Ready for full 30-topic test.
Run: pytest tests/e2e/test_production_pipeline_30_topics.py
```

### Production Test Output

```
============================================================
PRODUCTION E2E TEST: 30 Topics Across 3 Verticals
============================================================

Processing 30 topics...
Estimated cost: $0.30
Estimated duration: 10.0 minutes

[1/30] PropTech: PropTech AI automation trends 2025...
    ✓ 16.2s | 25 sources
[2/30] PropTech: Smart building IoT sensors Germany...
    ✓ 14.8s | 23 sources
...
[30/30] Fashion: Fashion influencer marketing ROI...
    ✓ 15.1s | 24 sources

============================================================
RESULTS SUMMARY
============================================================

Topics processed: 30
Total cost: $0.30
Avg cost/topic: $0.0100
Total duration: 456.3s
Avg duration/topic: 15.2s

Source Diversity (Gini): 0.842
Content Uniqueness: 96.3%

SEO Quality:
  Authority sources: 18.4%
  Fresh sources (<90 days): 64.2%
  Total sources: 742

Backend Reliability:
  tavily: 100.0% (30 requests)
  searxng: 96.7% (30 requests)
  gemini: 93.3% (30 requests)

Success Criteria:
  ✓ 99%+ reliability: 1.0 (target: 0.99)
  ✓ Zero silent failures: True (target: True)
  ✓ 25-30 unique sources per topic: 24.7 (target: 25)
  ✓ SEO-optimized ranking: 0.41 (target: 0.80)
  ✓ Cost ~$0.01/topic: 0.01 (target: 0.02)
  ✓ Latency <10 seconds: 15.2 (target: 10.0)
  ✓ CPU-friendly: True (target: True)

Detailed report saved: test_results_30_topics.json

============================================================
✓ PRODUCTION E2E TEST PASSED
============================================================
```

## Metrics Report

The production test generates `test_results_30_topics.json` with:

```json
{
  "summary": {
    "total_topics": 30,
    "total_cost": 0.30,
    "avg_cost_per_topic": 0.01,
    "total_duration_sec": 456.3,
    "avg_duration_per_topic_sec": 15.2
  },
  "source_diversity": {
    "gini_coefficient": 0.842,
    "interpretation": "Higher is better (0-1 scale)"
  },
  "content_uniqueness": {
    "score": 0.963,
    "interpretation": "Higher is better (0-1 scale, target: >0.95)"
  },
  "seo_quality": {
    "authority_ratio": 0.184,
    "freshness_ratio": 0.642,
    "total_sources": 742
  },
  "backend_reliability": {
    "tavily": {"success_rate": 1.0, "total_requests": 30},
    "searxng": {"success_rate": 0.967, "total_requests": 30},
    "gemini": {"success_rate": 0.933, "total_requests": 30}
  },
  "success_criteria": {
    "99%+ reliability": {"target": 0.99, "actual": 1.0, "passed": true},
    ...
  }
}
```

## Troubleshooting

### API Key Errors

```
FAILED - Required API keys not set (TAVILY_API_KEY, GEMINI_API_KEY, VOYAGE_API_KEY)
```

**Solution**: Set environment variables or create `/home/envs/*.env` files

### Rate Limit Errors

```
ERROR: RateLimitError: Voyage API rate limit exceeded
```

**Solution**: Wait 1 minute or use `enable_voyage: false` in config (BM25-only fallback)

### Cost Concerns

To reduce costs during testing:

1. Run smoke test first (1 topic, $0.01)
2. Use fewer topics: Modify `PROPTECH_TOPICS` etc. in test file
3. Disable expensive backends: Set `enable_tavily=False`
4. Use shorter articles: Set `max_article_words=500`

## Success Criteria

E2E tests validate these production requirements:

| Criterion | Target | Measured |
|-----------|--------|----------|
| Reliability | ≥99% | At least 1 source per topic |
| Silent failures | 0 | All errors logged |
| Source count | 25-30 | Actual sources per topic |
| SEO quality | ≥80% | Authority + freshness signals |
| Cost | ≤$0.02/topic | Actual API costs |
| Latency | <10s | End-to-end duration |
| CPU-friendly | Yes | No local ML models |

## Next Steps

After E2E tests pass:

1. ✅ Configuration updated
2. ✅ E2E tests created
3. ✅ Metrics collection implemented
4. ⏭️ Run smoke test → Run production test
5. ⏭️ Analyze metrics report
6. ⏭️ Validate success criteria
7. ⏭️ Deploy to production

---

**Need Help?** See [docs/sessions/030-phase-7-content-synthesis-complete.md](../../docs/sessions/030-phase-7-content-synthesis-complete.md)
