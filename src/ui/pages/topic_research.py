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


def get_opportunity_badge(score: float) -> str:
    """
    Get color-coded badge for opportunity score.

    Args:
        score: Opportunity score (0-100)

    Returns:
        Formatted badge string with emoji
    """
    if score >= 70:
        return f"🟢 {score:.0f}/100"
    elif score >= 40:
        return f"🟡 {score:.0f}/100"
    else:
        return f"🔴 {score:.0f}/100"


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
        "synthesis_strategy": "bm25_llm",
        "enable_images": False
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

            # Image generation settings
            st.subheader("🖼️ Image Generation")
            enable_images = st.checkbox(
                "Generate images (1 HD hero + 2 supporting)",
                value=config.get("enable_images", False),
                help="DALL-E 3: $0.16/topic (1 HD hero $0.08 + 2 standard supporting $0.08)"
            )
        else:
            max_article_words = 2000
            synthesis_strategy = "bm25_llm"
            enable_images = False

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
                "synthesis_strategy": synthesis_strategy,
                "enable_images": enable_images
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
        images_cost = 0.16 if enable_images else 0  # $0.16/topic (1 HD hero + 2 standard supporting)
        total_cost = base_cost + reranking_cost + synthesis_cost + images_cost
        st.caption(f"• Estimated: ${total_cost:.4f}/topic")
        st.caption(f"• {enabled_backends} backend{'s' if enabled_backends != 1 else ''} enabled")
        if enable_images:
            st.caption(f"• Images: +${images_cost:.2f}/topic")

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

        print("[DEBUG] Stage 1 START - Initializing DeepResearcher...")
        import sys
        sys.stdout.flush()

        researcher = DeepResearcher(
            enable_tavily=config["enable_tavily"],
            enable_searxng=config["enable_searxng"],
            enable_gemini=config["enable_gemini"],
            enable_rss=config["enable_rss"],
            enable_thenewsapi=config["enable_thenewsapi"]
        )

        print("[DEBUG] DeepResearcher initialized, initializing Reranker...")
        sys.stdout.flush()

        reranker = MultiStageReranker(
            enable_voyage=config["enable_reranking"],
            stage3_final_count=25
        ) if config["enable_reranking"] else None

        print("[DEBUG] Reranker initialized, initializing ContentSynthesizer...")
        sys.stdout.flush()

        synthesizer = ContentSynthesizer(
            strategy=PassageExtractionStrategy.BM25_LLM if config["synthesis_strategy"] == "bm25_llm" else PassageExtractionStrategy.LLM_ONLY,
            max_article_words=config["max_article_words"]
        ) if config["enable_synthesis"] else None

        print("[DEBUG] Stage 1 COMPLETE - All components initialized")
        sys.stdout.flush()

        # Stage 2: Research
        progress_bar.progress(0.25)
        status_text.info(f"🔍 **Stage 2/4**: Researching topic across {sum([config['enable_tavily'], config['enable_searxng'], config['enable_gemini'], config['enable_rss'], config['enable_thenewsapi']])} backends...")

        # Build config dict for researcher
        research_config = {
            "market": market_config.get("market", "Germany"),
            "vertical": market_config.get("vertical", "General"),
            "domain": market_config.get("domain", "General"),
            "language": market_config.get("language", "en")
        }

        print(f"[DEBUG] About to call researcher.research_topic with config: {research_config}")
        import sys
        sys.stdout.flush()

        research_result = await researcher.research_topic(topic=topic, config=research_config)

        print(f"[DEBUG] research_topic completed, got {len(research_result.get('sources', []))} sources")
        sys.stdout.flush()

        results = research_result.get("sources", [])
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
        hero_image_url = None
        hero_image_alt = None
        supporting_images = []
        image_cost = 0.0

        if synthesizer and results:
            progress_bar.progress(0.75)
            status_text.info("📝 **Stage 4/4**: Synthesizing article with citations...")

            # Extract brand tone from market config or use default
            brand_tone = market_config.market.brand_tone if hasattr(market_config, 'market') and hasattr(market_config.market, 'brand_tone') else ["Professional"]

            synthesis_result = await synthesizer.synthesize(
                query=topic,
                sources=results,
                config=market_config,
                brand_tone=brand_tone,
                generate_images=config.get("enable_images", False)
            )

            article = synthesis_result["article"]
            total_cost += synthesis_result.get("cost", 0)

            # Extract image data
            hero_image_url = synthesis_result.get("hero_image_url")
            hero_image_alt = synthesis_result.get("hero_image_alt")
            supporting_images = synthesis_result.get("supporting_images", [])
            image_cost = synthesis_result.get("image_cost", 0.0)
            total_cost += image_cost

            with metrics_container:
                word_count = len(article.split()) if article else 0
                st.success(f"✅ Article generated: {word_count} words, {len(synthesis_result.get('citations', []))} citations")
                if config.get("enable_images", False):
                    images_generated = (1 if hero_image_url else 0) + len(supporting_images)
                    st.info(f"🖼️ Images generated: {images_generated}/3 (${image_cost:.2f})")

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
            "backend_counts": dict(backend_counts),
            "hero_image_url": hero_image_url,
            "hero_image_alt": hero_image_alt,
            "supporting_images": supporting_images,
            "image_cost": image_cost
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

    # Show images count if generated
    if result.get('hero_image_url') or result.get('supporting_images'):
        images_count = (1 if result.get('hero_image_url') else 0) + len(result.get('supporting_images', []))
        col4.metric("Images", f"{images_count}/3")
    else:
        col4.metric("Backends", len(result['backend_counts']))

    # Tabs for different views
    tab_names = ["📝 Article", "🖼️ Images", "📊 Sources", "📈 Analytics", "🔍 Raw Data"]
    tabs = st.tabs(tab_names)

    with tabs[0]:
        st.subheader("Generated Article")
        if result.get('article'):
            # Display hero image if available
            if result.get('hero_image_url'):
                st.image(
                    result['hero_image_url'],
                    caption=result.get('hero_image_alt', 'Hero image'),
                    use_container_width=True
                )
                st.divider()

            st.markdown(result['article'])
        else:
            st.info("Content synthesis was disabled")

    with tabs[1]:
        st.subheader("Generated Images")

        # Hero image
        if result.get('hero_image_url'):
            st.markdown("### Hero Image (1792x1024 HD)")
            st.image(
                result['hero_image_url'],
                caption=result.get('hero_image_alt', 'Hero image'),
                use_container_width=True
            )
        else:
            st.info("No hero image generated")

        st.divider()

        # Supporting images
        supporting = result.get('supporting_images', [])
        if supporting:
            st.markdown(f"### Supporting Images ({len(supporting)}/2)")
            cols = st.columns(2)
            for i, img in enumerate(supporting):
                with cols[i % 2]:
                    st.image(
                        img.get('url'),
                        caption=img.get('alt', f'Supporting image {i+1}'),
                        use_container_width=True
                    )
                    st.caption(f"**Size**: {img.get('size', 'N/A')} | **Quality**: {img.get('quality', 'N/A')}")
        else:
            st.info("No supporting images generated")

        # Cost breakdown
        if result.get('image_cost', 0) > 0:
            st.divider()
            st.caption(f"**Image Generation Cost**: ${result['image_cost']:.2f}")

    with tabs[2]:
        st.subheader("Top Sources")
        for i, source in enumerate(result['sources'][:10], 1):
            with st.expander(f"{i}. {source.get('title', 'Untitled')[:80]}"):
                st.caption(f"**Backend**: {source.get('backend', 'unknown')}")
                st.caption(f"**URL**: {source.get('url', 'N/A')}")
                if 'score' in source:
                    st.caption(f"**Score**: {source['score']:.3f}")
                if 'snippet' in source:
                    st.text(source['snippet'][:200] + "...")

    with tabs[3]:
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
        if result.get('image_cost', 0) > 0:
            st.caption(f"• Images: ${result['image_cost']:.2f}")

    with tabs[4]:
        st.subheader("Raw Result Data")
        st.json({
            "topic": result['topic'],
            "sources_count": len(result['sources']),
            "has_article": result.get('article') is not None,
            "cost": result['cost'],
            "duration_sec": result['duration_sec'],
            "backend_counts": result['backend_counts'],
            "has_hero_image": result.get('hero_image_url') is not None,
            "supporting_images_count": len(result.get('supporting_images', [])),
            "image_cost": result.get('image_cost', 0.0)
        })


