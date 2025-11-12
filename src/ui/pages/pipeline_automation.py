"""
Pipeline Automation Page - Automated Website → Topics → Articles

6-Stage Pipeline:
1. Website Analysis - Extract keywords/tags/themes from customer site (FREE, Gemini API)
2. Competitor Research - Find competitors + market trends with automatic fallback (FREE → $0.02)
3. Consolidation - Merge and deduplicate keywords (FREE, CPU)
4. Topic Discovery - Generate 50+ candidates from 5 collectors (FREE, pattern-based)
5. Topic Validation - 5-metric scoring filters to top 20 (60% cost savings)
6. Research Topics - DeepResearcher → Reranker → Synthesizer ($0.01/topic)

Features:
- Automatic fallback (Gemini rate limit → Tavily API)
- Cost tracking per stage
- Topic selection for research
- Full pipeline or partial execution
"""

import streamlit as st
from pathlib import Path
import json
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import pipeline components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.orchestrator.hybrid_research_orchestrator import HybridResearchOrchestrator
from src.utils.config_loader import ConfigLoader

CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "pipeline_automation_config.json"


def load_pipeline_config():
    """Load pipeline configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "market": "Germany",
        "vertical": "PropTech",
        "domain": "SaaS",
        "language": "de",
        "enable_tavily": True,
        "max_topics_to_research": 10,
        "enable_images": False
    }


def save_pipeline_config(config: dict):
    """Save pipeline configuration."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def render_config_sidebar():
    """Render configuration sidebar."""
    with st.sidebar:
        st.header("⚙️ Pipeline Configuration")

        config = load_pipeline_config()

        # Customer info
        st.subheader("🏢 Customer Info")
        market = st.text_input(
            "Market",
            value=config.get("market", "Germany"),
            help="Target market (e.g., Germany, USA, France)"
        )
        vertical = st.text_input(
            "Vertical",
            value=config.get("vertical", "PropTech"),
            help="Industry vertical (e.g., PropTech, SaaS, Fashion)"
        )
        domain = st.text_input(
            "Domain",
            value=config.get("domain", "SaaS"),
            help="Business domain (e.g., SaaS, E-commerce, B2B)"
        )
        language = st.selectbox(
            "Language",
            ["de", "en", "fr", "es"],
            index=["de", "en", "fr", "es"].index(config.get("language", "de")),
            help="Content language"
        )

        # Pipeline settings
        st.subheader("🔧 Pipeline Settings")
        enable_tavily = st.checkbox(
            "Enable Tavily Fallback",
            value=config.get("enable_tavily", True),
            help="Automatic fallback when Gemini rate-limited ($0.02/fallback)"
        )
        max_topics_to_research = st.slider(
            "Max Topics to Research",
            min_value=1,
            max_value=50,
            value=config.get("max_topics_to_research", 10),
            step=1,
            help="Number of validated topics to research (after Stage 5)"
        )

        # Image generation
        st.subheader("🖼️ Image Generation")
        enable_images = st.checkbox(
            "Generate images (1 HD hero + 2 supporting)",
            value=config.get("enable_images", False),
            help="DALL-E 3: $0.16/topic (1 HD hero $0.08 + 2 standard supporting $0.08)"
        )

        if st.button("💾 Save Configuration", use_container_width=True):
            new_config = {
                "market": market,
                "vertical": vertical,
                "domain": domain,
                "language": language,
                "enable_tavily": enable_tavily,
                "max_topics_to_research": max_topics_to_research,
                "enable_images": enable_images
            }
            save_pipeline_config(new_config)
            st.success("✅ Configuration saved!")
            st.rerun()

        st.divider()

        # Cost estimation
        st.caption("💰 **Cost Estimation**")
        research_cost = 0.01 * max_topics_to_research
        image_cost = 0.16 * max_topics_to_research if enable_images else 0.0
        fallback_cost = 0.02  # One-time max if Gemini rate-limited
        total_cost = research_cost + image_cost
        total_with_fallback = total_cost + fallback_cost

        st.caption(f"• Research: ${research_cost:.2f} ({max_topics_to_research} topics)")
        if enable_images:
            st.caption(f"• Images: +${image_cost:.2f}")
        st.caption(f"• Fallback: +${fallback_cost:.2f} (if triggered)")
        st.caption(f"**Total**: ${total_cost:.2f} - ${total_with_fallback:.2f}")

        return {
            "market": market,
            "vertical": vertical,
            "domain": domain,
            "language": language,
            "enable_tavily": enable_tavily,
            "max_topics_to_research": max_topics_to_research,
            "enable_images": enable_images
        }


