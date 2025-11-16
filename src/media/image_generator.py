"""
Image Generator - Mixed Flux Models (Ultra for Hero, Dev for Supporting)

Generates ULTRA-CRISP, POLISHED, magazine-quality images with cost optimization:
- Hero: Flux 1.1 Pro Ultra ($0.06) - Premium 4MP, polished, STANDARD MODE
- Supporting: Flux Dev ($0.003) - Good 2MP quality, 95% cheaper
- Enhanced Qwen prompt expansion with professional photography keywords
- German language text in images (UI elements, captions, signs)
- 8-10 second generation time per image
- Balanced safety_tolerance (4) for good diversity without unpredictability

Enhanced STANDARD MODE delivers:
- **Tack-sharp focus** with professional DSLR quality
- **Award-winning composition** (rule of thirds, leading lines, dynamic framing)
- **Dramatic lighting** (golden hour, blue hour, rim lighting, side lighting)
- **Professional post-processing** (color grading, enhanced dynamic range)
- **Cinematic/Editorial style** (magazine-quality, polished, attractive)
- **Crisp, vibrant aesthetic** (NOT dull/candid RAW mode)

Photography keywords automatically included:
- Technical: "Messerscharfe Schärfe", "85mm f/2.8", "shallow depth of field"
- Composition: "Drittel-Regel", "Cinematic framing", "Negative space"
- Lighting: "Dramatisches Licht", "Goldene Stunde", "Rim lighting"
- Quality: "Ultra-detailliert", "Professionelle Farbkorrektur", "Editorial-Stil"

Architecture:
- Content Creator: Generate high-quality 4MP images → Store URLs in Notion
- Publishing System: Your blog/CMS optimizes images when publishing (WebP, responsive sizes, CDN)
- Separation of concerns: Generate quality content, let publishing infrastructure handle optimization

Example:
    from src.media.image_generator import ImageGenerator

    generator = ImageGenerator()  # Uses Replicate API

    # Generate hero image (16:9, ultra-crisp, polished, attractive)
    # Returns Replicate URL - your publishing system will optimize when serving
    hero = await generator.generate_hero_image(
        topic="Versicherungsschäden",
        brand_tone=["Professional"]
    )
"""

import os
import asyncio
import re
from typing import List, Optional, Dict
from openai import AsyncOpenAI
import replicate
import httpx

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ImageGenerationError(Exception):
    """Raised when image generation fails after retries"""
    pass


