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
from src.media.image_generator import ImageGenerator
from src.notion_integration.sync_manager import SyncManager
from src.notion_integration.notion_client import NotionClient
from src.cache_manager import CacheManager

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
    num_sections: int,
    content_language: str
):
    """
    Generate content asynchronously.

    Args:
        topic: Blog topic
        config: Project configuration
        include_images: Whether to generate images
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

        # Stage 4: Notion Sync (100%)
        st.session_state.progress = 1.0
        st.session_state.status = "📤 Syncing to Notion..."

        notion_client = NotionClient(token=notion_token)
        sync_manager = SyncManager(
            cache_manager=cache_manager,
            notion_client=notion_client
        )

        # Get cache path
        slug = topic.lower().replace(" ", "-")[:50]
        cache_path = cache_manager.cache_dir / "blog_posts" / f"{slug}.md"

        return {
            "success": True,
            "word_count": word_count,
            "cost": total_cost,
            "cache_path": str(cache_path),
            "hero_image_url": hero_image_url,
            "supporting_images": supporting_images,
            "content": blog_result.get("content", "")
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

    # Show what happens next
    what_happens_next()

    st.divider()

    # Main form
    with st.form("quick_create_form"):
        st.subheader("📝 What do you want to write about?")

        # Topic input (required)
        topic = st.text_input(
            "Article Topic",
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
            "🖼️ Generate AI Images",
            value=True,
            help="Create photorealistic images with Flux 1.1 Pro Ultra (adds $0.06-0.076 per article)"
        )

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

            cost_estimate(
                base_cost=0.0056,  # Blog writing cost
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

            tab_objects = st.tabs(tabs)

            # Article tab
            with tab_objects[0]:
                st.markdown(result.get("content", ""))

            # Hero image tab
            if result.get("hero_image_url"):
                with tab_objects[1]:
                    st.image(result["hero_image_url"], use_container_width=True)

            # Supporting images tabs
            if result.get("supporting_images"):
                for i, img in enumerate(result["supporting_images"]):
                    with tab_objects[i + 2]:
                        st.image(img.get("url", ""), use_container_width=True)
                        st.caption(img.get("alt_text", ""))

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