async def run_pipeline_async(
    website_url: str,
    config: dict,
    progress_container,
    run_full_pipeline: bool = True
) -> Dict:
    """Run pipeline with real-time progress updates."""

    # Progress tracking
    progress_bar = progress_container.progress(0.0)
    status_text = progress_container.empty()
    metrics_container = progress_container.container()

    start_time = datetime.now()

    try:
        # Initialize orchestrator
        status_text.info("🔧 **Initializing**: Setting up pipeline orchestrator...")
        orchestrator = HybridResearchOrchestrator(enable_tavily=config["enable_tavily"])

        # Prepare customer info
        customer_info = {
            "market": config["market"],
            "vertical": config["vertical"],
            "domain": config["domain"],
            "language": config["language"]
        }

        if run_full_pipeline:
            # Full pipeline: Website → Topics → Articles
            progress_bar.progress(0.0)
            status_text.info("🚀 **Running Full Pipeline**: Website → Topics → Articles...")

            # Run with progress callback
            def update_progress(stage: int, message: str):
                progress = stage / 6.0
                progress_bar.progress(progress)
                status_text.info(f"**Stage {stage}/6**: {message}")

            result = await orchestrator.run_pipeline(
                website_url=website_url,
                customer_info=customer_info,
                max_topics_to_research=config["max_topics_to_research"]
            )

            # Display metrics
            progress_bar.progress(1.0)

            # Extract topics from validation_data
            validated_topics_list = [
                {"topic": st.topic, "score": st.total_score}
                for st in result["validation_data"]["scored_topics"]
            ]

            with metrics_container:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Topics Discovered", result["discovered_topics_data"]["total_topics"])
                col2.metric("Articles Researched", len(result["research_results"]))
                col3.metric("Total Cost", f"${result['total_cost']:.3f}")
                col4.metric("Duration", f"{result['total_duration_sec']:.1f}s")

            status_text.success(f"✅ **Pipeline Complete!** ({result['total_duration_sec']:.1f}s)")

            return {
                "success": True,
                "mode": "full_pipeline",
                "website_url": website_url,
                "topics": validated_topics_list,
                "articles": result["research_results"],
                "total_cost": result["total_cost"],
                "duration_sec": result["total_duration_sec"]
            }

        else:
            # Topic discovery only (Stages 1-5)
            progress_bar.progress(0.0)
            status_text.info("🔍 **Discovering Topics**: Running Stages 1-5...")

            # Stage 1: Website Analysis
            progress_bar.progress(0.17)
            status_text.info("**Stage 1/6**: Extracting keywords from website...")
            keywords_result = await orchestrator.extract_website_keywords(website_url)

            # Stage 2: Competitor Research
            progress_bar.progress(0.33)
            status_text.info("**Stage 2/6**: Researching competitors (Gemini → Tavily fallback)...")
            competitors_result = await orchestrator.research_competitors(
                keywords_result["keywords"],
                customer_info
            )

            # Stage 3: Consolidation
            progress_bar.progress(0.50)
            status_text.info("**Stage 3/6**: Consolidating keywords and topics...")
            consolidated = orchestrator.consolidate_keywords_and_topics(
                keywords_result,
                competitors_result
            )

            # Stage 4: Topic Discovery
            progress_bar.progress(0.67)
            status_text.info("**Stage 4/6**: Discovering topics from 5 collectors...")
            topics_result = await orchestrator.discover_topics_from_collectors(
                consolidated["consolidated_keywords"],
                consolidated["consolidated_tags"]
            )

            # Stage 5: Topic Validation
            progress_bar.progress(0.83)
            status_text.info("**Stage 5/6**: Validating and scoring topics (60% cost savings)...")
            validation_result = orchestrator.validate_and_score_topics(
                discovered_topics=topics_result["discovered_topics"],
                topics_by_source=topics_result["topics_by_source"],
                consolidated_keywords=consolidated["consolidated_keywords"],
                threshold=0.3,  # Lower threshold to see more topics
                top_n=config["max_topics_to_research"]
            )
            # scored_topics is List[ScoredTopic] - convert to dict format for display
            validated_topics = [
                {"topic": st.topic, "score": st.total_score}
                for st in validation_result["scored_topics"]
            ]

            # If no topics passed validation, show top raw topics anyway
            if not validated_topics:
                status_text.warning(f"⚠️ No topics passed threshold 0.3. Showing top {config['max_topics_to_research']} raw topics...")
                validated_topics = [
                    {"topic": topic, "score": 0.0}
                    for topic in topics_result["discovered_topics"][:config["max_topics_to_research"]]
                ]

            progress_bar.progress(1.0)
            duration = (datetime.now() - start_time).total_seconds()

            with metrics_container:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Raw Topics", topics_result["total_topics"])
                col2.metric("Validated Topics", len(validated_topics))
                col3.metric("Keywords Extracted", len(consolidated["consolidated_keywords"]))
                col4.metric("Duration", f"{duration:.1f}s")

            status_text.success(f"✅ **Topic Discovery Complete!** ({duration:.1f}s)")

            return {
                "success": True,
                "mode": "discovery_only",
                "website_url": website_url,
                "topics": validated_topics,
                "all_keywords": consolidated["consolidated_keywords"],
                "total_cost": 0.0,  # Discovery is FREE
                "duration_sec": duration
            }

    except Exception as e:
        progress_bar.progress(0.0)
        status_text.error(f"❌ **Pipeline Failed**: {str(e)}")
        raise


