"""
Integration Tests for Cross-Topic Synthesis

Tests the complete synthesis flow with real SQLite database and research data.
"""

import pytest
import tempfile
import os
from datetime import datetime

from src.database.sqlite_manager import SQLiteManager
from src.synthesis.cross_topic_synthesizer import CrossTopicSynthesizer
from src.models.topic import Topic, TopicSource, TopicStatus
from src.utils.research_cache import save_research_to_cache, load_research_from_cache


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def db_manager(temp_db):
    """Create database manager with temp database"""
    return SQLiteManager(db_path=temp_db)


@pytest.fixture
def sample_research_data(temp_db):
    """Create sample research data in database"""
    # Save 3 related PropTech topics with overlapping keywords
    topics = [
        {
            "topic": "PropTech Technology Trends 2025",
            "research_article": """
# PropTech Technology Trends 2025

PropTech (Property Technology) is revolutionizing the real estate industry.
Key trends include smart buildings, AI-powered property management, and blockchain for transactions.

## Smart Building Technology

IoT sensors and automation systems are transforming building management.
Energy efficiency and tenant comfort are improved through intelligent systems.

## AI and Machine Learning

Artificial intelligence is being used for property valuation, market analysis, and predictive maintenance.
Machine learning models can predict property values with increasing accuracy.

## Blockchain Integration

Blockchain technology enables secure, transparent property transactions.
Smart contracts automate many aspects of real estate deals.
            """,
            "sources": [
                {"url": "https://example.com/proptech", "title": "PropTech Overview"}
            ],
            "config": {"market": "Germany", "vertical": "PropTech", "language": "de"}
        },
        {
            "topic": "PropTech Smart Building Technology",
            "research_article": """
# PropTech Smart Building Technology

Building automation systems integrate IoT, AI, and cloud computing.
Focus areas include energy management, security, and tenant experience.

## Energy Management

Smart meters and AI optimize energy consumption.
Predictive analytics reduce costs and environmental impact.

## Security Systems

Integrated security with facial recognition and access control.
Real-time monitoring and incident response automation.
            """,
            "sources": [
                {"url": "https://example.com/smart-buildings", "title": "Smart Buildings"}
            ],
            "config": {"market": "Germany", "vertical": "PropTech", "language": "de"}
        },
        {
            "topic": "PropTech Investment Technology Platforms",
            "research_article": """
# PropTech Investment Technology Platforms

Technology platforms democratize real estate investing.
Fractional ownership and crowdfunding expand access to investors.

## Investment Platforms

Digital platforms connect investors with opportunities.
Analytics tools help evaluate investment potential.

## Risk Assessment

AI-powered risk models analyze market trends.
Automated portfolio management optimizes returns.
            """,
            "sources": [
                {"url": "https://example.com/investment", "title": "Real Estate Investment"}
            ],
            "config": {"market": "Germany", "vertical": "PropTech", "language": "de"}
        }
    ]

    # Save all topics to cache
    for topic_data in topics:
        save_research_to_cache(
            topic=topic_data["topic"],
            research_article=topic_data["research_article"],
            sources=topic_data["sources"],
            config=topic_data["config"],
            db_path=temp_db
        )

    return topics


# === Integration Tests ===

def test_find_related_topics_integration(db_manager, sample_research_data):
    """Test: Find related topics using real database"""
    # Find topics related to PropTech Technology Trends 2025
    related = db_manager.find_related_topics(
        topic_id="proptech-technology-trends-2025",
        limit=5,
        min_similarity=0.1  # Low threshold to find all related topics
    )

    # Should find 2 related topics
    assert len(related) == 2

    # Verify structure
    for topic, similarity in related:
        assert isinstance(topic, Topic)
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        # Verify research report exists
        assert topic.research_report is not None
        assert len(topic.research_report) > 0


def test_keyword_similarity_calculation(db_manager, sample_research_data):
    """Test: Keyword similarity calculation works correctly"""
    related = db_manager.find_related_topics(
        topic_id="proptech-technology-trends-2025",
        limit=5,
        min_similarity=0.1
    )

    # Extract titles
    titles = {topic.title for topic, _ in related}

    # Should find "PropTech Smart Building Technology" (shares: proptech, technology)
    # Should find "PropTech Investment Technology Platforms" (shares: proptech, technology)
    assert "PropTech Smart Building Technology" in titles or "PropTech Investment Technology Platforms" in titles


