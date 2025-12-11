import google.generativeai as genai
import os
import json
from src.utils.schema import TaskExtractionResponse
from src.utils.config import Config
from typing import Optional, Union
import logging

class GeminiService:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"}
        )
        self.logger = logging.getLogger(__name__)

    def _get_system_prompt(self) -> str:
        return """
        You are an intelligent task assistant named Maui.
        Your goal is to extract task details from the user's input (text or audio).

        Analyze the input and determine if it represents a task that the user needs to do.
        - If it IS a task, set 'is_relevant' to True and populate 'formatted_task'.
        - If it is NOT a task (e.g., chit-chat, random statement), set 'is_relevant' to False and provide a 'reasoning' IN SPANISH.

        For 'formatted_task':
        - 'title': A concise summary of the task (IN SPANISH).
        - 'description': A detailed description if provided (IN SPANISH).
        - 'priority': Infer priority (LOW, MEDIUM, HIGH, URGENT). Default to MEDIUM.
        - 'deadline': Infer the deadline as a specific datetime (ISO 8601 format) if mentioned. Reference the current time provided in context if relative time is used (e.g., "mañana").

        Current Timestamp: {current_time}
        """

    def process_input(self, user_input: Union[str, bytes], mime_type: str = "text/plain") -> TaskExtractionResponse:
        """
        Process text or audio input to extract task details.
        """
        from datetime import datetime
        current_time = datetime.now().isoformat()

        system_instruction = self._get_system_prompt().format(current_time=current_time)

        try:
            prompt_parts = [system_instruction]

            if mime_type.startswith("audio/"):
                # For audio, we might need to upload or pass bytes directly depending on SDK version.
                # Simplest for now with 1.5 flash is passing the data part if supported,
                # or treating it as a file upload if large.
                # Assuming small voice notes, we can try passing blob if supported,
                # typically genai.types.Blob requires data and mime_type.
                prompt_parts.append({
                    "mime_type": mime_type,
                    "data": user_input
                })
                prompt_parts.append("Please transcribe this audio and extract the task details.")
            else:
                prompt_parts.append(user_input)

            response = self.model.generate_content(prompt_parts)

            self.logger.info(f"Gemini Raw Response: {response.text}")

            # Pydantic validation
            return TaskExtractionResponse.model_validate_json(response.text)

        except Exception as e:
            self.logger.error(f"Error processing input with Gemini: {e}")
            # Return a safe fallback
            return TaskExtractionResponse(
                is_relevant=False,
                reasoning="Failed to process input due to technical error."
            )
