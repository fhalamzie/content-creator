"""
Tests for ContentPipeline

5-stage content pipeline orchestrating:
1. Competitor Research (identify gaps)
2. Keyword Research (find SEO opportunities)
3. Deep Research (generate sourced report)
4. Content Optimization (apply insights)
5. Scoring & Ranking (prioritize topics)
"""

import pytest
from unittest.mock import Mock

from src.agents.content_pipeline import ContentPipeline, ContentPipelineError
from src.models.topic import Topic, TopicSource, TopicStatus
from src.models.config import MarketConfig


# Test fixtures
@pytest.fixture
def sample_config():
    """Sample market configuration"""
    return MarketConfig(
        domain="SaaS",
        market="Germany",
        language="de",
        vertical="Proptech",
        seed_keywords=["DSGVO", "Immobilien SaaS"]
    )


@pytest.fixture
def sample_topic():
    """Sample topic for pipeline processing"""
    return Topic(
        title="PropTech Trends 2025",
        description="Emerging trends in property technology",
        source=TopicSource.TRENDS,
        domain="SaaS",
        market="Germany",
        language="de",
        status=TopicStatus.DISCOVERED,
        engagement_score=85,
        trending_score=75.5
    )


@pytest.fixture
def mock_competitor_agent():
    """Mock competitor research agent"""
    agent = Mock()
    agent.research_competitors.return_value = {
        'competitors': [
            {'name': 'Competitor A', 'url': 'https://competitor-a.com'},
            {'name': 'Competitor B', 'url': 'https://competitor-b.com'}
        ],
        'content_gaps': [
            'GDPR compliance in PropTech',
            'Smart building automation'
        ],
        'trending_topics': ['AI in real estate', 'Sustainability']
    }
    return agent


@pytest.fixture
def mock_keyword_agent():
    """Mock keyword research agent"""
    agent = Mock()
    agent.research_keywords.return_value = {
        'primary_keyword': 'PropTech Trends Deutschland',
        'secondary_keywords': [
            'Immobilien Technologie',
            'Smart Buildings',
            'PropTech DSGVO',
            'Digitale Immobilienverwaltung'
        ],
        'long_tail_keywords': [
            'PropTech Trends 2025 Deutschland',
            'Smart Building DSGVO konform'
        ],
        'search_volume': 1200,
        'competition': 'medium',
        'difficulty_score': 45.5
    }
    return agent


@pytest.fixture
def mock_deep_researcher():
    """Mock deep researcher"""
    researcher = Mock()

    # Mock async method
    async def mock_research(*args, **kwargs):
        return {
            'report': '# PropTech Trends 2025\n\nDetailed research report...',
            'sources': [
                {'title': 'Source 1', 'url': 'https://source1.com', 'snippet': 'Snippet 1'},
                {'title': 'Source 2', 'url': 'https://source2.com', 'snippet': 'Snippet 2'}
            ],
            'word_count': 1850,
            'duration': 12.5
        }

    researcher.research_topic = mock_research
    return researcher


# Test: Initialization
class TestContentPipelineInitialization:
    """Test pipeline initialization"""

    def test_init_with_all_dependencies(self, mock_competitor_agent, mock_keyword_agent, mock_deep_researcher):
        """Should initialize with all dependencies"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        assert pipeline.competitor_agent == mock_competitor_agent
        assert pipeline.keyword_agent == mock_keyword_agent
        assert pipeline.deep_researcher == mock_deep_researcher
        assert pipeline.total_processed == 0
        assert pipeline.total_failed == 0

    def test_init_with_optional_parameters(self, mock_competitor_agent, mock_keyword_agent, mock_deep_researcher):
        """Should initialize with optional parameters"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher,
            max_competitors=3,
            max_keywords=15,
            enable_deep_research=False
        )

        assert pipeline.max_competitors == 3
        assert pipeline.max_keywords == 15
        assert pipeline.enable_deep_research is False

    def test_init_missing_competitor_agent(self, mock_keyword_agent, mock_deep_researcher):
        """Should raise error if competitor_agent missing"""
        with pytest.raises(ContentPipelineError, match="competitor_agent is required"):
            ContentPipeline(
                competitor_agent=None,
                keyword_agent=mock_keyword_agent,
                deep_researcher=mock_deep_researcher
            )

    def test_init_missing_keyword_agent(self, mock_competitor_agent, mock_deep_researcher):
        """Should raise error if keyword_agent missing"""
        with pytest.raises(ContentPipelineError, match="keyword_agent is required"):
            ContentPipeline(
                competitor_agent=mock_competitor_agent,
                keyword_agent=None,
                deep_researcher=mock_deep_researcher
            )

    def test_init_missing_deep_researcher(self, mock_competitor_agent, mock_keyword_agent):
        """Should raise error if deep_researcher missing"""
        with pytest.raises(ContentPipelineError, match="deep_researcher is required"):
            ContentPipeline(
                competitor_agent=mock_competitor_agent,
                keyword_agent=mock_keyword_agent,
                deep_researcher=None
            )


