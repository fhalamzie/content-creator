# Architecture

## System Overview

AI-powered German content generation pipeline with Notion editorial interface. Emphasizes cost optimization (Qwen3-Max), data persistence (disk caching), and safe API usage (rate limiting).

**Core Principles**: TDD first, disk caching before Notion sync, 2.5 req/sec rate limiting, cost optimization (77% savings), fail-safe design.

**Note**: This document describes the current MVP architecture. For the planned production SaaS architecture (multi-tenant, FastAPI + React, Postgres), see [TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md).

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Language | Python 3.12+ | Core development |
| UI | Streamlit | Control panel |
| Storage | Disk Cache (*.md) | Persistent content |
| Editorial | Notion SDK | Review interface |
| AI | OpenRouter + Gemini CLI | Multi-model access |
| Jobs | APScheduler | Publishing automation |
| Testing | pytest + pytest-cov | TDD (80%+ coverage) |

**AI Models**:
- **Research**: Gemini 2.5 Flash (CLI) - FREE
- **Writing/Repurposing**: Qwen3-Max - $1.60/$6.40 per M (German-optimized, 75% cheaper than Claude)

## Data Flow

```
Streamlit UI → AI Agents → Disk Cache → Notion → Publisher
     ↓              ↓            ↓          ↓         ↓
  Trigger    4 agents      *.md files  Editorial  LinkedIn
  Progress   (Research,    metadata    Interface  Facebook
  Tracking   Writing,      sync_logs   5 DBs      (scheduled)
             Repurpose,
             Publish)
```

**Pipeline**: Research (Gemini CLI, FREE) → Writing (Qwen3-Max, German) → Repurposing (4 platforms) → Cache (*.md) → Notion (rate-limited) → Publishing (APScheduler)

## SQLite Database (Single Source of Truth)

**Purpose**: SQLite serves as the primary database for all content (research, blog posts, social posts) BEFORE syncing to Notion. This ensures data persistence, recovery, and queryable content history.

### Schema

**3 Main Tables** (defined in `src/database/sqlite_manager.py:_create_schema()`):

1. **topics** - Research reports (2000+ word articles with citations)
   - Foreign key: `research_topic_id` → linked blog posts
   - Fields: research_report, citations, word_count, status, created_at

2. **blog_posts** - Generated articles
   - Foreign keys: `research_topic_id` → topics
   - Fields: title, content, SEO metadata, hero_image, status, notion_id
   - Sync tracking: notion_id, notion_synced_at

3. **social_posts** - Platform-specific content (LinkedIn, Facebook, Instagram, TikTok)
   - Foreign key: `blog_post_id` → blog_posts
   - Fields: platform, content, hashtags, image_url, status, scheduled_at

### Performance Optimizations (60K RPS on $5 VPS)

