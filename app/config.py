from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://worksphere:worksphere_dev@localhost:5432/worksphere"
    )
    jwt_secret_key: SecretStr = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
    session_cookie_secure: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
