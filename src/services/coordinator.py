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
            return extraction.reasoning or "No he entendido eso. ¿Podrías repetirlo?"

        # Handle Intents
        if extraction.intent == "QUERY_TASKS":
            return self.get_weekly_summary(user_id)

        if extraction.intent == "ADD_TASK" and extraction.formatted_task:
            task_data = extraction.formatted_task.model_dump()
            new_task = self.task_manager.add_task(user_id, task_data)
            deadline_str = f" para el {new_task.deadline}" if new_task.deadline else ""
            return f"✅ Tarea guardada: *{new_task.title}* {deadline_str}\n(ID: {new_task.id})"

        # Handle Task Modification Intents
        if extraction.intent in ("CANCEL_TASK", "COMPLETE_TASK", "EDIT_TASK"):
            if not extraction.target_search_term:
                return "Entiendo que quieres modificar una tarea, pero no sé cuál. ¿Podrías ser más específico?"

            # Find the task
            candidates = self.task_manager.find_tasks_by_keyword(user_id, extraction.target_search_term)

            if not candidates:
                return f"❌ No encontré ninguna tarea que coincida con '{extraction.target_search_term}'."

            if len(candidates) > 1:
                return f"⚠️ Encontré varias tareas para '{extraction.target_search_term}'. Por favor, usa el ID (ej: /done 123) o sé más específico."

            target_task = candidates[0]

            if extraction.intent == "CANCEL_TASK":
                self.task_manager.update_task_status(target_task.id, "CANCELLED")
                return f"🗑️ Tarea cancelada: *{target_task.title}*"

            if extraction.intent == "COMPLETE_TASK":
                self.task_manager.update_task_status(target_task.id, "COMPLETED")
                return f"✅ Tarea completada: *{target_task.title}*"

            if extraction.intent == "EDIT_TASK" and extraction.formatted_task:
                # Apply updates
                updates = extraction.formatted_task.model_dump(exclude_unset=True)
                # Remove None values
                updates = {k: v for k, v in updates.items() if v is not None}

                # Exclude priority if it's default value and not explicitly changed?
                # Pydantic sends defaults. Tough one.
                # The prompt says "Only the changed fields".
                # Schema has defaults. We should ideally make all fields Optional in TaskSchema for edits,
                # but TaskSchema is reused.
                # Let's trust Gemini populated fields only if changed? No, Pydantic fills defaults.
                # Hack: In prompt we said "Only the changed fields".
                # Code-side, we can check basic fields.
                # Actually, in Schema, title and priority have defaults/required.
                # I defined `title: Optional[str]` in the previous tool call for Schema update!
                # So `exclude_unset=True` should work if I didn't set defaults in Schema.

                self.task_manager.edit_task(
                    target_task.id,
                    title=updates.get('title'),
                    description=updates.get('description'),
                    deadline=updates.get('deadline')
                )
                return f"✏️ Tarea actualizada: *{target_task.title}*"

        return "He entendido el mensaje pero no estoy seguro de qué hacer."

    def get_weekly_summary(self, user_id: int) -> str:
        tasks = self.task_manager.get_pending_tasks(user_id)
        if not tasks:
            return "¡No tienes tareas pendientes para esta semana! 🎉"

        summary = "📅 *Resumen Semanal de Tareas*:\n\n"
        for task in tasks:
            deadline = task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else "Sin fecha límite"
            summary += f"• *{task.title}* (ID: {task.id})\n  _{deadline}_ - {task.priority}\n"

        return summary
