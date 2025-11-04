"""
Topic Research Page - ContentPipeline UI Integration

Process discovered topics through the 5-stage ContentPipeline:
1. Competitor Research (identify gaps)
2. Keyword Research (find SEO opportunities)
3. Deep Research (generate sourced reports)
4. Content Optimization (apply insights)
5. Scoring & Ranking (calculate priority scores)
"""

import streamlit as st
from pathlib import Path
import json
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()  # Load local .env first
load_dotenv("/home/envs/openrouter.env")  # Override with openrouter env

# Import agents and pipeline
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.content_pipeline import ContentPipeline
from src.agents.competitor_research_agent import CompetitorResearchAgent
from src.agents.keyword_research_agent import KeywordResearchAgent
from src.research.deep_researcher import DeepResearcher
from src.models.topic import Topic, TopicSource
from src.models.config import MarketConfig
from src.notion_integration.topics_sync import TopicsSync
from src.notion_integration.notion_client import NotionClient


CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "topic_research_config.json"


def load_research_config():
    """Load topic research configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "domain": "SaaS",
        "market": "Germany",
        "language": "de",
        "vertical": "Proptech",
        "seed_keywords": ["DSGVO", "Immobilien SaaS"]
    }


def save_research_config(config: dict):
    """Save topic research configuration."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def render_config_sidebar():
    """Render configuration sidebar."""
    with st.sidebar:
        st.header("📝 Research Configuration")

        config = load_research_config()

        domain = st.text_input("Domain", value=config.get("domain", "SaaS"))
        market = st.text_input("Market", value=config.get("market", "Germany"))
        language = st.text_input("Language Code", value=config.get("language", "de"))
        vertical = st.text_input("Vertical (Optional)", value=config.get("vertical", ""))
        target_audience = st.text_input("Target Audience (Optional)", value=config.get("target_audience", ""))

        seed_keywords_str = st.text_area(
            "Seed Keywords (one per line)",
            value="\n".join(config.get("seed_keywords", []))
        )
        seed_keywords = [k.strip() for k in seed_keywords_str.split("\n") if k.strip()]

        if st.button("💾 Save Configuration", use_container_width=True):
            new_config = {
                "domain": domain,
                "market": market,
                "language": language,
                "vertical": vertical if vertical else None,
                "target_audience": target_audience if target_audience else None,
                "seed_keywords": seed_keywords
            }
            save_research_config(new_config)
            st.success("✅ Configuration saved!")
            st.rerun()

        st.divider()

        st.caption("💡 **Configuration Guide**")
        st.caption("• **Domain**: Business type (SaaS, E-commerce)")
        st.caption("• **Market**: Target country")
        st.caption("• **Language**: Content language (de, en, fr)")
        st.caption("• **Vertical**: Optional niche (Proptech, Fashion)")

        return config


async def process_topic_async(
    topic: Topic,
    config: MarketConfig,
    pipeline: ContentPipeline,
    progress_container
):
    """Process topic through pipeline with real-time updates."""

    # Progress tracking
    progress_bar = progress_container.progress(0.0)
    status_text = progress_container.empty()
    stage_details = progress_container.empty()

    def progress_callback(stage: int, message: str):
        """Update progress UI."""
        progress = stage / 5.0
        progress_bar.progress(progress)
        status_text.info(f"**Stage {stage}/5**: {message}")

        # Stage details
        stage_info = {
            1: "🔎 Analyzing competitors and identifying content gaps",
            2: "🎯 Researching SEO keywords and search volume",
            3: "📚 Generating deep research report with citations",
            4: "✨ Optimizing content with insights and metadata",
            5: "📊 Calculating priority scores (demand, opportunity, fit, novelty)"
        }
        stage_details.info(stage_info.get(stage, "Processing..."))

    # Process topic
    enhanced_topic = await pipeline.process_topic(
        topic=topic,
        config=config,
        progress_callback=progress_callback
    )

    progress_bar.progress(1.0)
    status_text.success("✅ **Processing Complete!**")
    stage_details.empty()

    return enhanced_topic


def render_topic_results(topic: Topic):
    """Render enhanced topic results."""
    st.success(f"✅ Topic processed: **{topic.title}**")

    # Tabs for different result views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📚 Research Report", "🎯 Details", "📈 Scores"])

    with tab1:
        st.subheader("Topic Overview")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Status", topic.status.value)
            st.metric("Priority", f"{topic.priority}/10")

        with col2:
            st.metric("Language", topic.language.upper())
            st.metric("Domain", topic.domain)

        with col3:
            st.metric("Word Count", topic.word_count or 0)
            st.metric("Citations", len(topic.citations))

        if topic.description:
            st.info(f"**Description**: {topic.description}")

    with tab2:
        st.subheader("Deep Research Report")

        if topic.research_report:
            st.markdown(topic.research_report)

            if topic.citations:
                st.divider()
                st.subheader("📎 Citations")
                for i, citation in enumerate(topic.citations, 1):
                    st.caption(f"{i}. {citation}")
        else:
            st.warning("No research report available. Deep research may have been disabled.")

    with tab3:
        st.subheader("Topic Details")

        st.json({
            "id": topic.id,
            "title": topic.title,
            "source": topic.source.value,
            "domain": topic.domain,
            "market": topic.market,
            "language": topic.language,
            "vertical": getattr(topic, "vertical", None),
            "status": topic.status.value,
            "priority": topic.priority,
            "engagement_score": topic.engagement_score,
            "trending_score": topic.trending_score,
            "word_count": topic.word_count,
            "citations_count": len(topic.citations),
            "discovered_at": topic.discovered_at.isoformat(),
            "updated_at": topic.updated_at.isoformat()
        })

    with tab4:
        st.subheader("Priority Scores")

        st.info("**Note**: Detailed scores will be available once Topic model includes score fields (Phase 2)")

        # Show priority mapping
        priority = topic.priority
        if priority >= 9:
            score_label = "🔥 Very High Priority"
            score_color = "green"
        elif priority >= 7:
            score_label = "⬆️ High Priority"
            score_color = "blue"
        elif priority >= 5:
            score_label = "➡️ Medium Priority"
            score_color = "orange"
        else:
            score_label = "⬇️ Low Priority"
            score_color = "red"

        st.markdown(f"**Priority Level**: :{score_color}[{score_label}]")

        st.caption("Priority is calculated from: demand (search volume + engagement), opportunity (competition + gaps), fit (domain alignment), and novelty (trending)")


