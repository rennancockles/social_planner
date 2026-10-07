import logging
import random
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session

from app.ai_service import get_ai_service
from app.database import get_session
from app.image_search import fetch_image_bytes_by_id, suggest_images
from app.image_service import (
    FONTS,
    MEDIA_DIR,
    STYLE_LABELS,
    STYLE_PRESETS,
    compose_wizard_image,
    resolve_overrides,
)
from app.models import Post, Profile
from app.repositories import PostRepository, ProfileRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wizard", tags=["wizard"])

_MAX_PHRASE_LENGTH = 120
_MAX_INSTRUCTION_LENGTH = 300
_PREVIEW_COUNT = 4


def _require_profile(session: Session) -> Profile:
    profile = ProfileRepository(session).get()
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Perfil não configurado. Configure seu perfil antes de criar posts.",
        )
    return profile


def _check_phrase(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("A frase não pode ser vazia.")
    if len(v) > _MAX_PHRASE_LENGTH:
        raise ValueError(f"A frase deve ter no máximo {_MAX_PHRASE_LENGTH} caracteres.")
    return v


def _check_font(v: str) -> str:
    if v not in FONTS:
        raise ValueError(f"Fonte inválida: {v!r}")
    return v


def _check_style(v: str) -> str:
    if v not in STYLE_LABELS:
        raise ValueError(f"Estilo inválido: {v!r}")
    return v


def _preview_filename(batch_id: str, style_key: str) -> str:
    return f"preview_{batch_id}_{style_key}"


def _bg_filename(batch_id: str) -> str:
    return f"preview_{batch_id}_bg"


class PhrasesRequest(BaseModel):
    topic: str | None = None
    count: int = 4


class PhrasesResponse(BaseModel):
    phrases: list[str]


class ImagesRequest(BaseModel):
    phrase: str
    count: int = 4


class ImageCandidate(BaseModel):
    id: str
    thumb_url: str


class ImagesResponse(BaseModel):
    images: list[ImageCandidate]


class FontOption(BaseModel):
    key: str
    label: str


class StyleOption(BaseModel):
    key: str
    label: str


class OptionsResponse(BaseModel):
    fonts: list[FontOption]
    styles: list[StyleOption]


class PreviewsRequest(BaseModel):
    phrase: str
    image_id: str
    font: str
    count: int = _PREVIEW_COUNT
    batch_id: str | None = None
    exclude_labels: list[str] = []

    @field_validator("phrase")
    @classmethod
    def validate_phrase(cls, v: str) -> str:
        return _check_phrase(v)

    @field_validator("font")
    @classmethod
    def validate_font(cls, v: str) -> str:
        return _check_font(v)


class StylePreview(BaseModel):
    key: str
    label: str
    image_path: str
    token: str
    overrides: dict[str, Any]


class PreviewsResponse(BaseModel):
    batch_id: str
    previews: list[StylePreview]


class AdjustRequest(BaseModel):
    batch_id: str
    token: str
    phrase: str
    font: str
    style: str
    instruction: str
    overrides: dict[str, Any] = {}

    @field_validator("phrase")
    @classmethod
    def validate_phrase(cls, v: str) -> str:
        return _check_phrase(v)

    @field_validator("font")
    @classmethod
    def validate_font(cls, v: str) -> str:
        return _check_font(v)

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        return _check_style(v)

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Descreva o ajuste desejado.")
        if len(v) > _MAX_INSTRUCTION_LENGTH:
            raise ValueError(
                f"O pedido de ajuste deve ter no máximo {_MAX_INSTRUCTION_LENGTH} caracteres."
            )
        return v


class AdjustResponse(BaseModel):
    token: str
    image_path: str
    overrides: dict[str, Any]


class FinalizeRequest(BaseModel):
    phrase: str
    topic: str | None = None
    font: str
    style: str
    batch_id: str
    token: str

    @field_validator("phrase")
    @classmethod
    def validate_phrase(cls, v: str) -> str:
        return _check_phrase(v)

    @field_validator("font")
    @classmethod
    def validate_font(cls, v: str) -> str:
        return _check_font(v)

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        return _check_style(v)


@router.post("/phrases", response_model=PhrasesResponse)
def suggest_phrases(
    body: PhrasesRequest,
    session: Session = Depends(get_session),
) -> PhrasesResponse:
    profile = _require_profile(session)
    try:
        phrases = get_ai_service().suggest_phrases(profile, body.topic, body.count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao gerar frases: {e}") from e
    return PhrasesResponse(phrases=phrases)


@router.post("/images", response_model=ImagesResponse)
def suggest_wizard_images(
    body: ImagesRequest,
    session: Session = Depends(get_session),
) -> ImagesResponse:
    """Translates the (often long, Portuguese) phrase into short English keywords before
    hitting Unsplash — searching on the raw phrase matches a tiny, near-identical pool of
    photos, which is why 'gerar novas opções' kept surfacing the same handful of results."""
    _require_profile(session)
    try:
        keywords = get_ai_service().extract_image_keywords(None, body.phrase)
        query = keywords or body.phrase
        candidates = suggest_images(query, body.count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar imagens: {e}") from e
    return ImagesResponse(images=[ImageCandidate(**c) for c in candidates])


@router.get("/options", response_model=OptionsResponse)
def wizard_options() -> OptionsResponse:
    return OptionsResponse(
        fonts=[FontOption(key=key, label=data["label"]) for key, data in FONTS.items()],
        styles=[StyleOption(key=key, label=label) for key, label in STYLE_LABELS.items()],
    )


@router.post("/previews", response_model=PreviewsResponse)
def generate_previews(
    body: PreviewsRequest,
    session: Session = Depends(get_session),
) -> PreviewsResponse:
    """Render the phrase+font combo using a random sample of curated style presets (base
    style + a tasteful overrides bundle — see STYLE_PRESETS), so the user picks among
    actual final-looking images that vary each time instead of the same 4 plain defaults.

    If batch_id is given, reuses that batch's already-cached background (no new Unsplash
    hit) — used when the user asks for more options after pinning some previews, so
    pinned tokens from the earlier call stay valid and intact."""
    _require_profile(session)

    if body.batch_id:
        bg_path = MEDIA_DIR / f"{_bg_filename(body.batch_id)}.png"
        if not bg_path.exists():
            raise HTTPException(
                status_code=400,
                detail="Sessão expirada. Volte e escolha a imagem novamente.",
            )
        batch_id = body.batch_id
        image_bytes = bg_path.read_bytes()
    else:
        try:
            image_bytes = fetch_image_bytes_by_id(body.image_id)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Erro ao buscar imagem: {e}") from e
        batch_id = uuid.uuid4().hex
        # Cache the raw background so later /adjust and /previews rounds re-render
        # without hitting Unsplash again.
        (MEDIA_DIR / f"{_bg_filename(batch_id)}.png").write_bytes(image_bytes)

    available = [p for p in STYLE_PRESETS if p["label"] not in body.exclude_labels] or STYLE_PRESETS
    count = max(min(body.count, len(available)), 0)
    presets = random.sample(available, k=count)

    try:
        previews = []
        for preset in presets:
            style_key = cast(str, preset["style"])
            preset_overrides = cast(dict[str, Any], preset["overrides"])
            token = _preview_filename(batch_id, uuid.uuid4().hex[:8])
            image_path = compose_wizard_image(
                token, image_bytes, body.phrase, body.font, style_key, overrides=preset_overrides
            )
            previews.append(
                StylePreview(
                    key=style_key,
                    label=cast(str, preset["label"]),
                    token=token,
                    overrides=preset_overrides,
                    image_path=str(image_path),
                )
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao montar as prévias: {e}") from e

    return PreviewsResponse(batch_id=batch_id, previews=previews)


@router.post("/adjust", response_model=AdjustResponse)
def adjust_preview(
    body: AdjustRequest,
    session: Session = Depends(get_session),
) -> AdjustResponse:
    """Interprets a free-text instruction into render parameters (opacity/colors/sizes) and
    re-renders the same cached background with them — no new AI image generation involved."""
    _require_profile(session)

    bg_path = MEDIA_DIR / f"{_bg_filename(body.batch_id)}.png"
    if not bg_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Sessão de ajuste expirada. Volte e escolha a imagem novamente.",
        )

    effective_current = resolve_overrides(body.style, body.overrides)
    try:
        overrides = get_ai_service().suggest_style_adjustment(body.instruction, effective_current)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao interpretar o ajuste: {e}") from e

    new_token = f"preview_{body.batch_id}_{body.style}_{uuid.uuid4().hex[:8]}"
    try:
        image_path = compose_wizard_image(
            new_token,
            bg_path.read_bytes(),
            body.phrase,
            body.font,
            body.style,
            overrides=overrides,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao montar a nova prévia: {e}") from e

    return AdjustResponse(token=new_token, image_path=str(image_path), overrides=overrides)


@router.post("/finalize", response_model=Post, status_code=201)
def finalize_post(
    body: FinalizeRequest,
    session: Session = Depends(get_session),
) -> Post:
    """Promotes the variant the user picked (original preview or an adjusted round) to the
    post's final image — it is not re-rendered here, it's the exact file already chosen."""
    profile = _require_profile(session)

    chosen_path = MEDIA_DIR / f"{body.token}.png"
    if not chosen_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Pré-visualização expirada ou inválida. Volte e escolha o estilo novamente.",
        )

    try:
        caption = get_ai_service().generate_caption(profile, body.phrase, body.topic)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao gerar legenda: {e}") from e

    final_path = MEDIA_DIR / f"{uuid.uuid4().hex}.png"
    chosen_path.rename(final_path)
    for sibling in MEDIA_DIR.glob(f"preview_{body.batch_id}_*"):
        sibling.unlink(missing_ok=True)

    post = Post(
        content=caption,
        platform=profile.platform,
        topic=body.topic,
        phrase=body.phrase,
        font=body.font,
        overlay_style=body.style,
        image_path=str(final_path),
    )
    return PostRepository(session).create(post)