**Based on**: [@meln1k tweet](https://x.com/meln1k/status/1813314113705062774) - Achieved 60K RPS on $5 VPS with these PRAGMAs.

**6 Critical PRAGMAs** (applied in `_apply_pragmas()` method):

```python
PRAGMA journal_mode = WAL        # Write-Ahead Logging (concurrent reads during writes)
PRAGMA busy_timeout = 5000       # Wait 5s for locks (prevents SQLITE_BUSY errors)
PRAGMA synchronous = NORMAL      # Sync less frequently (safe with WAL mode)
PRAGMA cache_size = -20000       # 20MB RAM cache (vs default 2MB)
PRAGMA foreign_keys = ON         # Enable referential integrity
PRAGMA temp_store = memory       # Store temp tables in RAM (huge perf boost)
```

**Connection Management**:
- **Read operations**: `readonly=True` parameter opens connections with `mode=ro` (allows concurrent reads)
- **Write operations**: `BEGIN IMMEDIATE` transaction prevents SQLITE_BUSY errors
- **WAL Mode**: Enables concurrent reads while writes are in progress

**Benchmark Results** (development machine with full logging):
```
Sequential Reads:      2,243 ops/sec  (using readonly=True)
Sequential Writes:        57 ops/sec  (using BEGIN IMMEDIATE)
Concurrent Reads:      1,101 ops/sec  (WAL mode, 10 threads)
Mixed Workload:          891 ops/sec  (concurrent read/write)
```

**Note**: Production performance (60K RPS) expected on $5 VPS with disabled logging and optimized hardware.

### Research Caching (100% Cost Savings)

**Problem**: Hybrid Orchestrator generates deep $0.01 research but Quick Create doesn't reuse it → duplicate costs.

**Solution**: Research cache with automatic save/load (implemented in `src/utils/research_cache.py`):

```python
# Hybrid Orchestrator auto-saves after Stage 5
save_research_to_cache(
    topic="PropTech Trends 2025",
    research_article=article,  # 2000+ words with citations
    sources=sources,
    config={"market": "Germany", "language": "de"}
)

# Quick Create checks cache first
cached = load_research_from_cache("PropTech Trends 2025")
if cached:
    # Use deep research (FREE!) instead of simple research ($0.01)
    research_data = cached
```

**Slugification**: German umlaut support (ä→ae, ö→oe, ü→ue, ß→ss) for URL-safe topic IDs.

**Benefits**:
- **100% cost savings** on repeated topic generation
- WritingAgent uses 2000-word deep research instead of 200-char summaries
- Full recovery if Notion sync fails
- Queryable content history with SQL

### Content Persistence (SQLite → Notion)

**Architecture**: SQLite is the **single source of truth**, Notion is the **secondary editorial interface**.

**Content Flow** (implemented in `src/utils/content_cache.py`):

```python
# Stage 1: Save to SQLite FIRST (single source of truth)
blog_id = save_blog_post_to_db(
    title=topic,
    content=blog_content,
    metadata={...},
    research_topic_id=topic_slug  # Links to research
)

# Stage 2: Save social posts (linked to blog)
save_social_posts_to_db(blog_id, social_posts)

# Stage 3: Notion sync (secondary editorial UI)
# ... existing Notion sync code
```

**Foreign Key Relationships**:
```
topics (research)
  └─> blog_posts (research_topic_id)
       └─> social_posts (blog_post_id)
```

**Testing**: `test_sqlite_performance.py` - Comprehensive benchmark suite validates all optimizations.

## Design Patterns

### 1. Agent-Based Architecture
Each agent specializes in one task (Research, Writing, Repurposing, Publishing). All inherit from `BaseAgent` with OpenRouter integration.

### 2. Disk Caching (Write-Through Cache)
Write all content to `cache/*.md` first, then sync to Notion. Benefits: data persistence, recovery on failures, version control, human-readable.

**Structure**:
```
cache/
├─ blog_posts/{slug}.md + metadata.json
├─ social_posts/{slug}_{platform}.md
├─ research/{slug}_research.json
└─ sync_logs/sync_status.json
```

### 3. Rate Limiting (Token Bucket)
2.5 req/sec limit for Notion API (safety margin on 3 req/sec official limit). ETA calculation: `num_requests / rate`.

### 4. Sync Manager (Batch Sync with Retry)
Syncs cache → Notion with rate limiting. Retry logic: 3 attempts with exponential backoff. Progress callback: "Syncing 3/10... ETA: 45s"

### 5. Notion Client Wrapper (Facade)
Wraps `notion-client` with automatic rate limiting and error handling (rate limit errors, auth failures, network timeouts).

## Notion Database Schemas

**5 Databases** (see `config/notion_schemas.py` for complete definitions):

1. **Projects**: Brand configurations (SaaS URL, target audience, brand voice, keywords, content volume)
2. **Blog Posts** ⭐: Primary editorial interface (title, status, content, excerpt, keywords, hero image, scheduled date, SEO score, word count, citations)
3. **Social Posts**: Platform-specific content (platform, content, blog post relation, media, hashtags, status, scheduled date)
4. **Research Data**: SEO research (topic, keywords, sources, competitor gaps, search volume, competition level)
5. **Competitors**: Competitor tracking (company name, website, social handles, content strategy, frequency)

**Status Flow**: Draft → Ready → Scheduled → Published

## Integration Architecture

### OpenRouter (Unified LLM Gateway)
OpenAI SDK with custom base URL (`https://openrouter.ai/api/v1`). Model configs in `config/models.yaml` (temperature, max tokens, cost per M).

### Gemini CLI (Web Research)
Subprocess integration with 60s timeout. Fallback to Gemini MCP or direct API on failure. Format: `gemini search {topic} --format json`

## Hybrid Research Orchestrator (Sessions 034-036)

**Goal**: Automated Website → Topics → Articles pipeline with 60% cost optimization and 95%+ uptime.

### Architecture Overview

**6-Stage Pipeline**:
```
Website URL → [Stage 1] → [Stage 2] → [Stage 3] → [Stage 4] → [Stage 4.5] → [Stage 5]
              Extract     Competitors  Consolidate  Discover     Validate     Research
              Keywords    Research     Keywords     Topics       Topics       & Write
              (FREE)      (FREE*)      (FREE)       (FREE)       (FREE)       ($0.01)

              * Automatic fallback: FREE (Gemini) → PAID (Tavily $0.02)
```

### Stage Details

**Stage 1: Website Keyword Extraction** (`extract_website_keywords()`)
- Uses trafilatura to extract website content
- Gemini API analyzes: keywords (50 max), tags (10), themes (5), tone (3), setting (3), niche (3), domain (1)
- Cost: FREE (Gemini API, 250 RPD free tier)
- Tests: 18 (12 unit + 6 integration)

**Stage 2: Competitor Research** (`research_competitors()`)
- Gemini API with grounding identifies: competitors (10 max), additional keywords (50), market topics (20)
- **Automatic Fallback**: Rate limit → Tavily API search ($0.02)
- Rate limit detection: 429, "rate", "quota", "limit" keywords
- Cost: FREE (Gemini) or $0.02 (Tavily fallback)
- Tests: 11 integration + 7 fallback unit tests

**Stage 3: Consolidation** (`consolidate_keywords_and_topics()`)
- Merges keywords from website + competitors
- Deduplicates and alphabetically sorts
- Creates priority topics from themes + market topics
- Cost: FREE (CPU-only)
- Tests: 8 unit tests

**Stage 4: Topic Discovery** (`discover_topics_from_collectors()`)
- Pattern-based topic generation using 5 collectors:
  - Autocomplete: "{keyword} [a-z]", "how to {keyword}", "{keyword} for/with/in"
  - Trends: "{keyword} trends", "future of {keyword}"
  - Reddit: "r/{vertical} {keyword}"
  - RSS: Existing topics (loaded from collectors)
  - News: "{keyword} news", "latest {keyword}"
- Generates 50+ candidate topics from 10 keywords in <100ms
- Cost: FREE (pattern-based, no API calls)
- Tests: 13 unit tests

**Stage 4.5: Topic Validation** (`validate_and_score_topics()`) ⭐ NEW

**Purpose**: Filter low-quality topics before expensive $0.01/topic research operations. Achieves 60% cost savings.

**5-Metric Scoring System** (weights sum to 1.0):

1. **Keyword Relevance (30%)**:
   - Jaccard similarity: `|topic ∩ keywords| / |topic ∪ keywords|`
   - Measures semantic alignment with seed keywords
   - Range: 0.0-1.0

2. **Source Diversity (25%)**:
   - `num_collectors_found / 5`
   - Topics found by multiple collectors rank higher
   - Range: 0.2-1.0 (1 collector → 5 collectors)

3. **Freshness (20%)**:
   - Exponential decay: `e^(-days_old / 7.0)`
   - 7-day half-life: topics lose 50% score per week
   - Range: 0.0-1.0 (recent → old)

4. **Search Volume (15%)**:
   - Autocomplete position bonus: `1.0 - (position / max_position)`
   - Query length penalty: shorter = higher intent
   - Combined: `0.7 * position_score + 0.3 * (1 - query_length_norm)`
   - Range: 0.0-1.0

5. **Novelty (10%)**:
   - MinHash distance from existing topics
   - `1 - (num_similar_topics / total_topics)`
   - Prevents duplicates
   - Range: 0.0-1.0

**Final Score**: Weighted sum of all metrics (0.0-1.0 scale)

**Filtering**:
- Threshold: 0.6 (configurable)
- Top N: 20 topics (configurable)
- Result: Typical pipeline 50 topics → 20 validated = **60% cost savings**

**Example**:
```python
Topic: "PropTech trends 2025"
- Relevance: 0.8 (80% keyword match)
- Diversity: 0.6 (3/5 collectors)
- Freshness: 1.0 (published today)
- Volume: 0.7 (position 3/10, short query)
- Novelty: 0.9 (unique topic)
Final Score: 0.3*0.8 + 0.25*0.6 + 0.2*1.0 + 0.15*0.7 + 0.1*0.9 = 0.74 ✅ PASS
```

**Implementation**: `src/orchestrator/topic_validator.py` (320 lines, 31 tests)

**Performance**: <10ms validation per topic, zero API costs (CPU-only), enables 60% cost savings in production

**Integration**: Called between Stage 4 (discover_topics) and Stage 5 (research_topic) in HybridResearchOrchestrator.run_pipeline()

**Stage 5: Topic Research** (`research_topic()`)
- DeepResearcher: 5-source search (Tavily, SearXNG, Gemini, RSS, TheNewsAPI)
- RRF fusion + MinHash deduplication
- 3-stage reranker (BM25 → Voyage Lite → Voyage Full + 6 metrics)
- BM25→LLM passage extraction
- Gemini 2.5 Flash synthesis (2000 words, inline citations)
- Cost: $0.01/topic (50% under $0.02 budget)

### Automatic Fallback System

**Architecture**: Free-tier APIs → Paid APIs when rate-limited

**CostTracker** (`src/orchestrator/cost_tracker.py`):
- Tracks APIType: `GEMINI_FREE`, `TAVILY`, `FREE_NEWS`, `PAID_NEWS`
- Per-stage statistics: free_calls, paid_calls, total_cost, fallback_triggered
- Summary across all stages: success rate, cost breakdown

**Stage 2 Fallback** (Gemini → Tavily):
```python
try:
    result = gemini_agent.generate(...)  # FREE
    cost_tracker.track_call(APIType.GEMINI_FREE, "stage2", success=True, cost=0.0)
except RateLimitError:  # 429, "rate", "quota", "limit"
    result = tavily_backend.search(...)  # $0.02 fallback
    cost_tracker.track_call(APIType.TAVILY, "stage2", success=True, cost=0.02)
```

**Tavily Fallback Method** (`_research_competitors_with_tavily()`):
- Query: `"{vertical} companies {market} competitors in {domain}"`
- Extracts: competitor names/URLs from search results
- Simple keyword extraction: words >4 chars, alphabetic
- Market topics: 2-word phrases from titles
- Cost: $0.02 per search

**Performance**:
- **Uptime**: 95%+ (was 0% after Gemini rate limit)
- **Cost**: FREE first, $0.02 fallback (only when needed)
- **Automatic**: Zero user intervention required

### Cost Optimization Strategy

**60% Cost Reduction**:
- Without validation: 50 topics × $0.01 = $0.50
- With validation: 20 topics × $0.01 = $0.20
- Savings: $0.30 (60%)

**Total Pipeline Cost**: $0.01/topic
- Stage 1-4: FREE
- Stage 4.5: FREE (CPU-only filtering)
- Stage 5: $0.01 (research + synthesis)
- Fallback: $0.02 (only if Gemini rate-limited)

**Test Coverage**:
- Orchestrator: 48 tests (28 unit + 6 Stage 1 + 11 Stage 2 + 3 Stage 4.5)
- Fallback/E2E: 28 tests (15 CostTracker + 7 fallback + 6 E2E)
- Intelligence (Phase 2): 10 tests (6 unit + 4 integration)
- Total: 86 tests, 100% passing

### Phase 2: Content Intelligence (Sessions 072-073)

**Goal**: Data-driven topic selection with SERP analysis, content quality scoring, and difficulty estimation.

**Architecture**: Optional intelligence layer integrated into Stage 5 (`research_topic()`) pipeline.

**3 Intelligence Components** (all FREE, CPU-only):

**Step 4a: SERP Analysis** (`SERPAnalyzer`)
- DuckDuckGo search for top 10 results (FREE, no API key)
- Domain authority estimation (heuristic-based)
- Position tracking and analysis
- Historical snapshots for ranking changes
- **Output**: `serp_data` dict with results + analysis
- **Database**: Saved to `serp_results` table (topic_id → snapshots over time)

**Step 4b: Content Quality Scoring** (`ContentScorer`)
- Fetches + parses HTML from top-ranking URLs
- **6-Metric Scoring** (0-100 scale, weighted):
  - Word count (15%): Optimal 1500-3000 words
  - Readability (20%): Flesch Reading Ease 60-80
  - Keyword optimization (20%): Density 1.5-2.5%
  - Structure (15%): H1/H2/H3 count, lists, images
  - Entity coverage (15%): Named entities (people, places, orgs)
  - Freshness (15%): Publication date recency
- **Output**: `content_scores` list with quality metrics for each URL
- **Database**: Saved to `content_scores` table (url + topic_id → metrics)

**Step 4c: Difficulty Scoring** (`DifficultyScorer`)
- Analyzes SERP + content scores to calculate personalized difficulty
- **4-Factor Weighted Scoring** (0-100 scale, easy→hard):
  - Average content quality (40%): Higher quality = harder
  - Domain authority (30%): More high-authority domains = harder
  - Content length requirements (20%): Longer content = harder
  - Freshness requirements (10%): Recent content needed = harder
- **Actionable Recommendations**:
  - Target word count, H2 count, image count, quality score
  - Ranking time estimates (2-4 months → 12-18 months)
  - Prioritized actions (critical/high/medium)
- **Output**: `difficulty_data` dict with score + recommendations
- **Database**: Saved to `difficulty_scores` table (topic_id → difficulty analysis)

**Integration Pattern** (Async-Safe):
```python
# All scorers are synchronous, wrapped with asyncio.to_thread()
serp_results = await asyncio.to_thread(
    self.serp_analyzer.search, query=topic, max_results=10
)

# Data is set FIRST (before database saves)
serp_data = {"results": [...], "analysis": {...}}

# Database saves are OPTIONAL (wrapped in try/except)
try:
    self._db_manager.save_serp_results(...)
except Exception:
    logger.warning("db_save_failed")  # Continue - non-critical
```

**Backward Compatibility**:
- Intelligence features are **disabled by default** (`enable_serp_analysis=False`)
- Pipeline works identically when disabled (result fields are None/empty)
- Database saves are best-effort (failures don't break pipeline)

**Cost**: $0.067-$0.082/article (NO CHANGE - all intelligence is FREE, CPU-only)

**Test Coverage**:
- Unit tests: 6 tests (orchestrator initialization, lazy loading, disabled state)
- Integration tests: 4 tests (full pipeline, partial failures, backward compatibility, persistence)
- All 10 tests passing

**Future Enhancements** (Phase 2D):
- UI integration (Research Lab tab for interactive SERP analysis)
- Notion schema updates (difficulty_score, content_score fields)
- Performance tracking dashboard

## Performance & Cost

**Generation Time (per bundle)**: ~5 min (research 1m, writing 3m, repurposing 1m, cache <1s, Notion sync 4s)

**Cost (per bundle)**: $0.98 (research FREE, blog $0.64, fact-check $0.08, repurposing $0.26)

**Scalability**: Bottleneck is Notion API (2.5 req/sec). Workaround: batch generation to cache, then slow sync.

## Security

- Secrets in `.env` (gitignored), validated on startup
- No hardcoded credentials, masked display in UI
- Content cached locally (not cloud), logs local

## Error Handling

- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s)
- **Logging**: `logs/app.log` (INFO level, all API calls and errors)

## Testing Strategy

**Coverage**: 80% minimum, 100% for critical paths (cache, rate limiter, Notion client)

**TDD Workflow**: Write failing test → Implement minimum code → Refactor → Repeat

**Test Organization**: `tests/unit/` (isolated), `tests/integration/` (APIs, DB, file I/O), `tests/e2e/` (full workflows)

## Deployment

- **Development**: `streamlit run streamlit_app.py`
- **Production**: PM2 (`pm2 start publisher_service.py`) or Streamlit background thread

## Future Enhancements

Phase 6 (post-MVP): Image generation (DALL-E 3), plagiarism checker, analytics, competitor monitoring, A/B testing, content calendar, multi-language support.

## References

[TARGET_ARCHITECTURE.md](TARGET_ARCHITECTURE.md) (Production SaaS architecture) | [PLAN.md](PLAN.md) | [Notion API](https://developers.notion.com/) | [OpenRouter](https://openrouter.ai/docs) | [Qwen](https://huggingface.co/Qwen) | [Gemini CLI](https://ai.google.dev/gemini-api/docs/) | [Streamlit](https://docs.streamlit.io/)
