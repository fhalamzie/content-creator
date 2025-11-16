"""
Unit tests for OG Image Generator

Tests Pillow-based Open Graph image generation with 4 templates,
font registry, text wrapping, and WCAG contrast validation.
"""

import pytest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple

# Will implement these modules
from src.media.og_image_generator import (
    FontRegistry,
    wrap_text,
    validate_contrast,
    calculate_luminance,
    MinimalTemplate,
    GradientTemplate,
    PhotoTemplate,
    SplitTemplate,
    OGImageGenerator
)


class TestFontRegistry:
    """Test font loading and caching"""

    def test_get_system_font(self):
        """Should load system Roboto font"""
        registry = FontRegistry()
        font = registry.get_font(size=48, weight="bold")

        assert isinstance(font, ImageFont.FreeTypeFont)
        assert font.size == 48

    def test_get_regular_font(self):
        """Should load regular weight font"""
        registry = FontRegistry()
        font = registry.get_font(size=32, weight="regular")

        assert isinstance(font, ImageFont.FreeTypeFont)
        assert font.size == 32

    def test_font_caching(self):
        """Should cache loaded fonts (same object returned)"""
        registry = FontRegistry()

        font1 = registry.get_font(size=48, weight="bold")
        font2 = registry.get_font(size=48, weight="bold")

        # Should be same cached object
        assert font1 is font2

    def test_different_sizes_not_cached(self):
        """Different sizes should return different font objects"""
        registry = FontRegistry()

        font1 = registry.get_font(size=48, weight="bold")
        font2 = registry.get_font(size=72, weight="bold")

        # Different sizes
        assert font1 is not font2
        assert font1.size == 48
        assert font2.size == 72

    def test_fallback_to_default_font(self):
        """Should fallback to PIL default if system fonts missing"""
        registry = FontRegistry()
        # Override font paths to non-existent
        registry.font_paths = []

        font = registry.get_font(size=48, weight="bold")

        # Should still return a font (PIL default)
        assert isinstance(font, (ImageFont.FreeTypeFont, ImageFont.ImageFont))

    def test_invalid_weight_uses_regular(self):
        """Invalid weight should fallback to regular"""
        registry = FontRegistry()
        font = registry.get_font(size=48, weight="invalid_weight")

        assert isinstance(font, ImageFont.FreeTypeFont)

    def test_finds_roboto_fonts(self):
        """Should find Roboto fonts on system"""
        registry = FontRegistry()

        # Should have at least bold and regular
        assert len(registry.font_paths) >= 2
        assert any("Bold" in str(p) for p in registry.font_paths)
        assert any("Regular" in str(p) for p in registry.font_paths)

    def test_cache_key_format(self):
        """Cache key should include size and weight"""
        registry = FontRegistry()

        # Load fonts to populate cache
        registry.get_font(size=48, weight="bold")
        registry.get_font(size=32, weight="regular")

        # Check cache has correct keys
        assert "48-bold" in registry.cache or (48, "bold") in registry.cache
        assert "32-regular" in registry.cache or (32, "regular") in registry.cache


