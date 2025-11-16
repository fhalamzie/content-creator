"""
Unit tests for Platform Image Generator

Tests platform-specific image generation with smart OG reuse:
- LinkedIn/Facebook: Reuse OG image (Pillow, $0)
- Instagram: Generate 1:1 AI image (Flux Dev, $0.003)
- TikTok: Generate 9:16 AI image (Flux Dev, $0.003)

Features tested:
- Platform specifications (aspect ratio, size, provider)
- OG image generation and reuse
- AI image generation with fallback
- Cost tracking
- Batch generation
- Error handling
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from PIL import Image
import io
import base64

from src.media.platform_image_generator import (
    PlatformImageGenerator,
    should_use_og_image
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_og_generator():
    """Mock OGImageGenerator"""
    generator = Mock()

    # Create a simple 1200x630 PNG
    img = Image.new('RGB', (1200, 630), color='blue')
    img_bytes_io = io.BytesIO()
    img.save(img_bytes_io, format='PNG')
    img_bytes = img_bytes_io.getvalue()

    generator.generate.return_value = img_bytes
    return generator


@pytest.fixture
def mock_image_generator():
    """Mock ImageGenerator (Flux)"""
    generator = Mock()

    # Mock async generate_supporting_image
    async def mock_generate(topic, brand_tone, aspect, aspect_ratio="1:1"):
        return {
            "success": True,
            "url": "https://replicate.delivery/test-image.png",
            "cost": 0.003,
            "model": "Flux Dev"
        }

    generator.generate_supporting_image = AsyncMock(side_effect=mock_generate)
    return generator


@pytest.fixture
def platform_generator(mock_og_generator, mock_image_generator):
    """PlatformImageGenerator with mocked dependencies"""
    return PlatformImageGenerator(
        image_generator=mock_image_generator,
        og_generator=mock_og_generator
    )


@pytest.fixture
def platform_generator_no_flux(mock_og_generator):
    """PlatformImageGenerator without Flux (only OG)"""
    return PlatformImageGenerator(
        image_generator=None,
        og_generator=mock_og_generator
    )


# ============================================================================
# TestPlatformSpecs: Platform Configuration Tests
# ============================================================================


class TestPlatformSpecs:
    """Test platform specifications and configuration"""

    def test_linkedin_uses_og_image(self, platform_generator):
        """LinkedIn should use OG image (16:9, 1200x630)"""
        spec = platform_generator.PLATFORM_SPECS["LinkedIn"]

        assert spec["use_og"] is True
        assert spec["aspect_ratio"] == "16:9"
        assert spec["size"] == {"width": 1200, "height": 630}
        assert spec["provider"] == "pillow"

    def test_facebook_uses_og_image(self, platform_generator):
        """Facebook should use OG image (16:9, 1200x630)"""
        spec = platform_generator.PLATFORM_SPECS["Facebook"]

        assert spec["use_og"] is True
        assert spec["aspect_ratio"] == "16:9"
        assert spec["size"] == {"width": 1200, "height": 630}
        assert spec["provider"] == "pillow"

    def test_instagram_uses_ai_image(self, platform_generator):
        """Instagram should use AI image (1:1, 1080x1080)"""
        spec = platform_generator.PLATFORM_SPECS["Instagram"]

        assert spec["use_og"] is False
        assert spec["aspect_ratio"] == "1:1"
        assert spec["size"] == {"width": 1080, "height": 1080}
        assert spec["provider"] == "flux-dev"

    def test_tiktok_uses_ai_image(self, platform_generator):
        """TikTok should use AI image (9:16, 1080x1920)"""
        spec = platform_generator.PLATFORM_SPECS["TikTok"]

        assert spec["use_og"] is False
        assert spec["aspect_ratio"] == "9:16"
        assert spec["size"] == {"width": 1080, "height": 1920}
        assert spec["provider"] == "flux-dev"

    def test_should_use_og_image_helper(self):
        """Test should_use_og_image helper function"""
        assert should_use_og_image("LinkedIn") is True
        assert should_use_og_image("Facebook") is True
        assert should_use_og_image("Instagram") is False
        assert should_use_og_image("TikTok") is False
        assert should_use_og_image("Invalid") is False


# ============================================================================
# TestOGImageGeneration: Pillow-based Image Generation
# ============================================================================


class TestOGImageGeneration:
    """Test OG image generation for LinkedIn/Facebook"""

    @pytest.mark.asyncio
    async def test_linkedin_generates_og_image(self, platform_generator, mock_og_generator):
        """LinkedIn should generate OG image using Pillow"""
        result = await platform_generator.generate_platform_image(
            platform="LinkedIn",
            topic="PropTech Innovation",
            excerpt="Brief excerpt about PropTech",
            brand_color="#1a73e8"
        )

        # Verify OG generator was called
        mock_og_generator.generate.assert_called_once()
        call_kwargs = mock_og_generator.generate.call_args[1]
        assert call_kwargs["title"] == "PropTech Innovation"
        assert call_kwargs["excerpt"] == "Brief excerpt about PropTech"
        assert call_kwargs["brand_color"] == "#1a73e8"

        # Verify result structure
        assert result["success"] is True
        assert result["format"] == "png"
        assert result["size"] == {"width": 1200, "height": 630}
        assert result["cost"] == 0.0
        assert result["provider"] == "pillow"
        assert result["url"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_facebook_generates_og_image(self, platform_generator, mock_og_generator):
        """Facebook should generate OG image using Pillow"""
        result = await platform_generator.generate_platform_image(
            platform="Facebook",
            topic="Test Topic",
            excerpt="Test excerpt",
            brand_color="#000000"
        )

        # Verify OG generator was called
        assert mock_og_generator.generate.called

        # Verify result
        assert result["success"] is True
        assert result["cost"] == 0.0
        assert result["provider"] == "pillow"

    @pytest.mark.asyncio
    async def test_og_image_includes_bytes(self, platform_generator):
        """OG image result should include raw bytes for saving"""
        result = await platform_generator.generate_platform_image(
            platform="LinkedIn",
            topic="Test",
            excerpt="Test excerpt",
            brand_color="#1a73e8"
        )

        assert "bytes" in result
        assert isinstance(result["bytes"], bytes)
        assert len(result["bytes"]) > 0


# ============================================================================
# TestAIImageGeneration: Flux-based Image Generation
# ============================================================================


class TestAIImageGeneration:
    """Test AI image generation for Instagram/TikTok"""

    @pytest.mark.asyncio
    async def test_instagram_generates_ai_image(self, platform_generator, mock_image_generator):
        """Instagram should generate 1:1 AI image using Flux Dev"""
        result = await platform_generator.generate_platform_image(
            platform="Instagram",
            topic="PropTech Innovation",
            excerpt="Brief excerpt",
            brand_tone=["Professional"]
        )

        # Verify Flux was called with 1:1 aspect ratio
        mock_image_generator.generate_supporting_image.assert_called_once()
        call_kwargs = mock_image_generator.generate_supporting_image.call_args[1]
        assert call_kwargs["topic"] == "PropTech Innovation"
        assert call_kwargs["brand_tone"] == ["Professional"]
        assert call_kwargs["aspect_ratio"] == "1:1"

        # Verify result structure
        assert result["success"] is True
        assert result["url"] == "https://replicate.delivery/test-image.png"
        assert result["format"] == "png"
        assert result["size"] == {"width": 1080, "height": 1080}
        assert result["cost"] == 0.003
        assert result["provider"] == "flux-dev"

    @pytest.mark.asyncio
    async def test_tiktok_generates_ai_image(self, platform_generator, mock_image_generator):
        """TikTok should generate 9:16 AI image using Flux Dev"""
        result = await platform_generator.generate_platform_image(
            platform="TikTok",
            topic="PropTech Trends",
            excerpt="Brief excerpt",
            brand_tone=["Creative"]
        )

        # Verify Flux was called with 9:16 aspect ratio
        call_kwargs = mock_image_generator.generate_supporting_image.call_args[1]
        assert call_kwargs["aspect_ratio"] == "9:16"

        # Verify result structure
        assert result["success"] is True
        assert result["size"] == {"width": 1080, "height": 1920}
        assert result["cost"] == 0.003


# ============================================================================
# TestFallbackBehavior: OG Fallback When AI Fails
# ============================================================================


class TestFallbackBehavior:
    """Test fallback to OG image when AI generation fails"""

    @pytest.mark.asyncio
    async def test_fallback_when_no_flux(self, platform_generator_no_flux, mock_og_generator):
        """Should fallback to OG image when ImageGenerator is None"""
        result = await platform_generator_no_flux.generate_platform_image(
            platform="Instagram",
            topic="Test",
            excerpt="Test excerpt",
            brand_color="#1a73e8",
            use_og_fallback=True
        )

        # Should use OG generator as fallback
        assert mock_og_generator.generate.called
        assert result["success"] is True
        assert result["provider"] == "pillow"
        assert result["cost"] == 0.0

    @pytest.mark.asyncio
    async def test_no_fallback_when_disabled(self, platform_generator_no_flux):
        """Should fail when fallback disabled and Flux unavailable"""
        result = await platform_generator_no_flux.generate_platform_image(
            platform="Instagram",
            topic="Test",
            excerpt="Test excerpt",
            use_og_fallback=False
        )

        assert result["success"] is False
        assert result["cost"] == 0.0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_fallback_when_ai_generation_fails(self, mock_og_generator, mock_image_generator):
        """Should fallback to OG when AI generation returns None"""
        # Create new AsyncMock that returns None
        async def return_none(*args, **kwargs):
            return None

        mock_image_generator.generate_supporting_image = AsyncMock(side_effect=return_none)

        # Create platform generator with mocks
        platform_generator = PlatformImageGenerator(
            image_generator=mock_image_generator,
            og_generator=mock_og_generator
        )

        result = await platform_generator.generate_platform_image(
            platform="Instagram",
            topic="Test",
            excerpt="Test excerpt",
            brand_color="#1a73e8",
            use_og_fallback=True
        )

        # Should fallback to OG
        assert mock_og_generator.generate.called
        assert result["success"] is True
        assert result["provider"] == "pillow"

    @pytest.mark.asyncio
    async def test_fallback_when_ai_generation_throws(self, mock_og_generator, mock_image_generator):
        """Should fallback to OG when AI generation raises exception"""
        # Create new AsyncMock that raises exception
        async def raise_error(*args, **kwargs):
            raise Exception("API error")

        mock_image_generator.generate_supporting_image = AsyncMock(side_effect=raise_error)

        # Create platform generator with mocks
        platform_generator = PlatformImageGenerator(
            image_generator=mock_image_generator,
            og_generator=mock_og_generator
        )

        result = await platform_generator.generate_platform_image(
            platform="Instagram",
            topic="Test",
            excerpt="Test excerpt",
            brand_color="#1a73e8",
            use_og_fallback=True
        )

        # Should fallback to OG
        assert mock_og_generator.generate.called
        assert result["success"] is True
        assert result["provider"] == "pillow"


# ============================================================================
# TestCostTracking: Cost Calculation
# ============================================================================


class TestCostTracking:
    """Test cost tracking for different platforms"""

    @pytest.mark.asyncio
    async def test_og_image_cost_is_zero(self, platform_generator):
        """OG images (LinkedIn/Facebook) should cost $0"""
        result = await platform_generator.generate_platform_image(
            platform="LinkedIn",
            topic="Test",
            excerpt="Test excerpt",
            brand_color="#1a73e8"
        )

        assert result["cost"] == 0.0

    @pytest.mark.asyncio
    async def test_ai_image_cost_is_tracked(self, platform_generator):
        """AI images (Instagram/TikTok) should cost $0.003"""
        result = await platform_generator.generate_platform_image(
            platform="Instagram",
            topic="Test",
            excerpt="Test excerpt"
        )

        assert result["cost"] == 0.003

    @pytest.mark.asyncio
    async def test_batch_generation_total_cost(self, platform_generator):
        """Batch generation should calculate total cost correctly"""
        result = await platform_generator.generate_all_platform_images(
            topic="Test",
            excerpt="Test excerpt",
            brand_color="#1a73e8",
            platforms=["LinkedIn", "Facebook", "Instagram", "TikTok"]
        )

        # OG reused by LinkedIn/Facebook = $0
        # Instagram = $0.003
        # TikTok = $0.003
        # Total = $0.006
        assert result["total_cost"] == 0.006


# ============================================================================
# TestErrorHandling: Invalid Inputs and Edge Cases
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_invalid_platform_raises_error(self, platform_generator):
        """Invalid platform should raise ValueError"""
        with pytest.raises(ValueError, match="Platform 'InvalidPlatform' not supported"):
            await platform_generator.generate_platform_image(
                platform="InvalidPlatform",
                topic="Test",
                excerpt="Test excerpt"
            )

    @pytest.mark.asyncio
    async def test_og_generation_failure(self, mock_og_generator):
        """OG generation failure should return error result"""
        # Mock OG generator to raise exception
        mock_og_generator.generate.side_effect = Exception("Pillow error")

        # Create platform generator with failing OG mock
        platform_generator = PlatformImageGenerator(
            image_generator=None,
            og_generator=mock_og_generator
        )

        result = await platform_generator.generate_platform_image(
            platform="LinkedIn",
            topic="Test",
            excerpt="Test excerpt"
        )

        assert result["success"] is False
        assert result["cost"] == 0.0
        assert "error" in result


# ============================================================================
# TestBatchGeneration: Generate All Platform Images
# ============================================================================


class TestBatchGeneration:
    """Test batch generation for multiple platforms"""

    @pytest.mark.asyncio
    async def test_generate_all_platforms(self, platform_generator):
        """Should generate images for all 4 platforms"""
        result = await platform_generator.generate_all_platform_images(
            topic="Test Topic",
            excerpt="Test excerpt",
            brand_color="#1a73e8"
        )

        assert result["success"] is True
        assert len(result["images"]) == 4
        assert "LinkedIn" in result["images"]
        assert "Facebook" in result["images"]
        assert "Instagram" in result["images"]
        assert "TikTok" in result["images"]

    @pytest.mark.asyncio
    async def test_og_image_reused_across_platforms(self, platform_generator, mock_og_generator):
        """OG image should be generated once and reused by LinkedIn/Facebook"""
        result = await platform_generator.generate_all_platform_images(
            topic="Test",
            excerpt="Test excerpt",
            brand_color="#1a73e8",
            platforms=["LinkedIn", "Facebook", "Instagram"]
        )

        # OG generator should be called only once
        assert mock_og_generator.generate.call_count == 1

        # LinkedIn and Facebook should have same image
        assert result["images"]["LinkedIn"] == result["images"]["Facebook"]
        assert result["og_image_reused"] is True

    @pytest.mark.asyncio
    async def test_custom_platform_subset(self, platform_generator):
        """Should support generating for subset of platforms"""
        result = await platform_generator.generate_all_platform_images(
            topic="Test",
            excerpt="Test excerpt",
            platforms=["Instagram", "TikTok"]
        )

        assert len(result["images"]) == 2
        assert "Instagram" in result["images"]
        assert "TikTok" in result["images"]
        assert result["og_image_reused"] is False

    @pytest.mark.asyncio
    async def test_batch_cost_calculation(self, platform_generator):
        """Batch generation should sum costs correctly"""
        result = await platform_generator.generate_all_platform_images(
            topic="Test",
            excerpt="Test excerpt",
            platforms=["LinkedIn", "Instagram"]
        )

        # LinkedIn OG = $0
        # Instagram AI = $0.003
        assert result["total_cost"] == 0.003
