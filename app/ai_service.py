from abc import ABC, abstractmethod

import anthropic
import anthropic.types
import openai

from app.models import Platform, Post, Profile, Tone
from app.settings import AIProvider, settings


def _build_prompt(profile: Profile, topic: str | None, count: int) -> str:
    platform_hints = {
        Platform.instagram: (
            "Use emojis, hashtags relevantes e linguagem visual. Máximo ~2200 caracteres."
        ),
        Platform.linkedin: (
            "Tom mais profissional, foque em insights e valor. Máximo ~3000 caracteres."
        ),
        Platform.twitter: "Seja conciso e direto. Máximo 280 caracteres por post.",
    }
    tone_hints = {
        Tone.casual: "descontraído, próximo e informal",
        Tone.professional: "profissional, claro e objetivo",
        Tone.inspirational: "inspirador, motivador e emotivo",
        Tone.educational: "educativo, didático e informativo",
    }
    topic_line = (
        f"Tema/assunto específico: {topic}" if topic else "Escolha temas relevantes para o nicho."
    )

    return f"""Você é um especialista em marketing de conteúdo para redes sociais.

Crie exatamente {count} sugestões de posts para a seguinte criadora de conteúdo:

- Nome: {profile.name}
- Nicho: {profile.niche}
- Tom de voz: {tone_hints[profile.tone]}
- Plataforma: {profile.platform.value.capitalize()}
- Público-alvo: {profile.audience_description}
- {topic_line}

Instruções para a plataforma {profile.platform.value.capitalize()}:
{platform_hints[profile.platform]}

Retorne SOMENTE os {count} posts, separados por "---" (três hífens em uma linha sozinha).
Não inclua numeração, títulos, explicações ou qualquer outro texto além dos posts em si."""


def _parse_posts(raw: str, profile: Profile, topic: str | None, count: int) -> list[Post]:
    parts = [p.strip() for p in raw.split("---") if p.strip()]
    return [
        Post(content=content, platform=profile.platform, topic=topic) for content in parts[:count]
    ]


class AIService(ABC):
    @abstractmethod
    def generate_posts(self, profile: Profile, topic: str | None, count: int) -> list[Post]:
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


def get_ai_service() -> AIService:
    if settings.ai_provider == AIProvider.anthropic:
        return AnthropicService()
    return OpenAIService()
