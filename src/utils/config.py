from typing import List, Optional
import os
from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    TELEGRAM_TOKEN: Optional[str] = Field(default=None)

    # Read raw string from env, hiding it from public access if we want, or just keeping it secondary.
    # We alias it to GEMINI_API_KEYS so it picks up the env var.
    GEMINI_API_KEYS_RAW: str = Field(default="", validation_alias="GEMINI_API_KEYS")

    GEMINI_MODELS: List[str] = Field(
        default=[
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]
    )
    DATABASE_URL: Optional[str] = Field(default=None)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_db_url(cls, v):
        if v and v.strip():
            return v

        # Smart default: check if we are in Docker with mounted data
        if os.path.isdir("/app/data"):
            return "/app/data/maui.db"

        return "maui.db"

    LOG_LEVEL: str = Field(default="INFO")

    # LLM Configuration
    LLM_PROVIDER_RAW: str = Field(default="gemini", validation_alias="LLM_PROVIDER")
    GROQ_API_KEY: Optional[str] = Field(default=None)
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")
    GROQ_WHISPER_MODEL: str = Field(default="whisper-large-v3")

    # Web App Configuration
    WEBAPP_URL: str = Field(default="https://localhost:8123")

    @field_validator("WEBAPP_URL")
    @classmethod
    def validate_webapp_url(cls, v):
        if v and not v.startswith("https://"):
            return f"https://{v}"
        return v

    @computed_field
    @property
    def GEMINI_API_KEYS(self) -> List[str]:
        keys = self.GEMINI_API_KEYS_RAW
        if not keys:
            return []
        return [k.strip() for k in keys.split(",") if k.strip()]

    # Whitelist Configuration
    WHITELISTED_USERS_RAW: str = Field(default="", validation_alias="WHITELISTED_USERS")

    @computed_field
    @property
    def WHITELISTED_USERS(self) -> List[int]:
        users = self.WHITELISTED_USERS_RAW
        if not users:
            return []
        try:
            return [int(u.strip()) for u in users.split(",") if u.strip().isnumeric()]
        except ValueError:
            return []

    @computed_field
    @property
    def LLM_PROVIDER(self) -> str:
        return self.LLM_PROVIDER_RAW.lower()


# Instantiate settings
Config = Settings()
