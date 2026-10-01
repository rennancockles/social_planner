import json
import re

import anthropic
import anthropic.types
import httpx2
import openai

from app.models import Platform, Profile, Tone
from app.settings import AIProvider, settings

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
_FETCH_TIMEOUT = 10.0
_MAX_CHARS = 3000
_HTTP_OK = 200


def _detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "instagram.com" in url_lower:
        return "instagram"
    if "linkedin.com" in url_lower:
        return "linkedin"
    if "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    return "unknown"


def _extract_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_CHARS]


def _fetch_url(url: str) -> str | None:
    try:
        with httpx2.Client(
            headers=_HEADERS, timeout=_FETCH_TIMEOUT, follow_redirects=True
        ) as client:
            response = client.get(url)
            if response.status_code == _HTTP_OK:
                return _extract_text(response.text)
    except Exception:
        pass
    return None


def _build_suggestion_prompt(snippets: list[dict[str, str]]) -> str:
    entries = "\n\n".join(
        f"[URL: {s['url']} | Plataforma: {s['platform']}]\n{s['text']}" for s in snippets
    )
    return f"""Você é um especialista em marketing de conteúdo para redes sociais.

Analise os trechos de posts/perfis de referência abaixo e sugira as configurações de perfil
para uma criadora de conteúdo que se inspira nesses perfis.

{entries}

Com base nesses conteúdos, responda SOMENTE com um JSON válido no formato abaixo
(sem markdown, sem explicações extras):

{{
  "niche": "<nicho principal inferido, em português, ex: fitness, culinária, moda>",
  "tone": "<um de: casual, professional, inspirational, educational>",
  "platform": "<plataforma mais frequente: instagram, linkedin ou twitter>",
  "audience_description": "<descrição em português do público-alvo ideal, 1-2 frases>"
}}"""


def _parse_suggestion(raw: str) -> dict[str, str]:
    match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        return dict(json.loads(match.group()))
    except json.JSONDecodeError:
        return {}


def _call_openai(prompt: str) -> str:
    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content or ""


def _call_anthropic(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
    return text_blocks[0].text if text_blocks else ""


def suggest_profile_from_urls(urls: list[str]) -> Profile:
    snippets: list[dict[str, str]] = []
    for url in urls:
        text = _fetch_url(url)
        platform = _detect_platform(url)
        fallback = f"(conteúdo não disponível para {url})"
        snippets.append({"url": url, "platform": platform, "text": text or fallback})

    prompt = _build_suggestion_prompt(snippets)
    if settings.ai_provider == AIProvider.anthropic:
        raw = _call_anthropic(prompt)
    else:
        raw = _call_openai(prompt)
    data = _parse_suggestion(raw)

    tone_map = {t.value: t for t in Tone}
    platform_map = {p.value: p for p in Platform}

    return Profile(
        name="",
        niche=data.get("niche", ""),
        tone=tone_map.get(data.get("tone", ""), Tone.casual),
        platform=platform_map.get(data.get("platform", ""), Platform.instagram),
        audience_description=data.get("audience_description", ""),
    )
