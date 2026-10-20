import io
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from app.image_service import compose_wizard_image, wizard_background_path
from app.models import Platform, Post, Profile, Tone

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


def _make_profile(session: Session) -> None:
    session.add(
        Profile(
            name="Perfil de Teste",
            niche="bem-estar",
            tone=Tone.inspirational,
            platform=Platform.instagram,
            audience_description="mulheres 25-40",
        )
    )
    session.commit()


@pytest.mark.integration
def test_generate_video_rejects_post_without_wizard_render_data(
    client: TestClient, session: Session
):
    post = Post(content="Sem dados do wizard", platform=Platform.instagram)
    session.add(post)
    session.commit()
    session.refresh(post)

    res = client.post(f"/api/posts/{post.id}/video", json={})
    assert res.status_code == 400


@pytest.mark.integration
def test_generate_video_404_for_missing_post(client: TestClient):
    res = client.post("/api/posts/999999/video", json={})
    assert res.status_code == 404


@pytest.mark.integration
@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg is not installed")
def test_generate_video_end_to_end(client: TestClient, session: Session):
    _make_profile(session)

    buf = io.BytesIO()
    Image.new("RGB", (1080, 1080), (120, 90, 60)).save(buf, "PNG")
    image_bytes = buf.getvalue()

    stem = "test_e2e_post_video_stem"
    final_path = compose_wizard_image(stem, image_bytes, "Frase de teste", "playfair", "minimal")
    bg_path = wizard_background_path(final_path)
    bg_path.write_bytes(image_bytes)

    post = Post(
        content="Legenda de teste",
        platform=Platform.instagram,
        phrase="Frase de teste",
        font="playfair",
        overlay_style="minimal",
        image_path=str(final_path),
    )
    session.add(post)
    session.commit()
    session.refresh(post)

    video_path: Path | None = None
    try:
        res = client.post(f"/api/posts/{post.id}/video", json={"duration": 2})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["video_path"]
        video_path = Path(body["video_path"])
        assert video_path.exists()
    finally:
        final_path.unlink(missing_ok=True)
        bg_path.unlink(missing_ok=True)
        if video_path:
            video_path.unlink(missing_ok=True)


@pytest.mark.integration
def test_upload_audio_rejects_invalid_file(client: TestClient, session: Session):
    _make_profile(session)
    res = client.post(
        "/api/wizard/upload-audio",
        files={"file": ("music.mp3", b"not actually audio", "audio/mpeg")},
    )
    assert res.status_code == 400


@pytest.mark.integration
@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg is not installed")
def test_upload_audio_accepts_valid_file(client: TestClient, session: Session, tmp_path: Path):
    _make_profile(session)

    wav_path = tmp_path / "silence.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc", "-t", "1", str(wav_path)],
        check=True,
        capture_output=True,
    )

    res = client.post(
        "/api/wizard/upload-audio",
        files={"file": ("music.wav", wav_path.read_bytes(), "audio/wav")},
    )
    assert res.status_code == 200
    audio_id = res.json()["audio_id"]
    for leftover in Path("media").glob(f"audio_{audio_id}.*"):
        leftover.unlink(missing_ok=True)
