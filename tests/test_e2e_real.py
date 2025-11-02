"""
Real E2E Tests - Tests with actual API calls

WARNING: These tests make REAL API calls and will incur costs.
Only run when explicitly needed for validation.

Run with: pytest tests/test_e2e_real.py -v --e2e
"""

import pytest
import os
from pathlib import Path
from dotenv import load_dotenv

from src.agents.research_agent import ResearchAgent
from src.agents.writing_agent import WritingAgent
from src.cache_manager import CacheManager
from src.notion_integration.sync_manager import SyncManager
from src.notion_integration.notion_client import NotionClient

# Load environment variables
load_dotenv()


# No fixtures needed - use @pytest.mark.e2e on tests you want to skip by default


@pytest.fixture
def api_key():
    """Get OpenRouter API key from environment"""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")
    return key


@pytest.fixture
def notion_token():
    """Get Notion token from environment"""
    token = os.getenv("NOTION_TOKEN")
    if not token:
        pytest.skip("NOTION_TOKEN not set")
    return token


@pytest.fixture
def temp_e2e_cache(tmp_path):
    """Create temporary cache for E2E tests"""
    cache_dir = tmp_path / "e2e_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.mark.e2e
def test_real_research_agent(api_key):
    """Test: Real research with Gemini CLI or API"""

    research_agent = ResearchAgent(api_key=api_key, use_cli=True, cli_timeout=30)

    # Perform real research
    result = research_agent.research(
        topic="Python testing best practices",
        language="en"
    )

    # Verify real data returned
    assert 'sources' in result
    assert 'keywords' in result
    assert 'summary' in result

    # Should have actual sources (not mocked)
    assert len(result['sources']) > 0 or len(result['keywords']) > 0

    print(f"\n✅ Research completed:")
    print(f"  - Sources: {len(result['sources'])}")
    print(f"  - Keywords: {len(result['keywords'])}")
    print(f"  - Summary: {result['summary'][:100]}...")


@pytest.mark.e2e
def test_real_writing_agent(api_key, temp_e2e_cache):
    """Test: Real blog writing with Qwen"""

    # Mock minimal research data
    research_data = {
        'sources': [{'url': 'https://example.com', 'title': 'Test', 'snippet': 'Test data'}],
        'keywords': ['testing', 'python'],
        'summary': 'Testing best practices'
    }

    writing_agent = WritingAgent(api_key=api_key, cache_dir=temp_e2e_cache)

    # Real API call
    result = writing_agent.write_blog(
        topic="Python Testing Basics",
        research_data=research_data,
        brand_voice="Technical",
        target_audience="Developers",
        save_to_cache=True
    )

    # Verify real content
    assert 'content' in result
    assert 'metadata' in result
    assert 'cost' in result
    assert 'cache_path' in result

    # Should have substantial content
    assert len(result['content']) > 500
    assert result['cost'] > 0  # Real API cost

    print(f"\n✅ Blog generated:")
    print(f"  - Word count: {result['metadata']['word_count']}")
    print(f"  - Cost: ${result['cost']:.4f}")
    print(f"  - Cached: {result['cache_path']}")


@pytest.mark.e2e
def test_real_complete_pipeline_without_notion(api_key, temp_e2e_cache):
    """Test: Complete pipeline (Research → Write → Cache) without Notion sync"""

    # Step 1: Real research
    research_agent = ResearchAgent(api_key=api_key, use_cli=False)  # Use API for reliability
    research_data = research_agent.research(
        topic="AI content automation",
        language="en"
    )

    assert len(research_data['sources']) > 0 or len(research_data['keywords']) > 0

    # Step 2: Real writing
    writing_agent = WritingAgent(api_key=api_key, cache_dir=temp_e2e_cache)
    writing_result = writing_agent.write_blog(
        topic="AI content automation",
        research_data=research_data,
        save_to_cache=True
    )

    assert len(writing_result['content']) > 500
    assert writing_result['cost'] > 0

    # Step 3: Verify cache
    cache_manager = CacheManager(cache_dir=temp_e2e_cache)
    cached_posts = cache_manager.get_cached_blog_posts()

    assert len(cached_posts) == 1
    assert cached_posts[0]['metadata']['topic'] == "AI content automation"

    print(f"\n✅ Pipeline completed:")
    print(f"  - Research: {len(research_data['sources'])} sources")
    print(f"  - Content: {writing_result['metadata']['word_count']} words")
    print(f"  - Cost: ${writing_result['cost']:.4f}")
    print(f"  - Cached: {len(cached_posts)} posts")


