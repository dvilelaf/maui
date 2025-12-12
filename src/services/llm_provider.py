from abc import ABC, abstractmethod
from typing import Union
from src.utils.schema import TaskExtractionResponse
from src.utils.config import Config


class LLMProvider(ABC):
    @abstractmethod
    def process_input(
        self, user_input: Union[str, bytes], mime_type: str = "text/plain"
    ) -> TaskExtractionResponse:
        """
        Process text or audio input to extract task details.
        """
        pass


class LLMFactory:
    @staticmethod
    def get_provider() -> LLMProvider:
        provider = Config.LLM_PROVIDER

        if provider == "groq":
            from src.services.groq_provider import GroqProvider

            if not Config.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY is not set but LLM_PROVIDER is 'groq'")
            return GroqProvider(Config.GROQ_API_KEY)

        elif provider == "gemini":
            from src.services.gemini import GeminiService

            return GeminiService(Config.GEMINI_API_KEYS)

        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