async def sync_to_notion_async(topic: Topic, notion_client: NotionClient):
    """Sync enhanced topic to Notion."""
    topics_sync = TopicsSync(notion_client=notion_client)

    # Sync single topic
    results = topics_sync.sync_topics(
        topics=[topic],
        update_existing=True,
        skip_errors=False
    )

    return results


def render():
    """Render Topic Research page."""
    st.title("🔬 Topic Research Lab")
    st.caption("Process topics through the 5-stage ContentPipeline")

    # Render config sidebar
    config_dict = render_config_sidebar()

    # Initialize session state
    if "processed_topic" not in st.session_state:
        st.session_state.processed_topic = None

    # Main content
    st.header("🎯 Topic Input")

    # Topic input method
    input_method = st.radio(
        "Choose input method:",
        ["Manual Entry", "Load from Collectors"],
        horizontal=True
    )

    if input_method == "Manual Entry":
        topic_title = st.text_input(
            "Topic Title",
            placeholder="e.g., PropTech Trends 2025",
            help="Enter the topic you want to research"
        )

        col1, col2 = st.columns(2)

        with col1:
            topic_source = st.selectbox(
                "Source",
                ["trends", "rss", "reddit", "autocomplete", "manual"]
            )

        with col2:
            engagement_score = st.slider(
                "Engagement Score",
                min_value=0,
                max_value=100,
                value=50,
                help="Estimated engagement (likes, shares, comments)"
            )

        trending_score = st.slider(
            "Trending Score",
            min_value=0.0,
            max_value=100.0,
            value=50.0,
            help="How trending is this topic?"
        )

        process_button = st.button("🚀 Process Topic", type="primary", use_container_width=True)

        if process_button and topic_title:
            # Create topic object
            topic = Topic(
                title=topic_title,
                source=TopicSource(topic_source),
                domain=config_dict["domain"],
                market=config_dict["market"],
                language=config_dict["language"],
                engagement_score=engagement_score,
                trending_score=trending_score
            )

            # Create market config
            market_config = MarketConfig(
                domain=config_dict["domain"],
                market=config_dict["market"],
                language=config_dict["language"],
                vertical=config_dict.get("vertical"),
                target_audience=config_dict.get("target_audience"),
                seed_keywords=config_dict["seed_keywords"]
            )

            # Get API key
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                st.error("❌ OPENROUTER_API_KEY not found in environment")
                return

            # Initialize pipeline
            with st.spinner("Initializing pipeline..."):
                # Enable Gemini CLI (FREE Google Search) with stdin fix applied
                # Falls back to OpenRouter API if CLI fails
                competitor_agent = CompetitorResearchAgent(api_key=api_key, use_cli=True)
                keyword_agent = KeywordResearchAgent(api_key=api_key, use_cli=True)
                deep_researcher = DeepResearcher()

                pipeline = ContentPipeline(
                    competitor_agent=competitor_agent,
                    keyword_agent=keyword_agent,
                    deep_researcher=deep_researcher,
                    max_competitors=5,
                    max_keywords=10
                )

            # Process topic
            st.header("⚙️ Processing Pipeline")
            progress_container = st.container()

            try:
                # Run async processing
                enhanced_topic = asyncio.run(
                    process_topic_async(topic, market_config, pipeline, progress_container)
                )

                # Store in session state
                st.session_state.processed_topic = enhanced_topic

                st.success("✅ Topic processing complete!")

            except Exception as e:
                st.error(f"❌ Pipeline failed: {str(e)}")
                st.exception(e)

    else:  # Load from Collectors
        st.info("🚧 Collector integration coming soon!")
        st.caption("This will allow you to load topics from RSS, Reddit, Trends, and Autocomplete collectors.")

    # Display results if available
    if st.session_state.processed_topic:
        st.divider()
        st.header("📊 Enhanced Topic Results")

        render_topic_results(st.session_state.processed_topic)

        # Notion sync section
        st.divider()
        st.header("📤 Sync to Notion")

        notion_token = os.getenv("NOTION_TOKEN")
        if notion_token:
            col1, col2 = st.columns([3, 1])

            with col1:
                st.info("📝 Ready to sync enhanced topic to Notion database")

            with col2:
                if st.button("🔄 Sync to Notion", use_container_width=True):
                    with st.spinner("Syncing to Notion..."):
                        try:
                            notion_client = NotionClient(token=notion_token)

                            results = asyncio.run(
                                sync_to_notion_async(st.session_state.processed_topic, notion_client)
                            )

                            if results["success_count"] > 0:
                                st.success(f"✅ Synced {results['success_count']} topic to Notion!")
                            else:
                                st.error(f"❌ Sync failed: {results['error_count']} errors")

                        except Exception as e:
                            st.error(f"❌ Notion sync failed: {str(e)}")
        else:
            st.warning("⚠️ NOTION_TOKEN not found in environment. Cannot sync to Notion.")

        # Clear results button
        if st.button("🗑️ Clear Results", use_container_width=True):
            st.session_state.processed_topic = None
            st.rerun()
