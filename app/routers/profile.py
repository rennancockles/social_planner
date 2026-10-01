from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.models import Profile
from app.repositories import ProfileRepository

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=Profile | None)
def get_profile(session: Session = Depends(get_session)) -> Profile | None:
    return ProfileRepository(session).get()


@router.put("", response_model=Profile)
def save_profile(
    profile: Profile,
    session: Session = Depends(get_session),
) -> Profile:
    return ProfileRepository(session).save(profile)
