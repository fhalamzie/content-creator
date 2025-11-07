# Universal Topic Research Agent

Automated topic discovery and research system for SaaS companies. Finds trending topics in your industry before competitors do, validates SEO opportunities, and generates professional research reports with real citations.

**Business Value**: Stop guessing what to write about. Let AI discover high-demand topics with low competition, then deliver ready-to-use research reports.

## Features

- **Hybrid Research Orchestrator** (NEW) - Website → Topics → Articles with 60% cost optimization + automatic fallback
- **Automated Topic Discovery** - Monitor 100+ RSS feeds, Reddit discussions, Google Trends, autocomplete suggestions
- **Intelligent Feed Discovery** - Find industry-relevant feeds automatically using OPML seeds + Gemini expansion + SerpAPI
- **6-Stage Pipeline** - Website analysis → Competitor research → Topic validation → Research → Article
- **Automatic Fallback** - Gemini rate limit → Tavily API ensures 95%+ uptime
- **Professional Research Reports** - 2000-word articles at $0.01/topic (50% under budget)
- **Cost Tracking** - Monitor free vs paid API usage per stage
- **Notion Integration** - Review and approve discovered topics in Notion before writing
- **Smart Deduplication** - MinHash/LSH similarity detection keeps duplicate rate <5%
- **Background Automation** - Daily topic collection (2 AM) and weekly Notion sync (Monday 9 AM)

## Core Components

### Topic Discovery (FREE)

**FeedDiscoveryAgent** - Auto-discover industry RSS feeds (OPML + Gemini CLI + SerpAPI)

**RSSCollector** - Monitor 100+ blogs with conditional GET and full content extraction

**RedditCollector** - Discover customer questions via PRAW API with comment extraction

**TrendsCollector** - Catch rising topics using Gemini CLI (migrated from pytrends Nov 2025)

**AutocompleteCollector** - Find high-intent search queries (alphabet, questions, prepositions)

### Hybrid Research Orchestrator (NEW - Sessions 034-036)

**Website → Topics → Articles** pipeline with automatic fallback and 60% cost optimization.

**6-Stage Pipeline**:
1. **Website Analysis** - Extract keywords/tags/themes from customer site (FREE, Gemini API)
2. **Competitor Research** - Find competitors + market trends with automatic fallback (FREE → $0.02)
3. **Consolidation** - Merge and deduplicate keywords (FREE, CPU)
4. **Topic Discovery** - Generate 50+ candidates from 5 collectors (FREE, pattern-based)
5. **Topic Validation** - 5-metric scoring filters to top 20 (60% cost savings)
6. **Research Topics** - DeepResearcher → Reranker → Synthesizer ($0.01/topic)

**Key Features**:
- **Automatic Fallback**: Gemini rate limit → Tavily API (95%+ uptime)
- **Cost Tracking**: Per-stage free/paid API monitoring
- **Manual Mode**: Research custom topics via Python API or Streamlit UI
- **60% Cost Optimization**: Topic validation prevents wasted research

**Usage**:

*Full Pipeline (Automated Discovery)*:
```python
from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
import asyncio

orchestrator = HybridResearchOrchestrator(enable_tavily=True)

# Website → Topics → Articles
result = await orchestrator.run_pipeline(
    website_url="https://proptech-company.com",
    customer_info={"market": "Germany", "vertical": "PropTech"},
    max_topics_to_research=10
)

print(f"Discovered {len(result['topics'])} topics")
print(f"Researched {len(result['articles'])} articles")
print(f"Total cost: ${result['cost_tracker'].total_cost:.3f}")
```

*Manual Mode (Direct Topic Research)*:
```python
# Research single topic with custom config
article = await orchestrator.research_topic(
    topic="PropTech trends 2025",
    config={"market": "Germany", "vertical": "PropTech", "language": "de"}
)

print(f"Article: {article['title']}")
print(f"Sources: {len(article['sources'])}")
print(f"Cost: ${article['cost']:.3f}")
```

*Cost Tracking*:
```python
# Monitor free vs paid API usage
stats = result['cost_tracker'].get_summary()
print(f"Free API calls: {stats['total_free_calls']}")
print(f"Paid API calls: {stats['total_paid_calls']}")
print(f"Fallback rate: {stats['fallback_rate']:.1%}")
```

### 5-Stage ContentPipeline (Legacy)

Traditional pipeline: Competitor Research (FREE) → Keyword Research (FREE) → Deep Research ($0.02) → Content Optimization (FREE) → Scoring & Ranking (FREE). See ARCHITECTURE.md for details.

### Processing & Storage

**Deduplicator** - MinHash/LSH (<5% duplicates) | **Topic Clustering** - TF-IDF + HDBSCAN + LLM | **Entity Extractor** - LLM-based NER | **Notion Sync** - Rate-limited (2.5 req/sec)

## Cost Structure (Updated Session 029)

| Component | Method | Cost |
|-----------|--------|------|
| Feed Discovery | OPML + Gemini CLI + SerpAPI | FREE (3 req/day limit) |
| RSS/Reddit/Trends/Autocomplete | API + CLI | FREE |
| **5-Source Collection** | Tavily + SearXNG + Gemini + RSS + TheNewsAPI | **$0.002/topic** |
| **RRF Fusion + MinHash** | CPU-based | FREE |
| **3-Stage Reranker** | BM25 + Voyage Lite + Voyage Full + 6 metrics | **$0.005/topic** |
| **Passage Selection** | BM25 → Gemini Flash (primary) or LLM-only (fallback) | **$0.002-0.004/topic** |
| **Article Synthesis** | Gemini 2.5 Flash (1M context) | **$0.001/topic** |
| **Total per article** | | **$0.010/topic** (50% of budget) |

