from src.services.gemini import GeminiService
from src.database.access import TaskManager, UserManager
from src.utils.config import Config
import logging

logger = logging.getLogger(__name__)


class Coordinator:
    def __init__(self):
        self.gemini = GeminiService(api_keys=Config.GEMINI_API_KEYS)
        self.task_manager = TaskManager()
        self.user_manager = UserManager()
        self.logger = logger

    async def handle_message(
        self,
        user_id: int,
        username: str,
        content: str | bytes,
        extraction: "TaskExtractionResponse | None" = None,
        is_voice: bool = False,
        first_name: str = None,
        last_name: str = None,
    ) -> str:
        """
        Main entry point for processing user messages.
        """
        from src.utils.schema import UserIntent, TimeFilter, TaskStatus, TARGET_ALL, TaskExtractionResponse

        # Ensure user exists
        user = self.user_manager.get_or_create_user(
            telegram_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

        # Access Control
        from src.utils.schema import UserStatus

        if user.status != UserStatus.WHITELISTED:
            if user.status == UserStatus.PENDING:
                return "🔒 Tu cuenta está pendiente de aprobación por el administrador. Te notificaremos cuando tengas acceso."
            elif user.status == UserStatus.BLACKLISTED:
                # Silently ignore or refuse
                return "⛔ No tienes permiso para usar este bot."

        mime_type = "audio/ogg" if is_voice else "text/plain"

        # 1. Extract intent/task via Gemini
        if not extraction:
            extraction = self.gemini.process_input(content, mime_type=mime_type)

        if not extraction.is_relevant:
            return extraction.reasoning or "No he entendido eso. ¿Podrías repetirlo?"

        # Handle Intents
        if extraction.intent == UserIntent.CREATE_LIST:
            list_name = (
                extraction.formatted_task.title
                if extraction.formatted_task
                else "Nueva Lista"
            )
            new_list = self.task_manager.create_list(user_id, list_name)
            return f"📋 Lista creada: *{new_list.title}*"

        if extraction.intent == UserIntent.SHARE_LIST:
            # Requires target_search_term (list name) and shared_with (usernames)
            if (
                not extraction.target_search_term
                or not extraction.formatted_task
                or not extraction.formatted_task.shared_with
            ):
                return "⚠️ Para compartir necesito el nombre de la lista y el usuario (ej: 'Compartir lista Compra con @ana')."

            target_list = self.task_manager.find_list_by_name(
                user_id, extraction.target_search_term
            )
            if not target_list:
                return f"❌ No encontré ninguna lista llamada '{extraction.target_search_term}'."

            results = []
            for username in extraction.formatted_task.shared_with:
                success, msg = self.task_manager.share_list(target_list.id, username)
                emoji = "✅" if success else "⚠️"
                results.append(f"{emoji} {msg}")

            return "\n".join(results)

        if extraction.intent == UserIntent.QUERY_TASKS:
            # Check if user asked for a specific list
            if extraction.formatted_task and extraction.formatted_task.list_name:
                list_name = extraction.formatted_task.list_name
                found_list = self.task_manager.find_list_by_name(user_id, list_name)

                if not found_list:
                    return f"❌ No encontré ninguna lista llamada '{list_name}'."

                tasks = self.task_manager.get_tasks_in_list(found_list.id)
                if not tasks:
                    return f"📝 La lista *{found_list.title}* está vacía."

                response = [f"📝 *{found_list.title}*:"]
                for t in tasks:
                    status = "✅" if t.status == TaskStatus.COMPLETED else "⬜"
                    response.append(f"{status} {t.title}")
                return "\n".join(response)

            time_filter = extraction.time_filter or TimeFilter.ALL
            return self.get_task_summary(
                user_id, time_filter, extraction.priority_filter
            )

        if extraction.intent == UserIntent.ADD_TASK and extraction.formatted_task:
            from src.utils.formatters import format_datetime_es

            # extraction.formatted_task is already a TaskSchema
            new_task = self.task_manager.add_task(user_id, extraction.formatted_task)

            if not new_task:
                return f"⚠️ Ya tienes una tarea pendiente con ese nombre: *{extraction.formatted_task.title}*."

            deadline_str = (
                f" para {format_datetime_es(new_task.deadline)}"
                if new_task.deadline
                else ""
            )

            if new_task.task_list:
                return f"✅ Añadido a *{new_task.task_list.title}*: {new_task.title}"

            return f"✅ Tarea guardada: *{new_task.title}*{deadline_str}"

        # Handle Task Modification Intents
        if extraction.intent in (
            UserIntent.CANCEL_TASK,
            UserIntent.COMPLETE_TASK,
            UserIntent.EDIT_TASK,
        ):
            if not extraction.target_search_term:
                return "Entiendo que quieres modificar una tarea, pero no sé cuál. ¿Podrías ser más específico?"

            # Special handling for "ALL"
            if (
                extraction.target_search_term == TARGET_ALL
                and extraction.intent == UserIntent.CANCEL_TASK
            ):
                time_filter = extraction.time_filter or TimeFilter.ALL
                count = self.task_manager.delete_all_pending_tasks(
                    user_id, time_filter=time_filter
                )

                filter_text = {
                    TimeFilter.TODAY: "para hoy",
                    TimeFilter.WEEK: "para esta semana",
                    TimeFilter.MONTH: "para este mes",
                    TimeFilter.YEAR: "para este año",
                    TimeFilter.ALL: "pendientes",
                }.get(time_filter, "pendientes")

                if count > 0:
                    return f"🗑️ Se han eliminado {count} tareas {filter_text}."
                else:
                    return f"No tienes tareas {filter_text} para eliminar."

            # Find the task
            candidates = self.task_manager.find_tasks_by_keyword(
                user_id, extraction.target_search_term
            )

            if not candidates:
                return f"❌ No encontré ninguna tarea que coincida con '{extraction.target_search_term}'."

            if len(candidates) > 1:
                return f"⚠️ Encontré varias tareas para '{extraction.target_search_term}'. Por favor, usa el ID (ej: /done 123) o sé más específico."

            target_task = candidates[0]

            if extraction.intent == UserIntent.CANCEL_TASK:
                self.task_manager.delete_task(target_task.id)
                return f"🗑️ Tarea eliminada: *{target_task.title}*"

            if extraction.intent == UserIntent.COMPLETE_TASK:
                self.task_manager.update_task_status(
                    target_task.id, TaskStatus.COMPLETED
                )
                return f"✅ Tarea completada: *{target_task.title}*"

            if extraction.intent == UserIntent.EDIT_TASK and extraction.formatted_task:
                self.logger.info(
                    f"Updating task {target_task.id} with: {extraction.formatted_task}"
                )

                # Identify changes
                updates = extraction.formatted_task.model_dump(exclude_unset=True)
                changes = []

                if "title" in updates and updates["title"] != target_task.title:
                    changes.append(
                        f"📝 Título: {target_task.title} -> {updates['title']}"
                    )

                if (
                    "description" in updates
                    and updates["description"] != target_task.description
                ):
                    changes.append("📄 Descripción actualizada")

                if "status" in updates and updates["status"] != target_task.status:
                    changes.append(
                        f"📊 Estado: {target_task.status} -> {updates['status']}"
                    )

                if (
                    "priority" in updates
                    and updates["priority"] != target_task.priority
                ):
                    changes.append(
                        f"🚨 Prioridad: {target_task.priority} -> {updates['priority']}"
                    )

                if "deadline" in updates:
                    # Compare datetimes safely
                    old_dead = target_task.deadline
                    new_dead = updates["deadline"]

                    # If both are None, no change. If one is None, change. If values differ, change.
                    if old_dead != new_dead:
                        from src.utils.formatters import format_datetime_es

                        old_str = (
                            format_datetime_es(old_dead) if old_dead else "Sin fecha"
                        )
                        new_str = (
                            format_datetime_es(new_dead) if new_dead else "Sin fecha"
                        )
                        changes.append(f"📅 Fecha: {old_str} -> {new_str}")

                success = self.task_manager.edit_task(
                    target_task.id, extraction.formatted_task
                )

                if success:
                    msg = f"✏️ Tarea actualizada: *{target_task.title}*"
                    if changes:
                        msg += "\n" + "\n".join(changes)
                    return msg
                else:
                    return "❌ No se pudo actualizar la tarea (quizás no hubo cambios)."

        return "He entendido el mensaje pero no estoy seguro de qué hacer."

    def get_task_summary(
        self, user_id: int, time_filter: str = "ALL", priority_filter: str = None
    ) -> str:
        from src.utils.formatters import format_task_es
        from src.utils.schema import TimeFilter

        # Map filter to readable text
        filter_text = {
            TimeFilter.TODAY: "para hoy",
            TimeFilter.WEEK: "para esta semana",
            TimeFilter.MONTH: "para este mes",
            TimeFilter.YEAR: "para este año",
            TimeFilter.ALL: "pendientes",
        }.get(time_filter, "pendientes")

        if priority_filter:
            filter_text += f" - Prioridad {priority_filter}"

        tasks = self.task_manager.get_pending_tasks(
            user_id, time_filter=time_filter, priority_filter=priority_filter
        )
        if not tasks:
            return f"¡No tienes tareas {filter_text}! 🎉"

        summary = f"📅 *Tus Tareas ({filter_text})*:\n\n"
        for task in tasks:
            summary += format_task_es(task)

        return summary

    def get_lists_summary(self, user_id: int) -> str:
        """Returns a formatted list of lists."""
        lists = self.task_manager.get_lists(user_id)
        if not lists:
            return "No tienes listas creadas ni compartidas."

        summary = "*Tus Listas:*\n\n"
        for i, task_list in enumerate(lists, 1):
            # Owner check
            is_owner = task_list.owner.telegram_id == user_id
            role = "👑 Propietario" if is_owner else "👥 Compartida"

            # Item count
            count = task_list.tasks.count()

            summary += f"{i}. *{task_list.title}* ({count} tareas) | {role}\n"
            # Show members? Maybe too verbose.

        summary += "\nUsa `/tasks <nombre lista>` (próximamente) o menciona la lista para añadir tareas."
        return summary
