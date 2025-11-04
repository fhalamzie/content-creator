"""
Content Pipeline - 5-Stage Topic Enhancement

Orchestrates competitor research, keyword research, deep research,
content optimization, and scoring to transform discovered topics
into actionable, prioritized content opportunities.

Architecture:
1. Stage 1: Competitor Research → Identify content gaps
2. Stage 2: Keyword Research → Find SEO opportunities
3. Stage 3: Deep Research → Generate sourced reports
4. Stage 4: Content Optimization → Apply insights & metadata
5. Stage 5: Scoring & Ranking → Calculate priority scores

Usage:
    from src.agents.content_pipeline import ContentPipeline
    from src.agents.competitor_research_agent import CompetitorResearchAgent
    from src.agents.keyword_research_agent import KeywordResearchAgent
    from src.research.deep_researcher import DeepResearcher

    pipeline = ContentPipeline(
        competitor_agent=CompetitorResearchAgent(api_key),
        keyword_agent=KeywordResearchAgent(api_key),
        deep_researcher=DeepResearcher()
    )

    enhanced_topic = await pipeline.process_topic(topic, config)
"""

from typing import Dict, Any, Optional, Callable
from datetime import datetime

from src.models.topic import Topic, TopicStatus
from src.models.config import MarketConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContentPipelineError(Exception):
    """Raised when pipeline processing fails"""
    pass


