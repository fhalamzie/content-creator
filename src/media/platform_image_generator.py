"""
Platform-Specific Image Generator

Generates images for social media platforms with smart optimization:
- LinkedIn: Reuse OG image (Pillow, $0)
- Facebook: Reuse OG image (Pillow, $0)
- Instagram: Generate 1:1 image (Flux Dev, $0.003)
- TikTok: Generate 9:16 image (Flux Dev, $0.003)

Features:
- Smart OG image reuse (avoid duplicate AI costs)
- Platform-specific aspect ratios
- Fallback to Pillow templates if Flux fails
- Cost tracking per platform
- Base64 data URL encoding for easy storage

Usage:
    generator = PlatformImageGenerator()
    result = await generator.generate_platform_image(
        platform="Instagram",
        topic="PropTech Innovation",
        excerpt="Brief excerpt...",
        brand_tone=["Professional"],
        brand_color="#1a73e8"
    )

    # Returns:
    # {
    #     "success": True,
    #     "url": "https://replicate.delivery/...",  # or base64 data URL
    #     "format": "png",
    #     "size": {"width": 1080, "height": 1080},
    #     "cost": 0.003,
    #     "provider": "flux-dev"  # or "pillow"
    # }
"""

import logging
import base64
from typing import Dict, List, Optional
from PIL import Image
import io

from src.media.image_generator import ImageGenerator
from src.media.og_image_generator import OGImageGenerator

logger = logging.getLogger(__name__)