async def research_selected_topics_async(
    topics: List[Dict],
    config: dict,
    progress_container
) -> List[Dict]:
    """Research selected topics."""

    progress_bar = progress_container.progress(0.0)
    status_text = progress_container.empty()

    try:
        orchestrator = HybridResearchOrchestrator(enable_tavily=config["enable_tavily"])

        customer_info = {
            "market": config["market"],
            "vertical": config["vertical"],
            "domain": config["domain"],
            "language": config["language"]
        }

        articles = []
        total = len(topics)

        for i, topic in enumerate(topics):
            progress = (i + 1) / total
            progress_bar.progress(progress)
            status_text.info(f"🔬 **Researching {i+1}/{total}**: {topic['topic'][:60]}...")

            article = await orchestrator.research_topic(
                topic=topic["topic"],
                config=customer_info,
                enable_images=config.get("enable_images", False)
            )
            articles.append(article)

        progress_bar.progress(1.0)
        status_text.success(f"✅ **Research Complete!** ({total} articles)")

        return articles

    except Exception as e:
        status_text.error(f"❌ **Research Failed**: {str(e)}")
        raise


def render_topics_table(topics: List[Dict]):
    """Render topics as selectable table."""
    st.subheader(f"📋 Discovered Topics ({len(topics)})")
    st.caption(f"Select topics to research (estimated cost: ${0.01 * len(topics):.2f})")

    if not topics:
        st.warning("No topics discovered. Try adjusting the customer info or website URL.")
        return []

    # Create selection checkboxes
    selected_indices = []

    for i, topic in enumerate(topics):
        col1, col2, col3 = st.columns([1, 6, 2])

        with col1:
            selected = st.checkbox("", key=f"topic_{i}", value=False)
            if selected:
                selected_indices.append(i)

        with col2:
            st.text(topic["topic"])

        with col3:
            score = topic.get("score", 0.0)
            if score > 0:
                st.caption(f"Score: {score:.2f}")
            else:
                st.caption("Raw")

    return [topics[i] for i in selected_indices]


def render_articles(articles: List[Dict], config: dict):
    """Render researched articles."""
    st.subheader(f"📚 Researched Articles ({len(articles)})")

    for i, article in enumerate(articles, 1):
        with st.expander(f"{i}. {article.get('title', article.get('topic', 'Untitled'))[:80]}"):

            # Tabs for article content
            if config.get("enable_images", False):
                tabs = st.tabs(["🖼️ Hero Image", "📝 Article", "🖼️ Supporting Images", "📊 Metadata"])

                with tabs[0]:
                    if article.get("hero_image_url"):
                        st.image(
                            article["hero_image_url"],
                            caption=article.get("hero_image_alt", "Hero image"),
                            use_container_width=True
                        )
                    else:
                        st.info("No hero image generated")

                with tabs[1]:
                    st.markdown(article.get("article", "*No content*"))

                with tabs[2]:
                    supporting = article.get("supporting_images", [])
                    if supporting:
                        cols = st.columns(2)
                        for j, img in enumerate(supporting):
                            with cols[j % 2]:
                                st.image(
                                    img.get("url"),
                                    caption=img.get("alt", f"Supporting {j+1}"),
                                    use_container_width=True
                                )
                    else:
                        st.info("No supporting images generated")

                with tabs[3]:
                    st.json({
                        "word_count": len((article.get("article") or "").split()),
                        "sources": len(article.get("sources") or []),
                        "cost": article.get("cost", 0.0),
                        "image_cost": article.get("image_cost", 0.0)
                    })
            else:
                tabs = st.tabs(["📝 Article", "📊 Metadata"])

                with tabs[0]:
                    st.markdown(article.get("article", "*No content*"))

                with tabs[1]:
                    st.json({
                        "word_count": len(article.get("article", "").split()),
                        "sources": len(article.get("sources", [])),
                        "cost": article.get("cost", 0.0)
                    })