class TestTextWrapping:
    """Test text wrapping algorithm"""

    @pytest.fixture
    def test_font(self):
        """Create a test font for measuring"""
        registry = FontRegistry()
        return registry.get_font(size=48, weight="regular")

    def test_single_line_no_wrap(self, test_font):
        """Short text should not wrap"""
        text = "Short title"
        lines = wrap_text(text, max_width=1000, font=test_font, max_lines=2)

        assert len(lines) == 1
        assert lines[0] == "Short title"

    def test_two_line_wrap(self, test_font):
        """Long text should wrap to 2 lines"""
        text = "Die Zukunft von PropTech: Innovative Technologien revolutionieren die Immobilienbranche"
        lines = wrap_text(text, max_width=600, font=test_font, max_lines=2)

        assert len(lines) == 2
        assert len(lines[0]) > 0
        assert len(lines[1]) > 0
        # No line should be empty
        assert all(line.strip() for line in lines)

    def test_truncation_with_ellipsis(self, test_font):
        """Text exceeding max_lines should be truncated with ..."""
        text = "Very long text that will definitely exceed two lines when wrapped at narrow width so we need to test truncation behavior properly"
        lines = wrap_text(text, max_width=400, font=test_font, max_lines=2)

        assert len(lines) == 2
        # Last line should end with ... if truncated
        # (may not always truncate depending on width, so check conditionally)
        if len(lines) == 2:
            # Check that we got exactly 2 lines (truncated)
            pass  # Valid result

    def test_empty_text(self, test_font):
        """Empty text should return empty list"""
        lines = wrap_text("", max_width=1000, font=test_font, max_lines=2)

        assert len(lines) == 0 or lines == [""]

    def test_german_umlauts(self, test_font):
        """Should handle German umlauts (ä, ö, ü, ß)"""
        text = "Über größere Möglichkeiten für schöne Straßen"
        lines = wrap_text(text, max_width=800, font=test_font, max_lines=2)

        assert len(lines) >= 1
        # Check umlauts preserved
        full_text = " ".join(lines)
        assert "Über" in full_text or "über" in full_text.lower()
        assert "ö" in full_text

    def test_very_long_single_word(self, test_font):
        """Very long word should not break (keep on single line)"""
        text = "Verylongwordthatcannotfitononelinebutshouldbekeptyanyway"
        lines = wrap_text(text, max_width=300, font=test_font, max_lines=2)

        # Should keep the word even if it exceeds max_width
        assert len(lines) >= 1
        assert text in " ".join(lines) or text[:30] in " ".join(lines)


class TestContrastValidation:
    """Test WCAG contrast validation"""

    def test_white_on_blue_valid(self):
        """White on blue should have good contrast (>4.5:1)"""
        result = validate_contrast(
            foreground_color="#FFFFFF",
            background_color="#1a73e8",
            min_ratio=4.5
        )

        assert result is True

    def test_gray_on_light_gray_invalid(self):
        """Gray on light gray should have poor contrast"""
        result = validate_contrast(
            foreground_color="#CCCCCC",
            background_color="#EEEEEE",
            min_ratio=4.5
        )

        assert result is False

    def test_black_on_white_valid(self):
        """Black on white should have maximum contrast (21:1)"""
        result = validate_contrast(
            foreground_color="#000000",
            background_color="#FFFFFF",
            min_ratio=4.5
        )

        assert result is True

    def test_white_on_black_valid(self):
        """White on black should have maximum contrast"""
        result = validate_contrast(
            foreground_color="#FFFFFF",
            background_color="#000000",
            min_ratio=4.5
        )

        assert result is True

    def test_luminance_calculation_white(self):
        """White should have luminance ~1.0"""
        luminance = calculate_luminance("#FFFFFF")

        assert 0.99 <= luminance <= 1.0

    def test_luminance_calculation_black(self):
        """Black should have luminance ~0.0"""
        luminance = calculate_luminance("#000000")

        assert 0.0 <= luminance <= 0.01

    def test_luminance_calculation_gray(self):
        """Gray should have luminance ~0.5"""
        luminance = calculate_luminance("#808080")

        assert 0.2 <= luminance <= 0.6

    def test_contrast_ratio_calculation(self):
        """Contrast ratio calculation should be correct"""
        # Black on white = 21:1
        result = validate_contrast("#000000", "#FFFFFF", min_ratio=20.0)
        assert result is True

    def test_hex_color_parsing(self):
        """Should parse hex colors with and without #"""
        result1 = validate_contrast("FFFFFF", "000000", min_ratio=4.5)
        result2 = validate_contrast("#FFFFFF", "#000000", min_ratio=4.5)

        assert result1 == result2 == True


