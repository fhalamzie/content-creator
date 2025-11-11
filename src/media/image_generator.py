"""
Image Generator - Flux 1.1 Pro Ultra (RAW MODE) for photorealistic images

Generates hero and supporting images for blog articles with:
- Flux 1.1 Pro Ultra with RAW MODE (true photorealism, not 3D art!)
- Simple German prompts expanded with Qwen
- 2048x2048 high resolution images
- Cost: $0.04 per image (same as DALL-E standard, but MUCH better quality)
- 8-10 second generation time

RAW MODE delivers:
- Authentic, candid photographic feel
- Natural textures and imperfections
- Real-world realism (not polished 3D renders)
- Professional photography aesthetic

Example:
    from src.media.image_generator import ImageGenerator

    generator = ImageGenerator()  # Uses Replicate API

    # Generate hero image
    hero = await generator.generate_hero_image(
        topic="Versicherungsschäden",
        brand_tone=["Professional"]
    )
"""

import os
import asyncio
from typing import List, Optional, Dict
from openai import AsyncOpenAI
import replicate

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ImageGenerationError(Exception):
    """Raised when image generation fails after retries"""
    pass


class ImageGenerator:
    """
    Image generator using Flux 1.1 Pro Ultra with RAW MODE

    Features:
    - Flux 1.1 Pro Ultra with RAW MODE for true photorealism
    - Prompt expansion with Qwen (German prompts → detailed descriptions)
    - High resolution: 2048x2048 (4x better than standard)
    - Fast generation: 8-10 seconds
    - Authentic photography: natural textures, imperfections, realism
    - Cost: $0.04 per image (all images, any aspect ratio)
    """

    # Flux 1.1 Pro Ultra costs
    COST_PER_IMAGE = 0.04  # Same cost for all images

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize image generator

        Args:
            api_key: Replicate API key (auto-loads from /home/envs/replicate.env if not provided)

        Raises:
            ValueError: If API key not found
        """
        # Load Replicate API key for Flux
        self.replicate_key = api_key or self._load_replicate_key()
        if not self.replicate_key:
            raise ValueError(
                "REPLICATE_API_TOKEN not found in environment or /home/envs/replicate.env"
            )

        # Initialize Replicate client
        self.client = replicate.Client(api_token=self.replicate_key)

        # Load OpenRouter API key for Qwen (prompt expansion)
        self.openrouter_key = self._load_openrouter_key()
        if not self.openrouter_key:
            logger.warning("OPENROUTER_API_KEY not found, prompt expansion will be limited")
            self.openrouter_client = None
        else:
            # Initialize OpenRouter client (OpenAI-compatible)
            self.openrouter_client = AsyncOpenAI(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )

        logger.info(
            "image_generator_initialized",
            provider="flux-1.1-pro-ultra-raw",
            has_replicate_key=bool(self.replicate_key),
            has_openrouter_key=bool(self.openrouter_key)
        )

    def _load_replicate_key(self) -> Optional[str]:
        """Load Replicate API key from environment"""
        # Check environment variable
        api_key = os.getenv("REPLICATE_API_TOKEN")
        if api_key:
            return api_key

        # Check /home/envs/replicate.env
        env_file = "/home/envs/replicate.env"
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'REPLICATE_API_TOKEN':
                                logger.info("replicate_key_loaded_from_file", file=env_file)
                                return value.strip()
            except Exception as e:
                logger.warning("failed_to_load_replicate_key", error=str(e))

        return None

    def _load_openrouter_key(self) -> Optional[str]:
        """Load OpenRouter API key from environment"""
        # Check environment variable
        api_key = os.getenv("OPENROUTER_API_KEY")
        if api_key:
            return api_key

        # Check /home/envs/openrouter.env
        env_file = "/home/envs/openrouter.env"
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'OPENROUTER_API_KEY':
                                logger.info("openrouter_key_loaded_from_file", file=env_file)
                                return value.strip()
            except Exception as e:
                logger.warning("failed_to_load_openrouter_key", error=str(e))

        return None

    async def _expand_prompt_with_llm(self, simple_prompt: str, topic: str) -> str:
        """
        Expand simple prompt into detailed DALL-E 3 prompt using Qwen via OpenRouter.

        This mimics what ChatGPT does - it expands short prompts into detailed,
        descriptive prompts that produce photorealistic results.

        Args:
            simple_prompt: Simple prompt like "Ein Bild über Versicherungsschäden"
            topic: Original topic

        Returns:
            Expanded, detailed prompt in German
        """
        # If OpenRouter not available, return simple prompt
        if not self.openrouter_client:
            logger.warning("OpenRouter not configured, using simple prompt")
            return simple_prompt

        expansion_prompt = f"""Du bist ein Experte für RAW-Fotografie Prompt-Engineering für Flux 1.1 Pro Ultra.

