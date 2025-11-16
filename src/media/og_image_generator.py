"""
Open Graph Image Generator using Pillow

Generates customizable OG images (1200x630 PNG) with 4 templates:
- Minimal: Solid background + text
- Gradient: Linear gradient + text
- Photo: Background image + overlay + text
- Split: Split layout (image left, text right)

Features:
- Font registry with caching
- Text wrapping (2-line title, 3-line excerpt)
- WCAG contrast validation (4.5:1)
- File size optimization (<300KB)
- Zero AI cost (Pillow-based)

Usage:
    generator = OGImageGenerator()
    img_bytes = generator.generate(
        title="Blog Post Title",
        excerpt="Brief excerpt...",
        template="minimal",  # minimal, gradient, photo, split
        brand_color="#1a73e8"
    )

    # Save to file
    with open("og_image.png", "wb") as f:
        f.write(img_bytes)
"""

import io
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import hashlib

logger = logging.getLogger(__name__)


class FontRegistry:
    """
    Manages fonts with caching for Pillow

    Features:
    - Auto-load system fonts (Roboto, Arial, Helvetica)
    - Fallback to bundled fonts (src/media/fonts/)
    - Cache loaded fonts (avoid re-loading)
    - Support bold, regular, italic
    """

    def __init__(self):
        """Initialize font registry"""
        self.cache: Dict[str, ImageFont.FreeTypeFont] = {}
        self.font_paths: List[Path] = self._find_fonts()

        logger.info(
            f"font_registry_initialized",
            num_fonts=len(self.font_paths),
            fonts=[p.name for p in self.font_paths[:5]]
        )

    def _find_fonts(self) -> List[Path]:
        """
        Find available fonts on system

        Priority:
        1. System fonts: /usr/share/fonts/truetype/roboto/
        2. Bundled fonts: src/media/fonts/
        3. Common system fonts: /usr/share/fonts/

        Returns:
            List of font file paths
        """
        font_paths = []

        # Priority 1: System Roboto fonts
        system_roboto = Path("/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF")
        if system_roboto.exists():
            font_paths.extend(system_roboto.glob("*.ttf"))

        # Priority 2: Bundled fonts
        bundled_fonts = Path(__file__).parent / "fonts"
        if bundled_fonts.exists():
            font_paths.extend(bundled_fonts.glob("*.ttf"))

        # Priority 3: Common system fonts
        common_paths = [
            Path("/usr/share/fonts/truetype/dejavu"),
            Path("/usr/share/fonts/truetype/liberation"),
            Path("/usr/share/fonts/TTF"),  # Arch Linux
        ]
        for path in common_paths:
            if path.exists():
                font_paths.extend(path.glob("*.ttf"))

        return list(set(font_paths))  # Remove duplicates

    def get_font(self, size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
        """
        Get cached font instance

        Args:
            size: Font size in pixels
            weight: bold, regular, italic

        Returns:
            PIL ImageFont instance
        """
        # Create cache key
        cache_key = f"{size}-{weight}"

        # Return cached font if exists
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Find appropriate font file
        font_file = self._find_font_file(weight)

        try:
            if font_file:
                font = ImageFont.truetype(str(font_file), size)
            else:
                # Fallback to default font
                logger.warning(f"No TrueType font found for weight={weight}, using default")
                font = ImageFont.load_default()

            # Cache font
            self.cache[cache_key] = font
            return font

        except Exception as e:
            logger.error(f"Failed to load font: {e}")
            # Return default font
            font = ImageFont.load_default()
            self.cache[cache_key] = font
            return font

    def _find_font_file(self, weight: str) -> Optional[Path]:
        """
        Find font file matching weight

        Args:
            weight: bold, regular, italic

        Returns:
            Path to font file or None
        """
        weight_lower = weight.lower()

        # Search for exact match first
        for font_path in self.font_paths:
            font_name_lower = font_path.name.lower()

            if weight_lower == "bold" and "bold" in font_name_lower and "italic" not in font_name_lower:
                return font_path
            elif weight_lower == "regular" and "regular" in font_name_lower:
                return font_path
            elif weight_lower == "italic" and "italic" in font_name_lower:
                return font_path

        # Fallback: any font with the weight keyword
        for font_path in self.font_paths:
            if weight_lower in font_path.name.lower():
                return font_path

        # Last resort: return first available font
        return self.font_paths[0] if self.font_paths else None


def calculate_luminance(hex_color: str) -> float:
    """
    Calculate relative luminance of a color (WCAG formula)

    Args:
        hex_color: Hex color (with or without #)

    Returns:
        Luminance value (0.0-1.0)
    """
    # Remove # if present
    hex_color = hex_color.lstrip("#")

    # Parse RGB
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    # Apply sRGB gamma correction
    def gamma_correct(channel):
        if channel <= 0.03928:
            return channel / 12.92
        else:
            return ((channel + 0.055) / 1.055) ** 2.4

    r = gamma_correct(r)
    g = gamma_correct(g)
    b = gamma_correct(b)

    # Calculate luminance
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b

    return luminance


def validate_contrast(
    foreground_color: str,
    background_color: str,
    min_ratio: float = 4.5
) -> bool:
    """
    Validate WCAG AA contrast ratio (4.5:1 for normal text)

    Args:
        foreground_color: Hex color (with or without #)
        background_color: Hex color (with or without #)
        min_ratio: Minimum contrast ratio (default: 4.5 for WCAG AA)

    Returns:
        True if contrast is sufficient
    """
    # Calculate luminance for both colors
    l1 = calculate_luminance(foreground_color)
    l2 = calculate_luminance(background_color)

    # Ensure l1 is the lighter color
    if l1 < l2:
        l1, l2 = l2, l1

    # Calculate contrast ratio
    contrast_ratio = (l1 + 0.05) / (l2 + 0.05)

    return contrast_ratio >= min_ratio


def wrap_text(
    text: str,
    max_width: int,
    font: ImageFont.FreeTypeFont,
    max_lines: int = 2
) -> List[str]:
    """
    Wrap text to fit within max_width

    Algorithm:
    1. Split text into words
    2. Measure each word's pixel width
    3. Group words into lines (greedy fit)
    4. Limit to max_lines
    5. Add "..." if truncated

    Args:
        text: Text to wrap
        max_width: Maximum width in pixels
        font: PIL ImageFont for measuring
        max_lines: Maximum number of lines

    Returns:
        List of wrapped lines
    """
    if not text or not text.strip():
        return [""] if not text else []

    # Split into words
    words = text.split()

    lines = []
    current_line = []

    for word in words:
        # Try adding word to current line
        test_line = " ".join(current_line + [word])

        # Measure width using getbbox (modern Pillow API)
        try:
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
        except AttributeError:
            # Fallback for older Pillow versions
            text_width = font.getsize(test_line)[0]

        if text_width <= max_width:
            # Fits, add to current line
            current_line.append(word)
        else:
            # Doesn't fit, start new line
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                # Single word exceeds max_width, keep it anyway
                lines.append(word)
                current_line = []

            # Check if we've reached max_lines
            if len(lines) >= max_lines:
                break

    # Add remaining words (if any and not exceeded max_lines)
    if current_line and len(lines) < max_lines:
        lines.append(" ".join(current_line))

    # Truncate if exceeded max_lines and add ellipsis
    if len(words) > sum(len(line.split()) for line in lines):
        if lines:
            lines[-1] = lines[-1].rstrip() + "..."

    # Limit to max_lines
    lines = lines[:max_lines]

    return lines


class MinimalTemplate:
    """
    Minimal template: Solid background + text

    Layout:
    - Solid color background (brand_color)
    - Logo (top-left)
    - Title (2 lines max, bold, 72px)
    - Excerpt (3 lines max, regular, 36px)
    - White text (auto-adjusted for contrast)
    """

    def __init__(self):
        """Initialize minimal template"""
        self.font_registry = FontRegistry()

    def render(
        self,
        title: str,
        excerpt: str,
        brand_color: str,
        logo: Optional[Image.Image] = None
    ) -> Image.Image:
        """
        Render minimal template

        Args:
            title: Blog post title
            excerpt: Blog post excerpt
            brand_color: Brand color (hex)
            logo: Optional logo image

        Returns:
            PIL Image (1200x630)
        """
        # Create canvas
        img = Image.new("RGB", (1200, 630), color=self._hex_to_rgb(brand_color))
        draw = ImageDraw.Draw(img)

        # Validate text color (white or black based on contrast)
        text_color = "#FFFFFF"
        if not validate_contrast(text_color, brand_color, min_ratio=4.5):
            text_color = "#000000"

        # Add logo (if provided)
        y_offset = 80
        if logo:
            logo_resized = self._resize_logo(logo, max_width=250, max_height=100)
            img.paste(logo_resized, (80, y_offset), logo_resized if logo_resized.mode == "RGBA" else None)
            y_offset += 140

        # Load fonts
        title_font = self.font_registry.get_font(size=72, weight="bold")
        excerpt_font = self.font_registry.get_font(size=36, weight="regular")

        # Wrap title (2 lines max)
        title_lines = wrap_text(title, max_width=1040, font=title_font, max_lines=2)

        # Draw title
        for line in title_lines:
            draw.text((80, y_offset), line, font=title_font, fill=text_color)
            y_offset += 90

        # Add spacing
        y_offset += 30

        # Wrap excerpt (3 lines max)
        excerpt_lines = wrap_text(excerpt, max_width=1040, font=excerpt_font, max_lines=3)

        # Draw excerpt
        for line in excerpt_lines:
            draw.text((80, y_offset), line, font=excerpt_font, fill=text_color)
            y_offset += 50

        return img

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _resize_logo(self, logo: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """Resize logo to fit within max dimensions"""
        logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return logo


class GradientTemplate:
    """
    Gradient template: Linear gradient + text

    Layout:
    - Linear gradient background (brand_color to darker)
    - Logo (top-left)
    - Title (2 lines max, bold, 72px)
    - Excerpt (3 lines max, regular, 36px)
    - White text
    """

    def __init__(self):
        """Initialize gradient template"""
        self.font_registry = FontRegistry()

    def render(
        self,
        title: str,
        excerpt: str,
        brand_color: str,
        logo: Optional[Image.Image] = None
    ) -> Image.Image:
        """
        Render gradient template

        Args:
            title: Blog post title
            excerpt: Blog post excerpt
            brand_color: Brand color (hex)
            logo: Optional logo image

        Returns:
            PIL Image (1200x630)
        """
        # Create gradient background
        img = self._create_gradient(brand_color)
        draw = ImageDraw.Draw(img)

        # Use white text (gradients are dark enough)
        text_color = "#FFFFFF"

        # Add logo (if provided)
        y_offset = 80
        if logo:
            logo_resized = self._resize_logo(logo, max_width=250, max_height=100)
            img.paste(logo_resized, (80, y_offset), logo_resized if logo_resized.mode == "RGBA" else None)
            y_offset += 140

        # Load fonts
        title_font = self.font_registry.get_font(size=72, weight="bold")
        excerpt_font = self.font_registry.get_font(size=36, weight="regular")

        # Wrap and draw title
        title_lines = wrap_text(title, max_width=1040, font=title_font, max_lines=2)
        for line in title_lines:
            draw.text((80, y_offset), line, font=title_font, fill=text_color)
            y_offset += 90

        y_offset += 30

        # Wrap and draw excerpt
        excerpt_lines = wrap_text(excerpt, max_width=1040, font=excerpt_font, max_lines=3)
        for line in excerpt_lines:
            draw.text((80, y_offset), line, font=excerpt_font, fill=text_color)
            y_offset += 50

        return img

    def _create_gradient(self, brand_color: str) -> Image.Image:
        """Create linear gradient from brand_color to darker shade"""
        # Parse brand color
        hex_color = brand_color.lstrip("#")
        r1 = int(hex_color[0:2], 16)
        g1 = int(hex_color[2:4], 16)
        b1 = int(hex_color[4:6], 16)

        # Create darker shade (60% brightness)
        r2 = int(r1 * 0.6)
        g2 = int(g1 * 0.6)
        b2 = int(b1 * 0.6)

        # Create gradient
        img = Image.new("RGB", (1200, 630))
        draw = ImageDraw.Draw(img)

        # Draw gradient line by line
        for y in range(630):
            # Calculate interpolation factor (0.0 at top, 1.0 at bottom)
            factor = y / 630.0

            # Interpolate colors
            r = int(r1 + (r2 - r1) * factor)
            g = int(g1 + (g2 - g1) * factor)
            b = int(b1 + (b2 - b1) * factor)

            # Draw line
            draw.line([(0, y), (1200, y)], fill=(r, g, b))

        return img

    def _resize_logo(self, logo: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """Resize logo to fit within max dimensions"""
        logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return logo


class PhotoTemplate:
    """
    Photo overlay template: Background image + overlay + text

    Layout:
    - Background photo (blurred, darkened)
    - Semi-transparent black overlay (50% opacity)
    - Logo (top-left)
    - Title (2 lines max, bold, 72px, white with shadow)
    - Excerpt (3 lines max, regular, 36px, white with shadow)
    """

    def __init__(self):
        """Initialize photo template"""
        self.font_registry = FontRegistry()

    def render(
        self,
        title: str,
        excerpt: str,
        brand_color: str,
        background_image: Optional[Image.Image] = None,
        logo: Optional[Image.Image] = None
    ) -> Image.Image:
        """
        Render photo template

        Args:
            title: Blog post title
            excerpt: Blog post excerpt
            brand_color: Brand color (hex, used as fallback)
            background_image: Background photo
            logo: Optional logo image

        Returns:
            PIL Image (1200x630)
        """
        # Create base image
        if background_image:
            # Resize and crop background to 1200x630
            img = self._prepare_background(background_image)

            # Apply blur
            img = img.filter(ImageFilter.GaussianBlur(radius=3))

            # Apply dark overlay
            overlay = Image.new("RGBA", (1200, 630), color=(0, 0, 0, 128))  # 50% opacity
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay)
            img = img.convert("RGB")
        else:
            # Fallback to solid color
            hex_color = brand_color.lstrip("#")
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            img = Image.new("RGB", (1200, 630), color=(r, g, b))

        draw = ImageDraw.Draw(img)

        # White text (readable on dark background)
        text_color = "#FFFFFF"

        # Add logo
        y_offset = 80
        if logo:
            logo_resized = self._resize_logo(logo, max_width=250, max_height=100)
            img.paste(logo_resized, (80, y_offset), logo_resized if logo_resized.mode == "RGBA" else None)
            y_offset += 140

        # Load fonts
        title_font = self.font_registry.get_font(size=72, weight="bold")
        excerpt_font = self.font_registry.get_font(size=36, weight="regular")

        # Wrap and draw title (with shadow for readability)
        title_lines = wrap_text(title, max_width=1040, font=title_font, max_lines=2)
        for line in title_lines:
            # Draw shadow
            draw.text((82, y_offset + 2), line, font=title_font, fill=(0, 0, 0))
            # Draw text
            draw.text((80, y_offset), line, font=title_font, fill=text_color)
            y_offset += 90

        y_offset += 30

        # Wrap and draw excerpt
        excerpt_lines = wrap_text(excerpt, max_width=1040, font=excerpt_font, max_lines=3)
        for line in excerpt_lines:
            # Draw shadow
            draw.text((82, y_offset + 2), line, font=excerpt_font, fill=(0, 0, 0))
            # Draw text
            draw.text((80, y_offset), line, font=excerpt_font, fill=text_color)
            y_offset += 50

        return img

    def _prepare_background(self, bg_image: Image.Image) -> Image.Image:
        """Resize and crop background to 1200x630"""
        # Calculate aspect ratios
        target_ratio = 1200 / 630
        img_ratio = bg_image.width / bg_image.height

        if img_ratio > target_ratio:
            # Image is wider, crop width
            new_height = 630
            new_width = int(bg_image.width * (630 / bg_image.height))
        else:
            # Image is taller, crop height
            new_width = 1200
            new_height = int(bg_image.height * (1200 / bg_image.width))

        # Resize
        resized = bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Crop to center
        left = (new_width - 1200) // 2
        top = (new_height - 630) // 2
        cropped = resized.crop((left, top, left + 1200, top + 630))

        return cropped

    def _resize_logo(self, logo: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """Resize logo to fit within max dimensions"""
        logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return logo


class SplitTemplate:
    """
    Split layout template: Image left, text right

    Layout:
    - Left 50%: Background image (cropped to 600x630)
    - Right 50%: Solid color (brand_color) with text
    - Logo (top-right of text area)
    - Title (2 lines max, bold, 60px)
    - Excerpt (3 lines max, regular, 32px)
    """

    def __init__(self):
        """Initialize split template"""
        self.font_registry = FontRegistry()

    def render(
        self,
        title: str,
        excerpt: str,
        brand_color: str,
        background_image: Optional[Image.Image] = None,
        logo: Optional[Image.Image] = None
    ) -> Image.Image:
        """
        Render split template

        Args:
            title: Blog post title
            excerpt: Blog post excerpt
            brand_color: Brand color (hex)
            background_image: Background photo (for left side)
            logo: Optional logo image

        Returns:
            PIL Image (1200x630)
        """
        # Create canvas
        img = Image.new("RGB", (1200, 630))

        # Left side: Background image or solid color
        if background_image:
            left_img = self._prepare_left_image(background_image)
            img.paste(left_img, (0, 0))
        else:
            # Solid color
            draw = ImageDraw.Draw(img)
            hex_color = brand_color.lstrip("#")
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            # Darken a bit for left side
            dark_color = (int(r * 0.7), int(g * 0.7), int(b * 0.7))
            draw.rectangle([(0, 0), (600, 630)], fill=dark_color)

        # Right side: Text area
        draw = ImageDraw.Draw(img)
        hex_color = brand_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        draw.rectangle([(600, 0), (1200, 630)], fill=(r, g, b))

        # Validate text color
        text_color = "#FFFFFF"
        if not validate_contrast(text_color, brand_color, min_ratio=4.5):
            text_color = "#000000"

        # Add logo (top-right of text area)
        x_offset = 650
        y_offset = 80
        if logo:
            logo_resized = self._resize_logo(logo, max_width=200, max_height=80)
            img.paste(logo_resized, (x_offset, y_offset), logo_resized if logo_resized.mode == "RGBA" else None)
            y_offset += 120

        # Load fonts (slightly smaller for split layout)
        title_font = self.font_registry.get_font(size=60, weight="bold")
        excerpt_font = self.font_registry.get_font(size=32, weight="regular")

        # Wrap and draw title
        title_lines = wrap_text(title, max_width=500, font=title_font, max_lines=2)
        for line in title_lines:
            draw.text((x_offset, y_offset), line, font=title_font, fill=text_color)
            y_offset += 75

        y_offset += 25

        # Wrap and draw excerpt
        excerpt_lines = wrap_text(excerpt, max_width=500, font=excerpt_font, max_lines=3)
        for line in excerpt_lines:
            draw.text((x_offset, y_offset), line, font=excerpt_font, fill=text_color)
            y_offset += 45

        return img

    def _prepare_left_image(self, bg_image: Image.Image) -> Image.Image:
        """Resize and crop background to 600x630 (left side)"""
        # Calculate aspect ratios
        target_ratio = 600 / 630
        img_ratio = bg_image.width / bg_image.height

        if img_ratio > target_ratio:
            # Image is wider, crop width
            new_height = 630
            new_width = int(bg_image.width * (630 / bg_image.height))
        else:
            # Image is taller, crop height
            new_width = 600
            new_height = int(bg_image.height * (600 / bg_image.width))

        # Resize
        resized = bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Crop to center
        left = (new_width - 600) // 2
        top = (new_height - 630) // 2
        cropped = resized.crop((left, top, left + 600, top + 630))

        return cropped

    def _resize_logo(self, logo: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """Resize logo to fit within max dimensions"""
        logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return logo


class OGImageGenerator:
    """
    Main Open Graph image generator

    Features:
    - 4 customizable templates (minimal, gradient, photo, split)
    - Font registry with caching
    - Text wrapping (2-line title, 3-line excerpt)
    - WCAG contrast validation (4.5:1)
    - File size optimization (<300KB)
    - Image caching

    Usage:
        generator = OGImageGenerator()
        img_bytes = generator.generate(
            title="Blog Post Title",
            excerpt="Brief excerpt...",
            template="minimal",
            brand_color="#1a73e8"
        )
    """

    def __init__(self):
        """Initialize OG image generator"""
        self.font_registry = FontRegistry()
        self.cache: Dict[str, bytes] = {}

        # Initialize templates
        self.templates = {
            "minimal": MinimalTemplate(),
            "gradient": GradientTemplate(),
            "photo": PhotoTemplate(),
            "split": SplitTemplate()
        }

        logger.info(
            f"og_image_generator_initialized",
            num_templates=len(self.templates)
        )

    def generate(
        self,
        title: str,
        excerpt: str,
        template: str = "minimal",
        brand_color: str = "#1a73e8",
        logo_path: Optional[str] = None,
        background_image: Optional[str] = None
    ) -> bytes:
        """
        Generate OG image and return PNG bytes

        Args:
            title: Blog post title
            excerpt: Blog post excerpt
            template: Template name (minimal, gradient, photo, split)
            brand_color: Brand color (hex)
            logo_path: Path to logo file (optional)
            background_image: Path to background image (optional)

        Returns:
            PNG image bytes

        Raises:
            ValueError: If template is invalid
        """
        # Create cache key
        cache_key = hashlib.md5(
            f"{title}{excerpt}{template}{brand_color}{logo_path}{background_image}".encode()
        ).hexdigest()

        # Return cached image if exists
        if cache_key in self.cache:
            logger.info("og_image_cache_hit", cache_key=cache_key[:8])
            return self.cache[cache_key]

        # Get template (fallback to minimal if invalid)
        template_obj = self.templates.get(template, self.templates["minimal"])
        if template not in self.templates:
            logger.warning(
                f"Invalid template '{template}', falling back to 'minimal'"
            )

        # Load logo if provided
        logo = None
        if logo_path and Path(logo_path).exists():
            try:
                logo = Image.open(logo_path)
            except Exception as e:
                logger.error(f"Failed to load logo: {e}")

        # Load background image if provided
        bg_image = None
        if background_image and Path(background_image).exists():
            try:
                bg_image = Image.open(background_image)
            except Exception as e:
                logger.error(f"Failed to load background image: {e}")

        # Render template
        img = template_obj.render(
            title=title,
            excerpt=excerpt,
            brand_color=brand_color,
            logo=logo,
            **({'background_image': bg_image} if template in ["photo", "split"] else {})
        )

        # Convert to PNG bytes
        img_bytes = self._to_png_bytes(img)

        # Optimize file size if >300KB
        file_size_kb = len(img_bytes) / 1024
        if file_size_kb > 300:
            logger.warning(
                f"Image size {file_size_kb:.1f}KB exceeds 300KB, optimizing...",
                size_kb=file_size_kb
            )
            img_bytes = self._optimize_png(img, max_size_kb=300)

        # Cache result
        self.cache[cache_key] = img_bytes

        logger.info(
            f"og_image_generated",
            template=template,
            size_kb=len(img_bytes) / 1024,
            cache_key=cache_key[:8]
        )

        return img_bytes

    def _to_png_bytes(self, img: Image.Image) -> bytes:
        """Convert PIL Image to PNG bytes"""
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def _optimize_png(self, img: Image.Image, max_size_kb: int = 300) -> bytes:
        """Optimize PNG to reduce file size"""
        # Try reducing quality
        buffer = io.BytesIO()

        # Convert to RGB if RGBA (remove alpha channel)
        if img.mode == "RGBA":
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            img = rgb_img

        # Save with optimization
        img.save(buffer, format="PNG", optimize=True, compress_level=9)
        img_bytes = buffer.getvalue()

        # If still too large, reduce colors
        if len(img_bytes) / 1024 > max_size_kb:
            logger.warning("PNG still too large, quantizing colors...")
            img = img.quantize(colors=256, method=2)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            img_bytes = buffer.getvalue()

        return img_bytes