def render_topic_research_tab(config: dict):
    """Render Tab 1: Topic Research (Deep Research)."""
    from src.ui.components.help import feature_explanation

    # Tab-level explanation
    feature_explanation(
        title="When to use Topic Research",
        what="Comprehensive research across 5 backends with AI synthesis into a full article",
        why="Perfect for creating in-depth, well-researched content (1500-2000 words) with citations",
        when="Use when you need authoritative content for blog posts, guides, or whitepapers. Skip for quick social posts.",
        icon="🔍"
    )

    st.divider()

    # Initialize session state
    if "research_result" not in st.session_state:
        st.session_state.research_result = None

    # Main content
    st.subheader("🎯 Research a Topic")

    # Topic input
    topic = st.text_input(
        "Enter your research topic",
        placeholder="e.g., PropTech AI automation trends 2025",
        help="The system will research this topic across multiple backends",
        key="topic_research_input"
    )

    # Quick examples
    with st.expander("💡 Example Topics"):
        st.caption("**PropTech**: Smart building IoT sensors Germany, DSGVO compliance property management")
        st.caption("**SaaS**: B2B pricing strategies 2025, Customer success platforms")
        st.caption("**Fashion**: Sustainable fashion e-commerce, AI styling recommendations")

    # Process button
    process_button = st.button("🚀 Research Topic", type="primary", use_container_width=True, disabled=not topic, key="research_topic_btn")

    if process_button and topic:
        print(f"[DEBUG] BUTTON CLICKED - Topic: {topic}")
        import sys
        sys.stdout.flush()

        # Check API keys
        required_keys = []
        if config["enable_tavily"]:
            required_keys.append("TAVILY_API_KEY")
        if config["enable_gemini"]:
            required_keys.append("GEMINI_API_KEY")
        if config["enable_reranking"]:
            required_keys.append("VOYAGE_API_KEY")

        print(f"[DEBUG] Checking {len(required_keys)} API keys...")
        sys.stdout.flush()

        missing_keys = [key for key in required_keys if not os.getenv(key)]
        if missing_keys:
            st.error(f"❌ Missing API keys: {', '.join(missing_keys)}")
            return

        # Process topic
        st.divider()
        st.subheader("⚙️ Pipeline Processing")
        progress_container = st.container()

        print("[DEBUG] About to call asyncio.run(process_topic_async...)")
        sys.stdout.flush()

        try:
            # Run async processing
            result = asyncio.run(
                process_topic_async(topic, config, progress_container)
            )

            print(f"[DEBUG] asyncio.run completed successfully")
            sys.stdout.flush()

            # Store in session state
            st.session_state.research_result = result

        except Exception as e:
            st.error(f"❌ Pipeline failed: {str(e)}")
            st.exception(e)

    # Display results if available
    if st.session_state.research_result:
        st.divider()
        st.subheader("📊 Results")

        render_results(st.session_state.research_result)

        # Action buttons
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📤 Export to Quick Create", use_container_width=True, type="primary"):
                # Export research results to Quick Create page
                st.session_state.export_to_quick_create = {
                    "topic": st.session_state.research_result["topic"],
                    "article": st.session_state.research_result.get("article"),
                    "sources": st.session_state.research_result.get("sources", [])
                }
                st.success("✅ Research exported! Navigate to Quick Create to use it.")

        with col2:
            if st.button("🗑️ Clear Results", use_container_width=True):
                st.session_state.research_result = None
                st.rerun()


