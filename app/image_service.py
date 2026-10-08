import math
import random
import re
from io import BytesIO
from pathlib import Path
from typing import cast

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from app.ai_service import get_ai_service
from app.image_search import search_image

ASSETS_DIR = Path("assets")
MEDIA_DIR = Path("media")
IMAGE_SIZE = 1080
_MAX_ALPHA = 255
WATERMARK = "@stephanie_thuller"
WATERMARK_IMAGE_PATH = ASSETS_DIR / "watermark.png"

FONTS = {
    "playfair": {
        "regular": ASSETS_DIR / "fonts" / "PlayfairDisplay.ttf",
        "italic": ASSETS_DIR / "fonts" / "PlayfairDisplay-Italic.ttf",
        "label": "Playfair (serifada)",
    },
    "montserrat": {
        "regular": ASSETS_DIR / "fonts" / "Montserrat.ttf",
        "italic": ASSETS_DIR / "fonts" / "Montserrat-Italic.ttf",
        "label": "Montserrat (moderna)",
    },
    "caveat": {
        "regular": ASSETS_DIR / "fonts" / "Caveat.ttf",
        "italic": ASSETS_DIR / "fonts" / "Caveat.ttf",
        "label": "Caveat (manuscrita)",
    },
    "alex_brush": {
        "regular": ASSETS_DIR / "fonts" / "AlexBrush.ttf",
        "italic": ASSETS_DIR / "fonts" / "AlexBrush.ttf",
        "label": "Alex Brush (caligrafia elegante)",
    },
}
DEFAULT_FONT_KEY = "playfair"

_HASHTAG_RE = re.compile(r"#\w+", re.UNICODE)
_ALLOWED_OVERLAY_CHARS = " .,!?:;'\"-()…–—«»“”‘’\n"


# ── helpers ──────────────────────────────────────────────────────────────────


def _clean_overlay_text(text: str) -> str:
    """Strip hashtags and glyphs the overlay font can't render (emoji, symbols)."""
    without_hashtags = _HASHTAG_RE.sub("", text)
    allowed = "".join(ch for ch in without_hashtags if ch.isalnum() or ch in _ALLOWED_OVERLAY_CHARS)
    return re.sub(r"\s+", " ", allowed).strip()


def _font(
    size: int, italic: bool = False, font_key: str = DEFAULT_FONT_KEY
) -> ImageFont.FreeTypeFont:
    variant = "italic" if italic else "regular"
    path = FONTS[font_key][variant]
    return ImageFont.truetype(str(path), size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = font.getbbox(test)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    shadow: tuple[int, int, int, int],
    offset: int = 3,
) -> None:
    draw.text((xy[0] + offset, xy[1] + offset), text, font=font, fill=shadow)
    draw.text(xy, text, font=font, fill=fill)


def _text_block_height(lines: list[str], font: ImageFont.FreeTypeFont, spacing: int) -> int:
    if not lines:
        return 0
    bbox = font.getbbox(lines[0])
    line_h = int(bbox[3] - bbox[1])
    return line_h * len(lines) + spacing * (len(lines) - 1)


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def _ov_color(overrides: dict[str, object], key: str, default_hex: str) -> tuple[int, int, int]:
    value = overrides.get(key)
    if isinstance(value, str) and _HEX_COLOR_RE.match(value):
        return _hex_to_rgb(value)
    return _hex_to_rgb(default_hex)


def _ov_int(overrides: dict[str, object], key: str, default: int, lo: int, hi: int) -> int:
    value = overrides.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi:
        return value
    return default


def _ov_float(
    overrides: dict[str, object], key: str, default: float, lo: float, hi: float
) -> float:
    value = overrides.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool) and lo <= value <= hi:
        return float(value)
    return default


def _ov_bool(overrides: dict[str, object], key: str, default: bool) -> bool:
    value = overrides.get(key)
    return value if isinstance(value, bool) else default


def _resolve_align(overrides: dict[str, object]) -> str:
    return "left" if overrides.get("text_align") == "left" else "center"


