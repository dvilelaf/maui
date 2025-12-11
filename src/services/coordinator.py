from src.services.gemini import GeminiService
from src.database.access import TaskManager, UserManager
from src.utils.config import Config
import logging

logger = logging.getLogger(__name__)

class Coordinator:
    def __init__(self):
        self.gemini = GeminiService(api_key=Config.GEMINI_API_KEY)
        self.task_manager = TaskManager()
        self.user_manager = UserManager()

    def handle_message(self, user_id: int, username: str, content: str | bytes, is_voice: bool = False) -> str:
        """
        Main entry point for processing user messages.
        """
        # Ensure user exists
        self.user_manager.get_or_create_user(telegram_id=user_id, username=username)

        mime_type = "audio/ogg" if is_voice else "text/plain"

        # 1. Extract intent/task via Gemini
        extraction = self.gemini.process_input(content, mime_type=mime_type)

        if not extraction.is_relevant:
            return extraction.reasoning or "No he detectado ninguna tarea en tu mensaje. ¿Podrías reformularlo?"

        # 2. If relevant, save to DB
        if extraction.formatted_task:
            task_data = extraction.formatted_task.model_dump()
            new_task = self.task_manager.add_task(user_id, task_data)

            deadline_str = f" para el {new_task.deadline}" if new_task.deadline else ""
            return f"✅ Tarea guardada: *{new_task.title}* {deadline_str}\n(ID: {new_task.id})"

        return "Procesando..."

    def get_weekly_summary(self, user_id: int) -> str:
        tasks = self.task_manager.get_pending_tasks(user_id)
        if not tasks:
            return "¡No tienes tareas pendientes para esta semana! 🎉"

        summary = "📅 *Resumen Semanal de Tareas*:\n\n"
        for task in tasks:
            deadline = task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else "Sin fecha límite"
            summary += f"• *{task.title}* (ID: {task.id})\n  _{deadline}_ - {task.priority}\n"

        return summary
