# Repurposing Agent Phases 2-3 Implementation Plan

**Session**: 060
**Timeline**: 8-10 hours
**Status**: Planning Complete → Implementation Starting

---

## Phase 1 Status (Session 059) ✅

**Complete**: Text generation for 4 platforms
- ✅ RepurposingAgent generates platform-optimized posts (LinkedIn, Facebook, Instagram, TikTok)
- ✅ Platform profiles (character limits, tone, hashtags, emoji)
- ✅ Multi-language support (de, en, fr, etc.)
- ✅ Cost tracking ($0.003/blog for 4 platform text posts)
- ✅ 71/73 tests passing (97% pass rate)

---

## Phase 2: Open Graph Image Generation (Pillow)

**Goal**: Generate customizable OG images (1200x630) with 4 templates, zero AI cost

### Architecture

```python
src/media/
├── og_image_generator.py          # Main OG image generator
├── templates/                      # Template classes
│   ├── minimal.py                  # Solid background + text
│   ├── gradient.py                 # Gradient background + text
│   ├── photo.py                    # Photo overlay + text
│   └── split.py                    # Split layout (image + text)
└── fonts/                          # Bundled fonts (fallback)
    ├── Roboto-Bold.ttf
    ├── Roboto-Regular.ttf
    └── LICENSE

tests/unit/media/
└── test_og_image_generator.py      # OG image tests
```

### Components

#### 1. **OGImageGenerator** (Main Class)

```python
class OGImageGenerator:
    """
    Generate Open Graph images (1200x630 PNG) with Pillow

    Features:
    - 4 customizable templates
    - Font registry with caching
    - Text wrapping (2-line title, 3-line excerpt)
    - WCAG contrast validation (4.5:1)
    - File size optimization (<300KB)
    """

    def generate(
        self,
        title: str,
        excerpt: str,
        template: str = "minimal",  # minimal, gradient, photo, split
        brand_color: str = "#1a73e8",
        logo_path: Optional[str] = None,
        background_image: Optional[str] = None
    ) -> bytes:
        """Generate OG image and return PNG bytes"""
```

#### 2. **Template Classes** (4 Designs)

**Template 1: Minimal** (Solid Color + Text)
```
┌─────────────────────────────────────┐
│                                     │
│   [Logo]                            │
│                                     │
│   Title (2 lines max)               │
│   Bold, 72px                        │
│                                     │
│   Excerpt (3 lines max)             │
│   Regular, 36px                     │
│                                     │
│                                     │
└─────────────────────────────────────┘
Background: Solid color (brand_color)
Text: White (auto-adjusted for contrast)
```

**Template 2: Gradient** (Linear Gradient + Text)
```
┌─────────────────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ ← Gradient top
│ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ │
│   [Logo]                            │
│                                     │
│   Title (2 lines max)               │
│   Bold, 72px                        │
│                                     │
│   Excerpt (3 lines max)             │
│   Regular, 36px                     │
│                                     │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │ ← Gradient bottom
└─────────────────────────────────────┘
Background: Linear gradient (brand_color to darker shade)
Text: White (auto-adjusted for contrast)
```

**Template 3: Photo Overlay** (Background Image + Overlay + Text)
```
┌─────────────────────────────────────┐
│ [Background photo (blur + darken)]  │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │ ← 50% dark overlay
│   [Logo]                            │
│                                     │
│   Title (2 lines max)               │
│   Bold, 72px, White + shadow        │
│                                     │
│   Excerpt (3 lines max)             │
│   Regular, 36px, White + shadow     │
│                                     │
└─────────────────────────────────────┘
Background: User-provided image (blurred, darkened)
Overlay: Semi-transparent black (50% opacity)
Text: White with shadow (guaranteed readable)
```

**Template 4: Split Layout** (Image Left, Text Right)
```
┌───────────────────┬─────────────────┐
│                   │                 │
│                   │  [Logo]         │
│   Background      │                 │
│   Image           │  Title          │
│   (cropped        │  (2 lines)      │
│   50% width)      │  Bold, 60px     │
│                   │                 │
│                   │  Excerpt        │
│                   │  (3 lines)      │
│                   │  Regular, 32px  │
│                   │                 │
└───────────────────┴─────────────────┘
Left: Background image (cropped to 600x630)
Right: Solid color (brand_color) with text
Text: White (auto-adjusted for contrast)
```

