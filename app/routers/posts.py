from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.ai_service import get_ai_service
from app.database import get_session
from app.models import Post, PostStatus
from app.repositories import PostRepository, ProfileRepository

router = APIRouter(prefix="/api/posts", tags=["posts"])


class GenerateRequest(BaseModel):
    topic: str | None = None
    count: int = 5


@router.post("/generate", response_model=list[Post], status_code=201)
def generate_posts(
    body: GenerateRequest,
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

    return PostRepository(session).create_many(posts)


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
