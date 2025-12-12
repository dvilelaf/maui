from telegram.ext import ContextTypes
import logging
from src.database.repositories.task_repository import TaskManager
from src.database.models import Task, User
from datetime import datetime, timedelta
from src.utils.formatters import format_task_es, format_datetime_es

logger = logging.getLogger(__name__)
task_manager = TaskManager()


async def send_weekly_summary(context: ContextTypes.DEFAULT_TYPE):
    """
    Sends a weekly summary to all users.
    """

    logger.info("Running weekly summary job")
    users = User.select()
    for user in users:
        tasks = task_manager.get_pending_tasks(user.telegram_id)
        if tasks:
            summary = "📅 *Resumen Semanal de Tareas*:\n\n"
            for task in tasks:
                summary += format_task_es(task)

            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id, text=summary, parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send summary to {user.telegram_id}: {e}")


async def send_pending_alert(context: ContextTypes.DEFAULT_TYPE):
    """
    Sends an alert on Fridays if there are pending tasks.
    """

    logger.info("Running pending alert job")
    users = User.select()
    for user in users:
        tasks = task_manager.get_pending_tasks(user.telegram_id)
        if tasks:
            summary = "⚠️ *Tienes tareas pendientes para cerrar la semana*:\n\n"
            for task in tasks:
                deadline_str = (
                    f" (Vence: {format_datetime_es(task.deadline)})"
                    if task.deadline
                    else ""
                )
                summary += f"• {task.title}{deadline_str}\n"

            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=summary + "\n¡Ánimo! 💪",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to send pending alert to {user.telegram_id}: {e}")


async def check_deadlines_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Checks for upcoming deadlines and sends reminders.
    """
    now = datetime.now()
    # Alert if deadline is within the next 1 hour
    time_threshold = now + timedelta(hours=1)

    upcoming_tasks = (
        Task.select()
        .join(User)
        .where(
            (Task.status == "PENDING")
            & (Task.deadline.is_null(False))
            & (Task.deadline > now)
            & (Task.deadline <= time_threshold)
            & (Task.reminder_sent == False)  # noqa: E712
            & (Task.task_list.is_null())
        )
    )

    for task in upcoming_tasks:
        try:
            await context.bot.send_message(
                chat_id=task.user.telegram_id,
                text=f"⏰ *Recordatorio*: ¡La tarea *{task.title}* vence pronto!\nFecha límite: {task.deadline}",
                parse_mode="Markdown",
            )
            # Mark as sent
            task.reminder_sent = True
            task.save()
        except Exception as e:
            logger.error(f"Failed to send reminder for task {task.id}: {e}")
