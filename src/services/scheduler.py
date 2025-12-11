from telegram.ext import ContextTypes
from src.database.access import TaskManager
from src.database.models import Task, User
from datetime import datetime, timedelta
import logging

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
            summary = "📅 *Weekly Task Summary*:\n\n"
            for task in tasks:
                 deadline = task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else "No deadline"
                 summary += f"• *{task.title}* (ID: {task.id})\n  _{deadline}_ - {task.priority}\n"

            try:
                await context.bot.send_message(chat_id=user.telegram_id, text=summary, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send summary to {user.telegram_id}: {e}")

async def check_deadlines_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Checks for upcoming deadlines and sends reminders.
    """
    now = datetime.now()
    # Alert if deadline is within the next 1 hour
    time_threshold = now + timedelta(hours=1)

    upcoming_tasks = Task.select().join(User).where(
        (Task.status == 'PENDING') &
        (Task.deadline.is_null(False)) &
        (Task.deadline > now) &
        (Task.deadline <= time_threshold) &
        (Task.reminder_sent == False)
    )

    for task in upcoming_tasks:
        try:
            await context.bot.send_message(
                chat_id=task.user.telegram_id,
                text=f"⏰ *Reminder*: Task *{task.title}* is due soon!\nDeadline: {task.deadline}",
                parse_mode="Markdown"
            )
            # Mark as sent
            task.reminder_sent = True
            task.save()
        except Exception as e:
            logger.error(f"Failed to send reminder for task {task.id}: {e}")
