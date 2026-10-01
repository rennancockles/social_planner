import base64
import random
from io import BytesIO
from pathlib import Path

import httpx2
import openai
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.settings import settings

ASSETS_DIR = Path("assets")
MEDIA_DIR = Path("media")
FONT_REGULAR = ASSETS_DIR / "fonts" / "PlayfairDisplay.ttf"
FONT_ITALIC = ASSETS_DIR / "fonts" / "PlayfairDisplay-Italic.ttf"
IMAGE_SIZE = 1080
WATERMARK = "@stephanie_thuller"


# ── helpers ──────────────────────────────────────────────────────────────────


def _font(size: int, italic: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_ITALIC if italic else FONT_REGULAR
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


# ── 4 overlay styles ──────────────────────────────────────────────────────────


def _style_box(img: Image.Image, text: str, watermark: bool) -> Image.Image:
    """White/cream semi-transparent box with decorative quotes, centered."""
    out = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pad = 60
    box_w = int(IMAGE_SIZE * 0.72)
    font = _font(52)
    lines = _wrap(text, font, box_w - pad * 2)
    spacing = 18
    text_h = _text_block_height(lines, font, spacing)
    box_h = text_h + pad * 3
    bx = (IMAGE_SIZE - box_w) // 2
    by = (IMAGE_SIZE - box_h) // 2

    draw.rectangle([bx, by, bx + box_w, by + box_h], fill=(253, 245, 230, 220))
    border_color = (100, 50, 40, 200)
    lw = 2
    draw.rectangle(
        [bx + lw, by + lw, bx + box_w - lw, by + box_h - lw], outline=border_color, width=lw
    )

    q_font = _font(90, italic=True)
    draw.text((bx + 12, by - 20), "“", font=q_font, fill=(*border_color[:3], 180))
    draw.text((bx + box_w - 65, by + box_h - 55), "”", font=q_font, fill=(*border_color[:3], 180))

    y = by + pad
    bbox0 = font.getbbox(lines[0])
    line_h = int(bbox0[3] - bbox0[1])
    for line in lines:
        lbbox = font.getbbox(line)
        lw2 = int(lbbox[2] - lbbox[0])
        x = bx + (box_w - lw2) // 2
        draw.text((x, y), line, font=font, fill=(60, 20, 20, 255))
        y += line_h + spacing

    if watermark:
        wm_font = _font(28)
        wm_bbox = wm_font.getbbox(WATERMARK)
        wm_w = int(wm_bbox[2] - wm_bbox[0])
        wx = bx + (box_w - wm_w) // 2
        draw.text((wx, by + box_h + 16), WATERMARK, font=wm_font, fill=(80, 40, 30, 200))

    return Image.alpha_composite(out, overlay).convert("RGB")


def _style_bottom_dark(img: Image.Image, text: str, watermark: bool) -> Image.Image:
    """Dark gradient overlay on lower half, white text with shadow."""
    out = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    grad_h = IMAGE_SIZE // 2
    for i in range(grad_h):
        alpha = int(180 * (i / grad_h))
        draw.line(
            [(0, IMAGE_SIZE - grad_h + i), (IMAGE_SIZE, IMAGE_SIZE - grad_h + i)],
            fill=(0, 0, 0, alpha),
        )

    font = _font(54)
    pad = 70
    max_w = IMAGE_SIZE - pad * 2
    lines = _wrap(text, font, max_w)
    spacing = 16
    text_h = _text_block_height(lines, font, spacing)
    bbox0 = font.getbbox(lines[0])
    line_h = int(bbox0[3] - bbox0[1])
    y = IMAGE_SIZE - text_h - (80 if watermark else 55)

    for line in lines:
        lbbox = font.getbbox(line)
        lw = int(lbbox[2] - lbbox[0])
        x = (IMAGE_SIZE - lw) // 2
        _draw_text_with_shadow(
            draw, (x, y), line, font, fill=(255, 255, 255, 255), shadow=(0, 0, 0, 160)
        )
        y += line_h + spacing

    if watermark:
        wm_font = _font(30)
        wm_bbox = wm_font.getbbox(WATERMARK)
        wm_w = int(wm_bbox[2] - wm_bbox[0])
        wx = (IMAGE_SIZE - wm_w) // 2
        draw.text((wx, y + 10), WATERMARK, font=wm_font, fill=(220, 220, 220, 200))

    return Image.alpha_composite(out, overlay).convert("RGB")


def _style_light_border(img: Image.Image, text: str, watermark: bool) -> Image.Image:
    """Light frosted overlay centered, dark text, thin border frame."""
    out = img.copy().convert("RGBA")
    blurred = out.filter(ImageFilter.GaussianBlur(12))
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pad = 55
    box_w = int(IMAGE_SIZE * 0.78)
    font = _font(50, italic=True)
    lines = _wrap(text, font, box_w - pad * 2)
    spacing = 20
    text_h = _text_block_height(lines, font, spacing)
    box_h = text_h + pad * 2 + (40 if watermark else 0)
    bx = (IMAGE_SIZE - box_w) // 2
    by = (IMAGE_SIZE - box_h) // 2

    draw.rectangle([bx, by, bx + box_w, by + box_h], fill=(255, 255, 255, 175))
    draw.rectangle(
        [bx + 8, by + 8, bx + box_w - 8, by + box_h - 8], outline=(180, 160, 150, 220), width=1
    )

    bbox0 = font.getbbox(lines[0])
    line_h = int(bbox0[3] - bbox0[1])
    y = by + pad
    for line in lines:
        lbbox = font.getbbox(line)
        lw = int(lbbox[2] - lbbox[0])
        x = bx + (box_w - lw) // 2
        draw.text((x, y), line, font=font, fill=(50, 30, 25, 255))
        y += line_h + spacing

    if watermark:
        wm_font = _font(26)
        wm_bbox = wm_font.getbbox(WATERMARK)
        wm_w = int(wm_bbox[2] - wm_bbox[0])
        wx = bx + (box_w - wm_w) // 2
        draw.text((wx, y + 6), WATERMARK, font=wm_font, fill=(120, 80, 70, 200))

    merged = Image.alpha_composite(blurred, overlay)
    result = Image.alpha_composite(out, Image.new("RGBA", out.size, (0, 0, 0, 0)))
    mask = overlay.split()[3]
    result.paste(merged, mask=mask)
    return result.convert("RGB")


def _style_minimal(img: Image.Image, text: str, watermark: bool) -> Image.Image:
    """Text centered directly over image with subtle shadow, no box."""
    out = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = _font(58)
    pad = 80
    lines = _wrap(text, font, IMAGE_SIZE - pad * 2)
    spacing = 20
    text_h = _text_block_height(lines, font, spacing)
    bbox0 = font.getbbox(lines[0])
    line_h = int(bbox0[3] - bbox0[1])
    y = (IMAGE_SIZE - text_h) // 2

    for line in lines:
        lbbox = font.getbbox(line)
        lw = int(lbbox[2] - lbbox[0])
        x = (IMAGE_SIZE - lw) // 2
        _draw_text_with_shadow(
            draw, (x, y), line, font, fill=(255, 255, 255, 255), shadow=(0, 0, 0, 200), offset=4
        )
        y += line_h + spacing

    if watermark:
        wm_font = _font(30)
        wm_bbox = wm_font.getbbox(WATERMARK)
        wm_w = int(wm_bbox[2] - wm_bbox[0])
        wx = (IMAGE_SIZE - wm_w) // 2
        draw.text((wx, IMAGE_SIZE - 55), WATERMARK, font=wm_font, fill=(240, 240, 240, 200))

    return Image.alpha_composite(out, overlay).convert("RGB")


_STYLES = [_style_box, _style_bottom_dark, _style_light_border, _style_minimal]


# ── public API ────────────────────────────────────────────────────────────────


def _dalle_prompt(post_content: str) -> str:
    short = post_content[:300]
    return (
        f"Create a beautiful, artistic background image for a social media post with this theme: "
        f"{short}. "
        "The image must have NO text, letters, words, or writing of any kind. "
        "Aesthetic: soft, ethereal, warm tones. "
        "Style: fine art photography or painterly illustration. "
        "Square format 1:1."
    )


def generate_post_image(post_id: int, post_content: str, watermark: bool = True) -> Path:
    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.images.generate(  # type: ignore[call-overload]
        model=settings.openai_image_model,
        prompt=_dalle_prompt(post_content),
        size=settings.openai_image_size,
        quality=settings.openai_image_quality,
        n=1,
    )
    if not response.data:
        raise RuntimeError("Image generation did not return data.")

    item = response.data[0]
    if item.b64_json:
        img_bytes = base64.b64decode(item.b64_json)
    elif item.url:
        with httpx2.Client(timeout=30) as http:
            r = http.get(item.url)
            r.raise_for_status()
        img_bytes = r.content
    else:
        raise RuntimeError("Image generation returned neither b64_json nor url.")

    bg = Image.open(BytesIO(img_bytes)).resize(
        (IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS
    )

    style_fn = random.choice(_STYLES)
    result = style_fn(bg, post_content, watermark)

    out_path = MEDIA_DIR / f"{post_id}.png"
    result.save(str(out_path), "PNG", optimize=True)
    return out_path
