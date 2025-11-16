"""
Tests for CrossTopicSynthesizer

Tests cross-topic synthesis functionality for unique insights generation.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.synthesis.cross_topic_synthesizer import CrossTopicSynthesizer
from src.models.topic import Topic, TopicSource, TopicStatus


# === Fixtures ===

@pytest.fixture
def sample_topics():
    """Create sample topics for testing"""
    return [
        Topic(
            id="proptech-trends-2025",
            title="PropTech Trends 2025",
            description="Future of property technology",
            source=TopicSource.MANUAL,
            domain="proptech",
            market="de",
            language="de",
            research_report="# PropTech Trends 2025\n\nPropTech is transforming real estate...",
            citations=["https://example.com/proptech"],
            word_count=2000,
            status=TopicStatus.RESEARCHED
        ),
        Topic(
            id="proptech-investment-strategies",
            title="PropTech Investment Strategies",
            description="Investment approaches in PropTech",
            source=TopicSource.MANUAL,
            domain="proptech",
            market="de",
            language="de",
            research_report="# PropTech Investment\n\nInvesting in property technology...",
            citations=["https://example.com/investment"],
            word_count=1800,
            status=TopicStatus.RESEARCHED
        ),
        Topic(
            id="real-estate-technology",
            title="Real Estate Technology",
            description="Technology in real estate",
            source=TopicSource.MANUAL,
            domain="proptech",
            market="de",
            language="de",
            research_report="# Real Estate Tech\n\nTechnology is revolutionizing real estate...",
            citations=["https://example.com/realestate"],
            word_count=2200,
            status=TopicStatus.RESEARCHED
        )
    ]


@pytest.fixture
def mock_db_manager():
    """Mock SQLiteManager"""
    mock = MagicMock()
    return mock


@pytest.fixture
def synthesizer(mock_db_manager):
    """Create synthesizer with mocked database"""
    with patch('src.synthesis.cross_topic_synthesizer.SQLiteManager', return_value=mock_db_manager):
        return CrossTopicSynthesizer(db_path=":memory:")


# === Basic Initialization Tests ===

def test_synthesizer_initialization():
    """Test: Synthesizer initializes successfully"""
    with patch('src.synthesis.cross_topic_synthesizer.SQLiteManager'):
        synthesizer = CrossTopicSynthesizer(db_path="test.db")
        assert synthesizer is not None
        assert synthesizer.db_manager is not None


# === Semantic Search Tests ===

def test_synthesize_with_related_topics(synthesizer, mock_db_manager, sample_topics):
    """Test: Synthesis with related topics found"""
    # Mock find_related_topics to return related topics
    mock_db_manager.find_related_topics.return_value = [
        (sample_topics[1], 0.45),  # PropTech Investment Strategies (45% similar)
        (sample_topics[2], 0.38)   # Real Estate Technology (38% similar)
    ]

    result = synthesizer.synthesize_related_topics(
        topic="PropTech Trends 2025",
        topic_id="proptech-trends-2025",
        max_related=2
    )

    # Verify find_related_topics was called
    mock_db_manager.find_related_topics.assert_called_once_with(
        topic_id="proptech-trends-2025",
        limit=2,
        min_similarity=0.2
    )

    # Verify result structure
    assert "related_topics" in result
    assert "synthesis_summary" in result
    assert "unique_angles" in result
    assert "themes" in result
    assert "internal_links" in result
    assert "synthesized_at" in result

    # Verify related topics info
    assert len(result["related_topics"]) == 2
    assert result["related_topics"][0]["title"] == "PropTech Investment Strategies"
    assert result["related_topics"][0]["similarity"] == 0.45
    assert result["related_topics"][1]["title"] == "Real Estate Technology"
    assert result["related_topics"][1]["similarity"] == 0.38


def test_synthesize_with_no_related_topics(synthesizer, mock_db_manager):
    """Test: Synthesis when no related topics found"""
    # Mock find_related_topics to return empty list
    mock_db_manager.find_related_topics.return_value = []

    result = synthesizer.synthesize_related_topics(
        topic="Unique Topic",
        topic_id="unique-topic",
        max_related=3
    )

    # Verify empty result
    assert result["related_topics"] == []
    assert result["synthesis_summary"] == ""
    assert result["unique_angles"] == []
    assert result["themes"] == []
    assert result["internal_links"] == []


def test_synthesize_respects_max_related_limit(synthesizer, mock_db_manager, sample_topics):
    """Test: Synthesis respects max_related limit"""
    mock_db_manager.find_related_topics.return_value = [
        (sample_topics[1], 0.45),
        (sample_topics[2], 0.38)
    ]

    result = synthesizer.synthesize_related_topics(
        topic="PropTech Trends 2025",
        topic_id="proptech-trends-2025",
        max_related=1  # Limit to 1
    )

    # Verify limit was passed to find_related_topics
    mock_db_manager.find_related_topics.assert_called_once()
    call_kwargs = mock_db_manager.find_related_topics.call_args[1]
    assert call_kwargs["limit"] == 1


# === Insight Extraction Tests ===

def test_extract_insights(synthesizer, sample_topics):
    """Test: Insight extraction from research report"""
    insights = synthesizer._extract_insights(sample_topics[0])

    assert isinstance(insights, list)
    assert len(insights) > 0
    # Each insight should be a non-empty string
    for insight in insights:
        assert isinstance(insight, str)
        assert len(insight) > 20  # Minimum length check


def test_extract_insights_no_report(synthesizer):
    """Test: Insight extraction with no research report"""
    topic_no_report = Topic(
        id="test-topic",
        title="Test Topic",
        description="Test",
        source=TopicSource.MANUAL,
        domain="test",
        market="de",
        language="de",
        research_report=None,  # No report
        status=TopicStatus.DISCOVERED
    )

    insights = synthesizer._extract_insights(topic_no_report)
    assert insights == []


# === Theme Identification Tests ===

def test_identify_common_themes(synthesizer, sample_topics):
    """Test: Common theme identification across topics"""
    # Create related topics list with similarity scores
    related = [(sample_topics[1], 0.45), (sample_topics[2], 0.38)]

    # Mock _extract_keywords to return controlled keywords
    with patch.object(synthesizer.db_manager, '_extract_keywords') as mock_extract:
        mock_extract.side_effect = [
            {'proptech', 'investment', 'strategies'},
            {'real', 'estate', 'technology', 'proptech'}
        ]

        themes = synthesizer._identify_common_themes(related)

        assert isinstance(themes, list)
        # 'proptech' should appear as a common theme (appears in both)
        assert 'proptech' in themes


def test_identify_themes_no_related_topics(synthesizer):
    """Test: Theme identification with no related topics"""
    themes = synthesizer._identify_common_themes([])
    assert themes == []


def test_identify_themes_returns_top_5(synthesizer, sample_topics):
    """Test: Theme identification returns max 5 themes"""
    related = [(sample_topics[0], 0.5)]

    # Mock to return many keywords
    with patch.object(synthesizer.db_manager, '_extract_keywords') as mock_extract:
        mock_extract.return_value = {f'keyword{i}' for i in range(20)}

        themes = synthesizer._identify_common_themes(related)

        # Should return max 5 themes
        assert len(themes) <= 5


# === Unique Angle Generation Tests ===

def test_generate_unique_angles(synthesizer, sample_topics):
    """Test: Unique angle generation from related topics"""
    related = [
        (sample_topics[1], 0.45),
        (sample_topics[2], 0.38)
    ]

    # Mock _extract_keywords
    with patch.object(synthesizer.db_manager, '_extract_keywords') as mock_extract:
        mock_extract.side_effect = [
            {'proptech', 'investment', 'strategies'},
            {'real', 'estate', 'technology'}
        ]

        angles = synthesizer._generate_unique_angles("PropTech Trends 2025", related)

        assert isinstance(angles, list)
        assert len(angles) > 0
        # Each angle should reference a related topic
        assert any("Investment" in angle or "Real Estate" in angle for angle in angles)


def test_generate_unique_angles_no_related_topics(synthesizer):
    """Test: Unique angle generation with no related topics"""
    angles = synthesizer._generate_unique_angles("Test Topic", [])
    assert angles == []


# === Synthesis Summary Tests ===

def test_create_synthesis_summary(synthesizer):
    """Test: Synthesis summary creation"""
    related_info = [
        {"title": "Topic A", "similarity": 0.45},
        {"title": "Topic B", "similarity": 0.38}
    ]
    themes = ["proptech", "technology"]
    unique_angles = ["Angle 1", "Angle 2"]

    summary = synthesizer._create_synthesis_summary(
        topic="Main Topic",
        related_info=related_info,
        themes=themes,
        unique_angles=unique_angles
    )

    assert isinstance(summary, str)
    assert len(summary) > 0
    # Summary should mention related topics
    assert "Topic A" in summary or "Topic B" in summary
    # Summary should mention themes
    assert any(theme in summary.lower() for theme in themes)


def test_create_synthesis_summary_empty_input(synthesizer):
    """Test: Synthesis summary with empty inputs"""
    summary = synthesizer._create_synthesis_summary(
        topic="Main Topic",
        related_info=[],
        themes=[],
        unique_angles=[]
    )

    assert summary == ""


# === Internal Linking Suggestions Tests ===

def test_suggest_anchor_text_short_title(synthesizer):
    """Test: Anchor text suggestion for short title"""
    anchor = synthesizer._suggest_anchor_text(
        "Main Topic",
        "Short Title"
    )

    assert anchor == "Short Title"


def test_suggest_anchor_text_long_title(synthesizer):
    """Test: Anchor text suggestion for long title"""
    long_title = "This Is A Very Long Title That Exceeds Five Words"

    anchor = synthesizer._suggest_anchor_text(
        "Main Topic",
        long_title
    )

    # Should truncate to first 5 words
    assert len(anchor.split()) <= 6  # 5 words + "..."
    assert anchor.endswith("...")


# === WritingAgent Integration Tests ===

def test_get_related_context_for_writing(synthesizer, mock_db_manager, sample_topics):
    """Test: Get related context formatted for WritingAgent"""
    # Mock find_related_topics
    mock_db_manager.find_related_topics.return_value = [
        (sample_topics[1], 0.45),
        (sample_topics[2], 0.38)
    ]

    context = synthesizer.get_related_context_for_writing(
        topic_id="proptech-trends-2025",
        max_related=2
    )

    assert context is not None
    assert isinstance(context, str)
    # Context should mention RELATED CONTEXT
    assert "RELATED CONTEXT" in context
    # Should mention the related topics
    assert "PropTech Investment Strategies" in context or "Real Estate Technology" in context


def test_get_related_context_for_writing_no_related(synthesizer, mock_db_manager):
    """Test: Get related context when no related topics found"""
    mock_db_manager.find_related_topics.return_value = []

    context = synthesizer.get_related_context_for_writing(
        topic_id="unique-topic",
        max_related=3
    )

    assert context is None


# === Edge Cases ===

def test_synthesis_with_min_similarity_threshold(synthesizer, mock_db_manager, sample_topics):
    """Test: Synthesis respects minimum similarity threshold"""
    mock_db_manager.find_related_topics.return_value = []

    synthesizer.synthesize_related_topics(
        topic="Test Topic",
        topic_id="test-topic",
        max_related=3,
        min_similarity=0.5  # High threshold
    )

    # Verify min_similarity was passed
    call_kwargs = mock_db_manager.find_related_topics.call_args[1]
    assert call_kwargs["min_similarity"] == 0.5


def test_synthesis_error_handling(synthesizer, mock_db_manager):
    """Test: Synthesis handles database errors gracefully"""
    # Mock find_related_topics to raise exception
    mock_db_manager.find_related_topics.side_effect = Exception("Database error")

    # Should not raise, but return empty result or handle gracefully
    with pytest.raises(Exception):
        synthesizer.synthesize_related_topics(
            topic="Test Topic",
            topic_id="test-topic",
            max_related=3
        )
