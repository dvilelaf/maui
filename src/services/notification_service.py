import logging
from telegram import Bot
from src.utils.config import Config

logger = logging.getLogger(__name__)


async def notify_user(user_id: int, message: str):
    """Sends a notification to the user."""
    try:
        bot = Bot(token=Config.TELEGRAM_TOKEN)
        await bot.send_message(chat_id=user_id, text=message)
        logger.info(f"Notification sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")
