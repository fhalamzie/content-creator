"""
Platform-specific configurations for social media content generation

This module provides platform configuration profiles for generating optimized social media content
across different platforms (LinkedIn, Facebook, Instagram, TikTok). Each platform has distinct
character limits, tone preferences, hashtag strategies, emoji usage guidelines, and content formats.

Usage:
    # Get a specific platform configuration
    linkedin_config = get_platform_config("LinkedIn")
    print(f"Max characters: {linkedin_config.max_chars}")
    print(f"Optimal characters: {linkedin_config.optimal_chars}")
    print(f"Tone: {linkedin_config.tone}")

    # Access all platforms
    for platform_name, config in PLATFORM_PROFILES.items():
        print(f"{platform_name}: {config.hashtag_limit} hashtags max")

    # List valid platforms
    print(VALID_PLATFORMS)  # ["LinkedIn", "Facebook", "Instagram", "TikTok"]
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PlatformConfig:
    """
    Configuration for a specific social media platform.

    This dataclass defines all platform-specific guidelines for generating optimized
    social media content. It includes character limits, tone, hashtag strategies,
    emoji usage, and expected content format.

    Attributes:
        name: Platform name (e.g., "LinkedIn", "Facebook")
        max_chars: Maximum allowed characters for a post
        optimal_chars: Optimal character count for best engagement
        tone: Recommended tone and style for the platform
        hashtag_limit: Maximum number of hashtags to use
        emoji_usage: Guidelines for emoji frequency (e.g., "Moderate (1-2 per post)")
        cta_style: Call-to-action strategy for the platform
        format: Recommended post structure or format
    """
    name: str
    max_chars: int
    optimal_chars: int
    tone: str
    hashtag_limit: int
    emoji_usage: str
    cta_style: str
    format: str


# Platform profiles with specifications optimized for each platform
PLATFORM_PROFILES: Dict[str, PlatformConfig] = {
    "LinkedIn": PlatformConfig(
        name="LinkedIn",
        max_chars=3000,
        optimal_chars=1300,
        tone="Professional, thought-leadership",
        hashtag_limit=5,
        emoji_usage="Moderate (1-2 per post)",
        cta_style="Ask questions, invite discussion",
        format="Hook → Insights → CTA"
    ),
    "Facebook": PlatformConfig(
        name="Facebook",
        max_chars=63206,
        optimal_chars=250,
        tone="Conversational, community-focused",
        hashtag_limit=3,
        emoji_usage="High (3-5 per post)",
        cta_style="Ask for shares, reactions",
        format="Story → Value → Emotion"
    ),
    "Instagram": PlatformConfig(
        name="Instagram",
        max_chars=2200,
        optimal_chars=150,
        tone="Visual storytelling, authentic",
        hashtag_limit=30,
        emoji_usage="Very High (5-10)",
        cta_style="Link in bio, save for later",
        format="Hook → Visual description → Hashtags"
    ),
    "TikTok": PlatformConfig(
        name="TikTok",
        max_chars=2200,
        optimal_chars=100,
        tone="Casual, entertaining, trend-aware",
        hashtag_limit=5,
        emoji_usage="High (3-5)",
        cta_style="Watch till end, follow for more",
        format="Hook → Quick tips → Trending audio"
    ),
}

# List of valid platform names
VALID_PLATFORMS: List[str] = ["LinkedIn", "Facebook", "Instagram", "TikTok"]


def get_platform_config(platform: str) -> PlatformConfig:
    """
    Get validated platform configuration.

    Retrieves the platform-specific configuration from PLATFORM_PROFILES dictionary.
    Validates that the requested platform is in VALID_PLATFORMS before returning.

    Args:
        platform: Name of the platform (must be one of: LinkedIn, Facebook, Instagram, TikTok)

    Returns:
        PlatformConfig: Configuration object for the specified platform

    Raises:
        ValueError: If platform name is not in VALID_PLATFORMS

    Examples:
        >>> config = get_platform_config("LinkedIn")
        >>> print(config.optimal_chars)
        1300

        >>> try:
        ...     config = get_platform_config("Twitter")
        ... except ValueError as e:
        ...     print(f"Platform not supported: {e}")
        Platform not supported: ...
    """
    if platform not in VALID_PLATFORMS:
        raise ValueError(
            f"Platform '{platform}' not supported. "
            f"Valid platforms are: {', '.join(VALID_PLATFORMS)}"
        )

    return PLATFORM_PROFILES[platform]
