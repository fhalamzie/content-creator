"""
Hybrid Research Orchestrator

Combines keyword extraction, competitor research, and production pipeline.

Flow:
1. Website Keyword Extraction (customer's site)
2. Competitor/Market Research (using keywords + customer info)
3. Consolidate keywords + tags → topics
4. Feed to collectors (RSS, Reddit, Trends, etc.)
5. NEW Pipeline: DeepResearcher → MultiStageReranker → ContentSynthesizer

Cost: ~$0 for stages 1-3 (free Gemini CLI), $0.01/topic for stage 5
"""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path
import json
import os

import trafilatura

from src.utils.logger import get_logger
from src.research.deep_researcher_refactored import DeepResearcher
from src.research.reranker.multi_stage_reranker import MultiStageReranker
from src.research.synthesizer.content_synthesizer import (
    ContentSynthesizer,
    PassageExtractionStrategy
)
from src.utils.config_loader import ConfigLoader
from src.agents.gemini_agent import GeminiAgent, GeminiAgentError
from src.orchestrator.topic_validator import TopicValidator, TopicMetadata
from src.orchestrator.cost_tracker import CostTracker, APIType
from src.research.backends.exceptions import RateLimitError
from src.research.backends.tavily_backend import TavilyBackend
from src.database.sqlite_manager import SQLiteManager
from src.processors.deduplicator import Deduplicator
from src.collectors.autocomplete_collector import AutocompleteCollector, ExpansionType
from src.collectors.trends_collector import TrendsCollector

logger = get_logger(__name__)


