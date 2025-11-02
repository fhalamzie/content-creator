# Streamlit UI Guide

Complete guide for using the Content Creator Streamlit interface.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file with your API keys:

```bash
# Notion
NOTION_TOKEN=secret_xxxx...
NOTION_PAGE_ID=your_page_id

# OpenRouter
OPENROUTER_API_KEY=sk-or-v1-xxxx...

# Settings
CONTENT_LANGUAGE=de
NOTION_RATE_LIMIT=2.5
MODEL_WRITING=qwen/qwq-32b-preview
MODEL_REPURPOSING=qwen/qwq-32b-preview
```

### 3. Create Notion Databases

```bash
python setup_notion.py
```

This creates 5 databases: Projects, Blog Posts, Social Posts, Research Data, Competitors

### 4. Launch Streamlit

```bash
streamlit run streamlit_app.py
```

The app will open at `http://localhost:8501`

---

## UI Pages

### 📊 Dashboard (Landing Page)

**Purpose**: Overview of your content system

**Features**:
- Key metrics (blog posts, social posts, words, cost)
- Recent activity feed
- Configuration summary
- Status breakdown
- Quick actions
- Monthly progress tracking
- Tips and recommendations

**First-Time Setup**:
- If no configuration, shows "Go to Setup" button
- Configure project before generating content

---

### ⚙️ Setup

**Purpose**: Configure your brand and content strategy

**Sections**:

1. **Brand Information**
   - Brand name (required)
   - Website URL (optional)

2. **Brand Voice**
   - Professional / Casual / Technical / Friendly
   - Affects writing style and tone

3. **Target Audience**
   - Detailed description (required)
   - Demographics and interests
   - Used to tailor content

4. **Content Strategy**
   - Primary keywords (comma-separated)
   - Content goals
   - Posts per week (1-10)
   - Social posts per blog (1-4)

**Configuration Storage**:
- Saved to `cache/project_config.json`
- Persists across sessions
- Can be edited anytime

**Cost Estimate**:
- Shows monthly cost based on posts/week
- Formula: `posts_per_week * 4 * $0.98`

---

### ✨ Generate

**Purpose**: Create German blog posts with AI

**Workflow**:

1. **Enter Topic**
   - German or English topic
   - Example: "Die Vorteile von Cloud-Computing für kleine Unternehmen"

2. **Advanced Options** (optional)
   - Target word count (1000-3000)
   - Generate social posts (checkbox)

3. **Click "Generate Content"**
   - Shows real-time progress bar
   - 4 stages: Research → Writing → Cache → Sync
   - ETA displayed during sync

4. **View Results**
   - Stats: word count, sources, cost, time
   - Link to open in Notion
   - Content preview
   - Next steps guide

**Progress Stages**:
1. **Research (20%)** - Gemini CLI web research
2. **Writing (60%)** - Qwen3-Max generates German blog post
3. **Cache (80%)** - Saves to `cache/*.md`
4. **Sync (100%)** - Uploads to Notion (rate-limited, ETA shown)

**Recent Generations**:
- Shows last 5 generated posts
- Click to view in Content Browser

**Error Handling**:
- Research failures: Retries with fallback
- Writing failures: Shows error message
- Sync failures: Content still saved in cache

---

### 📚 Content Browser

**Purpose**: View and manage cached content

**Tabs**:

#### 📄 Blog Posts
- Search by title or slug
- Sort by: Newest / Oldest / Title
- Shows metadata (word count, status, language)
- Preview excerpt and keywords
- Actions:
  - View full content
  - Re-sync to Notion (coming soon)
  - Delete (coming soon)
- Link to Notion (if synced)

#### 📱 Social Posts
- Grouped by platform (LinkedIn, Facebook, TikTok, Instagram)
- Shows content and hashtags
- Copy to clipboard

#### 🔍 Research Data
- View research JSON files
- Shows topic, sources, keywords
- Links to original sources

**Features**:
- Real-time search filtering
- Expandable content cards
- Full content modal view
- Direct Notion links

---

### 🔧 Settings

**Purpose**: Configure API keys, rate limits, and models

**Tabs**:

#### 🔑 API Keys
- **Notion Integration Token**: From https://notion.so/my-integrations
- **Notion Page ID**: Parent page for databases
- **OpenRouter API Key**: From https://openrouter.ai/keys

**Features**:
- Masked key display
- Test connections (Notion, OpenRouter)
- Updates `.env` file
- Requires app restart after changes

#### ⚡ Rate Limits
- **Notion API Rate Limit**: 1.0 - 3.0 req/s
- Default: 2.5 (safety margin on 3.0 official limit)
- Shows ETA calculation example

#### 🤖 Models
- **Writing Model**: Blog post generation
  - qwen/qwq-32b-preview (default, $0.98/bundle)
  - anthropic/claude-sonnet-4 ($3.50/bundle)
  - anthropic/claude-opus-4 ($15.00/bundle)
  - openai/gpt-4 ($12.00/bundle)

- **Repurposing Model**: Social media content
  - Same options as writing model

- **Content Language**: de (German) or en (English)

- **Cost Estimate**: Shows per-bundle cost breakdown

