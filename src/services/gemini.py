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
        self.logger = logging.getLogger(__name__)
        # Track when a model can be used again: model_name -> timestamp (epoch)
        self.model_cooldowns = {}

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
        - 'time_filter': For QUERY_TASKS, CANCEL_TASK, and COMPLETE_TASK. Values: 'TODAY' (until tonight 23:59), 'WEEK' (next 7 days), 'MONTH' (next 30 days), 'YEAR' (next 365 days), 'ALL' (everything). Default to 'ALL' if no specific time mentions.
        - 'target_search_term': For CANCEL/COMPLETE/EDIT, providing the KEYWORDS to find the task (e.g., "milk", "calling mom", "meeting"). IMPORTANT: If the user wants to cancel/complete ALL tasks (e.g., "cancel everything", "delete all tasks"), set this to "ALL".
        - 'formatted_task':
          - For ADD_TASK: A JSON OBJECT containing full details. Keys: "title" (required), "description", "priority", "deadline".
            - "deadline": If user specifies a date BUT NO TIME (e.g. "today", "tomorrow", "next friday"), set time to 23:59:59. Example: "2025-10-10T23:59:59".
          - For EDIT_TASK: A JSON OBJECT containing only the changed fields. NEVER a string.

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
                    self.logger.warning(f"Gemini Quota Exceeded for {model_name}: {e}")
                    # SET COOLDOWN (default 60s if not parseable, but simplistic logic is fine)
                    self.model_cooldowns[model_name] = time.time() + 60
                    last_error = e
                    # Break inner loop immediately to rotate to next model
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