**Cost Breakdown Details**:
- Real article size: ~1,384 words/source, 22 paragraphs
- 25 reranked sources: ~45,000 tokens total
- **Passage selection**: BM25→LLM ($0.00189) or LLM-only ($0.00375) - 92-94% quality
- **Article synthesis**: Gemini Flash ($0.00133) - 75 passages, 2,000 word output
- **Embeddings rejected**: Voyage embeddings ($0.00356) - worse quality (87%), higher cost

**Budget**: $0.02/topic target, **$0.01 actual** (50% buffer remaining)

**Weekly Cost (50 topics)**: $0.50
**Monthly Cost (200 topics)**: $2.00

## Current Status (Session 036)

**Content Pipeline**: ✅ PRODUCTION ($0.01/topic, 96 tests passing)
**Hybrid Orchestrator**: ✅ PRODUCTION (95%+ uptime, $0.01/topic, 76 tests passing, automatic Gemini→Tavily fallback)

## Setup

### Prerequisites

- Python 3.11+
- [Gemini CLI](https://ai.google.dev/gemini-api/docs/) v0.11.3+ (for FREE web research)
- Notion account with integration created
- OpenRouter API key (for qwen models)
- Tavily API key (for web search with citations)
- Reddit API credentials (client_id, client_secret, user_agent)
- SerpAPI key (optional, for feed discovery Stage 2, 100 req/month free tier)

### Installation

1. **Clone and navigate**:
   ```bash
   cd /home/projects/content-creator
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-topic-research.txt
   ```

   **IMPORTANT**: `requirements-topic-research.txt` pins langchain ecosystem to <1.0 due to gpt-researcher 0.14.4 dependency.

3. **Configure environment** (`.env` or `/home/envs/*.env`):
   ```bash
   # OpenRouter (for qwen models)
   OPENROUTER_API_KEY=your_openrouter_key

   # Tavily API (for web search with citations)
   TAVILY_API_KEY=your_tavily_key

   # Notion
   NOTION_TOKEN=your_notion_token
   NOTION_PAGE_ID=your_page_id

   # Reddit API
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USER_AGENT=topic_research_agent/1.0

   # SerpAPI (optional)
   SERPAPI_KEY=your_serpapi_key

   # Settings
   CONTENT_LANGUAGE=de
   NOTION_RATE_LIMIT=2.5
   ```

4. **Install Gemini CLI** (FREE web research):
   ```bash
   npm install -g @google/generative-ai-cli
   gemini --version  # Verify installation
   ```

5. **Create Notion databases**:
   ```bash
   python setup_notion.py
   ```
   Creates 5 databases: Projects, Blog Posts, Social Posts, Research Data, Topics

6. **Launch Streamlit UI**:
   ```bash
   streamlit run streamlit_app.py
   ```
   Navigate to **Topic Research** page to test 5-stage pipeline

7. **Start background task queue** (optional):
   ```bash
   python -m src.tasks.huey_tasks
   ```

### Verify Setup

Test Notion connection:
```bash
python test_notion_connection.py
python check_databases.py
```

Test Gemini CLI:
```bash
gemini chat "What is PropTech?"
```

## Usage

### Quick Start

**Streamlit UI**: Configure market → Discover topics → Research selected topic → Review in Notion

**Python API**:
```python
from src.agents.content_pipeline import ContentPipeline

pipeline = ContentPipeline(enable_deep_research=True)
enhanced_topic = await pipeline.process_topic(topic, config)
```

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for detailed usage examples.

## Important Notes

**Stage 3 Deep Research**: Enabled by default. Primary: gpt-researcher ($0.02/topic), Fallback: Gemini CLI (FREE).

**API Keys**: Auto-loads from `/home/envs/` (openrouter.env, tavily.env) if not in environment.

## Testing

### Run All Tests

```bash
# Unit tests only (fast)
pytest tests/test_unit/ -v

# Integration tests (requires API keys)
pytest tests/test_integration/ -v

# All tests with coverage
pytest --cov=src --cov-report=html

# Specific component
pytest tests/test_unit/test_content_pipeline.py -v
```

### E2E Tests

```bash
pytest tests/test_integration/test_full_pipeline_e2e.py -v  # Costs $0.02-0.05
pytest tests/test_playwright_ui.py -v  # UI tests (fast)
```

## Troubleshooting

**langchain.docstore error**: `pip install 'langchain<1.0'` (gpt-researcher requires <1.0)

**OPENAI_API_KEY not found**: Ensure `/home/envs/openrouter.env` exists

**gemini: command not found**: `npm install -g @google/generative-ai-cli`

**Notion rate limits**: Lower `NOTION_RATE_LIMIT=2.0` in `.env`

See [TASKS.md](TASKS.md) for known issues and [docs/sessions/](docs/sessions/) for troubleshooting details.

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, patterns, integration architecture
- **[CHANGELOG.md](CHANGELOG.md)** - Recent sessions (last 5 sessions)
- **[TASKS.md](TASKS.md)** - Current priorities, backlog, known issues
- **[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)** - Comprehensive 1,400+ line plan
- **[docs/sessions/](docs/sessions/)** - Session narratives (one per session)
- **[docs/decisions/](docs/decisions/)** - Architecture Decision Records (ADRs)

## License

Private project - All rights reserved

## Support

For issues and questions:
- **Known Issues**: See [TASKS.md](TASKS.md)
- **Session History**: See [CHANGELOG.md](CHANGELOG.md)
- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Implementation Plan**: See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
