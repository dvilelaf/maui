import google.generativeai as genai
import os
import json
from src.utils.schema import TaskExtractionResponse
from src.utils.config import Config
from typing import Optional, Union
import logging

class GeminiService:
    def __init__(self, api_keys: list[str]):
        self.api_keys = api_keys
        if not self.api_keys:
             raise ValueError("No Gemini API keys provided.")

        self.current_key_index = 0
        self._configure_client()

        self.logger = logging.getLogger(__name__)
        # Track when a model can be used again: model_name -> timestamp (epoch)
        self.model_cooldowns = {}
        # Track key cooldowns if needed, or just simple rotation

        # Optimize keys verified status
        self._verify_and_sort_keys()

        self._configure_client()

    def _configure_client(self):
        genai.configure(api_key=self.api_keys[self.current_key_index])

    def _rotate_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self._configure_client()
        self.logger.info(f"Switched to API Key index {self.current_key_index}")

    def _verify_and_sort_keys(self):
        """Checks usage limits of keys and pushes exhausted ones to the back."""
        working_keys = []
        exhausted_keys = []

        self.logger.info(f"Verifying {len(self.api_keys)} API keys...")

        for key in self.api_keys:
            try:
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-2.5-flash") # Use a common model for verification
                # Lightweight check
                model.generate_content("ping")
                working_keys.append(key)
            except Exception as e:
                self.logger.warning(f"Key verification failed for a key (moving to end): {e}")
                exhausted_keys.append(key)

        if not working_keys and not exhausted_keys:
             self.logger.error("No API keys provided!")
             raise ValueError("No API keys provided or all are invalid.")
        elif not working_keys:
             self.logger.error("All API keys seem to be exhausted or invalid!")
             self.api_keys = exhausted_keys # Keep all just in case, but will likely fail
        else:
             self.logger.info(f"Key optimization complete: {len(working_keys)} working, {len(exhausted_keys)} exhausted.")
             self.api_keys = working_keys + exhausted_keys

        # Reset current_key_index to 0 after sorting
        self.current_key_index = 0
        self.logger.info(f"Initial API Key index set to {self.current_key_index}")

    def _get_system_prompt(self) -> str:
        return """
        You are an intelligent task assistant named Maui.
        Your goal is to extract task details or identify commands from the user's input (text or audio).

        Analyze the input and classify the intent into one of the following:
        - ADD_TASK: Create a new task.
        - QUERY_TASKS: List existing tasks. Can be filtered by time (e.g., "tasks for today", "what do I have this week").
        - CANCEL_TASK: Remove/cancel a specific task (e.g., "cancel the milk task").
        - COMPLETE_TASK: Mark a task as done (e.g., "I finished calling mom").
        - EDIT_TASK: Change details of a task (e.g., "postpone the meeting to Friday").
        - UNKNOWN: Irrelevant input.

        Output matching the JSON schema:
        - 'intent': One of the above.
        - 'is_relevant': True for all except UNKNOWN.
        - 'time_filter': For QUERY_TASKS, CANCEL_TASK, and COMPLETE_TASK. Values: 'TODAY', 'WEEK', 'MONTH', 'YEAR', 'ALL'. Default to 'ALL'.
        - 'priority_filter': For QUERY_TASKS. Values: 'LOW', 'MEDIUM', 'HIGH', 'URGENT'. Only if user explicitly asks (e.g., "high priority tasks").
        - 'target_search_term':
            - For CANCEL/COMPLETE/EDIT: Key phrase to find the task.
            - If user says "I bought bread" or "Mark buying bread as done", the target is "buying bread" or "bread".
            - If "cancel everything", set to "ALL".
        - 'formatted_task':
          - For ADD_TASK: Full details. "deadline": if date w/o time, set to 23:59:59.
          - For EDIT_TASK: Changed fields only.

        If UNKNOWN, provide reasoning in Spanish.

        Current Context:
        - Today's Date: {current_time}
        - Day of Week: {day_name}

        CRITICAL INSTRUCTION FOR DATES:
        - Interpretation: deeply analyze terms like "today" (hoy), "tomorrow" (mañana), "next Friday" (el próximo viernes).
        - Calculation: Calculate the exact ISO 8601 string based on "Today's Date".
        - Time:
            - If user mentions a date w/o time (e.g. "for today"), set time to 23:59:59.
            - "Today" = {today_date}T23:59:59
            - "Tomorrow" = {tomorrow_date}T23:59:59
        """

    def process_input(self, user_input: Union[str, bytes], mime_type: str = "text/plain") -> TaskExtractionResponse:
        """
        Process text or audio input to extract task details.
        """
        from datetime import datetime, timedelta
        import time
        from google.api_core.exceptions import InternalServerError, ServiceUnavailable, ResourceExhausted

        now = datetime.now()
        current_time = now.isoformat()
        day_name = now.strftime("%A")
        today_date = now.strftime("%Y-%m-%d")
        tomorrow_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        system_instruction = self._get_system_prompt().format(
            current_time=current_time,
            day_name=day_name,
            today_date=today_date,
            tomorrow_date=tomorrow_date
        )

        max_retries = 3
        # Use models from config, defaulting to single model if list missing
        models_to_try = getattr(Config, "GEMINI_MODELS", ["gemini-1.5-flash"])

        last_error = None

        for model_name in models_to_try:
            # CHECK COOLDOWN
            cooldown_expiry = self.model_cooldowns.get(model_name, 0)
            if time.time() < cooldown_expiry:
                self.logger.info(f"Skipping model {model_name} due to cooldown (expires in {int(cooldown_expiry - time.time())}s)")
                continue

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
                    last_error = e
                    if attempt == max_retries - 1:
                        # Try next model
                        break
                    time.sleep(1 * (attempt+1)) # Exponential-ish backoff

                except ResourceExhausted as e:
                    self.logger.warning(f"Gemini Quota Exceeded (KeyIdx: {self.current_key_index}, Model: {model_name}): {e}")

                    # Try rotating keys first
                    # We try all keys for the CURRENT model before giving up on the model
                    keys_tried = 0
                    success_with_other_key = False

                    while keys_tried < len(self.api_keys) - 1: # Try other keys
                        self._rotate_key()
                        keys_tried += 1
                        try:
                            # Re-create model with new key config
                            self.model = genai.GenerativeModel(
                                model_name=model_name,
                                generation_config={"response_mime_type": "application/json"}
                            )
                            # Retry request immediately
                            response = self.model.generate_content(prompt_parts)
                            self.logger.info(f"Gemini Raw Response (Recovered with Key {self.current_key_index}): {response.text}")
                            return TaskExtractionResponse.model_validate_json(response.text)
                        except ResourceExhausted:
                            self.logger.warning(f"Key {self.current_key_index} also exhausted.")
                            continue
                        except Exception as inner_e:
                             self.logger.error(f"Error with rotated key {self.current_key_index}: {inner_e}")
                             # If other error, break key rotation loop and fallback to next model logic?
                             # For now, treat as exhaustion/failure and continue rotating
                             continue

                    # If we fall through here, ALL keys failed for this model.
                    # Set cooldown for this model and break to next model.
                    self.model_cooldowns[model_name] = time.time() + 60
                    last_error = e
                    break

                except Exception as e:
                    self.logger.error(f"Error processing input with Gemini ({model_name}): {e}")
                    last_error = e
                    break

        # If we exhausted all models
        reasoning = "Lo siento, he tenido problemas con todos mis modelos de lenguaje."
        if isinstance(last_error, ResourceExhausted):
            reasoning = "He alcanzado el límite de uso en todos los modelos disponibles. Inténtalo más tarde."

        from src.utils.schema import UserIntent
        return TaskExtractionResponse(
            is_relevant=False,
            intent=UserIntent.UNKNOWN,
            reasoning=reasoning
        )
