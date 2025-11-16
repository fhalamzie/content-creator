"""
Pipeline Automation Page - 3-Step Wizard for Automated Content Generation

Design Principles (Session 051, Phase 4):
1. Clear 3-step wizard structure (Configure → Discover → Research)
2. Show "What we'll do" at each step
3. Display costs BEFORE execution (not after)
4. Prominent progress indicators (Step 1/3, 2/3, 3/3)
5. Explain what's happening at each stage

Wizard Steps:
- Step 1/3: Configure & Preview - Enter website URL, see what will happen, cost estimate
- Step 2/3: Discover Topics - Run 5 stages (FREE), validate 50+ topics
- Step 3/3: Research & Generate - Select topics, deep research ($0.01/topic)
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
from ui.components.help import cost_estimate, time_estimate, what_happens_next

CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "pipeline_automation_config.json"


def wizard_progress_indicator(current_step: int, total_steps: int = 3):
    """
    Display wizard progress indicator.

    Args:
        current_step: Current step number (1-3)
        total_steps: Total number of steps (default 3)
    """
    st.markdown(f"### Step {current_step}/{total_steps}")
    progress_percentage = (current_step - 1) / total_steps
    st.progress(progress_percentage)
    st.caption(f"**Progress**: {int(progress_percentage * 100)}% complete")


def step_explanation(title: str, what_well_do: List[str], why: str):
    """
    Show step explanation: What we'll do + Why.

    Args:
        title: Step title
        what_well_do: List of actions (bullet points)
        why: Why this step is important
    """
    with st.expander(f"ℹ️ What happens in this step?", expanded=False):
        st.markdown(f"### {title}")
        st.markdown("**What we'll do:**")
        for item in what_well_do:
            st.markdown(f"- {item}")
        st.markdown(f"**Why:** {why}")


def cost_preview(
    num_topics: int,
    enable_images: bool = False,
    enable_tavily: bool = True
):
    """
    Show cost preview BEFORE execution.

    Args:
        num_topics: Number of topics to research
        enable_images: Whether images will be generated
        enable_tavily: Whether Tavily fallback is enabled
    """
    st.markdown("### 💰 Cost Estimate")

    # Discovery cost
    discovery_cost = 0.0  # FREE
    st.caption(f"✅ **Topic Discovery** (Steps 1-5): FREE")

    # Research cost
    research_cost = 0.01 * num_topics
    st.caption(f"📊 **Topic Research** ({num_topics} topics × $0.01): ${research_cost:.2f}")

    # Image cost
    if enable_images:
        image_cost = 0.076 * num_topics  # Average cost with mixed models
        st.caption(f"🖼️ **Image Generation** ({num_topics} topics × $0.076): ${image_cost:.2f}")
    else:
        image_cost = 0.0
        st.caption(f"🖼️ **Image Generation**: Disabled (add +${0.076 * num_topics:.2f} to enable)")

    # Fallback cost
    fallback_cost = 0.02 if enable_tavily else 0.0
    if enable_tavily:
        st.caption(f"🔄 **Tavily Fallback** (if Gemini rate-limited): +${fallback_cost:.2f}")

    # Total
    total_min = discovery_cost + research_cost + image_cost
    total_max = total_min + fallback_cost

    if fallback_cost > 0:
        st.metric("**Total Estimated Cost**", f"${total_min:.2f} - ${total_max:.2f}")
    else:
        st.metric("**Total Estimated Cost**", f"${total_min:.2f}")

    st.divider()


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
        "max_topics_to_research": 50,
        "enable_images": False,
        # Topic discovery collectors (language/region auto-detect from "language" field)
        "enable_autocomplete": True,
        "enable_trends": True,
        "enable_rss": True
    }


def save_pipeline_config(config: dict):
    """Save pipeline configuration."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


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

        # Auto-detect topic discovery language/region from content language if not set
        topic_lang = config.get("topic_discovery_language") or config.get("language", "en")
        topic_region = config.get("topic_discovery_region") or {
            "de": "DE", "en": "US", "fr": "FR", "es": "ES", "it": "IT"
        }.get(topic_lang, "US")

        orchestrator = HybridResearchOrchestrator(
            enable_tavily=config["enable_tavily"],
            enable_autocomplete=config.get("enable_autocomplete", True),
            enable_trends=config.get("enable_trends", True),
            enable_rss=config.get("enable_rss", True),
            topic_discovery_language=topic_lang,
            topic_discovery_region=topic_region
        )

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
                {
                    "topic": st.topic,
                    "score": st.total_score,
                    "sources": st.metadata.sources if st.metadata.sources else [st.metadata.source]
                }
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
            status_text.info("**Stage 1/6**: 🌐 Analyzing website content and extracting keywords...")
            keywords_result = await orchestrator.extract_website_keywords(website_url)

            # Stage 2: Competitor Research
            progress_bar.progress(0.33)

            # Check if user wants to skip competitor research
            if config.get("skip_competitor_research", False):
                status_text.info("**Stage 2/6**: ⏭️ Skipping competitor research (user preference)")
                competitors_result = {
                    "competitors": [],
                    "additional_keywords": [],
                    "market_topics": [],
                    "cost": 0.0
                }
            else:
                status_text.info("**Stage 2/6**: 🔍 Researching competitors using AI web search...")

                # Add progress sub-steps for Stage 2
                import time
                stage2_start = time.time()

                # Try Stage 2 with timeout protection
                try:
                    import asyncio

                    # Set aggressive timeout (30s max for Stage 2)
                    competitors_result = await asyncio.wait_for(
                        orchestrator.research_competitors(
                            keywords_result["keywords"],
                            customer_info
                        ),
                        timeout=30.0  # 30 second timeout
                    )

                    # Show completion time
                    stage2_duration = time.time() - stage2_start
                    status_text.info(f"**Stage 2/6**: ✅ Completed in {stage2_duration:.1f}s")
                except asyncio.TimeoutError:
                    status_text.warning(
                        "⏱️ **Stage 2 Timeout** (30s exceeded) - Skipping competitor research. "
                        "Pipeline will continue with website keywords only. This won't affect topic discovery."
                    )
                    competitors_result = {
                        "competitors": [],
                        "additional_keywords": [],
                        "market_topics": [],
                        "cost": 0.0,
                        "error": "Timeout after 30s"
                    }
                except Exception as e:
                    status_text.warning(
                        f"⚠️ **Stage 2 Failed**: {str(e)[:100]}\n\n"
                        f"Don't worry! Continuing with website keywords only. Topic discovery will still work."
                    )
                    competitors_result = {
                        "competitors": [],
                        "additional_keywords": [],
                        "market_topics": [],
                        "cost": 0.0,
                        "error": str(e)
                    }

                # Handle Stage 2 failure gracefully (e.g., Gemini rate limit)
                if competitors_result.get("error"):
                    # Already showed warning above, just clear the error
                    pass
                    # Use empty competitor data to continue pipeline
                    competitors_result = {
                        "competitors": [],
                        "additional_keywords": [],
                        "market_topics": [],
                        "cost": 0.0
                    }

            # Stage 3: Consolidation
            progress_bar.progress(0.50)
            status_text.info("**Stage 3/6**: 🔗 Merging keywords from website + competitors...")
            consolidated = orchestrator.consolidate_keywords_and_topics(
                keywords_result,
                competitors_result
            )

            # Stage 4: Topic Discovery
            progress_bar.progress(0.67)
            status_text.info("**Stage 4/6**: 💡 Discovering topics from collectors (LLM expansion, autocomplete, trends, Reddit, news)...")
            topics_result = await orchestrator.discover_topics_from_collectors(
                consolidated["consolidated_keywords"],
                consolidated["consolidated_tags"],
                max_topics_per_collector=10,
                domain=config.get("domain", "General"),
                vertical=config.get("vertical", "Research"),
                market=config.get("market", "US"),
                language=config.get("language", "en")
            )

            # Stage 5: Topic Validation
            progress_bar.progress(0.83)
            status_text.info("**Stage 5/6**: ✅ Scoring and filtering topics (saves 60% on research costs)...")
            validation_result = orchestrator.validate_and_score_topics(
                discovered_topics=topics_result["discovered_topics"],
                topics_by_source=topics_result["topics_by_source"],
                consolidated_keywords=consolidated["consolidated_keywords"],
                threshold=0.3,  # Lower threshold to see more topics
                top_n=config["max_topics_to_research"]
            )
            # scored_topics is List[ScoredTopic] - convert to dict format for display
            validated_topics = [
                {
                    "topic": st.topic,
                    "score": st.total_score,
                    "sources": st.metadata.sources if st.metadata.sources else [st.metadata.source]
                }
                for st in validation_result["scored_topics"]
            ]

            # If no topics passed validation, show top raw topics anyway
            if not validated_topics:
                status_text.warning(f"⚠️ **Low-quality topics detected** - Showing top {config['max_topics_to_research']} anyway. Consider adjusting your website or keywords.")
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

            status_text.success(
                f"✅ **Topic Discovery Complete!** ({duration:.1f}s)\n\n"
                f"📊 **Summary**: Analyzed website → Found {len(consolidated['consolidated_keywords'])} keywords → "
                f"Discovered {topics_result['total_topics']} raw topics → Validated {len(validated_topics)} high-quality topics\n\n"
                f"👇 **Next Step**: Select topics below to research (scroll down)"
            )

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
        # Auto-detect topic discovery language/region from content language if not set
        topic_lang = config.get("topic_discovery_language") or config.get("language", "en")
        topic_region = config.get("topic_discovery_region") or {
            "de": "DE", "en": "US", "fr": "FR", "es": "ES", "it": "IT"
        }.get(topic_lang, "US")

        orchestrator = HybridResearchOrchestrator(
            enable_tavily=config["enable_tavily"],
            enable_autocomplete=config.get("enable_autocomplete", True),
            enable_trends=config.get("enable_trends", True),
            enable_rss=config.get("enable_rss", True),
            topic_discovery_language=topic_lang,
            topic_discovery_region=topic_region
        )

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
                generate_images=config.get("enable_images", False)
            )
            articles.append(article)

        progress_bar.progress(1.0)
        status_text.success(f"✅ **Research Complete!** ({total} articles)")

        return articles

    except Exception as e:
        status_text.error(f"❌ **Research Failed**: {str(e)}")
        raise


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
    """Render Pipeline Automation page - 3-Step Wizard."""
    st.title("🎯 Automation Wizard")
    st.caption("3-step guided process: Configure → Discover → Research")

    # Initialize session state
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 1
    if "wizard_config" not in st.session_state:
        st.session_state.wizard_config = load_pipeline_config()
    if "discovered_topics" not in st.session_state:
        st.session_state.discovered_topics = None
    if "selected_topics" not in st.session_state:
        st.session_state.selected_topics = []
    if "researched_articles" not in st.session_state:
        st.session_state.researched_articles = None

    st.divider()

    # Wizard Steps
    current_step = st.session_state.wizard_step
    config = st.session_state.wizard_config

    # ===== STEP 1: Configure & Preview =====
    if current_step == 1:
        wizard_progress_indicator(1, 3)
        st.markdown("## 🌐 Configure & Preview")

        step_explanation(
            title="Configure Your Automation",
            what_well_do=[
                "Analyze your website to extract keywords, themes, and brand tone",
                "Research your competitors and identify market trends",
                "Discover 50+ relevant topics using 5 different collectors",
                "Validate and score topics to find the best ones"
            ],
            why="Understanding your business and market helps us generate highly relevant, targeted content that resonates with your audience."
        )

        st.divider()

        # Configuration Form
        with st.form("wizard_step1_form"):
            st.markdown("### Website & Business Info")

            website_url = st.text_input(
                "Website URL *",
                placeholder="https://your-website.com",
                help="Your business website - we'll analyze it to understand your niche"
            )

            col1, col2 = st.columns(2)
            with col1:
                market = st.text_input(
                    "Market *",
                    value=config.get("market", "Germany"),
                    help="Target market (e.g., Germany, USA, France)"
                )
                vertical = st.text_input(
                    "Vertical *",
                    value=config.get("vertical", "PropTech"),
                    help="Industry vertical (e.g., PropTech, SaaS, Healthcare)"
                )

            with col2:
                domain = st.text_input(
                    "Domain *",
                    value=config.get("domain", "SaaS"),
                    help="Business domain (e.g., SaaS, E-commerce, B2B)"
                )
                language = st.selectbox(
                    "Language *",
                    ["de", "en", "fr", "es"],
                    index=["de", "en", "fr", "es"].index(config.get("language", "de")),
                    help="Content language"
                )

            st.divider()
            st.markdown("### Research Settings")

            col1, col2 = st.columns(2)
            with col1:
                max_topics = st.slider(
                    "Topics to Display",
                    min_value=1,
                    max_value=50,
                    value=config.get("max_topics_to_research", 50),
                    help="Number of topics to display and select from"
                )

            with col2:
                enable_tavily = st.checkbox(
                    "Enable Tavily Fallback",
                    value=config.get("enable_tavily", True),
                    help="Automatic fallback if Gemini rate-limited (+$0.02)"
                )

            enable_images = st.checkbox(
                "Generate images for articles",
                value=config.get("enable_images", False),
                help="Add +$0.076/topic for AI-generated images"
            )

            skip_competitor_research = st.checkbox(
                "Skip competitor research (faster, uses website keywords only)",
                value=config.get("skip_competitor_research", False),
                help="Skip Stage 2 to avoid Gemini API issues. Pipeline will use Stage 1 keywords only."
            )

            # Advanced Topic Discovery Settings
            with st.expander("⚙️ Advanced Topic Discovery Settings", expanded=False):
                st.markdown("**Topic Collectors** (FREE)")
                st.caption("Enable collectors to discover diverse, high-quality topics from multiple sources.")

                col1, col2, col3 = st.columns(3)
                with col1:
                    enable_autocomplete = st.checkbox(
                        "Google Autocomplete (Questions)",
                        value=config.get("enable_autocomplete", True),
                        help="Find questions people actually ask - high value, low noise (FREE)"
                    )

                with col2:
                    enable_trends = st.checkbox(
                        "Google Trends (Trending Topics)",
                        value=config.get("enable_trends", True),
                        help="Discover trending topics and related queries (FREE)"
                    )

                with col3:
                    enable_rss = st.checkbox(
                        "RSS Feeds (News & Blogs)",
                        value=config.get("enable_rss", True),
                        help="Collect topics from 1,037 RSS feeds + dynamic news feeds (FREE)"
                    )

                st.divider()
                st.markdown("**Topic Discovery Region & Language**")
                st.caption("Configure language and region for autocomplete and trends collectors.")

                col1, col2 = st.columns(2)
                with col1:
                    topic_discovery_language = st.selectbox(
                        "Discovery Language",
                        ["en", "de", "fr", "es", "it"],
                        index=["en", "de", "fr", "es", "it"].index(config.get("topic_discovery_language", "en")),
                        help="Language for topic discovery (autocomplete, trends)"
                    )

                with col2:
                    topic_discovery_region = st.selectbox(
                        "Discovery Region",
                        ["US", "DE", "GB", "FR", "ES", "IT"],
                        index=["US", "DE", "GB", "FR", "ES", "IT"].index(config.get("topic_discovery_region", "US")),
                        help="Region for trend data (2-letter country code)"
                    )

            st.divider()

            # Cost Preview
            cost_preview(max_topics, enable_images, enable_tavily)

            # Submit button
            submitted = st.form_submit_button(
                "✅ Start Topic Discovery",
                type="primary",
                use_container_width=True
            )

            if submitted:
                if not website_url:
                    st.error("❌ Please enter a website URL")
                elif not market or not vertical or not domain:
                    st.error("❌ Please fill in all required fields")
                else:
                    # Save config
                    st.session_state.wizard_config = {
                        "website_url": website_url,
                        "market": market,
                        "vertical": vertical,
                        "domain": domain,
                        "language": language,
                        "max_topics_to_research": max_topics,
                        "enable_tavily": enable_tavily,
                        "enable_images": enable_images,
                        "skip_competitor_research": skip_competitor_research,
                        # Topic discovery collectors
                        "enable_autocomplete": enable_autocomplete,
                        "enable_trends": enable_trends,
                        "enable_rss": enable_rss,
                        "topic_discovery_language": topic_discovery_language,
                        "topic_discovery_region": topic_discovery_region
                    }
                    save_pipeline_config(st.session_state.wizard_config)
                    st.session_state.wizard_step = 2
                    st.rerun()

    # ===== STEP 2: Discover Topics =====
    elif current_step == 2:
        wizard_progress_indicator(2, 3)
        st.markdown("## 🔍 Discover Topics")

        step_explanation(
            title="Topic Discovery Process",
            what_well_do=[
                "Extract keywords from your website (Stage 1 - FREE)",
                "Research competitors and market trends (Stage 2 - FREE)",
                "Consolidate and deduplicate keywords (Stage 3 - FREE)",
                "Discover sources with AI (Stage 3.5 - FREE): Suggest relevant subreddits, RSS feeds, topic angles",
                "Collect from dynamic sources (Stage 4 - FREE): LLM expansion, autocomplete, trends, Reddit, news",
                "Validate and score topics (Stage 5 - FREE)"
            ],
            why="This FREE discovery process uses AI to find relevant sources and generates 50+ diverse topic candidates before spending on research, saving you 60% on costs."
        )

        st.divider()

        # Show configuration summary
        st.markdown("### 📋 Configuration")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"**Website**: {config.get('website_url', 'N/A')}")
            st.caption(f"**Market**: {config.get('market', 'N/A')}")
        with col2:
            st.caption(f"**Vertical**: {config.get('vertical', 'N/A')}")
            st.caption(f"**Domain**: {config.get('domain', 'N/A')}")
        with col3:
            st.caption(f"**Language**: {config.get('language', 'N/A')}")
            st.caption(f"**Max Topics**: {config.get('max_topics_to_research', 10)}")

        st.divider()

        # Run discovery if not already done
        if st.session_state.discovered_topics is None:
            if st.button("🚀 Run Topic Discovery (FREE)", type="primary", use_container_width=True):
                # Check API keys
                required_keys = ["GEMINI_API_KEY"]
                if config.get("enable_tavily", True):
                    required_keys.append("TAVILY_API_KEY")

                missing_keys = [key for key in required_keys if not os.getenv(key)]
                if missing_keys:
                    st.error(f"❌ Missing API keys: {', '.join(missing_keys)}")
                    st.info("💡 Add these keys to your .env file to continue")
                else:
                    progress_container = st.container()

                    try:
                        result = asyncio.run(
                            run_pipeline_async(
                                config["website_url"],
                                config,
                                progress_container,
                                run_full_pipeline=False  # Discovery only
                            )
                        )
                        st.session_state.discovered_topics = result.get("topics", [])
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Discovery failed: {str(e)}")
                        st.exception(e)
        else:
            # Show discovered topics
            st.success(f"✅ **Topic Discovery Complete!** Found {len(st.session_state.discovered_topics)} high-quality topics")

            st.markdown("---")
            st.markdown("## 📋 Select Topics to Research")
            st.info(
                f"👇 **Action Required**: Check the boxes below to select topics for deep research.\n\n"
                f"💰 **Cost**: $0.01 per topic (FREE discovery already done!)\n\n"
                f"📊 **Max**: {config.get('max_topics_to_research', 10)} topics"
            )
            st.markdown("---")

            # Topic selection
            selected_topics = []
            for i, topic_data in enumerate(st.session_state.discovered_topics):
                col1, col2, col3 = st.columns([1, 8, 2])

                with col1:
                    selected = st.checkbox("", key=f"topic_select_{i}", value=False)
                    if selected:
                        selected_topics.append(topic_data)

                with col2:
                    # Display topic with source badges
                    sources = topic_data.get("sources", [])
                    if sources:
                        # Create source badges with emoji icons
                        source_icons = {
                            "llm": "🤖",
                            "reddit": "🔴",
                            "trends": "📈",
                            "autocomplete": "🔍",
                            "keywords": "🔑",
                            "tags": "🏷️",
                            "news": "📰",
                            "rss": "📡"
                        }
                        badges = " ".join([
                            f"{source_icons.get(s.lower(), '•')} {s}"
                            for s in sources[:3]  # Show max 3 sources
                        ])
                        st.markdown(f"**{topic_data['topic']}**  \n`{badges}`")
                    else:
                        st.text(topic_data["topic"])

                with col3:
                    score = topic_data.get("score", 0.0)
                    if score > 0:
                        st.caption(f"Score: {score:.2f}")
                    else:
                        st.caption("Raw")

            st.divider()

            # Action buttons
            col1, col2 = st.columns([2, 1])

            with col1:
                if len(selected_topics) > 0:
                    research_cost = len(selected_topics) * 0.01
                    if config.get("enable_images"):
                        research_cost += len(selected_topics) * 0.076

                    if st.button(
                        f"🔬 Research {len(selected_topics)} Topics (${research_cost:.2f})",
                        type="primary",
                        use_container_width=True
                    ):
                        st.session_state.selected_topics = selected_topics
                        st.session_state.wizard_step = 3
                        st.rerun()
                else:
                    st.button(
                        "🔬 Research Selected Topics",
                        type="primary",
                        use_container_width=True,
                        disabled=True,
                        help="Select at least one topic to continue"
                    )

            with col2:
                if st.button("← Back to Config", use_container_width=True):
                    st.session_state.wizard_step = 1
                    st.rerun()

    # ===== STEP 3: Research & Generate =====
    elif current_step == 3:
        wizard_progress_indicator(3, 3)
        st.markdown("## 🔬 Research & Generate")

        step_explanation(
            title="Deep Research Process",
            what_well_do=[
                "Search 5+ sources for each topic (Tavily, SearXNG, Gemini, RSS, News)",
                "Rank and rerank results using advanced algorithms",
                "Extract key passages using BM25 + LLM",
                "Generate 1500+ word articles with inline citations",
                "Create AI images if enabled (hero + supporting)"
            ],
            why="Deep research ensures your content is accurate, comprehensive, and backed by credible sources."
        )

        st.divider()

        # Show selected topics summary
        st.markdown("### 📋 Selected Topics")
        for i, topic in enumerate(st.session_state.selected_topics, 1):
            st.caption(f"{i}. {topic['topic']}")

        research_cost = len(st.session_state.selected_topics) * 0.01
        if config.get("enable_images"):
            research_cost += len(st.session_state.selected_topics) * 0.076

        st.metric("Total Research Cost", f"${research_cost:.2f}")

        st.divider()

        # Run research if not already done
        if st.session_state.researched_articles is None:
            if st.button("🚀 Start Deep Research", type="primary", use_container_width=True):
                progress_container = st.container()

                try:
                    articles = asyncio.run(
                        research_selected_topics_async(
                            st.session_state.selected_topics,
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
            # Show researched articles
            st.success(f"✅ Research Complete! Generated {len(st.session_state.researched_articles)} articles")

            st.divider()
            render_articles(st.session_state.researched_articles, config)

            st.divider()

            # Navigation buttons
            col1, col2 = st.columns(2)

            with col1:
                if st.button("🔄 Start Over", use_container_width=True):
                    # Reset wizard
                    st.session_state.wizard_step = 1
                    st.session_state.discovered_topics = None
                    st.session_state.selected_topics = []
                    st.session_state.researched_articles = None
                    st.rerun()

            with col2:
                if st.button("← Back to Topics", use_container_width=True):
                    st.session_state.wizard_step = 2
                    st.session_state.researched_articles = None
                    st.rerun()
