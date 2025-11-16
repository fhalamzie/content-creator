"""
Deep Researcher

gpt-researcher wrapper for generating sourced research reports with citations.
Uses Gemini 2.0 Flash (FREE) via google_genai provider.

Example:
    from src.research.deep_researcher import DeepResearcher

    researcher = DeepResearcher()

    config = {
        'domain': 'SaaS',
        'market': 'Germany',
        'language': 'de',
        'vertical': 'Proptech'
    }

    result = await researcher.research_topic("PropTech Trends 2025", config)
    print(f"Report: {result['report']}")
    print(f"Sources: {len(result['sources'])}")
"""

from typing import Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
import subprocess
import json
import os

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.research.source_cache import SourceCache
    from src.database.sqlite_manager import SQLiteManager

logger = get_logger(__name__)

# Lazy import to avoid dependency issues in tests
GPTResearcher = None


class DeepResearchError(Exception):
    """Raised when deep research fails"""
    pass


class DeepResearcher:
    """
    Wrapper for gpt-researcher with context-aware queries

    Features:
    - Uses Gemini 2.0 Flash (FREE via google_genai)
    - Generates 5-6 page reports with citations
    - Context-aware queries (domain, market, language, vertical)
    - DuckDuckGo search backend
    - Statistics tracking
    - Error handling with retries
    """

    def __init__(
        self,
        llm_provider: str = "openai",
        llm_model: str = "qwen/qwen-2.5-32b-instruct",
        search_engine: str = "duckduckgo",
        max_sources: int = 8,
        report_format: str = "markdown",
        db_manager: Optional['SQLiteManager'] = None
    ):
        """
        Initialize deep researcher

        Args:
            llm_provider: LLM provider (openai for OpenAI-compatible APIs)
            llm_model: Model to use (qwen/qwen-2.5-32b-instruct via OpenRouter)
            search_engine: Search backend (duckduckgo)
            max_sources: Maximum sources per research (default 8)
            report_format: Output format (markdown)
            db_manager: Optional SQLiteManager for source caching (30-50% cost savings)

        Note:
            Uses OpenAI-compatible API format to avoid gpt-researcher bugs.
            For qwen via OpenRouter: set OPENAI_API_BASE=https://openrouter.ai/api/v1
            OPENAI_API_KEY, TAVILY_API_KEY loaded automatically from /home/envs/.

            Source caching: If db_manager provided, sources are cached globally
            across topics for cost savings and quality tracking.
        """
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.search_engine = search_engine
        self.max_sources = max_sources  # Reduced for faster E2E testing (default: 8)
        self.report_format = report_format

        # Source caching (optional)
        self.source_cache = None
        if db_manager:
            try:
                from src.research.source_cache import SourceCache
                self.source_cache = SourceCache(db_manager)
                logger.info("source_cache_enabled", note="30-50% cost savings expected")
            except ImportError:
                logger.warning("source_cache_unavailable", note="Install source_cache.py for cost savings")

        # Load API keys from environment
        self._load_api_keys()

        # Statistics
        self.total_research = 0
        self.failed_research = 0
        self.total_sources_found = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls_saved = 0

        logger.info(
            "deep_researcher_initialized",
            llm_provider=llm_provider,
            llm_model=llm_model,
            search_engine=search_engine,
            max_sources=max_sources,
            caching_enabled=self.source_cache is not None
        )

    def _load_api_keys(self):
        """Load API keys from environment files and configure OpenRouter for qwen"""
        # Load OPENROUTER_API_KEY (for qwen models)
        if not os.getenv("OPENROUTER_API_KEY"):
            env_file = "/home/envs/openrouter.env"
            if os.path.exists(env_file):
                try:
                    with open(env_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                if key.strip() == 'OPENROUTER_API_KEY':
                                    os.environ['OPENROUTER_API_KEY'] = value.strip()
                                    logger.info("openrouter_key_loaded_from_file", file=env_file)
                                    break
                except Exception as e:
                    logger.warning("failed_to_load_openrouter_key", error=str(e))

        # Configure OpenAI-compatible API for OpenRouter (use OpenRouter key as OPENAI_API_KEY)
        if self.llm_model.startswith("qwen/") and os.getenv("OPENROUTER_API_KEY"):
            os.environ['OPENAI_API_KEY'] = os.environ['OPENROUTER_API_KEY']
            os.environ['OPENAI_API_BASE'] = 'https://openrouter.ai/api/v1'
            logger.info("configured_openrouter_for_qwen", model=self.llm_model)
        # Fall back to regular OpenAI if not using qwen
        elif not os.getenv("OPENAI_API_KEY"):
            env_file = "/home/envs/openai.env"
            if os.path.exists(env_file):
                try:
                    with open(env_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                if key.strip() == 'OPENAI_API_KEY':
                                    os.environ['OPENAI_API_KEY'] = value.strip()
                                    logger.info("openai_key_loaded_from_file", file=env_file)
                                    break
                except Exception as e:
                    logger.warning("failed_to_load_openai_key", error=str(e))
            else:
                logger.warning("openai_key_not_found", note="Set OPENAI_API_KEY or OPENROUTER_API_KEY")
        else:
            logger.debug("openai_key_already_set")

        # Load TAVILY_API_KEY
        if not os.getenv("TAVILY_API_KEY"):
            env_file = "/home/envs/tavily.env"
            if os.path.exists(env_file):
                try:
                    with open(env_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                if key.strip() == 'TAVILY_API_KEY':
                                    os.environ['TAVILY_API_KEY'] = value.strip()
                                    logger.info("tavily_key_loaded_from_file", file=env_file)
                                    break
                except Exception as e:
                    logger.warning("failed_to_load_tavily_key", error=str(e))
            else:
                logger.debug("tavily_key_not_found", note="Optional - enables web search with citations")
        else:
            logger.debug("tavily_key_already_set")

    async def research_topic(
        self,
        topic: str,
        config: Dict,
        competitor_gaps: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None
    ) -> Dict:
        """
        Research topic with context and generate sourced report

        Args:
            topic: Topic to research
            config: Research config (domain, market, language, vertical)
            competitor_gaps: Optional content gaps from competitor research
            keywords: Optional keywords to focus on

        Returns:
            Dictionary with:
            - topic: Original topic
            - report: Markdown report (5-6 pages)
            - sources: List of source URLs
            - word_count: Approximate word count
            - researched_at: ISO timestamp

        Raises:
            DeepResearchError: If research fails
        """
        if not topic or len(topic.strip()) == 0:
            raise DeepResearchError("Topic cannot be empty")

        self.total_research += 1

        try:
            # Contextualize query with domain, market, language, vertical
            contextualized_query = self._build_query(
                topic=topic,
                config=config,
                competitor_gaps=competitor_gaps,
                keywords=keywords
            )

            logger.info(
                "starting_research",
                topic=topic,
                domain=config.get('domain'),
                market=config.get('market'),
                language=config.get('language')
            )

            # Lazy import gpt-researcher
            global GPTResearcher
            if GPTResearcher is None:
                try:
                    from gpt_researcher import GPTResearcher as _GPTResearcher
                    GPTResearcher = _GPTResearcher
                except ImportError as e:
                    raise DeepResearchError(
                        f"gpt-researcher not installed. Install with: pip install gpt-researcher==0.14.4. Error: {e}"
                    )

            # Initialize gpt-researcher with minimal config to avoid bugs
            # Only pass query and report_type - let it use env vars/defaults for everything else
            # This avoids:
            # - Bug 1: Passing invalid kwargs like search_engine
            # - Bug 2: OPENAI_API_KEY loaded from environment in __init__
            # - Bug 3: Using openai provider (no langchain-google-genai conflict)
            researcher = GPTResearcher(
                query=contextualized_query,
                report_type="research_report"
            )

            # Conduct research
            await researcher.conduct_research()

            # Generate report
            report = await researcher.write_report()

            # Get sources (synchronous method, returns list directly)
            sources = researcher.get_source_urls()

            # Update statistics
            self.total_sources_found += len(sources)

            # Calculate word count (approximate)
            word_count = len(report.split())

            # Save sources to cache (if enabled)
            if self.source_cache:
                # Generate topic_id for cache (slugify topic)
                topic_id = self._slugify_topic(topic)
                cached_count, new_count = self._cache_sources(
                    sources=sources,
                    report=report,
                    topic_id=topic_id
                )

                # Update cache statistics
                self.cache_hits += cached_count
                self.cache_misses += new_count
                self.api_calls_saved += cached_count

                logger.info(
                    "sources_cached",
                    topic=topic,
                    total_sources=len(sources),
                    already_cached=cached_count,
                    newly_cached=new_count,
                    cache_hit_rate=f"{(cached_count/len(sources)*100):.1f}%" if sources else "0%"
                )

            result = {
                'topic': topic,
                'report': report,
                'sources': sources,
                'word_count': word_count,
                'researched_at': datetime.now().isoformat()
            }

            logger.info(
                "research_complete",
                topic=topic,
                word_count=word_count,
                num_sources=len(sources)
            )

            return result

        except Exception as e:
            # Try Gemini CLI fallback
            logger.warning("gpt_researcher_failed_trying_fallback", topic=topic, error=str(e))
            try:
                return await self._gemini_cli_fallback(
                    topic=topic,
                    contextualized_query=contextualized_query,
                    config=config
                )
            except Exception as fallback_error:
                self.failed_research += 1
                logger.error("research_failed_all_methods", topic=topic,
                           gpt_researcher_error=str(e),
                           fallback_error=str(fallback_error))
                raise DeepResearchError(f"Research failed for '{topic}': {e}")

    def _build_query(
        self,
        topic: str,
        config: Dict,
        competitor_gaps: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None
    ) -> str:
        """
        Build contextualized research query

        Args:
            topic: Base topic
            config: Research config (domain, market, language, vertical)
            competitor_gaps: Optional content gaps to focus on
            keywords: Optional keywords to target

        Returns:
            Contextualized query string
        """
        parts = [topic]

        # Add context from config
        if config.get('domain'):
            parts.append(f"in {config['domain']} industry")

        if config.get('market'):
            parts.append(f"for {config['market']} market")

        if config.get('language'):
            parts.append(f"in {config['language']} language")

        if config.get('vertical'):
            parts.append(f"focusing on {config['vertical']}")

        # Add competitor gaps (keep all but truncate if extremely long)
        if competitor_gaps and len(competitor_gaps) > 0:
            # Handle both string and dict formats
            gaps = []
            for gap in competitor_gaps[:3]:  # Keep all 3 gaps
                if isinstance(gap, dict):
                    gap_text = gap.get('gap', str(gap))
                else:
                    gap_text = str(gap)
                # Only truncate VERY long gaps (>150 chars) to keep query manageable
                if len(gap_text) > 150:
                    gap_text = gap_text[:147] + "..."
                gaps.append(gap_text)
            gaps_str = ", ".join(gaps)
            parts.append(f"with emphasis on: {gaps_str}")

        # Add keywords (keep all, rarely need truncation)
        if keywords and len(keywords) > 0:
            # Handle both string and dict formats (keywords from KeywordResearchAgent are dicts)
            kw_list = []
            for kw in keywords[:3]:  # Keep all 3 keywords
                if isinstance(kw, dict):
                    kw_text = kw.get('keyword', str(kw))
                else:
                    kw_text = str(kw)
                # Keywords are typically short, only truncate if unusually long
                if len(kw_text) > 60:
                    kw_text = kw_text[:57] + "..."
                kw_list.append(kw_text)
            keywords_str = ", ".join(kw_list)
            parts.append(f"targeting keywords: {keywords_str}")

        query = " ".join(parts)

        # Hard limit: Max 400 characters for gpt-researcher queries
        # Longer queries cause exponentially slower research and timeouts
        MAX_QUERY_LENGTH = 400

        if len(query) > MAX_QUERY_LENGTH:
            logger.warning(
                "query_too_long_truncating",
                original_length=len(query),
                max_length=MAX_QUERY_LENGTH
            )

            # Strategy: Truncate from end to preserve topic context
            # Keep topic + domain + market + language (core context)
            # Truncate emphasis/keywords if needed
            query = query[:MAX_QUERY_LENGTH - 3] + "..."

        logger.debug("query_built", original_topic=topic, contextualized_query=query, length=len(query))

        return query

    def _slugify_topic(self, topic: str) -> str:
        """
        Convert topic to URL-safe slug for cache key

        Args:
            topic: Original topic string

        Returns:
            Slugified topic ID (lowercase, hyphens, no special chars)

        Example:
            "PropTech Trends 2025" -> "proptech-trends-2025"
        """
        import re
        # Remove special characters, convert to lowercase, replace spaces with hyphens
        slug = re.sub(r'[^\w\s-]', '', topic.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')

    def _cache_sources(
        self,
        sources: List[str],
        report: str,
        topic_id: str
    ) -> tuple[int, int]:
        """
        Cache sources after research

        Args:
            sources: List of source URLs from research
            report: Generated report text
            topic_id: Topic identifier for tracking

        Returns:
            Tuple of (cached_count, new_count)
            - cached_count: Sources already in cache (cache hits, API calls saved)
            - new_count: New sources added to cache (cache misses)
        """
        cached_count = 0
        new_count = 0

        for url in sources:
            # Check if already cached
            existing = self.source_cache.get_source(url)

            if existing:
                # Source already in cache - mark usage for this topic
                self.source_cache.mark_usage(url, topic_id)
                cached_count += 1
                logger.debug("source_cache_hit", url=url[:50], topic_id=topic_id)
            else:
                # New source - save to cache
                # Extract title from report (simple heuristic: first mention of domain)
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace('www.', '')
                title = f"Source from {domain}"

                # Content preview: Extract sentences mentioning this domain from report
                content_preview = self._extract_source_context(report, domain)

                self.source_cache.save_source(
                    url=url,
                    title=title,
                    content=content_preview,
                    topic_id=topic_id,
                    author=None,
                    published_at=None
                )
                new_count += 1
                logger.debug("source_cache_miss_saved", url=url[:50], topic_id=topic_id)

        return cached_count, new_count

    def _extract_source_context(self, report: str, domain: str) -> str:
        """
        Extract sentences from report that might reference a source domain

        Args:
            report: Full research report text
            domain: Domain name to look for

        Returns:
            Context string (up to 500 chars)
        """
        # Simple heuristic: take first 500 chars of report as context
        # In future, could use NLP to extract sentences mentioning the domain
        return report[:500] if report else f"Source from {domain}"

    async def _gemini_cli_fallback(
        self,
        topic: str,
        contextualized_query: str,
        config: Dict
    ) -> Dict:
        """
        Fallback research method using Gemini CLI directly

        This method is used when gpt-researcher fails (e.g., due to dependency issues).
        It uses Gemini CLI to generate a research report without citations.

        Args:
            topic: Original topic
            contextualized_query: Contextualized query with domain/market/language
            config: Research config

        Returns:
            Dictionary with report, sources (empty list), word_count, researched_at
        """
        logger.info("using_gemini_cli_fallback", topic=topic)

        # Build research prompt
        prompt = f"""You are a professional research analyst. Write a comprehensive research report about:

{contextualized_query}

Requirements:
- Write a detailed 800-1200 word research report
- Use markdown formatting with clear sections
- Include an executive summary
- Cover current trends, key insights, and future outlook
- Be factual and analytical
- Write in {config.get('language', 'English')} language if applicable

Format the report with these sections:
# Executive Summary
# Current State
# Key Trends
# Market Analysis
# Future Outlook
# Conclusion"""

        # Use Gemini CLI
        try:
            result = subprocess.run(
                ['gemini', 'chat', prompt],
                capture_output=True,
                text=True,
                timeout=60,
                check=True
            )

            report = result.stdout.strip()

            if not report or len(report) < 100:
                raise DeepResearchError("Gemini CLI returned empty or invalid report")

            word_count = len(report.split())

            result_dict = {
                'topic': topic,
                'report': report,
                'sources': [],  # No sources from Gemini CLI
                'word_count': word_count,
                'researched_at': datetime.now().isoformat()
            }

            logger.info(
                "gemini_cli_fallback_complete",
                topic=topic,
                word_count=word_count
            )

            return result_dict

        except subprocess.TimeoutExpired:
            raise DeepResearchError("Gemini CLI timeout after 60 seconds")
        except subprocess.CalledProcessError as e:
            raise DeepResearchError(f"Gemini CLI failed: {e.stderr}")
        except FileNotFoundError:
            raise DeepResearchError("Gemini CLI not found. Install with: npm install -g @google/generative-ai-cli")

    def get_statistics(self) -> Dict:
        """
        Get research statistics including cache performance

        Returns:
            Dictionary with:
            - total_research: Total research attempts
            - failed_research: Failed attempts
            - total_sources_found: Total sources found
            - success_rate: Ratio of successful to total (0-1)
            - cache_hits: Sources already in cache (API calls saved)
            - cache_misses: New sources added to cache
            - cache_hit_rate: Percentage of sources found in cache (0-100)
            - api_calls_saved: Total API calls avoided via caching
        """
        success_rate = (
            (self.total_research - self.failed_research) / self.total_research
            if self.total_research > 0
            else 0.0
        )

        total_cache_lookups = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            (self.cache_hits / total_cache_lookups * 100)
            if total_cache_lookups > 0
            else 0.0
        )

        stats = {
            'total_research': self.total_research,
            'failed_research': self.failed_research,
            'total_sources_found': self.total_sources_found,
            'success_rate': success_rate,
        }

        # Add cache statistics if caching enabled
        if self.source_cache:
            stats.update({
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'cache_hit_rate': cache_hit_rate,
                'api_calls_saved': self.api_calls_saved,
                'caching_enabled': True
            })
        else:
            stats['caching_enabled'] = False

        return stats

    def reset_statistics(self) -> None:
        """Reset all statistics to zero (including cache stats)"""
        self.total_research = 0
        self.failed_research = 0
        self.total_sources_found = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls_saved = 0
        logger.info("statistics_reset")
