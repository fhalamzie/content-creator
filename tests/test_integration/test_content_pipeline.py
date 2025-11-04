"""
Integration Tests for Complete Content Pipeline

Tests the full workflow:
Research → Writing → Cache → Notion Sync

These tests use mocked external APIs but test the actual integration
between our components (agents, cache, sync manager).
"""

import pytest
from unittest.mock import Mock, patch
import json

from src.agents.research_agent import ResearchAgent
from src.agents.writing_agent import WritingAgent
from src.cache_manager import CacheManager
from src.notion_integration.sync_manager import SyncManager


# ==================== Fixtures ====================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def mock_gemini_cli():
    """Mock Gemini CLI subprocess"""
    with patch('subprocess.run') as mock_run:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "sources": [
                {
                    "url": "https://example.com/ai-marketing",
                    "title": "AI Marketing Trends 2024",
                    "snippet": "Latest trends in AI-powered marketing..."
                }
            ],
            "keywords": ["KI", "Marketing", "Automatisierung", "Content"],
            "summary": "AI is transforming marketing through automation and personalization."
        })
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_openrouter_api():
    """Mock OpenRouter API for writing"""
    with patch('src.agents.base_agent.OpenAI') as mock_client:
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""# KI-gestützte Marketing Automatisierung

## Einleitung

Künstliche Intelligenz revolutioniert das Marketing durch automatisierte Prozesse und personalisierte Inhalte.

## Hauptteil

Die Integration von KI in Marketing-Workflows ermöglicht...

## Fazit

KI-basierte Automatisierung ist der Schlüssel zu effizientem Content Marketing.

---

## Quellen

1. https://example.com/ai-marketing

---

## SEO-Metadaten

**Meta-Description**: KI revolutioniert Marketing durch Automatisierung

**Alt-Text Vorschläge**:
- Bild 1: AI Marketing Dashboard
- Bild 2: Automation Workflow

