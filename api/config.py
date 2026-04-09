from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_url: str
    mongodb_db_name: str = "traxion"
    environment: str = "development"
    ors_api_key: str = ""
    user_agent: str = "route-planning-traxion/1.0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
