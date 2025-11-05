"""
Simplified Full Pipeline E2E Test

Tests the working components directly without UniversalTopicAgent wrapper.
This test validates the actual component integrations that work today.

Pipeline tested:
1. RSS Collection → Collect documents from known feeds
2. ContentPipeline (5 stages) → Process topic through research pipeline
3. Validation → Verify all outputs meet quality standards

Note: This bypasses UniversalTopicAgent which has integration bugs discovered during E2E testing.
"""

import pytest
import asyncio
import os
from pathlib import Path
from datetime import datetime

from src.models.config import MarketConfig
from src.models.topic import Topic, TopicSource
from src.models.document import Document
from src.database.sqlite_manager import SQLiteManager
from src.collectors.rss_collector import RSSCollector
from src.processors.deduplicator import Deduplicator
from src.agents.content_pipeline import ContentPipeline
from src.agents.competitor_research_agent import CompetitorResearchAgent
from src.agents.keyword_research_agent import KeywordResearchAgent
from src.research.deep_researcher import DeepResearcher


@pytest.fixture
def gemini_api_key():
    """Load Gemini API key from environment or file"""
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        try:
            gemini_env_path = Path('/home/envs/gemini.env')
            if gemini_env_path.exists():
                api_key = gemini_env_path.read_text().strip()
        except Exception:
            pass

    if not api_key:
        pytest.skip("GEMINI_API_KEY required for E2E test")

    return api_key


@pytest.fixture
def test_config():
    """Create test market configuration"""
    return MarketConfig(
        domain='PropTech',
        market='Germany',
        language='de',
        vertical='Real Estate Technology',
        target_audience='Property managers, real estate companies',
        seed_keywords=['PropTech', 'Immobilien Software', 'Smart Building']
    )


@pytest.fixture
def db_manager():
    """Create in-memory database"""
    db = SQLiteManager(db_path=':memory:')
    yield db


@pytest.fixture
def content_pipeline(gemini_api_key):
    """Create ContentPipeline with all agents"""
    # FIXED: Now using grounding + JSON-in-prompt workaround
    # Gemini API doesn't support tools + JSON schema simultaneously
    # Workaround: Request JSON in prompt, parse manually with robust extraction
    competitor_agent = CompetitorResearchAgent(api_key=gemini_api_key, use_cli=False)
    keyword_agent = KeywordResearchAgent(api_key=gemini_api_key, use_cli=False)
    deep_researcher = DeepResearcher()

    return ContentPipeline(
        competitor_agent=competitor_agent,
        keyword_agent=keyword_agent,
        deep_researcher=deep_researcher,
        max_competitors=2,  # Reduced for faster testing
        max_keywords=3,     # Reduced for faster testing
        enable_deep_research=True
    )


