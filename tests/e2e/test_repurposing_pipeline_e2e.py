"""
E2E Tests for Full Repurposing Pipeline

Tests the complete flow:
1. Blog post generation (WritingAgent)
2. Social posts generation (RepurposingAgent)
3. Notion sync (SocialPostsSync)
4. Cost tracking
5. Error handling

These are integration tests that use mocked APIs but real object composition.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from src.agents.writing_agent import WritingAgent
from src.agents.repurposing_agent import RepurposingAgent
from src.media.platform_image_generator import PlatformImageGenerator
from src.notion_integration.social_posts_sync import SocialPostsSync


# ==================== Fixtures ====================

@pytest.fixture
def mock_openrouter_api():
    """Mock OpenRouter API responses"""
    with patch('src.agents.base_agent.OpenAI') as mock:
        client = Mock()

        # Mock blog writing response
        blog_response = Mock()
        blog_response.choices = [Mock(message=Mock(content="# Test Blog Post\n\nThis is a test blog post about PropTech trends."))]
        blog_response.usage = Mock(prompt_tokens=100, completion_tokens=200, total_tokens=300)
        blog_response.model = "qwen/qwq-32b-preview"

        # Mock social post responses
        social_responses = [
            "LinkedIn post content about PropTech trends. #PropTech #Innovation",
            "Facebook post content about PropTech. #PropTech",
            "Instagram post about PropTech trends! #PropTech #Innovation #Tech",
            "TikTok post about PropTech! #PropTech #Innovation"
        ]

        social_mocks = []
        for content in social_responses:
            response = Mock()
            response.choices = [Mock(message=Mock(content=content))]
            response.usage = Mock(prompt_tokens=50, completion_tokens=100, total_tokens=150)
            response.model = "qwen/qwq-32b-preview"
            social_mocks.append(response)

        # Set up side effects for multiple calls
        client.chat.completions.create.side_effect = [blog_response] + social_mocks

        mock.return_value = client
        yield client


@pytest.fixture
def mock_image_generator():
    """Mock PlatformImageGenerator"""
    with patch('src.media.platform_image_generator.PlatformImageGenerator') as mock:
        generator = AsyncMock()

        # Mock OG image generation (for LinkedIn/Facebook)
        og_result = {
            "success": True,
            "url": "data:image/png;base64,fake_og_image",
            "provider": "pillow",
            "cost": 0.0,
            "size": {"width": 1200, "height": 630}
        }

        # Mock AI image generation (for Instagram/TikTok)
        ai_result = {
            "success": True,
            "url": "https://replicate.delivery/fake_ai_image.png",
            "provider": "flux-dev",
            "cost": 0.003,
            "size": {"width": 1080, "height": 1080}
        }

        async def generate_platform_image_side_effect(platform, **kwargs):
            if platform in ["LinkedIn", "Facebook"]:
                return og_result
            else:  # Instagram, TikTok
                return ai_result

        generator.generate_platform_image = AsyncMock(side_effect=generate_platform_image_side_effect)

        mock.return_value = generator
        yield generator


@pytest.fixture
def mock_notion_client():
    """Mock NotionClient for social posts sync"""
    with patch('src.notion_integration.social_posts_sync.NotionClient') as mock:
        client = Mock()
        client.create_page.return_value = {
            'id': 'social_page_123',
            'url': 'https://notion.so/social_page_123'
        }
        mock.return_value = client
        yield client


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "social_posts").mkdir()
    return str(cache_dir)


# ==================== E2E Tests ====================

@pytest.mark.asyncio
async def test_full_pipeline_blog_to_social_posts_text_only(
    mock_openrouter_api,
    temp_cache_dir
):
    """Test full pipeline: blog → social posts (text only, no images)"""
    # Stage 1: Generate blog post
    writing_agent = WritingAgent(
        api_key="test_key",
        language="de",
        cache_dir=temp_cache_dir
    )

    blog_result = writing_agent.write_blog(
        topic="PropTech Trends 2025",
        research_data={"summary": "Test research"},
        brand_voice="Professional",
        target_audience="German professionals",
        primary_keyword="PropTech",
        save_to_cache=False
    )

    # WritingAgent returns {'content', 'cost', 'metadata', 'tokens'}
    assert 'content' in blog_result
    blog_cost = blog_result['cost']

    # Stage 2: Generate social posts (text only)
    repurposing_agent = RepurposingAgent(
        api_key="test_key",
        cache_dir=temp_cache_dir
    )

    blog_post_data = {
        'title': "PropTech Trends 2025",
        'excerpt': blog_result['content'][:200],
        'keywords': ["PropTech", "Innovation"],
        'slug': "proptech-trends-2025"
    }

    social_posts = await repurposing_agent.generate_social_posts(
        blog_post=blog_post_data,
        platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
        brand_tone=["Professional"],
        language="de",
        save_to_cache=False,
        generate_images=False  # Text only
    )

    # Verify results
    assert len(social_posts) == 4
    platforms = [p['platform'] for p in social_posts]
    assert set(platforms) == {"LinkedIn", "Facebook", "Instagram", "TikTok"}

    # Verify each post has required fields
    for post in social_posts:
        assert 'platform' in post
        assert 'content' in post
        assert 'hashtags' in post
        assert 'character_count' in post
        assert 'cost' in post
        assert 'tokens' in post
        assert 'image' not in post  # No images generated

    # Verify cost tracking
    total_social_cost = sum(p['cost'] for p in social_posts)
    total_cost = blog_cost + total_social_cost

    assert total_social_cost < 0.005  # Should be ~$0.003 for 4 text posts
    assert total_cost < 0.015  # Blog + social posts


@pytest.mark.asyncio
async def test_full_pipeline_with_images(
    mock_openrouter_api,
    mock_image_generator,
    temp_cache_dir
):
    """Test full pipeline: blog → social posts with images"""
    # Stage 1: Generate blog post
    writing_agent = WritingAgent(
        api_key="test_key",
        language="de",
        cache_dir=temp_cache_dir
    )

    blog_result = writing_agent.write_blog(
        topic="PropTech Trends 2025",
        research_data={"summary": "Test research"},
        brand_voice="Professional",
        target_audience="German professionals",
        primary_keyword="PropTech",
        save_to_cache=False
    )

    # Stage 2: Generate social posts with images
    repurposing_agent = RepurposingAgent(
        api_key="test_key",
        cache_dir=temp_cache_dir,
        image_generator=mock_image_generator
    )

    blog_post_data = {
        'title': "PropTech Trends 2025",
        'excerpt': blog_result['content'][:200],
        'keywords': ["PropTech", "Innovation"],
        'slug': "proptech-trends-2025"
    }

    social_posts = await repurposing_agent.generate_social_posts(
        blog_post=blog_post_data,
        platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
        brand_tone=["Professional"],
        language="de",
        save_to_cache=False,
        generate_images=True,
        brand_color="#1a73e8"
    )

    # Verify results
    assert len(social_posts) == 4

    # Verify LinkedIn and Facebook use OG images (FREE)
    linkedin_post = next(p for p in social_posts if p['platform'] == 'LinkedIn')
    assert 'image' in linkedin_post
    assert linkedin_post['image']['provider'] == 'pillow'
    assert linkedin_post['image']['cost'] == 0.0

    facebook_post = next(p for p in social_posts if p['platform'] == 'Facebook')
    assert 'image' in facebook_post
    assert facebook_post['image']['provider'] == 'pillow'
    assert facebook_post['image']['cost'] == 0.0

    # Verify Instagram and TikTok use AI images ($0.003 each)
    instagram_post = next(p for p in social_posts if p['platform'] == 'Instagram')
    assert 'image' in instagram_post
    assert instagram_post['image']['provider'] == 'flux-dev'
    assert instagram_post['image']['cost'] == 0.003

    tiktok_post = next(p for p in social_posts if p['platform'] == 'TikTok')
    assert 'image' in tiktok_post
    assert tiktok_post['image']['provider'] == 'flux-dev'
    assert tiktok_post['image']['cost'] == 0.003

    # Verify cost tracking (text + images)
    total_cost = sum(p['cost'] for p in social_posts)
    # Expected: LinkedIn/Facebook ~$0.00015 each (text only), Instagram/TikTok ~$0.00315 each (text + $0.003 image)
    # Total: ~$0.00066 (4 text posts) + $0.006 (2 AI images) = ~$0.00666
    assert total_cost > 0.006  # At least $0.006 for images
    assert total_cost < 0.008  # Less than $0.008 total


@pytest.mark.asyncio
async def test_full_pipeline_with_notion_sync(
    mock_openrouter_api,
    mock_image_generator,
    mock_notion_client,
    temp_cache_dir
):
    """Test full pipeline: blog → social posts → Notion sync"""
    # Stage 1: Generate blog post
    writing_agent = WritingAgent(
        api_key="test_key",
        language="de",
        cache_dir=temp_cache_dir
    )

    blog_result = writing_agent.write_blog(
        topic="PropTech Trends 2025",
        research_data={"summary": "Test research"},
        brand_voice="Professional",
        target_audience="German professionals",
        primary_keyword="PropTech",
        save_to_cache=False
    )

    # Stage 2: Generate social posts
    repurposing_agent = RepurposingAgent(
        api_key="test_key",
        cache_dir=temp_cache_dir,
        image_generator=mock_image_generator
    )

    blog_post_data = {
        'title': "PropTech Trends 2025",
        'excerpt': blog_result['content'][:200],
        'keywords': ["PropTech", "Innovation"],
        'slug': "proptech-trends-2025"
    }

    social_posts = await repurposing_agent.generate_social_posts(
        blog_post=blog_post_data,
        platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
        brand_tone=["Professional"],
        language="de",
        save_to_cache=False,
        generate_images=True
    )

    # Stage 3: Sync to Notion
    social_sync = SocialPostsSync(
        notion_token="test_token",
        social_posts_db_id="social_db_123",
        blog_posts_db_id="blog_db_456"
    )

    sync_result = social_sync.sync_social_posts_batch(
        social_posts=social_posts,
        blog_title="PropTech Trends 2025",
        blog_post_id="blog_page_789",
        skip_errors=False
    )

    # Verify sync results
    assert sync_result['total'] == 4
    assert sync_result['by_platform'] == {
        'LinkedIn': 1,
        'Facebook': 1,
        'Instagram': 1,
        'TikTok': 1
    }
    assert sync_result['failed'] == 0

    # Verify NotionClient was called 4 times
    assert mock_notion_client.create_page.call_count == 4

    # Verify statistics
    stats = social_sync.get_statistics()
    assert stats['total_synced'] == 4
    assert stats['failed_syncs'] == 0
    assert stats['success_rate'] == 1.0


@pytest.mark.asyncio
async def test_pipeline_partial_social_post_failure(
    mock_openrouter_api,
    temp_cache_dir
):
    """Test pipeline handles partial social post generation failure"""
    # Mock API failure for Instagram post (3rd call)
    call_count = [0]
    original_create = mock_openrouter_api.chat.completions.create

    def create_with_failure(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 4:  # Instagram (3rd social post, 4th total call)
            raise Exception("API timeout")
        return original_create.func(*args, **kwargs)

    mock_openrouter_api.chat.completions.create = create_with_failure

    # Generate social posts
    repurposing_agent = RepurposingAgent(
        api_key="test_key",
        cache_dir=temp_cache_dir
    )

    blog_post_data = {
        'title': "Test Blog",
        'excerpt': "Test excerpt",
        'keywords': ["Test"],
        'slug': "test-blog"
    }

    # Should raise error because Instagram failed
    with pytest.raises(Exception):
        await repurposing_agent.generate_social_posts(
            blog_post=blog_post_data,
            platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
            brand_tone=["Professional"],
            language="de",
            save_to_cache=False,
            generate_images=False
        )


@pytest.mark.asyncio
async def test_pipeline_multilingual_support(
    mock_openrouter_api,
    temp_cache_dir
):
    """Test pipeline supports multiple languages"""
    repurposing_agent = RepurposingAgent(
        api_key="test_key",
        cache_dir=temp_cache_dir
    )

    blog_post_data = {
        'title': "PropTech Trends 2025",
        'excerpt': "Test excerpt",
        'keywords': ["PropTech"],
        'slug': "proptech-trends"
    }

    # Test German
    social_posts_de = await repurposing_agent.generate_social_posts(
        blog_post=blog_post_data,
        platforms=["LinkedIn"],
        brand_tone=["Professional"],
        language="de",  # German
        save_to_cache=False,
        generate_images=False
    )

    assert len(social_posts_de) == 1
    assert social_posts_de[0]['platform'] == 'LinkedIn'

    # Test English
    social_posts_en = await repurposing_agent.generate_social_posts(
        blog_post=blog_post_data,
        platforms=["LinkedIn"],
        brand_tone=["Professional"],
        language="en",  # English
        save_to_cache=False,
        generate_images=False
    )

    assert len(social_posts_en) == 1
    assert social_posts_en[0]['platform'] == 'LinkedIn'


@pytest.mark.asyncio
async def test_pipeline_cost_breakdown(
    mock_openrouter_api,
    mock_image_generator,
    temp_cache_dir
):
    """Test accurate cost tracking across full pipeline"""
    # Generate social posts with images
    repurposing_agent = RepurposingAgent(
        api_key="test_key",
        cache_dir=temp_cache_dir,
        image_generator=mock_image_generator
    )

    blog_post_data = {
        'title': "Test Blog",
        'excerpt': "Test excerpt",
        'keywords': ["Test"],
        'slug': "test"
    }

    social_posts = await repurposing_agent.generate_social_posts(
        blog_post=blog_post_data,
        platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
        brand_tone=["Professional"],
        language="de",
        save_to_cache=False,
        generate_images=True
    )

    # Calculate costs
    image_cost = sum(p['image']['cost'] for p in social_posts if 'image' in p)
    total_cost = sum(p['cost'] for p in social_posts)

    # Verify cost breakdown
    assert image_cost == 0.006  # 2 AI images (Instagram + TikTok)
    assert total_cost > 0.006  # At least $0.006 for images
    assert total_cost < 0.010  # Less than $0.010 total (text + images)


# ==================== Error Handling Tests ====================

@pytest.mark.asyncio
async def test_pipeline_handles_missing_blog_data(temp_cache_dir):
    """Test pipeline handles missing required blog post data"""
    repurposing_agent = RepurposingAgent(
        api_key="test_key",
        cache_dir=temp_cache_dir
    )

    # Missing required keys
    incomplete_blog = {
        'title': "Test"
        # Missing: excerpt, keywords, slug
    }

    with pytest.raises(ValueError, match="blog_post missing required keys"):
        await repurposing_agent.generate_social_posts(
            blog_post=incomplete_blog,
            platforms=["LinkedIn"],
            brand_tone=["Professional"],
            language="de",
            save_to_cache=False,
            generate_images=False
        )


@pytest.mark.asyncio
async def test_pipeline_handles_invalid_platform(temp_cache_dir):
    """Test pipeline rejects invalid platform names"""
    repurposing_agent = RepurposingAgent(
        api_key="test_key",
        cache_dir=temp_cache_dir
    )

    blog_post_data = {
        'title': "Test",
        'excerpt': "Test",
        'keywords': ["Test"],
        'slug': "test"
    }

    with pytest.raises(ValueError, match="Invalid platforms"):
        await repurposing_agent.generate_social_posts(
            blog_post=blog_post_data,
            platforms=["LinkedIn", "InvalidPlatform"],  # Invalid platform
            brand_tone=["Professional"],
            language="de",
            save_to_cache=False,
            generate_images=False
        )
