import logging
import json
import tempfile
import os
from typing import Union
from groq import Groq
from src.services.llm_provider import LLMProvider
from src.utils.schema import TaskExtractionResponse, UserIntent
from src.utils.config import Config
from datetime import datetime, timedelta

class GroqProvider(LLMProvider):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Groq API key is required")
        self.client = Groq(api_key=api_key)
        self.logger = logging.getLogger(__name__)
        self.transcription_model = Config.GROQ_WHISPER_MODEL
        self.chat_model = Config.GROQ_MODEL

    def _get_system_prompt(self) -> str:
        # Reusing the robust prompt from GeminiService, adapted slightly if needed.
        # Ideally this prompt should be shared or imported, but copying for isolation is safer for now.
        return """
        You are an intelligent task assistant named Maui.
        Your goal is to extract task details or identify commands from the user's text input.

        Analyze the input and classify the intent into:
        ADD_TASK, QUERY_TASKS, CANCEL_TASK, COMPLETE_TASK, EDIT_TASK, CREATE_LIST, SHARE_LIST, JOIN_LIST, REJECT_LIST, LEAVE_LIST, UNKNOWN.

        Output must be valid JSON matching this schema:
        {{
          "intent": "string (enum)",
          "is_relevant": "boolean",
          "time_filter": "string (optional enum: TODAY, WEEK, MONTH, YEAR, ALL)",
          "priority_filter": "string (optional enum: LOW, MEDIUM, HIGH, URGENT)",
          "target_search_term": "string (optional)",
          "formatted_task": {{
            "title": "string",
            "deadline": "string (ISO datetime if mentioned)",
            "priority": "string",
            "list_name": "string (optional)",
            "shared_with": ["string"]
          }},
          "reasoning": "string (optional)"
        }}

        Current Context:
        - Today's Date: {current_time}
        - Day of Week: {day_name}

        CRITICAL:
        - If "tomorrow", calculated date must be {tomorrow_date}.
        - If "today", calculated date must be {today_date}.
        """

    def process_input(
        self, user_input: Union[str, bytes], mime_type: str = "text/plain"
    ) -> TaskExtractionResponse:

        text_input = user_input

        # 1. Transcribe if Audio
        if mime_type.startswith("audio/"):
            try:
                text_input = self._transcribe_audio(user_input)
                self.logger.info(f"Groq Transcription: {text_input}")
            except Exception as e:
                self.logger.error(f"Groq Transcription failed: {e}")
                return TaskExtractionResponse(
                    is_relevant=False,
                    intent=UserIntent.UNKNOWN,
                    reasoning=f"Error transcribing audio: {str(e)}"
                )

        # 2. Reason (Chat Completion)
        try:
           return self._process_text(text_input)
        except Exception as e:
            self.logger.error(f"Groq Chat Completion failed: {e}")
            return TaskExtractionResponse(
                is_relevant=False,
                intent=UserIntent.UNKNOWN,
                reasoning=f"Error processing text: {str(e)}"
            )

    def _transcribe_audio(self, audio_bytes: bytes) -> str:
        # Groq API requires a file-like object with a name, or actual file.
        # TempTable is safest.
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(tmp_path, file.read()),
                    model=self.transcription_model,
                    response_format="json" # or verbose_json, text
                )
            return transcription.text
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _process_text(self, text: str) -> TaskExtractionResponse:
        now = datetime.now()
        current_time = now.isoformat()
        day_name = now.strftime("%A")
        today_date = now.strftime("%Y-%m-%d")
        tomorrow_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        system_instruction = self._get_system_prompt().format(
            current_time=current_time,
            day_name=day_name,
            today_date=today_date,
            tomorrow_date=tomorrow_date,
        )

        completion = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": text}
            ],
            model=self.chat_model,
            response_format={"type": "json_object"},
            temperature=0.1
        )

        response_content = completion.choices[0].message.content
        self.logger.info(f"Groq Raw Response: {response_content}")

        return TaskExtractionResponse.model_validate_json(response_content)
