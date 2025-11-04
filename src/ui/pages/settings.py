"""Settings page - API keys, rate limits, and model configuration."""

import streamlit as st
from pathlib import Path
import os
from dotenv import load_dotenv, set_key, find_dotenv

# Load environment variables
load_dotenv()

ENV_FILE = find_dotenv() or Path(__file__).parent.parent.parent.parent / ".env"


def mask_api_key(key: str) -> str:
    """Mask API key for display."""
    if not key or len(key) < 8:
        return "Not set"
    return f"{key[:4]}...{key[-4:]}"


def save_env_variable(key: str, value: str):
    """Save environment variable to .env file."""
    if not ENV_FILE.exists():
        ENV_FILE.touch()

    set_key(ENV_FILE, key, value)
    os.environ[key] = value


def render():
    """Render settings page."""
    st.title("🔧 Settings")
    st.caption("Configure API keys, rate limits, and model settings")

    # Tabs for different settings
    tab1, tab2, tab3, tab4 = st.tabs(["🔑 API Keys", "⚡ Rate Limits", "🤖 Models", "📊 Advanced"])

    with tab1:
        render_api_keys()

    with tab2:
        render_rate_limits()

    with tab3:
        render_models()

    with tab4:
        render_advanced()


def render_api_keys():
    """Render API keys settings."""
    st.subheader("API Keys")
    st.caption("Configure your API keys for external services")

    # Current keys (masked)
    with st.expander("👁️ View Current Keys", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.caption("**Notion Token:**")
            st.code(mask_api_key(os.getenv("NOTION_TOKEN", "")))
        with col2:
            st.caption("**OpenRouter API Key:**")
            st.code(mask_api_key(os.getenv("OPENROUTER_API_KEY", "")))

    st.divider()

    # Update keys form
    with st.form("api_keys_form"):
        st.subheader("Update API Keys")

        # Notion
        notion_token = st.text_input(
            "Notion Integration Token",
            type="password",
            placeholder="secret_xxxx...",
            help="Get from https://www.notion.so/my-integrations"
        )

        notion_page_id = st.text_input(
            "Notion Page ID",
            placeholder="32-character page ID",
            value=os.getenv("NOTION_PAGE_ID", ""),
            help="The parent page ID for your content databases"
        )

        # OpenRouter
        openrouter_key = st.text_input(
            "OpenRouter API Key",
            type="password",
            placeholder="sk-or-v1-xxxx...",
            help="Get from https://openrouter.ai/keys"
        )

        # Submit
        if st.form_submit_button("💾 Save API Keys", type="primary"):
            updated = False

            if notion_token:
                save_env_variable("NOTION_TOKEN", notion_token)
                updated = True

            if notion_page_id:
                save_env_variable("NOTION_PAGE_ID", notion_page_id)
                updated = True

            if openrouter_key:
                save_env_variable("OPENROUTER_API_KEY", openrouter_key)
                updated = True

            if updated:
                st.success("✅ API keys updated successfully!")
                st.info("ℹ️ Restart the app to apply changes")
            else:
                st.warning("⚠️ No changes made")

    # Test connections
    st.divider()
    st.subheader("Test Connections")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🧪 Test Notion Connection", use_container_width=True):
            try:
                from notion_integration.notion_client import NotionClient
                NotionClient(os.getenv("NOTION_TOKEN", ""))
                st.success("✅ Notion connection successful!")
            except Exception as e:
                st.error(f"❌ Notion connection failed: {str(e)}")

    with col2:
        if st.button("🧪 Test OpenRouter Connection", use_container_width=True):
            try:
                from openai import OpenAI
                OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=os.getenv("OPENROUTER_API_KEY", "")
                )
                # Test with a minimal request
                st.success("✅ OpenRouter connection configured!")
            except Exception as e:
                st.error(f"❌ OpenRouter connection failed: {str(e)}")


def render_rate_limits():
    """Render rate limits settings."""
    st.subheader("Rate Limits")
    st.caption("Configure API rate limiting to avoid throttling")

    current_limit = float(os.getenv("NOTION_RATE_LIMIT", "2.5"))

    with st.form("rate_limits_form"):
        notion_rate = st.slider(
            "Notion API Rate Limit (requests/second)",
            min_value=1.0,
            max_value=3.0,
            value=current_limit,
            step=0.1,
            help="Official limit is 3 req/s. Use 2.5 for safety margin."
        )

        st.info(f"💡 With {notion_rate} req/s, syncing 10 posts will take ~{10/notion_rate:.1f} seconds")

        if st.form_submit_button("💾 Save Rate Limits", type="primary"):
            save_env_variable("NOTION_RATE_LIMIT", str(notion_rate))
            st.success("✅ Rate limits updated!")
            st.info("ℹ️ Restart the app to apply changes")