def render_competitor_analysis_tab():
    """Render Tab 2: Competitor Analysis (Content Gaps)."""
    import os
    from src.ui.components.help import (
        feature_explanation,
        cost_estimate,
        time_estimate,
        what_happens_next
    )
    from src.agents.competitor_research_agent import CompetitorResearchAgent, CompetitorResearchError

    # Tab-level explanation
    feature_explanation(
        title="When to use Competitor Analysis",
        what="Analyze competitor content to identify gaps and opportunities in your niche",
        why="Helps you find topics your competitors are missing and create differentiated content",
        when="Use before planning content strategy or when entering a new market. Great for finding low-competition keywords.",
        icon="🏢"
    )

    st.divider()

    st.subheader("🏢 Competitor Content Gap Analysis")

    # Cost and time estimates
    col1, col2 = st.columns(2)
    with col1:
        cost_estimate(
            base_cost=0.0
        )
    with col2:
        # Competitor analysis: ~10-20 seconds (Gemini API with search grounding)
        st.caption("⏱️ **Time**: ~10-20 seconds")

    st.divider()

    # Input form
    topic = st.text_input(
        "Research Topic or Niche",
        placeholder="e.g., property management software, sustainable fashion, AI content tools",
        help="Your business topic or industry niche for competitor analysis",
        key="competitor_topic"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        language = st.selectbox(
            "Language",
            options=["de", "en", "es", "fr"],
            format_func=lambda x: {"de": "German", "en": "English", "es": "Spanish", "fr": "French"}[x],
            help="Target language for competitor research",
            key="competitor_language"
        )

    with col2:
        max_competitors = st.slider(
            "Max Competitors",
            min_value=3,
            max_value=10,
            value=5,
            help="Number of competitors to analyze (3-10)",
            key="competitor_max"
        )

    with col3:
        include_content_analysis = st.checkbox(
            "Include Content Strategy",
            value=True,
            help="Analyze competitor content patterns and posting frequency",
            key="competitor_content_analysis"
        )

    # What happens next
    what_happens_next([
        "🔍 AI identifies top competitors in your niche using Google Search",
        "📊 Analyzes their content strategy, topics, and social presence",
        "🎯 Identifies content gaps and opportunities",
        "📈 Finds trending topics in your market",
        "💡 Provides strategic recommendations"
    ])

    # Analysis button
    analyze_button = st.button(
        "🔍 Analyze Competitors",
        type="primary",
        use_container_width=True,
        key="run_competitor_analysis"
    )

    # Process analysis
    if analyze_button and topic:
        # Check API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            st.error("❌ Missing GEMINI_API_KEY. Please configure in Settings → API Keys.")
            return

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # Initialize agent
            status_text.text("Initializing competitor research agent...")
            progress_bar.progress(10)

            agent = CompetitorResearchAgent(
                api_key=api_key,
                use_cli=False,  # Use API with grounding (more reliable)
                model="gemini-2.5-flash"
            )

            # Run analysis
            status_text.text(f"Analyzing competitors for '{topic}'...")
            progress_bar.progress(30)

            result = agent.research_competitors(
                topic=topic,
                language=language,
                max_competitors=max_competitors,
                include_content_analysis=include_content_analysis,
                save_to_cache=False
            )

            progress_bar.progress(90)
            status_text.text("Analysis complete! Displaying results...")

            # Store in session state
            st.session_state.competitor_result = result
            st.session_state.competitor_topic = topic

            progress_bar.progress(100)
            status_text.text("✅ Competitor analysis complete!")

            st.success(f"✅ Found {len(result.get('competitors', []))} competitors with {len(result.get('content_gaps', []))} content gap opportunities!")

        except CompetitorResearchError as e:
            st.error(f"❌ Competitor research failed: {str(e)}")
            progress_bar.empty()
            status_text.empty()
            return
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")
            progress_bar.empty()
            status_text.empty()
            return

    # Display results
    if st.session_state.get("competitor_result"):
        st.divider()
        st.subheader(f"📊 Results for '{st.session_state.get('competitor_topic', 'Unknown')}'")

        result = st.session_state.competitor_result
        competitors = result.get("competitors", [])
        content_gaps = result.get("content_gaps", [])
        trending_topics = result.get("trending_topics", [])
        recommendation = result.get("recommendation", "")

        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Competitors Found", len(competitors))
        with col2:
            st.metric("Content Gaps", len(content_gaps))
        with col3:
            st.metric("Trending Topics", len(trending_topics))

        # Results tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🏢 Competitors Overview",
            "🎯 Content Gaps",
            "📈 Trending Topics",
            "💡 Recommendation",
            "🔍 Raw Data"
        ])

        with tab1:
            st.markdown("### Competitor Overview")
            if competitors:
                for i, comp in enumerate(competitors, 1):
                    with st.expander(f"#{i}: {comp.get('name', 'Unknown')} - {comp.get('website', 'No URL')}"):
                        st.markdown(f"**Description:** {comp.get('description', 'N/A')}")

                        social = comp.get('social_handles', {})
                        if any(social.values()):
                            st.markdown("**Social Media:**")
                            if social.get('linkedin'):
                                st.markdown(f"- LinkedIn: {social['linkedin']}")
                            if social.get('twitter'):
                                st.markdown(f"- Twitter: {social['twitter']}")
                            if social.get('facebook'):
                                st.markdown(f"- Facebook: {social['facebook']}")

                        if comp.get('content_topics'):
                            st.markdown(f"**Content Topics:** {', '.join(comp['content_topics'][:5])}")

                        if comp.get('posting_frequency'):
                            st.markdown(f"**Posting Frequency:** {comp['posting_frequency']}")
            else:
                st.info("No competitors found")

        with tab2:
            st.markdown("### Content Gap Opportunities")
            if content_gaps:
                for i, gap in enumerate(content_gaps, 1):
                    st.markdown(f"{i}. **{gap}**")
            else:
                st.info("No content gaps identified")

        with tab3:
            st.markdown("### Trending Topics in Your Niche")
            if trending_topics:
                for i, topic in enumerate(trending_topics, 1):
                    st.markdown(f"{i}. {topic}")
            else:
                st.info("No trending topics found")

        with tab4:
            st.markdown("### Strategic Recommendation")
            if recommendation:
                st.info(recommendation)
            else:
                st.info("No recommendation available")

        with tab5:
            st.json(result)

        # Competitor Comparison Matrix (3 views)
        from src.ui.components.competitor_matrix import render_competitor_matrix
        render_competitor_matrix(result)

        # Export and Sync buttons
        st.divider()
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📤 Export to Quick Create", use_container_width=True):
                # Store for Quick Create integration
                st.session_state.imported_competitor_insights = {
                    "competitors": competitors,
                    "content_gaps": content_gaps,
                    "trending_topics": trending_topics,
                    "recommendation": recommendation,
                    "timestamp": topic
                }
                st.success("✅ Exported to Quick Create! Navigate to Quick Create to use these insights.")

        with col2:
            if st.button("💾 Sync to Notion", use_container_width=True, key="sync_competitors_btn"):
                # Sync competitors to Notion
                import os
                from src.notion_integration.competitors_sync import CompetitorsSync

                notion_token = os.getenv("NOTION_TOKEN")
                database_ids_path = "cache/database_ids.json"

                if not notion_token:
                    st.error("❌ Notion token not found. Please set NOTION_TOKEN in your .env file.")
                else:
                    try:
                        # Load database ID
                        import json
                        with open(database_ids_path, 'r') as f:
                            db_ids = json.load(f)
                        competitor_db_id = db_ids.get('databases', {}).get('competitors')

                        if not competitor_db_id:
                            st.error("❌ Competitors database ID not found. Please run setup_notion.py first.")
                        else:
                            # Initialize sync
                            with st.spinner(f"Syncing {len(competitors)} competitors to Notion..."):
                                sync = CompetitorsSync(notion_token=notion_token, database_id=competitor_db_id)

                                # Sync batch
                                results = sync.sync_batch(competitors, skip_errors=True)

                                # Show statistics
                                stats = sync.get_statistics()
                                if stats['failed_syncs'] == 0:
                                    st.success(f"✅ Successfully synced {stats['total_synced']} competitors to Notion!")
                                else:
                                    st.warning(f"⚠️ Synced {stats['total_synced']} competitors, {stats['failed_syncs']} failed.")
                    except Exception as e:
                        st.error(f"❌ Sync failed: {str(e)}")

        with col3:
            if st.button("🗑️ Clear Results", use_container_width=True):
                st.session_state.competitor_result = None
                st.session_state.competitor_topic = None
                st.rerun()


