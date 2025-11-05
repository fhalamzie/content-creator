# Universal Topic Research Agent

Automated topic discovery and research system for SaaS companies. Finds trending topics in your industry before competitors do, validates SEO opportunities, and generates professional research reports with real citations.

**Business Value**: Stop guessing what to write about. Let AI discover high-demand topics with low competition, then deliver ready-to-use research reports.

## Features

- **Automated Topic Discovery** - Monitor 100+ RSS feeds, Reddit discussions, Google Trends, autocomplete suggestions
- **Intelligent Feed Discovery** - Find industry-relevant feeds automatically using OPML seeds + Gemini expansion + SerpAPI
- **5-Stage Content Pipeline** - Transform raw topics into prioritized, researched content opportunities
- **Professional Research Reports** - 5-6 page sourced reports at $0.02/topic using qwen + Tavily API
- **Dual Research Backend** - Primary: gpt-researcher (with citations), Fallback: Gemini CLI (faster, no citations)
- **Cost-Optimized** - Topic discovery FREE, research $0.02/topic (qwen-2.5-32b-instruct via OpenRouter)
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

### 5-Stage ContentPipeline

**Stage 1: Competitor Research** - Analyze 5 competitors, identify content gaps (FREE, Gemini CLI)

**Stage 2: Keyword Research** - Find primary/secondary/long-tail keywords with difficulty scores (FREE, Gemini CLI)

**Stage 3: Deep Research** - Generate 5-6 page reports with 10-20 citations ($0.02, qwen + Tavily API)

**Stage 4: Content Optimization** - Combine gaps, keywords, research into enriched topics (FREE)

**Stage 5: Scoring & Ranking** - Calculate demand/opportunity/fit/novelty scores (FREE, 1-10 priority)

### Processing & Storage

**Deduplicator** - MinHash/LSH similarity detection (<5% duplicate rate)

**Topic Clustering** - TF-IDF + HDBSCAN + LLM labeling (auto-determines K)

**Entity Extractor** - LLM-based NER for tagging topics

**Notion Topics Sync** - Rate-limited (2.5 req/sec) editorial review interface

## Cost Structure

| Component | Method | Cost |
|-----------|--------|------|
| Feed Discovery | OPML + Gemini CLI + SerpAPI | FREE (3 req/day limit) |
| RSS/Reddit/Trends/Autocomplete | API + CLI | FREE |
| **Stage 1-2** (Competitor/Keyword) | Gemini CLI | FREE |
| **Stage 3** (Deep Research) | qwen + Tavily API | **$0.02/topic** |
| **Stage 4-5** (Optimize/Score) | No API calls | FREE |
| **Total per researched topic** | | **$0.02** |

**Weekly Cost (50 topics)**: $1.00
**Monthly Cost (200 topics)**: $4.00

## Current Status

- ✅ **Week 1 & 2 Complete**: 17/17 components (100%), 192 tests, 94.67% coverage
- 🔄 **Session 027**: SQLite persistence fixed, document collection working
- **Next**: Full E2E pipeline testing and acceptance criteria validation

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
