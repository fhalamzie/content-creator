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
        max_article_words: int = 2000
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
        """
        self.enable_tavily = enable_tavily
        self.enable_searxng = enable_searxng
        self.enable_gemini = enable_gemini
        self.enable_rss = enable_rss
        self.enable_thenewsapi = enable_thenewsapi
        self.enable_reranking = enable_reranking
        self.enable_synthesis = enable_synthesis
        self.max_article_words = max_article_words

        # Initialize components (lazy loading)
        self._researcher = None
        self._reranker = None
        self._synthesizer = None
        self._gemini_agent = None
        self._topic_validator = None

        logger.info(
            "hybrid_orchestrator_initialized",
            backends=f"{sum([enable_tavily, enable_searxng, enable_gemini])} backends",
            collectors=f"{sum([enable_rss, enable_thenewsapi])} collectors",
            reranking=enable_reranking,
            synthesis=enable_synthesis
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

            # Generate analysis
            logger.info("analyzing_with_gemini", url=website_url)
            result_raw = gemini_agent.generate(
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

    async def research_competitors(
        self,
        keywords: List[str],
        customer_info: Dict,
        max_competitors: int = 10
    ) -> Dict:
        """
        Stage 2: Competitor/market research using extracted keywords.

        Uses Gemini API with grounding (free tier) to:
        - Identify competitors in the market
        - Extract additional keywords from competitor content
        - Discover market topics and trends

        Args:
            keywords: Keywords from stage 1
            customer_info: Dict with market, vertical, language
            max_competitors: Max competitors to analyze (default: 10)

        Returns:
            Dict with:
                - competitors: List[Dict] - Competitor info (name, url, topics)
                - additional_keywords: List[str] - More keywords (max 50)
                - market_topics: List[str] - Trending topics (max 20)
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
            # Build search context from keywords and customer info
            market = customer_info.get("market", "")
            vertical = customer_info.get("vertical", "")
            language = customer_info.get("language", "en")
            domain = customer_info.get("domain", "")

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

            # Call Gemini API with grounding (synchronous method)
            logger.info("calling_gemini_api", grounding=True)
            result_raw = self.gemini_agent.generate(
                prompt=prompt,
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
                "competitors": content_data.get("competitors", [])[:max_competitors],
                "additional_keywords": content_data.get("additional_keywords", [])[:50],
                "market_topics": content_data.get("market_topics", [])[:20],
                "cost": result_raw.get("cost", 0.0)
            }

            logger.info(
                "stage2_complete",
                competitors_count=len(result["competitors"]),
                additional_keywords_count=len(result["additional_keywords"]),
                market_topics_count=len(result["market_topics"]),
                cost=f"${result['cost']:.4f}"
            )

            return result

        except GeminiAgentError as e:
            logger.error("gemini_api_failed", error=str(e))
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

    async def discover_topics_from_collectors(
        self,
        consolidated_keywords: List[str],
        consolidated_tags: List[str],
        max_topics_per_collector: int = 10
    ) -> Dict:
        """
        Stage 4: Feed consolidated keywords to collectors for topic discovery.

        Collectors (simplified implementation - full integration requires DB):
        - Autocomplete expansion: keyword + alphabet/questions/prepositions
        - Trend queries: "{keyword} trends", "{keyword} news"
        - Reddit queries: "{keyword} discussion", "{keyword} questions"
        - RSS queries: "{keyword} blog", "{keyword} article"
        - News queries: "{keyword} latest news"

        This is a lightweight topic discovery mechanism that generates
        candidate topics for research. Full collector integration with
        Document persistence will be added in Phase 2.

        Args:
            consolidated_keywords: Keywords from Stage 3
            consolidated_tags: Tags from Stage 3
            max_topics_per_collector: Max topics per collector (default: 10)

        Returns:
            Dict with:
                - discovered_topics: List[str] - Discovered topic candidates
                - topics_by_source: Dict[str, List[str]] - Topics grouped by source
                - total_topics: int - Total discovered topics
        """
        logger.info(
            "stage4_topic_discovery",
            keywords_count=len(consolidated_keywords),
            tags_count=len(consolidated_tags)
        )

        # Use top keywords for discovery (limit to avoid explosion)
        seed_keywords = consolidated_keywords[:10]
        seed_tags = consolidated_tags[:5]

        topics_by_source = {}

        # 1. Autocomplete-style expansion
        autocomplete_topics = []
        question_prefixes = ['how', 'what', 'why', 'when', 'where', 'best']
        for kw in seed_keywords[:5]:
            for prefix in question_prefixes[:3]:
                autocomplete_topics.append(f"{prefix} {kw}")
        topics_by_source["autocomplete"] = autocomplete_topics[:max_topics_per_collector]

        # 2. Trends-style queries
        trends_topics = []
        trends_suffixes = ['trends', 'innovations', 'future', 'market analysis']
        for kw in seed_keywords[:5]:
            for suffix in trends_suffixes[:2]:
                trends_topics.append(f"{kw} {suffix}")
        topics_by_source["trends"] = trends_topics[:max_topics_per_collector]

        # 3. Reddit-style discussion topics
        reddit_topics = []
        reddit_patterns = ['discussion', 'questions', 'guide', 'tips']
        for kw in seed_keywords[:5]:
            for pattern in reddit_patterns[:2]:
                reddit_topics.append(f"{kw} {pattern}")
        topics_by_source["reddit"] = reddit_topics[:max_topics_per_collector]

        # 4. RSS/Blog-style topics
        rss_topics = []
        rss_suffixes = ['blog', 'article', 'case study', 'best practices']
        for tag in seed_tags[:3]:
            for suffix in rss_suffixes[:2]:
                rss_topics.append(f"{tag} {suffix}")
        topics_by_source["rss"] = rss_topics[:max_topics_per_collector]

        # 5. News-style topics
        news_topics = []
        news_suffixes = ['latest news', 'recent developments', 'updates']
        for kw in seed_keywords[:5]:
            for suffix in news_suffixes[:2]:
                news_topics.append(f"{kw} {suffix}")
        topics_by_source["news"] = news_topics[:max_topics_per_collector]

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
            reddit=len(topics_by_source.get("reddit", [])),
            rss=len(topics_by_source.get("rss", [])),
            news=len(topics_by_source.get("news", []))
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
        max_results: int = 10
    ) -> Dict:
        """
        Stage 5: Research single topic through NEW pipeline.

        Flow: DeepResearcher → MultiStageReranker → ContentSynthesizer
        Cost: ~$0.01/topic

        Args:
            topic: Topic to research
            config: Market configuration (dict or Pydantic)
            max_results: Max sources to collect (default: 10)

        Returns:
            Dict with:
                - topic: str
                - sources: List[Dict] - Reranked sources
                - article: Optional[str] - Generated article
                - cost: float - Total cost
                - duration_sec: float - Processing time
        """
        logger.info("stage5_topic_research", topic=topic)
        start_time = datetime.now()
        total_cost = 0.0

        # Step 1: Research (multi-backend)
        sources = await self.researcher.search(topic, max_results=max_results)
        logger.info("research_complete", sources_count=len(sources))

        # Step 2: Rerank (3-stage)
        if self.reranker and sources:
            sources = await self.reranker.rerank(
                query=topic,
                sources=sources,
                config=config
            )
            logger.info("reranking_complete", sources_count=len(sources))

        # Step 3: Synthesize (BM25→LLM)
        article = None
        if self.synthesizer and sources:
            synthesis_result = await self.synthesizer.synthesize(
                query=topic,
                sources=sources,
                config=config
            )
            article = synthesis_result.get("article")
            total_cost += synthesis_result.get("cost", 0.0)
            logger.info("synthesis_complete", word_count=synthesis_result.get("word_count", 0))

        duration = (datetime.now() - start_time).total_seconds()

        return {
            "topic": topic,
            "sources": sources,
            "article": article,
            "cost": total_cost,
            "duration_sec": duration
        }

    async def run_pipeline(
        self,
        website_url: str,
        customer_info: Dict,
        max_topics_to_research: int = 5
    ) -> Dict:
        """
        Run complete hybrid pipeline.

        Args:
            website_url: Customer's website URL
            customer_info: Dict with market, vertical, language, domain
            max_topics_to_research: Max topics to research (default: 5)

        Returns:
            Dict with:
                - website_data: Stage 1 results
                - competitor_data: Stage 2 results
                - consolidated_data: Stage 3 results
                - research_results: List[Dict] - Stage 5 results for each topic
                - total_cost: float - Total pipeline cost
                - total_duration_sec: float - Total processing time
        """
        logger.info(
            "pipeline_start",
            website_url=website_url,
            market=customer_info.get("market"),
            max_topics=max_topics_to_research
        )
        start_time = datetime.now()
        total_cost = 0.0

        # Stage 1: Extract website keywords
        website_data = await self.extract_website_keywords(website_url)
        total_cost += website_data.get("cost", 0.0)

        # Stage 2: Research competitors
        competitor_data = await self.research_competitors(
            keywords=website_data["keywords"],
            customer_info=customer_info
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
            threshold=0.6,
            top_n=min(max_topics_to_research, 20)
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

        research_results = []
        for topic in validated_topics:
            result = await self.research_topic(
                topic=topic,
                config=customer_info,
                max_results=10
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
            "competitor_data": competitor_data,
            "consolidated_data": consolidated_data,
            "discovered_topics_data": discovered_topics_data,
            "validation_data": validation_data,
            "research_results": research_results,
            "total_cost": total_cost,
            "total_duration_sec": total_duration
        }