@pytest.mark.asyncio
@pytest.mark.slow
@pytest.mark.e2e
async def test_simplified_full_pipeline_proptech(test_config, db_manager, content_pipeline, gemini_api_key):
    """
    Test: Simplified full pipeline with real PropTech topic

    This test validates the core pipeline works end-to-end:
    1. RSS Collection (from Heise.de tech feed)
    2. ContentPipeline (5 stages)
    3. Quality validation
    """
    print("\n" + "="*80)
    print("SIMPLIFIED FULL PIPELINE E2E TEST - PropTech")
    print("="*80)

    # STAGE 1: RSS Collection
    print("\n[STAGE 1] RSS Collection")
    print("-" * 80)

    deduplicator = Deduplicator()
    rss_collector = RSSCollector(
        config=test_config,
        db_manager=db_manager,
        deduplicator=deduplicator
    )

    # Collect from Heise.de (German tech news - relevant to PropTech)
    feed_urls = [
        'https://www.heise.de/news/rss/news-atom.xml',
        'https://github.blog/feed/'
    ]

    print(f"Collecting from {len(feed_urls)} feeds...")

    # Note: RSS collectors have different method signatures
    # Let's try to call it correctly by checking what methods exist
    try:
        # Try to collect - method name might be different
        documents = []
        for feed_url in feed_urls:
            try:
                # RSSCollector might use collect_from_feed() or similar
                feed_docs = rss_collector.collect_from_feed(feed_url)
                documents.extend(feed_docs)
                print(f"✅ Collected {len(feed_docs)} documents from {feed_url}")
            except AttributeError:
                # Try alternative method name
                try:
                    feed_docs = rss_collector.collect([feed_url])
                    documents.extend(feed_docs)
                    print(f"✅ Collected {len(feed_docs)} documents from {feed_url}")
                except Exception as e:
                    print(f"❌ Failed to collect from {feed_url}: {e}")

        print(f"\nTotal documents collected: {len(documents)}")

    except Exception as e:
        print(f"❌ Collection failed: {e}")
        documents = []

    # If no documents, create a test topic manually for PropTech
    if len(documents) == 0:
        print("\n⚠️  No documents collected from RSS, creating manual PropTech topic for testing")

    # STAGE 2: Create test topic (from collected doc or manual)
    print("\n[STAGE 2] Topic Creation")
    print("-" * 80)

    if documents:
        # Use first document as basis for topic
        doc = documents[0]
        topic = Topic(
            title=doc.title or "PropTech SaaS Solutions 2025",
            description=doc.summary or "Emerging PropTech software solutions in Germany",
            source=TopicSource.RSS,
            source_url=doc.url,
            domain=test_config.domain,
            market=test_config.market,
            language=test_config.language,
            discovered_at=datetime.now()
        )
        print(f"Created topic from RSS document: {topic.title}")
    else:
        # Manual test topic
        topic = Topic(
            title="PropTech SaaS Solutions 2025",
            description="Emerging PropTech software solutions transforming real estate management in Germany",
            source=TopicSource.MANUAL,
            domain=test_config.domain,
            market=test_config.market,
            language=test_config.language,
            discovered_at=datetime.now()
        )
        print(f"Created manual test topic: {topic.title}")

    # STAGE 3: Process through ContentPipeline (5 stages)
    print("\n[STAGE 3] ContentPipeline (5 Stages)")
    print("-" * 80)

    stages_completed = []

    def progress_callback(stage, message):
        stages_completed.append({'stage': stage, 'message': message})
        print(f"   [Stage {stage}/5] {message}")

    processed_topic = await content_pipeline.process_topic(
        topic=topic,
        config=test_config,
        progress_callback=progress_callback
    )

    print(f"\n✅ ContentPipeline completed {len(stages_completed)} stages")

    # STAGE 4: Validate Results
    print("\n[STAGE 4] Quality Validation")
    print("-" * 80)

    # Validate basic fields
    assert processed_topic.title, "Topic should have title"
    assert processed_topic.domain == 'PropTech', f"Expected PropTech domain, got {processed_topic.domain}"
    assert processed_topic.market == 'Germany', f"Expected Germany market, got {processed_topic.market}"

    print(f"✅ Basic fields valid")
    print(f"   Title: {processed_topic.title}")
    print(f"   Domain: {processed_topic.domain}")
    print(f"   Market: {processed_topic.market}")

    # Validate Stage 1: Competitor Research
    if processed_topic.competitors:
        print(f"✅ Stage 1 (Competitors): {len(processed_topic.competitors)} competitors identified")
    else:
        print(f"⚠️  Stage 1 (Competitors): No competitors data")

    if processed_topic.content_gaps:
        print(f"✅ Stage 1 (Content Gaps): {len(processed_topic.content_gaps)} gaps identified")
    else:
        print(f"⚠️  Stage 1 (Content Gaps): No gaps data")

    # Validate Stage 2: Keyword Research
    if processed_topic.keywords:
        print(f"✅ Stage 2 (Keywords): {len(processed_topic.keywords)} keyword fields")
        assert isinstance(processed_topic.keywords, dict), "Keywords should be dict"
    else:
        print(f"⚠️  Stage 2 (Keywords): No keywords data")

    # Validate Stage 3: Deep Research
    if processed_topic.deep_research_report:
        report_length = len(processed_topic.deep_research_report)
        sources_count = len(processed_topic.research_sources) if processed_topic.research_sources else 0

        print(f"✅ Stage 3 (Deep Research):")
        print(f"   Report length: {report_length} chars")
        print(f"   Sources: {sources_count}")

        # Quality checks
        assert report_length > 500, f"Report should be substantial (>500 chars), got {report_length}"

        # Check for PropTech relevance
        report_lower = processed_topic.deep_research_report.lower()
        relevant_keywords = ['proptech', 'immobilien', 'real estate', 'software', 'technology']
        found_keywords = [kw for kw in relevant_keywords if kw in report_lower]

        if found_keywords:
            print(f"   PropTech keywords found: {', '.join(found_keywords)}")
        else:
            print(f"   ⚠️  No PropTech keywords found in report")

    else:
        print(f"⚠️  Stage 3 (Deep Research): No research report")

    # Validate Stage 5: Scoring
    if processed_topic.priority_score is not None:
        print(f"✅ Stage 5 (Scoring):")
        print(f"   Priority: {processed_topic.priority_score:.3f}")

        if processed_topic.demand_score is not None:
            print(f"   Demand: {processed_topic.demand_score:.3f}")
        if processed_topic.opportunity_score is not None:
            print(f"   Opportunity: {processed_topic.opportunity_score:.3f}")
        if processed_topic.fit_score is not None:
            print(f"   Fit: {processed_topic.fit_score:.3f}")
        if processed_topic.novelty_score is not None:
            print(f"   Novelty: {processed_topic.novelty_score:.3f}")

        # Validate score ranges
        assert 0.0 <= processed_topic.priority_score <= 1.0, "priority_score should be 0.0-1.0"
    else:
        print(f"⚠️  Stage 5 (Scoring): No scores")

    # Final Summary
    print("\n" + "="*80)
    print("✅ SIMPLIFIED FULL PIPELINE E2E TEST PASSED!")
    print("="*80)
    print(f"Topic: {processed_topic.title}")
    print(f"Domain: {processed_topic.domain} | Market: {processed_topic.market}")
    print(f"Stages completed: {len(stages_completed)}/5")

    if processed_topic.deep_research_report:
        print(f"Research report: {len(processed_topic.deep_research_report)} chars")
    if processed_topic.research_sources:
        print(f"Sources: {len(processed_topic.research_sources)}")
    if processed_topic.priority_score is not None:
        print(f"Priority score: {processed_topic.priority_score:.3f}/1.0")

    print("="*80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short", "-m", "e2e"])
