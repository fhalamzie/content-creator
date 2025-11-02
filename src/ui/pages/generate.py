"""Generate page - Content generation with progress tracking and ETA."""

import streamlit as st
from pathlib import Path
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import agents and managers
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.research_agent import ResearchAgent
from src.agents.writing_agent import WritingAgent
from src.notion_integration.sync_manager import SyncManager
from src.cache_manager import CacheManager


CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "project_config.json"


def load_project_config():
    """Load project configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def generate_content(topic: str, project_config: dict, progress_placeholder, status_placeholder):
    """Generate content with progress tracking.

    Args:
        topic: Blog post topic
        project_config: Project configuration
        progress_placeholder: Streamlit placeholder for progress bar
        status_placeholder: Streamlit placeholder for status messages

    Returns:
        dict: Generation results with blog post data
    """
    try:
        # Get API keys from environment
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return {"success": False, "error": "OPENROUTER_API_KEY not found in environment"}

        notion_token = os.getenv("NOTION_TOKEN")
        if not notion_token:
            return {"success": False, "error": "NOTION_TOKEN not found in environment"}

        # Initialize components
        cache_manager = CacheManager()
        research_agent = ResearchAgent(api_key=api_key)
        writing_agent = WritingAgent(api_key=api_key)

        # Initialize Notion client and sync manager
        from src.notion_integration.notion_client import NotionClient

        notion_client = NotionClient(token=notion_token)
        sync_manager = SyncManager(cache_manager=cache_manager, notion_client=notion_client)

        # Stage 1: Research (20%)
        status_placeholder.info("🔍 Researching topic...")
        progress_placeholder.progress(0.2)

        research_data = research_agent.research(topic=topic, language="de")

        # Stage 2: Writing (60%)
        status_placeholder.info("✍️ Writing German blog post...")
        progress_placeholder.progress(0.6)

        # Parse keywords from project config
        keywords_str = project_config.get("keywords", "")
        keywords_list = [k.strip() for k in keywords_str.split(",") if k.strip()] if keywords_str else []
        primary_keyword = keywords_list[0] if keywords_list else None
        secondary_keywords = keywords_list[1:] if len(keywords_list) > 1 else None

        # Generate blog post
        blog_result = writing_agent.write_blog(
            topic=topic,
            research_data=research_data,
            brand_voice=project_config.get("brand_voice", "Professional"),
            target_audience=project_config.get("target_audience", "Business professionals"),
            primary_keyword=primary_keyword,
            secondary_keywords=secondary_keywords,
            save_to_cache=False  # We'll handle caching separately
        )

        # Stage 3: Cache (80%)
        status_placeholder.info("💾 Writing to cache...")
        progress_placeholder.progress(0.8)

        # Prepare metadata for cache
        metadata = {
            **blog_result.get("metadata", {}),
            "seo": blog_result.get("seo", {}),
            "cost": blog_result.get("cost", 0),
            "sources": research_data.get("sources", [])
        }

        # Save to cache (returns slug)
        slug = cache_manager.save_blog_post(
            content=blog_result.get("content", ""),
            metadata=metadata,
            topic=topic
        )

        # Stage 4: Sync to Notion (100%)
        status_placeholder.info("☁️ Syncing to Notion...")

        def progress_callback(current, total, eta_seconds):
            """Progress callback for sync."""
            progress = 0.8 + (0.2 * current / total)
            progress_placeholder.progress(progress)
            status_placeholder.info(
                f"☁️ Syncing to Notion... ({current}/{total}) ETA: {eta_seconds:.0f}s"
            )

        # Try to sync to Notion
        sync_result = {'success': False, 'error': 'Not attempted'}
        try:
            sync_result = sync_manager.sync_blog_post(
                slug=slug,
                progress_callback=progress_callback
            )
        except Exception as e:
            # Sync failed but content is cached
            sync_result = {'success': False, 'error': str(e)}
            status_placeholder.warning(
                f"⚠️ Sync failed: {e}, but content is saved in cache"
            )

        # Complete
        progress_placeholder.progress(1.0)
        status_placeholder.success("✅ Content generated successfully!")

        return {
            "success": True,
            "blog_data": {
                "slug": slug,
                "content": blog_result.get("content", ""),
                "metadata": metadata
            },
            "notion_url": sync_result.get("url") if sync_result.get("success") else None,
            "stats": {
                "word_count": metadata.get("word_count", 0),
                "research_sources": len(research_data.get("sources", [])),
                "cost": blog_result.get("cost", 0.98)
            }
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def render():
    """Render generate page."""
    st.title("✨ Generate Content")
    st.caption("Create SEO-optimized German blog posts with AI")

    # Check if project is configured
    project_config = load_project_config()

    if not project_config:
        st.warning("⚠️ Please configure your project in the Setup page first")
        if st.button("Go to Setup"):
            st.session_state.current_page = "Setup"
            st.rerun()
        return

    # Show current configuration
    with st.expander("📋 Current Configuration", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Brand Voice", project_config.get("brand_voice", "N/A"))
        with col2:
            st.metric("Target Audience", "Configured" if project_config.get("target_audience") else "Not set")
        with col3:
            st.metric("Keywords", len(project_config.get("keywords", "").split(",")) if project_config.get("keywords") else 0)

    st.divider()

    # Topic input
    st.subheader("📝 Enter Topic")

    topic = st.text_input(
        "Blog Post Topic (in German or English)",
        placeholder="e.g., Die Vorteile von Cloud-Computing für kleine Unternehmen",
        help="Enter the topic you want to write about. The AI will generate a German blog post."
    )

    # Additional options
    with st.expander("🎛️ Advanced Options", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            word_count_target = st.slider(
                "Target Word Count",
                min_value=1000,
                max_value=3000,
                value=1800,
                step=100,
                help="Target word count for the blog post"
            )
        with col2:
            include_social = st.checkbox(
                "Generate Social Posts",
                value=True,
                help="Generate social media variants (LinkedIn, Facebook, etc.)"
            )

    # Generate button
    if st.button("🚀 Generate Content", type="primary", use_container_width=True, disabled=not topic):
        if not topic:
            st.error("❌ Please enter a topic")
            return

        # Create placeholders for progress
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        result_placeholder = st.empty()

        # Start generation
        start_time = time.time()

        with st.spinner("Generating content..."):
            result = generate_content(
                topic=topic,
                project_config=project_config,
                progress_placeholder=progress_placeholder,
                status_placeholder=status_placeholder
            )

        elapsed_time = time.time() - start_time

        # Show results
        if result.get("success"):
            status_placeholder.empty()
            progress_placeholder.empty()

            with result_placeholder.container():
                st.success("✅ Content generated successfully!")

                # Show stats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Word Count", result["stats"]["word_count"])
                with col2:
                    st.metric("Sources", result["stats"]["research_sources"])
                with col3:
                    st.metric("Cost", f"${result['stats']['cost']:.2f}")
                with col4:
                    st.metric("Time", f"{elapsed_time:.1f}s")

                # Notion link
                if result.get("notion_url"):
                    st.link_button(
                        "📝 Open in Notion",
                        result["notion_url"],
                        type="primary",
                        use_container_width=True
                    )

                # Show preview
                with st.expander("👀 Preview", expanded=True):
                    blog_data = result.get("blog_data", {})
                    st.subheader(blog_data.get("metadata", {}).get("title", "Untitled"))
                    st.caption(blog_data.get("metadata", {}).get("excerpt", ""))
                    st.markdown(blog_data.get("content", "")[:500] + "...")

                # Next steps
                st.info("💡 **Next Steps:**\n1. Open in Notion to review and edit\n2. Mark as 'Ready' when approved\n3. Content will be published automatically")

        else:
            status_placeholder.error(f"❌ Generation failed: {result.get('error', 'Unknown error')}")
            progress_placeholder.empty()

    # Show recent generations
    st.divider()
    st.subheader("📚 Recent Generations")

    # Load cached posts
    cache_manager = CacheManager()
    cached_posts = cache_manager.get_cached_blog_posts()

    if cached_posts:
        # Show last 5 posts
        for post in cached_posts[:5]:
            slug = post.get('slug', '')
            metadata = post.get('metadata', {})
            with st.expander(f"📄 {metadata.get('title', slug)}", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.caption(f"**Slug:** {slug}")
                with col2:
                    st.caption(f"**Words:** {metadata.get('word_count', 'N/A')}")
                with col3:
                    st.caption(f"**Created:** {metadata.get('created_at', 'N/A')}")

                if st.button(f"View in Browser", key=f"view_{slug}"):
                    st.session_state.current_page = "Content Browser"
                    st.session_state.selected_post = slug
                    st.rerun()
    else:
        st.info("No content generated yet. Create your first blog post above!")
