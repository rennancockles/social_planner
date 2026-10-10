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
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    unsplash_access_key: str = ""
    database_url: str = "sqlite:///./social_planner.db"


settings = Settings()
