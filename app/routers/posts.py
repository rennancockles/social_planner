import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.ai_service import get_ai_service
from app.database import engine, get_session
from app.image_service import generate_post_image
from app.models import Post, PostStatus
from app.repositories import PostRepository, ProfileRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])


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
