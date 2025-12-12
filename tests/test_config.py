
import os
import pytest
from src.utils.config import Settings

def test_config_defaults(mocker):
    # Mock os.environ to be empty (or minimal)
    mocker.patch.dict(os.environ, {}, clear=True)

    # We might need to mock dotenv so it doesn't load real .env
    mocker.patch("src.utils.config.load_dotenv")

    # Instantiate Settings directly, ignoring .env file
    settings = Settings(_env_file=None)

    # Check Defaults
    assert settings.LLM_PROVIDER == "gemini"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.DATABASE_URL == "maui.db"
    assert settings.GEMINI_MODELS == ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

def test_config_env_vars(mocker):
    envs = {
        "TELEGRAM_TOKEN": "123:ABC",
        "GEMINI_API_KEYS": "key1, key2 , key3", # Test splitting and stripping
        "LLM_PROVIDER": "GROQ", # Test casing if handled (though plan said .lower() in old config, Pydantic might not auto-lower unless validator used)
        "GROQ_API_KEY": "gsk_test"
    }
    mocker.patch.dict(os.environ, envs, clear=True)
    mocker.patch("src.utils.config.load_dotenv")

    settings = Settings(_env_file=None)

    assert settings.TELEGRAM_TOKEN == "123:ABC"
    assert settings.GEMINI_API_KEYS == ["key1", "key2", "key3"]
    assert settings.LLM_PROVIDER == "groq" # We should implement a validator or pre=True to lower()
    assert settings.GROQ_API_KEY == "gsk_test"

def test_missing_required(mocker):
    # If we make fields required (e.g. no default), this should fail.
    # Currently existing Config uses getenv so everything is mostly optional or has defaults.
    # But let's verify if we enforce any.
    # For now, let's assume we want valid defaults.
    pass