#### 📊 Advanced
- **Cache Directory**: Location for cached files
- **Log Level**: DEBUG / INFO / WARNING / ERROR
- **Feature Flags**:
  - Enable Web Research
  - Enable Fact Checking
  - Enable Auto-Sync to Notion

- **Danger Zone**:
  - Clear cache (coming soon)
  - Reset settings (coming soon)

---

## Typical Workflow

### First-Time Setup

1. **Launch App**: `streamlit run streamlit_app.py`
2. **Configure Settings** (🔧 Settings tab)
   - Add Notion token and page ID
   - Add OpenRouter API key
   - Test connections
3. **Setup Project** (⚙️ Setup tab)
   - Brand name and voice
   - Target audience
   - Keywords and goals
   - Posts per week
4. **Create Databases**: `python setup_notion.py` (if not done)

### Content Generation

1. **Go to Generate Page** (✨ Generate)
2. **Enter Topic** in German or English
3. **Click "Generate Content"**
4. **Wait for Progress** (Research → Writing → Cache → Sync)
5. **View Results**
   - Check stats and preview
   - Click "Open in Notion"
6. **Edit in Notion**
   - Review and edit content
   - Add images, formatting
   - Mark as "Ready" when approved

### Content Management

1. **Browse Content** (📚 Content Browser)
2. **View Blog Posts**
   - Search and filter
   - View full content
   - Click to open in Notion
3. **View Social Posts**
   - Platform-specific variants
   - Copy to clipboard for posting

### Dashboard Monitoring

1. **Go to Dashboard** (📊 Dashboard)
2. **Check Metrics**
   - Total posts and words
   - Total cost spent
   - Monthly progress
3. **View Recent Activity**
   - Last 5 posts
   - Quick access to Notion
4. **Follow Tips**
   - System recommendations
   - Action items

---

## File Structure

```
content-creator/
├── streamlit_app.py          # Main entry point
├── src/
│   └── ui/
│       └── pages/
│           ├── dashboard.py           # Landing page
│           ├── setup.py               # Project config
│           ├── generate.py            # Content generation
│           ├── content_browser.py     # Content viewer
│           └── settings.py            # System settings
├── cache/
│   ├── project_config.json   # Project configuration
│   ├── blog_posts/           # Generated blog posts
│   ├── social_posts/         # Social media content
│   ├── research/             # Research data
│   └── sync_logs/            # Sync status
└── .env                      # API keys (gitignored)
```

---

## Troubleshooting

### App Won't Start

```bash
# Check Python version (3.11+)
python --version

# Reinstall dependencies
pip install -r requirements.txt

# Check for syntax errors
python -m py_compile streamlit_app.py
```

### Notion Connection Failed

1. Verify token in Settings → API Keys
2. Test connection with "Test Notion Connection"
3. Check token has workspace access
4. Verify page ID is correct (32 characters)

### OpenRouter Connection Failed

1. Verify API key starts with `sk-or-v1-`
2. Check account has credits: https://openrouter.ai/account
3. Test with minimal request

### Generation Errors

**Research Failed**:
- Check Gemini CLI: `gemini --version`
- Verify network connection
- Try alternative research source

**Writing Failed**:
- Check OpenRouter API key
- Verify model availability
- Check account credits

**Sync Failed**:
- Content still saved in cache (`cache/blog_posts/`)
- Try manual re-sync from Content Browser
- Check rate limit settings (reduce from 2.5 to 2.0)

### No Content Showing

1. Check cache directory exists: `ls cache/blog_posts/`
2. Verify metadata files: `ls cache/blog_posts/*.json`
3. Generate test post in Generate page

---

## Performance

### Generation Time
- **Research**: ~1 minute (Gemini CLI)
- **Writing**: ~3 minutes (Qwen3-Max)
- **Cache**: <1 second
- **Sync**: ~4 seconds (10 Notion API calls at 2.5 req/s)
- **Total**: ~5 minutes per blog post

### Cost
- **Per Blog Post**: $0.98
- **Per Social Bundle** (4 posts): $0.26
- **Total per Bundle**: $0.98
- **Monthly** (8 bundles): ~$8

### Limits
- **Notion API**: 2.5 req/s (configurable)
- **OpenRouter**: Model-specific limits
- **Cache Storage**: Unlimited (disk space)

---

## Advanced Usage

### Custom Prompts

Edit prompts in `config/prompts/`:
- `blog_de.md` - German blog post template
- `social_de.md` - Social media variants

### Batch Generation

Generate multiple posts:
```python
# In Python console
from src.agents.writing_agent import WritingAgent

topics = ["Topic 1", "Topic 2", "Topic 3"]
for topic in topics:
    # Generate content (API in generate.py)
```

### Export Content

```bash
# Export all blog posts to single file
cat cache/blog_posts/*.md > all_posts.md

# Export metadata
cat cache/blog_posts/*/metadata.json
```

---

## Next Steps

After Phase 3 (Current):
- **Phase 4**: Repurposing agent (4 social platforms)
- **Phase 5**: Publishing automation (LinkedIn, Facebook APIs)
- **Phase 6**: Media generation (DALL-E 3), analytics

---

## Support

- **Issues**: See [TASKS.md](TASKS.md) for known issues
- **Documentation**: See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
- **Planning**: See [PLAN.md](PLAN.md) for comprehensive implementation plan