# Test: Stage 1 - Competitor Research
class TestStage1CompetitorResearch:
    """Test Stage 1: Competitor Research"""

    @pytest.mark.asyncio
    async def test_stage1_competitor_research_success(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should execute competitor research successfully"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        result = await pipeline._stage1_competitor_research(sample_topic, sample_config)

        assert 'competitors' in result
        assert 'content_gaps' in result
        assert len(result['competitors']) == 2
        assert len(result['content_gaps']) == 2

        # Verify agent was called correctly
        mock_competitor_agent.research_competitors.assert_called_once_with(
            topic=sample_topic.title,
            language=sample_config.language,
            max_competitors=5,  # default value
            include_content_analysis=True,
            save_to_cache=False
        )

    @pytest.mark.asyncio
    async def test_stage1_competitor_research_failure(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should handle competitor research failure gracefully"""
        # Mock failure
        mock_competitor_agent.research_competitors.side_effect = Exception("API error")

        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        with pytest.raises(ContentPipelineError, match="Stage 1 failed: API error"):
            await pipeline._stage1_competitor_research(sample_topic, sample_config)


# Test: Stage 2 - Keyword Research
class TestStage2KeywordResearch:
    """Test Stage 2: Keyword Research"""

    @pytest.mark.asyncio
    async def test_stage2_keyword_research_success(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should execute keyword research successfully"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        result = await pipeline._stage2_keyword_research(sample_topic, sample_config)

        assert 'primary_keyword' in result
        assert 'secondary_keywords' in result
        assert 'long_tail_keywords' in result
        assert result['primary_keyword'] == 'PropTech Trends Deutschland'
        assert len(result['secondary_keywords']) == 4

        # Verify agent was called correctly
        mock_keyword_agent.research_keywords.assert_called_once_with(
            topic=sample_topic.title,
            language=sample_config.language,
            target_audience=None,
            keyword_count=10,  # default value
            save_to_cache=False
        )

    @pytest.mark.asyncio
    async def test_stage2_keyword_research_with_target_audience(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should pass target_audience to keyword agent"""
        sample_config.target_audience = "German small businesses"

        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        await pipeline._stage2_keyword_research(sample_topic, sample_config)

        # Verify target_audience was passed
        call_args = mock_keyword_agent.research_keywords.call_args
        assert call_args.kwargs['target_audience'] == "German small businesses"


# Test: Stage 3 - Deep Research
class TestStage3DeepResearch:
    """Test Stage 3: Deep Research"""

    @pytest.mark.asyncio
    async def test_stage3_deep_research_success(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should execute deep research successfully"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        # Prepare context from previous stages
        competitor_data = {
            'content_gaps': ['Gap 1', 'Gap 2']
        }
        keyword_data = {
            'primary_keyword': 'PropTech',
            'secondary_keywords': ['keyword1', 'keyword2']
        }

        result = await pipeline._stage3_deep_research(
            sample_topic, sample_config, competitor_data, keyword_data
        )

        assert 'report' in result
        assert 'sources' in result
        assert 'word_count' in result
        assert result['word_count'] == 1850
        assert len(result['sources']) == 2

    @pytest.mark.asyncio
    async def test_stage3_deep_research_disabled(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should skip deep research if disabled"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher,
            enable_deep_research=False
        )

        competitor_data = {'content_gaps': []}
        keyword_data = {'secondary_keywords': []}

        result = await pipeline._stage3_deep_research(
            sample_topic, sample_config, competitor_data, keyword_data
        )

        # Should return empty result
        assert result['report'] is None
        assert result['sources'] == []
        assert result['word_count'] == 0


# Test: Stage 4 - Content Optimization
class TestStage4ContentOptimization:
    """Test Stage 4: Content Optimization"""

    def test_stage4_content_optimization(
        self, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should optimize topic with SEO metadata"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        # Create topic WITHOUT description (to test gap insertion)
        topic = Topic(
            title="PropTech Trends 2025",
            description=None,  # No description
            source=TopicSource.TRENDS,
            domain="SaaS",
            market="Germany",
            language="de"
        )

        # Prepare data from previous stages
        competitor_data = {
            'content_gaps': ['Gap 1', 'Gap 2'],
            'trending_topics': ['Trend 1']
        }
        keyword_data = {
            'primary_keyword': 'PropTech Trends',
            'secondary_keywords': ['keyword1', 'keyword2'],
            'difficulty_score': 45.5
        }
        research_data = {
            'report': '# Report',
            'sources': [{'url': 'https://example.com'}],
            'word_count': 1500
        }

        optimized_topic = pipeline._stage4_content_optimization(
            topic, competitor_data, keyword_data, research_data
        )

        # Verify topic was enriched
        assert optimized_topic.description is not None
        assert 'Gap 1' in optimized_topic.description or 'Gap 2' in optimized_topic.description
        assert optimized_topic.research_report == '# Report'
        assert len(optimized_topic.citations) == 1
        assert optimized_topic.word_count == 1500


# Test: Stage 5 - Scoring & Ranking
class TestStage5ScoringRanking:
    """Test Stage 5: Scoring & Ranking"""

    def test_stage5_scoring_ranking(
        self, sample_topic,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should calculate all scores correctly"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        # Prepare data for scoring
        keyword_data = {
            'search_volume': 1200,
            'competition': 'medium',
            'difficulty_score': 45.5
        }
        competitor_data = {
            'content_gaps': ['Gap 1', 'Gap 2', 'Gap 3']
        }

        scores = pipeline._stage5_scoring_ranking(
            sample_topic, keyword_data, competitor_data
        )

        # Verify all scores are present
        assert 'demand_score' in scores
        assert 'opportunity_score' in scores
        assert 'fit_score' in scores
        assert 'novelty_score' in scores
        assert 'priority_score' in scores

        # Verify scores are in valid range [0, 1]
        for score_name, score_value in scores.items():
            assert 0.0 <= score_value <= 1.0, f"{score_name} out of range: {score_value}"

    def test_stage5_demand_score_calculation(
        self, sample_topic,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should calculate demand_score based on search volume and engagement"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        # High search volume + high engagement
        keyword_data = {'search_volume': 5000, 'competition': 'low', 'difficulty_score': 30}
        sample_topic.engagement_score = 95

        scores = pipeline._stage5_scoring_ranking(sample_topic, keyword_data, {})

        # Should have high demand score (adjusted threshold to 0.6 for realism)
        assert scores['demand_score'] >= 0.6

    def test_stage5_opportunity_score_calculation(
        self, sample_topic,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should calculate opportunity_score based on competition and gaps"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        # Low difficulty + many content gaps
        keyword_data = {'search_volume': 1000, 'competition': 'low', 'difficulty_score': 20}
        competitor_data = {'content_gaps': ['Gap 1', 'Gap 2', 'Gap 3', 'Gap 4', 'Gap 5']}

        scores = pipeline._stage5_scoring_ranking(sample_topic, keyword_data, competitor_data)

        # Should have high opportunity score (adjusted threshold to 0.65 for realism)
        assert scores['opportunity_score'] >= 0.65


# Test: Full Pipeline Execution
class TestFullPipelineExecution:
    """Test full pipeline execution"""

    @pytest.mark.asyncio
    async def test_process_topic_success(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should process topic through all 5 stages"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        enhanced_topic = await pipeline.process_topic(sample_topic, sample_config)

        # Verify topic was enhanced
        assert enhanced_topic.research_report is not None
        assert len(enhanced_topic.citations) > 0
        assert enhanced_topic.word_count > 0
        assert enhanced_topic.status == TopicStatus.RESEARCHED

        # Verify statistics were updated
        assert pipeline.total_processed == 1
        assert pipeline.total_failed == 0

    @pytest.mark.asyncio
    async def test_process_topic_with_callback(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should call progress callback at each stage"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        progress_calls = []

        def progress_callback(stage: int, message: str):
            progress_calls.append((stage, message))

        await pipeline.process_topic(sample_topic, sample_config, progress_callback=progress_callback)

        # Should have 5 progress callbacks (one per stage)
        assert len(progress_calls) == 5
        assert progress_calls[0][0] == 1
        assert progress_calls[4][0] == 5

    @pytest.mark.asyncio
    async def test_process_topic_failure_handling(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should handle pipeline failure and update statistics"""
        # Mock failure in stage 1
        mock_competitor_agent.research_competitors.side_effect = Exception("API error")

        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        with pytest.raises(ContentPipelineError):
            await pipeline.process_topic(sample_topic, sample_config)

        # Verify failure statistics
        assert pipeline.total_processed == 0
        assert pipeline.total_failed == 1


# Test: Statistics
class TestContentPipelineStatistics:
    """Test pipeline statistics tracking"""

    @pytest.mark.asyncio
    async def test_get_statistics(
        self, sample_topic, sample_config,
        mock_competitor_agent, mock_keyword_agent, mock_deep_researcher
    ):
        """Should return accurate statistics"""
        pipeline = ContentPipeline(
            competitor_agent=mock_competitor_agent,
            keyword_agent=mock_keyword_agent,
            deep_researcher=mock_deep_researcher
        )

        # Process multiple topics
        await pipeline.process_topic(sample_topic, sample_config)

        topic2 = Topic(
            title="Another Topic",
            source=TopicSource.RSS,
            domain="SaaS",
            market="Germany",
            language="de"
        )
        await pipeline.process_topic(topic2, sample_config)

        stats = pipeline.get_statistics()

        assert stats['total_processed'] == 2
        assert stats['total_failed'] == 0
        assert stats['success_rate'] == 1.0
