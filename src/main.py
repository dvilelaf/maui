import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from src.utils.config import Config
from src.database.core import init_db
from src.database.models import create_tables
from src.bot.handlers import (
    start_command,
    help_command,
    handle_message,
    handle_voice,
    list_tasks_command,
    complete_task_command,
    cancel_task_command
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Silence httpx logger
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

def main():
    """Start the bot."""
    # 1. Init Database
    init_db(Config.DATABASE_URL.replace("sqlite:///", ""))
    create_tables()

    # 2. Setup Bot
    if not Config.TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not found in environment variables.")
        return

    application = Application.builder().token(Config.TELEGRAM_TOKEN).build()

    # 3. Register Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tasks", list_tasks_command))
    application.add_handler(CommandHandler("done", complete_task_command))
    application.add_handler(CommandHandler("cancel", cancel_task_command))

    # Text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Voice messages
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # 5. Setup Scheduler
    job_queue = application.job_queue
    if job_queue:
        from src.services.scheduler import send_weekly_summary, check_deadlines_job, send_pending_alert
        from datetime import time
        import pytz

        # Weekly summary every Monday at 8:00 AM
        job_queue.run_daily(send_weekly_summary, time=time(hour=8, minute=0), days=(1,)) # 1 = Monday

        # Pending alert every Friday at 8:00 AM
        job_queue.run_daily(send_pending_alert, time=time(hour=8, minute=0), days=(5,)) # 5 = Friday

        # Check deadlines every 5 minutes
        job_queue.run_repeating(check_deadlines_job, interval=300, first=10)

    # 6. Start Polling
    application.run_polling()

if __name__ == "__main__":
    main()
