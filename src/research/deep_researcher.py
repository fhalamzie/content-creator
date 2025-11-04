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

from typing import Dict, List, Optional
from datetime import datetime

from src.utils.logger import get_logger

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
        llm_provider: str = "google_genai",
        llm_model: str = "gemini-2.0-flash-exp",
        search_engine: str = "duckduckgo",
        max_sources: int = 8,
        report_format: str = "markdown"
    ):
        """
        Initialize deep researcher

        Args:
            llm_provider: LLM provider (google_genai for Gemini)
            llm_model: Model to use (gemini-2.0-flash-exp)
            search_engine: Search backend (duckduckgo)
            max_sources: Maximum sources per research (default 8)
            report_format: Output format (markdown)
        """
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.search_engine = search_engine
        self.max_sources = max_sources
        self.report_format = report_format

        # Statistics
        self.total_research = 0
        self.failed_research = 0
        self.total_sources_found = 0

        logger.info(
            "deep_researcher_initialized",
            llm_provider=llm_provider,
            llm_model=llm_model,
            search_engine=search_engine,
            max_sources=max_sources
        )

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

            # Initialize gpt-researcher
            researcher = GPTResearcher(
                query=contextualized_query,
                report_type="research_report",
                config_path=None,  # Use default config
                llm_provider=self.llm_provider,
                smart_llm_model=self.llm_model,
                fast_llm_model=self.llm_model,
                search_engine=self.search_engine,
                max_search_results=self.max_sources,
                report_format=self.report_format
            )

            # Conduct research
            await researcher.conduct_research()

            # Generate report
            report = await researcher.write_report()

            # Get sources
            sources = await researcher.get_source_urls()

            # Update statistics
            self.total_sources_found += len(sources)

            # Calculate word count (approximate)
            word_count = len(report.split())

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
            self.failed_research += 1
            logger.error("research_failed", topic=topic, error=str(e))
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

        # Add competitor gaps
        if competitor_gaps and len(competitor_gaps) > 0:
            # Handle both string and dict formats
            gaps = []
            for gap in competitor_gaps[:3]:
                if isinstance(gap, dict):
                    gaps.append(gap.get('gap', str(gap)))
                else:
                    gaps.append(str(gap))
            gaps_str = ", ".join(gaps)
            parts.append(f"with emphasis on: {gaps_str}")

        # Add keywords
        if keywords and len(keywords) > 0:
            # Handle both string and dict formats (keywords from KeywordResearchAgent are dicts)
            kw_list = []
            for kw in keywords[:3]:
                if isinstance(kw, dict):
                    kw_list.append(kw.get('keyword', str(kw)))
                else:
                    kw_list.append(str(kw))
            keywords_str = ", ".join(kw_list)
            parts.append(f"targeting keywords: {keywords_str}")

        query = " ".join(parts)

        logger.debug("query_built", original_topic=topic, contextualized_query=query)

        return query

    def get_statistics(self) -> Dict:
        """
        Get research statistics

        Returns:
            Dictionary with:
            - total_research: Total research attempts
            - failed_research: Failed attempts
            - total_sources_found: Total sources found
            - success_rate: Ratio of successful to total (0-1)
        """
        success_rate = (
            (self.total_research - self.failed_research) / self.total_research
            if self.total_research > 0
            else 0.0
        )

        return {
            'total_research': self.total_research,
            'failed_research': self.failed_research,
            'total_sources_found': self.total_sources_found,
            'success_rate': success_rate
        }

    def reset_statistics(self) -> None:
        """Reset all statistics to zero"""
        self.total_research = 0
        self.failed_research = 0
        self.total_sources_found = 0
        logger.info("statistics_reset")
