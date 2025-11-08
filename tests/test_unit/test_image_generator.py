"""
Unit tests for ImageGenerator

Tests 7-tone prompt mapping, DALL-E 3 integration, retry logic, and cost tracking.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.media.image_generator import ImageGenerator, ImageGenerationError


class TestImageGeneratorInitialization:
    """Test ImageGenerator initialization"""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key"""
        generator = ImageGenerator(api_key="test_key")
        assert generator.api_key == "test_key"

    def test_init_loads_api_key_from_env(self):
        """Test initialization loads API key from /home/envs/openai.env"""
        with patch("os.getenv", return_value=None):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.readlines.return_value = [
                        "OPENAI_API_KEY=env_key\n"
                    ]
                    # Mock to return lines iterator
                    mock_open.return_value.__enter__.return_value.__iter__ = lambda self: iter([
                        "OPENAI_API_KEY=env_key\n"
                    ])
                    generator = ImageGenerator()
                    assert generator.api_key == "env_key"

    def test_init_raises_without_api_key(self):
        """Test initialization raises error without API key"""
        with patch("os.getenv", return_value=None):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(ValueError, match="OPENAI_API_KEY not found"):
                    ImageGenerator()


class TestTonePromptMapping:
    """Test 7-tone prompt mapping"""

    @pytest.fixture
    def generator(self):
        return ImageGenerator(api_key="test_key")

    def test_professional_tone_mapping(self, generator):
        """Test Professional tone generates corporate prompt"""
        prompt = generator._map_tone_to_prompt(
            ["Professional"],
            "PropTech AI trends",
            is_hero=True
        )
        assert "professional" in prompt.lower()
        assert "corporate" in prompt.lower() or "business" in prompt.lower()

    def test_technical_tone_mapping(self, generator):
        """Test Technical tone generates technical/diagram prompt"""
        prompt = generator._map_tone_to_prompt(
            ["Technical"],
            "API architecture",
            is_hero=False
        )
        assert "technical" in prompt.lower() or "diagram" in prompt.lower()

    def test_creative_tone_mapping(self, generator):
        """Test Creative tone generates artistic prompt"""
        prompt = generator._map_tone_to_prompt(
            ["Creative"],
            "Design thinking",
            is_hero=True
        )
        assert "creative" in prompt.lower() or "artistic" in prompt.lower()

    def test_casual_tone_mapping(self, generator):
        """Test Casual tone generates friendly prompt"""
        prompt = generator._map_tone_to_prompt(
            ["Casual"],
            "Startup tips",
            is_hero=False
        )
        assert "casual" in prompt.lower() or "friendly" in prompt.lower()

    def test_authoritative_tone_mapping(self, generator):
        """Test Authoritative tone generates expert prompt"""
        prompt = generator._map_tone_to_prompt(
            ["Authoritative"],
            "Industry analysis",
            is_hero=True
        )
        assert "authoritative" in prompt.lower() or "expert" in prompt.lower()

    def test_innovative_tone_mapping(self, generator):
        """Test Innovative tone generates futuristic prompt"""
        prompt = generator._map_tone_to_prompt(
            ["Innovative"],
            "Future tech",
            is_hero=False
        )
        assert "innovative" in prompt.lower() or "futuristic" in prompt.lower()

    def test_friendly_tone_mapping(self, generator):
        """Test Friendly tone generates approachable prompt"""
        prompt = generator._map_tone_to_prompt(
            ["Friendly"],
            "Getting started guide",
            is_hero=True
        )
        assert "friendly" in prompt.lower() or "approachable" in prompt.lower()

    def test_multiple_tones_mapping(self, generator):
        """Test multiple tones are combined in prompt"""
        prompt = generator._map_tone_to_prompt(
            ["Professional", "Technical"],
            "Enterprise software",
            is_hero=True
        )
        assert "professional" in prompt.lower() or "technical" in prompt.lower()

    def test_unknown_tone_defaults_to_professional(self, generator):
        """Test unknown tone defaults to Professional"""
        prompt = generator._map_tone_to_prompt(
            ["UnknownTone"],
            "Some topic",
            is_hero=True
        )
        assert "professional" in prompt.lower()

    def test_empty_tone_list_defaults_to_professional(self, generator):
        """Test empty tone list defaults to Professional"""
        prompt = generator._map_tone_to_prompt(
            [],
            "Some topic",
            is_hero=False
        )
        assert "professional" in prompt.lower()


class TestHeroImageGeneration:
    """Test hero image generation (1792x1024 HD)"""

    @pytest.fixture
    def generator(self):
        return ImageGenerator(api_key="test_key")

    @pytest.mark.asyncio
    async def test_generate_hero_image_success(self, generator):
        """Test successful hero image generation"""
        mock_response = Mock()
        mock_response.data = [Mock(url="https://example.com/image.png")]

        # Create async mock
        async_mock = AsyncMock(return_value=mock_response)
        with patch.object(generator.client.images, "generate", async_mock):
            result = await generator.generate_hero_image(
                topic="PropTech trends",
                brand_tone=["Professional"]
            )

        assert result["url"] == "https://example.com/image.png"
        assert result["size"] == "1792x1024"
        assert result["quality"] == "hd"
        assert result["cost"] == 0.08

    @pytest.mark.asyncio
    async def test_generate_hero_image_calls_dalle3_with_correct_params(self, generator):
        """Test hero image calls DALL-E 3 with correct parameters"""
        mock_response = Mock()
        mock_response.data = [Mock(url="https://example.com/image.png")]

        # Create async mock
        async_mock = AsyncMock(return_value=mock_response)
        with patch.object(generator.client.images, "generate", async_mock) as mock_gen:
            await generator.generate_hero_image(
                topic="Test topic",
                brand_tone=["Technical"]
            )

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["model"] == "dall-e-3"
        assert call_kwargs["size"] == "1792x1024"
        assert call_kwargs["quality"] == "hd"
        assert call_kwargs["n"] == 1


