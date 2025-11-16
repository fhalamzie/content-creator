"""
Unit tests for SocialPostsSync

Tests social media post synchronization to Notion with:
- Single post sync
- Batch sync (4 platforms)
- Property mapping
- Error handling
- Statistics tracking
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from src.notion_integration.social_posts_sync import SocialPostsSync, SocialPostsSyncError


# ==================== Fixtures ====================

@pytest.fixture
def mock_notion_client():
    """Mock NotionClient"""
    with patch('src.notion_integration.social_posts_sync.NotionClient') as mock:
        client = Mock()
        client.create_page.return_value = {
            'id': 'page_123',
            'url': 'https://notion.so/page_123'
        }
        mock.return_value = client
        yield client


@pytest.fixture
def social_posts_sync(mock_notion_client):
    """Create SocialPostsSync instance"""
    return SocialPostsSync(
        notion_token="test_token",
        social_posts_db_id="social_db_123",
        blog_posts_db_id="blog_db_456",
        rate_limit=2.5
    )


@pytest.fixture
def sample_social_post():
    """Sample social post from RepurposingAgent"""
    return {
        'platform': 'LinkedIn',
        'content': 'This is a test post about PropTech trends.',
        'hashtags': ['#PropTech', '#Innovation', '#RealEstate'],
        'character_count': 42,
        'image': {
            'url': 'https://replicate.delivery/test.png',
            'provider': 'pillow',
            'cost': 0.0
        },
        'cost': 0.0008,
        'tokens': {'prompt': 200, 'completion': 150, 'total': 350}
    }


@pytest.fixture
def sample_social_posts_batch():
    """Sample batch of 4 social posts"""
    return [
        {
            'platform': 'LinkedIn',
            'content': 'LinkedIn post content...',
            'hashtags': ['#PropTech', '#B2B'],
            'character_count': 450,
            'image': {'url': 'https://example.com/linkedin.png', 'provider': 'pillow', 'cost': 0.0},
            'cost': 0.0008,
            'tokens': {'total': 350}
        },
        {
            'platform': 'Facebook',
            'content': 'Facebook post content...',
            'hashtags': ['#PropTech'],
            'character_count': 230,
            'image': {'url': 'https://example.com/facebook.png', 'provider': 'pillow', 'cost': 0.0},
            'cost': 0.0008,
            'tokens': {'total': 340}
        },
        {
            'platform': 'Instagram',
            'content': 'Instagram post content...',
            'hashtags': ['#PropTech', '#Innovation', '#Tech'],
            'character_count': 180,
            'image': {'url': 'https://example.com/instagram.png', 'provider': 'flux-dev', 'cost': 0.003},
            'cost': 0.0038,
            'tokens': {'total': 320}
        },
        {
            'platform': 'TikTok',
            'content': 'TikTok post content...',
            'hashtags': ['#PropTech', '#Innovation'],
            'character_count': 150,
            'image': {'url': 'https://example.com/tiktok.png', 'provider': 'flux-dev', 'cost': 0.003},
            'cost': 0.0038,
            'tokens': {'total': 310}
        }
    ]


# ==================== Initialization Tests ====================

def test_init_success(mock_notion_client):
    """Test successful initialization"""
    sync = SocialPostsSync(
        notion_token="test_token",
        social_posts_db_id="social_db_123",
        blog_posts_db_id="blog_db_456"
    )

    assert sync.social_posts_db_id == "social_db_123"
    assert sync.blog_posts_db_id == "blog_db_456"
    assert sync.total_synced == 0
    assert sync.failed_syncs == 0


def test_init_empty_token():
    """Test initialization with empty token raises ValueError"""
    with pytest.raises(ValueError, match="Notion token cannot be empty"):
        SocialPostsSync(notion_token="")


def test_init_whitespace_token():
    """Test initialization with whitespace token raises ValueError"""
    with pytest.raises(ValueError, match="Notion token cannot be empty"):
        SocialPostsSync(notion_token="   ")


def test_init_without_database_ids(mock_notion_client):
    """Test initialization without database IDs (optional)"""
    sync = SocialPostsSync(notion_token="test_token")

    assert sync.social_posts_db_id is None
    assert sync.blog_posts_db_id is None


# ==================== Single Post Sync Tests ====================

def test_sync_social_post_success(social_posts_sync, sample_social_post, mock_notion_client):
    """Test successful single post sync"""
    result = social_posts_sync.sync_social_post(
        social_post=sample_social_post,
        blog_title="PropTech Trends 2025",
        blog_post_id="blog_page_789"
    )

    # Verify result
    assert result['id'] == 'page_123'
    assert result['action'] == 'created'
    assert result['platform'] == 'LinkedIn'
    assert result['url'] == 'https://notion.so/page_123'

    # Verify NotionClient.create_page was called
    assert mock_notion_client.create_page.called
    call_args = mock_notion_client.create_page.call_args

    assert call_args[1]['parent_database_id'] == "social_db_123"
    assert call_args[1]['retry'] is True

    # Verify statistics
    assert social_posts_sync.total_synced == 1
    assert social_posts_sync.failed_syncs == 0


def test_sync_social_post_without_database_id(social_posts_sync, sample_social_post):
    """Test sync without database ID raises error"""
    social_posts_sync.social_posts_db_id = None

    with pytest.raises(SocialPostsSyncError, match="Social posts database ID not set"):
        social_posts_sync.sync_social_post(
            social_post=sample_social_post,
            blog_title="Test"
        )


def test_sync_social_post_without_image(social_posts_sync, mock_notion_client):
    """Test sync post without image (text-only mode)"""
    post_without_image = {
        'platform': 'LinkedIn',
        'content': 'Test content',
        'hashtags': ['#Test'],
        'character_count': 12,
        'cost': 0.0008,
        'tokens': {'total': 100}
    }

    result = social_posts_sync.sync_social_post(
        social_post=post_without_image,
        blog_title="Test Blog"
    )

    assert result['action'] == 'created'

    # Verify properties don't include Media URL
    call_args = mock_notion_client.create_page.call_args
    properties = call_args[1]['properties']
    assert 'Media URL' not in properties


def test_sync_social_post_with_blog_relation(social_posts_sync, sample_social_post, mock_notion_client):
    """Test sync with blog post relation"""
    social_posts_sync.sync_social_post(
        social_post=sample_social_post,
        blog_title="Test Blog",
        blog_post_id="blog_page_789"
    )

    call_args = mock_notion_client.create_page.call_args
    properties = call_args[1]['properties']

    # Verify Blog Post relation
    assert 'Blog Post' in properties
    assert properties['Blog Post']['relation'][0]['id'] == "blog_page_789"


def test_sync_social_post_without_blog_relation(social_posts_sync, sample_social_post, mock_notion_client):
    """Test sync without blog post relation"""
    social_posts_sync.sync_social_post(
        social_post=sample_social_post,
        blog_title="Test Blog"
        # blog_post_id NOT provided
    )

    call_args = mock_notion_client.create_page.call_args
    properties = call_args[1]['properties']

    # Verify Blog Post relation is NOT included
    assert 'Blog Post' not in properties


def test_sync_social_post_api_failure(social_posts_sync, sample_social_post, mock_notion_client):
    """Test sync failure due to Notion API error"""
    mock_notion_client.create_page.side_effect = Exception("Notion API error")

    with pytest.raises(SocialPostsSyncError, match="Failed to sync LinkedIn post"):
        social_posts_sync.sync_social_post(
            social_post=sample_social_post,
            blog_title="Test"
        )

    # Verify statistics
    assert social_posts_sync.total_synced == 0
    assert social_posts_sync.failed_syncs == 1


# ==================== Batch Sync Tests ====================

def test_sync_social_posts_batch_success(social_posts_sync, sample_social_posts_batch, mock_notion_client):
    """Test successful batch sync of 4 platforms"""
    result = social_posts_sync.sync_social_posts_batch(
        social_posts=sample_social_posts_batch,
        blog_title="PropTech Trends 2025",
        blog_post_id="blog_page_789"
    )

    # Verify results
    assert result['total'] == 4
    assert result['by_platform'] == {
        'LinkedIn': 1,
        'Facebook': 1,
        'Instagram': 1,
        'TikTok': 1
    }
    assert result['failed'] == 0

    # Verify NotionClient.create_page called 4 times
    assert mock_notion_client.create_page.call_count == 4

    # Verify statistics
    assert social_posts_sync.total_synced == 4
    assert social_posts_sync.failed_syncs == 0


def test_sync_social_posts_batch_partial_failure_skip_errors(
    social_posts_sync,
    sample_social_posts_batch,
    mock_notion_client
):
    """Test batch sync with partial failure (skip_errors=True)"""
    # Make 2nd post (Facebook) fail
    call_count = [0]

    def create_page_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:  # Facebook (2nd call)
            raise Exception("Notion API error")
        return {'id': f'page_{call_count[0]}', 'url': f'https://notion.so/page_{call_count[0]}'}

    mock_notion_client.create_page.side_effect = create_page_side_effect

    result = social_posts_sync.sync_social_posts_batch(
        social_posts=sample_social_posts_batch,
        blog_title="Test",
        skip_errors=True
    )

    # Verify results: 3 successful (LinkedIn, Instagram, TikTok), 1 failed (Facebook)
    assert result['total'] == 3
    assert result['failed'] == 1
    assert 'Facebook' not in result['by_platform']  # Failed post not counted

    # Verify statistics
    assert social_posts_sync.total_synced == 3
    assert social_posts_sync.failed_syncs == 1


def test_sync_social_posts_batch_partial_failure_raise_error(
    social_posts_sync,
    sample_social_posts_batch,
    mock_notion_client
):
    """Test batch sync with partial failure (skip_errors=False)"""
    # Make 2nd post (Facebook) fail
    call_count = [0]

    def create_page_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:  # Facebook (2nd call)
            raise Exception("Notion API error")
        return {'id': f'page_{call_count[0]}', 'url': f'https://notion.so/page_{call_count[0]}'}

    mock_notion_client.create_page.side_effect = create_page_side_effect

    with pytest.raises(SocialPostsSyncError, match="Failed to sync Facebook post"):
        social_posts_sync.sync_social_posts_batch(
            social_posts=sample_social_posts_batch,
            blog_title="Test",
            skip_errors=False  # Raise on first error
        )

    # Verify statistics: 1 successful (LinkedIn), 1 failed (Facebook)
    assert social_posts_sync.total_synced == 1
    assert social_posts_sync.failed_syncs == 1


def test_sync_social_posts_batch_empty_list(social_posts_sync):
    """Test batch sync with empty list"""
    result = social_posts_sync.sync_social_posts_batch(
        social_posts=[],
        blog_title="Test"
    )

    assert result['total'] == 0
    assert result['by_platform'] == {}
    assert result['failed'] == 0


# ==================== Property Mapping Tests ====================

def test_build_social_post_properties_complete(social_posts_sync, sample_social_post):
    """Test property mapping with all fields"""
    properties = social_posts_sync._build_social_post_properties(
        social_post=sample_social_post,
        blog_title="PropTech Trends 2025",
        blog_post_id="blog_page_789"
    )

    # Title
    assert properties['Title']['title'][0]['text']['content'] == "PropTech Trends 2025 - LinkedIn"

    # Platform
    assert properties['Platform']['select']['name'] == 'LinkedIn'

    # Content
    assert properties['Content']['rich_text'][0]['text']['content'] == \
           'This is a test post about PropTech trends.'

    # Character Count
    assert properties['Character Count']['number'] == 42

    # Media URL
    assert properties['Media URL']['url'] == 'https://replicate.delivery/test.png'

    # Hashtags (# prefix removed)
    assert properties['Hashtags']['multi_select'] == [
        {'name': 'PropTech'},
        {'name': 'Innovation'},
        {'name': 'RealEstate'}
    ]

    # Status
    assert properties['Status']['select']['name'] == 'Draft'

    # Blog Post relation
    assert properties['Blog Post']['relation'][0]['id'] == "blog_page_789"

    # Created date
    assert 'Created' in properties
    assert 'start' in properties['Created']['date']


def test_build_social_post_properties_minimal(social_posts_sync):
    """Test property mapping with minimal fields"""
    minimal_post = {
        'platform': 'Facebook',
        'content': 'Minimal post',
        'hashtags': [],
        'character_count': 12,
        'cost': 0.0008,
        'tokens': {'total': 100}
    }

    properties = social_posts_sync._build_social_post_properties(
        social_post=minimal_post,
        blog_title="Test Blog"
    )

    # Verify required fields only
    assert properties['Title']['title'][0]['text']['content'] == "Test Blog - Facebook"
    assert properties['Platform']['select']['name'] == 'Facebook'
    assert properties['Content']['rich_text'][0]['text']['content'] == 'Minimal post'
    assert properties['Character Count']['number'] == 12
    assert properties['Status']['select']['name'] == 'Draft'

    # Verify optional fields NOT included
    assert 'Media URL' not in properties
    assert 'Hashtags' not in properties  # Empty list
    assert 'Blog Post' not in properties


def test_build_social_post_properties_long_content(social_posts_sync):
    """Test property mapping truncates content >2000 chars"""
    long_content = "A" * 2500  # Exceeds Notion rich_text limit

    long_post = {
        'platform': 'Instagram',
        'content': long_content,
        'hashtags': [],
        'character_count': 2500,
        'cost': 0.0038,
        'tokens': {'total': 500}
    }

    properties = social_posts_sync._build_social_post_properties(
        social_post=long_post,
        blog_title="Test"
    )

    # Verify content truncated to 2000 chars
    assert len(properties['Content']['rich_text'][0]['text']['content']) == 2000


# ==================== Statistics Tests ====================

def test_get_statistics_initial(social_posts_sync):
    """Test statistics after initialization"""
    stats = social_posts_sync.get_statistics()

    assert stats['total_synced'] == 0
    assert stats['failed_syncs'] == 0
    assert stats['success_rate'] == 0.0


def test_get_statistics_after_syncs(social_posts_sync, sample_social_posts_batch, mock_notion_client):
    """Test statistics after successful syncs"""
    social_posts_sync.sync_social_posts_batch(
        social_posts=sample_social_posts_batch,
        blog_title="Test"
    )

    stats = social_posts_sync.get_statistics()

    assert stats['total_synced'] == 4
    assert stats['failed_syncs'] == 0
    assert stats['success_rate'] == 1.0


def test_get_statistics_after_partial_failure(
    social_posts_sync,
    sample_social_posts_batch,
    mock_notion_client
):
    """Test statistics after partial failure"""
    # Make 2nd post fail
    call_count = [0]

    def create_page_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise Exception("API error")
        return {'id': f'page_{call_count[0]}', 'url': ''}

    mock_notion_client.create_page.side_effect = create_page_side_effect

    social_posts_sync.sync_social_posts_batch(
        social_posts=sample_social_posts_batch,
        blog_title="Test",
        skip_errors=True
    )

    stats = social_posts_sync.get_statistics()

    assert stats['total_synced'] == 3
    assert stats['failed_syncs'] == 1
    assert stats['success_rate'] == 0.75  # 3/4


# ==================== Edge Cases ====================

def test_sync_post_with_unknown_platform(social_posts_sync, mock_notion_client):
    """Test sync with unknown platform (should still work)"""
    unknown_post = {
        'platform': 'UnknownPlatform',
        'content': 'Test',
        'hashtags': [],
        'character_count': 4,
        'cost': 0.0,
        'tokens': {'total': 50}
    }

    result = social_posts_sync.sync_social_post(
        social_post=unknown_post,
        blog_title="Test"
    )

    # Should succeed (Notion will create new select option)
    assert result['action'] == 'created'
    assert result['platform'] == 'UnknownPlatform'


def test_sync_post_missing_optional_fields(social_posts_sync, mock_notion_client):
    """Test sync with missing optional fields"""
    incomplete_post = {
        'platform': 'LinkedIn',
        'content': 'Test',
        'character_count': 4
        # Missing: hashtags, image, cost, tokens
    }

    result = social_posts_sync.sync_social_post(
        social_post=incomplete_post,
        blog_title="Test"
    )

    assert result['action'] == 'created'
