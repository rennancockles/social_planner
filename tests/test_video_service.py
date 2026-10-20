import io
import shutil

import pytest
from PIL import Image

from app.image_service import IMAGE_SIZE
from app.video_service import (
    MIN_DURATION,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    _pad_background,
    _pad_overlay,
    render_post_video,
    validate_audio_bytes,
)

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


@pytest.mark.unit
def test_pad_background_centers_square_on_vertical_canvas():
    square = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (10, 20, 30))
    padded = _pad_background(square)

    assert padded.size == (VIDEO_WIDTH, VIDEO_HEIGHT)
    offset_y = (VIDEO_HEIGHT - IMAGE_SIZE) // 2
    assert padded.getpixel((IMAGE_SIZE // 2, offset_y + IMAGE_SIZE // 2)) == (10, 20, 30)


@pytest.mark.unit
def test_pad_overlay_is_transparent_in_the_letterbox_bars():
    overlay = Image.new("RGBA", (IMAGE_SIZE, IMAGE_SIZE), (255, 0, 0, 255))
    padded = _pad_overlay(overlay)

    assert padded.size == (VIDEO_WIDTH, VIDEO_HEIGHT)
    assert padded.getpixel((0, 0))[3] == 0
    offset_y = (VIDEO_HEIGHT - IMAGE_SIZE) // 2
    assert padded.getpixel((IMAGE_SIZE // 2, offset_y + IMAGE_SIZE // 2)) == (255, 0, 0, 255)


@pytest.mark.unit
def test_validate_audio_bytes_rejects_garbage():
    assert validate_audio_bytes(b"this is definitely not an audio file") is False


@pytest.mark.integration
@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg is not installed")
def test_render_post_video_produces_a_playable_mp4():
    buf = io.BytesIO()
    Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (200, 150, 100)).save(buf, "PNG")

    out_path = render_post_video(
        out_stem="test_render_post_video_tmp",
        image_bytes=buf.getvalue(),
        phrase="Uma frase de teste",
        font_key="playfair",
        style_key="minimal",
        watermark=False,
        duration=MIN_DURATION,
    )
    try:
        assert out_path.exists()
        assert out_path.stat().st_size > 0
    finally:
        out_path.unlink(missing_ok=True)
