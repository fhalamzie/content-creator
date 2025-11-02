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
from src.agents.fact_checker_agent import FactCheckerAgent
from src.agents.competitor_research_agent import CompetitorResearchAgent
from src.agents.keyword_research_agent import KeywordResearchAgent
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
        competitor_agent = CompetitorResearchAgent(api_key=api_key, cache_dir=str(cache_manager.cache_dir))
        keyword_agent = KeywordResearchAgent(api_key=api_key, cache_dir=str(cache_manager.cache_dir))
        research_agent = ResearchAgent(api_key=api_key)
        writing_agent = WritingAgent(api_key=api_key)

        # Initialize Notion client and sync manager
        from src.notion_integration.notion_client import NotionClient

        notion_client = NotionClient(token=notion_token)
        sync_manager = SyncManager(cache_manager=cache_manager, notion_client=notion_client)

        # Stage 0: Competitor Research (10%)
        status_placeholder.info("🔎 Analyzing competitors...")
        progress_placeholder.progress(0.1)

        competitor_data = competitor_agent.research_competitors(
            topic=topic,
            language="de",
            max_competitors=5,
            include_content_analysis=True,
            save_to_cache=True
        )

        # Stage 1: Keyword Research (20%)
        status_placeholder.info("🎯 Researching keywords...")
        progress_placeholder.progress(0.2)

        keyword_data = keyword_agent.research_keywords(
            topic=topic,
            language="de",
            target_audience=project_config.get("target_audience", "Business professionals"),
            keyword_count=10,
            save_to_cache=True
        )

        # Stage 2: Topic Research (30%)
        status_placeholder.info("🔍 Researching topic...")
        progress_placeholder.progress(0.3)

        research_data = research_agent.research(topic=topic, language="de")

        # Stage 3: Writing (50%)
        status_placeholder.info("✍️ Writing German blog post...")
        progress_placeholder.progress(0.5)

        # Use keywords from keyword research (primary source)
        primary_keyword = keyword_data['primary_keyword']['keyword']
        secondary_keywords = [kw['keyword'] for kw in keyword_data['secondary_keywords'][:5]]

        # Merge research data with competitor and keyword insights
        enhanced_research_data = {
            **research_data,
            'competitor_insights': {
                'content_gaps': competitor_data['content_gaps'],
                'trending_topics': competitor_data['trending_topics']
            },
            'seo_insights': {
                'primary_keyword': keyword_data['primary_keyword'],
                'long_tail_keywords': [kw['keyword'] for kw in keyword_data['long_tail_keywords'][:3]],
                'related_questions': keyword_data['related_questions'][:3]
            }
        }

        # Generate blog post
        blog_result = writing_agent.write_blog(
            topic=topic,
            research_data=enhanced_research_data,
            brand_voice=project_config.get("brand_voice", "Professional"),
            target_audience=project_config.get("target_audience", "Business professionals"),
            primary_keyword=primary_keyword,
            secondary_keywords=secondary_keywords,
            save_to_cache=False  # We'll handle caching separately
        )

        # Stage 2.5: Fact-Checking (70%) - NEW!
        fact_check_enabled = os.getenv("ENABLE_FACT_CHECK", "true").lower() == "true"
        thoroughness = os.getenv("FACT_CHECK_THOROUGHNESS", "medium")

        if fact_check_enabled:
            status_placeholder.info("🔍 Fact-checking content...")
            progress_placeholder.progress(0.7)

            fact_checker = FactCheckerAgent(api_key=api_key)
            fact_check_result = fact_checker.verify_content(
                content=blog_result.get("content", ""),
                thoroughness=thoroughness
            )

            # Show fact-check results
            if not fact_check_result.get('valid', True):
                st.warning(f"⚠️ Fact-check found {len(fact_check_result.get('hallucinations', []))} issues")

                with st.expander("📊 View Fact-Check Report", expanded=True):
                    st.code(fact_check_result.get('report', 'No report available'))

                    # Show metrics
                    col1, col2, col3 = st.columns(3)
                    layers = fact_check_result.get('layers', {})

                    if 'consistency' in layers:
                        consistency_score = layers['consistency'].get('score', 0) * 10
                        col1.metric("Consistency", f"{consistency_score:.1f}/10")

                    if 'urls' in layers:
                        urls_real = layers['urls'].get('urls_real', 0)
                        urls_total = layers['urls'].get('urls_checked', 0)
                        col2.metric("Valid URLs", f"{urls_real}/{urls_total}")

                    if 'quality' in layers:
                        quality_score = layers['quality'].get('quality_score', 0)
                        col3.metric("Quality", f"{quality_score:.1f}/10")

                # Option to use corrected content
                use_corrected = st.checkbox("Use AI-corrected content (removes fake URLs)", value=False)
                if use_corrected and 'corrected_content' in fact_check_result:
                    blog_result['content'] = fact_check_result['corrected_content']
                    st.success("✅ Using corrected content")

                # Require confirmation to proceed
                proceed = st.button("Proceed Despite Issues")
                if not proceed and not use_corrected:
                    st.stop()  # Don't continue generation
            else:
                st.success("✅ Fact-check passed - No issues detected!")

        # Stage 4: Cache (80%)
        status_placeholder.info("💾 Writing to cache...")
        progress_placeholder.progress(0.8)

        # Prepare metadata for cache (includes all research data)
        metadata = {
            **blog_result.get("metadata", {}),
            "seo": blog_result.get("seo", {}),
            "cost": blog_result.get("cost", 0),
            "sources": research_data.get("sources", []),
            "competitor_analysis": {
                "competitors": len(competitor_data['competitors']),
                "content_gaps": competitor_data['content_gaps'],
                "trending_topics": competitor_data['trending_topics'],
                "recommendation": competitor_data['recommendation']
            },
            "keyword_research": {
                "primary_keyword": keyword_data['primary_keyword'],
                "secondary_keywords": [kw['keyword'] for kw in keyword_data['secondary_keywords'][:5]],
                "long_tail_keywords": [kw['keyword'] for kw in keyword_data['long_tail_keywords'][:3]],
                "related_questions": keyword_data['related_questions'][:3]
            }
        }

        # Save to cache (returns slug)
        slug = cache_manager.save_blog_post(
            content=blog_result.get("content", ""),
            metadata=metadata,
            topic=topic
        )

        # Stage 5: Sync to Notion (100%)
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
                "competitors_analyzed": len(competitor_data['competitors']),
                "keywords_found": len(keyword_data['secondary_keywords']) + 1,  # +1 for primary
                "primary_keyword": keyword_data['primary_keyword']['keyword'],
                "content_gaps": len(competitor_data['content_gaps']),
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

                # Show stats - Row 1
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Word Count", result["stats"]["word_count"])
                with col2:
                    st.metric("Keywords", result["stats"]["keywords_found"])
                with col3:
                    st.metric("Cost", f"${result['stats']['cost']:.2f}")
                with col4:
                    st.metric("Time", f"{elapsed_time:.1f}s")

                # Show stats - Row 2
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Competitors", result["stats"]["competitors_analyzed"])
                with col2:
                    st.metric("Sources", result["stats"]["research_sources"])
                with col3:
                    st.metric("Content Gaps", result["stats"]["content_gaps"])
                with col4:
                    st.caption(f"🎯 **Primary**: {result['stats']['primary_keyword']}")

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
