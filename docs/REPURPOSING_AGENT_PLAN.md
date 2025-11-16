# Repurposing Agent - Implementation Plan

**Status**: Planning (Session 059)
**Goal**: Generate platform-optimized social media content + visual assets from blog posts
**Focus**: Content generation first, platform sync later
**Timeline**: 4-6 weeks (TDD approach)

---

## Executive Summary

The Repurposing Agent transforms blog posts into platform-optimized social media content with custom visual assets. This plan focuses on **content generation** (text + images), deferring platform publishing APIs to Phase 5.

**Key Features**:
- Platform-specific text optimization (LinkedIn, Facebook, Instagram, TikTok)
- Open Graph image generation (1200x630, universal social sharing)
- Platform-specific image assets (1:1, 9:16, 4:5 aspect ratios)
- Hashtag generation with platform-specific limits
- Template-based visual design with brand consistency
- Cost optimization: Leverage existing Flux models + Pillow for templates

---

## Research Findings

### 1. Web Asset Generation Tools

**web-asset-generator** (MIT, Python):
- Emoji-based generation (60+ curated options)
- Pillow + Pilmoji for image rendering
- Validation: WCAG contrast, file sizes, dimensions
- Framework detection (Next.js, Astro)
- Natural language interface

**Takeaway**: Use Pillow for template-based generation (OG images, social cards), Replicate Flux for hero/photo-realistic images.

### 2. Open Graph Image Specifications (2025)

| Platform | Recommended Size | Aspect Ratio | Max File Size |
|----------|------------------|--------------|---------------|
| Universal (Facebook, LinkedIn) | 1200x630 | 1.91:1 | <1MB, <5MB absolute |
| Twitter/X Large Card | 1200x675 | 1.91:1 | <1MB |
| LinkedIn (tall option) | 1200x1200 | 1:1 | <1MB |
| Instagram Feed | 1080x1080 | 1:1 | <1MB |
| Instagram Story/Reels | 1080x1920 | 9:16 | <1MB |
| TikTok | 1080x1920 | 9:16 | <1MB |

**Format**: PNG (sharp graphics/text), JPEG (photos)
**Best Practices**:
- Text overlay <20% of image area (Facebook distribution)
- Center key elements (mobile/desktop compatibility)
- Validate with platform debuggers (Facebook Sharing Debugger, Twitter Card Validator)

### 3. Template-Based Generation (Vercel/Satori Approach)

Vercel's `@vercel/og` converts HTML/CSS → PNG via Satori library:
- Flexbox layouts (Grid not supported)
- Custom fonts (TTF/OTF preferred)
- Dynamic content injection (title, excerpt, logo, colors)
- Edge caching for performance

**Takeaway**: Use Pillow for Python-native approach, consider Satori/Puppeteer for complex layouts if needed.

### 4. Python Libraries for Social Media Assets

| Library | Use Case | Cost |
|---------|----------|------|
| **Pillow** | Template rendering, overlays, text | FREE |
| **Pilmoji** | Emoji rendering in images | FREE |
| **ReportLab** | PDF/vector graphics (advanced) | FREE |
| **Playwright** | HTML → Image (headless browser) | FREE |
| **Replicate Flux** | AI photo-realistic images | $0.003-$0.06 |
| **OpenAI DALL-E 3** | AI illustration/creative | $0.04-$0.08 |

**Chosen Stack**:
- **Pillow**: Template-based OG images, social cards (<$0.001/image)
- **Flux Dev**: Photo-realistic social images ($0.003/image, reuse existing)
- **Qwen3-Max**: Text generation for social posts ($0.0016/1K tokens)

---

## Architecture Overview

### Agent Structure

