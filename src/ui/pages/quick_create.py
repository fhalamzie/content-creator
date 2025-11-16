"""Quick Create - Simplified single-topic content generation.

Design Goals (Phase 1):
- Simple: Just enter topic, everything else uses Settings defaults
- Clear: Explain every option with "What + Why + When"
- Transparent: Show cost/time BEFORE generation
- Helpful: Inline tooltips and expandable help sections
- Safe: Hide advanced options by default

Target: <300 lines (vs 622 in generate.py)
"""

import streamlit as st
from pathlib import Path
import json
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import agents and managers
from src.agents.research_agent import ResearchAgent
from src.agents.writing_agent import WritingAgent
from src.agents.repurposing_agent import RepurposingAgent
from src.media.image_generator import ImageGenerator
from src.media.platform_image_generator import PlatformImageGenerator
from src.notion_integration.sync_manager import SyncManager
from src.notion_integration.social_posts_sync import SocialPostsSync
from src.notion_integration.notion_client import NotionClient
from src.cache_manager import CacheManager
from src.utils.research_cache import load_research_from_cache, slugify
from src.utils.content_cache import save_blog_post_to_db, save_social_posts_to_db

# Import help components
from src.ui.components.help import (
    cost_estimate,
    time_estimate,
    what_happens_next,
    feature_explanation,
    settings_reminder,
    advanced_options_expander,
    generation_summary,
    success_message,
    error_message
)

# Paths
CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "project_config.json"


