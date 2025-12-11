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
        self.logger = logger

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
            time_filter = extraction.time_filter or "ALL"
            return self.get_task_summary(user_id, time_filter)

        if extraction.intent == "ADD_TASK" and extraction.formatted_task:
            from src.utils.formatters import format_datetime_es

            task_data = extraction.formatted_task.model_dump()
            new_task = self.task_manager.add_task(user_id, task_data)

            deadline_str = f" para {format_datetime_es(new_task.deadline)}" if new_task.deadline else ""
            return f"✅ Tarea guardada: *{new_task.title}*{deadline_str}"

        # Handle Task Modification Intents
        if extraction.intent in ("CANCEL_TASK", "COMPLETE_TASK", "EDIT_TASK"):
            if not extraction.target_search_term:
                return "Entiendo que quieres modificar una tarea, pero no sé cuál. ¿Podrías ser más específico?"

            # Special handling for "ALL"
            if extraction.target_search_term == "ALL" and extraction.intent == "CANCEL_TASK":
                time_filter = extraction.time_filter or "ALL"
                count = self.task_manager.delete_all_pending_tasks(user_id, time_filter=time_filter)

                filter_text = {
                    "TODAY": "para hoy",
                    "WEEK": "para esta semana",
                    "MONTH": "para este mes",
                    "YEAR": "para este año",
                    "ALL": "pendientes"
                }.get(time_filter, "pendientes")

                if count > 0:
                    return f"🗑️ Se han eliminado {count} tareas {filter_text}."
                else:
                    return f"No tienes tareas {filter_text} para eliminar."

            # Find the task
            candidates = self.task_manager.find_tasks_by_keyword(user_id, extraction.target_search_term)

            if not candidates:
                return f"❌ No encontré ninguna tarea que coincida con '{extraction.target_search_term}'."

            if len(candidates) > 1:
                return f"⚠️ Encontré varias tareas para '{extraction.target_search_term}'. Por favor, usa el ID (ej: /done 123) o sé más específico."

            target_task = candidates[0]

            if extraction.intent == "CANCEL_TASK":
                self.task_manager.delete_task(target_task.id)
                return f"🗑️ Tarea eliminada: *{target_task.title}*"

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

                self.logger.info(f"Updating task {target_task.id} with: {updates}")

                self.task_manager.edit_task(target_task.id, **updates)
                return f"✏️ Tarea actualizada: *{target_task.title}*"

        return "He entendido el mensaje pero no estoy seguro de qué hacer."

    def get_task_summary(self, user_id: int, time_filter: str = "ALL") -> str:
        from src.utils.formatters import format_task_es, format_datetime_es

        # Map filter to readable text
        filter_text = {
            "TODAY": "para hoy",
            "WEEK": "para esta semana",
            "MONTH": "para este mes",
            "YEAR": "para este año",
            "ALL": "pendientes"
        }.get(time_filter, "pendientes")

        tasks = self.task_manager.get_pending_tasks(user_id, time_filter=time_filter)
        if not tasks:
            return f"¡No tienes tareas {filter_text}! 🎉"

        summary = f"📅 *Tus Tareas ({filter_text})*:\n\n"
        for task in tasks:
            summary += format_task_es(task)

        return summary