```
src/agents/repurposing_agent.py
├── RepurposingAgent (main class)
│   ├── generate_social_posts()      # Main entry point
│   ├── _generate_platform_content() # Text optimization per platform
│   ├── _generate_hashtags()         # Platform-specific hashtags
│   └── _calculate_cost()            # Track generation costs
│
src/media/social_image_generator.py
├── SocialImageGenerator (new class)
│   ├── generate_og_image()          # Open Graph 1200x630 (Pillow templates)
│   ├── generate_platform_image()    # Platform-specific sizes (Flux Dev)
│   ├── _create_template()           # Pillow template rendering
│   ├── _apply_brand_colors()        # Brand consistency
│   └── _add_text_overlay()          # Title/excerpt/CTA overlays
│
src/models/social_post.py
└── SocialPost (data model)
    ├── platform: str
    ├── content: str
    ├── image_url: str
    ├── og_image_url: str
    ├── hashtags: List[str]
    ├── character_count: int
    └── metadata: dict
```

### Data Flow

```
Blog Post (Markdown + Metadata)
    ↓
RepurposingAgent.generate_social_posts()
    ↓
[4 Platforms in Parallel]
    ↓
For Each Platform:
    1. _generate_platform_content() → Qwen3-Max ($0.0016/1K tokens)
    2. _generate_hashtags() → Platform rules + trending (FREE)
    3. SocialImageGenerator:
       a. generate_og_image() → Pillow template (<$0.001)
       b. generate_platform_image() → Flux Dev ($0.003)
    ↓
[4 SocialPost objects]
    ↓
Save to cache/social_posts/{slug}_{platform}.md
    ↓
Sync to Notion Social Posts DB (rate-limited 2.5 req/sec)
```

**Cost per Blog Post**:
- Text (4 platforms × 500 tokens × $0.0016/1K) = $0.003
- OG images (4 platforms × Pillow) = <$0.001
- Platform images (4 platforms × Flux Dev $0.003) = $0.012
- **Total**: ~$0.016/blog post (4 social posts)

---

## Phase 1: Platform Content Optimization (Week 1-2)

### Goal
Generate platform-optimized text content from blog posts.

### Components

**1.1. Platform Profiles**

```python
# src/agents/platform_profiles.py

PLATFORM_PROFILES = {
    "LinkedIn": {
        "max_chars": 3000,
        "optimal_chars": 1300,  # Sweet spot for engagement
        "tone": "Professional, thought-leadership",
        "hashtag_limit": 5,
        "emoji_usage": "Moderate (1-2 per post)",
        "cta_style": "Ask questions, invite discussion",
        "format": "Hook → Insights → CTA",
    },
    "Facebook": {
        "max_chars": 63206,
        "optimal_chars": 250,  # Most engagement at <250
        "tone": "Conversational, community-focused",
        "hashtag_limit": 3,
        "emoji_usage": "High (3-5 per post)",
        "cta_style": "Ask for shares, reactions",
        "format": "Story → Value → Emotion",
    },
    "Instagram": {
        "max_chars": 2200,
        "optimal_chars": 150,  # Caption + line break
        "tone": "Visual storytelling, authentic",
        "hashtag_limit": 30,
        "emoji_usage": "Very High (5-10)",
        "cta_style": "Link in bio, save for later",
        "format": "Hook → Visual description → Hashtags",
    },
    "TikTok": {
        "max_chars": 2200,
        "optimal_chars": 100,  # Video-first, text secondary
        "tone": "Casual, entertaining, trend-aware",
        "hashtag_limit": 5,
        "emoji_usage": "High (3-5)",
        "cta_style": "Watch till end, follow for more",
        "format": "Hook → Quick tips → Trending audio",
    },
}
```

**1.2. RepurposingAgent Core**

