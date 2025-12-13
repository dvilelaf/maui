import logging
from src.utils.config import Config
from src.database.core import init_db
from src.database.models import create_tables
from src.bot.handlers import (
    start_command,
    help_command,
    handle_message,
    handle_voice,
    webapp_command,
    handle_invite_response,
)
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import BotCommand
from src.services.scheduler import (
    send_weekly_summary,
    check_deadlines_job,
    send_daily_summary,
)
from datetime import time

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
        BotCommand("app", "Abrir Web App"),
        BotCommand("help", "Ayuda"),
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
        Application.builder()
        .token(Config.TELEGRAM_TOKEN)
        .post_init(post_init)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .build()
    )

    # 3. Register Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("app", webapp_command))

    # Text messages
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Voice messages
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # Callback Queries
    application.add_handler(CallbackQueryHandler(handle_invite_response, pattern="^INVITE_"))

    # 5. Setup Scheduler
    job_queue = application.job_queue
    if job_queue:
        # Weekly summary (Mondays and Fridays) at 8:00 AM
        job_queue.run_daily(
            send_weekly_summary, time=time(hour=8, minute=0), days=(1, 5)
        )

        # Daily summary (Monday to Friday) at 8:00 AM
        job_queue.run_daily(
            send_daily_summary, time=time(hour=8, minute=0), days=(1, 2, 3, 4, 5)
        )

        # Check deadlines every 5 minutes
        job_queue.run_repeating(check_deadlines_job, interval=300, first=10)

    # 6. Start Polling
    application.run_polling()


if __name__ == "__main__":
    main()
