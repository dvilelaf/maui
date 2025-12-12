
import pytest
from unittest.mock import patch, MagicMock
from src.services.llm_provider import LLMFactory
from src.utils.config import Config

def test_llm_factory_default(mocker):
    # Mock config to default (gemini)
    mocker.patch.object(Config, "LLM_PROVIDER_RAW", "gemini")
    mocker.patch.object(Config, "GEMINI_API_KEYS_RAW", "fake_key")

    provider = LLMFactory.get_provider()
    from src.services.gemini import GeminiService
    assert isinstance(provider, GeminiService)

def test_llm_factory_groq(mocker):
    # Mock config to groq
    mocker.patch.object(Config, "LLM_PROVIDER_RAW", "groq")
    mocker.patch.object(Config, "GROQ_API_KEY", "gsk_fake_key")

    # Mock Groq client to avoid init error
    mocker.patch("src.services.groq_provider.Groq")

    provider = LLMFactory.get_provider()
    from src.services.groq_provider import GroqProvider
    assert isinstance(provider, GroqProvider)

def test_llm_factory_invalid(mocker):
    mocker.patch.object(Config, "LLM_PROVIDER_RAW", "invalid_provider")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        LLMFactory.get_provider()

def test_llm_factory_groq_missing_key(mocker):
    mocker.patch.object(Config, "LLM_PROVIDER_RAW", "groq")
    mocker.patch.object(Config, "GROQ_API_KEY", None)

    with pytest.raises(ValueError, match="GROQ_API_KEY is not set"):
        LLMFactory.get_provider()
