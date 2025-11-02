"""
Tests for SyncManager

TDD approach: Write failing tests first, then implement SyncManager.

Test Coverage:
- Initialization with CacheManager, NotionClient, RateLimiter
- Single blog post sync (cache → Notion)
- Batch blog post sync
- Social posts sync
- Progress callback functionality
- ETA calculation
- Error handling (cache errors, Notion errors, network errors)
- Retry logic
- Logging
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import time

from src.notion_integration.sync_manager import SyncManager, SyncError


# ==================== Fixtures ====================

@pytest.fixture
def mock_cache_manager():
    """Mock CacheManager"""
    mock_cm = Mock()

    # Mock get_cached_blog_posts
    mock_cm.get_cached_blog_posts.return_value = [
        {
            'slug': 'test-post-1',
            'content': '# Test Post 1\n\nContent here...',
            'metadata': {
                'topic': 'Test Topic 1',
                'word_count': 1500,
                'language': 'de'
            }
        },
        {
            'slug': 'test-post-2',
            'content': '# Test Post 2\n\nContent here...',
            'metadata': {
                'topic': 'Test Topic 2',
                'word_count': 2000,
                'language': 'de'
            }
        }
    ]

    # Mock get_cached_social_posts
    mock_cm.get_cached_social_posts.return_value = [
        {
            'platform': 'linkedin',
            'content': 'LinkedIn post content',
            'blog_slug': 'test-post-1'
        },
        {
            'platform': 'facebook',
            'content': 'Facebook post content',
            'blog_slug': 'test-post-1'
        }
    ]

    # Mock read_blog_post to return data based on slug
    def read_blog_post_side_effect(slug):
        blog_posts = {
            'test-post-1': {
                'content': '# Test Post 1\n\nContent here...',
                'metadata': {
                    'topic': 'Test Topic 1',
                    'word_count': 1500,
                    'language': 'de'
                }
            },
            'test-post-2': {
                'content': '# Test Post 2\n\nContent here...',
                'metadata': {
                    'topic': 'Test Topic 2',
                    'word_count': 2000,
                    'language': 'de'
                }
            }
        }
        return blog_posts.get(slug, {'content': '', 'metadata': {}})

    mock_cm.read_blog_post.side_effect = read_blog_post_side_effect

    return mock_cm


@pytest.fixture
def mock_notion_client():
    """Mock NotionClient"""
    mock_nc = Mock()

    # Mock create_page
    mock_nc.create_page.return_value = {
        'id': 'page-123',
        'url': 'https://notion.so/page-123'
    }

    # Mock update_page
    mock_nc.update_page.return_value = {
        'id': 'page-123',
        'url': 'https://notion.so/page-123'
    }

    # Mock database IDs
    mock_nc.database_ids = {
        'blog_posts': 'db-blog-123',
        'social_posts': 'db-social-123'
    }

    return mock_nc


@pytest.fixture
def mock_rate_limiter():
    """Mock RateLimiter"""
    mock_rl = Mock()
    mock_rl.rate = 2.5  # 2.5 req/sec
    mock_rl.acquire.return_value = None  # No delay
    return mock_rl


# ==================== Initialization Tests ====================

def test_sync_manager_init(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test SyncManager initialization"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    assert sync_manager.cache_manager == mock_cache_manager
    assert sync_manager.notion_client == mock_notion_client
    assert sync_manager.rate_limiter == mock_rate_limiter


def test_sync_manager_init_creates_components_if_not_provided():
    """Test SyncManager creates default components if not provided"""
    with patch('src.notion_integration.sync_manager.CacheManager') as mock_cm, \
         patch('src.notion_integration.sync_manager.NotionClient') as mock_nc, \
         patch('src.notion_integration.sync_manager.RateLimiter') as mock_rl:

        sync_manager = SyncManager()

        # Should create default components
        mock_cm.assert_called_once()
        mock_nc.assert_called_once()
        mock_rl.assert_called_once()


# ==================== Single Blog Post Sync Tests ====================

def test_sync_blog_post_success(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test successful single blog post sync"""
    # Mock cache_manager.read_blog_post to return test data
    mock_cache_manager.read_blog_post.return_value = {
        'content': '# Test Post\n\nContent',
        'metadata': {
            'topic': 'Test Topic',
            'word_count': 1500
        }
    }

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    result = sync_manager.sync_blog_post('test-post')

    # Verify result
    assert result['success'] is True
    assert result['page_id'] == 'page-123'
    assert result['url'] == 'https://notion.so/page-123'

    # Verify NotionClient.create_page was called
    mock_notion_client.create_page.assert_called_once()

    # Verify rate limiter was used
    mock_rate_limiter.acquire.assert_called_once()


