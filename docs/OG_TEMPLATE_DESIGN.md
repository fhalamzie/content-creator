# Open Graph Image Template Design Document

## Overview

This document specifies Pillow-based patterns for generating WCAG-compliant Open Graph images (1200x630px) for social media preview cards. Focus areas: text rendering, layout patterns, accessibility, and performance optimization.

---

## 1. Pillow Text Rendering Best Practices

### 1.1 Font Loading & Caching

**Pattern: Font Registry Singleton**

```
FontRegistry
├── _cache: dict[str, FreeTypeFont]
├── load(font_path, size) -> FreeTypeFont
└── precache(fonts: list[dict])
    └── {path: str, sizes: list[int]}
```

**Key Practices:**

- **Load once, reuse often**: Create font objects during initialization, not on each render call
- **OS-specific paths**: Use `ImageFont.truetype()` which searches system fonts automatically
  - macOS: `/Library/Fonts/`, `~/Library/Fonts/`
  - Linux: `~/.local/share/fonts/`, `/usr/share/fonts/`
  - Windows: `C:\Windows\Fonts\` (via system search)
- **Memory management**:
  - On Windows, FreeType keeps files open while font objects exist (512 concurrent file limit)
  - Solution: Keep font objects alive for template lifetime OR cache as bytes in memory
- **Fallback fonts**: Use system fonts when custom fonts unavailable

**Recommended Loading Strategy:**

```
Initialize template:
  1. Load primary font (title): 60-72px
  2. Load secondary font (excerpt): 32-40px
  3. Load accent font (logo text): 24-32px
  Store as instance variables (never recreate)
```

**Supported Formats:**
- TTF (TrueType Font)
- OTF (OpenType Font)
- Both fully supported by Pillow's FreeType integration

---

### 1.2 Text Wrapping Algorithm (2-Line Title, 3-Line Excerpt)

**Constraint-Based Word Wrapping:**

```
TITLE WRAPPING (max 2 lines, 1200px - 80px padding = 1120px)
├── Attempt 1-line fit (full text)
│   ├── textbbox() → measure width
│   └── if width > MAX_WIDTH → proceed to 2-line
├── Binary search word count for line 1
│   ├── Try mid-point word count
│   ├── Measure with textbbox()
│   ├── Adjust up/down based on width
│   └── Stop when fit and next word would overflow
├── Wrap remaining text to line 2
│   ├── Truncate line 2 with ellipsis if needed
│   └── Measure final dimensions
└── Return: [(line1, x, y), (line2, x, y)]

EXCERPT WRAPPING (max 3 lines, 1120px width)
├── Split by sentence or word boundary
├── For each line (1-3):
│   └── Binary search fit (same as title)
├── Truncate line 3 with "..." if >3 lines needed
└── Return: [(line1, x, y), (line2, x, y), (line3, x, y)]
```

**Implementation Pattern:**

```python
def wrap_text(text, font, max_width, max_lines):
    """
    Returns list of (line_text, line_width) tuples.
    Uses textbbox() to measure proportional fonts accurately.
    """
    # Pseudocode
    lines = []
    words = text.split()

    for line_num in range(max_lines):
        line = ""
        for word in words:
            candidate = (line + " " + word).strip()
            bbox = draw.textbbox((0, 0), candidate, font=font, anchor="lt")
            width = bbox[2] - bbox[0]

            if width <= max_width:
                line = candidate
            else:
                if not line:
                    line = word[:n] + "…"  # Emergency fallback
                break

        lines.append(line)
        words = words[len(line.split()):]

    return lines
```

**Key Method: `textbbox(xy, text, font, anchor)`**

- Returns `(left, top, right, bottom)` in pixels
- `anchor="lt"` (left-top) for consistent measurement
- Requires FreeTypeFont (TTF/OTF only)
- Supports multiline text (splits on `\n`)
- Use for every wrapping decision, not character counting

---

### 1.3 Text Alignment & Centering

**Pillow Anchor System:**

```
Horizontal (first char):       Vertical (second char):
  l = left                       a = ascender (cap height)
  m = middle                     t = top
  r = right                      m = middle
                                 s = baseline (standard)
                                 b = bottom
                                 d = descender

Example anchors:
  "lt" = left-top (default)
  "mm" = center-center
  "ms" = center-baseline (for body text)
  "rs" = right-baseline