class PlatformImageGenerator:
    """
    Generate platform-specific images with smart OG reuse

    Platform Strategy:
    - LinkedIn/Facebook: Use OG image (1200x630, $0)
    - Instagram: Generate AI image (1:1, $0.003)
    - TikTok: Generate AI image (9:16, $0.003)

    Total cost: $0.006 per blog post (2 AI images + 1 OG image reused)
    """

    # Platform image specifications
    PLATFORM_SPECS = {
        "LinkedIn": {
            "aspect_ratio": "16:9",  # OG image ratio
            "size": {"width": 1200, "height": 630},
            "use_og": True,
            "provider": "pillow"
        },
        "Facebook": {
            "aspect_ratio": "16:9",  # OG image ratio
            "size": {"width": 1200, "height": 630},
            "use_og": True,
            "provider": "pillow"
        },
        "Instagram": {
            "aspect_ratio": "1:1",
            "size": {"width": 1080, "height": 1080},
            "use_og": False,
            "provider": "flux-dev"
        },
        "TikTok": {
            "aspect_ratio": "9:16",
            "size": {"width": 1080, "height": 1920},
            "use_og": False,
            "provider": "flux-dev"
        }
    }

    def __init__(
        self,
        image_generator: Optional[ImageGenerator] = None,
        og_generator: Optional[OGImageGenerator] = None
    ):
        """
        Initialize platform image generator

        Args:
            image_generator: ImageGenerator instance (Flux)
            og_generator: OGImageGenerator instance (Pillow)
        """
        self.image_gen = image_generator
        self.og_gen = og_generator or OGImageGenerator()

        logger.info(
            "platform_image_generator_initialized",
            has_flux=self.image_gen is not None,
            has_pillow=self.og_gen is not None
        )

    async def generate_platform_image(
        self,
        platform: str,
        topic: str,
        excerpt: str,
        brand_tone: List[str] = ["Professional"],
        brand_color: str = "#1a73e8",
        logo_path: Optional[str] = None,
        use_og_fallback: bool = True
    ) -> Dict:
        """
        Generate platform-specific image

        Platform logic:
        - LinkedIn: Use OG image (Pillow, $0)
        - Facebook: Use OG image (Pillow, $0)
        - Instagram: Generate 1:1 with Flux Dev ($0.003)
        - TikTok: Generate 9:16 with Flux Dev ($0.003)

        Args:
            platform: Platform name (LinkedIn, Facebook, Instagram, TikTok)
            topic: Blog post title
            excerpt: Blog post excerpt
            brand_tone: Brand tone descriptors
            brand_color: Brand color (hex)
            logo_path: Path to logo file (optional)
            use_og_fallback: If True, fallback to OG image if AI fails

        Returns:
            {
                "success": bool,
                "url": str,  # Replicate URL or base64 data URL
                "format": str,  # "png" or "jpeg"
                "size": Dict,  # {"width": 1080, "height": 1080}
                "cost": float,
                "provider": str  # "pillow" or "flux-dev"
            }
        """
        if platform not in self.PLATFORM_SPECS:
            raise ValueError(
                f"Platform '{platform}' not supported. "
                f"Valid platforms: {', '.join(self.PLATFORM_SPECS.keys())}"
            )

        spec = self.PLATFORM_SPECS[platform]

        logger.info(
            "generating_platform_image",
            platform=platform,
            use_og=spec["use_og"],
            provider=spec["provider"]
        )

        # Strategy 1: Use OG image (LinkedIn/Facebook)
        if spec["use_og"]:
            return self._generate_og_image(
                topic=topic,
                excerpt=excerpt,
                brand_color=brand_color,
                logo_path=logo_path,
                platform=platform
            )

        # Strategy 2: Generate AI image (Instagram/TikTok)
        if self.image_gen is None:
            logger.warning("ImageGenerator not available, falling back to OG image")
            if use_og_fallback:
                return self._generate_og_image(
                    topic=topic,
                    excerpt=excerpt,
                    brand_color=brand_color,
                    logo_path=logo_path,
                    platform=platform
                )
            else:
                return {
                    "success": False,
                    "cost": 0.0,
                    "error": "ImageGenerator not available and OG fallback disabled"
                }

        try:
            result = await self._generate_ai_image(
                topic=topic,
                brand_tone=brand_tone,
                aspect_ratio=spec["aspect_ratio"],
                platform=platform
            )

            if result and result.get("success"):
                return result
            else:
                # AI generation failed, fallback to OG if enabled
                if use_og_fallback:
                    logger.warning(
                        f"AI image generation failed for {platform}, falling back to OG image"
                    )
                    return self._generate_og_image(
                        topic=topic,
                        excerpt=excerpt,
                        brand_color=brand_color,
                        logo_path=logo_path,
                        platform=platform
                    )
                else:
                    return {
                        "success": False,
                        "cost": 0.0,
                        "error": "AI generation failed and OG fallback disabled"
                    }

        except Exception as e:
            logger.error(
                f"Failed to generate {platform} image: {e}",
                platform=platform,
                error=str(e)
            )

            if use_og_fallback:
                return self._generate_og_image(
                    topic=topic,
                    excerpt=excerpt,
                    brand_color=brand_color,
                    logo_path=logo_path,
                    platform=platform
                )
            else:
                return {
                    "success": False,
                    "cost": 0.0,
                    "error": str(e)
                }

    def _generate_og_image(
        self,
        topic: str,
        excerpt: str,
        brand_color: str,
        logo_path: Optional[str],
        platform: str
    ) -> Dict:
        """
        Generate OG image using Pillow

        Args:
            topic: Blog post title
            excerpt: Blog post excerpt
            brand_color: Brand color (hex)
            logo_path: Path to logo file (optional)
            platform: Platform name (for logging)

        Returns:
            Image result dict
        """
        try:
            # Generate OG image (PNG bytes)
            img_bytes = self.og_gen.generate(
                title=topic,
                excerpt=excerpt,
                template="minimal",  # Default to minimal for social
                brand_color=brand_color,
                logo_path=logo_path
            )

            # Convert to base64 data URL for easy storage
            b64_data = base64.b64encode(img_bytes).decode('utf-8')
            data_url = f"data:image/png;base64,{b64_data}"

            logger.info(
                "og_image_generated_for_platform",
                platform=platform,
                size_kb=len(img_bytes) / 1024
            )

            return {
                "success": True,
                "url": data_url,  # Base64 data URL
                "format": "png",
                "size": {"width": 1200, "height": 630},
                "cost": 0.0,  # Pillow is free
                "provider": "pillow",
                "bytes": img_bytes  # Include raw bytes for saving to file
            }

        except Exception as e:
            logger.error(
                f"Failed to generate OG image for {platform}: {e}",
                platform=platform,
                error=str(e)
            )
            return {
                "success": False,
                "cost": 0.0,
                "error": str(e)
            }

    async def _generate_ai_image(
        self,
        topic: str,
        brand_tone: List[str],
        aspect_ratio: str,
        platform: str
    ) -> Dict:
        """
        Generate AI image using Flux Dev

        Args:
            topic: Blog post title
            brand_tone: Brand tone descriptors
            aspect_ratio: Image aspect ratio (1:1 or 9:16)
            platform: Platform name (for logging)

        Returns:
            Image result dict
        """
        try:
            # Generate with Flux Dev (supports 1:1 and 9:16)
            result = await self.image_gen.generate_supporting_image(
                topic=topic,
                brand_tone=brand_tone,
                aspect=f"{platform} post",
                aspect_ratio=aspect_ratio  # NOTE: This needs to be added to generate_supporting_image
            )

            if result is None:
                return {
                    "success": False,
                    "cost": 0.0,
                    "error": "Flux Dev generation returned None"
                }

            # Extract size from aspect ratio
            if aspect_ratio == "1:1":
                size = {"width": 1080, "height": 1080}
            elif aspect_ratio == "9:16":
                size = {"width": 1080, "height": 1920}
            else:
                size = {"width": 1024, "height": 1024}  # Default

            logger.info(
                "ai_image_generated_for_platform",
                platform=platform,
                aspect_ratio=aspect_ratio,
                cost=result.get("cost", 0.0)
            )

            return {
                "success": True,
                "url": result["url"],  # Replicate URL
                "format": "png",
                "size": size,
                "cost": result.get("cost", 0.003),
                "provider": "flux-dev",
                "model": result.get("model", "Flux Dev")
            }

        except Exception as e:
            logger.error(
                f"Failed to generate AI image for {platform}: {e}",
                platform=platform,
                error=str(e)
            )
            return {
                "success": False,
                "cost": 0.0,
                "error": str(e)
            }

    async def generate_all_platform_images(
        self,
        topic: str,
        excerpt: str,
        brand_tone: List[str] = ["Professional"],
        brand_color: str = "#1a73e8",
        logo_path: Optional[str] = None,
        platforms: List[str] = ["LinkedIn", "Facebook", "Instagram", "TikTok"]
    ) -> Dict:
        """
        Generate images for all platforms concurrently

        Args:
            topic: Blog post title
            excerpt: Blog post excerpt
            brand_tone: Brand tone descriptors
            brand_color: Brand color (hex)
            logo_path: Path to logo file (optional)
            platforms: List of platforms to generate for

        Returns:
            {
                "success": bool,
                "images": {
                    "LinkedIn": {...},
                    "Facebook": {...},
                    "Instagram": {...},
                    "TikTok": {...}
                },
                "total_cost": float,
                "og_image_reused": bool
            }
        """
        import asyncio

        # Generate OG image once (shared by LinkedIn/Facebook)
        og_result = None
        og_platforms = [p for p in platforms if self.PLATFORM_SPECS[p]["use_og"]]

        if og_platforms:
            og_result = self._generate_og_image(
                topic=topic,
                excerpt=excerpt,
                brand_color=brand_color,
                logo_path=logo_path,
                platform="OG (shared)"
            )

        # Generate platform-specific images
        images = {}
        total_cost = 0.0

        for platform in platforms:
            if self.PLATFORM_SPECS[platform]["use_og"] and og_result:
                # Reuse OG image
                images[platform] = og_result
                total_cost += 0.0  # OG is free
            else:
                # Generate AI image
                result = await self.generate_platform_image(
                    platform=platform,
                    topic=topic,
                    excerpt=excerpt,
                    brand_tone=brand_tone,
                    brand_color=brand_color,
                    logo_path=logo_path,
                    use_og_fallback=True
                )
                images[platform] = result
                total_cost += result.get("cost", 0.0)

        logger.info(
            "all_platform_images_generated",
            num_platforms=len(platforms),
            total_cost=total_cost,
            og_reused=len(og_platforms) > 0
        )

        return {
            "success": True,
            "images": images,
            "total_cost": total_cost,
            "og_image_reused": len(og_platforms) > 0
        }


def should_use_og_image(platform: str) -> bool:
    """
    Determine if platform should use OG image

    LinkedIn/Facebook: True (use OG image, free)
    Instagram/TikTok: False (generate AI image, $0.003)

    Args:
        platform: Platform name

    Returns:
        True if should use OG image
    """
    return PlatformImageGenerator.PLATFORM_SPECS.get(platform, {}).get("use_og", False)
