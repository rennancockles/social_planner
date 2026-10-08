import json
import re
from abc import ABC, abstractmethod
from typing import Any

import anthropic
import anthropic.types
import openai

from app.models import Platform, Post, Profile, Tone
from app.settings import AIProvider, settings

PLATFORM_HINTS = {
    Platform.instagram: (
        "Use emojis, hashtags relevantes e linguagem visual. Máximo ~2200 caracteres."
    ),
    Platform.linkedin: (
        "Tom mais profissional, foque em insights e valor. Máximo ~3000 caracteres."
    ),
    Platform.twitter: "Seja conciso e direto. Máximo 280 caracteres por post.",
}
TONE_HINTS = {
    Tone.casual: "descontraído, próximo e informal",
    Tone.professional: "profissional, claro e objetivo",
    Tone.inspirational: "inspirador, motivador e emotivo",
    Tone.educational: "educativo, didático e informativo",
}


def _build_prompt(profile: Profile, topic: str | None, count: int) -> str:
    topic_line = (
        f"Tema/assunto específico: {topic}" if topic else "Escolha temas relevantes para o nicho."
    )

    return f"""Você é um especialista em marketing de conteúdo para redes sociais.

Crie exatamente {count} sugestões de posts para a seguinte criadora de conteúdo:

- Nome: {profile.name}
- Nicho: {profile.niche}
- Tom de voz: {TONE_HINTS[profile.tone]}
- Plataforma: {profile.platform.value.capitalize()}
- Público-alvo: {profile.audience_description}
- {topic_line}

Instruções para a plataforma {profile.platform.value.capitalize()}:
{PLATFORM_HINTS[profile.platform]}

Retorne SOMENTE os {count} posts, separados por "---" (três hífens em uma linha sozinha).
Não inclua numeração, títulos, explicações ou qualquer outro texto além dos posts em si."""


def _parse_posts(raw: str, profile: Profile, topic: str | None, count: int) -> list[Post]:
    parts = [p.strip() for p in raw.split("---") if p.strip()]
    return [
        Post(content=content, platform=profile.platform, topic=topic) for content in parts[:count]
    ]


def _keywords_prompt(topic: str | None, content: str) -> str:
    subject = topic or content[:300]
    return (
        "Extract 2 to 4 short English keywords describing a background photo that visually "
        f"matches the mood/theme of this social media post: {subject}\n"
        "Return ONLY the keywords separated by spaces. No punctuation, no explanation."
    )


def _phrases_prompt(profile: Profile, topic: str | None, count: int) -> str:
    topic_line = (
        f"Tema/assunto específico: {topic}" if topic else "Escolha temas relevantes para o nicho."
    )
    return f"""Você é um especialista em marketing de conteúdo para redes sociais.

Crie exatamente {count} frases curtas e autônomas (tipo citação/quote), para serem usadas como
texto principal sobreposto em uma imagem de post, para a seguinte criadora de conteúdo:

- Nicho: {profile.niche}
- Tom de voz: {TONE_HINTS[profile.tone]}
- Público-alvo: {profile.audience_description}
- {topic_line}

Cada frase deve ter no máximo 120 caracteres, sem hashtags, sem emojis, sem numeração.

Retorne SOMENTE as {count} frases, separadas por "---" (três hífens em uma linha sozinha).
Não inclua explicações ou qualquer outro texto além das frases em si."""


def _parse_phrases(raw: str, count: int) -> list[str]:
    return [p.strip() for p in raw.split("---") if p.strip()][:count]


def _caption_prompt(profile: Profile, phrase: str, topic: str | None) -> str:
    topic_line = f"Tema/assunto específico: {topic}" if topic else ""
    return f"""Você é um especialista em marketing de conteúdo para redes sociais.

Crie 1 legenda de post para a seguinte criadora de conteúdo, construída em torno da frase
principal abaixo (a frase já será exibida na imagem do post, então a legenda deve complementá-la,
não apenas repeti-la):

- Nome: {profile.name}
- Nicho: {profile.niche}
- Tom de voz: {TONE_HINTS[profile.tone]}
- Plataforma: {profile.platform.value.capitalize()}
- Público-alvo: {profile.audience_description}
- Frase principal: "{phrase}"
- {topic_line}

Instruções para a plataforma {profile.platform.value.capitalize()}:
{PLATFORM_HINTS[profile.platform]}

Retorne SOMENTE a legenda. Não inclua numeração, títulos, explicações ou qualquer outro texto
além da legenda em si."""


_ADJUSTMENT_KEYS_DOC = """- box_opacity: opacidade do fundo/caixa (ou do gradiente escuro) \
atrás do texto, de 0 a 255 (quanto maior, mais opaco)
- box_color: cor de fundo da caixa, em hex (#rrggbb)
- box_radius: arredondamento dos cantos da caixa em pixels, de 0 (reto) a 60 (bem arredondado)
- box_width_pct: largura da caixa como fração da imagem, de 0.4 (estreita) a 0.95 (larga)
- text_color: cor do texto principal (a frase), em hex
- text_size: tamanho da fonte do texto principal (a frase) em pixels (entre 24 e 90)
- text_align: alinhamento do texto, "center" ou "left"
- text_uppercase: true/false — deixa o texto principal em caixa alta
- text_line_spacing: espaço entre as linhas do texto em pixels (entre 4 e 50)
- text_vertical_offset: desloca o texto/caixa verticalmente em pixels, de -200 \
(mais para cima) a 200 (mais para baixo); 0 é centralizado
- text_shadow_opacity: opacidade da sombra atrás do texto principal, de 0 (sem sombra) \
a 255 (sombra forte) — só se aplica nos estilos que já têm sombra de texto
- accent_color: cor de detalhes decorativos (borda, aspas), em hex
- accent_decoration: "none", "stars" ou "hearts" — pequenos ícones decorativos \
perto do texto
- watermark_opacity: opacidade da marca d'água (@usuario), de 0 a 255
- watermark_color: cor da marca d'água, em hex
- watermark_size: tamanho da fonte da marca d'água em pixels (entre 14 e 60)
- bg_grayscale: true/false — deixa a imagem de fundo em preto e branco
- bg_sepia: true/false — aplica um tom sépia (vintage) na imagem de fundo
- bg_saturation: intensidade das cores do fundo, de 0.0 (preto e branco) a 2.0 \
(bem saturado); 1.0 é o normal
- bg_brightness: brilho do fundo, de 0.3 a 2.0; 1.0 é o normal
- bg_contrast: contraste do fundo, de 0.3 a 2.0; 1.0 é o normal
- bg_warmth: tom de cor do fundo, de -1.0 (mais frio/azulado) a 1.0 (mais \
quente/alaranjado); 0.0 é neutro
- bg_blur: desfoque do fundo em pixels, de 0 (nítido) a 20 (bem desfocado)"""


