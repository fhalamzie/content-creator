"""Reusable UI help components for Content Creator.

Design Principles (from TASKS.md):
1. Progressive Help: Inline hints → Tooltips → Expandables
2. Explain Everything: What + Why + When
3. Show Costs First: Before every action
4. Use Defaults: From Settings
5. Collapse Complexity: Hide advanced options
"""

import streamlit as st
from typing import Optional, List, Dict


def tooltip(label: str, help_text: str) -> str:
    """
    Create inline help tooltip using Streamlit's built-in help parameter.

    Args:
        label: Label text
        help_text: Tooltip text shown on hover

    Returns:
        Formatted label with help icon

    Example:
        st.text_input(tooltip("Topic", "The main subject of your article"))
    """
    return f"{label} ℹ️"


def info_box(message: str, type: str = "info") -> None:
    """
    Display colored information box.

    Args:
        message: Message to display
        type: Box type - "info", "success", "warning", "error"

    Example:
        info_box("Your API keys are configured correctly!", "success")
    """
    if type == "info":
        st.info(message)
    elif type == "success":
        st.success(message)
    elif type == "warning":
        st.warning(message)
    elif type == "error":
        st.error(message)


def cost_estimate(
    base_cost: float,
    include_images: bool = False,
    num_images: int = 0,
    include_research: bool = False
) -> None:
    """
    Display cost estimate BEFORE generation.

    Design principle: "Show Costs First" - users must see cost before action.

    Args:
        base_cost: Base content generation cost
        include_images: Whether images will be generated
        num_images: Number of images (hero + supporting)
        include_research: Whether research is included

    Example:
        cost_estimate(0.01, include_images=True, num_images=3)
    """
    total_cost = base_cost
    breakdown = []

    if include_research:
        research_cost = 0.01
        total_cost += research_cost
        breakdown.append(f"Research: ${research_cost:.4f}")

    breakdown.append(f"Blog Content: ${base_cost:.4f}")

    if include_images and num_images > 0:
        # Flux Ultra hero: $0.06, Flux Dev supporting: $0.003 each
        image_cost = 0.06 + (0.003 * (num_images - 1))
        total_cost += image_cost
        breakdown.append(f"Images ({num_images}): ${image_cost:.4f}")

    # Display cost estimate
    st.metric(
        label="💰 Estimated Cost",
        value=f"${total_cost:.4f}",
        delta=f"{len(breakdown)} components",
        help=" + ".join(breakdown)
    )


def time_estimate(
    include_research: bool = False,
    include_images: bool = False,
    num_images: int = 0
) -> None:
    """
    Display time estimate BEFORE generation.

    Args:
        include_research: Whether research is included
        include_images: Whether images will be generated
        num_images: Number of images

    Example:
        time_estimate(include_research=True, include_images=True, num_images=3)
    """
    total_seconds = 0
    breakdown = []

    if include_research:
        research_time = 60  # 1 minute
        total_seconds += research_time
        breakdown.append("Research: ~1min")

    # Blog generation: ~30 seconds
    blog_time = 30
    total_seconds += blog_time
    breakdown.append("Writing: ~30s")

    if include_images and num_images > 0:
        # Flux Ultra: ~13s, Flux Dev: ~10s each
        image_time = 13 + (10 * (num_images - 1))
        total_seconds += image_time
        breakdown.append(f"Images: ~{image_time}s")

    # Format time
    if total_seconds < 60:
        time_str = f"{total_seconds}s"
    else:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        time_str = f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"

    st.metric(
        label="⏱️ Estimated Time",
        value=time_str,
        help=" + ".join(breakdown)
    )


def what_happens_next(steps: Optional[List[str]] = None) -> None:
    """
    Show "What happens next?" expandable section.

    Default 5-step process for Quick Create.

    Args:
        steps: Optional custom steps list. If None, uses default Quick Create steps.

    Example:
        what_happens_next()
    """
    if steps is None:
        steps = [
            "🔍 **Research**: AI searches 5+ sources for accurate, up-to-date information",
            "✍️ **Writing**: Qwen3-Max generates professional German content (1500+ words)",
            "🖼️ **Images**: Flux generates photorealistic images (1 hero + supporting)",
            "💾 **Cache**: Content saved to disk (safe, recoverable, version-controlled)",
            "📤 **Notion**: Synced to your editorial database for review and publishing"
        ]

    with st.expander("❓ What happens next?", expanded=False):
        st.markdown("### Generation Process")
        for step in steps:
            st.markdown(step)

        st.divider()
        st.caption("💡 **Tip**: You can review and edit everything in Notion before publishing")


