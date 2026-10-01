from enum import StrEnum

from pydantic_settings import BaseSettings, SettingsConfigDict


class AIProvider(StrEnum):
    openai = "openai"
    anthropic = "anthropic"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ai_provider: AIProvider = AIProvider.openai
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_image_model: str = "gpt-image-1"
    openai_image_size: str = "1024x1024"
    openai_image_quality: str = "medium"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"


settings = Settings()
