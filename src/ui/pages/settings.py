"""Settings page - Unified configuration (Brand, API Keys, Models, Advanced).

Consolidates brand setup and technical settings into one page.
Each setting includes What/Why/Required? explanations.
"""

import streamlit as st
from pathlib import Path
import os
import json
from dotenv import load_dotenv, set_key, find_dotenv

# Load environment variables
load_dotenv()

# Import help components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ui.components.help import feature_explanation

# Paths
ENV_FILE = Path(find_dotenv() or Path(__file__).parent.parent.parent.parent / ".env")
CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "project_config.json"


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


def load_project_config():
    """Load project configuration from cache."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_project_config(config):
    """Save project configuration to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def render():
    """Render unified settings page."""
    st.title("🔧 Settings")
    st.caption("One place for all configuration: brand, API keys, models, and advanced settings")

    # Create 5 tabs (Brand Setup added as first tab)
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏢 Brand Setup",
        "🔑 API Keys",
        "⚡ Rate Limits",
        "🤖 Models",
        "📊 Advanced"
    ])

    with tab1:
        render_brand_setup()

    with tab2:
        render_api_keys()

    with tab3:
        render_rate_limits()

    with tab4:
        render_models()

    with tab5:
        render_advanced()


def render_brand_setup():
    """Render brand setup (merged from setup.py)."""
    st.subheader("Brand Configuration")
    st.caption("Define your brand identity and content strategy")

    # Show feature explanation
    feature_explanation(
        title="Why Brand Setup?",
        what="Configures your brand voice, target audience, and content goals",
        why="Quick Create uses these defaults, eliminating redundant configuration on every article",
        when="Set this up ONCE before creating your first article. Update anytime your brand evolves.",
        icon="🏢"
    )

    st.divider()

    # Load existing config
    config = load_project_config()

    # Create form
    with st.form("brand_setup_form"):
        st.markdown("### Basic Information")

        # Brand name and URL
        col1, col2 = st.columns(2)
        with col1:
            brand_name = st.text_input(
                "Brand Name ⚠️ Required",
                value=config.get("brand_name", ""),
                placeholder="e.g., TechStartup GmbH",
                help="**What**: Your company or personal brand name\n**Why**: Personalizes content and metadata\n**Required**: Yes"
            )
        with col2:
            brand_url = st.text_input(
                "Website URL (Optional)",
                value=config.get("brand_url", ""),
                placeholder="https://example.com",
                help="**What**: Your main website URL\n**Why**: Used for SEO metadata and backlinks\n**Required**: No"
            )

        st.divider()

        # Brand voice
        st.markdown("### Brand Voice")
        brand_voice = st.selectbox(
            "Select Brand Voice ⚠️ Required",
            options=["Professional", "Casual", "Technical", "Friendly"],
            index=["Professional", "Casual", "Technical", "Friendly"].index(
                config.get("brand_voice", "Professional")
            ),
            help="**What**: The tone and style for all generated content\n**Why**: Ensures consistent brand personality across articles\n**Required**: Yes"
        )

        # Voice descriptions
        voice_descriptions = {
            "Professional": "Formal, authoritative, business-oriented",
            "Casual": "Conversational, friendly, approachable",
            "Technical": "Precise, detailed, expert-focused",
            "Friendly": "Warm, personal, engaging"
        }
        st.caption(f"💡 **{brand_voice}**: {voice_descriptions[brand_voice]}")

        st.divider()

        # Target audience
        st.markdown("### Target Audience")
        target_audience = st.text_area(
            "Describe Your Target Audience ⚠️ Required",
            value=config.get("target_audience", ""),
            placeholder="e.g., German-speaking small business owners aged 30-50 looking for digital solutions",
            height=100,
            help="**What**: Who your content is written for\n**Why**: AI tailors complexity, examples, and language to your audience\n**Required**: Yes\n**Tips**: Include demographics, interests, pain points"
        )

        st.divider()

        # Content strategy
        st.markdown("### Content Strategy")

        # Keywords
        keywords = st.text_area(
            "Primary Keywords (Optional)",
            value=config.get("keywords", ""),
            placeholder="Enter keywords separated by commas\ne.g., Digitalisierung, KMU, Software, Innovation",
            height=100,
            help="**What**: Keywords to naturally include in content\n**Why**: Improves SEO and topic relevance\n**Required**: No\n**Tips**: Use German keywords for German content"
        )

        # Content goals
        content_goals = st.text_area(
            "Content Goals (Optional)",
            value=config.get("content_goals", ""),
            placeholder="e.g., Generate leads, build brand awareness, educate customers",
            height=80,
            help="**What**: What you want to achieve with content\n**Why**: Guides AI to create goal-aligned CTAs and messaging\n**Required**: No"
        )

        st.divider()

        # Publishing frequency
        st.markdown("### Publishing Frequency")
        col1, col2 = st.columns(2)
        with col1:
            posts_per_week = st.number_input(
                "Blog Posts Per Week",
                min_value=1,
                max_value=10,
                value=config.get("posts_per_week", 2),
                help="**What**: Target number of blog posts per week\n**Why**: Used for cost estimates\n**Required**: No (default: 2)"
            )
        with col2:
            social_per_post = st.number_input(
                "Social Posts Per Blog",
                min_value=1,
                max_value=4,
                value=config.get("social_per_post", 4),
                help="**What**: Social media variants per blog post\n**Why**: LinkedIn, Facebook, Twitter, Instagram\n**Required**: No (default: 4)"
            )

        st.divider()

        # Submit button
        submitted = st.form_submit_button(
            "💾 Save Brand Configuration",
            type="primary",
            use_container_width=True
        )

        if submitted:
            # Validate required fields
            if not brand_name:
                st.error("❌ Brand name is required")
                return

            if not target_audience:
                st.error("❌ Target audience is required")
                return

            # Save configuration
            new_config = {
                "brand_name": brand_name,
                "brand_url": brand_url,
                "brand_voice": brand_voice,
                "target_audience": target_audience,
                "keywords": keywords,
                "content_goals": content_goals,
                "posts_per_week": posts_per_week,
                "social_per_post": social_per_post
            }

            save_project_config(new_config)
            st.session_state.project_config = new_config
            st.success("✅ Brand configuration saved successfully!")
            st.balloons()

    # Show current configuration summary
    if config:
        st.divider()
        st.subheader("Current Configuration")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Brand Voice", config.get("brand_voice", "Not set"))
        with col2:
            st.metric("Posts/Week", config.get("posts_per_week", 0))
        with col3:
            st.metric("Social/Blog", config.get("social_per_post", 0))

        # Cost estimate
        posts_per_month = config.get("posts_per_week", 0) * 4
        cost_per_post = 0.076  # Updated cost with images
        monthly_cost = posts_per_month * cost_per_post

        st.info(f"💰 Estimated monthly cost: ${monthly_cost:.2f} ({posts_per_month} blog posts with images)")


