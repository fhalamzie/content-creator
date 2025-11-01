"""
Tests for WritingAgent

TDD approach: Write failing tests first, then implement WritingAgent.

Test Coverage:
- German blog post generation
- Brand voice support (Professional, Casual, Technical, Friendly)
- Research data integration
- Prompt template loading from config/prompts/blog_de.md
- SEO metadata generation
- Cache integration
- Logging
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.agents.writing_agent import WritingAgent, WritingError


# ==================== Fixtures ====================

@pytest.fixture
def mock_base_agent_generate():
    """Mock BaseAgent.generate for writing"""
    with patch('src.agents.base_agent.BaseAgent.generate') as mock_gen:
        # Mock German blog post response
        mock_gen.return_value = {
            'content': """# KI-gestützte Content-Erstellung

## Einleitung

Künstliche Intelligenz revolutioniert...

## Hauptteil

...detailed content...

## Fazit

...conclusion...

---

## Quellen

1. https://example.com/source1
2. https://example.com/source2

---

## SEO-Metadaten

**Meta-Description**: KI revolutioniert Content Marketing (160 chars)

**Alt-Text Vorschläge**:
- Bild 1: AI content dashboard
- Bild 2: Marketing automation

**Interne Verlinkung**:
- SEO Best Practices
- Content Marketing Strategy""",
            'tokens': {'prompt': 1000, 'completion': 2000, 'total': 3000},
            'cost': 0.64
        }
        yield mock_gen


@pytest.fixture
def mock_cache_manager():
    """Mock CacheManager"""
    with patch('src.agents.writing_agent.CacheManager') as mock_cm:
        mock_instance = Mock()
        mock_instance.save_blog_post.return_value = "cache/blog_posts/test-slug.md"
        mock_cm.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_research_data():
    """Sample research data from ResearchAgent"""
    return {
        'sources': [
            {
                'url': 'https://example.com/article1',
                'title': 'AI in Marketing 2024',
                'snippet': 'Latest AI trends...'
            },
            {
                'url': 'https://example.com/article2',
                'title': 'Content Automation',
                'snippet': 'How to automate...'
            }
        ],
        'keywords': ['KI', 'Content Marketing', 'Automatisierung', 'SEO'],
        'summary': 'AI is transforming content marketing through automation...'
    }


# ==================== Initialization Tests ====================

def test_writing_agent_init_default(mock_base_agent_generate, mock_cache_manager):
    """Test WritingAgent initialization with defaults"""
    agent = WritingAgent(api_key="test-key")

    assert agent.agent_type == "writing"
    assert agent.language == "de"
    assert agent.prompt_template is not None


def test_writing_agent_init_custom_language(mock_base_agent_generate, mock_cache_manager):
    """Test WritingAgent initialization with custom language raises error if template missing"""
    # Only blog_de.md exists, so 'en' should fail
    with pytest.raises(WritingError, match="Prompt template not found"):
        agent = WritingAgent(api_key="test-key", language="en")


def test_writing_agent_loads_prompt_template(mock_base_agent_generate, mock_cache_manager):
    """Test that prompt template is loaded from blog_de.md"""
    agent = WritingAgent(api_key="test-key")

    # Should have loaded template
    assert agent.prompt_template is not None
    assert len(agent.prompt_template) > 0


def test_writing_agent_prompt_template_missing(mock_base_agent_generate, mock_cache_manager):
    """Test error when prompt template file is missing"""
    # Test with unsupported language (no template exists)
    with pytest.raises(WritingError, match="Prompt template not found"):
        WritingAgent(api_key="test-key", language="unsupported")


# ==================== Blog Post Generation Tests ====================

def test_write_blog_success(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test successful blog post generation"""
    agent = WritingAgent(api_key="test-key")

    result = agent.write_blog(
        topic="KI-gestützte Content-Erstellung",
        research_data=sample_research_data,
        brand_voice="Professional",
        target_audience="Marketing Managers"
    )

    # Verify result structure
    assert 'content' in result
    assert 'metadata' in result
    assert 'seo' in result
    assert 'tokens' in result
    assert 'cost' in result

    # Verify content
    assert len(result['content']) > 0
    assert 'KI-gestützte' in result['content']

    # Verify metadata
    assert result['metadata']['topic'] == "KI-gestützte Content-Erstellung"
    assert result['metadata']['brand_voice'] == "Professional"
    assert result['metadata']['language'] == "de"

    # Verify BaseAgent.generate was called
    mock_base_agent_generate.assert_called_once()


