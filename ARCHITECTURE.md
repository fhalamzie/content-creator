# Architecture

## System Overview

AI-powered German content generation pipeline with Notion editorial interface. Emphasizes cost optimization (Qwen3-Max), data persistence (disk caching), and safe API usage (rate limiting).

**Core Principles**: TDD first, disk caching before Notion sync, 2.5 req/sec rate limiting, cost optimization (77% savings), fail-safe design.

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

[PLAN.md](PLAN.md) | [Notion API](https://developers.notion.com/) | [OpenRouter](https://openrouter.ai/docs) | [Qwen](https://huggingface.co/Qwen) | [Gemini CLI](https://ai.google.dev/gemini-api/docs/) | [Streamlit](https://docs.streamlit.io/)