**Interne Verlinkung**:
- Marketing Strategien
- Content Automatisierung
"""))]
        mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=2000, total_tokens=3000)

        mock_client.return_value.chat.completions.create.return_value = mock_response
        yield mock_client


@pytest.fixture
def mock_notion_client():
    """Mock NotionClient"""
    with patch('src.notion_integration.sync_manager.NotionClient') as mock_nc_class:
        mock_nc = Mock()
        mock_nc.create_page.return_value = {
            'id': 'notion-page-123',
            'url': 'https://notion.so/page-123'
        }
        mock_nc.database_ids = {
            'blog_posts': 'db-blog-123',
            'social_posts': 'db-social-123'
        }
        mock_nc_class.return_value = mock_nc
        yield mock_nc


@pytest.fixture
def mock_rate_limiter():
    """Mock RateLimiter"""
    with patch('src.notion_integration.sync_manager.RateLimiter') as mock_rl_class:
        mock_rl = Mock()
        mock_rl.rate = 2.5
        mock_rl.acquire.return_value = None
        mock_rl_class.return_value = mock_rl
        yield mock_rl


# ==================== Full Pipeline Tests ====================

def test_complete_pipeline_research_to_cache(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api
):
    """Test: Research → Writing → Cache (no Notion)"""

    # Step 1: Research
    research_agent = ResearchAgent(api_key="test-key")
    research_data = research_agent.research(
        topic="KI Marketing Automatisierung",
        language="de"
    )

    # Verify research output
    assert 'sources' in research_data
    assert 'keywords' in research_data
    assert 'summary' in research_data
    assert len(research_data['sources']) > 0

    # Step 2: Writing
    writing_agent = WritingAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    result = writing_agent.write_blog(
        topic="KI Marketing Automatisierung",
        research_data=research_data,
        brand_voice="Professional",
        target_audience="Marketing Managers",
        save_to_cache=True
    )

    # Verify writing output
    assert 'content' in result
    assert 'metadata' in result
    assert 'seo' in result
    assert 'cache_path' in result

    # Step 3: Verify cache
    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    cached_posts = cache_manager.get_cached_blog_posts()

    assert len(cached_posts) == 1
    assert cached_posts[0]['content'] == result['content']
    assert cached_posts[0]['metadata']['topic'] == "KI Marketing Automatisierung"


def test_complete_pipeline_research_to_notion(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api,
    mock_notion_client,
    mock_rate_limiter
):
    """Test: Research → Writing → Cache → Notion Sync"""

    # Step 1: Research
    research_agent = ResearchAgent(api_key="test-key")
    research_data = research_agent.research(
        topic="KI Marketing Automatisierung",
        language="de"
    )

    # Step 2: Writing with cache
    writing_agent = WritingAgent(
        api_key="test-key",
        cache_dir=temp_cache_dir
    )

    writing_agent.write_blog(
        topic="KI Marketing Automatisierung",
        research_data=research_data,
        save_to_cache=True
    )

    # Step 3: Sync to Notion
    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    sync_manager = SyncManager(
        cache_manager=cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    sync_results = sync_manager.sync_all_blog_posts()

    # Verify sync results
    assert sync_results['total'] == 1
    assert sync_results['successful'] == 1
    assert sync_results['failed'] == 0

    # Verify NotionClient was called
    mock_notion_client.create_page.assert_called_once()


def test_pipeline_with_progress_tracking(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api,
    mock_notion_client,
    mock_rate_limiter
):
    """Test: Full pipeline with progress callbacks"""

    progress_events = []

    def progress_callback(data):
        progress_events.append(data)

    # Research → Write → Cache
    research_agent = ResearchAgent(api_key="test-key")
    research_data = research_agent.research(topic="Test Topic", language="de")

    writing_agent = WritingAgent(api_key="test-key", cache_dir=temp_cache_dir)
    writing_agent.write_blog(
        topic="Test Topic",
        research_data=research_data,
        save_to_cache=True
    )

    # Sync with progress tracking
    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    sync_manager = SyncManager(
        cache_manager=cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    sync_manager.sync_all_blog_posts(progress_callback=progress_callback)

    # Verify progress events
    assert len(progress_events) > 0
    for event in progress_events:
        assert 'current' in event
        assert 'total' in event
        assert 'eta_seconds' in event
        assert 'message' in event


def test_pipeline_handles_research_failure(
    temp_cache_dir,
    mock_openrouter_api
):
    """Test: Pipeline handles research failures gracefully"""

    with patch('subprocess.run') as mock_run:
        # Simulate Gemini CLI failure
        mock_run.side_effect = Exception("CLI failed")

        # Research should fallback to API (also mocked)
        research_agent = ResearchAgent(api_key="test-key", use_cli=False)

        # Mock API fallback
        with patch.object(research_agent, 'generate') as mock_gen:
            mock_gen.return_value = {
                'content': json.dumps({
                    'sources': [],
                    'keywords': ['fallback'],
                    'summary': 'API fallback'
                }),
                'tokens': {'prompt': 100, 'completion': 50, 'total': 150},
                'cost': 0.0
            }

            research_data = research_agent.research(topic="Test")

            # Should have fallback data
            assert 'summary' in research_data
            assert research_data['summary'] == 'API fallback'


def test_pipeline_without_research_data(
    temp_cache_dir,
    mock_openrouter_api
):
    """Test: Pipeline works without research data"""

    # Write blog without research
    writing_agent = WritingAgent(api_key="test-key", cache_dir=temp_cache_dir)

    result = writing_agent.write_blog(
        topic="Test Topic Without Research",
        research_data=None,  # No research
        save_to_cache=True
    )

    # Should still generate content
    assert 'content' in result
    assert 'cache_path' in result

    # Verify cache
    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    cached_posts = cache_manager.get_cached_blog_posts()
    assert len(cached_posts) == 1


def test_pipeline_cost_calculation(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api
):
    """Test: Pipeline tracks costs correctly"""

    # Research (FREE)
    research_agent = ResearchAgent(api_key="test-key")
    research_data = research_agent.research(topic="Test", language="de")

    # Writing (with cost)
    writing_agent = WritingAgent(api_key="test-key", cache_dir=temp_cache_dir)
    result = writing_agent.write_blog(
        topic="Test",
        research_data=research_data,
        save_to_cache=True
    )

    # Verify cost tracking
    assert 'cost' in result
    assert isinstance(result['cost'], float)
    assert result['cost'] > 0  # Writing should have cost


def test_pipeline_multiple_posts_batch_sync(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api,
    mock_notion_client,
    mock_rate_limiter
):
    """Test: Multiple posts → Batch sync to Notion"""

    research_agent = ResearchAgent(api_key="test-key")
    writing_agent = WritingAgent(api_key="test-key", cache_dir=temp_cache_dir)

    # Generate 3 blog posts
    topics = [
        "KI Marketing",
        "Content Automatisierung",
        "SEO Optimierung"
    ]

    for topic in topics:
        research_data = research_agent.research(topic=topic, language="de")
        writing_agent.write_blog(
            topic=topic,
            research_data=research_data,
            save_to_cache=True
        )

    # Batch sync
    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    sync_manager = SyncManager(
        cache_manager=cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    results = sync_manager.sync_all_blog_posts()

    # Verify batch sync
    assert results['total'] == 3
    assert results['successful'] == 3
    assert results['failed'] == 0

    # Verify rate limiting applied
    assert mock_rate_limiter.acquire.call_count == 3


def test_pipeline_cache_persistence(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api
):
    """Test: Cache persists across restarts"""

    # Generate content
    research_agent = ResearchAgent(api_key="test-key")
    writing_agent = WritingAgent(api_key="test-key", cache_dir=temp_cache_dir)

    research_data = research_agent.research(topic="Test", language="de")
    result = writing_agent.write_blog(
        topic="Test",
        research_data=research_data,
        save_to_cache=True
    )

    original_content = result['content']

    # Simulate restart: create new cache manager
    cache_manager_2 = CacheManager(cache_dir=temp_cache_dir)
    cached_posts = cache_manager_2.get_cached_blog_posts()

    # Verify content persisted
    assert len(cached_posts) == 1
    assert cached_posts[0]['content'] == original_content


def test_pipeline_seo_metadata_preserved(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api,
    mock_notion_client,
    mock_rate_limiter
):
    """Test: SEO metadata preserved through pipeline"""

    # Research → Write
    research_agent = ResearchAgent(api_key="test-key")
    writing_agent = WritingAgent(api_key="test-key", cache_dir=temp_cache_dir)

    research_data = research_agent.research(topic="Test", language="de")
    result = writing_agent.write_blog(
        topic="Test",
        research_data=research_data,
        save_to_cache=True
    )

    # Verify SEO metadata in result
    assert 'seo' in result
    assert 'meta_description' in result['seo']
    assert 'alt_texts' in result['seo']
    assert 'internal_links' in result['seo']

    # Verify metadata in cache
    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    cached_posts = cache_manager.get_cached_blog_posts()

    assert len(cached_posts) == 1
    # SEO metadata is in the content, not separate metadata
    assert 'SEO-Metadaten' in cached_posts[0]['content']


# ==================== Error Recovery Tests ====================

def test_pipeline_recovers_from_sync_failure(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api,
    mock_notion_client,
    mock_rate_limiter
):
    """Test: Pipeline recovers from Notion sync failures"""

    # Generate content
    research_agent = ResearchAgent(api_key="test-key")
    writing_agent = WritingAgent(api_key="test-key", cache_dir=temp_cache_dir)

    research_data = research_agent.research(topic="Test", language="de")
    writing_agent.write_blog(
        topic="Test",
        research_data=research_data,
        save_to_cache=True
    )

    # First sync fails
    mock_notion_client.create_page.side_effect = Exception("Notion API down")

    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    sync_manager = SyncManager(
        cache_manager=cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter,
        max_retries=1  # Limit retries for test speed
    )

    results = sync_manager.sync_all_blog_posts()

    # Verify failure recorded
    assert results['failed'] == 1

    # Content still in cache
    cached_posts = cache_manager.get_cached_blog_posts()
    assert len(cached_posts) == 1

    # Fix Notion and retry
    mock_notion_client.create_page.side_effect = None
    mock_notion_client.create_page.return_value = {
        'id': 'page-123',
        'url': 'https://notion.so/page-123'
    }

    results_2 = sync_manager.sync_all_blog_posts()

    # Should succeed on retry
    assert results_2['successful'] == 1


def test_pipeline_partial_sync_failure(
    temp_cache_dir,
    mock_gemini_cli,
    mock_openrouter_api,
    mock_notion_client,
    mock_rate_limiter
):
    """Test: Pipeline handles partial sync failures"""

    # Generate 3 posts
    research_agent = ResearchAgent(api_key="test-key")
    writing_agent = WritingAgent(api_key="test-key", cache_dir=temp_cache_dir)

    for i in range(3):
        research_data = research_agent.research(topic=f"Test {i}", language="de")
        writing_agent.write_blog(
            topic=f"Test {i}",
            research_data=research_data,
            save_to_cache=True
        )

    # Fail on 2nd post
    mock_notion_client.create_page.side_effect = [
        {'id': 'page-1', 'url': 'https://notion.so/page-1'},  # Success
        Exception("Notion error"),  # Fail
        {'id': 'page-3', 'url': 'https://notion.so/page-3'}   # Success
    ]

    cache_manager = CacheManager(cache_dir=temp_cache_dir)
    sync_manager = SyncManager(
        cache_manager=cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter,
        max_retries=1
    )

    results = sync_manager.sync_all_blog_posts()

    # Verify partial success
    assert results['total'] == 3
    assert results['successful'] == 2
    assert results['failed'] == 1