#### 3. **FontRegistry** (Font Management with Caching)

```python
class FontRegistry:
    """
    Manages fonts with caching for Pillow

    Features:
    - Auto-load system fonts (Roboto, Arial, Helvetica)
    - Fallback to bundled fonts (src/media/fonts/)
    - Cache loaded fonts (avoid re-loading)
    - Support bold, regular, italic
    """

    def get_font(self, size: int, weight: str = "regular") -> ImageFont:
        """
        Get cached font instance

        Args:
            size: Font size in pixels
            weight: bold, regular, italic

        Returns:
            PIL ImageFont instance
        """
```

**Font Priority**:
1. System fonts: `/usr/share/fonts/truetype/` (Linux)
2. Bundled fonts: `src/media/fonts/Roboto-*.ttf`
3. PIL default font (last resort)

#### 4. **TextWrapper** (Multi-line Text with Wrapping)

```python
def wrap_text(
    text: str,
    max_width: int,
    font: ImageFont,
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

    Returns:
        List of lines (max_lines)
    """
```

**Example**:
```python
title = "Die Zukunft von PropTech: Innovative Technologien revolutionieren die Immobilienbranche"
lines = wrap_text(title, max_width=1000, font=font_72, max_lines=2)
# Returns:
# [
#   "Die Zukunft von PropTech: Innovative",
#   "Technologien revolutionieren die..."
# ]
```

#### 5. **WCAG Contrast Validator** (Accessibility)

```python
def validate_contrast(
    foreground_color: str,
    background_color: str,
    min_ratio: float = 4.5
) -> bool:
    """
    Validate WCAG AA contrast ratio (4.5:1 for normal text)

    Formula:
    1. Convert colors to relative luminance (L1, L2)
    2. Calculate contrast ratio: (L1 + 0.05) / (L2 + 0.05)
    3. Check if ratio >= min_ratio

    Returns:
        True if contrast is sufficient
    """
```

**Auto-adjustment**:
- If contrast fails, adjust text color (white → black or vice versa)
- Log warning if adjustment needed

### File Size Optimization

**Target**: <300KB per OG image

**Strategies**:
1. PNG optimization (PIL optimize=True)
2. Resize background images to 1200x630 (no larger)
3. Quantize colors if >300KB (256 colors max)
4. Avoid alpha channel if not needed

### Implementation Steps (TDD)

#### Step 1: Font Registry (2 hours)
- [ ] Download Roboto fonts (Google Fonts)
- [ ] Create `src/media/fonts/` directory
- [ ] Write `test_font_registry.py` (8 tests)
  - Test system font loading
  - Test bundled font fallback
  - Test font caching
  - Test missing font handling
- [ ] Implement `FontRegistry` class
- [ ] All tests passing

#### Step 2: Text Wrapping (1 hour)
- [ ] Write `test_text_wrapping.py` (6 tests)
  - Test single-line wrapping
  - Test multi-line wrapping
  - Test truncation with "..."
  - Test empty text
  - Test very long words
  - Test Unicode (German umlauts)
- [ ] Implement `wrap_text()` function
- [ ] All tests passing

#### Step 3: Contrast Validation (1 hour)
- [ ] Write `test_contrast_validation.py` (5 tests)
  - Test valid contrast (white on blue)
  - Test invalid contrast (gray on light gray)
  - Test luminance calculation
  - Test auto-adjustment
  - Test edge cases (black on white, white on black)
- [ ] Implement `validate_contrast()` function
- [ ] All tests passing

#### Step 4: Template Implementation (3 hours)
- [ ] Write `test_minimal_template.py` (4 tests)
- [ ] Implement `MinimalTemplate` class
- [ ] Write `test_gradient_template.py` (4 tests)
- [ ] Implement `GradientTemplate` class
- [ ] Write `test_photo_template.py` (5 tests)
- [ ] Implement `PhotoTemplate` class
- [ ] Write `test_split_template.py` (5 tests)
- [ ] Implement `SplitTemplate` class
- [ ] All tests passing

