from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    mongodb_url: str
    mongodb_db_name: str = "traxion"
    environment: str = "development"
    ors_api_key: str = ""
    user_agent: str = "route-planning-traxion/1.0"

    # Motor de IA multi-proveedor
    ai_provider: str = "openai"          # openai | github | azure | ollama | anthropic | gemini
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")


settings = Settings()
