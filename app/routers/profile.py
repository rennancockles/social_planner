from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session

from app.database import get_session
from app.models import Profile
from app.repositories import ProfileRepository
from app.suggestion_service import suggest_profile_from_urls

router = APIRouter(prefix="/api/profile", tags=["profile"])


_MAX_URLS = 10


class SuggestRequest(BaseModel):
    urls: list[str]

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Forneça ao menos uma URL.")
        if len(v) > _MAX_URLS:
            raise ValueError(f"Máximo de {_MAX_URLS} URLs por requisição.")
        return v


@router.get("", response_model=Profile | None)
def get_profile(session: Session = Depends(get_session)) -> Profile | None:
    return ProfileRepository(session).get()


@router.put("", response_model=Profile)
def save_profile(
    profile: Profile,
    session: Session = Depends(get_session),
) -> Profile:
    return ProfileRepository(session).save(profile)


@router.post("/suggest", response_model=Profile)
def suggest_profile(body: SuggestRequest) -> Profile:
    try:
        return suggest_profile_from_urls(body.urls)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao analisar perfis: {e}") from e