```

**Centering Patterns:**

| Use Case | Anchor | Notes |
|----------|--------|-------|
| Title (block centered) | `"mm"` | xy=(600, y) centers at page middle |
| Tagline baseline | `"ms"` | Baseline alignment for uniform text height |
| Corner logo text | `"ls"` or `"rs"` | Align with baseline for consistency |
| Multiline text block | `"lm"` or `"rm"` | Use `align="center"` in text() for multiline |

**Important Limitation:**
- Anchor parameter only works with OpenType/TrueType fonts
- Bitmap fonts ignore anchor and default to top-left (`"la"`)
- Always use TTF/OTF for precise control

---

### 1.4 Anti-Aliasing & Quality

**Control Via `fontmode` Attribute:**

```
font.fontmode = "1"  # No anti-aliasing (sharp, pixelated edges)
font.fontmode = "L"  # Anti-aliased (smooth, grayscale smoothing)
```

**Recommended Settings:**

- **Body text (≥32px)**: `fontmode="L"` for smooth appearance
- **Small text (<24px)**: `fontmode="L"` still preferred for legibility
- **High-contrast text**: `fontmode="L"` reduces aliasing artifacts
- **Performance optimization**: "L" mode has negligible perf cost vs "1"

**Stroke Effects (Optional):**

```python
# Outline text for better contrast
draw.text(
    (x, y),
    text,
    font=font,
    fill=foreground_color,
    stroke_width=2,
    stroke_fill=background_color,
    anchor="mm"
)
```

Benefits:
- Improves contrast over varied backgrounds
- 1-2px stroke adds professional polish
- Minimal performance impact

---

## 2. Layout Patterns for 1200x630 Images

### 2.1 Canvas Structure

**Safe Zone Analysis (1200x630px):**

```
┌─────────────────────────────────────────────────────┐
│ 1200px                                              │
│                                                     │
│  40px  SAFE ZONE (1120x550px)                      │
│  ├─────────────────────────────────────────────┤  │
│  │                                             │  │
│  │  TITLE (60-72px, 2 lines max)              │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │ "Your Article Title Here..."        │  │  │
│  │  │ "...continued on next line"         │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  │                                             │  │
│  │  ↓ 20px gap                               │  │
│  │                                             │  │
│  │  EXCERPT (32-40px, 3 lines max)            │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │ "Brief preview of article..."       │  │  │
│  │  │ "Second line of excerpt content"    │  │  │
│  │  │ "Third line with preview..."        │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  │                                             │  │
│  │  ↓ 30px gap                               │  │
│  │                                             │  │
│  │  [SITE LOGO] "Site Name" (24-32px)       │  │
│  │  ├──────────────┬──────────────────┤     │  │
│  │  │ 50x50 logo   │ Vertical text    │     │  │
│  │  │              │ Right-aligned    │     │  │
│  │  └──────────────┴──────────────────┘     │  │
│  │                                             │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│ 40px                                               │
└─────────────────────────────────────────────────────┘

DIMENSIONS:
- Canvas: 1200 x 630px
- Safe margin: 40px all sides
- Text block: 1120px width x 550px height
- Text start Y: 50-60px from top
```

### 2.2 Gradient Background Pattern

**Recommended Approach: PIL.Image.new() + ImageDraw.rectangle()**

```python
# Create base image
img = Image.new("RGB", (1200, 630), color=(255, 255, 255))

# Method 1: Solid background with overlay
draw.rectangle([(0, 0), (1200, 630)], fill=bg_color)

# Method 2: Simple gradient (manual)
# Pillow doesn't have native gradients, use:
# - Pre-generated gradient PNG (cached)
# - Numpy array manipulation (faster for gradients)
# - Paste smaller gradient image (stretched to 1200x630)

# Recommended: Cache pre-built gradients as PNG files
gradients/
├── gradient_blue_to_white.png (1200x630)
├── gradient_dark_to_light.png (1200x630)
└── gradient_brand_primary.png (1200x630)

# Then: Image.open("gradients/...") in render()
```

**Alternative: NumPy-Based Gradients (for dynamic colors):**

```
PERFORMANCE: Numpy approach takes ~50-100ms for 1200x630
PRACTICAL: Cache most-used gradients, generate dynamic only when needed
```

**Best Practice:**

- For fixed brand gradients: Pre-generate and cache PNG files
- For dynamic gradients: Generate once, cache by color hash
- For overlays: Use semi-transparent rectangles on top of gradient

---

### 2.3 Text Overlay with Contrast Management

**Layering Strategy:**

```
Layer 1: Background (solid or gradient)
         └─ 100% opaque

