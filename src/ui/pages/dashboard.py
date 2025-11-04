"""Dashboard page - Overview, stats, and recent activity."""

import streamlit as st
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cache_manager import CacheManager


CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "project_config.json"


def load_project_config():
    """Load project configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def calculate_stats(cache_manager: CacheManager):
    """Calculate system statistics."""
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

    # Estimate total cost (assuming $0.98 per blog bundle)
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


def render():
    """Render dashboard page."""
    st.title("📊 Dashboard")
    st.caption("Overview of your content generation system")

    # Check configuration
    project_config = load_project_config()
    cache_manager = CacheManager()

    # Configuration status
    if not project_config:
        st.warning("⚠️ Project not configured yet")
        if st.button("⚙️ Go to Setup", use_container_width=True):
            st.session_state.current_page = "Setup"
            st.rerun()
        return

    # Welcome message
    st.success(f"👋 Welcome to **{project_config.get('brand_name', 'Content Creator')}**!")

    st.divider()

    # Key metrics
    st.subheader("📈 Key Metrics")

    stats = calculate_stats(cache_manager)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "📄 Blog Posts",
            stats["total_blogs"],
            help="Total number of generated blog posts"
        )

    with col2:
        st.metric(
            "📱 Social Posts",
            stats["total_social"],
            help="Total number of social media posts"
        )

    with col3:
        st.metric(
            "📝 Total Words",
            f"{stats['total_words']:,}",
            help="Total words across all blog posts"
        )

    with col4:
        st.metric(
            "💰 Total Cost",
            f"${stats['total_cost']:.2f}",
            help="Estimated total generation cost"
        )

    st.divider()

    # Two-column layout
    col1, col2 = st.columns([2, 1])

    with col1:
        # Recent activity
        st.subheader("🕐 Recent Activity")

        blog_posts = cache_manager.get_cached_blog_posts()

        if blog_posts:
            # Sort by created_at (newest first)
            sorted_posts = sorted(
                blog_posts,
                key=lambda x: x.get("metadata", {}).get("created_at", ""),
                reverse=True
            )

            # Show last 5 posts
            for post in sorted_posts[:5]:
                slug = post.get("slug", "")
                metadata = post.get("metadata", {})
                with st.container():
                    col_icon, col_content, col_action = st.columns([1, 10, 2])

                    with col_icon:
                        st.write("📄")

                    with col_content:
                        st.markdown(f"**{metadata.get('title', slug)}**")
                        st.caption(
                            f"{metadata.get('word_count', 'N/A')} words • "
                            f"{metadata.get('created_at', 'N/A')}"
                        )

                    with col_action:
                        if metadata.get("notion_url"):
                            st.link_button("→", metadata["notion_url"], key=f"open_{slug}")

                st.divider()

            # View all button
            if len(blog_posts) > 5:
                if st.button("📚 View All Posts", use_container_width=True):
                    st.session_state.current_page = "Content Browser"
                    st.rerun()
        else:
            st.info("📭 No activity yet. Start by generating your first blog post!")
            if st.button("✨ Generate Content", use_container_width=True):
                st.session_state.current_page = "Generate"
                st.rerun()

    with col2:
        # Project configuration summary
        st.subheader("⚙️ Configuration")

        with st.container():
            st.markdown(f"**Brand:** {project_config.get('brand_name', 'N/A')}")
            st.markdown(f"**Voice:** {project_config.get('brand_voice', 'N/A')}")
            st.markdown(f"**Posts/Week:** {project_config.get('posts_per_week', 'N/A')}")

            if st.button("Edit Config", use_container_width=True):
                st.session_state.current_page = "Setup"
                st.rerun()

        st.divider()

        # Status breakdown
        st.subheader("📊 Status Breakdown")

        if stats["status_counts"]:
            for status, count in stats["status_counts"].items():
                st.metric(status, count)
        else:
            st.caption("No posts yet")

        st.divider()

        # Quick actions
        st.subheader("⚡ Quick Actions")

        if st.button("✨ Generate Content", use_container_width=True, type="primary"):
            st.session_state.current_page = "Generate"
            st.rerun()

        if st.button("📚 Browse Content", use_container_width=True):
            st.session_state.current_page = "Content Browser"
            st.rerun()

        if st.button("🔧 Settings", use_container_width=True):
            st.session_state.current_page = "Settings"
            st.rerun()

    st.divider()

    # System info
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("💡 System Info")
        st.caption("**Research:** Gemini CLI (FREE)")
        st.caption("**Writing:** Qwen3-Max ($0.64)")
        st.caption("**Language:** German 🇩🇪")

    with col2:
        st.subheader("📊 Performance")
        avg_words = stats["total_words"] / stats["total_blogs"] if stats["total_blogs"] > 0 else 0
        st.caption(f"**Avg Words/Post:** {avg_words:.0f}")
        st.caption("**Cost/Post:** $0.98")
        st.caption("**Sync Rate:** 2.5 req/s")

    with col3:
        st.subheader("🎯 Monthly Target")
        posts_per_week = project_config.get("posts_per_week", 2)
        monthly_posts = posts_per_week * 4
        monthly_cost = monthly_posts * 0.98
        st.caption(f"**Target Posts:** {monthly_posts}")
        st.caption(f"**Target Cost:** ${monthly_cost:.2f}")
        progress = (stats["total_blogs"] / monthly_posts * 100) if monthly_posts > 0 else 0
        st.progress(min(progress / 100, 1.0))

    # Tips and recommendations
    st.divider()
    st.subheader("💡 Tips & Recommendations")

    tips = []

    if not blog_posts:
        tips.append("📝 Start by generating your first blog post in the Generate page")
    elif len(blog_posts) < 5:
        tips.append("🚀 Keep generating content to build your content library")

    if project_config.get("posts_per_week", 0) > 3:
        tips.append("💰 Consider reducing posts/week to stay within budget")

    if not project_config.get("keywords"):
        tips.append("🎯 Add keywords in Setup to improve SEO targeting")

    if not any(post.get("metadata", {}).get("notion_url") for post in blog_posts):
        tips.append("☁️ Sync your content to Notion for editorial review")

    if tips:
        for tip in tips:
            st.info(tip)
    else:
        st.success("✨ Everything looks good! Keep creating amazing content!")