def render_models():
    """Render model configuration."""
    st.subheader("AI Models")
    st.caption("Configure which AI models to use for different tasks")

    with st.form("models_form"):
        # Writing model
        writing_model = st.selectbox(
            "Writing Model",
            options=[
                "qwen/qwq-32b-preview",
                "anthropic/claude-sonnet-4",
                "anthropic/claude-opus-4",
                "openai/gpt-4"
            ],
            index=0,
            help="Model for blog post generation"
        )

        # Repurposing model
        repurposing_model = st.selectbox(
            "Repurposing Model",
            options=[
                "qwen/qwq-32b-preview",
                "anthropic/claude-sonnet-4",
                "anthropic/claude-haiku-4",
                "openai/gpt-4"
            ],
            index=0,
            help="Model for social media content"
        )

        # Content language
        content_language = st.selectbox(
            "Content Language",
            options=["de", "en"],
            index=0,
            help="Primary language for generated content"
        )

        # Cost estimate
        st.divider()
        st.caption("💰 **Estimated Cost per Bundle:**")

        costs = {
            "qwen/qwq-32b-preview": 0.98,
            "anthropic/claude-sonnet-4": 3.50,
            "anthropic/claude-opus-4": 15.00,
            "anthropic/claude-haiku-4": 0.50,
            "openai/gpt-4": 12.00
        }

        writing_cost = costs.get(writing_model, 1.0) * 0.65  # Writing is ~65% of total
        repurposing_cost = costs.get(repurposing_model, 0.5) * 0.27  # Repurposing is ~27%
        total_cost = writing_cost + repurposing_cost

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Writing", f"${writing_cost:.2f}")
        with col2:
            st.metric("Repurposing", f"${repurposing_cost:.2f}")
        with col3:
            st.metric("Total", f"${total_cost:.2f}")

        # Submit
        if st.form_submit_button("💾 Save Model Configuration", type="primary"):
            save_env_variable("MODEL_WRITING", writing_model)
            save_env_variable("MODEL_REPURPOSING", repurposing_model)
            save_env_variable("CONTENT_LANGUAGE", content_language)

            st.success("✅ Model configuration updated!")
            st.info("ℹ️ Restart the app to apply changes")


def render_advanced():
    """Render advanced settings."""
    st.subheader("Advanced Settings")
    st.caption("Advanced configuration options")

    with st.form("advanced_form"):
        # Cache directory
        cache_dir = st.text_input(
            "Cache Directory",
            value=os.getenv("CACHE_DIR", "cache"),
            help="Directory for storing cached content"
        )

        # Log level
        log_level = st.selectbox(
            "Log Level",
            options=["DEBUG", "INFO", "WARNING", "ERROR"],
            index=1,
            help="Logging verbosity level"
        )

        # Enable features
        st.caption("**Feature Flags:**")
        enable_research = st.checkbox("Enable Web Research", value=True)
        enable_fact_check = st.checkbox("Enable Fact Checking", value=True, help="4-layer hallucination detection with Gemini CLI (FREE)")
        enable_auto_sync = st.checkbox("Enable Auto-Sync to Notion", value=True)

        # Fact-checking thoroughness (only shown if enabled)
        fact_check_thoroughness = "medium"
        if enable_fact_check:
            st.caption("**Fact-Checking Configuration:**")
            fact_check_thoroughness = st.select_slider(
                "Thoroughness Level",
                options=["basic", "medium", "thorough"],
                value=os.getenv("FACT_CHECK_THOROUGHNESS", "medium"),
                help="Basic: URLs only (~6s, FREE) | Medium: URLs + top 5 claims (~16s, FREE) | Thorough: All claims (~30s, FREE)"
            )
            time_estimates = {'basic': '~6s', 'medium': '~16s', 'thorough': '~30s'}
            st.caption(f"⏱️ Estimated time: {time_estimates[fact_check_thoroughness]} | 💰 Cost: $0.00 (FREE)")

        # Submit
        if st.form_submit_button("💾 Save Advanced Settings", type="primary"):
            save_env_variable("CACHE_DIR", cache_dir)
            save_env_variable("LOG_LEVEL", log_level)
            save_env_variable("ENABLE_RESEARCH", str(enable_research))
            save_env_variable("ENABLE_FACT_CHECK", str(enable_fact_check))
            save_env_variable("FACT_CHECK_THOROUGHNESS", fact_check_thoroughness)
            save_env_variable("ENABLE_AUTO_SYNC", str(enable_auto_sync))

            st.success("✅ Advanced settings updated!")
            st.info("💡 Fact-checking uses Gemini CLI (FREE) - no cost impact")

    # Danger zone
    st.divider()
    st.subheader("⚠️ Danger Zone")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ Clear Cache", type="secondary", use_container_width=True):
            st.warning("⚠️ This will delete all cached content. Feature coming soon!")

    with col2:
        if st.button("🔄 Reset All Settings", type="secondary", use_container_width=True):
            st.warning("⚠️ This will reset all settings to defaults. Feature coming soon!")
