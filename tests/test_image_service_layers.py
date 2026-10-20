import io

import pytest
from PIL import Image

from app.image_service import IMAGE_SIZE, render_wizard_layers

pytestmark = pytest.mark.unit


def _png_bytes(size: int, color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, "PNG")
    return buf.getvalue()


def test_render_wizard_layers_keeps_background_and_overlay_separate():
    background, overlay = render_wizard_layers(
        _png_bytes(400, (10, 20, 30)),
        "Uma frase qualquer",
        "playfair",
        "minimal",
        watermark=False,
    )

    assert background.size == (IMAGE_SIZE, IMAGE_SIZE)
    assert overlay.size == (IMAGE_SIZE, IMAGE_SIZE)
    assert overlay.mode == "RGBA"
    # Corners are far from the centered text/box, so they must stay fully transparent —
    # that's what lets a video exporter composite this layer over an animated background.
    assert overlay.getpixel((2, 2))[3] == 0