#### Step 5: OGImageGenerator Integration (1 hour)
- [ ] Write `test_og_image_generator.py` (8 tests)
  - Test all 4 templates
  - Test file size <300KB
  - Test image dimensions (1200x630)
  - Test PNG format
  - Test with/without logo
  - Test with/without background image
  - Test error handling (missing fonts, invalid colors)
  - Test caching
- [ ] Implement `OGImageGenerator` class
- [ ] All tests passing

**Total Phase 2**: 8 hours, 40 tests

---

## Phase 3: Platform-Specific Images (Flux Dev)

**Goal**: Generate AI images for Instagram (1:1) and TikTok (9:16), reuse OG for LinkedIn/Facebook

### Architecture

```python
src/media/
└── platform_image_generator.py     # Platform-specific image wrapper

tests/integration/media/
└── test_platform_image_generator.py  # Platform image tests
```

### Components

#### 1. **PlatformImageGenerator** (Wrapper)

```python
class PlatformImageGenerator:
    """
    Generate platform-specific images using Flux Dev

    Features:
    - Instagram: 1:1 (1080x1080) via Flux Dev ($0.003)
    - TikTok: 9:16 (1080x1920) via Flux Dev ($0.003)
    - LinkedIn/Facebook: Reuse OG image (Pillow, $0)
    - Smart fallback (Pillow templates if Flux fails)
    """

    def __init__(self, image_generator: ImageGenerator, og_generator: OGImageGenerator):
        self.image_gen = image_generator
        self.og_gen = og_generator

    async def generate_platform_images(
        self,
        platform: str,
        topic: str,
        excerpt: str,
        brand_tone: List[str],
        use_og_fallback: bool = True
    ) -> Dict:
        """
        Generate platform-specific image

        Platform logic:
        - LinkedIn: Use OG image (Pillow, $0)
        - Facebook: Use OG image (Pillow, $0)
        - Instagram: Generate 1:1 with Flux Dev ($0.003)
        - TikTok: Generate 9:16 with Flux Dev ($0.003)

        Returns:
            {
                "success": bool,
                "url": str,  # Base64 data URL or file path
                "format": str,  # "png" or "jpeg"
                "size": Dict,  # {"width": 1080, "height": 1080}
                "cost": float,
                "provider": str  # "pillow" or "flux-dev"
            }
        """
```

#### 2. **Integration with ImageGenerator** (Existing)

**Flux Dev Support** (already exists in `image_generator.py`):
```python
# Existing method (Session 048-049):
async def generate_supporting_image(
    topic: str,
    brand_tone: List[str],
    aspect: str,
    aspect_ratio: str = "1:1"  # Can be 1:1 or 9:16
) -> Dict
```

**Add 9:16 Support**:
```python
# Extend to support TikTok vertical aspect
async def generate_supporting_image(
    ...,
    aspect_ratio: str = "1:1"  # Now supports: 1:1 (Instagram), 9:16 (TikTok)
)
```

#### 3. **Smart OG Reuse Logic**

```python
def should_use_og_image(platform: str) -> bool:
    """
    LinkedIn/Facebook: True (use OG image, free)
    Instagram/TikTok: False (generate AI image, $0.003)
    """
    return platform in ["LinkedIn", "Facebook"]
```

### Implementation Steps (TDD)

#### Step 1: Extend ImageGenerator for 9:16 (1 hour)
- [ ] Write test: `test_generate_tiktok_image_9_16_aspect()`
- [ ] Update `generate_supporting_image()` to support `aspect_ratio="9:16"`
- [ ] Test with Flux Dev (9:16 → 1080x1920)
- [ ] Test passing

#### Step 2: PlatformImageGenerator (2 hours)
- [ ] Write `test_platform_image_generator.py` (12 tests)
  - Test LinkedIn uses OG ($0)
  - Test Facebook uses OG ($0)
  - Test Instagram generates 1:1 ($0.003)
  - Test TikTok generates 9:16 ($0.003)
  - Test OG fallback (if Flux fails)
  - Test cost tracking
  - Test error handling
  - Test image format (PNG vs JPEG)
  - Test base64 encoding
  - Test caching
  - Test concurrent generation (all 4 platforms)
  - Test with missing brand_tone
- [ ] Implement `PlatformImageGenerator` class
- [ ] All tests passing