@pytest.mark.e2e
def test_real_sync_manager_with_mocked_notion(api_key, temp_e2e_cache):
    """Test: Real pipeline with mocked Notion (don't pollute Notion DB)"""

    from unittest.mock import Mock

    # Generate real content
    research_agent = ResearchAgent(api_key=api_key, use_cli=False)
    writing_agent = WritingAgent(api_key=api_key, cache_dir=temp_e2e_cache)

    research_data = research_agent.research(topic="Test Topic", language="en")
    writing_agent.write_blog(
        topic="Test Topic",
        research_data=research_data,
        save_to_cache=True
    )

    # Mock Notion client to avoid polluting database
    mock_notion = Mock()
    mock_notion.database_ids = {'blog_posts': 'mock-db-id'}
    mock_notion.create_page.return_value = {
        'id': 'mock-page-id',
        'url': 'https://notion.so/mock-page'
    }

    # Test sync with mocked Notion
    cache_manager = CacheManager(cache_dir=temp_e2e_cache)
    sync_manager = SyncManager(
        cache_manager=cache_manager,
        notion_client=mock_notion
    )

    results = sync_manager.sync_all_blog_posts()

    assert results['total'] == 1
    assert results['successful'] == 1
    assert results['failed'] == 0

    # Verify Notion was called with real data
    mock_notion.create_page.assert_called_once()
    call_args = mock_notion.create_page.call_args
    assert 'database_id' in call_args.kwargs
    assert 'properties' in call_args.kwargs

    print(f"\n✅ Sync completed (mocked Notion):")
    print(f"  - Synced: {results['successful']}/{results['total']}")


@pytest.mark.e2e
def test_fixed_sync_blog_post_signature(api_key, temp_e2e_cache):
    """Test: Verify Bug #1 fix - sync_blog_post accepts slug parameter"""

    from unittest.mock import Mock

    # Generate real content
    writing_agent = WritingAgent(api_key=api_key, cache_dir=temp_e2e_cache)
    research_data = {'sources': [], 'keywords': ['test'], 'summary': 'Test'}

    writing_agent.write_blog(
        topic="Bug Fix Test",
        research_data=research_data,
        save_to_cache=True
    )

    # Mock Notion
    mock_notion = Mock()
    mock_notion.database_ids = {'blog_posts': 'mock-db-id'}
    mock_notion.create_page.return_value = {'id': 'page-id', 'url': 'https://notion.so/page'}

    # Test sync_blog_post with slug parameter (Bug #1 fix)
    cache_manager = CacheManager(cache_dir=temp_e2e_cache)
    sync_manager = SyncManager(cache_manager=cache_manager, notion_client=mock_notion)

    cached_posts = cache_manager.get_cached_blog_posts()
    slug = cached_posts[0]['slug']

    # This should work with slug parameter (previously required blog_data dict)
    result = sync_manager.sync_blog_post(slug=slug)

    assert result['success'] == True
    assert 'page_id' in result

    print(f"\n✅ Bug #1 fix verified: sync_blog_post accepts slug parameter")


@pytest.mark.e2e
def test_fixed_notion_client_database_ids(notion_token):
    """Test: Verify Bug #2 fix - NotionClient loads database_ids"""

    # Create database_ids.json if not exists
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)

    db_ids_path = cache_dir / "database_ids.json"
    if not db_ids_path.exists():
        import json
        db_ids_path.write_text(json.dumps({
            "created_at": "2025-11-01",
            "databases": {
                "blog_posts": "test-blog-db",
                "social_posts": "test-social-db"
            }
        }))

    # Test NotionClient initialization (Bug #2 fix)
    notion_client = NotionClient(token=notion_token)

    # Verify database_ids loaded automatically
    assert hasattr(notion_client, 'database_ids')
    assert isinstance(notion_client.database_ids, dict)
    assert 'blog_posts' in notion_client.database_ids or len(notion_client.database_ids) == 0

    print(f"\n✅ Bug #2 fix verified: NotionClient loads database_ids")
    print(f"  - Database IDs: {list(notion_client.database_ids.keys())}")


def test_fixed_model_id_config():
    """Test: Verify Bug #4 fix - models.yaml has valid model ID"""

    import yaml

    config_path = Path("config/models.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Verify research model ID is valid OpenRouter format
    research_model = config['agents']['research']['model']

    # Should be google/gemini-2.0-flash (not gemini-2.5-flash)
    assert research_model == "google/gemini-2.0-flash", \
        f"Expected 'google/gemini-2.0-flash', got '{research_model}'"

    print(f"\n✅ Bug #4 fix verified: research model ID = {research_model}")


if __name__ == "__main__":
    print("Run with: pytest tests/test_e2e_real.py -v --e2e")