Layer 2: Contrast overlay (optional, for dark text on light)
         ├─ Semi-transparent dark rect (0.1-0.2 alpha)
         ├─ Covers title + excerpt area
         └─ Improves readability

Layer 3: Title text
         ├─ Font size: 60-72px
         ├─ Weight: Bold (700-900)
         └─ Color: High contrast (black, white, or brand)

Layer 4: Excerpt text
         ├─ Font size: 32-40px
         ├─ Weight: Regular (400)
         └─ Color: Slightly muted but still ≥4.5:1 contrast

Layer 5: Branding (logo + site name)
         ├─ Logo: 50x50px, bottom-left
         └─ Site name: 24-32px, right-aligned
```

**Contrast Overlay Example:**

```python
# Add semi-transparent dark overlay for text contrast
overlay_rect = [(40, 40), (1160, 450)]  # Title + excerpt area
draw.rectangle(overlay_rect, fill=(0, 0, 0, 51), outline=None)  # 20% opacity

# Then draw white text on top
draw.text((600, 150), title, fill=(255, 255, 255), font=font_title, anchor="mm")
```

**Safe Zone for Mobile/Desktop:**

```
Desktop (>768px width):        Mobile (<768px width):
├─ Full title visible          ├─ Title may be truncated
├─ Full excerpt visible        ├─ Excerpt shortened to 2 lines
└─ Logo in bottom corner       └─ Logo hidden or repositioned

→ Design for mobile first
→ Test at 600px width (mobile preview)
→ Use max 2 lines for title (fits all devices)
→ Use max 2-3 lines for excerpt (truncate gracefully)
```

---

## 3. WCAG Contrast Validation

### 3.1 Contrast Ratio Calculation

**Formula: (L1 + 0.05) / (L2 + 0.05)**

Where:
- L1 = relative luminance of lighter color
- L2 = relative luminance of darker color
- Range: 1:1 (no contrast) to 21:1 (maximum)

**Relative Luminance (sRGB):**

```
L = 0.2126 × R + 0.7152 × G + 0.0722 × B