```python
# src/agents/repurposing_agent.py

class RepurposingAgent(BaseAgent):
    """
    Generates platform-optimized social media content from blog posts

    Features:
    - Platform-specific text optimization (tone, length, format)
    - Hashtag generation with trending analysis
    - Cost tracking per platform
    - Batch generation (4 platforms in parallel)
    """

    async def generate_social_posts(
        self,
        blog_post: dict,
        platforms: List[str] = ["LinkedIn", "Facebook", "Instagram", "TikTok"],
        brand_tone: List[str] = ["Professional"],
        generate_images: bool = True,
    ) -> List[SocialPost]:
        """
        Generate social posts for all platforms

        Args:
            blog_post: Blog post metadata (title, content, excerpt, keywords)
            platforms: List of platforms to generate for
            brand_tone: Brand voice settings
            generate_images: Whether to generate platform images

        Returns:
            List of SocialPost objects (one per platform)
        """
        pass

    async def _generate_platform_content(
        self,
        blog_post: dict,
        platform: str,
        brand_tone: List[str],
    ) -> str:
        """
        Generate platform-optimized content using Qwen3-Max

        Prompt structure:
        - Role: Social media expert for {platform}
        - Context: Blog post title, excerpt, keywords
        - Task: Transform into {platform} post
        - Constraints: Character limit, tone, format
        - Output: Optimized post text
        """
        pass

    async def _generate_hashtags(
        self,
        keywords: List[str],
        platform: str,
    ) -> List[str]:
        """
        Generate platform-specific hashtags

        Strategy:
        - Extract from keywords (capitalize, remove spaces)
        - Respect platform limits (LinkedIn 5, Instagram 30, etc.)
        - Mix: Brand (2) + Topic (3-5) + Trending (0-2)
        - German-specific: #PropTech vs #Immobilien
        """
        pass
```

### Testing Strategy

**Unit Tests** (20 tests):
- Platform profile loading
- Character limit enforcement
- Hashtag generation (limits, formatting)
- Cost calculation accuracy
- Error handling (missing fields, empty content)

**Integration Tests** (10 tests):
- Qwen3-Max API calls (mocked + 2 live)
- Batch generation (4 platforms)
- Brand tone propagation
- Cache file creation