def render():
    """Render Pipeline Automation page."""
    st.title("🎯 Pipeline Automation")
    st.caption("Automated Website → Topics → Articles (6-stage pipeline with 60% cost optimization)")

    # Render config sidebar
    config = render_config_sidebar()

    # Initialize session state
    if "pipeline_result" not in st.session_state:
        st.session_state.pipeline_result = None
    if "researched_articles" not in st.session_state:
        st.session_state.researched_articles = None

    # Main content
    st.header("🌐 Website Analysis")

    # Website URL input
    website_url = st.text_input(
        "Enter website URL",
        placeholder="https://example-proptech.com",
        help="Customer website to analyze for topic discovery"
    )

    # Pipeline mode selection
    col1, col2 = st.columns(2)
    with col1:
        discovery_button = st.button(
            "🔍 Discover Topics (Stages 1-5)",
            type="secondary",
            use_container_width=True,
            disabled=not website_url,
            help="Run topic discovery only (FREE, no research)"
        )
    with col2:
        full_pipeline_button = st.button(
            "🚀 Full Pipeline (Stages 1-6)",
            type="primary",
            use_container_width=True,
            disabled=not website_url,
            help=f"Discover + Research top {config['max_topics_to_research']} topics"
        )

    # Process buttons
    if (discovery_button or full_pipeline_button) and website_url:
        # Check API keys
        required_keys = ["GEMINI_API_KEY"]
        if config["enable_tavily"]:
            required_keys.append("TAVILY_API_KEY")

        missing_keys = [key for key in required_keys if not os.getenv(key)]
        if missing_keys:
            st.error(f"❌ Missing API keys: {', '.join(missing_keys)}")
            return

        # Run pipeline
        st.divider()
        st.header("⚙️ Pipeline Processing")
        progress_container = st.container()

        try:
            result = asyncio.run(
                run_pipeline_async(
                    website_url,
                    config,
                    progress_container,
                    run_full_pipeline=full_pipeline_button
                )
            )
            st.session_state.pipeline_result = result
            st.session_state.researched_articles = result.get("articles", []) if full_pipeline_button else None

        except Exception as e:
            st.error(f"❌ Pipeline failed: {str(e)}")
            st.exception(e)

    # Display results
    if st.session_state.pipeline_result:
        st.divider()
        result = st.session_state.pipeline_result

        # Show topics
        if result.get("topics"):
            st.header("📋 Results")

            if result["mode"] == "discovery_only":
                # Allow topic selection for research
                selected_topics = render_topics_table(result["topics"])

                if selected_topics:
                    st.divider()
                    research_button = st.button(
                        f"🔬 Research {len(selected_topics)} Selected Topics",
                        type="primary",
                        use_container_width=True
                    )

                    if research_button:
                        progress_container = st.container()
                        try:
                            articles = asyncio.run(
                                research_selected_topics_async(
                                    selected_topics,
                                    config,
                                    progress_container
                                )
                            )
                            st.session_state.researched_articles = articles
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Research failed: {str(e)}")
                            st.exception(e)

            else:
                # Full pipeline - show all topics
                st.success(f"✅ Discovered {len(result['topics'])} topics")
                with st.expander("📋 View All Topics"):
                    for i, topic in enumerate(result["topics"], 1):
                        st.caption(f"{i}. {topic['topic']} (Score: {topic.get('score', 0.0):.2f})")

        # Show researched articles
        if st.session_state.researched_articles:
            st.divider()
            render_articles(st.session_state.researched_articles, config)

        # Clear results button
        if st.button("🗑️ Clear Results", use_container_width=True):
            st.session_state.pipeline_result = None
            st.session_state.researched_articles = None
            st.rerun()