class ContentPipeline:
    """
    5-stage content pipeline for topic enhancement

    Features:
    - Competitor analysis with content gap identification
    - SEO keyword research with difficulty scoring
    - Deep research with citations (gpt-researcher)
    - Content optimization with metadata enrichment
    - Multi-factor scoring (demand, opportunity, fit, novelty)
    - Progress tracking via callbacks
    - Statistics tracking

    Scoring Algorithm:
    - demand_score: Based on search volume + engagement
    - opportunity_score: Based on competition + content gaps
    - fit_score: Based on domain/market/vertical alignment
    - novelty_score: Based on trending + uniqueness
    - priority_score: Weighted combination of all factors
    """

    def __init__(
        self,
        competitor_agent,
        keyword_agent,
        deep_researcher,
        max_competitors: int = 5,
        max_keywords: int = 10,
        enable_deep_research: bool = False
    ):
        """
        Initialize content pipeline

        Args:
            competitor_agent: CompetitorResearchAgent instance
            keyword_agent: KeywordResearchAgent instance
            deep_researcher: DeepResearcher instance
            max_competitors: Maximum competitors to analyze (default: 5)
            max_keywords: Maximum keywords to research (default: 10)
            enable_deep_research: Enable deep research stage (default: False, enable tomorrow when Gemini quota resets)

        Raises:
            ContentPipelineError: If required agents are missing
        """
        # Validate dependencies
        if competitor_agent is None:
            raise ContentPipelineError("competitor_agent is required")
        if keyword_agent is None:
            raise ContentPipelineError("keyword_agent is required")
        if deep_researcher is None:
            raise ContentPipelineError("deep_researcher is required")

        self.competitor_agent = competitor_agent
        self.keyword_agent = keyword_agent
        self.deep_researcher = deep_researcher

        # Configuration
        self.max_competitors = max_competitors
        self.max_keywords = max_keywords
        self.enable_deep_research = enable_deep_research

        # Statistics
        self.total_processed = 0
        self.total_failed = 0

        logger.info(
            "content_pipeline_initialized",
            max_competitors=max_competitors,
            max_keywords=max_keywords,
            enable_deep_research=enable_deep_research
        )

    async def process_topic(
        self,
        topic: Topic,
        config: MarketConfig,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Topic:
        """
        Process topic through 5-stage pipeline

        Args:
            topic: Topic to process
            config: Market configuration
            progress_callback: Optional callback(stage, message)

        Returns:
            Enhanced topic with research, keywords, and scores

        Raises:
            ContentPipelineError: If pipeline fails
        """
        logger.info(
            "pipeline_started",
            topic_id=topic.id,
            topic_title=topic.title,
            domain=config.domain,
            market=config.market
        )

        try:
            # Stage 1: Competitor Research
            if progress_callback:
                progress_callback(1, "Analyzing competitors and content gaps...")
            competitor_data = await self._stage1_competitor_research(topic, config)

            # Stage 2: Keyword Research
            if progress_callback:
                progress_callback(2, "Researching SEO keywords...")
            keyword_data = await self._stage2_keyword_research(topic, config)

            # Stage 3: Deep Research
            if progress_callback:
                progress_callback(3, "Generating deep research report...")
            research_data = await self._stage3_deep_research(
                topic, config, competitor_data, keyword_data
            )

            # Stage 4: Content Optimization
            if progress_callback:
                progress_callback(4, "Optimizing content with insights...")
            optimized_topic = self._stage4_content_optimization(
                topic, competitor_data, keyword_data, research_data
            )

            # Stage 5: Scoring & Ranking
            if progress_callback:
                progress_callback(5, "Calculating priority scores...")
            scores = self._stage5_scoring_ranking(
                optimized_topic, keyword_data, competitor_data
            )

            # Apply scores to topic
            optimized_topic = self._apply_scores(optimized_topic, scores)

            # Update status
            optimized_topic.status = TopicStatus.RESEARCHED
            optimized_topic.updated_at = datetime.utcnow()

            # Update statistics
            self.total_processed += 1

            logger.info(
                "pipeline_completed",
                topic_id=optimized_topic.id,
                priority_score=scores['priority_score'],
                word_count=optimized_topic.word_count
            )

            return optimized_topic

        except Exception as e:
            self.total_failed += 1
            logger.error(
                "pipeline_failed",
                topic_id=topic.id,
                error=str(e)
            )
            raise ContentPipelineError(f"Pipeline failed: {e}") from e

    async def _stage1_competitor_research(
        self,
        topic: Topic,
        config: MarketConfig
    ) -> Dict[str, Any]:
        """
        Stage 1: Competitor Research

        Identifies competitors and content gaps using CompetitorResearchAgent.

        Returns:
            Dict with 'competitors', 'content_gaps', 'trending_topics'
        """
        logger.info("stage1_started", topic_title=topic.title)

        try:
            result = self.competitor_agent.research_competitors(
                topic=topic.title,
                language=config.language,
                max_competitors=self.max_competitors,
                include_content_analysis=True,
                save_to_cache=False
            )

            logger.info(
                "stage1_completed",
                competitors_found=len(result.get('competitors', [])),
                content_gaps=len(result.get('content_gaps', []))
            )

            return result

        except Exception as e:
            logger.error("stage1_failed", error=str(e))
            raise ContentPipelineError(f"Stage 1 failed: {e}") from e

    async def _stage2_keyword_research(
        self,
        topic: Topic,
        config: MarketConfig
    ) -> Dict[str, Any]:
        """
        Stage 2: Keyword Research

        Finds SEO keywords using KeywordResearchAgent.

        Returns:
            Dict with 'primary_keyword', 'secondary_keywords', 'long_tail_keywords',
            'search_volume', 'competition', 'difficulty_score'
        """
        logger.info("stage2_started", topic_title=topic.title)

        try:
            result = self.keyword_agent.research_keywords(
                topic=topic.title,
                language=config.language,
                target_audience=getattr(config, 'target_audience', None),
                keyword_count=self.max_keywords,
                save_to_cache=False
            )

            logger.info(
                "stage2_completed",
                primary_keyword=result.get('primary_keyword'),
                secondary_count=len(result.get('secondary_keywords', [])),
                difficulty=result.get('difficulty_score')
            )

            return result

        except Exception as e:
            logger.error("stage2_failed", error=str(e))
            raise ContentPipelineError(f"Stage 2 failed: {e}") from e

    async def _stage3_deep_research(
        self,
        topic: Topic,
        config: MarketConfig,
        competitor_data: Dict[str, Any],
        keyword_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stage 3: Deep Research

        Generates sourced research report using DeepResearcher.
        Enhanced with competitor gaps and keywords from previous stages.

        Returns:
            Dict with 'report', 'sources', 'word_count', 'duration'
        """
        if not self.enable_deep_research:
            logger.info("stage3_skipped", reason="deep_research_disabled")
            return {
                'report': None,
                'sources': [],
                'word_count': 0,
                'duration': 0
            }

        logger.info("stage3_started", topic_title=topic.title)

        try:
            # Extract context for enhanced research
            competitor_gaps = competitor_data.get('content_gaps', [])
            keywords = keyword_data.get('secondary_keywords', [])

            # Convert config to dict
            config_dict = {
                'domain': config.domain,
                'market': config.market,
                'language': config.language,
                'vertical': getattr(config, 'vertical', None)
            }

            result = await self.deep_researcher.research_topic(
                topic=topic.title,
                config=config_dict,
                competitor_gaps=competitor_gaps,
                keywords=keywords
            )

            logger.info(
                "stage3_completed",
                word_count=result.get('word_count', 0),
                sources_found=len(result.get('sources', [])),
                duration=result.get('duration', 0)
            )

            return result

        except Exception as e:
            logger.error("stage3_failed", error=str(e))
            raise ContentPipelineError(f"Stage 3 failed: {e}") from e

    def _stage4_content_optimization(
        self,
        topic: Topic,
        competitor_data: Dict[str, Any],
        keyword_data: Dict[str, Any],
        research_data: Dict[str, Any]
    ) -> Topic:
        """
        Stage 4: Content Optimization

        Enriches topic with metadata from all previous stages.

        Returns:
            Optimized topic with research, keywords, and metadata
        """
        logger.info("stage4_started", topic_title=topic.title)

        # Create enhanced description from content gaps
        content_gaps = competitor_data.get('content_gaps', [])
        if content_gaps and not topic.description:
            topic.description = f"Content opportunities: {', '.join(content_gaps[:3])}"

        # Add research report and citations
        if research_data.get('report'):
            topic.research_report = research_data['report']
            topic.word_count = research_data.get('word_count', 0)

            # Extract source URLs as citations
            sources = research_data.get('sources', [])
            topic.citations = [s.get('url', '') for s in sources if s.get('url')]

        logger.info(
            "stage4_completed",
            description_added=topic.description is not None,
            research_added=topic.research_report is not None,
            citations_count=len(topic.citations)
        )

        return topic

    def _stage5_scoring_ranking(
        self,
        topic: Topic,
        keyword_data: Dict[str, Any],
        competitor_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Stage 5: Scoring & Ranking

        Calculates multi-factor priority scores:
        - demand_score: Search volume + engagement
        - opportunity_score: Competition + content gaps
        - fit_score: Domain/market/vertical alignment
        - novelty_score: Trending + uniqueness
        - priority_score: Weighted combination

        Returns:
            Dict with all scores (0-1 scale)
        """
        logger.info("stage5_started", topic_title=topic.title)

        # Calculate demand score (0-1 scale)
        demand_score = self._calculate_demand_score(topic, keyword_data)

        # Calculate opportunity score (0-1 scale)
        opportunity_score = self._calculate_opportunity_score(keyword_data, competitor_data)

        # Calculate fit score (0-1 scale)
        fit_score = self._calculate_fit_score(topic)

        # Calculate novelty score (0-1 scale)
        novelty_score = self._calculate_novelty_score(topic)

        # Calculate weighted priority score
        priority_score = (
            0.35 * demand_score +
            0.30 * opportunity_score +
            0.20 * fit_score +
            0.15 * novelty_score
        )

        scores = {
            'demand_score': demand_score,
            'opportunity_score': opportunity_score,
            'fit_score': fit_score,
            'novelty_score': novelty_score,
            'priority_score': priority_score
        }

        logger.info(
            "stage5_completed",
            priority_score=priority_score,
            demand=demand_score,
            opportunity=opportunity_score,
            fit=fit_score,
            novelty=novelty_score
        )

        return scores

    def _calculate_demand_score(self, topic: Topic, keyword_data: Dict[str, Any]) -> float:
        """
        Calculate demand score based on search volume and engagement

        Formula: (normalized_search_volume * 0.7) + (normalized_engagement * 0.3)

        Returns:
            Score between 0.0 and 1.0
        """
        search_volume = keyword_data.get('search_volume', 0)
        engagement = topic.engagement_score

        # Normalize search volume (assume max 10,000 for context)
        normalized_volume = min(search_volume / 10000.0, 1.0)

        # Normalize engagement (0-100 scale)
        normalized_engagement = engagement / 100.0

        demand_score = (normalized_volume * 0.7) + (normalized_engagement * 0.3)

        return min(max(demand_score, 0.0), 1.0)

    def _calculate_opportunity_score(
        self,
        keyword_data: Dict[str, Any],
        competitor_data: Dict[str, Any]
    ) -> float:
        """
        Calculate opportunity score based on competition and content gaps

        Formula: (low_difficulty * 0.6) + (content_gaps * 0.4)

        Returns:
            Score between 0.0 and 1.0
        """
        difficulty = keyword_data.get('difficulty_score', 50.0)
        content_gaps = len(competitor_data.get('content_gaps', []))

        # Invert difficulty (lower difficulty = higher opportunity)
        normalized_difficulty = 1.0 - (difficulty / 100.0)

        # Normalize content gaps (assume max 10 gaps)
        normalized_gaps = min(content_gaps / 10.0, 1.0)

        opportunity_score = (normalized_difficulty * 0.6) + (normalized_gaps * 0.4)

        return min(max(opportunity_score, 0.0), 1.0)

    def _calculate_fit_score(self, topic: Topic) -> float:
        """
        Calculate fit score based on domain/market/vertical alignment

        For MVP: Use engagement + trending as proxy for fit
        In production: Could use LLM to evaluate alignment

        Returns:
            Score between 0.0 and 1.0
        """
        # Normalize trending score (0-100 scale)
        normalized_trending = topic.trending_score / 100.0

        # Normalize engagement (0-100 scale)
        normalized_engagement = topic.engagement_score / 100.0

        fit_score = (normalized_trending * 0.6) + (normalized_engagement * 0.4)

        return min(max(fit_score, 0.0), 1.0)

    def _calculate_novelty_score(self, topic: Topic) -> float:
        """
        Calculate novelty score based on trending and uniqueness

        Formula: trending_score as proxy for novelty

        Returns:
            Score between 0.0 and 1.0
        """
        # Use trending score as proxy (0-100 scale)
        novelty_score = topic.trending_score / 100.0

        return min(max(novelty_score, 0.0), 1.0)

    def _apply_scores(self, topic: Topic, scores: Dict[str, float]) -> Topic:
        """
        Apply scores to topic model

        Note: Topic model doesn't have score fields yet (Phase 2 feature)
        For now, just log the scores

        Args:
            topic: Topic to update
            scores: Score dictionary

        Returns:
            Topic with scores applied (when model supports it)
        """
        # TODO: Once Topic model has score fields, update them here
        # topic.demand_score = scores['demand_score']
        # topic.opportunity_score = scores['opportunity_score']
        # topic.fit_score = scores['fit_score']
        # topic.novelty_score = scores['novelty_score']
        # topic.priority_score = scores['priority_score']

        # For now, just set priority based on priority_score
        priority_score = scores['priority_score']
        if priority_score >= 0.8:
            topic.priority = 10
        elif priority_score >= 0.6:
            topic.priority = 8
        elif priority_score >= 0.4:
            topic.priority = 6
        else:
            topic.priority = 4

        return topic

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get pipeline statistics

        Returns:
            Dict with total_processed, total_failed, success_rate
        """
        success_rate = (
            self.total_processed / (self.total_processed + self.total_failed)
            if (self.total_processed + self.total_failed) > 0
            else 0.0
        )

        return {
            'total_processed': self.total_processed,
            'total_failed': self.total_failed,
            'success_rate': success_rate
        }
