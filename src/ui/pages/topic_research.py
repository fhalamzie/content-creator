"""
Topic Research Page - Production Pipeline UI

Process topics through the production-ready pipeline:
1. Multi-Backend Research (Tavily + SearXNG + Gemini + RSS + TheNewsAPI)
2. 3-Stage Reranking (BM25 → Voyage Lite → Voyage Full)
3. Content Synthesis (BM25→LLM passage extraction → 2000-word article)

Features:
- Real-time progress tracking
- Cost estimation and tracking
- Source diversity visualization
- Backend reliability monitoring
"""

import streamlit as st
from pathlib import Path
import json
import os
import asyncio
from datetime import datetime
from typing import Dict, List
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import production pipeline components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.research.deep_researcher_refactored import DeepResearcher
from src.research.reranker.multi_stage_reranker import MultiStageReranker
from src.research.synthesizer.content_synthesizer import (
    ContentSynthesizer,
    PassageExtractionStrategy
)
from src.utils.config_loader import ConfigLoader


CACHE_DIR = Path(__file__).parent.parent.parent.parent / "cache"
CONFIG_FILE = CACHE_DIR / "topic_research_config.json"


def load_research_config():
    """Load topic research configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "market": "proptech_de",
        "enable_tavily": True,
        "enable_searxng": True,
        "enable_gemini": True,
        "enable_rss": False,
        "enable_thenewsapi": False,
        "enable_reranking": True,
        "enable_synthesis": True,
        "max_article_words": 2000,
        "synthesis_strategy": "bm25_llm"
    }


def save_research_config(config: dict):
    """Save topic research configuration."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def render_config_sidebar():
    """Render configuration sidebar."""
    with st.sidebar:
        st.header("⚙️ Pipeline Configuration")

        config = load_research_config()

        # Market config
        st.subheader("📍 Market Config")
        market_preset = st.selectbox(
            "Market Preset",
            ["proptech_de", "fashion_fr", "saas_us", "custom"],
            index=0 if config.get("market") == "proptech_de" else 3,
            help="Load predefined market configuration"
        )

        # Backend configuration
        st.subheader("🔍 Research Backends")
        enable_tavily = st.checkbox(
            "Tavily (DEPTH)",
            value=config.get("enable_tavily", True),
            help="Deep, comprehensive search results"
        )
        enable_searxng = st.checkbox(
            "SearXNG (BREADTH)",
            value=config.get("enable_searxng", True),
            help="Wide coverage across multiple sources"
        )
        enable_gemini = st.checkbox(
            "Gemini API (TRENDS)",
            value=config.get("enable_gemini", True),
            help="Google Search grounding for trending content"
        )
        enable_rss = st.checkbox(
            "RSS Feeds (NICHE)",
            value=config.get("enable_rss", False),
            help="Industry-specific RSS feeds"
        )
        enable_thenewsapi = st.checkbox(
            "TheNewsAPI (NEWS)",
            value=config.get("enable_thenewsapi", False),
            help="Real-time news coverage"
        )

        # Pipeline stages
        st.subheader("🎯 Pipeline Stages")
        enable_reranking = st.checkbox(
            "Enable Reranking",
            value=config.get("enable_reranking", True),
            help="3-stage reranker (BM25 → Voyage Lite → Voyage Full)"
        )
        enable_synthesis = st.checkbox(
            "Enable Content Synthesis",
            value=config.get("enable_synthesis", True),
            help="Generate 2000-word article with citations"
        )

        # Synthesis settings
        if enable_synthesis:
            st.subheader("📝 Synthesis Settings")
            max_article_words = st.slider(
                "Max Article Words",
                min_value=500,
                max_value=3000,
                value=config.get("max_article_words", 2000),
                step=500
            )
            synthesis_strategy = st.selectbox(
                "Strategy",
                ["bm25_llm", "llm_only"],
                index=0 if config.get("synthesis_strategy") == "bm25_llm" else 1,
                help="BM25→LLM: fast, cheap (92% quality) | LLM-only: slower, expensive (94% quality)"
            )
        else:
            max_article_words = 2000
            synthesis_strategy = "bm25_llm"

        if st.button("💾 Save Configuration", use_container_width=True):
            new_config = {
                "market": market_preset,
                "enable_tavily": enable_tavily,
                "enable_searxng": enable_searxng,
                "enable_gemini": enable_gemini,
                "enable_rss": enable_rss,
                "enable_thenewsapi": enable_thenewsapi,
                "enable_reranking": enable_reranking,
                "enable_synthesis": enable_synthesis,
                "max_article_words": max_article_words,
                "synthesis_strategy": synthesis_strategy
            }
            save_research_config(new_config)
            st.success("✅ Configuration saved!")
            st.rerun()

        st.divider()

        # Cost estimation
        st.caption("💰 **Cost Estimation**")
        enabled_backends = sum([enable_tavily, enable_searxng, enable_gemini, enable_rss, enable_thenewsapi])
        base_cost = 0.005 * enabled_backends  # ~$0.005 per backend
        reranking_cost = 0.002 if enable_reranking else 0
        synthesis_cost = 0.003 if enable_synthesis else 0
        total_cost = base_cost + reranking_cost + synthesis_cost
        st.caption(f"• Estimated: ${total_cost:.4f}/topic")
        st.caption(f"• {enabled_backends} backend{'s' if enabled_backends != 1 else ''} enabled")

        return config