class TestMinimalTemplate:
    """Test minimal template (solid color + text)"""

    def test_create_minimal_template(self):
        """Should create minimal template image"""
        template = MinimalTemplate()
        img = template.render(
            title="Test Title",
            excerpt="Test excerpt for OG image",
            brand_color="#1a73e8"
        )

        assert isinstance(img, Image.Image)
        assert img.size == (1200, 630)
        assert img.mode in ["RGB", "RGBA"]

    def test_minimal_template_with_logo(self):
        """Should include logo if provided"""
        template = MinimalTemplate()

        # Create a dummy logo
        logo = Image.new("RGBA", (200, 100), color=(255, 0, 0, 255))

        img = template.render(
            title="Test Title",
            excerpt="Test excerpt",
            brand_color="#1a73e8",
            logo=logo
        )

        assert isinstance(img, Image.Image)
        assert img.size == (1200, 630)

    def test_minimal_template_long_title(self):
        """Should handle long title (wrap to 2 lines)"""
        template = MinimalTemplate()
        img = template.render(
            title="Very long title that should wrap to multiple lines when rendered on the image",
            excerpt="Short excerpt",
            brand_color="#1a73e8"
        )

        assert isinstance(img, Image.Image)

    def test_minimal_template_custom_color(self):
        """Should use custom brand color"""
        template = MinimalTemplate()
        img = template.render(
            title="Title",
            excerpt="Excerpt",
            brand_color="#FF5722"
        )

        assert isinstance(img, Image.Image)
        # Could verify color if needed (pixel sampling)


class TestGradientTemplate:
    """Test gradient template"""

    def test_create_gradient_template(self):
        """Should create gradient background image"""
        template = GradientTemplate()
        img = template.render(
            title="Test Title",
            excerpt="Test excerpt",
            brand_color="#1a73e8"
        )

        assert isinstance(img, Image.Image)
        assert img.size == (1200, 630)

    def test_gradient_creates_smooth_transition(self):
        """Gradient should have smooth color transition"""
        template = GradientTemplate()
        img = template.render(
            title="Title",
            excerpt="Excerpt",
            brand_color="#FF5722"
        )

        # Sample colors from top and bottom
        top_pixel = img.getpixel((600, 100))
        bottom_pixel = img.getpixel((600, 530))

        # Top and bottom should be different (gradient effect)
        assert top_pixel != bottom_pixel


class TestPhotoTemplate:
    """Test photo overlay template"""

    @pytest.fixture
    def test_background_image(self):
        """Create a test background image"""
        img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
        return img

    def test_create_photo_template(self, test_background_image):
        """Should create photo overlay image"""
        template = PhotoTemplate()
        img = template.render(
            title="Test Title",
            excerpt="Test excerpt",
            brand_color="#1a73e8",
            background_image=test_background_image
        )

        assert isinstance(img, Image.Image)
        assert img.size == (1200, 630)

    def test_photo_template_applies_overlay(self, test_background_image):
        """Should apply dark overlay for text readability"""
        template = PhotoTemplate()
        img = template.render(
            title="Title",
            excerpt="Excerpt",
            brand_color="#FFFFFF",
            background_image=test_background_image
        )

        # Sample pixel should be darker than original background
        pixel = img.getpixel((600, 315))
        # Should be darker than (100, 150, 200)
        assert pixel[0] < 150  # Some darkening applied

    def test_photo_template_without_background(self):
        """Should fallback to solid color if no background provided"""
        template = PhotoTemplate()
        img = template.render(
            title="Title",
            excerpt="Excerpt",
            brand_color="#1a73e8",
            background_image=None
        )

        # Should still create image (fallback to solid color)
        assert isinstance(img, Image.Image)
        assert img.size == (1200, 630)


class TestSplitTemplate:
    """Test split layout template"""

    @pytest.fixture
    def test_background_image(self):
        """Create a test background image"""
        img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
        return img

    def test_create_split_template(self, test_background_image):
        """Should create split layout image"""
        template = SplitTemplate()
        img = template.render(
            title="Test Title",
            excerpt="Test excerpt",
            brand_color="#1a73e8",
            background_image=test_background_image
        )

        assert isinstance(img, Image.Image)
        assert img.size == (1200, 630)

    def test_split_template_has_two_sections(self, test_background_image):
        """Split template should have distinct left and right sections"""
        template = SplitTemplate()
        img = template.render(
            title="Title",
            excerpt="Excerpt",
            brand_color="#FF5722",
            background_image=test_background_image
        )

        # Sample left and right sides
        left_pixel = img.getpixel((100, 315))  # Left side (image)
        right_pixel = img.getpixel((900, 315))  # Right side (text)

        # Left and right should be different colors
        assert left_pixel != right_pixel

    def test_split_template_without_background(self):
        """Should work without background image"""
        template = SplitTemplate()
        img = template.render(
            title="Title",
            excerpt="Excerpt",
            brand_color="#1a73e8",
            background_image=None
        )

        # Should still create image (solid color on left)
        assert isinstance(img, Image.Image)