def test_sync_blog_post_with_progress_callback(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test blog post sync with progress callback"""
    # Mock cache_manager.read_blog_post
    mock_cache_manager.read_blog_post.return_value = {
        'content': '# Test Post',
        'metadata': {'topic': 'Test'}
    }

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    progress_callback = Mock()

    sync_manager.sync_blog_post('test-post', progress_callback=progress_callback)

    # Verify callback was called
    progress_callback.assert_called()


def test_sync_blog_post_handles_notion_error(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test error handling when Notion API fails"""
    # Mock cache_manager.read_blog_post
    mock_cache_manager.read_blog_post.return_value = {
        'content': '# Test',
        'metadata': {'topic': 'Test'}
    }

    mock_notion_client.create_page.side_effect = Exception("Notion API error")

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    with pytest.raises(SyncError, match="Failed to sync blog post"):
        sync_manager.sync_blog_post('test-post')


# ==================== Batch Blog Post Sync Tests ====================

def test_sync_all_blog_posts_success(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test successful batch blog post sync"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    results = sync_manager.sync_all_blog_posts()

    # Verify results
    assert results['total'] == 2
    assert results['successful'] == 2
    assert results['failed'] == 0

    # Verify NotionClient.create_page called twice (2 cached posts)
    assert mock_notion_client.create_page.call_count == 2

    # Verify rate limiter called twice
    assert mock_rate_limiter.acquire.call_count == 2


def test_sync_all_blog_posts_with_progress_callback(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test batch sync with progress callback"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    progress_callback = Mock()

    sync_manager.sync_all_blog_posts(progress_callback=progress_callback)

    # Verify callback called for each post
    assert progress_callback.call_count >= 2


def test_sync_all_blog_posts_partial_failure(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test batch sync with some failures"""
    # First call succeeds, second fails
    mock_notion_client.create_page.side_effect = [
        {'id': 'page-1', 'url': 'https://notion.so/page-1'},
        Exception("Notion error")
    ]

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    results = sync_manager.sync_all_blog_posts()

    # Verify partial success
    assert results['total'] == 2
    assert results['successful'] == 1
    assert results['failed'] == 1


def test_sync_all_blog_posts_no_cached_posts(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test batch sync with no cached posts"""
    mock_cache_manager.get_cached_blog_posts.return_value = []

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    results = sync_manager.sync_all_blog_posts()

    # Verify no syncs
    assert results['total'] == 0
    assert results['successful'] == 0
    assert results['failed'] == 0

    # Verify NotionClient not called
    mock_notion_client.create_page.assert_not_called()


# ==================== Social Posts Sync Tests ====================

def test_sync_social_posts_success(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test successful social posts sync"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    results = sync_manager.sync_all_social_posts()

    # Verify results
    assert results['total'] == 2
    assert results['successful'] == 2
    assert results['failed'] == 0

    # Verify NotionClient.create_page called twice
    assert mock_notion_client.create_page.call_count == 2


# ==================== ETA Calculation Tests ====================

def test_calculate_eta(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test ETA calculation"""
    mock_rate_limiter.rate = 2.5  # 2.5 req/sec

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    # 10 items at 2.5 req/sec = 4 seconds
    eta = sync_manager.calculate_eta(num_items=10)

    assert eta == pytest.approx(4.0, rel=0.1)


def test_calculate_eta_zero_items(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test ETA calculation with zero items"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    eta = sync_manager.calculate_eta(num_items=0)

    assert eta == 0.0


# ==================== Progress Callback Tests ====================

def test_progress_callback_format(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test progress callback receives correct format"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    progress_callback = Mock()

    sync_manager.sync_all_blog_posts(progress_callback=progress_callback)

    # Verify callback called with dict containing progress info
    for call_args in progress_callback.call_args_list:
        progress_data = call_args[0][0]
        assert 'current' in progress_data
        assert 'total' in progress_data
        assert 'eta_seconds' in progress_data
        assert 'message' in progress_data


def test_progress_callback_eta_decreases(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test that ETA decreases as sync progresses"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    progress_callback = Mock()

    sync_manager.sync_all_blog_posts(progress_callback=progress_callback)

    # Get ETAs from callbacks
    etas = [call[0][0]['eta_seconds'] for call in progress_callback.call_args_list]

    # Verify ETAs decrease (or stay same if instant)
    for i in range(len(etas) - 1):
        assert etas[i] >= etas[i + 1]


# ==================== Error Handling Tests ====================

def test_sync_continues_after_error(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test that batch sync continues after individual errors"""
    # Fail on first, succeed on second
    mock_notion_client.create_page.side_effect = [
        Exception("Error on first"),
        {'id': 'page-2', 'url': 'https://notion.so/page-2'}
    ]

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    results = sync_manager.sync_all_blog_posts()

    # Verify second item succeeded
    assert results['successful'] == 1
    assert results['failed'] == 1


def test_sync_logs_errors(mock_cache_manager, mock_notion_client, mock_rate_limiter, caplog):
    """Test that sync errors are logged"""
    import logging
    caplog.set_level(logging.ERROR)

    # Mock cache_manager.read_blog_post
    mock_cache_manager.read_blog_post.return_value = {
        'content': '# Test',
        'metadata': {'topic': 'Test'}
    }

    mock_notion_client.create_page.side_effect = Exception("Sync error")

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    try:
        sync_manager.sync_blog_post('test')
    except SyncError:
        pass

    # Verify error logged
    assert any("error" in record.message.lower() for record in caplog.records)


# ==================== Retry Logic Tests ====================

def test_sync_retries_on_failure(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test retry logic on transient failures"""
    # Mock cache_manager.read_blog_post
    mock_cache_manager.read_blog_post.return_value = {
        'content': '# Test',
        'metadata': {'topic': 'Test'}
    }

    # Fail twice, succeed on third
    mock_notion_client.create_page.side_effect = [
        Exception("Transient error 1"),
        Exception("Transient error 2"),
        {'id': 'page-123', 'url': 'https://notion.so/page-123'}
    ]

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter,
        max_retries=3
    )

    result = sync_manager.sync_blog_post('test')

    # Should succeed after retries
    assert result['success'] is True

    # Verify 3 attempts made
    assert mock_notion_client.create_page.call_count == 3


def test_sync_fails_after_max_retries(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test failure after exceeding max retries"""
    # Mock cache_manager.read_blog_post
    mock_cache_manager.read_blog_post.return_value = {
        'content': '# Test',
        'metadata': {'topic': 'Test'}
    }

    mock_notion_client.create_page.side_effect = Exception("Persistent error")

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter,
        max_retries=3
    )

    with pytest.raises(SyncError):
        sync_manager.sync_blog_post('test')

    # Verify 3 attempts made
    assert mock_notion_client.create_page.call_count == 3


# ==================== Logging Tests ====================

def test_sync_logs_start(mock_cache_manager, mock_notion_client, mock_rate_limiter, caplog):
    """Test that sync start is logged"""
    import logging
    caplog.set_level(logging.INFO)

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    sync_manager.sync_all_blog_posts()

    # Verify start log
    assert any("Syncing" in record.message or "sync" in record.message.lower() for record in caplog.records)


def test_sync_logs_success(mock_cache_manager, mock_notion_client, mock_rate_limiter, caplog):
    """Test that successful sync is logged"""
    import logging
    caplog.set_level(logging.INFO)

    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    sync_manager.sync_all_blog_posts()

    # Verify success log
    assert any("success" in record.message.lower() or "complete" in record.message.lower() for record in caplog.records)


# ==================== Integration Tests ====================

def test_sync_respects_rate_limit(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test that sync respects rate limiting"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    sync_manager.sync_all_blog_posts()

    # Verify rate limiter acquired for each sync
    assert mock_rate_limiter.acquire.call_count == 2


def test_sync_batch_creates_correct_notion_pages(mock_cache_manager, mock_notion_client, mock_rate_limiter):
    """Test that batch sync creates pages with correct data"""
    sync_manager = SyncManager(
        cache_manager=mock_cache_manager,
        notion_client=mock_notion_client,
        rate_limiter=mock_rate_limiter
    )

    sync_manager.sync_all_blog_posts()

    # Verify create_page called with correct database and properties
    for call_obj in mock_notion_client.create_page.call_args_list:
        # Access kwargs
        database_id = call_obj.kwargs.get('database_id') or (call_obj.args[0] if call_obj.args else None)
        properties = call_obj.kwargs.get('properties') or (call_obj.args[1] if len(call_obj.args) > 1 else None)

        assert database_id == 'db-blog-123'
        assert 'Title' in properties
