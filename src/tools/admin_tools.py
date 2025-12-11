import sys
import asyncio
import logging
from telegram import Bot
from src.database.models import User
from src.database.core import db, init_db
from src.utils.schema import UserStatus
from src.utils.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def notify_user(user_id: int, message: str):
    """Sends a notification to the user."""
    try:
        bot = Bot(token=Config.TELEGRAM_TOKEN)
        await bot.send_message(chat_id=user_id, text=message)
        logger.info(f"Notification sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")

def resolve_user(target: str):
    """Resolve a target string (ID or @username) to a User object."""
    if target.isdigit():
        return User.get_or_none(User.telegram_id == int(target))
    elif target.startswith("@"):
        username = target[1:] # Remove @
        return User.get_or_none(User.username == username)
    else:
        # Try as username without @
        return User.get_or_none(User.username == target)

def update_status(user: User, status: UserStatus):
    try:
        user_id = user.telegram_id
        user.status = status
        user.save()
        print(f"User {user_id} ({user.username}) status updated to {status}.")

        # Notify user
        msg = ""
        if status == UserStatus.WHITELISTED:
            msg = "✅ ¡Tu cuenta ha sido aprobada! Ya puedes usar Maui para gestionar tus tareas."
        elif status == UserStatus.BLACKLISTED:
            msg = "⛔ Tu solicitud de acceso ha sido denegada."

        if msg:
            asyncio.run(notify_user(user_id, msg))

    except Exception as e:
        print(f"Error updating user status: {e}")

def update_all_pending(status: UserStatus):
    """Updates all PENDING users to the new status."""
    try:
        pending_users = User.select().where(User.status == UserStatus.PENDING)
        count = 0
        for user in pending_users:
            update_status(user, status)
            count += 1
        print(f"Processed {count} users.")
    except Exception as e:
        print(f"Error processing all users: {e}")


if __name__ == "__main__":
    init_db()
    if len(sys.argv) < 3:
        print("Usage: python admin_tools.py <whitelist|blacklist> <user_id|@username|all>")
        sys.exit(1)

    action = sys.argv[1].lower()
    target_input = sys.argv[2] # Keep as string

    status = None
    if action == "whitelist":
        status = UserStatus.WHITELISTED
    elif action == "blacklist":
        status = UserStatus.BLACKLISTED
    else:
        print("Unknown action. Use 'whitelist' or 'blacklist'.")
        sys.exit(1)

    if target_input.lower() == "all":
        print(f"Running {action} for ALL pending users...")
        update_all_pending(status)
    else:
        user = resolve_user(target_input)
        if user:
            update_status(user, status)
        else:
            print(f"User '{target_input}' not found.")
