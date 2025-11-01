# Content Creator System

AI-powered content generation system that creates SEO-optimized German blog posts and social media content, with Notion as the primary editing interface.

## Features

- **German Content Generation** - Native German blog posts (1500-2500 words) using Qwen3-Max
- **Multi-Platform Repurposing** - Automatic social media variants (LinkedIn, Facebook, TikTok, Instagram)
- **Notion Integration** - Edit generated content in Notion before publishing
- **Cost-Optimized** - ~$8/month (77% cheaper than premium models)
- **Rate-Limited Sync** - Safe Notion API usage (2.5 req/sec) with progress tracking
- **Background Publishing** - Automated scheduling and publishing to social platforms
- **Disk Caching** - Persistent storage in `cache/*.md` for recovery and version control

## Business Logic

### Content Pipeline

1. **Research Phase** - Gemini CLI performs web research with Google Search (FREE)
2. **Writing Phase** - Qwen3-Max generates German blog posts with citations
3. **Repurposing Phase** - Creates 4 social media variants in German
4. **Cache Phase** - Writes all content to disk (`cache/*.md`)
5. **Sync Phase** - Rate-limited upload to Notion (2.5 req/sec)
6. **Editorial Phase** - Human review and editing in Notion
7. **Publishing Phase** - Automated posting to LinkedIn, Facebook

### Cost Structure

| Component | Model | Cost |
|-----------|-------|------|
| Research | Gemini CLI | FREE |
| Blog Writing | Qwen3-Max | $0.64 |
| Fact-Checking | Qwen3-Max | $0.08 |
| Social Repurposing | Qwen3-Max | $0.26 |
| **Total per bundle** | | **$0.98** |
| **Monthly (8 bundles)** | | **~$8** |

### Content Quality

- **Language**: Native German with cultural context
- **SEO**: Keyword optimization, authoritative citations
- **Brand Voice**: Configurable (Professional, Casual, Technical, Friendly)
- **Fact-Checking**: Integrated verification during writing
- **Human Review**: Editorial control in Notion before publishing

## Setup

### Prerequisites

- Python 3.11+
- [Gemini CLI](https://ai.google.dev/gemini-api/docs/) v0.11.3+
- Notion account with integration created
- OpenRouter API key

### Installation

1. **Clone and navigate**:
   ```bash
   cd /home/content-creator
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment** (`.env`):
   ```bash
   # Notion
   NOTION_TOKEN=your_notion_token
   NOTION_PAGE_ID=your_page_id

   # OpenRouter
   OPENROUTER_API_KEY=your_openrouter_key
   MODEL_WRITING=qwen/qwq-32b-preview
   MODEL_REPURPOSING=qwen/qwq-32b-preview

   # Settings
   CONTENT_LANGUAGE=de
   NOTION_RATE_LIMIT=2.5
   ```

4. **Create Notion databases**:
   ```bash
   python setup_notion.py
   ```
   This creates 5 databases: Projects, Blog Posts, Social Posts, Research Data, Competitors

5. **Launch Streamlit UI**:
   ```bash
   streamlit run streamlit_app.py
   ```

6. **Start background publisher** (optional):
   ```bash
   python publisher_service.py
   ```

### Verify Setup

Test Notion connection:
```bash
python test_notion_connection.py
```

Check databases:
```bash
python check_databases.py
```

## Usage

### Via Streamlit UI

1. **Setup**: Complete project questionnaire (brand voice, target audience, keywords)
2. **Generate**: Enter German topic → Click "Generate" → Watch progress with ETA
3. **Edit**: Open generated content in Notion, make edits
4. **Publish**: Mark as "Ready" in Notion → Background publisher handles posting

### Progress Tracking

Real-time updates during generation:
```
Researching topic... (1/5)
Writing German blog post... (2/5)
Generating social posts... (3/5)
Writing to cache... (4/5)
Syncing to Notion... (5/5) ETA: 45s
Complete! [Open in Notion]
```

### Notion Workflow

**Status Progression**:
- `Draft` - Generated, ready for review
- `Ready` - Reviewed, approved for publishing
- `Scheduled` - Queued for future posting
- `Published` - Live on platforms

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details:
- System design patterns
- Data flow diagrams
- Integration architecture
- Rate limiting strategy

## Development

### Current Status

- ✅ **Phase 0**: Setup complete (environment, configuration, integrations)
- ✅ **Phase 1**: Foundation complete (cache manager, rate limiter, Notion client)
- ✅ **Phase 2**: Core agents complete (research, writing, sync manager, integration tests)
- ⏳ **Phase 3**: UI development (Streamlit interface with progress tracking)
- ⏳ **Phase 4**: Repurposing agent (social media content from blog posts)
- ⏳ **Phase 5**: Publishing automation (LinkedIn, Facebook APIs)
- ⏳ **Phase 6**: Media generation & analytics (DALL-E 3, performance tracking)

### Contributing

See [TASKS.md](TASKS.md) for current priorities and backlog.

### Testing

TDD approach with 80%+ coverage target:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_cache_manager.py
```

## Project Structure

```
content-creator/
├── src/                    # Core application
│   ├── agents/            # AI agents (research, writing, repurposing, publishing)
│   └── notion_integration/ # Notion client, rate limiter, sync manager
├── tests/                 # TDD tests (write tests first!)
├── config/                # Configuration files
│   ├── models.yaml       # OpenRouter model assignments
│   ├── notion_schemas.py # Database property definitions
│   └── prompts/          # German content prompts
├── cache/                 # Disk cache (gitignored)
│   ├── blog_posts/       # *.md files + metadata
│   ├── social_posts/     # Platform-specific content
│   ├── research/         # Research JSON files
│   └── sync_logs/        # Sync status tracking
├── docs/                  # Documentation
│   ├── sessions/         # Session narratives
│   └── decisions/        # Architecture Decision Records
├── publisher/             # Background publishing service
├── streamlit_app.py       # Main UI
├── setup_notion.py        # Database creation script
└── PLAN.md               # Comprehensive implementation plan
```

## Notion Database Schemas

### 1. Projects Database
Store brand configurations (SaaS URL, target audience, brand voice, keywords)

### 2. Blog Posts Database
Primary editorial interface (title, content, status, SEO metadata, scheduled date)

### 3. Social Posts Database
Platform-specific content (LinkedIn, Facebook, TikTok, Instagram variants)

### 4. Research Data Database
SEO research and keyword strategy (sources, competitor gaps, search volume)

### 5. Competitors Database
Competitor tracking (websites, social handles, content strategy analysis)

See [ARCHITECTURE.md](ARCHITECTURE.md) for complete schema definitions.

## Troubleshooting

### Notion Rate Limits

If you see rate limit errors:
- Reduce `NOTION_RATE_LIMIT` in `.env` (try 2.0)
- Check sync logs in `cache/sync_logs/sync_status.json`
- Re-run sync: cached content persists on disk

### German Content Quality

If content quality is poor:
- Verify `CONTENT_LANGUAGE=de` in `.env`
- Check German prompts in `config/prompts/blog_de.md`
- Consider switching to `anthropic/claude-sonnet-4` (higher cost)

### Gemini CLI Errors

If web research fails:
- Verify Gemini CLI: `gemini --version`
- Check installation: `npm list -g @google/generative-ai-cli`
- Alternative: Switch to Gemini MCP server

## License

Private project - All rights reserved

## Support

For issues and questions, see [PLAN.md](PLAN.md) sections:
- "⚠️ Critical Risks & Mitigations" (troubleshooting)
- "📞 Support & Resources" (documentation links)