class ImageGenerator:
    """
    Image generator using MIXED Flux models for cost optimization

    Enhanced Features (Session 048):
    - Hero images: Flux 1.1 Pro Ultra STANDARD MODE ($0.06, 4MP premium quality)
    - Supporting images: Flux Dev ($0.003, 2MP good quality, 95% cheaper)
    - Safety_tolerance: 4 (good diversity, professional predictability)
    - German language specification for text in images
    - Professional photography prompt expansion with Qwen:
      * Technical quality: Tack-sharp focus, DSLR specs, depth of field
      * Composition: Rule of thirds, leading lines, cinematic framing
      * Lighting: Dramatic natural light, golden/blue hour, rim lighting
      * Post-processing: Color grading, enhanced dynamic range, film grain
      * Artistic style: Editorial/magazine quality, award-winning composition
    - High resolution: Up to 4MP (hero), ~2MP (supporting)
    - Fast generation: 8-10 seconds per image

    Cost per article (dynamic):
    - Short (1-3 sections): Hero only = $0.07 total
    - Medium (4-5 sections): Hero + 1 Dev = $0.073 total
    - Long (6+ sections): Hero + 2 Dev = $0.076 total

    Result: Premium hero + good supporting images, 60% cost savings vs all-Ultra
    """

    # Flux model costs (Replicate official pricing, Session 048)
    COST_ULTRA = 0.06   # Flux 1.1 Pro Ultra (hero images)
    COST_DEV = 0.003    # Flux Dev (supporting images, 95% cheaper)

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

        # Load Chutes.ai API key for model comparison
        self.chutes_key = self._load_chutes_key()
        if not self.chutes_key:
            logger.warning("CHUTES_API_KEY not found, chutes.ai models will not be available")
            self.chutes_client = None
        else:
            # Initialize HTTP client for chutes.ai
            self.chutes_client = httpx.AsyncClient(
                base_url="https://chutes.ai",
                headers={
                    "Authorization": f"Bearer {self.chutes_key}",
                    "Content-Type": "application/json"
                },
                timeout=60.0
            )

        logger.info(
            "image_generator_initialized",
            provider="flux-1.1-pro-ultra-standard",
            has_replicate_key=bool(self.replicate_key),
            has_openrouter_key=bool(self.openrouter_key),
            has_chutes_key=bool(self.chutes_key)
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

    def _load_chutes_key(self) -> Optional[str]:
        """Load Chutes.ai API key from environment"""
        # Check environment variable
        api_key = os.getenv("CHUTES_API_KEY")
        if api_key:
            return api_key

        # Check /home/envs/choutes.env
        env_file = "/home/envs/choutes.env"
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() == 'CHUTES_API_KEY':
                                logger.info("chutes_key_loaded_from_file", file=env_file)
                                return value.strip()
            except Exception as e:
                logger.warning("failed_to_load_chutes_key", error=str(e))

        return None

    def _create_slug(self, topic: str) -> str:
        """
        Create URL-safe slug from topic.

        Args:
            topic: Article topic (e.g., "Laktoseintoleranz und Laktase")

        Returns:
            Lowercase slug with hyphens (e.g., "laktoseintoleranz-und-laktase")
        """
        # Convert to lowercase
        slug = topic.lower()

        # Replace umlauts and special characters
        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
            'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a',
            'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
            'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
            'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o',
            'ù': 'u', 'ú': 'u', 'û': 'u',
            'ñ': 'n', 'ç': 'c'
        }
        for char, replacement in replacements.items():
            slug = slug.replace(char, replacement)

        # Remove all non-alphanumeric characters except spaces and hyphens
        slug = re.sub(r'[^\w\s-]', '', slug)

        # Replace spaces with hyphens
        slug = re.sub(r'[\s_]+', '-', slug)

        # Remove consecutive hyphens
        slug = re.sub(r'-+', '-', slug)

        # Strip leading/trailing hyphens
        slug = slug.strip('-')

        return slug

    async def _download_and_upload_to_s3(
        self,
        url: str,
        topic: str,
        image_type: str,
        suffix: str = ""
    ) -> Optional[str]:
        """
        Download image from URL and upload to S3.

        Args:
            url: Source URL (e.g., Replicate CDN)
            topic: Article topic for folder structure
            image_type: Type of image (hero, supporting, platform)
            suffix: Optional suffix for filename (e.g., hash for supporting images)

        Returns:
            S3 public URL or None if upload failed
        """
        try:
            from .s3_uploader import get_s3_uploader
            import base64

            # Download image from URL
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                image_bytes = response.content

            # Detect content type from response headers
            content_type = response.headers.get('content-type', 'image/png')

            # Create structured path: {user_id}/{article-slug}/{type}/{filename}
            article_slug = self._create_slug(topic)
            user_id = "default"  # Single-user MVP, will be user_id in SaaS

            # Determine file extension
            ext = '.png' if 'png' in content_type else '.jpg'

            # Create filename based on type
            if image_type == "hero":
                filename = f"{user_id}/{article_slug}/hero{ext}"
            elif image_type == "supporting":
                filename = f"{user_id}/{article_slug}/supporting/{suffix}{ext}"
            elif image_type == "platform":
                filename = f"{user_id}/{article_slug}/platform/{suffix}{ext}"
            else:
                filename = f"{user_id}/{article_slug}/{image_type}/{suffix}{ext}"

            # Convert to base64 for uploader
            b64_data = base64.b64encode(image_bytes).decode('utf-8')
            data_url = f"data:{content_type};base64,{b64_data}"

            # Upload to B2
            uploader = get_s3_uploader()
            public_url = uploader.upload_base64_image(
                data_url,
                filename=filename,
                content_type=content_type
            )

            logger.info(
                "image_uploaded_to_s3",
                image_type=image_type,
                original_url=url[:100],
                s3_url=public_url,
                path=filename,
                size=len(image_bytes)
            )

            return public_url

        except Exception as e:
            logger.error(
                "s3_upload_failed_using_replicate_url",
                image_type=image_type,
                error=str(e),
                original_url=url[:100]
            )
            # Fallback to original URL if S3 upload fails
            return url

    async def _expand_prompt_with_llm(
        self,
        simple_prompt: str,
        topic: str,
        content_language: str = "de"
    ) -> str:
        """
        Expand simple prompt into detailed professional photography prompt using Qwen.

        Uses English instructions + target language parameter (industry best practice).
        This approach works for any language without maintaining N translations.

        Args:
            simple_prompt: Simple prompt like "Ein Bild über Versicherungsschäden"
            topic: Original topic
            content_language: ISO 639-1 code (de, en, es, fr, etc.)

        Returns:
            Expanded, detailed prompt in target language
        """
        # If OpenRouter not available, return simple prompt
        if not self.openrouter_client:
            logger.warning("OpenRouter not configured, using simple prompt")
            return simple_prompt

        # Qwen expansion: Always use English for best Flux quality
        # Flux is trained primarily on English - better quality and adherence

        # Map content language for text-in-image specification
        language_map = {'de': 'German', 'en': 'English', 'es': 'Spanish', 'fr': 'French'}
        target_language = language_map.get(content_language, 'German')

        expansion_prompt = f"""You are an expert in Flux 1.1 Pro Ultra prompt engineering. Create a natural language photography prompt following Flux best practices.

**INPUT**:
Simple prompt: "{simple_prompt}"
Topic: {topic}

**IMPORTANT FLUX BEST PRACTICES**:

1. **Natural Language Structure** (Subject → Background → Lighting → Camera Settings):
   - Start with the MAIN SUBJECT (front-load most important elements)
   - Add background/environment
   - Describe lighting conditions
   - End with camera/lens specs

2. **Use Specific Camera Equipment**:
   - Real cameras: "shot on Canon EOS R5", "captured with Sony A7R IV", "photographed on Nikon Z9"
   - Specific lenses: "85mm f/1.8", "50mm f/1.4", "24-70mm f/2.8"
   - Real settings: "f/2.8, ISO 400, 1/250s"

3. **CRITICAL - Photorealistic Humans** (when people are in the image):
   - ALWAYS include "photorealistic portrait" or "real person photographed"
   - Specify natural skin texture, realistic facial features
   - NEVER use words that suggest artificiality (3D, CGI, render, illustration, plastic, synthetic, mannequin)
   - Use portrait photography terms: "natural skin tones", "authentic expression", "documentary portrait style"

4. **Active, Natural Language**:
   - Use action and movement words
   - Write as if describing to a human photographer
   - Avoid keyword stacking

5. **Keep It Concise** (40-60 words):
   - Flux works best with focused, clear descriptions
   - Don't over-describe
   - One main style anchor only

6. **If text is visible** (screens, signs, UI, documents, papers, letters, forms, certificates): specify "{target_language} text" or "{target_language} document"
   - Examples: "{target_language} document in hand", "{target_language} text on screen", "{target_language} sign in background"

**EXAMPLE OUTPUTS** (Note the natural flow):

1. "Close-up of water-damaged hardwood flooring showing warped planks and discoloration, captured in natural window light from the side creating dramatic shadows, shot on Canon EOS R5 with 50mm f/2.8 lens, sharp focus on wood grain texture, documentary editorial style"

2. "Photorealistic portrait of professional property manager consulting with tenant at modern office desk, natural skin tones and authentic expressions, natural golden hour sunlight streaming through window, captured with Sony A7R IV using 85mm f/1.8 lens for shallow depth of field, documentary portrait style"

3. "Modern smart home dashboard displaying on tablet screen with {target_language} interface, placed on minimalist desk in bright natural daylight, photographed with Nikon Z9 macro lens at f/4, clean composition with soft bokeh background"

4. "Real person photographed reviewing a {target_language} document in hand with natural skin texture and realistic facial features, standing near bright office window with soft natural daylight, shot on Canon EOS R6 with 50mm f/2.0 lens creating shallow depth of field on the paper, authentic documentary portrait style"

**YOUR TASK**:
Create ONE concise prompt (40-60 words) following this structure:
[Subject with action/state] → [Environment/background] → [Lighting description] → [Camera: specific model + lens + settings] → [One style anchor]

**CRITICAL REMINDER**: If the image includes PEOPLE, you MUST:
- Include "photorealistic portrait" or "real person photographed" in the prompt
- Add "natural skin tones", "realistic facial features", or "authentic expression"
- Use "documentary portrait style" or similar authentic photography descriptor
- NEVER use: 3D, CGI, render, illustration, plastic, synthetic, mannequin, artificial

Output ONLY the prompt in English, no explanations or quotes."""

        try:
            # Use Qwen via OpenRouter for prompt expansion (cheap and fast)
            # Add 30s timeout to prevent hanging when OpenRouter is overloaded
            import asyncio

            logger.info(
                "qwen_expansion_started",
                topic=topic,
                simple_prompt_length=len(simple_prompt)
            )

            response = await asyncio.wait_for(
                self.openrouter_client.chat.completions.create(
                    model="qwen/qwen-2.5-72b-instruct",  # Fast and cheap via OpenRouter
                    messages=[
                        {"role": "user", "content": expansion_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=150,  # Reduced from 200 for more concise 40-60 word prompts
                    extra_headers={
                        "HTTP-Referer": "https://github.com/content-creator",
                        "X-Title": "Content Creator - Image Prompt Expansion"
                    }
                ),
                timeout=30.0  # 30 second timeout
            )

            expanded = response.choices[0].message.content.strip()

            # Remove quotes if LLM wrapped it
            if expanded.startswith('"') and expanded.endswith('"'):
                expanded = expanded[1:-1]

            logger.info(
                "qwen_expansion_success",
                original_length=len(simple_prompt),
                expanded_length=len(expanded),
                topic=topic,
                expanded_preview=expanded[:100]
            )

            return expanded

        except asyncio.TimeoutError:
            logger.warning(
                "qwen_expansion_timeout",
                topic=topic,
                message="Qwen expansion timed out after 30s, using simple fallback prompt"
            )
            return simple_prompt
        except Exception as e:
            logger.warning(
                "qwen_expansion_failed",
                topic=topic,
                error=str(e),
                error_type=type(e).__name__,
                message="Using simple fallback prompt"
            )
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
        Generate simple English prompt (will be expanded later with Qwen → German)

        Args:
            brand_tone: List of tone descriptors (not used - kept for compatibility)
            topic: Article topic
            is_hero: True for hero image, False for supporting
            domain: Domain/vertical (not used - kept for compatibility)
            keywords: Key concepts (not used - kept for compatibility)
            themes: Main themes (not used - kept for compatibility)
            article_excerpt: Article excerpt (not used)

        Returns:
            Simple professional prompt in English (Flux works best with English)
        """
        # Simple English prompt with professional photography keywords
        # Flux is trained on English - better quality than German prompts
        # Qwen expansion will translate to German when OpenRouter works
        prompt = f"Professional photograph about {topic}, photorealistic, magazine quality, sharp focus, natural lighting, suitable for blog article header"

        logger.info(
            "simple_english_prompt_created",
            topic=topic,
            is_hero=is_hero,
            prompt_length=len(prompt)
        )

        return prompt

    async def _generate_with_retry(
        self,
        prompt: str,
        aspect_ratio: str,
        topic: str,
        use_dev_model: bool = False
    ) -> Optional[str]:
        """
        Generate image with retry logic using Flux (Ultra for hero, Dev for supporting)

        Args:
            prompt: Simple base prompt
            aspect_ratio: Image aspect ratio (16:9 for hero, 1:1 for supporting)
            topic: Topic for prompt expansion
            use_dev_model: If True, use Flux Dev ($0.003) instead of Ultra ($0.06)

        Returns:
            Image URL (Replicate-hosted) or None if all retries failed
        """
        # CRITICAL: Expand prompt with Qwen (like ChatGPT does!)
        expanded_prompt = await self._expand_prompt_with_llm(prompt, topic)

        # Select model and parameters
        if use_dev_model:
            model_name = "black-forest-labs/flux-dev"
            model_label = "flux-dev"
            cost = self.COST_DEV
            # Flux Dev doesn't support safety_tolerance or raw parameters
            model_input = {
                "prompt": expanded_prompt,
                "aspect_ratio": aspect_ratio,
                "output_format": "png"
            }
        else:
            model_name = "black-forest-labs/flux-1.1-pro-ultra"
            model_label = "flux-1.1-pro-ultra-standard"
            cost = self.COST_ULTRA
            model_input = {
                "prompt": expanded_prompt,
                "aspect_ratio": aspect_ratio,
                "output_format": "png",
                "output_quality": 90,  # Higher quality output (80-100, default 80)
                "safety_tolerance": 4,  # Good diversity without unpredictability
                "raw": False  # Standard mode = polished, crisp, attractive
            }

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(
                    "flux_generation_attempt",
                    attempt=attempt,
                    aspect_ratio=aspect_ratio,
                    model=model_label,
                    cost=cost,
                    safety_tolerance=model_input.get("safety_tolerance"),
                    raw_mode=model_input.get("raw"),
                    full_prompt=expanded_prompt  # Log full prompt for debugging
                )

                # Run Flux model
                output = await asyncio.to_thread(
                    self.client.run,
                    model_name,
                    input=model_input
                )

                # Flux returns a FileOutput object (or list of FileOutput objects) with .url attribute
                # Handle both single object and list cases
                if isinstance(output, list) and len(output) > 0:
                    file_output = output[0]  # Take first image from list
                else:
                    file_output = output

                url = file_output.url if hasattr(file_output, 'url') else str(file_output)

                logger.info(
                    "flux_generation_success",
                    attempt=attempt,
                    model=model_label,
                    url_length=len(url)
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

    async def _generate_with_chutes(
        self,
        prompt: str,
        model_slug: str,
        model_name: str,
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 20,
        guidance_scale: float = 7.5,
        negative_prompt: str = ""
    ) -> Optional[bytes]:
        """
        Generate image using chutes.ai diffusion model

        Args:
            prompt: Expanded prompt
            model_slug: Chutes model slug (e.g., 'chutes-qwen-image')
            model_name: Display name for logging
            width: Image width
            height: Image height
            num_inference_steps: Number of inference steps
            guidance_scale: How closely to follow the prompt (1.0-20.0, default 7.5)
            negative_prompt: What to avoid in the image

        Returns:
            Image bytes or None if failed
        """
        if not self.chutes_client:
            logger.warning("chutes_client_not_initialized")
            return None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.info(
                    "chutes_generation_attempt",
                    attempt=attempt,
                    model=model_name,
                    slug=model_slug,
                    width=width,
                    height=height,
                    steps=num_inference_steps
                )

                # Generate image
                payload = {
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_inference_steps": num_inference_steps,
                    "guidance_scale": guidance_scale
                }

                # Add negative prompt if provided
                if negative_prompt:
                    payload["negative_prompt"] = negative_prompt

                response = await self.chutes_client.post(
                    f"https://{model_slug}.chutes.ai/generate",
                    json=payload,
                    timeout=60.0
                )

                if response.status_code == 200:
                    logger.info(
                        "chutes_generation_success",
                        attempt=attempt,
                        model=model_name,
                        content_length=len(response.content)
                    )
                    return response.content
                else:
                    logger.warning(
                        "chutes_generation_http_error",
                        attempt=attempt,
                        status_code=response.status_code,
                        error=response.text[:200]
                    )

                    # Retry on rate limiting or infrastructure issues
                    if response.status_code in [429, 503]:
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(self.RETRY_DELAY * 2)  # Longer delay for infra issues
                            continue
                    return None

            except Exception as e:
                logger.warning(
                    "chutes_generation_attempt_failed",
                    attempt=attempt,
                    error=str(e),
                    error_type=type(e).__name__
                )

                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    logger.error(
                        "chutes_generation_failed",
                        max_retries=self.MAX_RETRIES,
                        model=model_name,
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

        # Generate with retry (includes Qwen prompt expansion + Flux)
        replicate_url = await self._generate_with_retry(
            prompt=prompt,
            aspect_ratio="16:9",
            topic=topic
        )

        if replicate_url is None:
            return {"success": False, "cost": 0.0}

        # Upload to S3 for permanent storage
        s3_url = await self._download_and_upload_to_s3(
            url=replicate_url,
            topic=topic,
            image_type="hero"
        )

        return {
            "success": True,
            "url": s3_url,  # S3 URL instead of Replicate URL
            "alt_text": f"Hero image for {topic}",
            "aspect_ratio": "16:9",
            "resolution": "2048x2048 (up to 4MP)",
            "model": "Flux 1.1 Pro Ultra",
            "cost": self.COST_ULTRA
        }

    async def generate_supporting_image(
        self,
        topic: str,
        brand_tone: List[str],
        aspect: str,
        domain: Optional[str] = None,
        keywords: Optional[str] = None,
        themes: Optional[List[str]] = None,
        aspect_ratio: str = "1:1"
    ) -> Optional[Dict]:
        """
        Generate supporting image with Flux Dev (~2MP, $0.003)

        Uses budget Flux Dev model for supporting images (95% cheaper than Ultra).
        Quality is still good, just not premium 4MP like hero images.

        Args:
            topic: Article topic
            brand_tone: Brand tone descriptors (not used currently)
            aspect: Aspect to illustrate (e.g., 'implementation', 'benefits', 'overview')
            domain: Domain/vertical (not used currently)
            keywords: Key concepts (not used currently)
            themes: Main themes (not used currently)
            aspect_ratio: Image aspect ratio (1:1 for Instagram, 9:16 for TikTok, default: 1:1)

        Returns:
            Dict with url, alt_text, aspect_ratio, cost or None if failed
        """
        logger.info(
            "generating_flux_supporting_image",
            topic=topic,
            aspect=aspect,
            aspect_ratio=aspect_ratio,
            model="flux-dev"
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

        # Generate with retry (includes Qwen prompt expansion + Flux Dev)
        replicate_url = await self._generate_with_retry(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            topic=topic_with_aspect,
            use_dev_model=True  # Use budget model for supporting images
        )

        if replicate_url is None:
            return None

        # Upload to S3 for permanent storage
        # Use aspect as suffix to distinguish multiple supporting images
        import hashlib
        aspect_hash = hashlib.sha256(aspect.encode()).hexdigest()[:8]
        s3_url = await self._download_and_upload_to_s3(
            url=replicate_url,
            topic=topic,
            image_type="supporting",
            suffix=f"{aspect_hash}"
        )

        # Calculate resolution based on aspect ratio
        if aspect_ratio == "1:1":
            resolution = "~2048x2048 (~2MP)"
        elif aspect_ratio == "9:16":
            resolution = "~1080x1920 (~2MP)"
        else:
            resolution = f"~2MP ({aspect_ratio})"

        return {
            "url": s3_url,  # S3 URL instead of Replicate URL
            "alt_text": f"Supporting image for {topic} - {aspect}",
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "model": "Flux Dev",
            "cost": self.COST_DEV
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

    async def generate_chutes_comparison_images(
        self,
        prompt: str,
        topic: str
    ) -> List[Dict]:
        """
        Generate comparison images using optimized chutes.ai models

        Models (optimized for photorealistic quality):
        - JuggernautXL ($0.20/hr, 25 steps) - Photorealistic, cinematic
        - qwen-image ($0.6/hr, 35 steps) - High quality, detailed

        Optimizations:
        - Enhanced prompt with professional photography keywords
        - Negative prompt to avoid common issues (blur, cartoon, text)
        - Higher guidance_scale for better prompt adherence (7.5-8.0)
        - More inference steps (25-35 vs 10-20)

        Args:
            prompt: Simple prompt (will be expanded with Qwen)
            topic: Topic for prompt expansion

        Returns:
            List of dicts with url (base64 data URL), alt_text, model, cost
        """
        if not self.chutes_client:
            logger.warning("chutes_comparison_skipped_no_client")
            return []

        # Expand prompt with Qwen first (same as Flux pipeline)
        expanded_prompt = await self._expand_prompt_with_llm(prompt, topic)

        # Enhanced prompt for photorealistic quality
        # Add professional photography keywords for better results
        enhanced_prompt = f"{expanded_prompt}, professional photography, high detail, sharp focus, realistic lighting, cinematic composition"

        # Negative prompt to avoid common issues
        negative_prompt = "blurry, low quality, cartoon, anime, illustration, painting, drawing, sketch, out of focus, distorted, deformed, ugly, bad anatomy, text, watermark, signature"

        # Define comparison models (optimized based on testing)
        models = [
            {
                "slug": "chutes-juggernautxl",
                "name": "JuggernautXL",
                "label": "Photorealistic (JuggernautXL)",
                "cost": 0.001,  # per step
                "steps": 25,  # More steps for quality
                "guidance_scale": 7.5,  # Standard guidance
                "negative_prompt": negative_prompt
            },
            {
                "slug": "chutes-qwen-image",
                "name": "qwen-image",
                "label": "Quality (qwen-image)",
                "cost": 0.003,  # per step
                "steps": 35,  # Increased from 20 for better quality
                "guidance_scale": 8.0,  # Slightly higher for more prompt adherence
                "negative_prompt": negative_prompt
            }
        ]

        logger.info(
            "chutes_comparison_started",
            num_models=len(models),
            expanded_prompt_length=len(expanded_prompt)
        )

        # Generate images in parallel
        tasks = []
        for model in models:
            tasks.append(
                self._generate_with_chutes(
                    prompt=enhanced_prompt,
                    model_slug=model["slug"],
                    model_name=model["name"],
                    width=1024,
                    height=1024,
                    num_inference_steps=model["steps"],
                    guidance_scale=model.get("guidance_scale", 7.5),
                    negative_prompt=model.get("negative_prompt", "")
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        comparison_images = []
        # Create structured path: default/{article-slug}/comparison/{model}_{hash}.jpg
        article_slug = self._create_slug(topic)
        user_id = "default"  # Single-user MVP, will be user_id in SaaS

        for model, result in zip(models, results):
            if isinstance(result, bytes):
                # Upload to B2 instead of storing base64
                try:
                    from .s3_uploader import get_s3_uploader
                    import base64
                    import hashlib

                    # Create unique filename from content hash
                    content_hash = hashlib.sha256(result).hexdigest()[:16]
                    filename = f"{user_id}/{article_slug}/comparison/{model['name'].lower()}_{content_hash}.jpg"

                    # Convert bytes to base64 for uploader
                    b64_data = base64.b64encode(result).decode('utf-8')
                    data_url = f"data:image/jpeg;base64,{b64_data}"

                    # Upload to B2
                    uploader = get_s3_uploader()
                    public_url = uploader.upload_base64_image(
                        data_url,
                        filename=filename,
                        content_type="image/jpeg"
                    )

                    logger.info(
                        "chutes_model_uploaded_to_b2",
                        model=model["name"],
                        url=public_url,
                        path=filename,
                        size=len(result)
                    )

                    # Use B2 public URL instead of base64
                    final_url = public_url

                except Exception as upload_error:
                    # Fallback to base64 if B2 upload fails
                    logger.warning(
                        "chutes_b2_upload_failed_using_base64",
                        model=model["name"],
                        error=str(upload_error)
                    )
                    import base64
                    b64_data = base64.b64encode(result).decode('utf-8')
                    final_url = f"data:image/jpeg;base64,{b64_data}"

                comparison_images.append({
                    "success": True,
                    "url": final_url,
                    "alt_text": f"{topic} - {model['label']}",
                    "model": model["name"],
                    "label": model["label"],
                    "cost": model["cost"] * model["steps"],
                    "provider": "chutes.ai"
                })
                logger.info(
                    "chutes_model_success",
                    model=model["name"],
                    cost=model["cost"] * model["steps"]
                )
            else:
                logger.warning(
                    "chutes_model_failed",
                    model=model["name"],
                    error=str(result) if isinstance(result, Exception) else "Unknown error"
                )
                comparison_images.append({
                    "success": False,
                    "model": model["name"],
                    "label": model["label"],
                    "cost": 0.0
                })

        return comparison_images


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
