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
        # Use first model as default
        default_model = getattr(Config, "GEMINI_MODELS", ["gemini-2.5-flash"])[0]
        self.model = genai.GenerativeModel(
            model_name=default_model,
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
          - For ADD_TASK: A JSON OBJECT containing full details (e.g., {{"title": "Buy milk", "deadline": null}}). NEVER a string.
          - For EDIT_TASK: A JSON OBJECT containing only the changed fields (e.g., {{"deadline": "2025-12-12"}}). NEVER a string.

        If UNKNOWN, provide reasoning in Spanish.

        Current Timestamp: {current_time}
        """

    def process_input(self, user_input: Union[str, bytes], mime_type: str = "text/plain") -> TaskExtractionResponse:
        """
        Process text or audio input to extract task details.
        """
        from datetime import datetime
        import time
        from google.api_core.exceptions import InternalServerError, ServiceUnavailable, ResourceExhausted

        current_time = datetime.now().isoformat()
        system_instruction = self._get_system_prompt().format(current_time=current_time)

        max_retries = 3
        # Use models from config, defaulting to single model if list missing
        models_to_try = getattr(Config, "GEMINI_MODELS", ["gemini-2.5-flash"])

        for model_name in models_to_try:
            # Re-configure model for this attempt
            self.model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"}
            )
            self.logger.info(f"Attempting with model: {model_name}")

            for attempt in range(max_retries):
                try:
                    prompt_parts = [system_instruction]

                    if mime_type.startswith("audio/"):
                        prompt_parts.append({
                            "mime_type": mime_type,
                            "data": user_input
                        })
                        prompt_parts.append("Please transcribe this audio and extract the task details.")
                    else:
                        prompt_parts.append(user_input)

                    response = self.model.generate_content(prompt_parts)
                    self.logger.info(f"Gemini Raw Response: {response.text}")

                    return TaskExtractionResponse.model_validate_json(response.text)

                except (InternalServerError, ServiceUnavailable) as e:
                    self.logger.warning(f"Gemini API error (model {model_name}, attempt {attempt+1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        # If this was the last retry for this model, break internal loop to try next model?
                        # No, InternalServerError might be transient for this model/region.
                        # But if we exhaust retries here, we could try next model.
                        # Let's break to outer loop to try next model if available.
                        break
                    time.sleep(1 * (attempt+1)) # Exponential-ish backoff

                except ResourceExhausted as e:
                    self.logger.warning(f"Gemini Quota Exceeded for {model_name}: {e}")
                    # Break inner loop immediately to rotate to next model
                    break

                except Exception as e:
                    self.logger.error(f"Error processing input with Gemini ({model_name}): {e}")
                    # For generic errors, maybe safer to abort or try next?
                    # Let's try next model just in case.
                    break

        # If we exhausted all models and retries
        from src.utils.schema import UserIntent
        return TaskExtractionResponse(
            is_relevant=False,
            intent=UserIntent.UNKNOWN,
            reasoning="Lo siento, he tenido problemas con todos mis modelos de lenguaje. Por favor inténtalo más tarde."
        )