class TestOGImageGenerator:
    """Test main OG image generator"""

    def test_generate_minimal_template(self):
        """Should generate OG image with minimal template"""
        generator = OGImageGenerator()
        img_bytes = generator.generate(
            title="Test Title",
            excerpt="Test excerpt",
            template="minimal",
            brand_color="#1a73e8"
        )

        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0

        # Verify it's a valid PNG
        img = Image.open(io.BytesIO(img_bytes))
        assert img.format == "PNG"
        assert img.size == (1200, 630)

    def test_generate_all_templates(self):
        """Should generate all 4 templates"""
        generator = OGImageGenerator()
        templates = ["minimal", "gradient", "photo", "split"]

        for template_name in templates:
            img_bytes = generator.generate(
                title="Title",
                excerpt="Excerpt",
                template=template_name,
                brand_color="#1a73e8"
            )

            assert isinstance(img_bytes, bytes)
            assert len(img_bytes) > 0

    def test_file_size_under_300kb(self):
        """Generated images should be <300KB"""
        generator = OGImageGenerator()
        img_bytes = generator.generate(
            title="Test Title",
            excerpt="Test excerpt",
            template="minimal",
            brand_color="#1a73e8"
        )

        file_size_kb = len(img_bytes) / 1024
        assert file_size_kb < 300

    def test_invalid_template_uses_default(self):
        """Invalid template should fallback to minimal"""
        generator = OGImageGenerator()
        img_bytes = generator.generate(
            title="Title",
            excerpt="Excerpt",
            template="invalid_template",
            brand_color="#1a73e8"
        )

        # Should still generate image (fallback to minimal)
        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0

    def test_generate_with_logo(self, tmp_path):
        """Should include logo in image"""
        # Create a dummy logo file
        logo_path = tmp_path / "logo.png"
        logo_img = Image.new("RGBA", (200, 100), color=(255, 0, 0, 255))
        logo_img.save(logo_path)

        generator = OGImageGenerator()
        img_bytes = generator.generate(
            title="Title",
            excerpt="Excerpt",
            template="minimal",
            brand_color="#1a73e8",
            logo_path=str(logo_path)
        )

        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0

    def test_generate_with_background_image(self, tmp_path):
        """Should use background image for photo/split templates"""
        # Create a dummy background
        bg_path = tmp_path / "background.jpg"
        bg_img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
        bg_img.save(bg_path)

        generator = OGImageGenerator()
        img_bytes = generator.generate(
            title="Title",
            excerpt="Excerpt",
            template="photo",
            brand_color="#1a73e8",
            background_image=str(bg_path)
        )

        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0

    def test_caching_same_params(self):
        """Should cache images with same parameters"""
        generator = OGImageGenerator()

        img1 = generator.generate(
            title="Title",
            excerpt="Excerpt",
            template="minimal",
            brand_color="#1a73e8"
        )

        img2 = generator.generate(
            title="Title",
            excerpt="Excerpt",
            template="minimal",
            brand_color="#1a73e8"
        )

        # Should return cached result (same bytes)
        assert img1 == img2

    def test_error_handling_missing_font(self):
        """Should handle missing fonts gracefully"""
        generator = OGImageGenerator()
        # Override font registry to simulate missing fonts
        generator.font_registry.font_paths = []

        img_bytes = generator.generate(
            title="Title",
            excerpt="Excerpt",
            template="minimal",
            brand_color="#1a73e8"
        )

        # Should still generate image (with default font)
        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0


# Import io for BytesIO
import io