Expandiere diesen einfachen Prompt in einen detaillierten, RAW-Photography Prompt:

"{simple_prompt}"

Thema: {topic}

Erstelle einen detaillierten deutschen Prompt mit:
- VIELFÄLTIGE MOTIVE: Wähle das passendste Motiv für das Thema - Menschen, Objekte, Räume, Situationen, Details. Nicht immer Menschen!
- RAW AUTHENTIZITÄT: Betone Unperfektion, natürliche Texturen, leichte Fehler, Körnigkeit
- SCHARFE DETAILS: "Scharfe Fokussierung", "hohe Detailgenauigkeit", "klare Kanten"
- NATÜRLICHES LICHT: Echtes Tageslicht, keine perfekte Studiobeleuchtung
- KAMERA: "Aufgenommen mit DSLR", "RAW-Format", "dokumentarischer Stil"
- VERMEIDEN: Perfekte Symmetrie, zu saubere Szenen, Stockfoto-Ästhetik

Beispiele:
- Schadensmanagement: "Ein wasserfleckiger Parkettboden mit sichtbaren Beschädigungen, dokumentarischer RAW-Stil, natürliches Fensterlicht"
- Kundengespräch: "Zwei Personen im Beratungsgespräch an einem Holztisch, natürliches Tageslicht von der Seite, authentische Gesprächssituation"
- Digitale Tools: "Ein Laptop mit geöffneter Software auf einem Schreibtisch, scharfe Details der Benutzeroberfläche, leichte Unordnung im Hintergrund"

Wichtig: Auf Deutsch, RAW + CRISP + IMPERFEKT betonen, Motivwahl thematisch passend (nicht gezwungen).

