"""Content Browser page - View and manage cached content."""

import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cache_manager import CacheManager


def render():
    """Render content browser page."""
    st.title("📚 Content Browser")
    st.caption("View and manage your generated content")

    cache_manager = CacheManager()

    # Tabs for different content types
    tab1, tab2, tab3 = st.tabs(["📄 Blog Posts", "📱 Social Posts", "🔍 Research Data"])

    with tab1:
        render_blog_posts(cache_manager)

    with tab2:
        render_social_posts(cache_manager)

    with tab3:
        render_research_data(cache_manager)


def render_blog_posts(cache_manager: CacheManager):
    """Render blog posts list."""
    st.subheader("Blog Posts")

    cached_posts = cache_manager.get_cached_blog_posts()

    if not cached_posts:
        st.info("📭 No blog posts found. Generate your first post in the Generate page!")
        if st.button("Go to Generate"):
            st.session_state.current_page = "Generate"
            st.rerun()
        return

    # Search and filter
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("🔍 Search", placeholder="Search by title or slug...")
    with col2:
        sort_by = st.selectbox("Sort by", ["Newest", "Oldest", "Title"])

    # Filter posts
    filtered_posts = cached_posts
    if search_query:
        filtered_posts = [
            post for post in filtered_posts
            if search_query.lower() in post.get("slug", "").lower()
            or search_query.lower() in post.get("metadata", {}).get("title", "").lower()
        ]

    # Sort posts
    if sort_by == "Newest":
        filtered_posts = sorted(
            filtered_posts,
            key=lambda x: x.get("metadata", {}).get("created_at", ""),
            reverse=True
        )
    elif sort_by == "Oldest":
        filtered_posts = sorted(
            filtered_posts,
            key=lambda x: x.get("metadata", {}).get("created_at", "")
        )
    else:  # Title
        filtered_posts = sorted(
            filtered_posts,
            key=lambda x: x.get("metadata", {}).get("title", "")
        )

    st.caption(f"Found {len(filtered_posts)} blog post(s)")

    # Display posts
    for post in filtered_posts:
        slug = post.get("slug", "")
        metadata = post.get("metadata", {})
        content = post.get("content", "")

        # Extract title from content (first heading) or use topic
        title = metadata.get('title') or metadata.get('topic', slug)
        if content and content.startswith('#'):
            # Extract first heading
            first_line = content.split('\n')[0]
            title = first_line.lstrip('#').strip()

        with st.expander(f"📄 {title}", expanded=False):
            # Metadata
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Word Count", metadata.get("word_count", "N/A"))
            with col2:
                st.metric("Status", metadata.get("status", "Draft"))
            with col3:
                st.metric("Language", metadata.get("language", "de"))
            with col4:
                if metadata.get("notion_url"):
                    st.link_button("Open in Notion", metadata["notion_url"])

            # Content preview
            st.caption("**Excerpt:**")
            st.markdown(metadata.get("excerpt", "No excerpt available"))

            # Keywords
            if metadata.get("keywords"):
                st.caption("**Keywords:**")
                st.write(", ".join(metadata["keywords"]))

            # Actions
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("📖 View Full Content", key=f"view_{slug}"):
                    st.session_state.selected_post = slug
                    st.session_state.show_full_content = True
                    st.rerun()
            with col2:
                if st.button("📋 Copy Content", key=f"copy_{slug}"):
                    # Set session state to show copy modal
                    st.session_state.copy_content = slug
                    st.rerun()
            with col3:
                if st.button("🔄 Re-sync to Notion", key=f"sync_{slug}"):
                    try:
                        from src.notion_integration.sync_manager import SyncManager
                        from src.notion_integration.notion_client import NotionClient
                        import os

                        notion_token = os.getenv("NOTION_TOKEN")
                        if not notion_token:
                            st.error("NOTION_TOKEN not set in environment")
                        else:
                            notion_client = NotionClient(token=notion_token)
                            sync_manager = SyncManager(
                                cache_manager=cache_manager,
                                notion_client=notion_client
                            )

                            with st.spinner("Syncing to Notion..."):
                                result = sync_manager.sync_blog_post(slug=slug)

                            if result.get('success'):
                                st.success(f"✅ Synced! [Open in Notion]({result.get('url', '#')})")
                            else:
                                st.error(f"❌ Sync failed: {result.get('error', 'Unknown error')}")
                    except Exception as e:
                        st.error(f"Sync error: {e}")
            with col4:
                if st.button("🗑️ Delete", key=f"delete_{slug}", type="secondary"):
                    st.warning("Delete feature coming soon!")

    # Show full content modal
    if st.session_state.get("show_full_content") and st.session_state.get("selected_post"):
        show_full_content_modal(cache_manager, st.session_state.selected_post)

    # Show copy content modal
    if st.session_state.get("copy_content"):
        show_copy_modal(cache_manager, st.session_state.copy_content)


