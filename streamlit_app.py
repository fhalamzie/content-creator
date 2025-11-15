"""Content Creator System - Main Streamlit Application

AI-powered German content generation with Notion editorial interface.
Cost-optimized ($8/month) using Qwen3-Max and Gemini CLI.
"""

import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import pages
from ui.pages import dashboard, generate, content_browser, settings, topic_research, pipeline_automation, quick_create, logo_showcase
from src.utils.logger import setup_logging


def init_session_state():
    """Initialize session state variables."""
    if "project_config" not in st.session_state:
        st.session_state.project_config = {}

    if "generation_history" not in st.session_state:
        st.session_state.generation_history = []

    if "current_page" not in st.session_state:
        st.session_state.current_page = "Dashboard"


def render_sidebar():
    """Render navigation sidebar."""
    with st.sidebar:
        st.title("🤖 Content Creator")
        st.caption("AI-powered German content generation")

        st.divider()

        # Navigation menu
        pages = {
            "📊 Dashboard": "Dashboard",
            "⚡ Quick Create": "Quick Create",
            "✨ Generate": "Generate",
            "🎯 Pipeline Automation": "Pipeline Automation",
            "🔬 Topic Research": "Topic Research",
            "📚 Content Browser": "Content Browser",
            "🏠 Logo Showcase": "Logo Showcase",
            "🔧 Settings": "Settings"
        }

        for label, page_name in pages.items():
            if st.button(
                label,
                key=f"nav_{page_name}",
                use_container_width=True,
                type="primary" if st.session_state.current_page == page_name else "secondary"
            ):
                st.session_state.current_page = page_name
                st.rerun()

        st.divider()

        # Footer info
        st.caption("💰 Cost: ~$8/month")
        st.caption("🇩🇪 Language: German")
        st.caption("📝 Model: Qwen3-Max")


def main():
    """Main application entry point."""
    # Page config
    st.set_page_config(
        page_title="Content Creator System",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Setup logging
    setup_logging(log_level="DEBUG")

    # Initialize session state
    init_session_state()

    # Render sidebar navigation
    render_sidebar()

    # Route to current page
    page = st.session_state.current_page

    if page == "Dashboard":
        dashboard.render()
    elif page == "Quick Create":
        quick_create.render()
    elif page == "Generate":
        generate.render()
    elif page == "Pipeline Automation":
        pipeline_automation.render()
    elif page == "Topic Research":
        topic_research.render()
    elif page == "Content Browser":
        content_browser.render()
    elif page == "Logo Showcase":
        logo_showcase.render()
    elif page == "Settings":
        settings.render()
    else:
        st.error(f"Unknown page: {page}")


if __name__ == "__main__":
    main()
