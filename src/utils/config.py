
import os
from typing import List, Optional
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

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
    DATABASE_URL: str = Field(default="maui.db")
    LOG_LEVEL: str = Field(default="INFO")

    # LLM Configuration
    LLM_PROVIDER_RAW: str = Field(default="gemini", validation_alias="LLM_PROVIDER")
    GROQ_API_KEY: Optional[str] = Field(default=None)
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")
    GROQ_WHISPER_MODEL: str = Field(default="whisper-large-v3")

    @computed_field
    @property
    def GEMINI_API_KEYS(self) -> List[str]:
        keys = self.GEMINI_API_KEYS_RAW
        if not keys:
            return []
        return [k.strip() for k in keys.split(",") if k.strip()]

    @computed_field
    @property
    def LLM_PROVIDER(self) -> str:
        return self.LLM_PROVIDER_RAW.lower()

# Instantiate settings
Config = Settings()