def render_keyword_research_tab():
    """Render Tab 3: Keyword Research (SEO Keywords)."""
    import os
    from src.ui.components.help import (
        feature_explanation,
        cost_estimate,
        time_estimate,
        what_happens_next
    )
    from src.agents.keyword_research_agent import KeywordResearchAgent, KeywordResearchError

    # Tab-level explanation
    feature_explanation(
        title="When to use Keyword Research",
        what="Discover high-value SEO keywords with search volume, competition, and intent analysis",
        why="Target keywords that drive organic traffic without expensive paid ads",
        when="Use at the start of content planning or when optimizing existing content. Essential for SEO-focused content.",
        icon="🔑"
    )

    st.divider()

    st.subheader("🔑 SEO Keyword Research")

    # Cost and time estimates
    col1, col2 = st.columns(2)
    with col1:
        cost_estimate(
            base_cost=0.0
        )
    with col2:
        # Keyword research: ~10-15 seconds (Gemini API with search grounding)
        st.caption("⏱️ **Time**: ~10-15 seconds")

    st.divider()

    # Input form
    seed_keyword = st.text_input(
        "Seed Keyword or Topic",
        placeholder="e.g., property management software, sustainable fashion, content marketing",
        help="Starting keyword or topic for SEO research",
        key="keyword_seed"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        language = st.selectbox(
            "Language",
            options=["de", "en", "es", "fr"],
            format_func=lambda x: {"de": "German", "en": "English", "es": "Spanish", "fr": "French"}[x],
            help="Target language for keyword research",
            key="keyword_language"
        )

    with col2:
        keyword_count = st.slider(
            "Keywords to Find",
            min_value=10,
            max_value=50,
            value=20,
            help="Number of keywords to discover (10-50)",
            key="keyword_count"
        )

    with col3:
        target_audience = st.text_input(
            "Target Audience (Optional)",
            placeholder="e.g., small business owners",
            help="Refines keyword suggestions for specific audience",
            key="keyword_audience"
        )

    # Advanced options
    with st.expander("🔧 Advanced Options"):
        include_search_trends = st.checkbox(
            "Include Search Trends",
            value=True,
            help="Analyze trending keywords and seasonal patterns",
            key="keyword_trends"
        )

    # What happens next
    what_happens_next([
        "🔍 AI analyzes your seed keyword using Google Search",
        "📊 Discovers primary, secondary, and long-tail keywords",
        "💡 Identifies related questions people ask",
        "📈 Estimates search volume and competition level",
        "🎯 Calculates keyword difficulty (0-100 score)",
        "✨ Provides strategic keyword recommendations"
    ])

    # Research button
    research_button = st.button(
        "🔍 Research Keywords",
        type="primary",
        use_container_width=True,
        key="run_keyword_research"
    )

    # Process research
    if research_button and seed_keyword:
        # Check API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            st.error("❌ Missing GEMINI_API_KEY. Please configure in Settings → API Keys.")
            return

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # Initialize agent
            status_text.text("Initializing keyword research agent...")
            progress_bar.progress(10)

            agent = KeywordResearchAgent(
                api_key=api_key,
                use_cli=False,  # Use API with grounding (more reliable)
                model="gemini-2.5-flash"
            )

            # Run research
            status_text.text(f"Researching keywords for '{seed_keyword}'...")
            progress_bar.progress(30)

            result = agent.research_keywords(
                topic=seed_keyword,
                language=language,
                target_audience=target_audience if target_audience else None,
                keyword_count=keyword_count,
                save_to_cache=False
            )

            progress_bar.progress(90)
            status_text.text("Calculating opportunity scores...")

            # Calculate opportunity scores for all keywords
            from src.scoring.opportunity_scorer import OpportunityScorer

            scorer = OpportunityScorer()
            content_gaps = []  # No competitor data in this tab
            trending_topics = result.get('search_trends', {}).get('trending_up', [])

            # Add opportunity scores to keywords
            if result.get('primary_keyword'):
                primary_kw = result['primary_keyword']
                primary_kw['opportunity_score'] = scorer.calculate_opportunity_score(
                    primary_kw, content_gaps, trending_topics
                )
                primary_kw['opportunity_explanation'] = scorer.explain_opportunity(
                    primary_kw, primary_kw['opportunity_score'], content_gaps, trending_topics
                )

            for kw in result.get('secondary_keywords', []):
                kw['opportunity_score'] = scorer.calculate_opportunity_score(
                    kw, content_gaps, trending_topics
                )

            for kw in result.get('long_tail_keywords', []):
                kw['opportunity_score'] = scorer.calculate_opportunity_score(
                    kw, content_gaps, trending_topics
                )

            # Store in session state
            st.session_state.keyword_result = result
            st.session_state.keyword_seed = seed_keyword

            progress_bar.progress(100)
            status_text.text("✅ Keyword research complete!")

            # Count keywords
            total_keywords = (
                1 +  # primary
                len(result.get('secondary_keywords', [])) +
                len(result.get('long_tail_keywords', []))
            )

            st.success(f"✅ Discovered {total_keywords} keywords including {len(result.get('related_questions', []))} question variations!")

        except KeywordResearchError as e:
            st.error(f"❌ Keyword research failed: {str(e)}")
            progress_bar.empty()
            status_text.empty()
            return
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")
            progress_bar.empty()
            status_text.empty()
            return

    # Display results
    if st.session_state.get("keyword_result"):
        st.divider()
        st.subheader(f"📊 Results for '{st.session_state.get('keyword_seed', 'Unknown')}'")

        result = st.session_state.keyword_result
        primary = result.get("primary_keyword", {})
        secondary = result.get("secondary_keywords", [])
        long_tail = result.get("long_tail_keywords", [])
        questions = result.get("related_questions", [])
        trends = result.get("search_trends", {})
        recommendation = result.get("recommendation", "")

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Keywords", 1 + len(secondary) + len(long_tail))
        with col2:
            st.metric("Secondary Keywords", len(secondary))
        with col3:
            st.metric("Long-tail Keywords", len(long_tail))
        with col4:
            st.metric("Question Keywords", len(questions))

        # Results tabs
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "🎯 Primary Keyword",
            "📊 Secondary Keywords",
            "🔎 Long-tail Keywords",
            "❓ Related Questions",
            "📈 Search Trends",
            "🔍 Raw Data"
        ])

        with tab1:
            st.markdown("### Primary Keyword")
            if primary:
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Keyword", primary.get('keyword', 'N/A'))
                with col2:
                    st.metric("Search Volume", primary.get('search_volume', 'Unknown'))
                with col3:
                    st.metric("Competition", primary.get('competition', 'Medium'))
                with col4:
                    st.metric("Difficulty", f"{primary.get('difficulty', 50)}/100")
                with col5:
                    # Opportunity Score with color-coded badge
                    opp_score = primary.get('opportunity_score', 0)
                    badge = get_opportunity_badge(opp_score)
                    st.metric("Opportunity", badge)

                st.markdown(f"**Search Intent:** {primary.get('intent', 'Informational')}")

                # AI-powered opportunity explanation
                if primary.get('opportunity_explanation'):
                    with st.expander("💡 AI Opportunity Analysis", expanded=True):
                        st.info(primary['opportunity_explanation'])

                if recommendation:
                    st.info(f"💡 **Recommendation:** {recommendation}")
            else:
                st.info("No primary keyword found")

        with tab2:
            st.markdown("### Secondary Keywords")
            if secondary:
                # Create table
                import pandas as pd
                df_data = []
                for kw in secondary:
                    opp_score = kw.get('opportunity_score', 0)
                    df_data.append({
                        "Keyword": kw.get('keyword', ''),
                        "Search Volume": kw.get('search_volume', 'Unknown'),
                        "Competition": kw.get('competition', 'Medium'),
                        "Difficulty": f"{kw.get('difficulty', 50)}/100",
                        "Relevance": f"{kw.get('relevance', 50)}%",
                        "Opportunity": get_opportunity_badge(opp_score)
                    })
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No secondary keywords found")

        with tab3:
            st.markdown("### Long-tail Keywords (3-5 words)")
            if long_tail:
                # Create table
                import pandas as pd
                df_data = []
                for kw in long_tail:
                    opp_score = kw.get('opportunity_score', 0)
                    df_data.append({
                        "Keyword": kw.get('keyword', ''),
                        "Search Volume": kw.get('search_volume', 'Unknown'),
                        "Competition": kw.get('competition', 'Low'),
                        "Difficulty": f"{kw.get('difficulty', 30)}/100",
                        "Opportunity": get_opportunity_badge(opp_score)
                    })
                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No long-tail keywords found")

        with tab4:
            st.markdown("### Related Questions")
            st.caption("Common questions people search related to your topic")
            if questions:
                for i, question in enumerate(questions, 1):
                    st.markdown(f"{i}. {question}")
            else:
                st.info("No related questions found")

        with tab5:
            st.markdown("### Search Trends")
            if trends:
                st.json(trends)
            else:
                st.info("No search trend data available")

        with tab6:
            st.json(result)

        # Export and Sync buttons
        st.divider()
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📤 Export to Quick Create", use_container_width=True, key="export_keywords_btn"):
                # Store for Quick Create integration
                st.session_state.imported_keyword_research = {
                    "primary_keyword": primary,
                    "secondary_keywords": secondary,
                    "long_tail_keywords": long_tail,
                    "related_questions": questions,
                    "recommendation": recommendation,
                    "seed_keyword": seed_keyword
                }
                st.success("✅ Exported to Quick Create! Navigate to Quick Create to use these keywords.")

        with col2:
            if st.button("💾 Sync to Notion", use_container_width=True, key="sync_keywords_btn"):
                # Sync keywords to Notion
                import os
                from src.notion_integration.keywords_sync import KeywordsSync

                notion_token = os.getenv("NOTION_TOKEN")
                database_ids_path = "cache/database_ids.json"

                if not notion_token:
                    st.error("❌ Notion token not found. Please set NOTION_TOKEN in your .env file.")
                else:
                    try:
                        # Load database ID
                        import json
                        with open(database_ids_path, 'r') as f:
                            db_ids = json.load(f)
                        keywords_db_id = db_ids.get('databases', {}).get('keywords')

                        if not keywords_db_id:
                            st.warning("⚠️ Keywords database ID not found in cache/database_ids.json")
                            st.info("Please create the 'Keywords' database in Notion and add its ID to cache/database_ids.json as 'keywords': 'your-database-id-here'")
                        else:
                            # Initialize sync
                            total_keywords = 1 + len(secondary) + len(long_tail)  # primary + secondary + long-tail
                            with st.spinner(f"Syncing {total_keywords} keywords to Notion..."):
                                sync = KeywordsSync(notion_token=notion_token, database_id=keywords_db_id)

                                # Sync keyword set (primary + secondary + long-tail)
                                sync_result = sync.sync_keyword_set(
                                    research_result=result,
                                    source_topic=seed_keyword,
                                    skip_errors=True
                                )

                                # Show statistics
                                stats = sync.get_statistics()
                                if stats['failed_syncs'] == 0:
                                    st.success(f"✅ Successfully synced {sync_result['total']} keywords to Notion! (Primary: {sync_result['primary']}, Secondary: {sync_result['secondary']}, Long-tail: {sync_result['long_tail']})")
                                else:
                                    st.warning(f"⚠️ Synced {sync_result['total']} keywords, {sync_result.get('failed', 0)} failed.")
                    except Exception as e:
                        st.error(f"❌ Sync failed: {str(e)}")

        with col3:
            if st.button("🗑️ Clear Results", use_container_width=True, key="clear_keywords_btn"):
                st.session_state.keyword_result = None
                st.session_state.keyword_seed = None
                st.rerun()


def render():
    """Render Topic Research Lab page with 3 tabs."""
    st.title("🔬 Research Lab")
    st.caption("Comprehensive research tools: Deep topic research, competitor analysis, and SEO keyword discovery")

    # Render config sidebar (shared across all tabs)
    config = render_config_sidebar()

    st.divider()

    # Tab navigation
    tab1, tab2, tab3 = st.tabs([
        "🔍 Topic Research",
        "🏢 Competitor Analysis",
        "🔑 Keyword Research"
    ])

    with tab1:
        render_topic_research_tab(config)

    with tab2:
        render_competitor_analysis_tab()

    with tab3:
        render_keyword_research_tab()