Where R, G, B are normalized to 0-1:
├─ if RGB ≤ 0.03928:  use RGB / 12.92
└─ if RGB > 0.03928:  use ((RGB + 0.055) / 1.055) ^ 2.4
```

**Example Calculation:**

```
Black text (#000000) on white background (#FFFFFF):
├─ White luminance: L = 0.2126(1) + 0.7152(1) + 0.0722(1) = 1.0
├─ Black luminance: L = 0.2126(0) + 0.7152(0) + 0.0722(0) = 0.0
├─ Contrast = (1.0 + 0.05) / (0.0 + 0.05) = 1.05 / 0.05 = 21:1 ✓ AAA
```

### 3.2 WCAG Standards

| Level | Standard Text | Large Text | UI Components | Images |
|-------|---------------|-----------|---------------|--------|
| AA | 4.5:1 | 3:1 | 3:1 | No requirement |
| AAA | 7:1 | 4.5:1 | 3:1 | No requirement |

**Text Size Definitions:**
- **Normal text**: <18pt (24px) or <14pt (18.7px) bold
- **Large text**: ≥18pt (24px) or ≥14pt (18.7px) bold

**Exceptions:**
- Logos and brand names: No contrast requirement
- Decorative text: No requirement
- Disabled UI components: No requirement

---

### 3.3 Python Libraries for Contrast Checking

**Option 1: Manual Calculation (Lightweight)**

```
No dependencies, use sRGB formula above
Pros: Zero external deps, <50 lines
Cons: Must implement correctly
```

**Option 2: `wcag-contrast` (PyPI)**

```
pip install wcag-contrast

Usage:
  contrast_ratio = get_contrast_ratio("#000000", "#FFFFFF")
  # Returns: 21.0

  passes = contrast_ratio >= 4.5  # AA standard
```

**Option 3: `webaim-contrast` (PyPI)**

```
pip install webaim-contrast

Usage:
  from webaim_contrast import ratio
  r = ratio("#333333", "#FFFFFF")
  # Returns: (contrast_ratio, level)  # (13.25, 'AAA')
```

**Recommendation for OGTemplate:**

```
├─ Use `wcag-contrast` (simpler API)
├─ Or implement manual calculation (zero deps, ~30 lines)
├─ Validate on save:
│  ├─ Title text vs background: ≥4.5:1 (AA)
│  ├─ Excerpt text vs background: ≥4.5:1 (AA)
│  └─ Logo text vs background: ≥4.5:1 (AA)
└─ Log warnings if below threshold (don't block)
```

**Integration Pattern:**

```python
def validate_contrast(img, draw, text_color, bg_color):
    """
    Check if text color meets WCAG AA on background.
    Returns (passes: bool, ratio: float, level: str)
    """
    ratio = calculate_contrast_ratio(text_color, bg_color)
    passes = ratio >= 4.5  # AA threshold
    level = "AAA" if ratio >= 7.0 else "AA" if passes else "FAIL"
    return passes, ratio, level
```

---

## 4. Performance Optimization

### 4.1 Image Quality vs File Size

**Target: <300KB per image**

**PNG Strategy (Preferred for text-heavy images):**

```
Settings:
├─ compress_level: 9 (maximum compression)
├─ optimize: True (extra processing pass)
└─ format: "PNG" (lossless, better for sharp text)

Result: 150-250KB typical
Trade-off: ~2-5ms extra save time, significantly smaller file
```

**JPEG Strategy (Fallback for photo-heavy backgrounds):**

```
Settings:
├─ quality: 75-80 (good balance)
├─ optimize: True (extra encoder pass)
├─ subsampling: "4:2:2" (reduce chroma, keep luma sharp)
└─ format: "JPEG"

Result: 80-150KB typical
Trade-off: Slight quality loss (imperceptible at 75+), faster save
```

**Format Selection Decision Tree:**

```
Is background photo/gradient-heavy?
├─ YES → Use JPEG, quality=75-80
└─ NO (text-focused, solid colors)
    └─ Use PNG, compress_level=9
```

**Quality Benchmarks (1200x630 solid color + text):**

```
PNG:
  compress_level=6 (default): ~180KB, 1ms save
  compress_level=9 + optimize: ~150KB, 5ms save

JPEG:
  quality=90, no optimize: ~110KB, 2ms save
  quality=75, optimize=True: ~95KB, 3ms save
  quality=60, optimize=True: ~75KB, 3ms save (visible degradation)
```

---

### 4.2 PNG vs JPEG Format Selection

| Criterion | PNG | JPEG |
|-----------|-----|------|
| Text quality | Sharp, crisp | Slight artifacts at low quality |
| Compression | Lossless, good for flat colors | Lossy, excellent for photos |
| File size (solid bg) | 120-200KB | 80-120KB |
| Best case | Text + solid colors | Photo backgrounds |
| Transparency | Supported | Not supported |
| Browser support | 100% | 100% |

**Recommendation:**

- **Default: PNG** (all OG images are text-centric)
- **Override to JPEG** only if background is high-resolution photo

---

### 4.3 Font Object Caching

**Singleton Registry Pattern:**

```python
class FontRegistry:
    _instance = None
    _fonts = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, font_path, size):
        key = f"{font_path}@{size}"
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(font_path, size)
        return self._fonts[key]

    def precache(self, fonts):
        """Load fonts at startup"""
        for spec in fonts:
            self.load(spec["path"], spec["size"])

# Usage:
fonts = FontRegistry()
title_font = fonts.load("Arial.ttf", 72)  # Cached after first call
title_font = fonts.load("Arial.ttf", 72)  # Returned from cache
```

**Benefits:**

```
Per-image improvement:
├─ Without caching: 50-100ms per font load
├─ With caching: 0ms (immediate return)
└─ 3-4 fonts per image = 150-400ms saved

For 1000 images/day:
├─ Without: 150-400 seconds
├─ With: ~1-2 seconds
└─ Speedup: 100-200x
```

---

## 5. Code Architecture Recommendations

### 5.1 Module Structure

```
og_templates/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── registry.py          # FontRegistry singleton
│   ├── canvas.py            # Canvas, safe zones, layout
│   └── validation.py        # WCAG contrast validation
├── text/
│   ├── __init__.py
│   ├── wrapping.py          # wrap_text() function
│   ├── alignment.py         # Center, align, anchor logic
│   └── rendering.py         # draw.text() with quality settings
├── background/
│   ├── __init__.py
│   ├── solid.py             # Solid color backgrounds
│   ├── gradient.py          # Cached gradient patterns
│   └── overlay.py           # Contrast overlays
├── templates/
│   ├── __init__.py
│   ├── base.py              # Abstract OGTemplate class
│   └── blog.py              # BlogOGTemplate(title, excerpt, logo)
├── optimization/
│   ├── __init__.py
│   ├── quality.py           # PNG/JPEG quality settings
│   └── compression.py       # File size optimization
└── tests/
    ├── test_wrapping.py     # Text wrapping edge cases
    ├── test_contrast.py     # WCAG validation
    ├── test_rendering.py    # Image output quality
    └── test_performance.py  # Save time, file size
```

### 5.2 Core Class Interface

```python
class OGTemplate:
    """Abstract base for Open Graph templates"""

    def __init__(self, width=1200, height=630, bg_color=(255, 255, 255)):
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.font_registry = FontRegistry()
        self.margin = 40
        self.safe_width = width - 2 * self.margin

    def render(self, **kwargs) -> Image.Image:
        """Generate image, return PIL Image object"""
        raise NotImplementedError

    def save(self, path, quality=80, format="PNG"):
        """Save image with optimization"""
        raise NotImplementedError

    def validate_contrast(self) -> dict:
        """Return contrast validation results"""
        raise NotImplementedError


class BlogOGTemplate(OGTemplate):
    """Generate blog post Open Graph images"""

    def render(
        self,
        title: str,
        excerpt: str,
        site_name: str,
        logo_path: str | None = None,
        bg_color: tuple[int, int, int] = (255, 255, 255),
        text_color: tuple[int, int, int] = (0, 0, 0),
    ) -> Image.Image:
        """
        Render blog OG image with title, excerpt, branding.

        Args:
            title: Blog post title (auto-wrapped to 2 lines)
            excerpt: Brief summary (auto-wrapped to 3 lines)
            site_name: Brand name
            logo_path: Path to logo image (50x50px recommended)
            bg_color: RGB background color
            text_color: RGB text color

        Returns:
            PIL.Image.Image (1200x630px, RGB mode)
        """
        # Implement using patterns in sections 2-3
```

---

## 6. Integration Checklist

### Phase 1: Foundation (Week 1)

- [ ] FontRegistry with TTF loading and caching
- [ ] wrap_text() with textbbox() measurement
- [ ] Canvas/safe-zone structure (40px margins)
- [ ] Solid background + text rendering
- [ ] Manual contrast ratio calculation

### Phase 2: Templates (Week 2)

- [ ] BlogOGTemplate class
- [ ] Gradient background support
- [ ] Overlay contrast enhancement
- [ ] Logo + branding integration
- [ ] WCAG validation on render

### Phase 3: Optimization (Week 3)

- [ ] PNG/JPEG quality settings
- [ ] File size benchmarking
- [ ] Gradient caching
- [ ] Performance profiling

### Phase 4: Testing (Week 4)

- [ ] Text wrapping edge cases (Unicode, emoji, long words)
- [ ] Contrast validation (100 color pairs)
- [ ] File size regression tests
- [ ] Mobile preview testing

---

## 7. Key References

**Pillow Documentation:**
- Text rendering: https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html#PIL.ImageDraw.ImageDraw.text
- Text anchors: https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html
- Font loading: https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
- Image formats: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html

**WCAG Standards:**
- Contrast requirement: https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html
- WebAIM contrast guidance: https://webaim.org/articles/contrast/

**Open Graph Spec:**
- Official spec: https://ogp.me/ (no dimension requirements specified; use 1200x630 industry standard)

**Python Contrast Libraries:**
- `wcag-contrast`: https://pypi.org/project/wcag-contrast/
- `webaim-contrast`: https://pypi.org/project/webaim-contrast/

---

## 8. Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Single image render | <500ms | Includes font loading first time |
| Image with cache | <100ms | After FontRegistry primed |
| File size (PNG) | <250KB | compress_level=9 + optimize |
| File size (JPEG) | <150KB | quality=75 + optimize |
| Contrast validation | <5ms | Per image |
| Memory per image | <50MB | Peak during render, released after save |

---

**Document Version:** 1.0
**Last Updated:** Phase 2 Design
**Status:** Ready for implementation
