import logging
from src.database.models import User

logger = logging.getLogger(__name__)


class UserManager:
    @staticmethod
    def get_or_create_user(
        telegram_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
    ) -> User:
        user, created = User.get_or_create(
            telegram_id=telegram_id,
            defaults={
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        if created:
            logger.info(f"User CREATED: ID={telegram_id} (@{username})")

        # Update info if changed
        updates = []
        if username and user.username != username:
            user.username = username
            updates.append(True)
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updates.append(True)
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updates.append(True)

        if updates:
            user.save()
            if not created:  # Only log update if it wasn't just created
                logger.info(f"User UPDATED: ID={telegram_id} (@{username})")

        # Config-based auto-whitelist
        # This ensures that specific users are always whitelisted regardless of DB state
        from src.utils.config import Config
        from src.database.models import UserStatus

        if (
            telegram_id in Config.WHITELISTED_USERS
            and user.status != UserStatus.WHITELISTED
        ):
            user.status = UserStatus.WHITELISTED
            user.save()
            logger.info(f"User AUTO-WHITELISTED (Config): ID={telegram_id}")

        return user

    def update_status(self, telegram_id: int, status: str) -> bool:
        """Update the status of a user by Telegram ID."""
        try:
            user = User.get(User.telegram_id == telegram_id)
            user.status = status
            user.save()
            logger.info(f"User status updated: ID={telegram_id} -> {status}")
            return True
        except User.DoesNotExist:
            logger.warning(
                f"Attempted to update status for non-existent user {telegram_id}"
            )
            return False

    def get_pending_users(self) -> list[User]:
        """Get all users with PENDING status."""
        from src.database.models import UserStatus

        return list(User.select().where(User.status == UserStatus.PENDING))

    def update_notification_time(self, telegram_id: int, new_time) -> bool:
        """Update the daily notification time for a user."""
        try:
            user = User.get(User.telegram_id == telegram_id)
            user.notification_time = new_time
            user.save()
            logger.info(f"Notification time updated: ID={telegram_id} -> {new_time}")
            return True
        except User.DoesNotExist:
            logger.warning(
                f"Attempted to update notification time for non-existent user {telegram_id}"
            )
            return False