#### Step 3: RepurposingAgent Integration (1 hour)
- [ ] Extend `RepurposingAgent.generate_social_posts()`
- [ ] Add `generate_images: bool = True` parameter
- [ ] Add `brand_color: str = "#1a73e8"` parameter
- [ ] Add `logo_path: Optional[str] = None` parameter
- [ ] Generate images for each platform
- [ ] Save images to `cache/social_posts/{slug}_{platform}_image.png`
- [ ] Return image metadata in results
- [ ] Write tests (8 tests)
  - Test images generated for all platforms
  - Test images disabled
  - Test LinkedIn/Facebook share OG
  - Test Instagram/TikTok get AI images
  - Test cost calculation ($0 OG + $0.006 AI = $0.006)
  - Test cache integration
  - Test error handling (image gen fails, post text succeeds)
  - Test concurrent generation
- [ ] All tests passing

**Total Phase 3**: 4 hours, 20 tests

---

## Combined Phase 2-3 Results

### Cost Per Blog Post

**Text Only** (Phase 1):
- 4 platform posts: $0.003

**Text + Images** (Phases 1-3):
- 4 platform posts: $0.003
- OG image (LinkedIn + Facebook): $0 (Pillow)
- Instagram image (1:1 Flux Dev): $0.003
- TikTok image (9:16 Flux Dev): $0.003
- **Total**: $0.009 per blog post

### Deliverables per Platform

| Platform | Text | Image | Image Source | Cost |
|----------|------|-------|--------------|------|
| LinkedIn | ✅ Optimized | ✅ OG (1200x630) | Pillow | $0.0008 |
| Facebook | ✅ Optimized | ✅ OG (1200x630) | Pillow | $0.0008 |
| Instagram | ✅ Optimized | ✅ 1:1 (1080x1080) | Flux Dev | $0.0038 |
| TikTok | ✅ Optimized | ✅ 9:16 (1080x1920) | Flux Dev | $0.0038 |
| **Total** | 4 posts | 3 unique images | 2 providers | **$0.009** |

### Timeline

- **Phase 2**: 8 hours (OG images)
- **Phase 3**: 4 hours (Platform images)
- **Total**: 12 hours

### Test Coverage

- **Phase 2**: 40 tests (font, wrapping, contrast, templates, generator)
- **Phase 3**: 20 tests (platform logic, integration, caching)
- **Total**: 60 new tests

---

## Success Criteria

### Phase 2 (OG Images)
- ✅ All 4 templates render correctly
- ✅ Font registry loads system and bundled fonts
- ✅ Text wrapping limits to 2 lines (title), 3 lines (excerpt)
- ✅ WCAG contrast validation passes (4.5:1)
- ✅ File size <300KB per OG image
- ✅ 40 tests passing

### Phase 3 (Platform Images)
- ✅ LinkedIn/Facebook use OG image ($0 cost)
- ✅ Instagram generates 1:1 image ($0.003 cost)
- ✅ TikTok generates 9:16 image ($0.003 cost)
- ✅ Smart fallback to Pillow if Flux fails
- ✅ All images cached to `cache/social_posts/`
- ✅ 20 tests passing

### Combined
- ✅ Generate full social post bundles (text + images) for 4 platforms
- ✅ Total cost: $0.009 per blog post
- ✅ E2E test: Blog → 4 platform posts with images
- ✅ All 60 new tests passing
- ✅ Integration with existing RepurposingAgent seamless

---

## Dependencies

### Python Packages (Add to requirements.txt)
```
Pillow>=10.0.0  # Image generation
```

### Fonts (Bundled in src/media/fonts/)
```
Roboto-Bold.ttf      (Google Fonts, Apache 2.0)
Roboto-Regular.ttf   (Google Fonts, Apache 2.0)
LICENSE              (Apache 2.0 license)
```

### Existing Dependencies (Already Installed)
- replicate (Flux Dev integration)
- openai (OpenRouter for Qwen)
- httpx (Chutes.ai, optional)

---

## Next Steps

1. ✅ Create todo list (11 tasks)
2. 🔄 Implement Phase 2 (OG images with Pillow)
3. ⏳ Implement Phase 3 (Platform images with Flux Dev)
4. ⏳ Integration testing (E2E)
5. ⏳ Update documentation (CHANGELOG, session summary)

---

**Document Version**: 1.0
**Created**: 2025-11-16 (Session 060)
**Status**: Ready for Implementation
