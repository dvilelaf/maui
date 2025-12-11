import logging
from src.utils.config import Config
from src.database.core import init_db
from src.database.models import create_tables
from src.bot.handlers import (
    start_command,
    help_command,
    handle_message,
    handle_voice,
    get_tasks_command,
    get_lists_command,
    complete_task_command,
    cancel_task_command,
    add_task_command,
)
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import BotCommand

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Silence httpx logger
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def post_init(application: Application):
    """Set bot commands on startup."""
    commands = [
        BotCommand("start", "Iniciar el bot"),
        BotCommand("help", "Ayuda y ejemplos"),
        BotCommand("add", "Añadir tarea"),
        BotCommand("tasks", "Ver tareas pendientes"),
        BotCommand("lists", "Ver listas de tareas"),
        BotCommand("done", "Marcar como completada"),
        BotCommand("delete", "Borrar tarea"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    """Start the bot."""
    # 1. Init Database
    init_db(Config.DATABASE_URL.replace("sqlite:///", ""))
    create_tables()

    # 2. Setup Bot
    if not Config.TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not found in environment variables.")
        return

    application = (
        Application.builder().token(Config.TELEGRAM_TOKEN).post_init(post_init).build()
    )

    # 3. Register Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tasks", get_tasks_command))
    application.add_handler(CommandHandler("list", get_tasks_command))  # Alias
    application.add_handler(CommandHandler("lists", get_lists_command))
    application.add_handler(CommandHandler("done", complete_task_command))
    application.add_handler(CommandHandler("cancel", cancel_task_command))
    application.add_handler(CommandHandler("delete", cancel_task_command))  # Alias
    application.add_handler(CommandHandler("add", add_task_command))

    # Text messages
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Voice messages
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # 5. Setup Scheduler
    job_queue = application.job_queue
    if job_queue:
        from src.services.scheduler import (
            send_weekly_summary,
            check_deadlines_job,
            send_pending_alert,
        )
        from datetime import time

        # Weekly summary every Monday at 8:00 AM
        job_queue.run_daily(
            send_weekly_summary, time=time(hour=8, minute=0), days=(1,)
        )  # 1 = Monday

        # Pending alert every Friday at 8:00 AM
        job_queue.run_daily(
            send_pending_alert, time=time(hour=8, minute=0), days=(5,)
        )  # 5 = Friday

        # Check deadlines every 5 minutes
        job_queue.run_repeating(check_deadlines_job, interval=300, first=10)

    # 6. Start Polling
    application.run_polling()


if __name__ == "__main__":
    main()