def test_cross_topic_synthesis_integration(temp_db, sample_research_data):
    """Test: Complete synthesis flow with real data"""
    synthesizer = CrossTopicSynthesizer(db_path=temp_db)

    # Synthesize insights for PropTech Technology Trends 2025
    result = synthesizer.synthesize_related_topics(
        topic="PropTech Technology Trends 2025",
        topic_id="proptech-technology-trends-2025",
        max_related=3
    )

    # Verify result structure
    assert "related_topics" in result
    assert "synthesis_summary" in result
    assert "unique_angles" in result
    assert "themes" in result
    assert "internal_links" in result

    # Should have found related topics
    assert len(result["related_topics"]) > 0

    # Verify each related topic has expected fields
    for topic_info in result["related_topics"]:
        assert "title" in topic_info
        assert "id" in topic_info
        assert "similarity" in topic_info
        assert 0.0 <= topic_info["similarity"] <= 1.0

    # Synthesis summary should be non-empty
    assert len(result["synthesis_summary"]) > 0

    # Should have identified common themes
    assert len(result["themes"]) > 0

    # Should have internal link suggestions
    assert len(result["internal_links"]) > 0


def test_get_related_context_for_writing_integration(temp_db, sample_research_data):
    """Test: Get formatted context for WritingAgent"""
    synthesizer = CrossTopicSynthesizer(db_path=temp_db)

    context = synthesizer.get_related_context_for_writing(
        topic_id="proptech-technology-trends-2025",
        max_related=2
    )

    # Should return formatted context string
    assert context is not None
    assert isinstance(context, str)
    assert len(context) > 0

    # Should contain key sections
    assert "RELATED CONTEXT" in context
    assert "SYNTHESIS" in context

    # Should mention at least one related topic (all share "PropTech" and "Technology")
    assert ("PropTech" in context or
            "Technology" in context or
            "Investment" in context)


def test_synthesis_with_no_related_topics_integration(temp_db, db_manager):
    """Test: Synthesis when topic has no related topics"""
    # Insert a unique topic with no related topics
    unique_topic = Topic(
        id="quantum-computing-xyz",
        title="Quantum Computing XYZ Applications",
        description="Unique quantum topic",
        source=TopicSource.MANUAL,
        domain="quantum",
        market="de",
        language="de",
        research_report="# Quantum Computing\n\nUnique research content...",
        citations=["https://example.com/quantum"],
        word_count=500,
        status=TopicStatus.RESEARCHED
    )

    db_manager.insert_topic(unique_topic)

    # Try to synthesize
    synthesizer = CrossTopicSynthesizer(db_path=temp_db)
    result = synthesizer.synthesize_related_topics(
        topic="Quantum Computing XYZ Applications",
        topic_id="quantum-computing-xyz",
        max_related=3
    )

    # Should return empty synthesis
    assert result["related_topics"] == []
    assert result["synthesis_summary"] == ""
    assert result["themes"] == []


def test_research_cache_integration(temp_db):
    """Test: Research cache save/load integration with synthesis"""
    # Save research to cache
    topic_id = save_research_to_cache(
        topic="AI-Powered Property Management",
        research_article="# AI Property Management\n\nAI is transforming property management...",
        sources=[{"url": "https://example.com/ai", "title": "AI in PropTech"}],
        config={"market": "Germany", "vertical": "PropTech", "language": "de"},
        db_path=temp_db
    )

    # Load from cache
    cached = load_research_from_cache("AI-Powered Property Management", db_path=temp_db)

    # Verify loaded data
    assert cached is not None
    assert cached["topic"] == "AI-Powered Property Management"
    assert len(cached["research_article"]) > 0

    # Verify topic is in database for synthesis
    db_manager = SQLiteManager(db_path=temp_db)
    topic = db_manager.get_topic(topic_id)

    assert topic is not None
    assert topic.research_report is not None


def test_similarity_threshold_filtering(db_manager, sample_research_data):
    """Test: Similarity threshold filters out low-similarity topics"""
    # Find with high similarity threshold
    related_high = db_manager.find_related_topics(
        topic_id="proptech-technology-trends-2025",
        limit=10,
        min_similarity=0.9  # Very high threshold
    )

    # Find with low similarity threshold
    related_low = db_manager.find_related_topics(
        topic_id="proptech-technology-trends-2025",
        limit=10,
        min_similarity=0.1  # Low threshold
    )

    # High threshold should return fewer (or zero) results
    assert len(related_high) <= len(related_low)


# === Performance Tests ===

def test_synthesis_performance(temp_db, sample_research_data):
    """Test: Synthesis completes in reasonable time"""
    import time

    synthesizer = CrossTopicSynthesizer(db_path=temp_db)

    start_time = time.time()

    result = synthesizer.synthesize_related_topics(
        topic="PropTech Technology Trends 2025",
        topic_id="proptech-technology-trends-2025",
        max_related=3
    )

    elapsed_time = time.time() - start_time

    # Should complete in under 1 second (CPU-only operations)
    assert elapsed_time < 1.0

    # Should have produced valid result
    assert len(result["related_topics"]) > 0
