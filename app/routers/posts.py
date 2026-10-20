import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session

from app.ai_service import get_ai_service
from app.database import engine, get_session
from app.image_service import MEDIA_DIR, generate_post_image, wizard_background_path
from app.models import Post, PostStatus
from app.repositories import PostRepository, ProfileRepository
from app.video_service import (
    DEFAULT_DURATION,
    MAX_DURATION,
    MIN_DURATION,
    VideoGenerationError,
    render_post_video,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])

_HEX_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class GenerateRequest(BaseModel):
    topic: str | None = None
    count: int = 5


def _generate_and_save_image(post_id: int, content: str, topic: str | None) -> None:
    try:
        path = generate_post_image(post_id, content, topic)
        with Session(engine) as session:
            repo = PostRepository(session)
            post = repo.get_by_id(post_id)
            if post:
                post.image_path = str(path)
                session.add(post)
                session.commit()
    except Exception:
        logger.exception("Image generation failed for post %s", post_id)


@router.post("/generate", response_model=list[Post], status_code=201)
def generate_posts(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> list[Post]:
    profile = ProfileRepository(session).get()
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Perfil não configurado. Configure seu perfil antes de gerar posts.",
        )

    try:
        posts = get_ai_service().generate_posts(profile, body.topic, body.count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao gerar posts: {e}") from e

    saved = PostRepository(session).create_many(posts)

    for post in saved:
        if post.id is not None:
            background_tasks.add_task(_generate_and_save_image, post.id, post.content, post.topic)

    return saved


@router.get("", response_model=list[Post])
def list_posts(
    status: PostStatus = PostStatus.pending,
    session: Session = Depends(get_session),
) -> list[Post]:
    return PostRepository(session).list_by_status(status)


@router.patch("/{post_id}/approve", response_model=Post)
def approve_post(
    post_id: int,
    session: Session = Depends(get_session),
) -> Post:
    repo = PostRepository(session)
    post = repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    return repo.update_status(post, PostStatus.approved)


@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    session: Session = Depends(get_session),
) -> None:
    repo = PostRepository(session)
    post = repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    repo.delete(post)


class GenerateVideoRequest(BaseModel):
    audio_id: str | None = None
    duration: float = DEFAULT_DURATION

    @field_validator("audio_id")
    @classmethod
    def validate_audio_id(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_ID_RE.match(v):
            raise ValueError("audio_id inválido.")
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: float) -> float:
        if not (MIN_DURATION <= v <= MAX_DURATION):
            raise ValueError(
                f"Duração deve estar entre {MIN_DURATION:.0f} e {MAX_DURATION:.0f} segundos."
            )
        return v


def _resolve_audio_path(audio_id: str) -> Path | None:
    return next(MEDIA_DIR.glob(f"audio_{audio_id}.*"), None)


@router.post("/{post_id}/video", response_model=Post)
def generate_video(
    post_id: int,
    body: GenerateVideoRequest,
    session: Session = Depends(get_session),
) -> Post:
    """Renders the wizard-created post as a short vertical video: the same background +
    text/box overlay as the static image, with the background gently animated and an
    optional user-supplied music track mixed in."""
    repo = PostRepository(session)
    post = repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    if not post.image_path or not post.phrase or not post.font or not post.overlay_style:
        raise HTTPException(
            status_code=400,
            detail="Este post não foi criado pelo wizard, não é possível gerar vídeo.",
        )

    bg_path = wizard_background_path(post.image_path)
    if not bg_path.exists():
        raise HTTPException(
            status_code=400,
            detail="O fundo original deste post não está mais disponível para gerar vídeo.",
        )

    audio_bytes = None
    if body.audio_id:
        audio_path = _resolve_audio_path(body.audio_id)
        if not audio_path:
            raise HTTPException(status_code=400, detail="Áudio enviado não encontrado ou expirado.")
        audio_bytes = audio_path.read_bytes()

    overrides = json.loads(post.overrides_json) if post.overrides_json else {}
    try:
        video_path = render_post_video(
            out_stem=Path(post.image_path).stem,
            image_bytes=bg_path.read_bytes(),
            phrase=post.phrase,
            font_key=post.font,
            style_key=post.overlay_style,
            overrides=overrides,
            audio_bytes=audio_bytes,
            duration=body.duration,
        )
    except VideoGenerationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    post.video_path = str(video_path)
    session.add(post)
    session.commit()
    session.refresh(post)
    return post