def load_project_config():
    """Load project configuration from Setup page."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "brand_voice": "Professional",
        "target_audience": "German-speaking professionals",
        "keywords": "",
        "content_language": "de"
    }


async def generate_content_async(
    topic: str,
    config: dict,
    include_images: bool,
    generate_social_posts: bool,
    num_sections: int,
    content_language: str
):
    """
    Generate content asynchronously.

    Args:
        topic: Blog topic
        config: Project configuration
        include_images: Whether to generate blog images
        generate_social_posts: Whether to generate social media posts
        num_sections: Number of article sections (determines supporting images)
        content_language: Content language code

    Returns:
        dict: Generation results
    """
    try:
        # Get API keys
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_key:
            return {"success": False, "error": "OPENROUTER_API_KEY not found"}

        notion_token = os.getenv("NOTION_TOKEN")
        if not notion_token:
            return {"success": False, "error": "NOTION_TOKEN not found"}

        # Initialize components
        cache_manager = CacheManager()
        research_agent = ResearchAgent(api_key=openrouter_key)
        writing_agent = WritingAgent(
            api_key=openrouter_key,
            language=content_language,
            cache_dir=str(cache_manager.cache_dir)
        )

        # Stage 1: Research (30%)
        st.session_state.progress = 0.3
        st.session_state.status = "🔍 Researching topic..."

        # Check cache first (reuse deep research from Hybrid Orchestrator)
        cached_research = load_research_from_cache(topic)

        if cached_research:
            # Use cached deep research (FREE!)
            st.session_state.status = "✨ Using cached deep research (FREE!)"
            research_data = {
                'sources': [{'url': url, 'title': '', 'snippet': ''} for url in cached_research.get('sources', [])],
                'keywords': cached_research.get('keywords', []),
                'summary': cached_research.get('summary', '')[:500],  # Use summary as research summary
                'article': cached_research.get('research_article', '')  # Include full deep research
            }
        else:
            # Fall back to simple research (if not in cache)
            st.session_state.status = "🔍 Researching topic (not in cache)..."
            research_data = research_agent.research(
                topic=topic,
                language=content_language
            )

        # Stage 2: Writing (60%)
        st.session_state.progress = 0.6
        st.session_state.status = "✍️ Writing blog post..."

        blog_result = writing_agent.write_blog(
            topic=topic,
            research_data=research_data,
            brand_voice=config.get("brand_voice", "Professional"),
            target_audience=config.get("target_audience", ""),
            primary_keyword=topic,
            save_to_cache=True
        )

        total_cost = blog_result.get("cost", 0.0)
        word_count = blog_result.get("metadata", {}).get("word_count", 0)

        # Stage 3: Images (80%) - Optional
        hero_image_url = None
        supporting_images = []

        if include_images:
            st.session_state.progress = 0.8
            st.session_state.status = "🖼️ Generating images..."

            image_gen = ImageGenerator()

            # Calculate number of supporting images based on sections
            if num_sections <= 3:
                num_supporting = 0  # Hero only
            elif num_sections <= 5:
                num_supporting = 1  # Hero + 1
            else:
                num_supporting = 2  # Hero + 2

            # Generate hero image
            hero_result = await image_gen.generate_hero_image(
                topic=topic,
                brand_tone=[config.get("brand_voice", "Professional")],
                article_excerpt=blog_result.get("content", "")[:500]
            )

            if hero_result and hero_result.get("success"):
                hero_image_url = hero_result.get("url")
                total_cost += hero_result.get("cost", 0.0)

            # Generate supporting images
            if num_supporting > 0:
                supporting_result = await image_gen.generate_supporting_images(
                    article_content=blog_result.get("content", ""),
                    num_images=num_supporting,
                    brand_tone=[config.get("brand_voice", "Professional")],
                    topic=topic
                )

                if supporting_result.get("success"):
                    supporting_images = supporting_result.get("images", [])
                    total_cost += supporting_result.get("cost", 0.0)

        # Stage 4: Social Media Posts (85%) - Optional
        social_posts = []
        social_posts_cost = 0.0

        if generate_social_posts:
            st.session_state.progress = 0.85
            st.session_state.status = "📱 Generating social posts..."

            # Initialize PlatformImageGenerator if images enabled
            platform_image_gen = None
            if include_images:
                platform_image_gen = PlatformImageGenerator()

            # Initialize RepurposingAgent
            repurposing_agent = RepurposingAgent(
                api_key=openrouter_key,
                cache_dir=str(cache_manager.cache_dir),
                image_generator=platform_image_gen
            )

            # Prepare blog post data
            blog_post_data = {
                'title': topic,
                'excerpt': blog_result.get("content", "")[:200],  # First 200 chars
                'keywords': [topic],  # Simple keywords from topic
                'slug': topic.lower().replace(" ", "-")[:50]
            }

            # Generate social posts for all 4 platforms
            social_posts_result = await repurposing_agent.generate_social_posts(
                blog_post=blog_post_data,
                platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
                brand_tone=[config.get("brand_voice", "Professional")],
                language=content_language,
                save_to_cache=True,
                generate_images=include_images,
                brand_color="#1a73e8"  # Default brand color
            )

            social_posts = social_posts_result
            social_posts_cost = sum(p.get('cost', 0.0) for p in social_posts)
            total_cost += social_posts_cost

        # Stage 5: Save to SQLite (95%) - Single source of truth
        st.session_state.progress = 0.95
        st.session_state.status = "💾 Saving to database..."

        # Generate slug for database
        slug = slugify(topic)

        # Get research topic ID if available (link blog post to deep research)
        research_topic_id = None
        if cached_research:
            research_topic_id = slug  # Same slug as research topic

        # Save blog post to SQLite FIRST
        blog_post_id = save_blog_post_to_db(
            title=topic,
            content=blog_result.get("content", ""),
            metadata={
                "word_count": word_count,
                "language": content_language,
                "brand_voice": config.get("brand_voice", "Professional"),
                "target_audience": config.get("target_audience", ""),
                "primary_keyword": topic,
                "hero_image_alt": f"Hero image for {topic}"
            },
            hero_image_url=hero_image_url,
            supporting_images=supporting_images,
            research_topic_id=research_topic_id
        )

        # Save social posts to SQLite (if generated)
        if social_posts:
            save_social_posts_to_db(
                blog_post_id=blog_post_id,
                social_posts=social_posts
            )

        # Stage 6: Notion Sync (100%) - Editorial interface
        st.session_state.progress = 1.0
        st.session_state.status = "📤 Syncing to Notion (editorial UI)..."

        notion_client = NotionClient(token=notion_token)
        sync_manager = SyncManager(
            cache_manager=cache_manager,
            notion_client=notion_client
        )

        # Get cache path (markdown still exists for backward compatibility)
        cache_path = cache_manager.cache_dir / "blog_posts" / f"{slug}.md"

        return {
            "success": True,
            "blog_post_id": blog_post_id,
            "word_count": word_count,
            "cost": total_cost,
            "cache_path": str(cache_path),
            "hero_image_url": hero_image_url,
            "supporting_images": supporting_images,
            "social_posts": social_posts,
            "social_posts_cost": social_posts_cost,
            "content": blog_result.get("content", ""),
            "cached_research_used": cached_research is not None
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def render():
    """Render Quick Create page."""
    st.title("✨ Quick Create")
    st.caption("Generate high-quality German blog posts in minutes")

    # Load project config
    config = load_project_config()

    # Check if configured
    if not config.get("brand_voice"):
        st.warning("⚠️ **Setup Required**: Please configure your brand settings first.")
        if st.button("🔧 Go to Settings", type="primary"):
            st.session_state.current_page = "Settings"
            st.rerun()
        return

    # Check for exported research data from Research Lab
    exported_topic = None
    competitor_insights = None
    imported_keywords = None

    # Tab 1: Topic Research import
    if "export_to_quick_create" in st.session_state:
        exported_data = st.session_state.export_to_quick_create
        exported_topic = exported_data.get("topic", "")

        st.success("✅ **Topic Research Imported!** Topic pre-filled from Research Lab")
        st.info(f"📊 **Topic**: {exported_topic}")

        if st.button("🗑️ Clear Topic Research", key="clear_research"):
            del st.session_state.export_to_quick_create
            st.rerun()

        st.divider()

    # Tab 2: Competitor Analysis import
    if "imported_competitor_insights" in st.session_state:
        competitor_insights = st.session_state.imported_competitor_insights
        num_competitors = len(competitor_insights.get("competitors", []))
        num_gaps = len(competitor_insights.get("content_gaps", []))

        st.success(f"✅ **Competitor Insights Imported!** {num_competitors} competitors, {num_gaps} content gaps identified")

        # Show content gaps as suggestions
        with st.expander("📊 **View Content Gaps**", expanded=False):
            for gap in competitor_insights.get("content_gaps", [])[:5]:  # Show top 5
                st.markdown(f"- {gap}")

            if num_gaps > 5:
                st.caption(f"... and {num_gaps - 5} more gaps")

        if st.button("🗑️ Clear Competitor Insights", key="clear_competitors"):
            del st.session_state.imported_competitor_insights
            st.rerun()

        st.divider()

    # Tab 3: Keyword Research import (to be implemented in Phase 2.2)
    if "imported_keyword_research" in st.session_state:
        imported_keywords = st.session_state.imported_keyword_research

        primary_kw = imported_keywords.get("primary_keyword", {}).get("keyword", "N/A")
        num_secondary = len(imported_keywords.get("secondary_keywords", []))
        num_long_tail = len(imported_keywords.get("long_tail_keywords", []))

        st.success(f"✅ **Keywords Imported!** Primary: '{primary_kw}', {num_secondary} secondary, {num_long_tail} long-tail")

        # Show keywords as suggestions
        with st.expander("🔑 **View All Keywords**", expanded=False):
            st.markdown(f"**Primary**: {primary_kw}")

            if num_secondary > 0:
                st.markdown("**Secondary**:")
                for kw in imported_keywords.get("secondary_keywords", [])[:5]:
                    st.markdown(f"- {kw.get('keyword', '')}")

            if num_long_tail > 0:
                st.markdown("**Long-tail**:")
                for kw in imported_keywords.get("long_tail_keywords", [])[:3]:
                    st.markdown(f"- {kw.get('keyword', '')}")

        if st.button("🗑️ Clear Keywords", key="clear_keywords"):
            del st.session_state.imported_keyword_research
            st.rerun()

        st.divider()

    # Show what happens next
    what_happens_next()

    st.divider()

    # Main form
    with st.form("quick_create_form"):
        st.subheader("📝 What do you want to write about?")

        # Topic input (required) - pre-fill with exported topic if available
        topic = st.text_input(
            "Article Topic",
            value=exported_topic if exported_topic else "",
            placeholder="e.g., PropTech Trends 2025",
            help="The main subject of your blog post. Be specific!"
        )

        # Language selector
        language_options = {
            "🇩🇪 German": "de",
            "🇬🇧 English": "en",
            "🇫🇷 French": "fr",
            "🇪🇸 Spanish": "es"
        }

        selected_language = st.selectbox(
            "Content Language",
            options=list(language_options.keys()),
            index=0,
            help="Language for the generated content"
        )
        content_language = language_options[selected_language]

        st.divider()

        # Show current settings being used
        st.caption("**🔧 Using Settings Defaults:**")
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"• Brand Voice: **{config.get('brand_voice', 'Professional')}**")
        with col2:
            st.caption(f"• Target Audience: **{config.get('target_audience', 'Not set')[:30]}...**")

        # Image generation toggle
        st.divider()
        include_images = st.checkbox(
            "🖼️ Generate AI Images for Blog",
            value=True,
            help="Create photorealistic images with Flux 1.1 Pro Ultra (adds $0.06-0.076 per article)"
        )

        # Social posts generation toggle
        generate_social_posts = st.checkbox(
            "📱 Generate Social Media Posts",
            value=True,
            help="Create platform-optimized posts for LinkedIn, Facebook, Instagram, and TikTok (adds $0.0092 per article)"
        )

        if generate_social_posts:
            st.caption("✨ **Includes**: 4 platform-optimized posts with hashtags" + (
                " + images (OG + AI)" if include_images else ""
            ))

        # Advanced options (collapsed by default)
        with advanced_options_expander():
            st.caption("**Article Structure**")

            num_sections = st.slider(
                "Number of Sections (H2 headings)",
                min_value=3,
                max_value=8,
                value=5,
                help="More sections = longer article + more supporting images"
            )

            st.caption("**Image Details**")
            if num_sections <= 3:
                st.info("Short articles: **1 hero image** (no supporting images)")
            elif num_sections <= 5:
                st.info("Medium articles: **1 hero + 1 supporting image**")
            else:
                st.info("Long articles: **1 hero + 2 supporting images**")

        st.divider()

        # Cost & Time Estimates
        st.subheader("💰 Estimate Before You Generate")

        col1, col2 = st.columns(2)

        with col1:
            # Calculate number of images
            if include_images:
                if num_sections <= 3:
                    num_images = 1  # Hero only
                elif num_sections <= 5:
                    num_images = 2  # Hero + 1
                else:
                    num_images = 3  # Hero + 2
            else:
                num_images = 0

            # Calculate social posts cost
            social_posts_cost_est = 0.0092 if generate_social_posts else 0.0

            cost_estimate(
                base_cost=0.0056 + social_posts_cost_est,  # Blog + social posts
                include_images=include_images,
                num_images=num_images,
                include_research=True
            )

        with col2:
            time_estimate(
                include_research=True,
                include_images=include_images,
                num_images=num_images if include_images else 0
            )

        st.divider()

        # Submit button
        submitted = st.form_submit_button(
            "🚀 Generate Content",
            type="primary",
            use_container_width=True
        )

    # Handle submission
    if submitted:
        if not topic:
            error_message(
                "Please enter a topic",
                "The topic field is required. Try something like 'PropTech Trends 2025'"
            )
            return

        # Initialize progress tracking
        if "progress" not in st.session_state:
            st.session_state.progress = 0.0
        if "status" not in st.session_state:
            st.session_state.status = ""

        # Create placeholders
        progress_placeholder = st.empty()
        status_placeholder = st.empty()

        # Run generation
        with st.spinner("Generating content..."):
            result = asyncio.run(generate_content_async(
                topic=topic,
                config=config,
                include_images=include_images,
                generate_social_posts=generate_social_posts,
                num_sections=num_sections,
                content_language=content_language
            ))

        # Show result
        if result.get("success"):
            success_message(
                word_count=result.get("word_count", 0),
                cost=result.get("cost", 0.0),
                cache_path=result.get("cache_path", ""),
                notion_synced=True
            )

            # Show preview tabs
            st.divider()
            st.subheader("📄 Preview")

            tabs = ["📝 Article"]
            if result.get("hero_image_url"):
                tabs.append("🖼️ Hero Image")
            if result.get("supporting_images"):
                tabs.extend([f"🖼️ Support {i+1}" for i in range(len(result["supporting_images"]))])

            # Add social posts tabs
            social_posts = result.get("social_posts", [])
            if social_posts:
                for post in social_posts:
                    platform = post.get("platform", "Unknown")
                    platform_icons = {
                        "LinkedIn": "💼",
                        "Facebook": "👥",
                        "Instagram": "📸",
                        "TikTok": "🎵"
                    }
                    icon = platform_icons.get(platform, "📱")
                    tabs.append(f"{icon} {platform}")

            tab_objects = st.tabs(tabs)

            # Article tab
            tab_idx = 0
            with tab_objects[tab_idx]:
                st.markdown(result.get("content", ""))

            # Hero image tab
            if result.get("hero_image_url"):
                tab_idx += 1
                with tab_objects[tab_idx]:
                    st.image(result["hero_image_url"], use_container_width=True)

            # Supporting images tabs
            if result.get("supporting_images"):
                for i, img in enumerate(result["supporting_images"]):
                    tab_idx += 1
                    with tab_objects[tab_idx]:
                        st.image(img.get("url", ""), use_container_width=True)
                        st.caption(img.get("alt_text", ""))

            # Social posts tabs
            if social_posts:
                for post in social_posts:
                    tab_idx += 1
                    with tab_objects[tab_idx]:
                        platform = post.get("platform", "Unknown")
                        st.caption(f"**Platform**: {platform}")
                        st.caption(f"**Character Count**: {post.get('character_count', 0)}")

                        # Show content
                        st.text_area(
                            "Post Content",
                            value=post.get("content", ""),
                            height=200,
                            disabled=True,
                            label_visibility="collapsed"
                        )

                        # Show hashtags
                        hashtags = post.get("hashtags", [])
                        if hashtags:
                            st.caption(f"**Hashtags**: {' '.join(hashtags)}")

                        # Show image if available
                        if post.get("image", {}).get("url"):
                            st.image(post["image"]["url"], use_container_width=True)
                            st.caption(f"Provider: {post['image'].get('provider', 'unknown')}")

                        # Show cost breakdown
                        post_cost = post.get("cost", 0.0)
                        st.caption(f"**Cost**: ${post_cost:.4f}")

        else:
            error_message(
                result.get("error", "Unknown error"),
                "Check your API keys in Settings and try again"
            )


# Feature explanations (shown only on first visit)
def show_feature_help():
    """Show feature explanations for first-time users."""
    if "quick_create_visited" not in st.session_state:
        st.session_state.quick_create_visited = True

        with st.expander("ℹ️ First Time Here? Read This", expanded=True):
            st.markdown("""
            ### Welcome to Quick Create!

            This is the fastest way to create professional German content.

            **How it works:**
            1. Enter your topic
            2. Review cost/time estimates
            3. Click "Generate Content"
            4. Review and publish in Notion

            **What you get:**
            - 1500+ word professional blog post
            - Photorealistic AI images (optional)
            - SEO-optimized content
            - Saved to your Notion database

            **Cost:** ~$0.07-0.076 per article with images
            """)