def render_api_keys():
    """Render API keys settings."""
    st.subheader("API Keys")
    st.caption("Configure your API keys for external services")

    # Show why API keys are needed
    feature_explanation(
        title="Why do I need these API keys?",
        what="API keys authenticate your account with external services",
        why="Notion stores your content, OpenRouter provides AI models for writing",
        when="Set up ONCE before first generation. Keep these keys secret!",
        icon="🔑"
    )

    st.divider()

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
        st.markdown("#### Notion Integration")
        notion_token = st.text_input(
            "Notion Integration Token ⚠️ Required",
            type="password",
            placeholder="secret_xxxx...",
            help="**What**: Secret token to access your Notion workspace\n**How to get**: https://www.notion.so/my-integrations\n**Required**: Yes (without this, can't save to Notion)"
        )

        notion_page_id = st.text_input(
            "Notion Page ID ⚠️ Required",
            placeholder="32-character page ID",
            value=os.getenv("NOTION_PAGE_ID", ""),
            help="**What**: The parent page where content databases are created\n**How to get**: Copy from Notion page URL\n**Required**: Yes"
        )

        st.divider()

        # OpenRouter
        st.markdown("#### OpenRouter (AI Models)")
        openrouter_key = st.text_input(
            "OpenRouter API Key ⚠️ Required",
            type="password",
            placeholder="sk-or-v1-xxxx...",
            help="**What**: API key for accessing AI writing models\n**How to get**: https://openrouter.ai/keys\n**Required**: Yes (without this, can't generate content)\n**Cost**: Pay-as-you-go (~$0.076/article)"
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
                st.success("✅ OpenRouter connection configured!")
            except Exception as e:
                st.error(f"❌ OpenRouter connection failed: {str(e)}")


def render_rate_limits():
    """Render rate limits settings."""
    st.subheader("Rate Limits")
    st.caption("Configure API rate limiting to avoid throttling")

    # Explanation
    feature_explanation(
        title="What are rate limits?",
        what="Maximum API requests per second to prevent overwhelming external services",
        why="Notion has a 3 req/sec limit. We use 2.5 req/sec for safety margin to avoid errors.",
        when="Default (2.5 req/sec) works for most users. Only change if you experience rate limit errors.",
        icon="⚡"
    )

    st.divider()

    current_limit = float(os.getenv("NOTION_RATE_LIMIT", "2.5"))

    with st.form("rate_limits_form"):
        notion_rate = st.slider(
            "Notion API Rate Limit (requests/second)",
            min_value=1.0,
            max_value=3.0,
            value=current_limit,
            step=0.1,
            help="**Official limit**: 3 req/s\n**Recommended**: 2.5 req/s for safety\n**Lower**: Slower but safer"
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

    # Explanation
    feature_explanation(
        title="Which model should I choose?",
        what="Different AI models have different costs and quality levels",
        why="Qwen3-Max provides excellent German quality at lowest cost. Claude/GPT-4 are premium options.",
        when="Default (Qwen3-Max) recommended for most users. Switch to Claude for mission-critical content.",
        icon="🤖"
    )

    st.divider()

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
            help="**Recommended**: qwen/qwq-32b-preview (best German quality, lowest cost)\n**Premium**: Claude Sonnet 4 (highest quality, 3.5x cost)"
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
            help="**Recommended**: qwen/qwq-32b-preview (fast and cheap for social posts)"
        )

        # Content language
        content_language = st.selectbox(
            "Content Language",
            options=["de", "en", "fr", "es"],
            index=0,
            help="**What**: Primary language for generated content\n**Supported**: German (de), English (en), French (fr), Spanish (es)"
        )

        # Cost estimate
        st.divider()
        st.caption("💰 **Estimated Cost per Article:**")

        costs = {
            "qwen/qwq-32b-preview": 0.0056,
            "anthropic/claude-sonnet-4": 0.020,
            "anthropic/claude-opus-4": 0.086,
            "anthropic/claude-haiku-4": 0.003,
            "openai/gpt-4": 0.069
        }

        writing_cost = costs.get(writing_model, 0.0056)
        repurposing_cost = costs.get(repurposing_model, 0.0) * 0.27  # Social posts
        image_cost = 0.070  # Average image cost (hero + 1-2 supporting)
        total_cost = writing_cost + repurposing_cost + image_cost

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Writing", f"${writing_cost:.4f}")
        with col2:
            st.metric("Images", f"${image_cost:.3f}")
        with col3:
            st.metric("Social", f"${repurposing_cost:.4f}")
        with col4:
            st.metric("Total", f"${total_cost:.3f}")

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
    st.caption("Advanced configuration options for power users")

    # Explanation
    feature_explanation(
        title="Advanced Settings",
        what="Feature flags, logging, and experimental options",
        why="Fine-tune system behavior for specific use cases",
        when="Only change these if you know what you're doing. Defaults work for 95% of users.",
        icon="📊"
    )

    st.divider()

    with st.form("advanced_form"):
        # Cache directory
        cache_dir = st.text_input(
            "Cache Directory",
            value=os.getenv("CACHE_DIR", "cache"),
            help="**What**: Directory for storing cached content\n**Default**: cache/\n**When to change**: Custom backup location"
        )

        # Log level
        log_level = st.selectbox(
            "Log Level",
            options=["DEBUG", "INFO", "WARNING", "ERROR"],
            index=1,
            help="**DEBUG**: All logs (verbose)\n**INFO**: Normal operations (recommended)\n**WARNING**: Warnings only\n**ERROR**: Errors only"
        )

        # Enable features
        st.caption("**Feature Flags:**")
        enable_research = st.checkbox(
            "Enable Web Research",
            value=True,
            help="**What**: AI searches 5+ sources before writing\n**Why**: Ensures accurate, up-to-date content\n**Cost**: $0.01/article"
        )

        enable_fact_check = st.checkbox(
            "Enable Fact Checking",
            value=True,
            help="**What**: 4-layer hallucination detection with Gemini CLI\n**Why**: Catches false claims and unsupported statements\n**Cost**: FREE"
        )

        enable_auto_sync = st.checkbox(
            "Enable Auto-Sync to Notion",
            value=True,
            help="**What**: Automatically sync generated content to Notion\n**Why**: Content saved to editorial database for review\n**When to disable**: Testing or debugging"
        )

        # Fact-checking thoroughness (only shown if enabled)
        fact_check_thoroughness = "medium"
        if enable_fact_check:
            st.caption("**Fact-Checking Configuration:**")
            fact_check_thoroughness = st.select_slider(
                "Thoroughness Level",
                options=["basic", "medium", "thorough"],
                value=os.getenv("FACT_CHECK_THOROUGHNESS", "medium"),
                help="**Basic**: URLs only (~6s, FREE)\n**Medium**: URLs + top 5 claims (~16s, FREE)\n**Thorough**: All claims (~30s, FREE)"
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