class HybridResearchOrchestrator:
    """
    Orchestrates the complete research pipeline.

    Stages:
    1. Website keyword extraction (customer site analysis)
    2. Competitor research (market analysis using keywords)
    3. Consolidation (keywords + tags → topics)
    4. Topic discovery (collectors find relevant content)
    5. Content research (NEW pipeline: research → rerank → synthesize)
    """

    def __init__(
        self,
        enable_tavily: bool = True,
        enable_searxng: bool = True,
        enable_gemini: bool = True,
        enable_rss: bool = False,
        enable_thenewsapi: bool = False,
        enable_reranking: bool = True,
        enable_synthesis: bool = True,
        max_article_words: int = 2000,
        # Topic discovery settings
        enable_autocomplete: bool = True,
        enable_trends: bool = True,
        topic_discovery_language: str = "en",
        topic_discovery_region: str = "US",
        db_path: str = "data/topics.db"
    ):
        """
        Initialize orchestrator.

        Args:
            enable_tavily: Enable Tavily backend (DEPTH)
            enable_searxng: Enable SearXNG backend (BREADTH)
            enable_gemini: Enable Gemini backend (TRENDS)
            enable_rss: Enable RSS collector (NICHE)
            enable_thenewsapi: Enable TheNewsAPI collector (NEWS)
            enable_reranking: Enable 3-stage reranking
            enable_synthesis: Enable content synthesis
            max_article_words: Max words per article (default: 2000)
            enable_autocomplete: Enable Google Autocomplete collector (QUESTIONS)
            enable_trends: Enable Google Trends collector (TRENDING)
            topic_discovery_language: Language for topic discovery (default: en)
            topic_discovery_region: Region for trends (default: US)
            db_path: Path to SQLite database for collectors (default: data/topics.db)
        """
        self.enable_tavily = enable_tavily
        self.enable_searxng = enable_searxng
        self.enable_gemini = enable_gemini
        self.enable_rss = enable_rss
        self.enable_thenewsapi = enable_thenewsapi
        self.enable_reranking = enable_reranking
        self.enable_synthesis = enable_synthesis
        self.max_article_words = max_article_words
        self.enable_autocomplete = enable_autocomplete
        self.enable_trends = enable_trends
        self.topic_discovery_language = topic_discovery_language
        self.topic_discovery_region = topic_discovery_region

        # Initialize components (lazy loading)
        self._researcher = None
        self._reranker = None
        self._synthesizer = None
        self._gemini_agent = None
        self._topic_validator = None
        self._tavily_backend = None
        self._cost_tracker = CostTracker()  # Always initialized for cost tracking

        # Initialize topic discovery infrastructure
        self._db_manager = None
        self._deduplicator = None
        self._autocomplete_collector = None
        self._trends_collector = None

        # Initialize DatabaseManager and Deduplicator if any collector is enabled
        if enable_autocomplete or enable_trends or enable_rss or enable_thenewsapi:
            self._db_manager = SQLiteManager(db_path=db_path)
            self._deduplicator = Deduplicator(threshold=0.7, num_perm=128)

            # Create minimal config for collectors
            from unittest.mock import Mock
            self._collector_config = Mock()
            self._collector_config.market = Mock()
            self._collector_config.market.domain = "General"
            self._collector_config.market.market = topic_discovery_region
            self._collector_config.market.language = topic_discovery_language
            self._collector_config.market.vertical = "Research"

        logger.info(
            "hybrid_orchestrator_initialized",
            backends=f"{sum([enable_tavily, enable_searxng, enable_gemini])} backends",
            collectors=f"{sum([enable_rss, enable_thenewsapi, enable_autocomplete, enable_trends])} collectors",
            reranking=enable_reranking,
            synthesis=enable_synthesis,
            topic_discovery=f"autocomplete={enable_autocomplete}, trends={enable_trends}"
        )

    @property
    def researcher(self) -> DeepResearcher:
        """Lazy load researcher"""
        if self._researcher is None:
            self._researcher = DeepResearcher(
                enable_tavily=self.enable_tavily,
                enable_searxng=self.enable_searxng,
                enable_gemini=self.enable_gemini,
                enable_rss=self.enable_rss,
                enable_thenewsapi=self.enable_thenewsapi
            )
        return self._researcher

    @property
    def reranker(self) -> Optional[MultiStageReranker]:
        """Lazy load reranker"""
        if self.enable_reranking and self._reranker is None:
            self._reranker = MultiStageReranker(
                enable_voyage=True,
                stage3_final_count=25
            )
        return self._reranker if self.enable_reranking else None

    @property
    def synthesizer(self) -> Optional[ContentSynthesizer]:
        """Lazy load synthesizer"""
        if self.enable_synthesis and self._synthesizer is None:
            self._synthesizer = ContentSynthesizer(
                strategy=PassageExtractionStrategy.BM25_LLM,
                max_article_words=self.max_article_words
            )
        return self._synthesizer if self.enable_synthesis else None

    @property
    def gemini_agent(self) -> GeminiAgent:
        """Lazy load Gemini agent for competitor research with grounding"""
        if self._gemini_agent is None:
            self._gemini_agent = GeminiAgent(
                model="gemini-2.5-flash",
                api_key=os.getenv("GEMINI_API_KEY"),
                enable_grounding=True,  # Enable web search for competitor research
                temperature=0.3,
                max_tokens=4000
            )
        return self._gemini_agent

    @property
    def topic_validator(self) -> TopicValidator:
        """Lazy load topic validator"""
        if self._topic_validator is None:
            self._topic_validator = TopicValidator()
        return self._topic_validator

    @property
    def cost_tracker(self) -> CostTracker:
        """Get cost tracker"""
        return self._cost_tracker

    @property
    def tavily_backend(self) -> Optional[TavilyBackend]:
        """Lazy load Tavily backend for fallback"""
        if self._tavily_backend is None and self.enable_tavily:
            try:
                self._tavily_backend = TavilyBackend()
                logger.info("tavily_backend_loaded_for_fallback")
            except Exception as e:
                logger.warning("tavily_backend_init_failed", error=str(e))
                return None
        return self._tavily_backend

    @property
    def autocomplete_collector(self) -> Optional[AutocompleteCollector]:
        """Lazy load Autocomplete collector"""
        if self.enable_autocomplete and self._autocomplete_collector is None:
            self._autocomplete_collector = AutocompleteCollector(
                config=self._collector_config,
                db_manager=self._db_manager,
                deduplicator=self._deduplicator,
                language=self.topic_discovery_language,
                cache_dir="cache/autocomplete"
            )
            logger.info("autocomplete_collector_initialized", language=self.topic_discovery_language)
        return self._autocomplete_collector if self.enable_autocomplete else None

    @property
    def trends_collector(self) -> Optional[TrendsCollector]:
        """Lazy load Trends collector"""
        if self.enable_trends and self._trends_collector is None:
            self._trends_collector = TrendsCollector(
                config=self._collector_config,
                db_manager=self._db_manager,
                deduplicator=self._deduplicator,
                gemini_agent=self.gemini_agent,  # Reuse orchestrator's Gemini agent
                region=self.topic_discovery_region,
                cache_dir="cache/trends"
            )
            logger.info("trends_collector_initialized", region=self.topic_discovery_region)
        return self._trends_collector if self.enable_trends else None

    async def extract_website_keywords(
        self,
        website_url: str,
        max_keywords: int = 50
    ) -> Dict:
        """
        Stage 1: Extract keywords from customer website.

        Uses trafilatura to fetch content, then Gemini (free tier) to analyze:
        - SEO keywords (search terms)
        - Semantic tags (topics, categories)
        - Content themes

        Args:
            website_url: Customer's website URL
            max_keywords: Max keywords to extract (default: 50)

        Returns:
            Dict with:
                - keywords: List[str] - SEO keywords
                - tags: List[str] - Semantic tags/topics
                - themes: List[str] - Content themes
                - tone: List[str] - Communication tone/style (1-3)
                - setting: List[str] - Target audience/setting (1-3)
                - niche: List[str] - Industry niches (1-3)
                - domain: str - Primary business domain
                - cost: float - Processing cost ($0 with free tier)
        """
        logger.info("stage1_website_keyword_extraction", url=website_url)

        try:
            # Step 1: Fetch website content with trafilatura
            logger.info("fetching_website_content", url=website_url)

            downloaded = trafilatura.fetch_url(website_url)
            if not downloaded:
                logger.warning("failed_to_fetch_website", url=website_url)
                # Return empty result on fetch failure
                return {
                    "keywords": [],
                    "tags": [],
                    "themes": [],
                    "tone": [],
                    "setting": [],
                    "niche": [],
                    "domain": "Unknown",
                    "cost": 0.0,
                    "error": "Failed to fetch website content"
                }

            # Extract clean text content
            content = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                output_format='txt'
            )

            if not content or len(content.strip()) < 100:
                logger.warning("insufficient_content", url=website_url, length=len(content) if content else 0)
                return {
                    "keywords": [],
                    "tags": [],
                    "themes": [],
                    "tone": [],
                    "setting": [],
                    "niche": [],
                    "domain": "Unknown",
                    "cost": 0.0,
                    "error": "Insufficient content extracted from website"
                }

            logger.info("content_extracted", url=website_url, length=len(content))

            # Step 2: Analyze content with Gemini
            gemini_agent = GeminiAgent(
                model="gemini-2.5-flash",
                api_key=os.getenv("GEMINI_API_KEY"),
                enable_grounding=False,  # No web search needed for local content analysis
                temperature=0.3
            )

            # Build analysis prompt
            analysis_prompt = f"""Analyze this website content and extract:

1. **SEO Keywords** (max {max_keywords}): Specific search terms users might use to find this business
   - Focus on product/service names, industry terms, technologies
   - Include both broad and long-tail keywords
   - Include geographic/market-specific terms if present

2. **Semantic Tags** (5-10): High-level topics, categories, or themes
   - Industry verticals (e.g., "PropTech", "SaaS", "E-commerce")
   - Technology areas (e.g., "AI", "IoT", "Cloud Computing")
   - Market segments (e.g., "B2B", "Enterprise", "SMB")

3. **Content Themes** (3-5): Main narrative arcs or value propositions
   - What problems does this business solve?
   - What makes them unique?
   - What are their core focus areas?

4. **Tone** (1-3 descriptors): Communication style and voice
   - Examples: "Professional", "Technical", "Casual", "Friendly", "Authoritative", "Innovative"
   - Describe how the content speaks to the audience

5. **Target Setting** (1-3 categories): Business model and audience
   - Examples: "B2B", "B2C", "Enterprise", "SMB", "Consumer", "Developer-focused"
   - Who is this business serving?

6. **Niche** (1-3 industries): Specific industry verticals
   - Examples: "PropTech", "FinTech", "HealthTech", "EdTech", "E-commerce", "SaaS"
   - Be specific about the industry niche

7. **Domain** (single): Primary business domain/industry
   - Examples: "Real Estate", "Financial Services", "Healthcare", "Education", "Retail"
   - The overarching domain this business operates in

Website Content:
{content[:5000]}  # Limit to first 5000 chars to avoid token limits

Return ONLY valid JSON (no markdown fences)."""

            # Define response schema
            response_schema = {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"SEO keywords (max {max_keywords})"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Semantic tags/topics (5-10)"
                    },
                    "themes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Content themes (3-5)"
                    },
                    "tone": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Communication tone/style (1-3 descriptors)"
                    },
                    "setting": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Target setting/audience (1-3 categories)"
                    },
                    "niche": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Industry niche (1-3 industries)"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Primary business domain/industry"
                    }
                },
                "required": ["keywords", "tags", "themes", "tone", "setting", "niche", "domain"]
            }

            # Generate analysis (wrap synchronous call for async context)
            logger.info("analyzing_with_gemini", url=website_url)
            result_raw = await asyncio.to_thread(
                gemini_agent.generate,
                prompt=analysis_prompt,
                response_schema=response_schema
            )

            # Extract parsed content
            content_data = result_raw.get("content", {})
            if isinstance(content_data, str):
                # Parse JSON string if needed
                import json
                content_data = json.loads(content_data)

            # Build result with limits enforced
            result = {
                "keywords": content_data.get("keywords", [])[:max_keywords],
                "tags": content_data.get("tags", [])[:10],
                "themes": content_data.get("themes", [])[:5],
                "tone": content_data.get("tone", [])[:3],
                "setting": content_data.get("setting", [])[:3],
                "niche": content_data.get("niche", [])[:3],
                "domain": content_data.get("domain", "Unknown"),
                "cost": result_raw.get("cost", 0.0)
            }

            logger.info(
                "stage1_complete",
                url=website_url,
                keywords_count=len(result["keywords"]),
                tags_count=len(result["tags"]),
                themes_count=len(result["themes"]),
                tone_count=len(result["tone"]),
                setting_count=len(result["setting"]),
                niche_count=len(result["niche"]),
                domain=result["domain"],
                cost=f"${result['cost']:.4f}"
            )

            return result

        except GeminiAgentError as e:
            logger.error("gemini_analysis_failed", url=website_url, error=str(e))
            return {
                "keywords": [],
                "tags": [],
                "themes": [],
                "tone": [],
                "setting": [],
                "niche": [],
                "domain": "Unknown",
                "cost": 0.0,
                "error": f"Gemini analysis failed: {str(e)}"
            }
        except Exception as e:
            logger.error("stage1_failed", url=website_url, error=str(e), exc_info=True)
            return {
                "keywords": [],
                "tags": [],
                "themes": [],
                "tone": [],
                "setting": [],
                "niche": [],
                "domain": "Unknown",
                "cost": 0.0,
                "error": f"Extraction failed: {str(e)}"
            }

    async def _research_competitors_with_tavily(
        self,
        keywords: List[str],
        customer_info: Dict,
        max_competitors: int = 10
    ) -> Dict:
        """
        Fallback: Research competitors using Tavily API.

        Used when Gemini API hits rate limits. Uses Tavily search to
        find competitors and extract market information.

        Args:
            keywords: Keywords from stage 1
            customer_info: Dict with market, vertical, language
            max_competitors: Max competitors to analyze

        Returns:
            Dict with competitors, keywords, market_topics, cost
        """
        logger.info("stage2_fallback_tavily_research")

        if not self.tavily_backend:
            logger.error("tavily_backend_not_available")
            return {
                "competitors": [],
                "additional_keywords": [],
                "market_topics": [],
                "cost": 0.0,
                "error": "Tavily backend not available"
            }

        try:
            market = customer_info.get("market", "")
            vertical = customer_info.get("vertical", "")
            domain = customer_info.get("domain", "")

            # Build search query for competitors
            keywords_str = " ".join(keywords[:10])
            competitor_query = f"{vertical} companies {market} competitors in {domain}"

            logger.info("tavily_competitor_search", query=competitor_query[:100])

            # Search with Tavily
            results = await self.tavily_backend.search(
                query=competitor_query,
                max_results=max_competitors,
                search_depth="basic"  # Basic depth for cost optimization
            )

            # Parse results to extract competitor info
            competitors = []
            additional_keywords = set(keywords)  # Start with existing keywords
            market_topics = set()

            for result in results:
                # Each result is a potential competitor
                competitors.append({
                    "name": result.get("title", "Unknown")[:50],
                    "url": result.get("url", ""),
                    "topics": result.get("snippet", "").split()[:5]  # Extract key words from snippet
                })

                # Extract keywords from content
                content = result.get("content", "")
                if content:
                    # Simple keyword extraction: split and filter
                    words = content.lower().split()
                    relevant_words = [w for w in words if len(w) > 4 and w.isalpha()][:10]
                    additional_keywords.update(relevant_words)

            # Market topics from result titles
            for result in results:
                title = result.get("title", "")
                if title:
                    # Extract key phrases from title
                    words = title.split()
                    for i in range(len(words) - 1):
                        phrase = f"{words[i]} {words[i+1]}"
                        if len(phrase) > 8:
                            market_topics.add(phrase)

            # Tavily search cost: $0.02 per query
            cost = 0.02

            logger.info(
                "tavily_fallback_complete",
                competitors=len(competitors),
                additional_keywords=len(additional_keywords),
                market_topics=len(market_topics),
                cost=f"${cost:.4f}"
            )

            return {
                "competitors": competitors[:max_competitors],
                "additional_keywords": list(additional_keywords)[:50],
                "market_topics": list(market_topics)[:20],
                "cost": cost
            }

        except Exception as e:
            logger.error("tavily_fallback_failed", error=str(e), exc_info=True)
            return {
                "competitors": [],
                "additional_keywords": [],
                "market_topics": [],
                "cost": 0.0,
                "error": f"Tavily fallback failed: {str(e)}"
            }

    async def discover_competitor_feeds(
        self,
        competitor_urls: List[str],
        hint_domain: Optional[str] = None,
        hint_vertical: Optional[str] = None
    ) -> Dict:
        """
        Phase B: Discover RSS feeds from competitor websites.

        Uses automated feed discovery to find and add competitor RSS feeds
        to the database for future topic collection.

        Args:
            competitor_urls: List of competitor website URLs
            hint_domain: Optional domain hint for categorization
            hint_vertical: Optional vertical hint for categorization

        Returns:
            Dict with:
                - feeds_discovered: int - Number of feeds found
                - feeds_added: int - Number of feeds added to database
                - feeds: List[RSSFeed] - Discovered feed objects
                - cost: float - Processing cost ($0 - uses free Gemini for categorization)
        """
        logger.info(
            "phase_b_competitor_feed_discovery",
            competitor_count=len(competitor_urls),
            hint_domain=hint_domain,
            hint_vertical=hint_vertical
        )

        try:
            from src.collectors.automated_feed_discovery import AutomatedFeedDiscovery

            # Initialize feed discovery with auto-add enabled
            discovery = AutomatedFeedDiscovery(
                min_quality_score=0.6,
                auto_add_to_database=True
            )

            # Discover feeds from competitor URLs
            feeds = await discovery.discover_from_competitor_urls(
                competitor_urls=competitor_urls,
                hint_domain=hint_domain,
                hint_vertical=hint_vertical
            )

            # Get statistics
            stats = discovery.get_statistics()

            result = {
                "feeds_discovered": stats["feeds_discovered"],
                "feeds_added": stats["feeds_added"],
                "feeds": feeds,
                "cost": 0.0  # Free Gemini API for categorization
            }

            logger.info(
                "competitor_feed_discovery_complete",
                feeds_discovered=result["feeds_discovered"],
                feeds_added=result["feeds_added"]
            )

            return result

        except Exception as e:
            logger.error("competitor_feed_discovery_failed", error=str(e), exc_info=True)
            return {
                "feeds_discovered": 0,
                "feeds_added": 0,
                "feeds": [],
                "cost": 0.0,
                "error": f"Feed discovery failed: {str(e)}"
            }

    async def research_competitors(
        self,
        keywords: List[str],
        customer_info: Dict,
        max_competitors: int = 10,
        discover_feeds: bool = False
    ) -> Dict:
        """
        Stage 2: Competitor/market research using extracted keywords.

        Uses Gemini API with grounding (free tier) to:
        - Identify competitors in the market
        - Extract additional keywords from competitor content
        - Discover market topics and trends
        - Optionally discover RSS feeds from competitors (Phase B)

        Args:
            keywords: Keywords from stage 1
            customer_info: Dict with market, vertical, language
            max_competitors: Max competitors to analyze (default: 10)
            discover_feeds: Enable Phase B feed discovery (default: False)

        Returns:
            Dict with:
                - competitors: List[Dict] - Competitor info (name, url, topics)
                - additional_keywords: List[str] - More keywords (max 50)
                - market_topics: List[str] - Trending topics (max 20)
                - rss_feeds: Dict - Discovered RSS feeds (if discover_feeds=True)
                - cost: float - Processing cost ($0 with free tier)
        """
        logger.info(
            "stage2_competitor_research",
            keywords_count=len(keywords),
            market=customer_info.get("market", "unknown")
        )

        # Handle empty keywords gracefully
        if not keywords:
            logger.warning("stage2_empty_keywords")
            return {
                "competitors": [],
                "additional_keywords": [],
                "market_topics": [],
                "cost": 0.0
            }

        try:
            logger.info("stage2_step1_building_context")

            # Build search context from keywords and customer info
            market = customer_info.get("market", "")
            vertical = customer_info.get("vertical", "")
            language = customer_info.get("language", "en")
            domain = customer_info.get("domain", "")

            logger.info("stage2_step2_creating_prompt", keywords_count=len(keywords))

            # Create research prompt
            keywords_str = ", ".join(keywords[:20])  # Use top 20 keywords
            prompt = f"""You are a market research expert. Analyze the {vertical} market in {market}.

Customer Keywords: {keywords_str}
Customer Domain: {domain}
Market: {market}
Language: {language}

Tasks:
1. Identify top {max_competitors} competitors in this market (companies offering similar products/services)
2. Extract {50} additional relevant keywords and search terms for this market
3. Identify {20} trending topics and themes in this market

For each competitor, provide:
- name: Company name
- url: Official website URL
- topics: List of their main product/service topics (2-5 topics)

Return in strict JSON format matching the schema below."""

            # Define response schema
            response_schema = {
                "type": "object",
                "properties": {
                    "competitors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "url": {"type": "string"},
                                "topics": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["name", "url", "topics"]
                        }
                    },
                    "additional_keywords": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "market_topics": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["competitors", "additional_keywords", "market_topics"]
            }

            # Call Gemini API with grounding (native async version)
            # FIX: Use generate_async() directly - no executor needed!
            # This properly uses the Gemini SDK's async client (client.aio.models.generate_content)
            logger.info("stage2_step3_creating_gemini_agent", grounding=True)
            gemini_agent = GeminiAgent(
                model="gemini-2.5-flash",
                api_key=os.getenv("GEMINI_API_KEY"),
                enable_grounding=True,  # Enable web search for competitor research
                temperature=0.3,
                max_tokens=4000
            )
            logger.info("stage2_step3_agent_created")

            logger.info("stage2_step4_calling_gemini_api_START", grounding=True, prompt_length=len(prompt))
            try:
                # FIX: Call async method directly - no run_in_executor needed!
                # The Gemini SDK supports native async via client.aio namespace
                import time
                api_start = time.time()

                result_raw = await gemini_agent.generate_async(
                    prompt=prompt,
                    response_schema=response_schema
                )

                api_duration = time.time() - api_start
                logger.info("stage2_step4_gemini_api_COMPLETE",
                           duration_s=f"{api_duration:.2f}",
                           result_keys=list(result_raw.keys()) if result_raw else [])

                # Track successful free API call
                self.cost_tracker.track_call(
                    api_type=APIType.GEMINI_FREE,
                    stage="stage2",
                    success=True,
                    cost=result_raw.get("cost", 0.0)
                )

                logger.info("stage2_step5_parsing_response")

                # Extract parsed content
                content_data = result_raw.get("content", {})
                if isinstance(content_data, str):
                    # Parse JSON string if needed
                    import json
                    logger.info("stage2_step5_parsing_json_string", length=len(content_data))
                    content_data = json.loads(content_data)
                    logger.info("stage2_step5_json_parsed", keys=list(content_data.keys()) if isinstance(content_data, dict) else "not_dict")

                # Handle case where Gemini returns partial response (array instead of object)
                # This can happen with the JSON-in-prompt workaround
                if isinstance(content_data, list):
                    logger.warning(
                        "gemini_returned_array_instead_of_object",
                        message="Gemini returned array instead of full object schema. Using as competitors array."
                    )
                    # Treat the array as the competitors field
                    content_data = {
                        "competitors": content_data,
                        "additional_keywords": [],
                        "market_topics": []
                    }
                elif not isinstance(content_data, dict):
                    logger.error(
                        "gemini_returned_unexpected_type",
                        type=type(content_data).__name__
                    )
                    content_data = {
                        "competitors": [],
                        "additional_keywords": [],
                        "market_topics": []
                    }

                logger.info("stage2_step6_building_result")

                # Build result with limits enforced
                result = {
                    "competitors": content_data.get("competitors", [])[:max_competitors],
                    "additional_keywords": content_data.get("additional_keywords", [])[:50],
                    "market_topics": content_data.get("market_topics", [])[:20],
                    "cost": result_raw.get("cost", 0.0)
                }

                # Phase B: Optional RSS feed discovery from competitors
                if discover_feeds and result["competitors"]:
                    logger.info("stage2_step7_discovering_competitor_feeds", competitors_count=len(result["competitors"]))

                    # Extract competitor URLs
                    competitor_urls = [comp.get("url") for comp in result["competitors"] if comp.get("url")]

                    if competitor_urls:
                        # Get domain/vertical hints from customer info
                        hint_domain = customer_info.get("domain")
                        hint_vertical = customer_info.get("vertical")

                        # Discover RSS feeds
                        feed_result = await self.discover_competitor_feeds(
                            competitor_urls=competitor_urls,
                            hint_domain=hint_domain,
                            hint_vertical=hint_vertical
                        )

                        # Add feed discovery results to output
                        result["rss_feeds"] = feed_result
                        result["cost"] += feed_result.get("cost", 0.0)

                        logger.info(
                            "competitor_feeds_discovered",
                            feeds_added=feed_result["feeds_added"],
                            feeds_discovered=feed_result["feeds_discovered"]
                        )
                    else:
                        logger.warning("no_competitor_urls_found", message="Competitors found but no valid URLs")
                        result["rss_feeds"] = {
                            "feeds_discovered": 0,
                            "feeds_added": 0,
                            "feeds": [],
                            "cost": 0.0
                        }

                logger.info(
                    "stage2_step8_COMPLETE_SUCCESS",
                    competitors_count=len(result["competitors"]),
                    additional_keywords_count=len(result["additional_keywords"]),
                    market_topics_count=len(result["market_topics"]),
                    rss_feeds_discovered=result.get("rss_feeds", {}).get("feeds_discovered", 0) if discover_feeds else "disabled",
                    cost=f"${result['cost']:.4f}"
                )

                return result

            except Exception as gemini_error:
                # Check if it's a rate limit error (429 status code in error message)
                error_str = str(gemini_error).lower()
                is_rate_limit = (
                    "429" in error_str or
                    "rate" in error_str or
                    "quota" in error_str or
                    "limit" in error_str
                )

                if is_rate_limit:
                    logger.warning("gemini_rate_limit_detected", error=str(gemini_error))

                    # Track failed free API call
                    self.cost_tracker.track_call(
                        api_type=APIType.GEMINI_FREE,
                        stage="stage2",
                        success=False,
                        cost=0.0,
                        error="Rate limit exceeded"
                    )

                    # FALLBACK: Try Tavily API
                    logger.info("stage2_fallback_to_tavily")
                    tavily_result = await self._research_competitors_with_tavily(
                        keywords=keywords,
                        customer_info=customer_info,
                        max_competitors=max_competitors
                    )

                    # Track fallback call
                    if not tavily_result.get("error"):
                        self.cost_tracker.track_call(
                            api_type=APIType.TAVILY,
                            stage="stage2",
                            success=True,
                            cost=tavily_result.get("cost", 0.0)
                        )
                    else:
                        self.cost_tracker.track_call(
                            api_type=APIType.TAVILY,
                            stage="stage2",
                            success=False,
                            cost=0.0,
                            error=tavily_result.get("error")
                        )

                    return tavily_result
                else:
                    # Non-rate-limit error, raise
                    raise

        except GeminiAgentError as e:
            logger.error("gemini_api_failed", error=str(e))

            # Track failed API call
            self.cost_tracker.track_call(
                api_type=APIType.GEMINI_FREE,
                stage="stage2",
                success=False,
                cost=0.0,
                error=str(e)
            )

            return {
                "competitors": [],
                "additional_keywords": [],
                "market_topics": [],
                "cost": 0.0,
                "error": f"Gemini API failed: {str(e)}"
            }
        except Exception as e:
            logger.error("stage2_failed", error=str(e), exc_info=True)
            return {
                "competitors": [],
                "additional_keywords": [],
                "market_topics": [],
                "cost": 0.0,
                "error": f"Competitor research failed: {str(e)}"
            }

    def consolidate_keywords_and_topics(
        self,
        website_data: Dict,
        competitor_data: Dict
    ) -> Dict:
        """
        Stage 3: Consolidate keywords and tags into unified topic list.

        Combines:
        - Website keywords + tags
        - Competitor keywords
        - Market topics

        Deduplicates and prioritizes by relevance.

        Args:
            website_data: Output from stage 1
            competitor_data: Output from stage 2

        Returns:
            Dict with:
                - consolidated_keywords: List[str] - All unique keywords
                - consolidated_tags: List[str] - All unique tags/topics
                - priority_topics: List[str] - Top topics to research
        """
        logger.info("stage3_consolidation")

        # Combine all keywords
        all_keywords = set()
        all_keywords.update(website_data.get("keywords", []))
        all_keywords.update(competitor_data.get("additional_keywords", []))

        # Combine all tags/topics
        all_tags = set()
        all_tags.update(website_data.get("tags", []))
        all_tags.update(website_data.get("themes", []))
        all_tags.update(competitor_data.get("market_topics", []))

        # Priority topics (combination of keywords + market trends)
        priority_topics = []
        priority_topics.extend(competitor_data.get("market_topics", [])[:5])
        priority_topics.extend(website_data.get("themes", [])[:3])

        result = {
            "consolidated_keywords": sorted(list(all_keywords)),
            "consolidated_tags": sorted(list(all_tags)),
            "priority_topics": priority_topics
        }

        logger.info(
            "stage3_complete",
            keywords_count=len(result["consolidated_keywords"]),
            tags_count=len(result["consolidated_tags"]),
            priority_topics_count=len(result["priority_topics"])
        )

        return result

    async def _translate_topics(
        self,
        topics: List[str],
        target_language: str = "de"
    ) -> List[str]:
        """
        Translate topic titles to target language using Gemini (FREE).

        Args:
            topics: List of topic titles in English
            target_language: Target language code (e.g., "de", "fr", "es")

        Returns:
            List of translated topic titles
        """
        if not topics:
            return []

        # Language map
        lang_names = {
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "it": "Italian",
            "en": "English"
        }
        target_lang_name = lang_names.get(target_language, target_language)

        prompt = f"""Translate these topic titles to {target_lang_name}. Keep them concise and relevant.

Topics to translate:
{chr(10).join(f"{i+1}. {topic}" for i, topic in enumerate(topics))}

Return ONLY a JSON array of translated titles in the same order:
["Translated title 1", "Translated title 2", ...]"""

        try:
            import json
            response_schema = {
                "type": "array",
                "items": {"type": "string"}
            }

            response = await self.gemini_agent.generate_async(
                prompt=prompt,
                response_schema=response_schema,
                temperature=0.3  # Low temp for accurate translation
            )

            translated = json.loads(response['content'])
            return translated[:len(topics)]  # Ensure same length

        except Exception as e:
            logger.error("translation_failed", error=str(e))
            return topics  # Fallback to original

    async def discover_relevant_sources(
        self,
        keywords: List[str],
        domain: str,
        vertical: str,
        market: str,
        language: str = "en"
    ) -> Dict:
        """
        Stage 3.5: Intelligently discover relevant sources using LLM.

        Uses Gemini (FREE with grounding) to find:
        - Relevant subreddits for the niche
        - Relevant RSS feeds/blogs
        - Related topic angles

        Args:
            keywords: Top keywords from consolidation
            domain: Business domain (e.g., "SaaS", "E-commerce")
            vertical: Industry vertical (e.g., "PropTech", "FinTech")
            market: Target market (e.g., "Germany", "US")
            language: Content language (default: "en")

        Returns:
            Dict with:
                - subreddits: List[str] - Relevant subreddit names
                - rss_feeds: List[str] - Relevant RSS feed URLs
                - topic_angles: List[str] - Creative topic ideas from LLM
                - cost: float - Processing cost (FREE)
        """
        logger.info(
            "stage3_5_source_discovery",
            keywords=keywords[:5],
            domain=domain,
            vertical=vertical,
            market=market
        )

        prompt = f"""You are an expert content strategist. Given these keywords and context, suggest relevant content sources and topic ideas.

**Context**:
- Keywords: {', '.join(keywords[:10])}
- Domain: {domain}
- Vertical: {vertical}
- Market: {market}
- Language: {language}

**Task 1 - Find Relevant Subreddits** (5-10):
Suggest active, relevant subreddits (without r/ prefix). Include:
- Broad subreddits for the vertical (e.g., "PropTech", "realestate")
- Language-specific subreddits if market is not US (e.g., "de_EDV" for German tech)
- Related professional communities (e.g., "SaaS", "startups")

**Task 2 - Suggest RSS Feeds/Blogs** (5-10):
Suggest popular blogs and RSS feed topics for this niche. Focus on:
- Industry-leading blogs
- News aggregators for the vertical
- Regional/language-specific publications

**Task 3 - Generate Creative Topic Angles** (10-15):
Based on the keywords, create diverse, engaging article topics. Make them:
- Actionable and specific (not generic)
- Relevant to the keywords
- Varied in scope (how-to, trends, case studies, comparisons)
- In {language} language

Return JSON:
{{
  "subreddits": ["subreddit1", "subreddit2", ...],
  "rss_feed_suggestions": ["Blog name 1", "Blog name 2", ...],
  "topic_angles": ["Topic 1", "Topic 2", ...]
}}"""

        try:
            # Define JSON schema for structured output
            response_schema = {
                "type": "object",
                "properties": {
                    "subreddits": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of relevant subreddit names (without r/ prefix)"
                    },
                    "rss_feed_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of popular blog/RSS feed names"
                    },
                    "topic_angles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of creative topic ideas in target language"
                    }
                },
                "required": ["subreddits", "rss_feed_suggestions", "topic_angles"]
            }

            # Call Gemini with grounding (FREE) - use generate_async
            response = await self.gemini_agent.generate_async(
                prompt=prompt,
                response_schema=response_schema,
                enable_grounding=True,
                temperature=0.7  # Higher temp for creativity
            )

            # Parse JSON from response content
            import json
            result = json.loads(response['content'])

            # Validate and clean
            subreddits = result.get("subreddits", [])[:10]
            rss_suggestions = result.get("rss_feed_suggestions", [])[:10]
            topic_angles = result.get("topic_angles", [])[:15]

            logger.info(
                "source_discovery_complete",
                subreddits_found=len(subreddits),
                rss_found=len(rss_suggestions),
                topics_generated=len(topic_angles),
                cost=response.get('cost', 0.0)
            )

            return {
                "subreddits": subreddits,
                "rss_feed_suggestions": rss_suggestions,
                "topic_angles": topic_angles,
                "cost": response.get('cost', 0.0)
            }

        except Exception as e:
            logger.warning(
                "source_discovery_failed",
                error=str(e),
                message="Returning empty sources"
            )
            return {
                "subreddits": [],
                "rss_feed_suggestions": [],
                "topic_angles": [],
                "cost": 0.0
            }

    async def discover_topics_from_collectors(
        self,
        consolidated_keywords: List[str],
        consolidated_tags: List[str],
        max_topics_per_collector: int = 10,
        domain: str = "General",
        vertical: str = "Research",
        market: str = "US",
        language: str = "en",
        english_ratio: float = 0.70
    ) -> Dict:
        """
        Stage 4: Feed consolidated keywords to collectors for topic discovery.

        Collectors:
        - Autocomplete expansion: Google autocomplete questions (high-value, low-noise)
        - Trend queries: Google Trends trending + related queries (real-time trends)
        - LLM expansion: Creative topic ideas from Gemini (FREE, diverse)
        - Keywords: Direct use of extracted keywords (baseline)
        - Tags: Direct use of semantic tags (high-level concepts)
        - Compound: Meaningful keyword combinations

        Args:
            consolidated_keywords: Keywords from Stage 3
            consolidated_tags: Tags from Stage 3
            max_topics_per_collector: Max topics per collector (default: 10)
            domain: Business domain (e.g., "SaaS")
            vertical: Industry vertical (e.g., "PropTech")
            market: Target market (e.g., "Germany")
            language: Content language (e.g., "de")
            english_ratio: Ratio of English sources to local language sources (0.0-1.0)
                          - 0.90 = Global/Tech topics (90% English, 10% local)
                          - 0.70 = Industry topics (70% English, 30% local) ⭐ RECOMMENDED DEFAULT
                          - 0.40 = National topics (40% English, 60% local - law, regulations)
                          - 0.20 = Hyper-local (20% English, 80% local - city news, local events)

        Returns:
            Dict with:
                - discovered_topics: List[str] - Discovered topic candidates
                - topics_by_source: Dict[str, List[str]] - Topics grouped by source
                - total_topics: int - Total discovered topics
        """
        logger.info(
            "stage4_topic_discovery",
            keywords_count=len(consolidated_keywords),
            tags_count=len(consolidated_tags),
            autocomplete_enabled=self.enable_autocomplete,
            trends_enabled=self.enable_trends,
            domain=domain,
            vertical=vertical
        )

        # Use top keywords and tags as seed
        seed_keywords = consolidated_keywords[:15]
        seed_tags = consolidated_tags[:10]

        topics_by_source = {}

        # 1. Use keywords directly as topics (actual meaningful terms)
        keyword_topics = seed_keywords[:max_topics_per_collector]
        topics_by_source["keywords"] = keyword_topics

        # 2. Use tags/themes as topics (high-level concepts)
        tag_topics = seed_tags[:max_topics_per_collector]
        topics_by_source["tags"] = tag_topics

        # 3. Compound topics - DISABLED (redundant with LLM/Reddit/Trends)
        # Keyword permutations don't provide value when we have AI-generated topics
        topics_by_source["compound"] = []

        # 4. Google Autocomplete - Questions people actually ask
        if self.autocomplete_collector:
            try:
                logger.info("collecting_autocomplete_topics", seed_count=len(seed_keywords))
                # Use QUESTIONS only by default (high value, low noise)
                autocomplete_docs = self.autocomplete_collector.collect_suggestions(
                    seed_keywords=seed_keywords[:5],  # Limit to top 5 to avoid rate limits
                    expansion_types=[ExpansionType.QUESTIONS],  # Questions only
                    max_per_keyword=max_topics_per_collector
                )

                # Extract topic titles from Documents
                autocomplete_topics = [doc.title for doc in autocomplete_docs[:max_topics_per_collector]]
                topics_by_source["autocomplete"] = autocomplete_topics

                logger.info(
                    "autocomplete_collection_complete",
                    topics_found=len(autocomplete_topics),
                    docs_collected=len(autocomplete_docs)
                )
            except Exception as e:
                logger.warning("autocomplete_collection_failed", error=str(e))
                topics_by_source["autocomplete"] = []

        # 5. Google Trends - Trending topics and related queries
        if self.trends_collector:
            try:
                logger.info("collecting_trends_topics", seed_count=len(seed_keywords))

                # Collect related queries for top keywords
                trends_docs = []
                for keyword in seed_keywords[:3]:  # Top 3 keywords to avoid rate limits
                    try:
                        related_docs = self.trends_collector.collect_related_queries(
                            keywords=[keyword],
                            query_type='top'  # Top related queries
                        )
                        trends_docs.extend(related_docs)
                    except Exception as e:
                        logger.warning("trends_related_query_failed", keyword=keyword, error=str(e))

                # Extract topic titles from Documents
                trends_topics = [doc.title for doc in trends_docs[:max_topics_per_collector]]
                topics_by_source["trends"] = trends_topics

                logger.info(
                    "trends_collection_complete",
                    topics_found=len(trends_topics),
                    docs_collected=len(trends_docs)
                )
            except Exception as e:
                logger.warning("trends_collection_failed", error=str(e))
                topics_by_source["trends"] = []

        # 6. LLM Topic Expansion + Dynamic Source Discovery (FREE with Gemini)
        source_discovery = None
        try:
            logger.info("discovering_sources_and_topics", seed_count=len(seed_keywords))

            # Call intelligent source discovery for topic angles AND source suggestions
            source_discovery = await self.discover_relevant_sources(
                keywords=seed_keywords,
                domain=domain,
                vertical=vertical,
                market=market,
                language=language
            )

            # Use the LLM-generated topic angles
            llm_topics = source_discovery["topic_angles"][:max_topics_per_collector]
            topics_by_source["llm"] = llm_topics

            logger.info(
                "llm_topic_expansion_complete",
                topics_generated=len(llm_topics),
                suggested_subreddits=len(source_discovery["subreddits"]),
                suggested_feeds=len(source_discovery["rss_feed_suggestions"]),
                cost=source_discovery["cost"]
            )
        except Exception as e:
            logger.warning("llm_topic_expansion_failed", error=str(e))
            topics_by_source["llm"] = []

        # 7. Reddit - Collect from dynamically discovered subreddits
        if source_discovery and source_discovery["subreddits"]:
            try:
                from src.collectors.reddit_collector import RedditCollector

                logger.info("collecting_reddit_topics", subreddits=source_discovery["subreddits"][:3])

                # Initialize Reddit collector
                reddit_collector = RedditCollector(
                    config=self._collector_config,
                    db_manager=self._db_manager,
                    deduplicator=self._deduplicator
                )

                # Collect from top 3 suggested subreddits
                reddit_docs = []
                for subreddit in source_discovery["subreddits"][:3]:
                    try:
                        docs = reddit_collector.collect_from_subreddit(
                            subreddit_name=subreddit,
                            sort='hot',
                            limit=10,
                            min_score=5  # Quality filter
                        )
                        reddit_docs.extend(docs)
                    except Exception as e:
                        logger.warning("reddit_subreddit_failed", subreddit=subreddit, error=str(e))

                # Extract topic titles
                reddit_topics = [doc.title for doc in reddit_docs[:max_topics_per_collector]]

                # Translate to target language if not English
                if language != "en" and reddit_topics:
                    logger.info("translating_reddit_topics", count=len(reddit_topics), target_lang=language)
                    try:
                        translated_topics = await self._translate_topics(reddit_topics, target_language=language)
                        topics_by_source["reddit"] = translated_topics
                        logger.info("reddit_translation_complete", topics_count=len(translated_topics))
                    except Exception as e:
                        logger.warning("reddit_translation_failed", error=str(e), fallback="using_english")
                        topics_by_source["reddit"] = reddit_topics  # Fallback to English
                else:
                    topics_by_source["reddit"] = reddit_topics

                logger.info(
                    "reddit_collection_complete",
                    topics_found=len(topics_by_source["reddit"]),
                    docs_collected=len(reddit_docs)
                )
            except Exception as e:
                logger.warning("reddit_collection_failed", error=str(e))
                topics_by_source["reddit"] = []

        # 8. News - Search for keywords in news
        if source_discovery:
            try:
                from src.collectors.thenewsapi_collector import TheNewsAPICollector

                logger.info("collecting_news_topics", keywords=seed_keywords[:3])

                # Initialize News collector
                news_collector = TheNewsAPICollector(
                    config=self._collector_config,
                    db_manager=self._db_manager,
                    deduplicator=self._deduplicator
                )

                # Search news for top keywords
                news_docs = []
                for keyword in seed_keywords[:2]:  # Top 2 keywords to avoid quota limits
                    try:
                        docs = await news_collector.collect(
                            query=keyword,
                            categories=["tech", "business"],
                            limit=10
                        )
                        news_docs.extend(docs)
                    except Exception as e:
                        logger.warning("news_keyword_failed", keyword=keyword, error=str(e))

                # Extract topic titles
                news_topics = [doc.title for doc in news_docs[:max_topics_per_collector]]

                # Translate to target language if not English
                if language != "en" and news_topics:
                    logger.info("translating_news_topics", count=len(news_topics), target_lang=language)
                    try:
                        translated_topics = await self._translate_topics(news_topics, target_language=language)
                        topics_by_source["news"] = translated_topics
                        logger.info("news_translation_complete", topics_count=len(translated_topics))
                    except Exception as e:
                        logger.warning("news_translation_failed", error=str(e), fallback="using_english")
                        topics_by_source["news"] = news_topics  # Fallback to English
                else:
                    topics_by_source["news"] = news_topics

                logger.info(
                    "news_collection_complete",
                    topics_found=len(topics_by_source["news"]),
                    docs_collected=len(news_docs)
                )
            except Exception as e:
                logger.warning("news_collection_failed", error=str(e))
                topics_by_source["news"] = []

        # 9. RSS - Collect from dynamic feeds (Bing News, Google News) + curated database
        # Supports multilingual strategy with configurable English/Local ratio
        if self.enable_rss:
            try:
                from src.collectors.rss_collector import RSSCollector
                from src.collectors.dynamic_feed_generator import DynamicFeedGenerator
                from src.collectors.rss_feed_database import RSSFeedDatabase

                logger.info(
                    "collecting_rss_topics",
                    keywords=seed_keywords[:3],
                    domain=domain,
                    vertical=vertical,
                    language=language,
                    english_ratio=english_ratio if language != "en" else 1.0
                )

                # Initialize RSS collector
                rss_collector = RSSCollector(
                    config=self._collector_config,
                    db_manager=self._db_manager,
                    deduplicator=self._deduplicator
                )

                dynamic_gen = DynamicFeedGenerator()

                # Multilingual strategy: Mix English and local language sources
                if language != "en":
                    # Calculate topic distribution (70/30 default)
                    english_topics_count = int(max_topics_per_collector * english_ratio)
                    local_topics_count = max_topics_per_collector - english_topics_count

                    logger.info(
                        "rss_multilingual_strategy",
                        english_topics=english_topics_count,
                        local_topics=local_topics_count,
                        ratio=f"{int(english_ratio*100)}/{int((1-english_ratio)*100)}"
                    )

                    # Collect from ENGLISH sources (latest trends, more abundant)
                    english_feed_urls = []
                    for keyword in seed_keywords[:2]:  # Top 2 keywords for English
                        try:
                            bing_feed = dynamic_gen.generate_bing_news_feed(
                                query=keyword,
                                language="en",
                                region="US"
                            )
                            english_feed_urls.append(bing_feed.url)

                            google_feed = dynamic_gen.generate_google_news_feed(
                                query=keyword,
                                language="en",
                                region="US"
                            )
                            english_feed_urls.append(google_feed.url)
                        except Exception as e:
                            logger.warning("english_feed_generation_failed", keyword=keyword, error=str(e))

                    # Collect from LOCAL language sources (regional relevance)
                    local_feed_urls = []
                    for keyword in seed_keywords[:2]:  # Top 2 keywords for local
                        try:
                            bing_feed = dynamic_gen.generate_bing_news_feed(
                                query=keyword,
                                language=language,
                                region=market if len(market) == 2 else "US"
                            )
                            local_feed_urls.append(bing_feed.url)

                            google_feed = dynamic_gen.generate_google_news_feed(
                                query=keyword,
                                language=language,
                                region=market if len(market) == 2 else "US"
                            )
                            local_feed_urls.append(google_feed.url)
                        except Exception as e:
                            logger.warning("local_feed_generation_failed", keyword=keyword, error=str(e))

                    # Collect English topics
                    english_docs = []
                    for feed_url in english_feed_urls[:5]:  # Limit English feeds
                        try:
                            docs = rss_collector.collect_from_feed(feed_url=feed_url)
                            english_docs.extend(docs[:english_topics_count])  # Slice to limit
                        except Exception as e:
                            logger.warning("english_feed_collection_failed", feed_url=feed_url, error=str(e))

                    # Collect local topics
                    local_docs = []
                    for feed_url in local_feed_urls[:5]:  # Limit local feeds
                        try:
                            docs = rss_collector.collect_from_feed(feed_url=feed_url)
                            local_docs.extend(docs[:local_topics_count])  # Slice to limit
                        except Exception as e:
                            logger.warning("local_feed_collection_failed", feed_url=feed_url, error=str(e))

                    # Extract and mix topics
                    english_topics = [doc.title for doc in english_docs[:english_topics_count]]
                    local_topics = [doc.title for doc in local_docs[:local_topics_count]]

                    # Translate English topics to target language
                    if english_topics:
                        try:
                            translated_english = await self._translate_topics(english_topics, target_language=language)
                            rss_topics = translated_english + local_topics
                            logger.info(
                                "rss_multilingual_mix",
                                english_translated=len(translated_english),
                                local_native=len(local_topics),
                                total=len(rss_topics)
                            )
                        except Exception as e:
                            logger.warning("english_translation_failed", error=str(e))
                            rss_topics = english_topics + local_topics  # Fallback: mix without translation
                    else:
                        rss_topics = local_topics

                    topics_by_source["rss"] = rss_topics

                else:
                    # English content: Standard collection
                    feed_urls = []
                    for keyword in seed_keywords[:3]:  # Top 3 keywords
                        try:
                            bing_feed = dynamic_gen.generate_bing_news_feed(
                                query=keyword,
                                language="en",
                                region=market if len(market) == 2 else "US"
                            )
                            feed_urls.append(bing_feed.url)

                            google_feed = dynamic_gen.generate_google_news_feed(
                                query=keyword,
                                language="en",
                                region=market if len(market) == 2 else "US"
                            )
                            feed_urls.append(google_feed.url)
                        except Exception as e:
                            logger.warning("dynamic_feed_generation_failed", keyword=keyword, error=str(e))

                    # Add curated feeds from database
                    if domain and vertical and domain.lower() != "general":
                        try:
                            feed_db = RSSFeedDatabase()
                            curated_feeds = feed_db.get_feeds(
                                domain=domain.lower(),
                                vertical=vertical.lower(),
                                min_quality_score=0.6,
                                limit=5
                            )
                            feed_urls.extend([feed["url"] for feed in curated_feeds])
                            logger.info("added_curated_feeds", count=len(curated_feeds), domain=domain, vertical=vertical)
                        except Exception as e:
                            logger.warning("curated_feed_selection_failed", error=str(e))

                    # Collect documents
                    rss_docs = []
                    for feed_url in feed_urls[:10]:
                        try:
                            docs = rss_collector.collect_from_feed(feed_url=feed_url)
                            rss_docs.extend(docs[:5])  # Limit to 5 articles per feed
                        except Exception as e:
                            logger.warning("rss_feed_collection_failed", feed_url=feed_url, error=str(e))

                    rss_topics = [doc.title for doc in rss_docs[:max_topics_per_collector]]
                    topics_by_source["rss"] = rss_topics

                logger.info(
                    "rss_collection_complete",
                    topics_found=len(topics_by_source["rss"]),
                    language=language,
                    english_ratio=english_ratio if language != "en" else 1.0
                )
            except Exception as e:
                logger.warning("rss_collection_failed", error=str(e))
                topics_by_source["rss"] = []

        # Aggregate and deduplicate
        all_topics = set()
        for topics in topics_by_source.values():
            all_topics.update(topics)

        discovered_topics = sorted(list(all_topics))

        result = {
            "discovered_topics": discovered_topics,
            "topics_by_source": topics_by_source,
            "total_topics": len(discovered_topics)
        }

        logger.info(
            "stage4_complete",
            total_topics=result["total_topics"],
            autocomplete=len(topics_by_source.get("autocomplete", [])),
            trends=len(topics_by_source.get("trends", [])),
            llm=len(topics_by_source.get("llm", [])),
            reddit=len(topics_by_source.get("reddit", [])),
            news=len(topics_by_source.get("news", [])),
            rss=len(topics_by_source.get("rss", [])),
            keywords=len(topics_by_source.get("keywords", [])),
            tags=len(topics_by_source.get("tags", [])),
            compound=len(topics_by_source.get("compound", []))
        )

        return result

    def validate_and_score_topics(
        self,
        discovered_topics: List[str],
        topics_by_source: Dict[str, List[str]],
        consolidated_keywords: List[str],
        threshold: float = 0.6,
        top_n: int = 20
    ) -> Dict:
        """
        Stage 4.5: Validate and score discovered topics using 5-metric scoring.

        Filters topics by relevance before expensive research operations.
        Uses TopicValidator with:
        - Keyword relevance (30%)
        - Source diversity (25%)
        - Freshness (20%)
        - Search volume (15%)
        - Novelty (10%)

        Args:
            discovered_topics: Topics from Stage 4
            topics_by_source: Topics grouped by source
            consolidated_keywords: Keywords from Stage 3
            threshold: Minimum score threshold (0.0-1.0, default: 0.6)
            top_n: Maximum topics to return (default: 20)

        Returns:
            Dict with:
                - scored_topics: List[ScoredTopic] - Validated topics
                - filtered_count: int - Topics that passed threshold
                - rejected_count: int - Topics that failed threshold
                - avg_score: float - Average score of validated topics
        """
        logger.info(
            "stage4_5_topic_validation",
            total_topics=len(discovered_topics),
            threshold=threshold,
            top_n=top_n
        )

        # Create topic metadata for scoring
        topics_with_metadata = []
        now = datetime.now()

        for topic in discovered_topics:
            # Find which sources discovered this topic
            sources = []
            for source, source_topics in topics_by_source.items():
                if topic in source_topics:
                    sources.append(source)

            # Create metadata
            metadata = TopicMetadata(
                source=sources[0] if sources else "unknown",
                timestamp=now,
                sources=sources
            )

            topics_with_metadata.append((topic, metadata))

        # Score and filter topics
        scored_topics = self.topic_validator.filter_topics(
            topics=topics_with_metadata,
            keywords=consolidated_keywords,
            threshold=threshold,
            top_n=top_n
        )

        # Calculate statistics
        avg_score = (
            sum(st.total_score for st in scored_topics) / len(scored_topics)
            if scored_topics else 0.0
        )
        rejected_count = len(discovered_topics) - len(scored_topics)

        result = {
            "scored_topics": scored_topics,
            "filtered_count": len(scored_topics),
            "rejected_count": rejected_count,
            "avg_score": avg_score
        }

        logger.info(
            "stage4_5_complete",
            filtered_topics=result["filtered_count"],
            rejected_topics=result["rejected_count"],
            avg_score=f"{avg_score:.3f}"
        )

        return result

    async def research_topic(
        self,
        topic: str,
        config: Dict,
        brand_tone: Optional[List[str]] = None,
        generate_images: Optional[bool] = None,
        max_results: int = 10,
        keywords: Optional[List[str]] = None,
        themes: Optional[List[str]] = None
    ) -> Dict:
        """
        Stage 5: Research single topic through NEW pipeline.

        Flow: DeepResearcher → MultiStageReranker → ContentSynthesizer
        Cost: ~$0.01/topic (+ $0.16 if images enabled)

        Args:
            topic: Topic to research
            config: Market configuration (dict or Pydantic)
            brand_tone: Brand tone extracted from website (e.g., ['Professional', 'Technical'])
            generate_images: Whether to generate images (None = inherit from config)
            max_results: Max sources to collect (default: 10)
            keywords: Key concepts from website analysis (for image context)
            themes: Main themes from website analysis (for image context)

        Returns:
            Dict with:
                - topic: str
                - sources: List[Dict] - Reranked sources
                - article: Optional[str] - Generated article
                - hero_image_url: Optional[str] - Hero image URL (if images enabled)
                - supporting_images: List[Dict] - Supporting images (if images enabled)
                - image_cost: float - Image generation cost
                - cost: float - Total cost
                - duration_sec: float - Processing time
        """
        logger.info("stage5_topic_research", topic=topic)
        start_time = datetime.now()
        total_cost = 0.0

        # Resolve image generation preference
        if generate_images is None:
            # Inherit from market config
            generate_images = config.get("enable_image_generation", True)

        # Step 1: Research (multi-backend)
        research_result = await self.researcher.research_topic(topic=topic, config=config)
        sources = research_result.get("sources", [])
        logger.info("research_complete", sources_count=len(sources))

        # Step 2: Rerank (3-stage)
        if self.reranker and sources:
            sources = await self.reranker.rerank(
                query=topic,
                sources=sources,
                config=config
            )
            logger.info("reranking_complete", sources_count=len(sources))

        # Step 3: Synthesize (BM25→LLM + optional image generation)
        article = None
        hero_image_url = None
        hero_image_alt = None
        supporting_images = []
        image_cost = 0.0

        if self.synthesizer and sources:
            synthesis_result = await self.synthesizer.synthesize(
                query=topic,
                sources=sources,
                config=config,
                brand_tone=brand_tone,
                generate_images=generate_images,
                keywords=keywords,
                themes=themes
            )
            article = synthesis_result.get("article")
            hero_image_url = synthesis_result.get("hero_image_url")
            hero_image_alt = synthesis_result.get("hero_image_alt")
            supporting_images = synthesis_result.get("supporting_images", [])
            image_cost = synthesis_result.get("image_cost", 0.0)
            total_cost += synthesis_result.get("cost", 0.0) + image_cost
            logger.info("synthesis_complete", word_count=synthesis_result.get("word_count", 0), image_cost=image_cost)

        duration = (datetime.now() - start_time).total_seconds()

        return {
            "topic": topic,
            "sources": sources,
            "article": article,
            "hero_image_url": hero_image_url,
            "hero_image_alt": hero_image_alt,
            "supporting_images": supporting_images,
            "image_cost": image_cost,
            "cost": total_cost,
            "duration_sec": duration
        }

    async def run_pipeline(
        self,
        website_url: str,
        customer_info: Dict,
        max_topics_to_research: int = 5,
        discover_competitor_feeds: bool = False
    ) -> Dict:
        """
        Run complete hybrid pipeline.

        Args:
            website_url: Customer's website URL
            customer_info: Dict with market, vertical, language, domain
            max_topics_to_research: Max topics to research (default: 5)
            discover_competitor_feeds: Enable Phase B feed discovery (default: False)

        Returns:
            Dict with:
                - website_data: Stage 1 results
                - competitor_data: Stage 2 results (includes rss_feeds if enabled)
                - consolidated_data: Stage 3 results
                - research_results: List[Dict] - Stage 5 results for each topic
                - total_cost: float - Total pipeline cost
                - total_duration_sec: float - Total processing time
        """
        logger.info(
            "pipeline_start",
            website_url=website_url,
            market=customer_info.get("market"),
            max_topics=max_topics_to_research,
            discover_feeds=discover_competitor_feeds
        )
        start_time = datetime.now()
        total_cost = 0.0

        # Stage 1: Extract website keywords
        website_data = await self.extract_website_keywords(website_url)
        total_cost += website_data.get("cost", 0.0)

        # Stage 2: Research competitors (+ Phase B: Optional RSS feed discovery)
        competitor_data = await self.research_competitors(
            keywords=website_data["keywords"],
            customer_info=customer_info,
            discover_feeds=discover_competitor_feeds
        )
        total_cost += competitor_data.get("cost", 0.0)

        # Stage 3: Consolidate
        consolidated_data = self.consolidate_keywords_and_topics(
            website_data=website_data,
            competitor_data=competitor_data
        )

        # Stage 4: Feed to collectors - discover topics from keywords
        discovered_topics_data = await self.discover_topics_from_collectors(
            consolidated_keywords=consolidated_data["consolidated_keywords"],
            consolidated_tags=consolidated_data["consolidated_tags"],
            max_topics_per_collector=10
        )

        # Stage 4.5: Validate and score discovered topics
        validation_data = self.validate_and_score_topics(
            discovered_topics=discovered_topics_data["discovered_topics"],
            topics_by_source=discovered_topics_data["topics_by_source"],
            consolidated_keywords=consolidated_data["consolidated_keywords"],
            threshold=0.2,  # Lower threshold to ensure topics pass validation
            top_n=min(max_topics_to_research, 50)  # Increased to 50 for maximum diversity
        )

        # Stage 5: Research validated topics
        # Use scored topics from Stage 4.5 instead of priority topics from Stage 3
        validated_topics = [st.topic for st in validation_data["scored_topics"]][:max_topics_to_research]

        logger.info(
            "stage5_topic_selection",
            validated_topics=len(validated_topics),
            avg_validation_score=validation_data["avg_score"]
        )

        logger.info("stage5_batch_research", topics_count=len(validated_topics))

        # Extract context from website data for image generation
        brand_tone = website_data.get("tone", [])
        keywords = website_data.get("keywords", [])
        themes = website_data.get("themes", [])
        logger.info("context_extracted", tone=brand_tone,
                   keywords_count=len(keywords), themes_count=len(themes))

        research_results = []
        for topic in validated_topics:
            result = await self.research_topic(
                topic=topic,
                config=customer_info,
                brand_tone=brand_tone,
                generate_images=None,  # Inherit from config
                max_results=10,
                keywords=keywords,
                themes=themes
            )
            research_results.append(result)
            total_cost += result.get("cost", 0.0)

        total_duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            "pipeline_complete",
            topics_researched=len(research_results),
            total_cost=f"${total_cost:.4f}",
            total_duration=f"{total_duration:.1f}s"
        )

        return {
            "website_data": website_data,
            "brand_tone": brand_tone,
            "competitor_data": competitor_data,
            "consolidated_data": consolidated_data,
            "discovered_topics_data": discovered_topics_data,
            "validation_data": validation_data,
            "research_results": research_results,
            "total_cost": total_cost,
            "total_duration_sec": total_duration
        }