def _adjustment_prompt(instruction: str, current_overrides: dict[str, Any]) -> str:
    return f"""Você ajusta parâmetros visuais de uma imagem de post com overlay de texto.

Parâmetros ajustáveis (todos opcionais, use apenas os que fizerem sentido para o pedido):
{_ADJUSTMENT_KEYS_DOC}

Valores atuais (podem estar vazios se ainda não foram ajustados): {json.dumps(current_overrides)}

Pedido do usuário: "{instruction}"

Retorne SOMENTE um JSON válido com o conjunto completo de valores atualizados (incluindo os que
não mudaram, mantendo os valores atuais quando não fizer sentido alterá-los). Não inclua texto
antes ou depois do JSON, nem cercas de markdown. Use somente as chaves listadas acima."""


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_json_object(raw: str) -> dict[str, Any]:
    cleaned = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"A IA não retornou um JSON válido: {raw!r}") from e
    if not isinstance(parsed, dict):
        raise ValueError(f"A IA não retornou um objeto JSON: {raw!r}")
    return parsed


class AIService(ABC):
    @abstractmethod
    def generate_posts(self, profile: Profile, topic: str | None, count: int) -> list[Post]:
        pass

    @abstractmethod
    def extract_image_keywords(self, topic: str | None, content: str) -> str:
        pass

    @abstractmethod
    def suggest_phrases(self, profile: Profile, topic: str | None, count: int) -> list[str]:
        pass

    @abstractmethod
    def generate_caption(self, profile: Profile, phrase: str, topic: str | None) -> str:
        pass

    @abstractmethod
    def suggest_style_adjustment(
        self, instruction: str, current_overrides: dict[str, Any]
    ) -> dict[str, Any]:
        pass


class OpenAIService(AIService):
    def __init__(self) -> None:
        self._client = openai.OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def generate_posts(self, profile: Profile, topic: str | None, count: int) -> list[Post]:
        prompt = _build_prompt(profile, topic, count)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        raw = response.choices[0].message.content or ""
        return _parse_posts(raw, profile, topic, count)

    def extract_image_keywords(self, topic: str | None, content: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": _keywords_prompt(topic, content)}],
            temperature=0.3,
            max_tokens=20,
        )
        return (response.choices[0].message.content or "").strip()

    def suggest_phrases(self, profile: Profile, topic: str | None, count: int) -> list[str]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": _phrases_prompt(profile, topic, count)}],
            temperature=0.8,
        )
        raw = response.choices[0].message.content or ""
        return _parse_phrases(raw, count)

    def generate_caption(self, profile: Profile, phrase: str, topic: str | None) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": _caption_prompt(profile, phrase, topic)}],
            temperature=0.8,
        )
        return (response.choices[0].message.content or "").strip()

    def suggest_style_adjustment(
        self, instruction: str, current_overrides: dict[str, Any]
    ) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "user", "content": _adjustment_prompt(instruction, current_overrides)}
            ],
            temperature=0.2,
            max_tokens=300,
        )
        return _parse_json_object(response.choices[0].message.content or "")


class AnthropicService(AIService):
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    def generate_posts(self, profile: Profile, topic: str | None, count: int) -> list[Post]:
        prompt = _build_prompt(profile, topic, count)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
        raw = text_blocks[0].text if text_blocks else ""
        return _parse_posts(raw, profile, topic, count)

    def extract_image_keywords(self, topic: str | None, content: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=20,
            messages=[{"role": "user", "content": _keywords_prompt(topic, content)}],
        )
        text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
        return text_blocks[0].text.strip() if text_blocks else ""

    def suggest_phrases(self, profile: Profile, topic: str | None, count: int) -> list[str]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": _phrases_prompt(profile, topic, count)}],
        )
        text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
        raw = text_blocks[0].text if text_blocks else ""
        return _parse_phrases(raw, count)

    def generate_caption(self, profile: Profile, phrase: str, topic: str | None) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": _caption_prompt(profile, phrase, topic)}],
        )
        text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
        return text_blocks[0].text.strip() if text_blocks else ""

    def suggest_style_adjustment(
        self, instruction: str, current_overrides: dict[str, Any]
    ) -> dict[str, Any]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            messages=[
                {"role": "user", "content": _adjustment_prompt(instruction, current_overrides)}
            ],
        )
        text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
        raw = text_blocks[0].text if text_blocks else ""
        return _parse_json_object(raw)


def get_ai_service() -> AIService:
    if settings.ai_provider == AIProvider.anthropic:
        return AnthropicService()
    return OpenAIService()
