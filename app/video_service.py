import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

from app.image_service import MEDIA_DIR, render_wizard_layers

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
DEFAULT_DURATION = 6.0
MIN_DURATION = 2.0
MAX_DURATION = 15.0

_BACKGROUND_BLUR_RADIUS = 40
_MAX_ZOOM = 1.08
_ZOOM_STEP_PER_FRAME = 0.0006
_FFMPEG_TIMEOUT_SECONDS = 180
_FFPROBE_TIMEOUT_SECONDS = 10


class VideoGenerationError(RuntimeError):
    """Raised when ffmpeg is missing or fails to render — carries a user-facing message."""


def _pad_background(square_rgb: Image.Image) -> Image.Image:
    """Pads a square background onto the vertical reel canvas by stretching a blurred copy
    of itself into the letterbox bars, so the edges read as an intentional crop rather
    than plain black bars."""
    canvas = square_rgb.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)
    canvas = canvas.filter(ImageFilter.GaussianBlur(_BACKGROUND_BLUR_RADIUS))
    offset_y = (VIDEO_HEIGHT - square_rgb.height) // 2
    canvas.paste(square_rgb, (0, offset_y))
    return canvas


def _pad_overlay(square_rgba: Image.Image) -> Image.Image:
    """Pads the transparent text/box overlay onto the vertical canvas at the same
    vertical offset as _pad_background, so the two layers line up when composited."""
    canvas = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
    offset_y = (VIDEO_HEIGHT - square_rgba.height) // 2
    canvas.alpha_composite(square_rgba, (0, offset_y))
    return canvas


def validate_audio_bytes(data: bytes) -> bool:
    """Confirms ffmpeg can actually decode an uploaded "audio" file — content-type
    headers are client-supplied and not trustworthy on their own."""
    with tempfile.NamedTemporaryFile(suffix=".audio") as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    tmp.name,
                ],
                check=True,
                capture_output=True,
                timeout=_FFPROBE_TIMEOUT_SECONDS,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False
    return True


def render_post_video(  # noqa: PLR0913
    *,
    out_stem: str,
    image_bytes: bytes,
    phrase: str,
    font_key: str,
    style_key: str,
    overrides: dict[str, object] | None = None,
    watermark: bool = True,
    audio_bytes: bytes | None = None,
    duration: float = DEFAULT_DURATION,
) -> Path:
    """Renders a short vertical (9:16) mp4: the background slowly zooms in (Ken Burns)
    while the phrase/box overlay stays static on top of it, matching how the static
    wizard image already looks — then optionally mixes in a user-supplied music track."""
    bg, overlay = render_wizard_layers(
        image_bytes, phrase, font_key, style_key, watermark=watermark, overrides=overrides
    )
    canvas_bg = _pad_background(bg)
    canvas_overlay = _pad_overlay(overlay)

    out_path = MEDIA_DIR / f"{out_stem}.mp4"
    with tempfile.TemporaryDirectory(dir=MEDIA_DIR) as tmp_dir:
        tmp = Path(tmp_dir)
        bg_path = tmp / "bg.png"
        overlay_path = tmp / "overlay.png"
        canvas_bg.save(bg_path, "PNG")
        canvas_overlay.save(overlay_path, "PNG")

        total_frames = int(duration * VIDEO_FPS)
        zoompan = (
            f"zoompan=z='min(zoom+{_ZOOM_STEP_PER_FRAME},{_MAX_ZOOM})':"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(bg_path),
            "-loop",
            "1",
            "-i",
            str(overlay_path),
        ]

        audio_path = None
        if audio_bytes is not None:
            audio_path = tmp / "audio.input"
            audio_path.write_bytes(audio_bytes)
            cmd += ["-stream_loop", "-1", "-i", str(audio_path)]

        cmd += [
            "-filter_complex",
            f"[0:v]{zoompan}[bg];[bg][1:v]overlay[v]",
            "-map",
            "[v]",
        ]
        if audio_path is not None:
            cmd += ["-map", "2:a", "-c:a", "aac", "-b:a", "128k", "-shortest"]

        cmd += [
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=_FFMPEG_TIMEOUT_SECONDS)
        except FileNotFoundError as e:
            raise VideoGenerationError("ffmpeg não está instalado neste servidor.") from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode(errors="replace") if e.stderr else ""
            raise VideoGenerationError(f"Falha ao renderizar o vídeo: {stderr[-500:]}") from e
        except subprocess.TimeoutExpired as e:
            raise VideoGenerationError("Tempo limite excedido ao renderizar o vídeo.") from e

    return out_path
