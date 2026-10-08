import json
import logging
import random
import re
import uuid
from io import BytesIO
from typing import Any, cast

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image
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

# Curated search terms for the "paper/texture" background mode — a plain neutral
# backdrop (images 3/6/7/8 in tmp/) instead of a real-world photo. Varied randomly per
# request so regenerating gives different textures, not the same query every time.
_PAPER_TEXTURE_QUERIES = [
    "paper texture neutral",
    "beige paper grain texture",
    "linen fabric texture",
    "cream canvas texture",
    "watercolor paper texture",
    "neutral wall texture",
]


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


# batch_id/token are always server-generated uuid4().hex (optionally with a short hex
# suffix) and get interpolated straight into media/ filenames and glob patterns — unlike
# every other field here, they weren't validated, which would let a crafted value escape
# the media/ directory (path traversal) or glob-delete an unrelated batch's files.
_HEX_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_TOKEN_RE = re.compile(r"^preview_[0-9a-f]{32}_[0-9a-f]{8}$")


def _check_batch_id(v: str) -> str:
    if not _HEX_ID_RE.match(v):
        raise ValueError("batch_id inválido.")
    return v


def _check_token(v: str) -> str:
    if not _TOKEN_RE.match(v):
        raise ValueError("token inválido.")
    return v


def _preview_filename(batch_id: str, style_key: str) -> str:
    return f"preview_{batch_id}_{style_key}"


def _bg_filename(batch_id: str) -> str:
    return f"preview_{batch_id}_bg"


# User-uploaded backgrounds (as an alternative to Unsplash search/paper-texture): saved
# to media/upload_{hex}.png and referenced by an "upload:{hex}" image_id, so they slot
# into the exact same selection flow as any other ImageCandidate.
_UPLOAD_PREFIX = "upload:"
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _upload_filename(upload_id: str) -> str:
    return f"upload_{upload_id}"


def _resolve_background_bytes(image_id: str) -> bytes:
    if image_id.startswith(_UPLOAD_PREFIX):
        upload_id = image_id.removeprefix(_UPLOAD_PREFIX)
        if not _HEX_ID_RE.match(upload_id):
            raise HTTPException(status_code=400, detail="ID de upload inválido.")
        upload_path = MEDIA_DIR / f"{_upload_filename(upload_id)}.png"
        if not upload_path.exists():
            raise HTTPException(
                status_code=400,
                detail="Imagem enviada não encontrada ou expirada. Envie novamente.",
            )
        return upload_path.read_bytes()
    try:
        return fetch_image_bytes_by_id(image_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar imagem: {e}") from e


class PhrasesRequest(BaseModel):
    topic: str | None = None
    count: int = 4


class PhrasesResponse(BaseModel):
    phrases: list[str]


class ImagesRequest(BaseModel):
    phrase: str
    count: int = 4
    background_mode: str = "photo"

    @field_validator("background_mode")
    @classmethod
    def validate_background_mode(cls, v: str) -> str:
        if v not in ("photo", "paper"):
            raise ValueError(f"Modo de fundo inválido: {v!r}")
        return v


class ImageCandidate(BaseModel):
    id: str
    thumb_url: str


class ImagesResponse(BaseModel):
    images: list[ImageCandidate]


class FontOption(BaseModel):
    key: str
    label: str


class OptionsResponse(BaseModel):
    fonts: list[FontOption]


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

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, v: str | None) -> str | None:
        return _check_batch_id(v) if v is not None else v


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

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, v: str) -> str:
        return _check_batch_id(v)

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        return _check_token(v)


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

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id(cls, v: str) -> str:
        return _check_batch_id(v)

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        return _check_token(v)


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
    """In "photo" mode, translates the (often long, Portuguese) phrase into short English
    keywords before hitting Unsplash — searching on the raw phrase matches a tiny,
    near-identical pool of photos, which is why 'gerar novas opções' kept surfacing the
    same handful of results. In "paper" mode, searches a curated texture query instead —
    a plain neutral backdrop, not a real-world photo tied to the phrase's content."""
    _require_profile(session)
    try:
        if body.background_mode == "paper":
            query = random.choice(_PAPER_TEXTURE_QUERIES)
        else:
            keywords = get_ai_service().extract_image_keywords(None, body.phrase)
            query = keywords or body.phrase
        candidates = suggest_images(query, body.count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar imagens: {e}") from e
    return ImagesResponse(images=[ImageCandidate(**c) for c in candidates])


@router.post("/upload-image", response_model=ImageCandidate)
async def upload_image(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ImageCandidate:
    """Lets the user supply their own background instead of an Unsplash candidate — the
    result slots into the wizard exactly like any other ImageCandidate (same selection,
    pinning, and /previews flow), just referenced by an "upload:" id instead of a real
    Unsplash photo id."""
    _require_profile(session)

    if file.content_type not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Tipo de arquivo não suportado: {file.content_type!r}"
        )

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máximo 10MB).")

    try:
        # Decode-then-reencode (not just copy the raw bytes) both confirms the content is
        # a genuinely valid image regardless of what the content-type header claimed, and
        # normalizes it to a known-good PNG before it ever reaches the render pipeline.
        Image.open(BytesIO(content)).verify()
        rgb_image = Image.open(BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Arquivo não é uma imagem válida.") from e

    upload_id = uuid.uuid4().hex
    out_path = MEDIA_DIR / f"{_upload_filename(upload_id)}.png"
    rgb_image.save(out_path, "PNG")
    return ImageCandidate(id=f"{_UPLOAD_PREFIX}{upload_id}", thumb_url=str(out_path))


@router.get("/options", response_model=OptionsResponse)
def wizard_options() -> OptionsResponse:
    return OptionsResponse(
        fonts=[FontOption(key=key, label=data["label"]) for key, data in FONTS.items()],
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
        image_bytes = _resolve_background_bytes(body.image_id)
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
        ai_overrides = get_ai_service().suggest_style_adjustment(
            body.instruction, effective_current
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao interpretar o ajuste: {e}") from e
    # Merge onto the current state rather than trusting the AI's response as the full,
    # authoritative set — if it ever drops a key, that value should stay what it was,
    # not silently snap back to the hardcoded default (and since this response becomes
    # next round's body.overrides, a dropped key would otherwise be lost permanently).
    overrides = {**effective_current, **ai_overrides}

    new_token = _preview_filename(body.batch_id, uuid.uuid4().hex[:8])
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
        overrides_json=json.dumps(body.overrides) if body.overrides else None,
        image_path=str(final_path),
    )
    return PostRepository(session).create(post)
