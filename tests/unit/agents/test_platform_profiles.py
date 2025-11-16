"""
Tests for platform_profiles module

Tests platform configuration management for social media content generation.
Validates platform-specific settings (character limits, tone, hashtags, etc.)
"""

import pytest
from src.agents.platform_profiles import (
    PlatformConfig,
    PLATFORM_PROFILES,
    VALID_PLATFORMS,
    get_platform_config
)


class TestPlatformConfigDataclass:
    """Test PlatformConfig dataclass structure and initialization"""

    def test_platform_config_creation(self):
        """Test creating a PlatformConfig instance with all fields"""
        config = PlatformConfig(
            name="TestPlatform",
            max_chars=1000,
            optimal_chars=500,
            tone="Test tone",
            hashtag_limit=5,
            emoji_usage="Moderate",
            cta_style="Test CTA",
            format="Test format"
        )
        assert config.name == "TestPlatform"
        assert config.max_chars == 1000
        assert config.optimal_chars == 500
        assert config.tone == "Test tone"
        assert config.hashtag_limit == 5
        assert config.emoji_usage == "Moderate"
        assert config.cta_style == "Test CTA"
        assert config.format == "Test format"

    def test_platform_config_has_required_fields(self):
        """Test that PlatformConfig has all required fields"""
        config = PlatformConfig(
            name="Test",
            max_chars=100,
            optimal_chars=50,
            tone="test",
            hashtag_limit=3,
            emoji_usage="low",
            cta_style="test",
            format="test"
        )
        # Verify all fields exist and are accessible
        assert hasattr(config, 'name')
        assert hasattr(config, 'max_chars')
        assert hasattr(config, 'optimal_chars')
        assert hasattr(config, 'tone')
        assert hasattr(config, 'hashtag_limit')
        assert hasattr(config, 'emoji_usage')
        assert hasattr(config, 'cta_style')
        assert hasattr(config, 'format')


class TestGetPlatformConfigValid:
    """Test retrieving valid platform configurations"""

    def test_get_linkedin_config(self):
        """Test retrieving LinkedIn platform configuration"""
        config = get_platform_config("LinkedIn")
        assert config.name == "LinkedIn"
        assert config.max_chars == 3000
        assert config.optimal_chars == 1300
        assert config.tone == "Professional, thought-leadership"
        assert config.hashtag_limit == 5
        assert config.emoji_usage == "Moderate (1-2 per post)"
        assert config.cta_style == "Ask questions, invite discussion"
        assert config.format == "Hook → Insights → CTA"

    def test_get_facebook_config(self):
        """Test retrieving Facebook platform configuration"""
        config = get_platform_config("Facebook")
        assert config.name == "Facebook"
        assert config.max_chars == 63206
        assert config.optimal_chars == 250
        assert config.tone == "Conversational, community-focused"
        assert config.hashtag_limit == 3
        assert config.emoji_usage == "High (3-5 per post)"
        assert config.cta_style == "Ask for shares, reactions"
        assert config.format == "Story → Value → Emotion"

    def test_get_instagram_config(self):
        """Test retrieving Instagram platform configuration"""
        config = get_platform_config("Instagram")
        assert config.name == "Instagram"
        assert config.max_chars == 2200
        assert config.optimal_chars == 150
        assert config.tone == "Visual storytelling, authentic"
        assert config.hashtag_limit == 30
        assert config.emoji_usage == "Very High (5-10)"
        assert config.cta_style == "Link in bio, save for later"
        assert config.format == "Hook → Visual description → Hashtags"

    def test_get_tiktok_config(self):
        """Test retrieving TikTok platform configuration"""
        config = get_platform_config("TikTok")
        assert config.name == "TikTok"
        assert config.max_chars == 2200
        assert config.optimal_chars == 100
        assert config.tone == "Casual, entertaining, trend-aware"
        assert config.hashtag_limit == 5
        assert config.emoji_usage == "High (3-5)"
        assert config.cta_style == "Watch till end, follow for more"
        assert config.format == "Hook → Quick tips → Trending audio"


class TestGetPlatformConfigInvalid:
    """Test error handling for invalid platforms"""

    def test_invalid_platform_raises_value_error(self):
        """Test that unknown platform raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            get_platform_config("InvalidPlatform")
        assert "InvalidPlatform" in str(exc_info.value)

    def test_case_sensitive_platform_lookup(self):
        """Test that platform lookup is case-sensitive"""
        with pytest.raises(ValueError):
            get_platform_config("linkedin")  # lowercase should fail
        with pytest.raises(ValueError):
            get_platform_config("FACEBOOK")  # uppercase should fail

    def test_empty_string_platform_raises_error(self):
        """Test that empty string raises ValueError"""
        with pytest.raises(ValueError):
            get_platform_config("")


class TestPlatformLimits:
    """Test character limit specifications for all platforms"""

    def test_linkedin_character_limits(self):
        """Test LinkedIn character limits are correct"""
        config = PLATFORM_PROFILES["LinkedIn"]
        assert config.max_chars == 3000
        assert config.optimal_chars == 1300
        assert config.optimal_chars < config.max_chars

    def test_facebook_character_limits(self):
        """Test Facebook character limits are correct"""
        config = PLATFORM_PROFILES["Facebook"]
        assert config.max_chars == 63206
        assert config.optimal_chars == 250
        assert config.optimal_chars < config.max_chars

    def test_instagram_character_limits(self):
        """Test Instagram character limits are correct"""
        config = PLATFORM_PROFILES["Instagram"]
        assert config.max_chars == 2200
        assert config.optimal_chars == 150
        assert config.optimal_chars < config.max_chars

    def test_tiktok_character_limits(self):
        """Test TikTok character limits are correct"""
        config = PLATFORM_PROFILES["TikTok"]
        assert config.max_chars == 2200
        assert config.optimal_chars == 100
        assert config.optimal_chars < config.max_chars

    def test_optimal_chars_less_than_max_chars_all_platforms(self):
        """Test that optimal_chars < max_chars for all platforms"""
        for platform_name, config in PLATFORM_PROFILES.items():
            assert config.optimal_chars < config.max_chars, \
                f"Platform {platform_name}: optimal_chars ({config.optimal_chars}) >= max_chars ({config.max_chars})"


class TestValidPlatformsConstant:
    """Test VALID_PLATFORMS constant contains all platforms"""

    def test_valid_platforms_contains_all_four_platforms(self):
        """Test VALID_PLATFORMS list has exactly 4 platforms"""
        assert len(VALID_PLATFORMS) == 4
        assert "LinkedIn" in VALID_PLATFORMS
        assert "Facebook" in VALID_PLATFORMS
        assert "Instagram" in VALID_PLATFORMS
        assert "TikTok" in VALID_PLATFORMS

    def test_platform_profiles_matches_valid_platforms(self):
        """Test that PLATFORM_PROFILES keys match VALID_PLATFORMS"""
        assert set(PLATFORM_PROFILES.keys()) == set(VALID_PLATFORMS)

    def test_get_platform_config_works_for_all_valid_platforms(self):
        """Test get_platform_config works for each valid platform"""
        for platform in VALID_PLATFORMS:
            config = get_platform_config(platform)
            assert config is not None
            assert config.name == platform

    def test_all_platforms_have_configs(self):
        """Test all valid platforms have corresponding configs in PLATFORM_PROFILES"""
        for platform in VALID_PLATFORMS:
            assert platform in PLATFORM_PROFILES
            assert isinstance(PLATFORM_PROFILES[platform], PlatformConfig)