def show_copy_modal(cache_manager: CacheManager, slug: str):
    """Show content in copyable format."""
    try:
        post_data = cache_manager.read_blog_post(slug)
        content = post_data.get('content', '')
    except Exception as e:
        st.error(f"Failed to load content: {e}")
        return

    with st.container():
        st.divider()
        st.subheader("📋 Copy Content")

        if st.button("❌ Close", key="close_copy"):
            st.session_state.copy_content = None
            st.rerun()

        st.info("👇 Click the copy icon in the top-right corner of the code block to copy")

        # Display content in copyable code block
        st.code(content, language="markdown", line_numbers=False)

        st.divider()


def render_social_posts(cache_manager: CacheManager):
    """Render social posts list."""
    st.subheader("Social Media Posts")

    cached_social = cache_manager.get_cached_social_posts()

    if not cached_social:
        st.info("📭 No social posts found. Generate blog posts with social variants first!")
        return

    # Group by platform
    platforms = {}
    for key, post_data in cached_social.items():
        platform = post_data.get("platform", "unknown")
        if platform not in platforms:
            platforms[platform] = []
        platforms[platform].append((key, post_data))

    # Show by platform
    for platform, posts in platforms.items():
        st.subheader(f"📱 {platform.title()}")

        for key, post_data in posts:
            with st.expander(f"{post_data.get('blog_slug', 'Unknown')} - {platform}", expanded=False):
                st.markdown(post_data.get("content", "No content"))

                if post_data.get("hashtags"):
                    st.caption("**Hashtags:**")
                    st.write(" ".join(post_data["hashtags"]))

                if st.button("📋 Copy to Clipboard", key=f"copy_{key}"):
                    st.code(post_data.get("content", ""))


def render_research_data(cache_manager: CacheManager):
    """Render research data."""
    st.subheader("Research Data")

    # Get research files
    research_dir = cache_manager.cache_dir / "research"

    if not research_dir.exists() or not list(research_dir.glob("*_research.json")):
        st.info("📭 No research data found.")
        return

    import json

    research_files = sorted(research_dir.glob("*_research.json"), reverse=True)

    for research_file in research_files:
        with open(research_file, "r", encoding="utf-8") as f:
            research_data = json.load(f)

        slug = research_file.stem.replace("_research", "")

        with st.expander(f"🔍 {slug}", expanded=False):
            st.caption(f"**Topic:** {research_data.get('topic', 'N/A')}")

            # Sources
            sources = research_data.get("sources", [])
            if sources:
                st.caption(f"**Sources ({len(sources)}):**")
                for i, source in enumerate(sources[:5], 1):
                    st.markdown(f"{i}. {source.get('title', 'No title')} - [{source.get('url', '#')}]({source.get('url', '#')})")

            # Keywords
            keywords = research_data.get("keywords", [])
            if keywords:
                st.caption("**Keywords:**")
                st.write(", ".join(keywords))


def show_full_content_modal(cache_manager: CacheManager, slug: str):
    """Show full content in a modal."""
    try:
        post_data = cache_manager.read_blog_post(slug)
        content = post_data.get('content', '')
    except Exception as e:
        st.error(f"Failed to load content: {e}")
        return

    if content:
        with st.container():
            st.divider()
            st.subheader("📖 Full Content")

            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("❌ Close", key="close_full"):
                    st.session_state.show_full_content = False
                    st.rerun()
            with col2:
                if st.button("📋 Copy Format", key="copy_from_full"):
                    st.session_state.show_full_content = False
                    st.session_state.copy_content = slug
                    st.rerun()

            st.markdown(content)

            st.info("💡 Use 'Copy Format' button to see content in a copyable code block")
            st.divider()
