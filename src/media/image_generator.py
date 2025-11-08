"""
Image Generator - DALL-E 3 integration with tone-aware prompt mapping

Generates hero and supporting images for blog articles with:
- 7-tone prompt mapping (Professional, Technical, Creative, etc.)
- DALL-E 3 integration (HD hero 1792x1024, Standard supporting 1024x1024)
- Silent failure handling (3 retries, return None on error)
- Cost tracking ($0.08 HD, $0.04 Standard)

Example:
    from src.media.image_generator import ImageGenerator

    generator = ImageGenerator(api_key="your_key")

    # Generate hero image
    hero = await generator.generate_hero_image(
        topic="PropTech AI trends",
        brand_tone=["Professional", "Technical"]
    )

    # Generate supporting images
    support1 = await generator.generate_supporting_image(
        topic="PropTech AI trends",
        brand_tone=["Professional"],
        aspect="implementation"
    )
"""

import os
import asyncio
from typing import List, Optional, Dict
from openai import AsyncOpenAI

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ImageGenerationError(Exception):
    """Raised when image generation fails after retries"""
    pass


class ImageGenerator:
    """
    Image generator for blog articles using DALL-E 3

    Features:
    - 7-tone prompt mapping (Professional, Technical, Creative, Casual,
      Authoritative, Innovative, Friendly)
    - Hero image: 1792x1024 HD ($0.08)
    - Supporting image: 1024x1024 Standard ($0.04)
    - Silent failure: Returns None after 3 retries
    - Cost tracking per image
    """

    # DALL-E 3 costs (per image)
    COST_HD = 0.08      # 1792x1024 HD
    COST_STANDARD = 0.04  # 1024x1024 Standard

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    # Tone to style mapping
    TONE_STYLES = {
        "professional": "professional, corporate, business-oriented, clean design",
        "technical": "technical, diagram-style, blueprint aesthetic, precise",
        "creative": "creative, artistic, vibrant colors, imaginative",
        "casual": "casual, friendly, approachable, warm colors",
        "authoritative": "authoritative, expert-level, confident, premium quality",
        "innovative": "innovative, futuristic, cutting-edge, modern",
        "friendly": "friendly, welcoming, approachable, soft colors"
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize image generator

        Args:
            api_key: OpenAI API key (auto-loads from /home/envs/openai.env if not provided)

        Raises:
            ValueError: If API key not found
        """
        # Load API key
        self.api_key = api_key or self._load_api_key()
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not found in environment or /home/envs/openai.env"
            )

        # Initialize OpenAI client
        self.client = AsyncOpenAI(api_key=self.api_key)

        logger.info("image_generator_initialized", api_key_set=bool(self.api_key))

    def _load_api_key(self) -> Optional[str]:
        """Load OpenAI API key from environment"""
        # Check environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            return api_key

        # Check /home/envs/openai.env
        env_file = "/home/envs/openai.env"
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'OPENAI_API_KEY':
                                logger.info("openai_key_loaded_from_file", file=env_file)
                                return value.strip()
            except Exception as e:
                logger.warning("failed_to_load_openai_key", error=str(e))

        return None

    def _map_tone_to_prompt(
        self,
        brand_tone: List[str],
        topic: str,
        is_hero: bool
    ) -> str:
        """
        Map brand tone to DALL-E prompt style

        Args:
            brand_tone: List of tone descriptors (e.g., ['Professional', 'Technical'])
            topic: Article topic
            is_hero: True for hero image, False for supporting

        Returns:
            DALL-E prompt with tone-appropriate styling
        """
        # Default to Professional if no tone specified
        if not brand_tone:
            brand_tone = ["Professional"]

        # Get style descriptors for each tone (case-insensitive)
        styles = []
        for tone in brand_tone:
            tone_lower = tone.lower()
            if tone_lower in self.TONE_STYLES:
                styles.append(self.TONE_STYLES[tone_lower])
            else:
                # Unknown tone defaults to professional
                logger.warning("unknown_tone_defaulting_to_professional", tone=tone)
                styles.append(self.TONE_STYLES["professional"])

        # Combine styles
        combined_style = ", ".join(styles) if len(styles) > 1 else styles[0]

        # Build prompt
        image_type = "hero banner image" if is_hero else "supporting illustration"
        prompt = (
            f"Create a {image_type} for an article about '{topic}'. "
            f"Style: {combined_style}. "
            f"No text or typography in the image. "
            f"High quality, professional composition."
        )

        logger.info(
            "tone_mapped_to_prompt",
            tones=brand_tone,
            is_hero=is_hero,
            prompt_length=len(prompt)
        )

        return prompt

    async def _generate_with_retry(
        self,
        prompt: str,
        size: str,
        quality: str
    ) -> Optional[str]:
        """
        Generate image with retry logic

        Args:
            prompt: DALL-E prompt
            size: Image size (1792x1024 or 1024x1024)
            quality: Image quality (hd or standard)

        Returns:
            Image URL or None if all retries failed
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(
                    "image_generation_attempt",
                    attempt=attempt,
                    size=size,
                    quality=quality
                )

                response = await self.client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=1
                )

                url = response.data[0].url
                logger.info(
                    "image_generation_success",
                    attempt=attempt,
                    url_length=len(url)
                )
                return url

            except Exception as e:
                logger.warning(
                    "image_generation_attempt_failed",
                    attempt=attempt,
                    error=str(e),
                    error_type=type(e).__name__
                )

                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    logger.error(
                        "image_generation_failed",
                        max_retries=self.MAX_RETRIES,
                        error=str(e)
                    )
                    return None

        return None

    async def generate_hero_image(
        self,
        topic: str,
        brand_tone: List[str]
    ) -> Optional[Dict]:
        """
        Generate hero image (1792x1024 HD, $0.08)

        Args:
            topic: Article topic
            brand_tone: Brand tone descriptors (e.g., ['Professional', 'Technical'])

        Returns:
            Dict with url, size, quality, cost or None if failed
        """
        logger.info("generating_hero_image", topic=topic, tones=brand_tone)

        # Map tone to prompt
        prompt = self._map_tone_to_prompt(brand_tone, topic, is_hero=True)

        # Generate with retry
        url = await self._generate_with_retry(
            prompt=prompt,
            size="1792x1024",
            quality="hd"
        )

        if url is None:
            return None

        return {
            "url": url,
            "size": "1792x1024",
            "quality": "hd",
            "cost": self.COST_HD
        }

    async def generate_supporting_image(
        self,
        topic: str,
        brand_tone: List[str],
        aspect: str
    ) -> Optional[Dict]:
        """
        Generate supporting image (1024x1024 Standard, $0.04)

        Args:
            topic: Article topic
            brand_tone: Brand tone descriptors
            aspect: Aspect to illustrate (e.g., 'implementation', 'benefits', 'overview')

        Returns:
            Dict with url, size, quality, cost or None if failed
        """
        logger.info(
            "generating_supporting_image",
            topic=topic,
            aspect=aspect,
            tones=brand_tone
        )

        # Add aspect to topic for more specific prompt
        topic_with_aspect = f"{topic} - {aspect}"

        # Map tone to prompt
        prompt = self._map_tone_to_prompt(brand_tone, topic_with_aspect, is_hero=False)

        # Generate with retry
        url = await self._generate_with_retry(
            prompt=prompt,
            size="1024x1024",
            quality="standard"
        )

        if url is None:
            return None

        return {
            "url": url,
            "size": "1024x1024",
            "quality": "standard",
            "cost": self.COST_STANDARD
        }


# Helper function for loading env file (for testing)
def load_env_file(file_path: str) -> Dict[str, str]:
    """
    Load environment variables from file

    Args:
        file_path: Path to .env file

    Returns:
        Dict of environment variables
    """
    env_vars = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        except Exception as e:
            logger.warning("failed_to_load_env_file", file=file_path, error=str(e))
    return env_vars
