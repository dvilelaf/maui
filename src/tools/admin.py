from src.database.models import User, Task
from src.utils.schema import UserStatus
from src.services.notification_service import notify_user
import asyncio
import logging

logger = logging.getLogger(__name__)

def resolve_user(target: str):
    """Resolve a target string (ID or @username) to a User object."""
    if target.isdigit():
        return User.get_or_none(User.telegram_id == int(target))
    elif target.startswith("@"):
        username = target[1:]  # Remove @
        return User.get_or_none(User.username == username)
    else:
        # Try as username without @
        return User.get_or_none(User.username == target)


def confirm_action(prompt: str) -> bool:
    resp = input(f"{prompt} (y/n): ").strip().lower()
    return resp == "y"


def kick_user(user_id: int):
    """Deletes a user and their tasks after confirmation."""
    try:
        user = User.get_or_none(User.telegram_id == user_id)
        if not user:
            print(f"User {user_id} not found.")
            return
        if not confirm_action(
            f"Are you sure you want to delete user {user_id} and all their tasks?"
        ):
            print("Deletion cancelled.")
            return

        task_count = Task.delete().where(Task.user == user.telegram_id).execute()
        user.delete_instance()
        logger.warning(
            f"User KICKED (Deleted): {user.telegram_id} and {task_count} tasks."
        )
        print(
            f"✅ User {user.telegram_id} (@{user.username}) and their {task_count} tasks have been deleted."
        )
    except Exception as e:
        print(f"Error kicking user {user_id}: {e}")


def update_status(user: User, status: UserStatus):
    try:
        user_id = user.telegram_id
        user.status = status
        user.save()
        print(f"User {user_id} ({user.username}) status updated to {status}.")
        msg = ""
        if status == UserStatus.WHITELISTED:
            msg = "✅ ¡Tu cuenta ha sido aprobada! Ya puedes usar Maui para gestionar tus tareas."
        elif status == UserStatus.BLACKLISTED:
            msg = "⛔ Tu solicitud de acceso ha sido denegada."
        if msg:
            asyncio.run(notify_user(user_id, msg))
    except Exception as e:
        print(f"Error updating user status: {e}")
