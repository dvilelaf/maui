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
        Your goal is to extract task details or identify commands from the user's input (text or audio).

        Analyze the input and classify the intent into one of the following:
        - ADD_TASK: Create a new task.
        - QUERY_TASKS: List existing tasks.
        - CANCEL_TASK: Remove/cancel a specific task (e.g., "cancel the milk task").
        - COMPLETE_TASK: Mark a task as done (e.g., "I finished calling mom").
        - EDIT_TASK: Change details of a task (e.g., "postpone the meeting to Friday").
        - UNKNOWN: Irrelevant input.

        Output matching the JSON schema:
        - 'intent': One of the above.
        - 'is_relevant': True for all except UNKNOWN.
        - 'target_search_term': For CANCEL/COMPLETE/EDIT, providing the KEYWORDS to find the task (e.g., "milk", "calling mom", "meeting").
        - 'formatted_task':
          - For ADD_TASK: Full details.
          - For EDIT_TASK: Only the changed fields (e.g., new deadline).

        If UNKNOWN, provide reasoning in Spanish.

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
