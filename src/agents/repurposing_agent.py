"""
Social media content repurposing agent

Generates platform-optimized posts from blog articles using Qwen3-Max.
Supports LinkedIn, Facebook, Instagram, and TikTok with platform-specific
tone, length, format, hashtags, emoji usage, and images.

Design Principles:
- Platform-specific content optimization (tone, length, format)
- Smart image generation (OG reuse for LinkedIn/Facebook, AI for Instagram/TikTok)
- Batch generation for multiple platforms
- Cost tracking per platform (text + images)
- Cache integration (fail-safe)
- Multi-language content generation
"""

from pathlib import Path
from typing import Dict, List, Any, Optional

from src.agents.base_agent import BaseAgent, AgentError
from src.agents.platform_profiles import get_platform_config, VALID_PLATFORMS
from src.cache_manager import CacheManager
from src.media.platform_image_generator import PlatformImageGenerator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RepurposingError(AgentError):
    """Raised when repurposing operations fail"""
    pass


class RepurposingAgent(BaseAgent):
    """
    Generates platform-optimized social media content from blog posts

    Features:
    - Platform-specific text optimization (tone, length, format)
    - Hashtag generation with platform limits
    - Cost tracking per platform
    - Batch generation for multiple platforms
    - Multi-language content generation (de, en, fr, etc.)
    - Cache integration (optional)

    Example:
        agent = RepurposingAgent(api_key=os.getenv("OPENROUTER_API_KEY"))
        results = agent.generate_social_posts(
            blog_post={
                "title": "Die Zukunft von PropTech",
                "excerpt": "Innovative Technologien revolutionieren...",
                "keywords": ["PropTech", "Innovation", "Digitalisierung"],
                "slug": "proptech-zukunft"
            },
            platforms=["LinkedIn", "Facebook"],
            brand_tone=["Professional"]
        )

        # Results:
        # [
        #     {
        #         "platform": "LinkedIn",
        #         "content": "...",
        #         "hashtags": ["#PropTech", "#Innovation"],
        #         "character_count": 450,
        #         "cost": 0.0008,
        #         "tokens": {"prompt": 200, "completion": 150, "total": 350}
        #     },
        #     ...
        # ]
    """

    def __init__(
        self,
        api_key: str,
        cache_dir: Optional[str] = None,
        custom_config: Optional[Dict] = None,
        image_generator: Optional[PlatformImageGenerator] = None
    ):
        """
        Initialize RepurposingAgent

        Args:
            api_key: OpenRouter API key
            cache_dir: Directory for caching (default: cache/)
            custom_config: Override agent config from models.yaml
            image_generator: PlatformImageGenerator instance (optional)

        Raises:
            RepurposingError: If initialization fails
        """
        # Call parent with agent_type="repurposing"
        super().__init__(
            agent_type="repurposing",
            api_key=api_key,
            custom_config=custom_config
        )

        # Initialize cache manager if cache_dir provided
        self.cache_manager = None
        if cache_dir:
            try:
                self.cache_manager = CacheManager(cache_dir=cache_dir)
                logger.info("cache_manager_initialized", cache_dir=cache_dir)
            except Exception as e:
                logger.warning("cache_manager_init_failed", error=str(e))

        # Initialize image generator (optional)
        self.image_generator = image_generator

        # Load prompt template (language-agnostic)
        try:
            self.prompt_template = self._load_prompt_template()
            logger.info("prompt_template_loaded", language_agnostic=True)
        except Exception as e:
            raise RepurposingError(f"Failed to load prompt template: {e}") from e

        logger.info(
            "repurposing_agent_initialized",
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            has_image_generator=self.image_generator is not None
        )

    async def generate_social_posts(
        self,
        blog_post: Dict[str, Any],
        platforms: List[str] = ["LinkedIn", "Facebook", "Instagram", "TikTok"],
        brand_tone: List[str] = ["Professional"],
        language: str = "de",
        save_to_cache: bool = True,
        generate_images: bool = False,
        brand_color: str = "#1a73e8",
        logo_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate social posts for multiple platforms (text + optional images)

        Args:
            blog_post: Dict with keys: title, excerpt, keywords (list), slug
            platforms: List of platform names (must be in VALID_PLATFORMS)
            brand_tone: Brand voice settings (e.g., ["Professional", "Friendly"])
            language: Output language code (e.g., "de", "en", "fr") - default: "de"
            save_to_cache: Whether to save to cache/social_posts/
            generate_images: Whether to generate platform images (default: False)
            brand_color: Brand color hex code for OG images (default: #1a73e8)
            logo_path: Path to logo file for OG images (optional)

        Returns:
            List of dicts, one per platform:
            [
                {
                    "platform": "LinkedIn",
                    "content": "Post text...",
                    "hashtags": ["#PropTech", "#Innovation"],
                    "character_count": 450,
                    "image": {  # Only if generate_images=True
                        "url": "https://replicate.delivery/..." or "data:image/png;base64,...",
                        "provider": "pillow" or "flux-dev",
                        "cost": 0.0 or 0.003
                    },
                    "cost": 0.0008,  # Text cost + image cost
                    "tokens": {"prompt": 200, "completion": 150, "total": 350}
                },
                ...
            ]

        Raises:
            RepurposingError: If generation fails for all platforms
            ValueError: If platforms list is empty or contains invalid platforms
        """
        # Validate inputs
        if not platforms:
            raise ValueError("platforms list cannot be empty")

        # Validate required blog_post keys
        required_keys = ["title", "excerpt", "keywords", "slug"]
        missing_keys = [key for key in required_keys if key not in blog_post]
        if missing_keys:
            raise ValueError(
                f"blog_post missing required keys: {', '.join(missing_keys)}"
            )

        # Validate platforms
        invalid_platforms = [p for p in platforms if p not in VALID_PLATFORMS]
        if invalid_platforms:
            raise ValueError(
                f"Invalid platforms: {', '.join(invalid_platforms)}. "
                f"Valid platforms are: {', '.join(VALID_PLATFORMS)}"
            )

        logger.info(
            "social_posts_generation_started",
            topic=blog_post['title'],
            platforms=platforms,
            brand_tone=brand_tone,
            generate_images=generate_images
        )

        # Initialize results list
        results = []
        errors = []

        # Generate content for each platform
        for platform in platforms:
            try:
                logger.info("generating_platform_content", platform=platform)

                # Generate platform-specific text content
                result = self._generate_platform_content(
                    blog_post=blog_post,
                    platform=platform,
                    brand_tone=brand_tone,
                    language=language
                )

                content = result['content']

                # Generate hashtags from keywords
                hashtags = self._generate_hashtags(
                    keywords=blog_post['keywords'],
                    platform=platform
                )

                # Calculate character count
                character_count = len(content)

                # Initialize total cost (text only)
                total_cost = result['cost']

                # Build result dict
                platform_result = {
                    'platform': platform,
                    'content': content,
                    'hashtags': hashtags,
                    'character_count': character_count,
                    'cost': total_cost,
                    'tokens': result['tokens']
                }

                # Generate image if requested and generator available
                if generate_images and self.image_generator:
                    try:
                        logger.info("generating_platform_image", platform=platform)

                        image_result = await self.image_generator.generate_platform_image(
                            platform=platform,
                            topic=blog_post['title'],
                            excerpt=blog_post['excerpt'],
                            brand_tone=brand_tone,
                            brand_color=brand_color,
                            logo_path=logo_path,
                            use_og_fallback=True
                        )

                        if image_result.get("success"):
                            platform_result['image'] = {
                                'url': image_result['url'],
                                'provider': image_result['provider'],
                                'cost': image_result['cost'],
                                'size': image_result.get('size', {})
                            }
                            total_cost += image_result['cost']
                            platform_result['cost'] = total_cost

                            logger.info(
                                "platform_image_generated",
                                platform=platform,
                                provider=image_result['provider'],
                                cost=image_result['cost']
                            )
                        else:
                            logger.warning(
                                "platform_image_generation_failed",
                                platform=platform,
                                error=image_result.get('error', 'Unknown error')
                            )

                    except Exception as e:
                        logger.error(
                            "platform_image_generation_error",
                            platform=platform,
                            error=str(e)
                        )
                        # Continue without image (don't fail the whole post)

                results.append(platform_result)

                # Save to cache if enabled
                if save_to_cache and self.cache_manager:
                    try:
                        self.cache_manager.write_social_post(
                            slug=blog_post['slug'],
                            platform=platform.lower(),
                            content=content
                        )
                        logger.info("social_post_cached", platform=platform)
                    except Exception as e:
                        # Don't fail on cache errors
                        logger.error(
                            "cache_write_failed",
                            platform=platform,
                            error=str(e)
                        )

                logger.info(
                    "platform_post_generated",
                    platform=platform,
                    character_count=character_count,
                    hashtag_count=len(hashtags),
                    has_image=generate_images and 'image' in platform_result,
                    cost=total_cost
                )

            except Exception as e:
                error_msg = f"Failed to generate {platform} post: {e}"
                logger.error("platform_generation_failed", platform=platform, error=str(e))
                errors.append(error_msg)
                continue

        # Check if all platforms failed
        if not results:
            raise RepurposingError(
                f"Failed to generate content for all platforms. Errors: {'; '.join(errors)}"
            )

        # Log summary
        total_cost = sum(r['cost'] for r in results)
        total_images = sum(1 for r in results if 'image' in r)
        logger.info(
            "social_posts_generation_complete",
            success_count=len(results),
            total_platforms=len(platforms),
            total_images=total_images,
            total_cost=total_cost
        )

        return results

    def _generate_platform_content(
        self,
        blog_post: Dict[str, Any],
        platform: str,
        brand_tone: List[str],
        language: str = "de"
    ) -> Dict[str, Any]:
        """
        Generate platform-optimized content using Qwen3-Max

        Args:
            blog_post: Blog post data
            platform: Platform name (LinkedIn, Facebook, etc.)
            brand_tone: Brand voice settings
            language: Output language code (e.g., "de", "en", "fr")

        Returns:
            Dict with keys: content, tokens, cost

        Raises:
            RepurposingError: If generation fails after retries
        """
        try:
            # Get platform config
            platform_config = get_platform_config(platform)

            # Build prompt with language parameter
            prompt = self._build_prompt(
                blog_post=blog_post,
                platform=platform,
                brand_tone=brand_tone,
                language=language
            )

            logger.debug(f"Generated prompt for {platform}: {len(prompt)} chars")

            # Call BaseAgent.generate() with prompt
            result = self.generate(prompt=prompt)

            content = result['content'].strip()

            # Enforce character limit (hard truncation if needed)
            if len(content) > platform_config.max_chars:
                logger.warning(
                    f"{platform} content exceeds max_chars "
                    f"({len(content)} > {platform_config.max_chars}). "
                    f"Truncating..."
                )
                content = content[:platform_config.max_chars - 3] + "..."

            return {
                'content': content,
                'tokens': result['tokens'],
                'cost': result['cost']
            }

        except AgentError as e:
            raise RepurposingError(
                f"Failed to generate {platform} content for '{blog_post['title']}': {e}"
            ) from e
        except Exception as e:
            raise RepurposingError(
                f"Unexpected error generating {platform} content: {e}"
            ) from e

    def _generate_hashtags(
        self,
        keywords: List[str],
        platform: str
    ) -> List[str]:
        """
        Generate platform-specific hashtags from keywords

        Strategy:
        - Convert keywords to hashtags (capitalize, remove spaces)
        - Respect platform limits (5 for LinkedIn, 30 for Instagram, etc.)
        - Format: #PropTech (not #prop tech or #proptech)

        Args:
            keywords: List of keywords from blog post
            platform: Platform name

        Returns:
            List of formatted hashtags (e.g., ["#PropTech", "#Innovation"])
        """
        # Get platform config for hashtag_limit
        platform_config = get_platform_config(platform)

        # Convert keywords to hashtags
        hashtags = []
        for keyword in keywords:
            # Remove spaces and capitalize first letter of each word (CamelCase)
            # Split by space, capitalize each word, join without spaces
            words = keyword.split()
            camel_case = ''.join(word.capitalize() for word in words)

            # Add # prefix
            hashtag = f"#{camel_case}"
            hashtags.append(hashtag)

        # Limit to platform's hashtag_limit
        hashtags = hashtags[:platform_config.hashtag_limit]

        logger.debug(
            f"Generated {len(hashtags)} hashtags for {platform}: {hashtags}"
        )

        return hashtags

    def _load_prompt_template(self) -> str:
        """
        Load language-agnostic prompt template from config/prompts/repurpose.md

        Returns:
            Template content as string (English with {language} variable)

        Raises:
            RepurposingError: If file not found or read fails
        """
        # Get template path (language-agnostic)
        template_path = (
            Path(__file__).parent.parent.parent /
            "config" / "prompts" / "repurpose.md"
        )

        if not template_path.exists():
            raise RepurposingError(
                f"Prompt template not found: {template_path}"
            )

        try:
            content = template_path.read_text(encoding="utf-8")
            logger.debug(f"Loaded prompt template: {len(content)} chars")
            return content
        except Exception as e:
            raise RepurposingError(
                f"Failed to read prompt template: {e}"
            ) from e

    def _build_prompt(
        self,
        blog_post: Dict[str, Any],
        platform: str,
        brand_tone: List[str],
        language: str = "de"
    ) -> str:
        """
        Build final prompt by filling template variables

        Variables:
        - {language}: Output language (e.g., "de", "en", "fr")
        - {platform}: Platform name
        - {topic}: Blog title
        - {excerpt}: Blog excerpt
        - {keywords}: Comma-separated keywords
        - {tone}: Brand tone
        - {optimal_chars}: Optimal character count
        - {max_chars}: Maximum character count
        - {format}: Post format structure
        - {hashtag_limit}: Maximum hashtags
        - {emoji_usage}: Emoji usage guidelines
        - {cta_style}: CTA style

        Args:
            blog_post: Blog post data
            platform: Platform name
            brand_tone: Brand voice settings

        Returns:
            Filled prompt ready for LLM
        """
        # Get platform config
        platform_config = get_platform_config(platform)

        # Format keywords as comma-separated string
        keywords_str = ", ".join(blog_post['keywords'])

        # Format brand tone (join multiple tones)
        tone_str = ", ".join(brand_tone)

        # Replace all template variables (including language)
        prompt = self.prompt_template.format(
            language=language,
            platform=platform_config.name,
            topic=blog_post['title'],
            excerpt=blog_post['excerpt'],
            keywords=keywords_str,
            tone=tone_str,
            optimal_chars=platform_config.optimal_chars,
            max_chars=platform_config.max_chars,
            format=platform_config.format,
            hashtag_limit=platform_config.hashtag_limit,
            emoji_usage=platform_config.emoji_usage,
            cta_style=platform_config.cta_style
        )

        return prompt
