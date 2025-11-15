"""Dashboard page - Guided routing to help users find the right tool.

Design Principles (Session 051, Phase 3):
1. Clear routing cards (Quick Create, Automation, Research Lab, Library)
2. Explain What + When for each path
3. Show time/cost estimates before user clicks
4. Getting Started guide for new users
5. Minimal stats (don't overwhelm)
"""

import streamlit as st
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cache_manager import CacheManager
from ui.components.help import feature_explanation


CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "project_config.json"


def load_project_config():
    """Load project configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def calculate_stats(cache_manager: CacheManager):
    """Calculate system statistics.

    Note: Kept for backward compatibility with tests.
    Stats are now displayed minimally in an expander.
    """
    blog_posts = cache_manager.get_cached_blog_posts()
    social_posts = cache_manager.get_cached_social_posts()

    # Count posts
    total_blogs = len(blog_posts)
    total_social = len(social_posts)

    # Calculate total words
    total_words = sum(
        post.get("metadata", {}).get("word_count", 0)
        for post in blog_posts
    )

    # Estimate total cost (assuming $0.98 per blog bundle - old estimate for backward compatibility)
    total_cost = total_blogs * 0.98

    # Count by status
    status_counts = {}
    for post in blog_posts:
        status = post.get("metadata", {}).get("status", "Draft")
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "total_blogs": total_blogs,
        "total_social": total_social,
        "total_words": total_words,
        "total_cost": total_cost,
        "status_counts": status_counts
    }


def routing_card(
    icon: str,
    title: str,
    what: str,
    when: str,
    time: str,
    cost: str,
    button_label: str,
    page_name: str,
    type: str = "primary"
):
    """
    Render a routing card for navigation.

    Args:
        icon: Card icon/emoji
        title: Card title
        what: What this tool does (1-2 sentences)
        when: When to use it (1 sentence)
        time: Time estimate (e.g., "2-3 min")
        cost: Cost estimate (e.g., "$0.07-$0.10")
        button_label: CTA button text
        page_name: Target page in session_state
        type: Button type ("primary" or "secondary")
    """
    with st.container():
        # Card header
        st.markdown(f"### {icon} {title}")

        # What it does
        st.markdown(what)

        # When to use
        st.caption(f"**When to use**: {when}")

        # Time and cost estimates
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            # CTA button
            if st.button(button_label, key=f"route_{page_name}", use_container_width=True, type=type):
                st.session_state.current_page = page_name
                st.rerun()

        with col2:
            st.metric("⏱️ Time", time)

        with col3:
            st.metric("💰 Cost", cost)

        st.divider()


def render():
    """Render dashboard page."""
    # Title
    st.title("🤖 Content Creator")
    st.caption("AI-powered German content generation - Choose your workflow below")

    # Check configuration
    project_config = load_project_config()
    cache_manager = CacheManager()

    # Configuration status
    if not project_config:
        st.warning("⚠️ **First time here?** Let's get you set up!")
        st.markdown("You need to configure your Settings before creating content.")
        if st.button("⚙️ Go to Settings", use_container_width=True, type="primary"):
            st.session_state.current_page = "Settings"
            st.rerun()
        return

    # Getting Started Guide (for new users)
    blog_posts = cache_manager.get_cached_blog_posts()
    if len(blog_posts) == 0:
        with st.expander("🚀 Getting Started - New User Guide", expanded=True):
            st.markdown("""
            ### Welcome! Here's how to create your first article:

            **Step 1: Choose Your Path**
            - 👉 **Start here**: Use **Quick Create** below for your first article
            - Single topic, uses your Settings defaults, generates in ~2 minutes

            **Step 2: Review & Edit**
            - Content is saved to disk cache and synced to Notion
            - Open Notion to review, edit, and polish your article
            - All images and metadata are included

            **Step 3: Publish**
            - Use Notion to schedule and publish to your platforms
            - Track performance and iterate

            💡 **Tip**: Your first article takes ~2 min and costs $0.07-$0.10 (with images)
            """)

    st.divider()

    # Main Section: What do you want to do?
    st.subheader("📍 What do you want to do?")
    st.caption("Choose the right tool for your needs")

    st.divider()

    # Routing Card 1: Quick Create (RECOMMENDED for beginners)
    routing_card(
        icon="⚡",
        title="Quick Create",
        what="Generate a single high-quality German article on any topic. Perfect for beginners - just enter a topic and go. Uses your Settings defaults (no configuration needed).",
        when="You know exactly what topic you want to write about and need content fast.",
        time="2-3 min",
        cost="$0.07-$0.10",
        button_label="Create Single Article",
        page_name="Quick Create",
        type="primary"
    )

    # Routing Card 2: Automation (Pipeline)
    routing_card(
        icon="🎯",
        title="Automation",
        what="Fully automated research-to-content pipeline. Enter your website URL, and the AI discovers topics, researches them, and generates multiple articles. Best for bulk content creation.",
        when="You want to generate multiple articles automatically based on your business domain.",
        time="10-30 min",
        cost="$0.50-$2.00",
        button_label="Run Automation Pipeline",
        page_name="Pipeline Automation",
        type="secondary"
    )

    # Routing Card 3: Research Lab
    routing_card(
        icon="🔬",
        title="Research Lab",
        what="Deep topic research, competitor analysis, and keyword discovery. Explore topics before writing. Get 5-6 page research reports with citations and SEO insights.",
        when="You need to validate topics, analyze competitors, or discover content gaps before writing.",
        time="1-2 min",
        cost="$0.01-$0.02",
        button_label="Research Topics",
        page_name="Topic Research",
        type="secondary"
    )

    # Routing Card 4: Library (Content Browser)
    routing_card(
        icon="📚",
        title="Library",
        what="Browse, search, and manage all your generated content. View cached articles, sync to Notion, and track your content inventory.",
        when="You want to review past articles or manage your content library.",
        time="<1 min",
        cost="FREE",
        button_label="Browse Content",
        page_name="Content Browser",
        type="secondary"
    )

    # Optional: Minimal Stats (don't overwhelm)
    st.divider()

    with st.expander("📊 Quick Stats", expanded=False):
        stats = calculate_stats(cache_manager)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📄 Blog Posts", stats["total_blogs"])

        with col2:
            st.metric("📱 Social Posts", stats["total_social"])

        with col3:
            st.metric("📝 Total Words", f"{stats['total_words']:,}")

        with col4:
            st.metric("💰 Total Cost", f"${stats['total_cost']:.2f}")

        if stats["total_blogs"] > 0:
            st.caption(f"**Brand**: {project_config.get('brand_name', 'N/A')} • **Voice**: {project_config.get('brand_voice', 'N/A')}")

    st.divider()

    # Footer: Feature explanations
    st.caption("💡 **New to Content Creator?** Each tool has inline help and cost/time estimates. Start with Quick Create!")