def _line_x(align: str, line_w: int, left: int, center: int) -> int:
    return left if align == "left" else center - line_w // 2


def _draw_star(
    draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill: tuple[int, ...]
) -> None:
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        radius = r if i % 2 == 0 else r * 0.45
        points.append((cx + radius * math.cos(angle), cy - radius * math.sin(angle)))
    draw.polygon(points, fill=fill)


def _draw_heart(
    draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill: tuple[int, ...]
) -> None:
    draw.ellipse([cx - r, cy - r, cx, cy + r * 0.2], fill=fill)
    draw.ellipse([cx, cy - r, cx + r, cy + r * 0.2], fill=fill)
    draw.polygon([(cx - r, cy), (cx + r, cy), (cx, cy + r * 1.3)], fill=fill)


def _draw_accents(
    draw: ImageDraw.ImageDraw,
    overrides: dict[str, object],
    box: tuple[float, float, float, float],
    color: tuple[int, int, int],
) -> None:
    """Small decorative stars/hearts flanking the quote text, drawn as plain shapes (not
    font glyphs — most of our fonts don't actually carry ★/♥ glyphs, they'd render as
    tofu boxes)."""
    kind = overrides.get("accent_decoration")
    if kind not in ("stars", "hearts"):
        return
    x0, y0, x1, y1 = box
    draw_fn = _draw_star if kind == "stars" else _draw_heart
    fill = (*color, 230)
    draw_fn(draw, x0 - 26, y0 - 22, 15, fill)
    draw_fn(draw, x1 + 24, y1 + 16, 15, fill)


