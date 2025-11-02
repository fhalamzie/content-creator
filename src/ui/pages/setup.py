"""Setup page - Project configuration (brand voice, target audience, keywords)."""

import streamlit as st
from pathlib import Path
import json


CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "project_config.json"


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
    """Render setup page."""
    st.title("⚙️ Project Setup")
    st.caption("Configure your brand voice, target audience, and content strategy")

    # Load existing config
    config = load_project_config()

    # Create form
    with st.form("project_setup_form"):
        st.subheader("Brand Information")

        # Brand name and URL
        col1, col2 = st.columns(2)
        with col1:
            brand_name = st.text_input(
                "Brand Name",
                value=config.get("brand_name", ""),
                placeholder="e.g., TechStartup GmbH",
                help="Your company or personal brand name"
            )
        with col2:
            brand_url = st.text_input(
                "Website URL",
                value=config.get("brand_url", ""),
                placeholder="https://example.com",
                help="Your website URL (optional)"
            )

        st.divider()

        # Brand voice
        st.subheader("Brand Voice")
        brand_voice = st.selectbox(
            "Select Brand Voice",
            options=["Professional", "Casual", "Technical", "Friendly"],
            index=["Professional", "Casual", "Technical", "Friendly"].index(
                config.get("brand_voice", "Professional")
            ),
            help="The tone and style for your content"
        )

        # Target audience
        st.subheader("Target Audience")
        target_audience = st.text_area(
            "Describe Your Target Audience",
            value=config.get("target_audience", ""),
            placeholder="e.g., German-speaking small business owners aged 30-50 looking for digital solutions",
            height=100,
            help="Who is your content for? Be specific about demographics and interests."
        )

        st.divider()

        # Content strategy
        st.subheader("Content Strategy")

        # Keywords
        keywords = st.text_area(
            "Primary Keywords",
            value=config.get("keywords", ""),
            placeholder="Enter keywords separated by commas\ne.g., Digitalisierung, KMU, Software, Innovation",
            height=100,
            help="Keywords to target in your content (German)"
        )

        # Content goals
        content_goals = st.text_area(
            "Content Goals",
            value=config.get("content_goals", ""),
            placeholder="e.g., Generate leads, build brand awareness, educate customers",
            height=80,
            help="What do you want to achieve with your content?"
        )

        # Publishing frequency
        col1, col2 = st.columns(2)
        with col1:
            posts_per_week = st.number_input(
                "Blog Posts Per Week",
                min_value=1,
                max_value=10,
                value=config.get("posts_per_week", 2),
                help="How many blog posts to generate per week"
            )
        with col2:
            social_per_post = st.number_input(
                "Social Posts Per Blog",
                min_value=1,
                max_value=4,
                value=config.get("social_per_post", 4),
                help="Number of social media variants per blog post"
            )

        st.divider()

        # Submit button
        submitted = st.form_submit_button(
            "💾 Save Configuration",
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
            st.success("✅ Configuration saved successfully!")
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
        cost_per_post = 0.98
        monthly_cost = posts_per_month * cost_per_post

        st.info(f"💰 Estimated monthly cost: ${monthly_cost:.2f} ({posts_per_month} blog posts)")