def feature_explanation(
    title: str,
    what: str,
    why: str,
    when: str,
    icon: str = "ℹ️"
) -> None:
    """
    Show feature explanation: What + Why + When.

    Design principle: "Explain Everything" - users should understand every option.

    Args:
        title: Feature name
        what: What this feature does
        why: Why it exists / benefits
        when: When to use it
        icon: Icon/emoji for the feature

    Example:
        feature_explanation(
            title="Image Generation",
            what="Creates photorealistic AI images for your blog post",
            why="Visual content increases engagement by 80% and SEO rankings",
            when="Use for all public-facing blog posts. Skip for internal drafts.",
            icon="🖼️"
        )
    """
    with st.expander(f"{icon} {title} - Learn More", expanded=False):
        st.markdown(f"**What it does**: {what}")
        st.markdown(f"**Why it exists**: {why}")
        st.markdown(f"**When to use**: {when}")


def settings_reminder(config_key: str, config_value: any) -> None:
    """
    Show reminder that a setting is being used from Settings.

    Design principle: "Use Defaults" - Settings → Quick Create.

    Args:
        config_key: Setting name
        config_value: Current value from Settings

    Example:
        settings_reminder("Brand Voice", "Professional")
    """
    st.caption(f"🔧 Using **{config_key}**: {config_value} (configured in Settings)")


def advanced_options_expander(title: str = "⚙️ Advanced Options") -> any:
    """
    Create expandable section for advanced options.

    Design principle: "Collapse Complexity" - Hide advanced options by default.

    Args:
        title: Expander title

    Returns:
        Streamlit expander context manager

    Example:
        with advanced_options_expander():
            enable_competitor = st.checkbox("Enable competitor research")
    """
    return st.expander(title, expanded=False)


def generation_summary(
    topic: str,
    language: str,
    cost: float,
    time_seconds: int,
    includes: Dict[str, bool]
) -> None:
    """
    Show generation summary BEFORE starting.

    Args:
        topic: Article topic
        language: Content language
        cost: Total estimated cost
        time_seconds: Total estimated time
        includes: Dict of included features (research, images, etc.)

    Example:
        generation_summary(
            topic="PropTech Trends 2025",
            language="German",
            cost=0.076,
            time_seconds=120,
            includes={"research": True, "images": True, "fact_check": False}
        )
    """
    st.markdown("### 📋 Generation Summary")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Topic**: {topic}")
        st.markdown(f"**Language**: {language}")

    with col2:
        minutes = time_seconds // 60
        seconds = time_seconds % 60
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

        st.markdown(f"**Cost**: ${cost:.4f}")
        st.markdown(f"**Time**: ~{time_str}")

    # Features included
    st.markdown("**Includes**:")
    features = []
    if includes.get("research", False):
        features.append("✅ Deep Research")
    if includes.get("images", False):
        features.append("✅ AI Images")
    if includes.get("fact_check", False):
        features.append("✅ Fact Checking")
    if includes.get("seo", False):
        features.append("✅ SEO Optimization")

    st.markdown(" • ".join(features) if features else "❌ No additional features")


def success_message(
    word_count: int,
    cost: float,
    cache_path: str,
    notion_synced: bool = False
) -> None:
    """
    Show success message after generation.

    Args:
        word_count: Number of words generated
        cost: Actual cost spent
        cache_path: Path to cached content
        notion_synced: Whether synced to Notion

    Example:
        success_message(1523, 0.073, "cache/blog_posts/proptech-trends.md", True)
    """
    st.success("✅ Content generated successfully!")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("📝 Words", word_count)

    with col2:
        st.metric("💰 Cost", f"${cost:.4f}")

    with col3:
        status = "Synced" if notion_synced else "Cached"
        st.metric("📤 Status", status)

    st.caption(f"💾 Saved to: `{cache_path}`")

    if notion_synced:
        st.caption("✅ Available in Notion for review and publishing")


def error_message(error: str, retry_suggestion: Optional[str] = None) -> None:
    """
    Show error message with optional retry suggestion.

    Args:
        error: Error message
        retry_suggestion: Optional suggestion for how to fix

    Example:
        error_message(
            "API rate limit exceeded",
            "Wait 60 seconds and try again, or use a different API key"
        )
    """
    st.error(f"❌ Error: {error}")

    if retry_suggestion:
        st.info(f"💡 **Suggestion**: {retry_suggestion}")