Antworte NUR mit dem erweiterten Prompt, keine Erklärungen."""

        try:
            # Use Qwen via OpenRouter for prompt expansion (cheap and fast)
            response = await self.openrouter_client.chat.completions.create(
                model="qwen/qwen-2.5-72b-instruct",  # Fast and cheap via OpenRouter
                messages=[
                    {"role": "user", "content": expansion_prompt}
                ],
                temperature=0.7,
                max_tokens=200,
                extra_headers={
                    "HTTP-Referer": "https://github.com/content-creator",
                    "X-Title": "Content Creator - Image Prompt Expansion"
                }
            )

            expanded = response.choices[0].message.content.strip()

            # Remove quotes if LLM wrapped it
            if expanded.startswith('"') and expanded.endswith('"'):
                expanded = expanded[1:-1]

            logger.info(
                "prompt_expanded_with_qwen",
                original_length=len(simple_prompt),
                expanded_length=len(expanded),
                topic=topic
            )

            return expanded

        except Exception as e:
            logger.warning(f"Prompt expansion failed: {e}, using simple prompt")
            return simple_prompt

    def _map_tone_to_prompt(
        self,
        brand_tone: List[str],
        topic: str,
        is_hero: bool,
        domain: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        themes: Optional[List[str]] = None,
        article_excerpt: Optional[str] = None
    ) -> str:
        """
        Generate simple German prompt (will be expanded later with LLM)

        Args:
            brand_tone: List of tone descriptors (not used - kept for compatibility)
            topic: Article topic
            is_hero: True for hero image, False for supporting
            domain: Domain/vertical (not used - kept for compatibility)
            keywords: Key concepts (not used - kept for compatibility)
            themes: Main themes (not used - kept for compatibility)
            article_excerpt: Article excerpt (not used)

        Returns:
            Simple prompt in German (will be expanded by _expand_prompt_with_llm)
        """
        # Simple base prompt - will be expanded with LLM to match ChatGPT's approach
        prompt = f"Ein Bild über {topic}. Photorealistisch, passend für einen Blog-Artikel."

        logger.info(
            "simple_german_prompt_created",
            topic=topic,
            is_hero=is_hero,
            prompt_length=len(prompt)
        )

        return prompt

    async def _generate_with_retry(
        self,
        prompt: str,
        aspect_ratio: str,
        topic: str
    ) -> Optional[str]:
        """
        Generate image with retry logic using Flux 1.1 Pro Ultra (RAW MODE)

        Args:
            prompt: Simple base prompt
            aspect_ratio: Image aspect ratio (16:9 for hero, 1:1 for supporting)
            topic: Topic for prompt expansion

        Returns:
            Image URL or None if all retries failed
        """
        # CRITICAL: Expand prompt with Qwen (like ChatGPT does!)
        expanded_prompt = await self._expand_prompt_with_llm(prompt, topic)

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(
                    "flux_generation_attempt",
                    attempt=attempt,
                    aspect_ratio=aspect_ratio,
                    model="flux-1.1-pro-ultra-raw",
                    prompt_preview=expanded_prompt[:100]
                )

                # Run Flux 1.1 Pro Ultra with RAW MODE (synchronously)
                output = await asyncio.to_thread(
                    self.client.run,
                    "black-forest-labs/flux-1.1-pro-ultra",
                    input={
                        "prompt": expanded_prompt,
                        "aspect_ratio": aspect_ratio,
                        "output_format": "png",  # Flux supports jpg/png only
                        "safety_tolerance": 5,  # Higher = more diverse/raw outputs (max 6)
                        "raw": True  # RAW MODE = photorealistic, authentic photography!
                    }
                )

                # Flux returns a FileOutput object with .url attribute
                url = output.url if hasattr(output, 'url') else str(output)

                logger.info(
                    "flux_generation_success",
                    attempt=attempt,
                    url_length=len(url),
                    raw_mode=True
                )
                return url

            except Exception as e:
                logger.warning(
                    "flux_generation_attempt_failed",
                    attempt=attempt,
                    error=str(e),
                    error_type=type(e).__name__
                )

                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    logger.error(
                        "flux_generation_failed",
                        max_retries=self.MAX_RETRIES,
                        error=str(e)
                    )
                    return None

        return None

    async def generate_hero_image(
        self,
        topic: str,
        brand_tone: List[str],
        domain: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        themes: Optional[List[str]] = None,
        article_excerpt: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Generate hero image with Flux 1.1 Pro Ultra RAW MODE (16:9, 2048x2048, $0.04)

        Args:
            topic: Article topic
            brand_tone: Brand tone descriptors (not used currently)
            domain: Domain/vertical (not used currently)
            keywords: Key concepts (not used currently)
            themes: Main themes (not used currently)
            article_excerpt: Article excerpt (not used currently)

        Returns:
            Dict with url, alt_text, aspect_ratio, cost, success or None if failed
        """
        logger.info("generating_flux_hero_image", topic=topic, raw_mode=True)

        # Generate simple German prompt (will be expanded by Qwen)
        prompt = self._map_tone_to_prompt(
            brand_tone=brand_tone,
            topic=topic,
            is_hero=True,
            domain=domain,
            keywords=keywords,
            themes=themes,
            article_excerpt=article_excerpt
        )

        # Generate with retry (includes Qwen prompt expansion + Flux RAW MODE)
        url = await self._generate_with_retry(
            prompt=prompt,
            aspect_ratio="16:9",
            topic=topic
        )

        if url is None:
            return {"success": False, "cost": 0.0}

        return {
            "success": True,
            "url": url,
            "alt_text": f"Hero image for {topic}",
            "aspect_ratio": "16:9",
            "resolution": "2048x2048",
            "raw_mode": True,
            "cost": self.COST_PER_IMAGE
        }

    async def generate_supporting_image(
        self,
        topic: str,
        brand_tone: List[str],
        aspect: str,
        domain: Optional[str] = None,
        keywords: Optional[str] = None,
        themes: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Generate supporting image with Flux 1.1 Pro Ultra RAW MODE (1:1, 2048x2048, $0.04)

        Args:
            topic: Article topic
            brand_tone: Brand tone descriptors (not used currently)
            aspect: Aspect to illustrate (e.g., 'implementation', 'benefits', 'overview')
            domain: Domain/vertical (not used currently)
            keywords: Key concepts (not used currently)
            themes: Main themes (not used currently)

        Returns:
            Dict with url, alt_text, aspect_ratio, cost or None if failed
        """
        logger.info(
            "generating_flux_supporting_image",
            topic=topic,
            aspect=aspect,
            raw_mode=True
        )

        # Add aspect to topic for more specific prompt
        topic_with_aspect = f"{topic} - {aspect}"

        # Generate simple German prompt (will be expanded by Qwen)
        prompt = self._map_tone_to_prompt(
            brand_tone=brand_tone,
            topic=topic_with_aspect,
            is_hero=False,
            domain=domain,
            keywords=keywords,
            themes=themes
        )

        # Generate with retry (includes Qwen prompt expansion + Flux RAW MODE)
        url = await self._generate_with_retry(
            prompt=prompt,
            aspect_ratio="1:1",
            topic=topic_with_aspect
        )

        if url is None:
            return None

        return {
            "url": url,
            "alt_text": f"Supporting image for {topic} - {aspect}",
            "aspect_ratio": "1:1",
            "resolution": "2048x2048",
            "raw_mode": True,
            "cost": self.COST_PER_IMAGE
        }

    async def generate_supporting_images(
        self,
        article_content: str,
        num_images: int = 2,
        brand_tone: List[str] = None,
        domain: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        themes: Optional[List[str]] = None,
        topic: Optional[str] = None
    ) -> Dict:
        """
        Generate multiple supporting images for an article

        Args:
            article_content: Full article content
            num_images: Number of supporting images to generate (default: 2)
            brand_tone: Brand tone descriptors (not used with simple prompts)
            domain: Domain/vertical (not used with simple prompts)
            keywords: Key concepts (not used with simple prompts)
            themes: Main themes (not used with simple prompts)
            topic: Optional topic override (recommended to avoid markdown parsing issues)

        Returns:
            Dict with:
            - success: bool
            - images: List[Dict] with url, alt_text, size, quality
            - cost: float - Total cost
        """
        if brand_tone is None:
            brand_tone = ["Professional"]

        # Use provided topic or extract from article
        if not topic:
            # Extract topic from article, skipping markdown fences and blank lines
            for line in article_content.split('\n'):
                clean_line = line.strip()
                # Skip markdown code fences, blank lines, and comments
                if clean_line and not clean_line.startswith('```') and not clean_line.startswith('#'):
                    topic = clean_line[:100]
                    break
            if not topic:
                topic = "Article"

        # Extract actual section headings from article content
        aspects = []

        # Step 1: Try H2 headings (##)
        for line in article_content.split('\n'):
            clean_line = line.strip()
            if clean_line.startswith('## ') and not clean_line.startswith('###'):
                heading = clean_line[3:].strip()
                if heading and len(heading) < 150 and not heading.startswith('```'):
                    aspects.append(heading)

        # Step 2: If not enough H2, try H3 headings (###)
        if len(aspects) < num_images:
            for line in article_content.split('\n'):
                clean_line = line.strip()
                if clean_line.startswith('### ') and not clean_line.startswith('####'):
                    heading = clean_line[4:].strip()
                    if heading and len(heading) < 150 and not heading.startswith('```'):
                        if heading not in aspects:  # Avoid duplicates
                            aspects.append(heading)

        # Step 3: If still not enough, extract first sentences from paragraphs
        if len(aspects) < num_images:
            for line in article_content.split('\n'):
                clean_line = line.strip()
                # Skip headings, code fences, and short lines
                if (clean_line and
                    not clean_line.startswith('#') and
                    not clean_line.startswith('```') and
                    not clean_line.startswith('-') and
                    not clean_line.startswith('*') and
                    len(clean_line) > 50):
                    # Take first sentence
                    first_sentence = clean_line.split('.')[0].strip()
                    if len(first_sentence) > 30 and len(first_sentence) < 150:
                        if first_sentence not in aspects:
                            aspects.append(first_sentence)

        # Step 4: Last resort - use topic with different descriptive contexts
        if len(aspects) < num_images:
            contexts = [
                "Überblick",
                "Praktische Anwendung",
                "Detailansicht",
                "Kontext"
            ]
            for i in range(len(aspects), num_images):
                if i < len(contexts):
                    aspects.append(f"{topic} - {contexts[i]}")
                else:
                    aspects.append(topic)

        # Take only the number of images requested
        aspects = aspects[:num_images]

        logger.info(
            "extracted_aspects_for_supporting_images",
            num_aspects=len(aspects),
            aspects=aspects[:5],  # Log first 5 for brevity
            topic=topic[:50]
        )

        # Generate images in parallel
        tasks = [
            self.generate_supporting_image(
                topic=topic,
                brand_tone=brand_tone,
                aspect=aspect,
                domain=domain,
                keywords=keywords,
                themes=themes
            )
            for aspect in aspects
        ]

        results = await asyncio.gather(*tasks)

        # Filter successful results
        images = [r for r in results if r is not None]
        total_cost = sum(img.get("cost", 0) for img in images)

        return {
            "success": len(images) > 0,
            "images": images,
            "cost": total_cost
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