def test_write_blog_with_brand_voice_professional(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test blog generation with Professional brand voice"""
    agent = WritingAgent(api_key="test-key")
    agent.write_blog(
        topic="Test Topic",
        research_data=sample_research_data,
        brand_voice="Professional"
    )

    # Check that brand_voice is in the prompt
    call_args = mock_base_agent_generate.call_args
    prompt = call_args.kwargs.get('prompt', '')

    assert "Professional" in prompt


def test_write_blog_with_brand_voice_casual(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test blog generation with Casual brand voice"""
    agent = WritingAgent(api_key="test-key")
    agent.write_blog(
        topic="Test Topic",
        research_data=sample_research_data,
        brand_voice="Casual"
    )

    call_args = mock_base_agent_generate.call_args
    prompt = call_args.kwargs.get('prompt', '')

    assert "Casual" in prompt


def test_write_blog_includes_research_data(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test that research data is included in prompt"""
    agent = WritingAgent(api_key="test-key")
    agent.write_blog(
        topic="Test Topic",
        research_data=sample_research_data
    )

    call_args = mock_base_agent_generate.call_args
    prompt = call_args.kwargs.get('prompt', '')

    # Should include research summary or keywords
    assert any(keyword in prompt for keyword in sample_research_data['keywords'])


def test_write_blog_includes_keywords(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test that keywords from research are included in prompt"""
    agent = WritingAgent(api_key="test-key")
    agent.write_blog(
        topic="Test Topic",
        research_data=sample_research_data,
        primary_keyword="KI",
        secondary_keywords=["Content Marketing", "SEO"]
    )

    call_args = mock_base_agent_generate.call_args
    prompt = call_args.kwargs.get('prompt', '')

    assert "KI" in prompt
    assert "Content Marketing" in prompt


def test_write_blog_without_research_data(mock_base_agent_generate, mock_cache_manager):
    """Test blog generation without research data (should still work)"""
    agent = WritingAgent(api_key="test-key")

    result = agent.write_blog(
        topic="Test Topic",
        research_data=None  # No research
    )

    # Should still generate content
    assert 'content' in result
    mock_base_agent_generate.assert_called_once()


# ==================== Cache Integration Tests ====================

def test_write_blog_saves_to_cache(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test that blog post is saved to cache"""
    agent = WritingAgent(api_key="test-key", cache_dir="cache")

    result = agent.write_blog(
        topic="Test Topic",
        research_data=sample_research_data,
        save_to_cache=True
    )

    # Verify cache.save_blog_post was called
    mock_cache_manager.save_blog_post.assert_called_once()

    # Verify cache path in result
    assert 'cache_path' in result


def test_write_blog_skip_cache(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test blog generation without caching"""
    agent = WritingAgent(api_key="test-key")

    result = agent.write_blog(
        topic="Test Topic",
        research_data=sample_research_data,
        save_to_cache=False
    )

    # Should not call cache
    mock_cache_manager.save_blog_post.assert_not_called()

    # Should not have cache_path
    assert 'cache_path' not in result


# ==================== SEO Metadata Extraction Tests ====================

def test_extract_seo_metadata_from_content(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test SEO metadata extraction from generated content"""
    agent = WritingAgent(api_key="test-key")

    result = agent.write_blog(
        topic="Test Topic",
        research_data=sample_research_data
    )

    # Verify SEO metadata
    assert 'seo' in result
    assert 'meta_description' in result['seo']
    assert 'alt_texts' in result['seo']
    assert 'internal_links' in result['seo']


def test_extract_seo_metadata_handles_missing_sections(mock_base_agent_generate, mock_cache_manager):
    """Test SEO extraction when sections are missing"""
    # Mock response without SEO section
    mock_base_agent_generate.return_value = {
        'content': '# Title\n\nContent without SEO section',
        'tokens': {'prompt': 100, 'completion': 50, 'total': 150},
        'cost': 0.1
    }

    agent = WritingAgent(api_key="test-key")
    result = agent.write_blog(topic="Test")

    # Should have default SEO values
    assert result['seo']['meta_description'] == ""
    assert result['seo']['alt_texts'] == []
    assert result['seo']['internal_links'] == []


# ==================== Input Validation Tests ====================

def test_write_blog_empty_topic_raises_error(mock_base_agent_generate, mock_cache_manager):
    """Test that empty topic raises error"""
    agent = WritingAgent(api_key="test-key")

    with pytest.raises(WritingError, match="Topic is required"):
        agent.write_blog(topic="")


def test_write_blog_none_topic_raises_error(mock_base_agent_generate, mock_cache_manager):
    """Test that None topic raises error"""
    agent = WritingAgent(api_key="test-key")

    with pytest.raises(WritingError, match="Topic is required"):
        agent.write_blog(topic=None)


def test_write_blog_invalid_brand_voice(mock_base_agent_generate, mock_cache_manager):
    """Test that invalid brand voice raises warning but continues"""
    agent = WritingAgent(api_key="test-key")

    # Should not raise error, but may log warning
    result = agent.write_blog(
        topic="Test Topic",
        brand_voice="InvalidVoice"
    )

    # Should still generate content
    assert 'content' in result


# ==================== Logging Tests ====================

def test_write_blog_logs_generation(mock_base_agent_generate, mock_cache_manager, sample_research_data, caplog):
    """Test that blog generation is logged"""
    import logging
    caplog.set_level(logging.INFO)

    agent = WritingAgent(api_key="test-key")
    agent.write_blog(topic="Test Topic", research_data=sample_research_data)

    # Check for start log
    assert any("Writing blog post" in record.message for record in caplog.records)


def test_write_blog_logs_success(mock_base_agent_generate, mock_cache_manager, sample_research_data, caplog):
    """Test that successful generation is logged"""
    import logging
    caplog.set_level(logging.INFO)

    agent = WritingAgent(api_key="test-key")
    agent.write_blog(topic="Test Topic", research_data=sample_research_data)

    # Check for success log
    assert any("Blog post generated" in record.message or "complete" in record.message.lower() for record in caplog.records)


# ==================== Word Count Tests ====================

def test_write_blog_includes_word_count(mock_base_agent_generate, mock_cache_manager, sample_research_data):
    """Test that word count is included in metadata"""
    agent = WritingAgent(api_key="test-key")

    result = agent.write_blog(topic="Test Topic", research_data=sample_research_data)

    assert 'metadata' in result
    assert 'word_count' in result['metadata']
    assert isinstance(result['metadata']['word_count'], int)
    assert result['metadata']['word_count'] > 0


# ==================== Error Handling Tests ====================

def test_write_blog_handles_api_error(mock_base_agent_generate, mock_cache_manager):
    """Test error handling when API fails"""
    from src.agents.base_agent import AgentError
    mock_base_agent_generate.side_effect = AgentError("API failed")

    agent = WritingAgent(api_key="test-key")

    with pytest.raises(WritingError, match="Failed to generate"):
        agent.write_blog(topic="Test Topic")


def test_write_blog_handles_cache_error(mock_base_agent_generate, mock_cache_manager, sample_research_data, caplog):
    """Test handling of cache save errors"""
    import logging
    caplog.set_level(logging.ERROR)

    # Mock cache save error
    mock_cache_manager.save_blog_post.side_effect = Exception("Cache error")

    agent = WritingAgent(api_key="test-key", cache_dir="cache")

    # Should not raise error, but log it
    result = agent.write_blog(
        topic="Test Topic",
        research_data=sample_research_data,
        save_to_cache=True
    )

    # Should still have content
    assert 'content' in result

    # Should log error
    assert any("Cache" in record.message or "error" in record.message.lower() for record in caplog.records)