async def process_topic_async(
    topic: str,
    config: dict,
    progress_container
) -> Dict:
    """Process topic through production pipeline with real-time updates."""

    # Progress tracking
    progress_bar = progress_container.progress(0.0)
    status_text = progress_container.empty()
    metrics_container = progress_container.container()

    start_time = datetime.now()
    total_cost = 0.0

    try:
        # Load market config
        config_loader = ConfigLoader()
        if config["market"] == "custom":
            market_config = {"market": "USA", "language": "en", "domain": "SaaS"}
        else:
            market_config = config_loader.load(config["market"])

        # Stage 1: Initialize components
        progress_bar.progress(0.1)
        status_text.info("🔧 **Stage 1/4**: Initializing pipeline components...")

        researcher = DeepResearcher(
            enable_tavily=config["enable_tavily"],
            enable_searxng=config["enable_searxng"],
            enable_gemini=config["enable_gemini"],
            enable_rss=config["enable_rss"],
            enable_thenewsapi=config["enable_thenewsapi"]
        )

        reranker = MultiStageReranker(
            enable_voyage=config["enable_reranking"],
            stage3_final_count=25
        ) if config["enable_reranking"] else None

        synthesizer = ContentSynthesizer(
            strategy=PassageExtractionStrategy.BM25_LLM if config["synthesis_strategy"] == "bm25_llm" else PassageExtractionStrategy.LLM_ONLY,
            max_article_words=config["max_article_words"]
        ) if config["enable_synthesis"] else None

        # Stage 2: Research
        progress_bar.progress(0.25)
        status_text.info(f"🔍 **Stage 2/4**: Researching topic across {sum([config['enable_tavily'], config['enable_searxng'], config['enable_gemini'], config['enable_rss'], config['enable_thenewsapi']])} backends...")

        results = await researcher.search(topic, max_results=10)
        backend_counts = defaultdict(int)
        for result in results:
            backend_counts[result.get('backend', 'unknown')] += 1

        with metrics_container:
            cols = st.columns(4)
            cols[0].metric("Sources Found", len(results))
            cols[1].metric("Backends Used", len(backend_counts))
            cols[2].metric("Tavily", backend_counts.get('tavily', 0))
            cols[3].metric("Gemini", backend_counts.get('gemini', 0))

        # Stage 3: Reranking
        if reranker and results:
            progress_bar.progress(0.5)
            status_text.info("🎯 **Stage 3/4**: Reranking sources (BM25 → Voyage Lite → Voyage Full)...")

            reranked = await reranker.rerank(
                query=topic,
                sources=results,
                config=market_config
            )

            with metrics_container:
                st.info(f"✅ Reranking complete: {len(results)} → {len(reranked)} sources")
                if reranked:
                    st.caption(f"Top score: {reranked[0].get('score', 0):.3f}")

            results = reranked

        # Stage 4: Content Synthesis
        article = None
        if synthesizer and results:
            progress_bar.progress(0.75)
            status_text.info("📝 **Stage 4/4**: Synthesizing article with citations...")

            synthesis_result = await synthesizer.synthesize(
                query=topic,
                sources=results,
                config=market_config
            )

            article = synthesis_result["article"]
            total_cost += synthesis_result.get("cost", 0)

            with metrics_container:
                st.success(f"✅ Article generated: {synthesis_result.get('word_count', 0)} words, {len(synthesis_result.get('citations', []))} citations")

        # Complete
        progress_bar.progress(1.0)
        duration = (datetime.now() - start_time).total_seconds()
        status_text.success(f"✅ **Processing Complete!** ({duration:.1f}s, ${total_cost:.4f})")

        return {
            "success": True,
            "topic": topic,
            "sources": results,
            "article": article,
            "cost": total_cost,
            "duration_sec": duration,
            "backend_counts": dict(backend_counts)
        }

    except Exception as e:
        progress_bar.progress(0.0)
        status_text.error(f"❌ **Pipeline Failed**: {str(e)}")
        raise