def _draw_watermark_mark(
    overlay: Image.Image,
    draw: ImageDraw.ImageDraw,
    cx: int,
    y: int,
    font_key: str,
    size: int,
    rgb: tuple[int, int, int],
    alpha: int,
) -> None:
    """Draws the brand watermark centered at (cx, y) — the real logo image if
    assets/watermark.png has been provided, else the classic "@handle" text."""
    if WATERMARK_IMAGE_PATH.exists():
        logo = Image.open(WATERMARK_IMAGE_PATH).convert("RGBA")
        target_h = 52
        scale = target_h / logo.height
        logo = logo.resize((max(1, int(logo.width * scale)), target_h))
        if alpha < _MAX_ALPHA:
            logo.putalpha(logo.getchannel("A").point(lambda a: a * alpha // _MAX_ALPHA))
        overlay.alpha_composite(logo, (cx - logo.width // 2, y))
    else:
        wm_font = _font(size, font_key=font_key)
        bbox = wm_font.getbbox(WATERMARK)
        w = int(bbox[2] - bbox[0])
        draw.text((cx - w // 2, y), WATERMARK, font=wm_font, fill=(*rgb, alpha))


def _apply_background_adjustments(bg: Image.Image, overrides: dict[str, object]) -> Image.Image:
    """Continuous, composable background edits (not a closed filter list) — the AI picks
    which of these to set and by how much, so any photo-editing request it can reason
    about in these terms (brightness, contrast, saturation, warmth, blur, b&w, sepia) maps
    to a real Pillow operation instead of silently no-op'ing on an unrecognized name."""
    grayscale = _ov_bool(overrides, "bg_grayscale", False)
    sepia = _ov_bool(overrides, "bg_sepia", False)
    saturation = _ov_float(overrides, "bg_saturation", 1.0, 0.0, 2.0)
    brightness = _ov_float(overrides, "bg_brightness", 1.0, 0.3, 2.0)
    contrast = _ov_float(overrides, "bg_contrast", 1.0, 0.3, 2.0)
    warmth = _ov_float(overrides, "bg_warmth", 0.0, -1.0, 1.0)
    blur = _ov_int(overrides, "bg_blur", 0, 0, 20)

    if grayscale or sepia:
        gray = ImageOps.grayscale(bg)
        bg = (
            ImageOps.colorize(gray, black="#2b1b0e", white="#d8c39f").convert("RGB")
            if sepia
            else gray.convert("RGB")
        )
    if saturation != 1.0:
        bg = ImageEnhance.Color(bg).enhance(saturation)
    if brightness != 1.0:
        bg = ImageEnhance.Brightness(bg).enhance(brightness)
    if contrast != 1.0:
        bg = ImageEnhance.Contrast(bg).enhance(contrast)
    if warmth != 0.0:
        tint = (255, 170, 80) if warmth > 0 else (80, 140, 255)
        overlay = Image.new("RGB", bg.size, tint)
        bg = Image.blend(bg, overlay, min(abs(warmth), 1.0) * 0.35)
    if blur > 0:
        bg = bg.filter(ImageFilter.GaussianBlur(blur))
    return bg


# Single source of truth for each style's baked-in render values — used both as the
# fallback when resolving an override (see _ov_color/_ov_int call sites below) and to
# tell the AI what the *current* value actually is (see resolve_overrides). Without the
# latter, "make it more transparent" has no baseline to decrease from on the first round,
# since an empty overrides dict carries no information about where box_opacity starts.
STYLE_DEFAULTS: dict[str, dict[str, object]] = {
    "box": {
        "box_color": "#fdf5e6",
        "box_opacity": 220,
        "box_radius": 0,
        "box_width_pct": 0.72,
        "accent_color": "#643228",
        "text_color": "#3c1414",
        "text_size": 52,
        "text_line_spacing": 18,
        "text_vertical_offset": 0,
        "watermark_color": "#50281e",
        "watermark_opacity": 200,
        "watermark_size": 28,
        "text_align": "center",
        "text_uppercase": False,
        "accent_decoration": "none",
    },
    "bottom_dark": {
        "box_opacity": 180,
        "text_color": "#ffffff",
        "text_size": 54,
        "text_line_spacing": 16,
        "text_vertical_offset": 0,
        "text_shadow_opacity": 160,
        "watermark_color": "#dcdcdc",
        "watermark_opacity": 200,
        "watermark_size": 30,
        "text_align": "center",
        "text_uppercase": False,
        "accent_decoration": "none",
    },
    "light_border": {
        "box_color": "#ffffff",
        "box_opacity": 175,
        "box_radius": 0,
        "box_width_pct": 0.78,
        "accent_color": "#b4a096",
        "text_color": "#321e19",
        "text_size": 50,
        "text_line_spacing": 20,
        "text_vertical_offset": 0,
        "watermark_color": "#785046",
        "watermark_opacity": 200,
        "watermark_size": 26,
        "text_align": "center",
        "text_uppercase": False,
        "accent_decoration": "none",
    },
    "minimal": {
        "text_color": "#ffffff",
        "text_size": 58,
        "text_line_spacing": 20,
        "text_vertical_offset": 0,
        "text_shadow_opacity": 200,
        "watermark_color": "#f0f0f0",
        "watermark_opacity": 200,
        "watermark_size": 30,
        "text_align": "center",
        "text_uppercase": False,
        "accent_decoration": "none",
    },
}

BACKGROUND_DEFAULTS: dict[str, object] = {
    "bg_grayscale": False,
    "bg_sepia": False,
    "bg_saturation": 1.0,
    "bg_brightness": 1.0,
    "bg_contrast": 1.0,
    "bg_warmth": 0.0,
    "bg_blur": 0,
}


def resolve_overrides(style_key: str, overrides: dict[str, object]) -> dict[str, object]:
    """Merge a style's defaults with whatever has already been overridden, so the result
    always has concrete current values — not just the keys the user happened to touch."""
    return {**STYLE_DEFAULTS.get(style_key, {}), **BACKGROUND_DEFAULTS, **overrides}


# ── 4 overlay styles ──────────────────────────────────────────────────────────


def _style_box(
    img: Image.Image,
    text: str,
    watermark: bool,
    font_key: str = DEFAULT_FONT_KEY,
    overrides: dict[str, object] | None = None,
) -> Image.Image:
    """White/cream semi-transparent box with decorative quotes, centered."""
    ov = overrides or {}
    out = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    d = STYLE_DEFAULTS["box"]
    box_rgb = _ov_color(ov, "box_color", cast(str, d["box_color"]))
    box_alpha = _ov_int(ov, "box_opacity", cast(int, d["box_opacity"]), 0, 255)
    box_radius = _ov_int(ov, "box_radius", cast(int, d["box_radius"]), 0, 60)
    box_width_pct = _ov_float(ov, "box_width_pct", cast(float, d["box_width_pct"]), 0.4, 0.95)
    accent_rgb = _ov_color(ov, "accent_color", cast(str, d["accent_color"]))
    text_rgb = _ov_color(ov, "text_color", cast(str, d["text_color"]))
    align = _resolve_align(ov)
    if _ov_bool(ov, "text_uppercase", cast(bool, d["text_uppercase"])):
        text = text.upper()

    pad = 60
    box_w = int(IMAGE_SIZE * box_width_pct)
    text_size = _ov_int(ov, "text_size", cast(int, d["text_size"]), 24, 90)
    font = _font(text_size, font_key=font_key)
    spacing = _ov_int(ov, "text_line_spacing", cast(int, d["text_line_spacing"]), 4, 50)
    lines = _wrap(text, font, box_w - pad * 2)
    text_h = _text_block_height(lines, font, spacing)
    box_h = text_h + pad * 3
    bx = (IMAGE_SIZE - box_w) // 2
    v_offset = _ov_int(ov, "text_vertical_offset", cast(int, d["text_vertical_offset"]), -200, 200)
    by = (IMAGE_SIZE - box_h) // 2 + v_offset

    draw.rounded_rectangle(
        [bx, by, bx + box_w, by + box_h], radius=box_radius, fill=(*box_rgb, box_alpha)
    )
    lw = 2
    draw.rounded_rectangle(
        [bx + lw, by + lw, bx + box_w - lw, by + box_h - lw],
        radius=max(box_radius - lw, 0),
        outline=(*accent_rgb, 200),
        width=lw,
    )

    q_font = _font(90, italic=True, font_key=font_key)
    draw.text((bx + 12, by - 20), "“", font=q_font, fill=(*accent_rgb, 180))
    draw.text((bx + box_w - 65, by + box_h - 55), "”", font=q_font, fill=(*accent_rgb, 180))

    y = by + pad
    bbox0 = font.getbbox(lines[0])
    line_h = int(bbox0[3] - bbox0[1])
    max_line_w = 0
    for line in lines:
        lbbox = font.getbbox(line)
        lw2 = int(lbbox[2] - lbbox[0])
        max_line_w = max(max_line_w, lw2)
        x = _line_x(align, lw2, bx + pad, bx + box_w // 2)
        draw.text((x, y), line, font=font, fill=(*text_rgb, 255))
        y += line_h + spacing

    text_left = bx + pad if align == "left" else bx + (box_w - max_line_w) // 2
    _draw_accents(draw, ov, (text_left, by + pad, text_left + max_line_w, y - spacing), text_rgb)

    if watermark:
        wm_rgb = _ov_color(ov, "watermark_color", cast(str, d["watermark_color"]))
        wm_alpha = _ov_int(ov, "watermark_opacity", cast(int, d["watermark_opacity"]), 0, 255)
        wm_size = _ov_int(ov, "watermark_size", cast(int, d["watermark_size"]), 14, 60)
        _draw_watermark_mark(
            overlay, draw, bx + box_w // 2, by + box_h + 16, font_key, wm_size, wm_rgb, wm_alpha
        )

    return Image.alpha_composite(out, overlay).convert("RGB")


def _style_bottom_dark(
    img: Image.Image,
    text: str,
    watermark: bool,
    font_key: str = DEFAULT_FONT_KEY,
    overrides: dict[str, object] | None = None,
) -> Image.Image:
    """Dark gradient overlay on lower half, white text with shadow."""
    ov = overrides or {}
    out = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    d = STYLE_DEFAULTS["bottom_dark"]
    peak_alpha = _ov_int(ov, "box_opacity", cast(int, d["box_opacity"]), 0, 255)
    text_rgb = _ov_color(ov, "text_color", cast(str, d["text_color"]))
    align = _resolve_align(ov)
    if _ov_bool(ov, "text_uppercase", cast(bool, d["text_uppercase"])):
        text = text.upper()

    grad_h = IMAGE_SIZE // 2
    for i in range(grad_h):
        alpha = int(peak_alpha * (i / grad_h))
        draw.line(
            [(0, IMAGE_SIZE - grad_h + i), (IMAGE_SIZE, IMAGE_SIZE - grad_h + i)],
            fill=(0, 0, 0, alpha),
        )

    text_size = _ov_int(ov, "text_size", cast(int, d["text_size"]), 24, 90)
    font = _font(text_size, font_key=font_key)
    spacing = _ov_int(ov, "text_line_spacing", cast(int, d["text_line_spacing"]), 4, 50)
    shadow_alpha = _ov_int(ov, "text_shadow_opacity", cast(int, d["text_shadow_opacity"]), 0, 255)
    pad = 70
    max_w = IMAGE_SIZE - pad * 2
    lines = _wrap(text, font, max_w)
    text_h = _text_block_height(lines, font, spacing)
    bbox0 = font.getbbox(lines[0])
    line_h = int(bbox0[3] - bbox0[1])
    v_offset = _ov_int(ov, "text_vertical_offset", cast(int, d["text_vertical_offset"]), -200, 200)
    y = IMAGE_SIZE - text_h - (80 if watermark else 55) + v_offset
    text_top = y

    max_line_w = 0
    for line in lines:
        lbbox = font.getbbox(line)
        lw = int(lbbox[2] - lbbox[0])
        max_line_w = max(max_line_w, lw)
        x = _line_x(align, lw, pad, IMAGE_SIZE // 2)
        _draw_text_with_shadow(
            draw, (x, y), line, font, fill=(*text_rgb, 255), shadow=(0, 0, 0, shadow_alpha)
        )
        y += line_h + spacing

    text_left = pad if align == "left" else (IMAGE_SIZE - max_line_w) // 2
    _draw_accents(draw, ov, (text_left, text_top, text_left + max_line_w, y - spacing), text_rgb)

    if watermark:
        wm_rgb = _ov_color(ov, "watermark_color", cast(str, d["watermark_color"]))
        wm_alpha = _ov_int(ov, "watermark_opacity", cast(int, d["watermark_opacity"]), 0, 255)
        wm_size = _ov_int(ov, "watermark_size", cast(int, d["watermark_size"]), 14, 60)
        _draw_watermark_mark(
            overlay, draw, IMAGE_SIZE // 2, y + 10, font_key, wm_size, wm_rgb, wm_alpha
        )

    return Image.alpha_composite(out, overlay).convert("RGB")


def _style_light_border(
    img: Image.Image,
    text: str,
    watermark: bool,
    font_key: str = DEFAULT_FONT_KEY,
    overrides: dict[str, object] | None = None,
) -> Image.Image:
    """Light frosted overlay centered, dark text, thin border frame."""
    ov = overrides or {}
    out = img.copy().convert("RGBA")
    blurred = out.filter(ImageFilter.GaussianBlur(12))
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    d = STYLE_DEFAULTS["light_border"]
    box_rgb = _ov_color(ov, "box_color", cast(str, d["box_color"]))
    box_alpha = _ov_int(ov, "box_opacity", cast(int, d["box_opacity"]), 0, 255)
    box_radius = _ov_int(ov, "box_radius", cast(int, d["box_radius"]), 0, 60)
    box_width_pct = _ov_float(ov, "box_width_pct", cast(float, d["box_width_pct"]), 0.4, 0.95)
    accent_rgb = _ov_color(ov, "accent_color", cast(str, d["accent_color"]))
    text_rgb = _ov_color(ov, "text_color", cast(str, d["text_color"]))
    align = _resolve_align(ov)
    if _ov_bool(ov, "text_uppercase", cast(bool, d["text_uppercase"])):
        text = text.upper()

    pad = 55
    box_w = int(IMAGE_SIZE * box_width_pct)
    text_size = _ov_int(ov, "text_size", cast(int, d["text_size"]), 24, 90)
    font = _font(text_size, italic=True, font_key=font_key)
    spacing = _ov_int(ov, "text_line_spacing", cast(int, d["text_line_spacing"]), 4, 50)
    lines = _wrap(text, font, box_w - pad * 2)
    text_h = _text_block_height(lines, font, spacing)
    box_h = text_h + pad * 2 + (40 if watermark else 0)
    bx = (IMAGE_SIZE - box_w) // 2
    v_offset = _ov_int(ov, "text_vertical_offset", cast(int, d["text_vertical_offset"]), -200, 200)
    by = (IMAGE_SIZE - box_h) // 2 + v_offset

    draw.rounded_rectangle(
        [bx, by, bx + box_w, by + box_h], radius=box_radius, fill=(*box_rgb, box_alpha)
    )
    draw.rounded_rectangle(
        [bx + 8, by + 8, bx + box_w - 8, by + box_h - 8],
        radius=max(box_radius - 8, 0),
        outline=(*accent_rgb, 220),
        width=1,
    )

    bbox0 = font.getbbox(lines[0])
    line_h = int(bbox0[3] - bbox0[1])
    y = by + pad
    max_line_w = 0
    for line in lines:
        lbbox = font.getbbox(line)
        lw = int(lbbox[2] - lbbox[0])
        max_line_w = max(max_line_w, lw)
        x = _line_x(align, lw, bx + pad, bx + box_w // 2)
        draw.text((x, y), line, font=font, fill=(*text_rgb, 255))
        y += line_h + spacing

    text_left = bx + pad if align == "left" else bx + (box_w - max_line_w) // 2
    _draw_accents(draw, ov, (text_left, by + pad, text_left + max_line_w, y - spacing), text_rgb)

    if watermark:
        wm_rgb = _ov_color(ov, "watermark_color", cast(str, d["watermark_color"]))
        wm_alpha = _ov_int(ov, "watermark_opacity", cast(int, d["watermark_opacity"]), 0, 255)
        wm_size = _ov_int(ov, "watermark_size", cast(int, d["watermark_size"]), 14, 60)
        _draw_watermark_mark(
            overlay, draw, bx + box_w // 2, y + 6, font_key, wm_size, wm_rgb, wm_alpha
        )

    merged = Image.alpha_composite(blurred, overlay)
    result = Image.alpha_composite(out, Image.new("RGBA", out.size, (0, 0, 0, 0)))
    mask = overlay.split()[3]
    result.paste(merged, mask=mask)
    return result.convert("RGB")


def _style_minimal(
    img: Image.Image,
    text: str,
    watermark: bool,
    font_key: str = DEFAULT_FONT_KEY,
    overrides: dict[str, object] | None = None,
) -> Image.Image:
    """Text centered directly over image with subtle shadow, no box."""
    ov = overrides or {}
    out = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    d = STYLE_DEFAULTS["minimal"]
    text_rgb = _ov_color(ov, "text_color", cast(str, d["text_color"]))
    align = _resolve_align(ov)
    if _ov_bool(ov, "text_uppercase", cast(bool, d["text_uppercase"])):
        text = text.upper()

    text_size = _ov_int(ov, "text_size", cast(int, d["text_size"]), 24, 90)
    font = _font(text_size, font_key=font_key)
    spacing = _ov_int(ov, "text_line_spacing", cast(int, d["text_line_spacing"]), 4, 50)
    shadow_alpha = _ov_int(ov, "text_shadow_opacity", cast(int, d["text_shadow_opacity"]), 0, 255)
    pad = 80
    lines = _wrap(text, font, IMAGE_SIZE - pad * 2)
    text_h = _text_block_height(lines, font, spacing)
    bbox0 = font.getbbox(lines[0])
    line_h = int(bbox0[3] - bbox0[1])
    v_offset = _ov_int(ov, "text_vertical_offset", cast(int, d["text_vertical_offset"]), -200, 200)
    y = (IMAGE_SIZE - text_h) // 2 + v_offset
    text_top = y

    max_line_w = 0
    for line in lines:
        lbbox = font.getbbox(line)
        lw = int(lbbox[2] - lbbox[0])
        max_line_w = max(max_line_w, lw)
        x = _line_x(align, lw, pad, IMAGE_SIZE // 2)
        _draw_text_with_shadow(
            draw,
            (x, y),
            line,
            font,
            fill=(*text_rgb, 255),
            shadow=(0, 0, 0, shadow_alpha),
            offset=4,
        )
        y += line_h + spacing

    text_left = pad if align == "left" else (IMAGE_SIZE - max_line_w) // 2
    _draw_accents(draw, ov, (text_left, text_top, text_left + max_line_w, y - spacing), text_rgb)

    if watermark:
        wm_rgb = _ov_color(ov, "watermark_color", cast(str, d["watermark_color"]))
        wm_alpha = _ov_int(ov, "watermark_opacity", cast(int, d["watermark_opacity"]), 0, 255)
        wm_size = _ov_int(ov, "watermark_size", cast(int, d["watermark_size"]), 14, 60)
        _draw_watermark_mark(
            overlay, draw, IMAGE_SIZE // 2, IMAGE_SIZE - 55, font_key, wm_size, wm_rgb, wm_alpha
        )

    return Image.alpha_composite(out, overlay).convert("RGB")


_STYLES = {
    "box": _style_box,
    "bottom_dark": _style_bottom_dark,
    "light_border": _style_light_border,
    "minimal": _style_minimal,
}
STYLE_LABELS = {
    "box": "Caixa opaca",
    "bottom_dark": "Gradiente escuro",
    "light_border": "Borda clara (efeito vidro)",
    "minimal": "Texto livre",
}
DEFAULT_STYLE_KEY = "minimal"

# Curated looks (base style + a tasteful bundle of the overrides above) — sampled
# randomly for the wizard's style-preview step so it doesn't render the same 4 plain
# defaults every time. Curated rather than fully random per-knob, so every combination
# still reads clearly (legible text, no color clashing with the overlay text).
STYLE_PRESETS: list[dict[str, object]] = [
    # Presets gerais (variedade) — mantidos por combinarem com a paleta quente/sóbria dela.
    {"style": "minimal", "label": "Clássico", "overrides": {}},
    {"style": "box", "label": "Caixa Creme", "overrides": {}},
    {"style": "bottom_dark", "label": "Gradiente Noturno", "overrides": {}},
    {"style": "light_border", "label": "Vidro Fosco", "overrides": {}},
    {
        "style": "box",
        "label": "Vintage Sépia",
        "overrides": {
            "bg_sepia": True,
            "box_color": "#3a2b1d",
            "box_opacity": 180,
            "text_color": "#f4e4bc",
            "accent_color": "#d8c39f",
        },
    },
    {
        "style": "bottom_dark",
        "label": "Pôr do Sol Quente",
        "overrides": {"bg_warmth": 0.6, "bg_saturation": 1.3, "box_opacity": 140},
    },
    {
        "style": "light_border",
        "label": "Pastel Suave",
        "overrides": {
            "bg_saturation": 0.6,
            "bg_brightness": 1.15,
            "box_color": "#fef6f0",
            "box_radius": 30,
            "text_color": "#5a4a42",
        },
    },
    {
        "style": "bottom_dark",
        "label": "Desfoque Suave",
        "overrides": {"bg_blur": 6, "box_opacity": 200},
    },
    {
        "style": "light_border",
        "label": "Dourado Elegante",
        "overrides": {"accent_color": "#c9a227", "box_color": "#fffdf5", "text_color": "#2b2b2b"},
    },
    {
        "style": "minimal",
        "label": "Golden Hour",
        "overrides": {
            "bg_warmth": 0.75,
            "bg_saturation": 1.15,
            "bg_brightness": 1.1,
            "text_color": "#fff4dc",
            "text_shadow_opacity": 180,
        },
    },
    # Modelados diretamente nas referências reais do perfil dela (tmp/Image (1-8).jpeg):
    # sem caixa, fundo aproximado de papel/neutro, texto alinhado à esquerda — escolha a
    # fonte "Alex Brush" no passo 3 para reproduzir a caligrafia das imagens 6/7.
    {
        "style": "minimal",
        "label": "Papel Neutro",
        "overrides": {
            "bg_saturation": 0.25,
            "bg_brightness": 1.2,
            "bg_warmth": 0.15,
            "bg_blur": 14,
            "text_color": "#2b2420",
            "text_align": "left",
            "text_size": 40,
            "text_line_spacing": 14,
            "text_shadow_opacity": 0,
        },
    },
    {
        "style": "minimal",
        "label": "Caligrafia Manuscrita",
        "overrides": {
            "bg_saturation": 0.3,
            "bg_brightness": 1.15,
            "bg_warmth": 0.15,
            "bg_blur": 16,
            "text_color": "#1a1a1a",
            "text_align": "left",
            "text_size": 46,
            "text_line_spacing": 10,
            "text_shadow_opacity": 0,
        },
    },
    {
        "style": "minimal",
        "label": "Afirmação Vinho",
        "overrides": {
            "bg_saturation": 0.2,
            "bg_brightness": 1.15,
            "bg_blur": 18,
            "text_color": "#5c2a2a",
            "text_uppercase": True,
            "text_align": "center",
            "text_size": 50,
            "text_shadow_opacity": 0,
        },
    },
    {
        "style": "minimal",
        "label": "Legenda com Estrelas",
        "overrides": {
            "text_color": "#ffffff",
            "text_align": "left",
            "text_size": 62,
            "text_shadow_opacity": 210,
            "accent_decoration": "stars",
        },
    },
]


# ── public API ────────────────────────────────────────────────────────────────


def _search_query(topic: str | None, post_content: str) -> str:
    keywords = get_ai_service().extract_image_keywords(topic, post_content)
    return keywords or topic or "abstract aesthetic background"


def _load_background(img_bytes: bytes) -> Image.Image:
    return (
        Image.open(BytesIO(img_bytes))
        .convert("RGB")
        .resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
    )


def generate_post_image(
    post_id: int, post_content: str, topic: str | None = None, watermark: bool = True
) -> Path:
    query = _search_query(topic, post_content)
    img_bytes = search_image(query)
    bg = _load_background(img_bytes)

    style_fn = random.choice(list(_STYLES.values()))
    result = style_fn(bg, _clean_overlay_text(post_content), watermark)

    out_path = MEDIA_DIR / f"{post_id}.png"
    result.save(str(out_path), "PNG", optimize=True)
    return out_path


def compose_wizard_image(
    file_stem: str,
    image_bytes: bytes,
    phrase: str,
    font_key: str,
    style_key: str,
    watermark: bool = True,
    overrides: dict[str, object] | None = None,
) -> Path:
    """Render phrase + chosen style/font onto image_bytes, saved under a caller-chosen
    filename stem (not a Post id — the wizard composes the image before the Post exists
    so a single DB write can happen only after the image is known to succeed)."""
    bg = _load_background(image_bytes)
    bg = _apply_background_adjustments(bg, overrides or {})
    style_fn = _STYLES[style_key]
    result = style_fn(
        bg, _clean_overlay_text(phrase), watermark, font_key=font_key, overrides=overrides
    )

    out_path = MEDIA_DIR / f"{file_stem}.png"
    result.save(str(out_path), "PNG", optimize=True)
    return out_path
