"""
E2E tests for RepurposingAgent with image generation

Tests the full social bundle generation pipeline:
- Text content generation for 4 platforms
- Smart image generation (OG reuse + AI images)
- Cost tracking (text + images)
- Cache integration

These tests use mocked image generation to avoid API calls.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from PIL import Image
import io

from src.agents.repurposing_agent import RepurposingAgent, RepurposingError
from src.media.platform_image_generator import PlatformImageGenerator


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_key():
    """OpenRouter API key for testing"""
    return "test-api-key-123"


@pytest.fixture
def sample_blog_post():
    """Sample blog post for testing"""
    return {
        "title": "Die Zukunft von PropTech: Innovative Technologien",
        "excerpt": "Revolutionäre Technologien verändern die Immobilienbranche grundlegend",
        "keywords": ["PropTech", "Innovation", "Digitalisierung", "Smart Buildings"],
        "slug": "proptech-zukunft-2025"
    }


@pytest.fixture
def mock_image_generator():
    """Mock ImageGenerator for Flux"""
    generator = Mock()

    # Mock async generate_supporting_image
    async def mock_generate(topic, brand_tone, aspect, aspect_ratio="1:1"):
        # Return AI image result
        return {
            "success": True,
            "url": f"https://replicate.delivery/test-{aspect_ratio.replace(':', 'x')}.png",
            "cost": 0.003,
            "model": "Flux Dev"
        }

    generator.generate_supporting_image = AsyncMock(side_effect=mock_generate)
    return generator


@pytest.fixture
def mock_og_generator():
    """Mock OGImageGenerator for Pillow"""
    generator = Mock()

    # Create a simple OG image
    img = Image.new('RGB', (1200, 630), color='blue')
    img_bytes_io = io.BytesIO()
    img.save(img_bytes_io, format='PNG')
    img_bytes = img_bytes_io.getvalue()

    generator.generate.return_value = img_bytes
    return generator


@pytest.fixture
def platform_image_generator(mock_image_generator, mock_og_generator):
    """PlatformImageGenerator with mocked dependencies"""
    return PlatformImageGenerator(
        image_generator=mock_image_generator,
        og_generator=mock_og_generator
    )


@pytest.fixture
def repurposing_agent_with_images(api_key, platform_image_generator, tmp_path):
    """RepurposingAgent with image generation enabled"""
    with patch('src.agents.repurposing_agent.RepurposingAgent._load_prompt_template'):
        agent = RepurposingAgent(
            api_key=api_key,
            cache_dir=str(tmp_path / "cache"),
            image_generator=platform_image_generator
        )
        agent.prompt_template = (
            "Generate a {platform} post about {topic}. "
            "Language: {language}. Keywords: {keywords}"
        )
        return agent


@pytest.fixture
def base_agent_response():
    """Standard text generation response"""
    return {
        'content': 'Test social media content for platform optimization',
        'tokens': {
            'prompt': 150,
            'completion': 100,
            'total': 250
        },
        'cost': 0.0008  # Cost per platform for text
    }


# ============================================================================
# E2E Tests: Full Social Bundles (Text + Images)
# ============================================================================


class TestFullSocialBundleGeneration:
    """E2E tests for complete social bundles with text and images"""

    @pytest.mark.asyncio
    async def test_generate_full_bundle_all_platforms(
        self,
        repurposing_agent_with_images,
        sample_blog_post,
        base_agent_response
    ):
        """Test generating complete social bundles for all 4 platforms"""
        with patch.object(
            repurposing_agent_with_images,
            'generate',
            return_value=base_agent_response
        ):
            results = await repurposing_agent_with_images.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
                brand_tone=["Professional"],
                language="de",
                generate_images=True,
                brand_color="#1a73e8"
            )

            # Verify all 4 platforms generated
            assert len(results) == 4
            platforms = [r['platform'] for r in results]
            assert set(platforms) == {"LinkedIn", "Facebook", "Instagram", "TikTok"}

            # Verify each platform has text content
            for result in results:
                assert 'content' in result
                assert 'hashtags' in result
                assert 'character_count' in result
                assert 'cost' in result
                assert len(result['content']) > 0

            # Verify image presence and providers
            linkedin = next(r for r in results if r['platform'] == "LinkedIn")
            facebook = next(r for r in results if r['platform'] == "Facebook")
            instagram = next(r for r in results if r['platform'] == "Instagram")
            tiktok = next(r for r in results if r['platform'] == "TikTok")

            # LinkedIn and Facebook should have OG images (Pillow, free)
            assert 'image' in linkedin
            assert linkedin['image']['provider'] == 'pillow'
            assert linkedin['image']['cost'] == 0.0
            assert linkedin['image']['url'].startswith('data:image/png;base64,')

            assert 'image' in facebook
            assert facebook['image']['provider'] == 'pillow'
            assert facebook['image']['cost'] == 0.0

            # Instagram and TikTok should have AI images (Flux Dev, $0.003)
            assert 'image' in instagram
            assert instagram['image']['provider'] == 'flux-dev'
            assert instagram['image']['cost'] == 0.003
            assert 'replicate.delivery' in instagram['image']['url']

            assert 'image' in tiktok
            assert tiktok['image']['provider'] == 'flux-dev'
            assert tiktok['image']['cost'] == 0.003
            assert 'replicate.delivery' in tiktok['image']['url']

    @pytest.mark.asyncio
    async def test_cost_calculation_with_images(
        self,
        repurposing_agent_with_images,
        sample_blog_post,
        base_agent_response
    ):
        """Test cost calculation includes both text and image costs"""
        with patch.object(
            repurposing_agent_with_images,
            'generate',
            return_value=base_agent_response
        ):
            results = await repurposing_agent_with_images.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"],
                generate_images=True
            )

            # Expected costs:
            # LinkedIn: $0.0008 (text) + $0 (OG image) = $0.0008
            # Facebook: $0.0008 (text) + $0 (OG image) = $0.0008
            # Instagram: $0.0008 (text) + $0.003 (AI image) = $0.0038
            # TikTok: $0.0008 (text) + $0.003 (AI image) = $0.0038
            # Total: $0.0008 * 2 + $0.0038 * 2 = $0.0092

            linkedin = next(r for r in results if r['platform'] == "LinkedIn")
            facebook = next(r for r in results if r['platform'] == "Facebook")
            instagram = next(r for r in results if r['platform'] == "Instagram")
            tiktok = next(r for r in results if r['platform'] == "TikTok")

            assert linkedin['cost'] == pytest.approx(0.0008, abs=0.0001)
            assert facebook['cost'] == pytest.approx(0.0008, abs=0.0001)
            assert instagram['cost'] == pytest.approx(0.0038, abs=0.0001)
            assert tiktok['cost'] == pytest.approx(0.0038, abs=0.0001)

            total_cost = sum(r['cost'] for r in results)
            assert total_cost == pytest.approx(0.0092, abs=0.0001)

    @pytest.mark.asyncio
    async def test_text_only_generation_without_images(
        self,
        repurposing_agent_with_images,
        sample_blog_post,
        base_agent_response
    ):
        """Test text-only generation when generate_images=False"""
        with patch.object(
            repurposing_agent_with_images,
            'generate',
            return_value=base_agent_response
        ):
            results = await repurposing_agent_with_images.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn", "Instagram"],
                generate_images=False  # Text only
            )

            # Verify no images generated
            for result in results:
                assert 'image' not in result
                assert result['cost'] == base_agent_response['cost']  # Only text cost

    @pytest.mark.asyncio
    async def test_image_generation_failure_doesnt_break_text(
        self,
        repurposing_agent_with_images,
        sample_blog_post,
        base_agent_response,
        mock_image_generator
    ):
        """Test that image generation failures don't prevent text generation"""
        # Mock image generator to raise exception
        async def raise_error(*args, **kwargs):
            raise Exception("AI image generation failed")

        mock_image_generator.generate_supporting_image.side_effect = raise_error

        with patch.object(
            repurposing_agent_with_images,
            'generate',
            return_value=base_agent_response
        ):
            results = await repurposing_agent_with_images.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["Instagram"],  # Uses AI images
                generate_images=True
            )

            # Should still generate text successfully
            assert len(results) == 1
            assert results[0]['content'] == base_agent_response['content']

            # Image should be present (OG fallback)
            assert 'image' in results[0]
            assert results[0]['image']['provider'] == 'pillow'  # Fallback to OG

    @pytest.mark.asyncio
    async def test_og_image_reuse_optimization(
        self,
        repurposing_agent_with_images,
        sample_blog_post,
        base_agent_response,
        mock_og_generator
    ):
        """Test that OG image is generated once and reused for LinkedIn/Facebook"""
        with patch.object(
            repurposing_agent_with_images,
            'generate',
            return_value=base_agent_response
        ):
            results = await repurposing_agent_with_images.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn", "Facebook"],  # Both use OG
                generate_images=True
            )

            # Verify both platforms got images
            assert all('image' in r for r in results)

            # OG generator should be called (possibly cached, but at least once)
            assert mock_og_generator.generate.called

            # Both should have same provider
            assert all(r['image']['provider'] == 'pillow' for r in results)

    @pytest.mark.asyncio
    async def test_multilingual_support_with_images(
        self,
        repurposing_agent_with_images,
        base_agent_response
    ):
        """Test multilingual generation with images"""
        english_blog = {
            "title": "The Future of PropTech Innovation",
            "excerpt": "Revolutionary technologies transforming real estate",
            "keywords": ["PropTech", "Innovation", "Technology"],
            "slug": "proptech-future"
        }

        with patch.object(
            repurposing_agent_with_images,
            'generate',
            return_value=base_agent_response
        ):
            results = await repurposing_agent_with_images.generate_social_posts(
                blog_post=english_blog,
                platforms=["LinkedIn", "Instagram"],
                language="en",  # English language
                generate_images=True
            )

            assert len(results) == 2
            # Images should be generated regardless of language
            assert all('image' in r for r in results)

    @pytest.mark.asyncio
    async def test_cache_integration_with_images(
        self,
        repurposing_agent_with_images,
        sample_blog_post,
        base_agent_response,
        tmp_path
    ):
        """Test that text posts are cached (images not cached in this version)"""
        with patch.object(
            repurposing_agent_with_images,
            'generate',
            return_value=base_agent_response
        ):
            results = await repurposing_agent_with_images.generate_social_posts(
                blog_post=sample_blog_post,
                platforms=["LinkedIn"],
                generate_images=True,
                save_to_cache=True
            )

            # Verify text was cached (check cache directory)
            cache_dir = tmp_path / "cache" / "social_posts"
            expected_file = cache_dir / f"{sample_blog_post['slug']}_linkedin.md"

            # Cache file should exist with text content
            assert expected_file.exists()
            content = expected_file.read_text()
            assert len(content) > 0
