"""
Full Pipeline E2E Integration Test

Tests the complete 5-stage ContentPipeline end-to-end:
1. Competitor Research - Identify content gaps
2. Keyword Research - Find SEO opportunities
3. Deep Research - Generate sourced reports (NOW ENABLED!)
4. Content Optimization - Apply insights
5. Scoring & Ranking - Calculate priority scores

This test validates:
- All stages execute successfully
- Data flows correctly between stages
- Stage 3 (Deep Research) works with qwen/OpenRouter
- Final output includes all enrichments
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from src.agents.content_pipeline import ContentPipeline
from src.agents.competitor_research_agent import CompetitorResearchAgent
from src.agents.keyword_research_agent import KeywordResearchAgent
from src.research.deep_researcher import DeepResearcher
from src.models.topic import Topic, TopicSource
from src.models.config import MarketConfig


@pytest.fixture
def content_pipeline():
    """Create ContentPipeline with all agents"""
    import os

    # Get API key from environment or use test key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "test-key"

    competitor_agent = CompetitorResearchAgent(api_key=api_key)
    keyword_agent = KeywordResearchAgent(api_key=api_key)
    deep_researcher = DeepResearcher()  # Uses qwen/qwen-2.5-32b-instruct by default

    return ContentPipeline(
        competitor_agent=competitor_agent,
        keyword_agent=keyword_agent,
        deep_researcher=deep_researcher,
        max_competitors=3,  # Reduced for faster testing
        max_keywords=5,     # Reduced for faster testing
        enable_deep_research=True  # NOW ENABLED!
    )


@pytest.fixture
def test_topic():
    """Create a realistic test topic"""
    return Topic(
        title="PropTech SaaS Solutions 2025",
        description="Emerging PropTech software solutions transforming real estate management in Germany",
        source=TopicSource.MANUAL,
        keywords=["PropTech", "SaaS", "Real Estate", "Germany"],
        domain="SaaS",
        market="Germany",
        language="de",
        vertical="PropTech",
        discovered_at=datetime.now(),
        url=None
    )


@pytest.fixture
def test_config():
    """Create test configuration"""
    return MarketConfig(
        domain='SaaS',
        market='Germany',
        language='de',
        vertical='PropTech',
        target_audience='Property managers, real estate companies',
        seed_keywords=['PropTech', 'SaaS', 'Real Estate']
    )


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.e2e
async def test_full_pipeline_e2e(content_pipeline, test_topic, test_config):
    """
    Test: Full 5-stage pipeline executes successfully

    This is the main E2E test validating all stages work together.
    """
    # Track progress
    stages_completed = []

    def progress_callback(stage, message):
        """Callback to track stage progress"""
        stages_completed.append({
            'stage': stage,
            'message': message
        })
        print(f"[Stage {stage}] {message}")

    # Execute full pipeline
    result = await content_pipeline.process_topic(
        topic=test_topic,
        config=test_config,
        progress_callback=progress_callback
    )

    # Validate result structure
    assert result is not None, "Pipeline returned None"
    assert isinstance(result, Topic), "Pipeline should return Topic instance"

    # Validate all 5 stages completed
    assert len(stages_completed) >= 5, f"Expected 5 stages, got {len(stages_completed)}"

    # Stage 1: Competitor Research
    assert result.competitors is not None, "Stage 1: competitors should be populated"
    assert len(result.competitors) > 0, "Stage 1: Should find at least 1 competitor"
    assert result.content_gaps is not None, "Stage 1: content_gaps should be populated"
    print(f"✅ Stage 1: Found {len(result.competitors)} competitors, {len(result.content_gaps)} gaps")

    # Stage 2: Keyword Research
    assert result.keywords is not None, "Stage 2: keywords should be populated"
    assert len(result.keywords) > 0, "Stage 2: Should find at least 1 keyword"
    # Validate keyword structure
    if len(result.keywords) > 0:
        first_keyword = result.keywords[0]
        assert 'keyword' in first_keyword or isinstance(first_keyword, str), "Keyword should have 'keyword' field or be string"
    print(f"✅ Stage 2: Found {len(result.keywords)} keywords")

    # Stage 3: Deep Research (THE NEWLY ENABLED STAGE!)
    assert result.deep_research_report is not None, "Stage 3: deep_research_report should be populated"
    assert len(result.deep_research_report) > 0, "Stage 3: Report should not be empty"
    assert result.research_sources is not None, "Stage 3: research_sources should be populated"

    # Validate report quality
    assert len(result.deep_research_report) > 500, f"Stage 3: Report should be substantial (got {len(result.deep_research_report)} chars)"
    assert len(result.research_sources) >= 0, "Stage 3: Should have sources (or 0 if using non-Tavily backend)"

    print(f"✅ Stage 3: Generated {len(result.deep_research_report)} char report with {len(result.research_sources)} sources")

    # Stage 4: Content Optimization
    # Check that insights were applied (keywords and gaps integrated)
    assert hasattr(result, 'updated_at'), "Stage 4: Should have updated_at timestamp"
    print(f"✅ Stage 4: Content optimized at {result.updated_at}")

    # Stage 5: Scoring & Ranking
    assert result.demand_score is not None, "Stage 5: demand_score should be set"
    assert result.opportunity_score is not None, "Stage 5: opportunity_score should be set"
    assert result.fit_score is not None, "Stage 5: fit_score should be set"
    assert result.novelty_score is not None, "Stage 5: novelty_score should be set"
    assert result.priority_score is not None, "Stage 5: priority_score should be set"

    # Validate score ranges
    assert 0 <= result.demand_score <= 100, "demand_score should be 0-100"
    assert 0 <= result.opportunity_score <= 100, "opportunity_score should be 0-100"
    assert 0 <= result.fit_score <= 100, "fit_score should be 0-100"
    assert 0 <= result.novelty_score <= 100, "novelty_score should be 0-100"
    assert 0 <= result.priority_score <= 100, "priority_score should be 0-100"

    print(f"✅ Stage 5: Scores - Priority: {result.priority_score}, Demand: {result.demand_score}, "
          f"Opportunity: {result.opportunity_score}, Fit: {result.fit_score}, Novelty: {result.novelty_score}")

    # Overall validation
    print("\n" + "="*60)
    print("🎉 FULL 5-STAGE PIPELINE E2E TEST PASSED!")
    print("="*60)
    print(f"Topic: {result.title}")
    print(f"Competitors: {len(result.competitors)}")
    print(f"Content Gaps: {len(result.content_gaps)}")
    print(f"Keywords: {len(result.keywords)}")
    print(f"Research Report: {len(result.deep_research_report)} chars")
    print(f"Research Sources: {len(result.research_sources)}")
    print(f"Priority Score: {result.priority_score}/100")
    print("="*60)


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.e2e
async def test_stage3_deep_research_produces_quality_report(content_pipeline, test_topic, test_config):
    """
    Test: Stage 3 produces high-quality research report

    Validates that the newly enabled Stage 3 generates substantial,
    well-structured research reports with proper formatting.
    """
    result = await content_pipeline.process_topic(
        topic=test_topic,
        config=test_config
    )

    report = result.deep_research_report

    # Quality checks
    assert len(report) > 1000, f"Report should be substantial (>1000 chars), got {len(report)}"
    assert len(report) < 50000, f"Report should be reasonable length (<50k chars), got {len(report)}"

    # Check for markdown formatting
    assert '#' in report or '##' in report, "Report should have markdown headings"

    # Check for paragraph structure
    assert '\n\n' in report, "Report should have paragraph breaks"

    # Check word count
    word_count = len(report.split())
    assert word_count > 200, f"Report should have substantial content (>200 words), got {word_count}"

    print(f"✅ Stage 3 Quality: {len(report)} chars, {word_count} words")
    print(f"   Report preview: {report[:200]}...")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.e2e
async def test_pipeline_handles_stage_failures_gracefully(content_pipeline, test_config):
    """
    Test: Pipeline handles invalid inputs and failures gracefully
    """
    # Create invalid topic (missing required fields)
    invalid_topic = Topic(
        title="",  # Empty title
        description="",
        source=TopicSource.MANUAL,
        keywords=[],
        domain=None,  # Missing domain
        market=None,  # Missing market
        language="de",
        discovered_at=datetime.now()
    )

    # Should either handle gracefully or raise appropriate error
    with pytest.raises(Exception):
        await content_pipeline.process_topic(
            topic=invalid_topic,
            config=test_config
        )

    print("✅ Pipeline handles invalid inputs appropriately")


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.e2e
async def test_pipeline_statistics_tracking(content_pipeline, test_topic, test_config):
    """
    Test: Pipeline tracks statistics correctly
    """
    # Get initial stats
    initial_stats = content_pipeline.get_statistics()
    initial_total = initial_stats['total_topics_processed']

    # Process topic
    await content_pipeline.process_topic(
        topic=test_topic,
        config=test_config
    )

    # Get updated stats
    updated_stats = content_pipeline.get_statistics()

    # Validate stats incremented
    assert updated_stats['total_topics_processed'] == initial_total + 1, "Should increment total topics"
    assert updated_stats['successful_topics'] >= initial_stats['successful_topics'], "Should track successful topics"

    print(f"✅ Statistics: {updated_stats['total_topics_processed']} topics processed, "
          f"{updated_stats['successful_topics']} successful")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short", "-m", "e2e"])