**Acceptance Criteria**:
- ✅ All 4 platforms generate unique content
- ✅ Character limits respected (<1300 LinkedIn, <250 Facebook, etc.)
- ✅ Hashtags formatted correctly (#PropTech, not #prop tech)
- ✅ Cost tracking accurate (<$0.005/blog post for text)
- ✅ 30 tests passing, >85% coverage

---

## Phase 2: Open Graph Image Generation (Week 3)

### Goal
Generate universal Open Graph images (1200x630) using Pillow templates.

### Components

**2.1. Template System**

```python
# src/media/og_templates.py

class OGTemplate:
    """Base template for Open Graph images"""

    WIDTH = 1200
    HEIGHT = 630

    def __init__(self, brand_colors: dict):
        self.primary_color = brand_colors.get("primary", "#1E40AF")
        self.secondary_color = brand_colors.get("secondary", "#FFFFFF")
        self.background_color = brand_colors.get("background", "#F3F4F6")

    def render(
        self,
        title: str,
        excerpt: str,
        logo_path: Optional[str] = None,
    ) -> bytes:
        """
        Render OG image as PNG bytes

        Layout:
        ┌─────────────────────────────────────┐
        │  [Logo]                   [Brand]   │
        │                                     │
        │  Title (48px bold, 2 lines max)     │
        │                                     │
        │  Excerpt (24px, 3 lines max)        │
        │                                     │
        │  [Gradient footer with CTA]         │
        └─────────────────────────────────────┘
        """
        pass

# Template variants
TEMPLATES = {
    "minimal": MinimalTemplate,      # Clean, text-focused
    "gradient": GradientTemplate,    # Colorful gradient background
    "photo": PhotoTemplate,          # Hero image + text overlay
    "split": SplitTemplate,          # 50/50 image/text split
}
```

**2.2. SocialImageGenerator**

```python
# src/media/social_image_generator.py

class SocialImageGenerator:
    """
    Generates social media images using templates + AI

    Features:
    - OG images: Pillow templates (1200x630, <$0.001/image)
    - Platform images: Flux Dev (1:1, 9:16, 4:5, $0.003/image)
    - Brand consistency (colors, fonts, logo)
    - Text overlay optimization (readability, contrast)
    - WCAG contrast validation
    """

    COST_TEMPLATE = 0.0001  # Negligible (CPU-only)
    COST_FLUX_DEV = 0.003   # Reuse from ImageGenerator

    async def generate_og_image(
        self,
        blog_post: dict,
        template: str = "gradient",
        brand_config: dict = None,
    ) -> str:
        """
        Generate Open Graph image (1200x630)

        Returns:
            URL to generated image (saved to cache/social_images/)
        """
        pass

    async def generate_platform_image(
        self,
        blog_post: dict,
        platform: str,
        brand_tone: List[str],
    ) -> str:
        """
        Generate platform-specific image using Flux Dev

        Aspect ratios:
        - LinkedIn/Facebook: 1.91:1 (1200x630) → Use OG image
        - Instagram Feed: 1:1 (1080x1080)
        - Instagram Story/TikTok: 9:16 (1080x1920)
        """
        pass

    def _create_template(
        self,
        template_class: type,
        title: str,
        excerpt: str,
        brand_config: dict,
    ) -> Image:
        """Render Pillow template"""
        pass

    def _validate_contrast(
        self,
        text_color: str,
        bg_color: str,
    ) -> bool:
        """
        Validate WCAG AA contrast ratio (4.5:1 for normal text)
        """
        pass
```

### Testing Strategy

**Unit Tests** (15 tests):
- Template rendering (all 4 variants)
- Color validation (WCAG contrast)
- Text truncation (title 2 lines, excerpt 3 lines)
- Brand color application
- File size validation (<1MB)

**Integration Tests** (8 tests):
- Save to cache/social_images/
- Dimension validation (1200x630 exact)
- Logo overlay (if provided)
- Font rendering (custom TTF/OTF)

**Visual Tests** (Manual):
- Generate 10 sample OG images
- Test with Facebook Sharing Debugger
- Test with Twitter Card Validator
- Verify readability on mobile

**Acceptance Criteria**:
- ✅ 1200x630 PNG images generated
- ✅ File size <1MB (target <300KB)
- ✅ WCAG AA contrast compliance
- ✅ Title truncates gracefully (2 lines)
- ✅ Validates on Facebook/Twitter debuggers
- ✅ 23 tests passing, >90% coverage

---

## Phase 3: Platform-Specific Images (Week 4)

### Goal
Generate platform-optimized images (1:1, 9:16) using Flux Dev.

### Components

**3.1. Platform Image Specs**

```python
# src/media/platform_specs.py

PLATFORM_IMAGE_SPECS = {
    "LinkedIn": {
        "aspect_ratio": "1.91:1",
        "dimensions": (1200, 630),
        "use_og": True,  # Reuse OG image
        "format": "PNG",
    },
    "Facebook": {
        "aspect_ratio": "1.91:1",
        "dimensions": (1200, 630),
        "use_og": True,  # Reuse OG image
        "format": "PNG",
    },
    "Instagram": {
        "aspect_ratio": "1:1",
        "dimensions": (1080, 1080),
        "use_og": False,  # Generate new
        "format": "JPEG",
        "style": "Vibrant, lifestyle, mobile-optimized",
    },
    "TikTok": {
        "aspect_ratio": "9:16",
        "dimensions": (1080, 1920),
        "use_og": False,  # Generate new
        "format": "JPEG",
        "style": "Bold, attention-grabbing, vertical",
    },
}
```

**3.2. Flux Dev Integration**

```python
# Extension to SocialImageGenerator

async def generate_platform_image(
    self,
    blog_post: dict,
    platform: str,
    brand_tone: List[str],
) -> str:
    """
    Generate platform-specific image

    Strategy:
    - LinkedIn/Facebook: Return OG image URL (no new generation)
    - Instagram (1:1): Flux Dev with "square composition, centered subject"
    - TikTok (9:16): Flux Dev with "vertical composition, bold text overlay"

    Reuses existing ImageGenerator._generate_flux_image() with custom aspect ratios
    """

    spec = PLATFORM_IMAGE_SPECS[platform]

    if spec["use_og"]:
        # Reuse OG image for LinkedIn/Facebook
        return await self.generate_og_image(blog_post)

    # Generate new image with Flux Dev
    prompt = await self._create_platform_prompt(
        topic=blog_post["title"],
        platform=platform,
        brand_tone=brand_tone,
    )

    image_url = await self._generate_flux_dev_image(
        prompt=prompt,
        width=spec["dimensions"][0],
        height=spec["dimensions"][1],
        output_format=spec["format"],
    )

    return image_url

async def _create_platform_prompt(
    self,
    topic: str,
    platform: str,
    brand_tone: List[str],
) -> str:
    """
    Generate platform-optimized Flux prompt

    Platform-specific keywords:
    - Instagram: "Square composition, centered subject, lifestyle aesthetic"
    - TikTok: "Vertical portrait, bold dynamic framing, mobile-first"
    """
    pass
```

### Cost Optimization

**Smart Reuse Strategy**:
- LinkedIn + Facebook → Reuse OG image (2 platforms, 1 image = $0.0001)
- Instagram → Generate 1:1 Flux Dev ($0.003)
- TikTok → Generate 9:16 Flux Dev ($0.003)

**Total Cost per Blog Post**:
- OG image (Pillow): $0.0001
- Instagram (Flux Dev): $0.003
- TikTok (Flux Dev): $0.003
- **Total**: $0.006/blog post (vs $0.012 if generating all 4)

**Savings**: 50% cost reduction via OG image reuse

### Testing Strategy

**Unit Tests** (12 tests):
- Platform spec loading
- Aspect ratio calculation
- OG image reuse logic
- Flux Dev prompt generation
- File format validation

**Integration Tests** (10 tests):
- Generate 1:1 Instagram image (live Flux Dev API)
- Generate 9:16 TikTok image (live Flux Dev API)
- Validate dimensions (1080x1080, 1080x1920)
- Cost tracking ($0.003 per new image)

**Acceptance Criteria**:
- ✅ LinkedIn/Facebook reuse OG image (no new generation)
- ✅ Instagram generates 1:1 image (1080x1080)
- ✅ TikTok generates 9:16 image (1080x1920)
- ✅ Cost <$0.01/blog post (4 platforms)
- ✅ 22 tests passing, >88% coverage

---

## Phase 4: Integration & Notion Sync (Week 5)

### Goal
Integrate RepurposingAgent with content pipeline and Notion Social Posts DB.

### Components

**4.1. Cache Structure**

```
cache/social_posts/
├── proptech-versicherung_linkedin.md
├── proptech-versicherung_facebook.md
├── proptech-versicherung_instagram.md
└── proptech-versicherung_tiktok.md

cache/social_images/
├── proptech-versicherung_og.png         (1200x630, OG image)
├── proptech-versicherung_instagram.jpg  (1080x1080)
└── proptech-versicherung_tiktok.jpg     (1080x1920)

cache/social_posts/metadata.json
{
  "blog_post": "proptech-versicherung",
  "generated_at": "2025-11-16T14:30:00Z",
  "platforms": ["LinkedIn", "Facebook", "Instagram", "TikTok"],
  "total_cost": 0.019,
  "costs": {
    "text_generation": 0.003,
    "og_image": 0.0001,
    "instagram_image": 0.003,
    "tiktok_image": 0.003
  }
}
```

**4.2. Notion Sync Extension**

```python
# src/sync/social_posts_sync.py

class SocialPostsSync:
    """
    Syncs social posts from cache to Notion Social Posts DB

    Maps to SOCIAL_POSTS_SCHEMA:
    - Title: "{Blog Title} - {Platform}"
    - Platform: Select (LinkedIn, Facebook, Instagram, TikTok)
    - Blog Post: Relation to Blog Posts DB
    - Content: Rich text (post content)
    - Media URL: URL (platform image or OG image)
    - Hashtags: Multi-select
    - Status: Select (Draft by default)
    - Scheduled Date: Date (empty)
    """

    async def sync_social_posts(
        self,
        blog_post_id: str,
        social_posts: List[SocialPost],
        rate_limit: float = 2.5,
    ) -> dict:
        """
        Sync social posts to Notion with rate limiting

        Returns:
            {
                "synced": 4,
                "failed": 0,
                "duration": 2.1,
                "notion_ids": ["page_id_1", "page_id_2", ...]
            }
        """
        pass
```

**4.3. Pipeline Integration**

```python
# Extend src/agents/content_synthesizer.py

async def synthesize(
    self,
    research_data: dict,
    brand_tone: List[str],
    generate_images: bool = True,
    generate_social: bool = True,  # NEW
) -> dict:
    """
    Synthesize blog post + images + social posts

    Returns:
        {
            "article": "...",
            "hero_image_url": "...",
            "supporting_images": [...],
            "social_posts": [  # NEW
                {"platform": "LinkedIn", "content": "...", "image_url": "..."},
                ...
            ],
            "costs": {
                "research": 0.01,
                "blog": 0.006,
                "images": 0.076,
                "social": 0.019,  # NEW
                "total": 0.111
            }
        }
    """

    # ... existing blog + image generation ...

    if generate_social:
        repurposing_agent = RepurposingAgent()
        social_posts = await repurposing_agent.generate_social_posts(
            blog_post={
                "title": result["title"],
                "content": result["article"],
                "excerpt": result["excerpt"],
                "keywords": research_data["keywords"],
            },
            brand_tone=brand_tone,
            generate_images=generate_images,
        )
        result["social_posts"] = social_posts
        result["costs"]["social"] = sum(p.cost for p in social_posts)

    return result
```

### Testing Strategy

**E2E Tests** (6 tests):
- Full pipeline: Blog post → Social posts → Cache → Notion sync
- Test with images disabled (text only)
- Test cache recovery (reload from disk)
- Test Notion sync retry logic (rate limit simulation)

**Manual Testing Checklist**:
- [ ] Generate blog post with social posts enabled
- [ ] Verify 4 social post files in cache/social_posts/
- [ ] Verify 3 image files in cache/social_images/
- [ ] Sync to Notion Social Posts DB
- [ ] Check relation to Blog Posts DB (linked correctly)
- [ ] Verify hashtags appear as multi-select tags
- [ ] Verify cost tracking in metadata.json

**Acceptance Criteria**:
- ✅ 4 social posts generated per blog post
- ✅ Cache files created correctly
- ✅ Notion sync successful (4 pages created)
- ✅ Blog Post relation linked
- ✅ Total cost <$0.02/blog post (text + images + social)
- ✅ 6 E2E tests passing

---

## Phase 5: Streamlit UI Integration (Week 6)

### Goal
Add social post generation to Streamlit UI (Generate page, Quick Create, Library).

### Components

**5.1. Generate Page Enhancement**

```python
# src/ui/pages/generate.py

# Add checkbox after "Generate images"
col1, col2 = st.columns(2)
with col1:
    generate_images = st.checkbox(
        "Generate images (1 hero + 0-2 supporting)",
        value=market_config.enable_image_generation,
        help="Creates photorealistic images for blog post"
    )
with col2:
    generate_social = st.checkbox(
        "Generate social posts (4 platforms)",
        value=True,  # Enabled by default
        help="Creates LinkedIn, Facebook, Instagram, TikTok posts with images"
    )

# Show cost estimate
if generate_social:
    st.info(
        f"**Social Posts Cost**: ~$0.019 (4 platforms, text + 3 images)\n"
        f"- Text generation: $0.003\n"
        f"- OG image (LinkedIn/Facebook): $0.0001\n"
        f"- Instagram image (1:1): $0.003\n"
        f"- TikTok image (9:16): $0.003"
    )

# After generation, add 5th tab for social posts
if result.get("social_posts"):
    tabs = st.tabs(["Article", "Hero", "Support 1", "Support 2", "Sources", "Social"])

    with tabs[5]:
        st.subheader("Social Media Posts")

        for post in result["social_posts"]:
            with st.expander(f"{post['platform']} Post"):
                st.markdown(f"**Content** ({post['character_count']} chars):")
                st.text_area("", value=post['content'], height=150, disabled=True)

                st.markdown(f"**Hashtags**: {', '.join(post['hashtags'])}")

                if post.get('image_url'):
                    st.image(post['image_url'], caption=f"{post['platform']} Image")

                if st.button(f"Copy {post['platform']} Post", key=f"copy_{post['platform']}"):
                    st.code(post['content'], language=None)
```

**5.2. Library Page Enhancement**

```python
# src/ui/pages/library.py

# Add social posts column to blog posts table
if st.button("View Social Posts", key=f"social_{slug}"):
    st.session_state.selected_slug = slug
    st.session_state.view_mode = "social"

# Social posts viewer
if st.session_state.get("view_mode") == "social":
    slug = st.session_state.selected_slug
    social_files = glob(f"cache/social_posts/{slug}_*.md")

    if social_files:
        st.subheader(f"Social Posts for {slug}")

        for file in social_files:
            platform = file.split("_")[-1].replace(".md", "").capitalize()
            content = Path(file).read_text()

            with st.expander(f"{platform} Post"):
                st.markdown(content)

                # Show image if exists
                image_path = f"cache/social_images/{slug}_{platform.lower()}.jpg"
                if Path(image_path).exists():
                    st.image(image_path)
    else:
        st.warning("No social posts found. Generate them first.")
```

### Testing Strategy

**UI Tests** (Playwright, 8 tests):
- Generate blog post with social posts enabled
- Verify "Social" tab appears
- Click each platform expander (4 platforms)
- Verify images render in social tab
- View social posts in Library
- Copy social post content (clipboard test)

**Acceptance Criteria**:
- ✅ Social posts checkbox appears on Generate page
- ✅ Cost estimate shows before generation
- ✅ "Social" tab appears after generation
- ✅ All 4 platforms display correctly
- ✅ Images render in social tab
- ✅ Library shows social posts for each blog post
- ✅ 8 UI tests passing

---

## Cost Analysis

### Per Blog Post (4 Social Posts)

| Component | Provider | Cost | Notes |
|-----------|----------|------|-------|
| **Text Generation** | Qwen3-Max | $0.003 | 4 platforms × 500 tokens × $0.0016/1K |
| **OG Image** | Pillow | $0.0001 | Template rendering (CPU) |
| **Instagram Image** | Flux Dev | $0.003 | 1080x1080 JPEG |
| **TikTok Image** | Flux Dev | $0.003 | 1080x1920 JPEG |
| **Total Social** | - | **$0.009** | 4 posts + 3 images |

### Full Content Bundle (Blog + Social)

| Component | Cost | Notes |
|-----------|------|-------|
| Research | $0.01 | Gemini FREE or $0.02 Tavily |
| Blog Content | $0.006 | Qwen3-Max |
| Blog Images | $0.076 | Hero + 2 supporting (dynamic) |
| Social Posts | $0.009 | 4 platforms + images |
| **Total** | **$0.101** | Complete content bundle |

### Monthly Cost (10 Bundles)

- Current (blog only): $0.076 × 10 = $0.76
- With social: $0.101 × 10 = **$1.01/month**
- Increase: $0.25/month (+33%)

**ROI**: 4× content output (1 blog → 5 pieces) for 33% cost increase

---

## Success Metrics

### Technical KPIs

- ✅ 4 platforms generate unique content (no duplicates)
- ✅ Character limits respected (100% compliance)
- ✅ OG images validate on Facebook/Twitter debuggers
- ✅ Image file sizes <1MB (target <300KB for OG)
- ✅ Generation time <30s (4 platforms in parallel)
- ✅ Cost per blog post <$0.02 (target: $0.009)
- ✅ Test coverage >85% (unit + integration)

### User Experience KPIs

- ✅ Users can generate social posts with 1 click
- ✅ Preview all platforms before publishing
- ✅ Edit content in Notion before scheduling
- ✅ Copy-paste ready for manual posting
- ✅ Brand consistency across all platforms

---

## Phase 6: Platform Publishing (Future)

**Deferred to later**: LinkedIn API, Facebook Graph API, Instagram Basic Display API.

**Rationale**:
- Focus on content generation first (higher value)
- APIs require OAuth, webhooks, app review (2-4 weeks setup)
- Manual posting workflow validates content quality first

**When to implement**:
- After 50+ blog posts generated
- After user feedback on content quality
- When scheduling automation becomes bottleneck

---

## Dependencies & Prerequisites

### Required

- ✅ Existing ImageGenerator (Flux Ultra + Dev) - Already implemented
- ✅ Qwen3-Max integration (OpenRouter) - Already implemented
- ✅ Notion Social Posts schema - Already defined
- ✅ Cache system - Already implemented
- ✅ Cost tracking - Already implemented

### New Libraries

```bash
# requirements.txt additions
Pillow>=10.4.0          # Image template generation
pilmoji>=2.0.3          # Emoji rendering in images
colorthief>=0.2.1       # Brand color extraction (optional)
wcag-contrast-ratio>=0.9  # WCAG contrast validation
```

### Environment Variables

```bash
# /home/envs/repurposing.env (create new)
REPLICATE_API_TOKEN=...  # Already exists
OPENROUTER_API_KEY=...   # Already exists

# Brand configuration (from market config YAML)
BRAND_PRIMARY_COLOR=#1E40AF
BRAND_SECONDARY_COLOR=#FFFFFF
BRAND_LOGO_PATH=assets/logo.png  # Optional
```

---

## Implementation Timeline

### Week 1-2: Platform Content Optimization (Phase 1)
- **Days 1-2**: Platform profiles + RepurposingAgent skeleton
- **Days 3-4**: Qwen3-Max integration for text generation
- **Days 5-6**: Hashtag generation logic
- **Days 7-8**: Unit tests (20) + integration tests (10)
- **Deliverable**: Text generation working for 4 platforms

### Week 3: Open Graph Images (Phase 2)
- **Days 9-10**: Pillow template system (4 templates)
- **Days 11-12**: SocialImageGenerator OG image generation
- **Day 13**: WCAG contrast validation
- **Days 14-15**: Unit tests (15) + integration tests (8)
- **Deliverable**: 1200x630 OG images generated

### Week 4: Platform Images (Phase 3)
- **Days 16-17**: Platform-specific Flux Dev prompts
- **Day 18**: Instagram 1:1 image generation
- **Day 19**: TikTok 9:16 image generation
- **Days 20-21**: Cost optimization + tests (22)
- **Deliverable**: All 4 platforms have optimized images

### Week 5: Integration & Notion Sync (Phase 4)
- **Days 22-23**: Cache structure + SocialPostsSync
- **Days 24-25**: Pipeline integration (ContentSynthesizer)
- **Day 26**: E2E tests (6)
- **Days 27-28**: Manual testing + bug fixes
- **Deliverable**: Full pipeline working (blog → social → Notion)

### Week 6: Streamlit UI (Phase 5)
- **Days 29-30**: Generate page enhancements
- **Days 31-32**: Library page social viewer
- **Days 33-34**: Playwright UI tests (8)
- **Day 35**: Polish + documentation
- **Deliverable**: Production-ready UI

**Total**: 6 weeks (35 days) at 4-6 hours/day = **140-210 development hours**

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Flux Dev rate limits** | High | Batch generation with exponential backoff, queue system |
| **Pillow template complexity** | Medium | Start with 1 simple template, add variants iteratively |
| **Platform spec changes** | Medium | Version platform profiles, monitor official docs quarterly |
| **Character limit overruns** | Medium | Hard truncation + ellipsis, warn users in UI |
| **Hashtag quality** | Low | Manual review in Notion, A/B test hashtag strategies |
| **OG image not validating** | Medium | Automated testing with Facebook/Twitter debuggers in CI |

---

## Next Steps

1. **Review & Approve Plan** - User feedback on approach, priorities
2. **Create Session 060 Branch** - `git checkout -b session-060-repurposing-agent`
3. **Phase 1 Kickoff** - Start with platform profiles + RepurposingAgent skeleton
4. **TDD Workflow** - Write tests first, implement incrementally

---

**Document Version**: 1.0
**Created**: 2025-11-16 (Session 059)
**Status**: Planning - Awaiting Approval
**Estimated Cost**: $0.009/blog post (4 social posts)
**Estimated Timeline**: 6 weeks (140-210 hours)