def render_results(result: Dict):
    """Render pipeline results."""
    st.success(f"✅ Topic processed: **{result['topic']}**")

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sources", len(result['sources']))
    col2.metric("Total Cost", f"${result['cost']:.4f}")
    col3.metric("Duration", f"{result['duration_sec']:.1f}s")
    col4.metric("Backends", len(result['backend_counts']))

    # Tabs for different views
    tabs = st.tabs(["📝 Article", "📊 Sources", "📈 Analytics", "🔍 Raw Data"])

    with tabs[0]:
        st.subheader("Generated Article")
        if result.get('article'):
            st.markdown(result['article'])
        else:
            st.info("Content synthesis was disabled")

    with tabs[1]:
        st.subheader("Top Sources")
        for i, source in enumerate(result['sources'][:10], 1):
            with st.expander(f"{i}. {source.get('title', 'Untitled')[:80]}"):
                st.caption(f"**Backend**: {source.get('backend', 'unknown')}")
                st.caption(f"**URL**: {source.get('url', 'N/A')}")
                if 'score' in source:
                    st.caption(f"**Score**: {source['score']:.3f}")
                if 'snippet' in source:
                    st.text(source['snippet'][:200] + "...")

    with tabs[2]:
        st.subheader("Backend Distribution")

        # Backend breakdown
        backend_data = result['backend_counts']
        if backend_data:
            import pandas as pd
            df = pd.DataFrame(list(backend_data.items()), columns=['Backend', 'Count'])
            st.bar_chart(df.set_index('Backend'))

        # Cost breakdown
        st.subheader("Cost Breakdown")
        st.caption(f"• Total: ${result['cost']:.4f}")
        st.caption(f"• Per source: ${result['cost'] / max(len(result['sources']), 1):.5f}")

    with tabs[3]:
        st.subheader("Raw Result Data")
        st.json({
            "topic": result['topic'],
            "sources_count": len(result['sources']),
            "has_article": result.get('article') is not None,
            "cost": result['cost'],
            "duration_sec": result['duration_sec'],
            "backend_counts": result['backend_counts']
        })


def render():
    """Render Topic Research page."""
    st.title("🔬 Topic Research Lab")
    st.caption("Production-ready pipeline with 5 backends, 3-stage reranking, and content synthesis")

    # Render config sidebar
    config = render_config_sidebar()

    # Initialize session state
    if "research_result" not in st.session_state:
        st.session_state.research_result = None

    # Main content
    st.header("🎯 Research a Topic")

    # Topic input
    topic = st.text_input(
        "Enter your research topic",
        placeholder="e.g., PropTech AI automation trends 2025",
        help="The system will research this topic across multiple backends"
    )

    # Quick examples
    with st.expander("💡 Example Topics"):
        st.caption("**PropTech**: Smart building IoT sensors Germany, DSGVO compliance property management")
        st.caption("**SaaS**: B2B pricing strategies 2025, Customer success platforms")
        st.caption("**Fashion**: Sustainable fashion e-commerce, AI styling recommendations")

    # Process button
    process_button = st.button("🚀 Research Topic", type="primary", use_container_width=True, disabled=not topic)

    if process_button and topic:
        # Check API keys
        required_keys = []
        if config["enable_tavily"]:
            required_keys.append("TAVILY_API_KEY")
        if config["enable_gemini"]:
            required_keys.append("GEMINI_API_KEY")
        if config["enable_reranking"]:
            required_keys.append("VOYAGE_API_KEY")

        missing_keys = [key for key in required_keys if not os.getenv(key)]
        if missing_keys:
            st.error(f"❌ Missing API keys: {', '.join(missing_keys)}")
            return

        # Process topic
        st.divider()
        st.header("⚙️ Pipeline Processing")
        progress_container = st.container()

        try:
            # Run async processing
            result = asyncio.run(
                process_topic_async(topic, config, progress_container)
            )

            # Store in session state
            st.session_state.research_result = result

        except Exception as e:
            st.error(f"❌ Pipeline failed: {str(e)}")
            st.exception(e)

    # Display results if available
    if st.session_state.research_result:
        st.divider()
        st.header("📊 Results")

        render_results(st.session_state.research_result)

        # Clear results button
        if st.button("🗑️ Clear Results", use_container_width=True):
            st.session_state.research_result = None
            st.rerun()