class TestSupportingImageGeneration:
    """Test supporting image generation (1024x1024 standard)"""

    @pytest.fixture
    def generator(self):
        return ImageGenerator(api_key="test_key")

    @pytest.mark.asyncio
    async def test_generate_supporting_image_success(self, generator):
        """Test successful supporting image generation"""
        mock_response = Mock()
        mock_response.data = [Mock(url="https://example.com/support.png")]

        # Create async mock
        async_mock = AsyncMock(return_value=mock_response)
        with patch.object(generator.client.images, "generate", async_mock):
            result = await generator.generate_supporting_image(
                topic="API design",
                brand_tone=["Creative"],
                aspect="implementation"
            )

        assert result["url"] == "https://example.com/support.png"
        assert result["size"] == "1024x1024"
        assert result["quality"] == "standard"
        assert result["cost"] == 0.04

    @pytest.mark.asyncio
    async def test_generate_supporting_image_calls_dalle3_with_correct_params(self, generator):
        """Test supporting image calls DALL-E 3 with correct parameters"""
        mock_response = Mock()
        mock_response.data = [Mock(url="https://example.com/support.png")]

        # Create async mock
        async_mock = AsyncMock(return_value=mock_response)
        with patch.object(generator.client.images, "generate", async_mock) as mock_gen:
            await generator.generate_supporting_image(
                topic="Test topic",
                brand_tone=["Casual"],
                aspect="benefits"
            )

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["model"] == "dall-e-3"
        assert call_kwargs["size"] == "1024x1024"
        assert call_kwargs["quality"] == "standard"
        assert call_kwargs["n"] == 1


class TestErrorHandlingAndRetry:
    """Test silent failure and retry logic"""

    @pytest.fixture
    def generator(self):
        return ImageGenerator(api_key="test_key")

    @pytest.mark.asyncio
    async def test_retry_on_api_error(self, generator):
        """Test retry logic on API error (3 attempts)"""
        mock_response = Mock()
        mock_response.data = [Mock(url="https://example.com/success.png")]

        # Create async mock with side effects
        async_mock = AsyncMock()
        async_mock.side_effect = [
            Exception("Rate limit"),
            Exception("Timeout"),
            mock_response
        ]

        with patch.object(generator.client.images, "generate", async_mock):
            result = await generator.generate_hero_image(
                topic="Test",
                brand_tone=["Professional"]
            )

        assert result["url"] == "https://example.com/success.png"
        assert async_mock.call_count == 3

    @pytest.mark.asyncio
    async def test_silent_failure_returns_none_after_3_retries(self, generator):
        """Test returns None after 3 failed retries"""
        with patch.object(generator.client.images, "generate") as mock_gen:
            mock_gen.side_effect = Exception("API Error")

            result = await generator.generate_hero_image(
                topic="Test",
                brand_tone=["Professional"]
            )

        assert result is None
        assert mock_gen.call_count == 3

    @pytest.mark.asyncio
    async def test_silent_failure_logs_error(self, generator):
        """Test error is logged on failure"""
        with patch.object(generator.client.images, "generate", side_effect=Exception("API Error")):
            with patch("src.media.image_generator.logger") as mock_logger:
                result = await generator.generate_hero_image(
                    topic="Test",
                    brand_tone=["Professional"]
                )

                assert result is None
                # Check error was logged
                assert any(
                    "image_generation_failed" in str(call)
                    for call in mock_logger.error.call_args_list
                )


class TestCostTracking:
    """Test cost tracking integration"""

    @pytest.fixture
    def generator(self):
        return ImageGenerator(api_key="test_key")

    @pytest.mark.asyncio
    async def test_hero_image_cost_tracked(self, generator):
        """Test hero image cost is $0.08"""
        mock_response = Mock()
        mock_response.data = [Mock(url="https://example.com/hero.png")]

        # Create async mock
        async_mock = AsyncMock(return_value=mock_response)
        with patch.object(generator.client.images, "generate", async_mock):
            result = await generator.generate_hero_image(
                topic="Test",
                brand_tone=["Professional"]
            )

        assert result["cost"] == 0.08

    @pytest.mark.asyncio
    async def test_supporting_image_cost_tracked(self, generator):
        """Test supporting image cost is $0.04"""
        mock_response = Mock()
        mock_response.data = [Mock(url="https://example.com/support.png")]

        # Create async mock
        async_mock = AsyncMock(return_value=mock_response)
        with patch.object(generator.client.images, "generate", async_mock):
            result = await generator.generate_supporting_image(
                topic="Test",
                brand_tone=["Technical"],
                aspect="overview"
            )

        assert result["cost"] == 0.04

    @pytest.mark.asyncio
    async def test_failed_image_generation_has_zero_cost(self, generator):
        """Test failed generation returns None (no cost)"""
        with patch.object(generator.client.images, "generate", side_effect=Exception("Error")):
            result = await generator.generate_hero_image(
                topic="Test",
                brand_tone=["Professional"]
            )

        assert result is None  # No cost when generation fails
