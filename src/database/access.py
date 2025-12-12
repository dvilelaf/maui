from datetime import datetime
from peewee import fn
from typing import List, Optional

import asyncio
import logging
from src.utils.schema import TaskSchema, TimeFilter, TaskStatus, UserStatus
from src.utils.config import Config
from src.database.models import User, Task, TaskList, SharedAccess
from telegram import Bot

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
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
        # from src.database.models import Task # Already imported above
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

        return user


class TaskManager:
    @staticmethod
    def add_task(user_id: int, task_data: TaskSchema) -> Optional[Task]:
        # task_data is now a validated Pydantic model

        # Check for duplicates (case-insensitive title match for pending tasks)
        # We need to use fn.Lower or similar if we want DB-side case insensitivity,
        # or just fetch all pending and check in python if list is small.
        # For simplicity and robustness with SQLite/Peewee:
        from peewee import fn

        # Resolve List if specified
        target_list_id = None
        if task_data.list_name:
            # We need to use 'self' but this is static.
            # We can just call TaskManager.find_list_by_name or use class method.
            # Changing to class method might be better, but simpler:
            found_list = TaskManager.find_list_by_name(user_id, task_data.list_name)
            if found_list:
                target_list_id = found_list.id
            else:
                # Optional: warn user? For now silently ignore or default to None
                pass

        existing = (
            Task.select()
            .where(
                (Task.user == user_id)
                & (Task.status == TaskStatus.PENDING)
                & (fn.Lower(Task.title) == task_data.title.lower())
            )
            .first()
        )

        if existing:
            return None

        new_task = Task.create(
            user=user_id,
            title=task_data.title,
            description=task_data.description,
            priority=task_data.priority,
            deadline=task_data.deadline,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            task_list=target_list_id,
        )
        logger.info(
            f"Task CREATED: ID={new_task.id} User={user_id} Title='{new_task.title}'"
        )
        return new_task

    @staticmethod
    def get_pending_tasks(
        user_id: int,
        time_filter: TimeFilter = TimeFilter.ALL,
        priority_filter: str = None,
    ) -> List[Task]:
        from datetime import datetime, timedelta

        query = (
            (Task.user == user_id)
            & (Task.status == TaskStatus.PENDING)
            & (Task.task_list.is_null())
        )

        now = datetime.now()

        if time_filter == TimeFilter.TODAY:
            # Deadline <= Today 23:59:59 (and not none)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            query &= Task.deadline <= end_of_day

        elif time_filter == TimeFilter.WEEK:
            # Deadline <= Now + 7 days
            end_of_week = now + timedelta(days=7)
            query &= Task.deadline <= end_of_week

        elif time_filter == TimeFilter.MONTH:
            # Deadline <= Now + 30 days
            end_of_month = now + timedelta(days=30)
            query &= Task.deadline <= end_of_month

        elif time_filter == TimeFilter.YEAR:
            # Deadline <= Now + 365 days
            end_of_year = now + timedelta(days=365)
            query &= Task.deadline <= end_of_year

        if priority_filter:
            query &= Task.priority == priority_filter

        tasks = list(Task.select().where(query))

        # Sort logic:
        # 1. Deadline: Ascending (Earnest first). None goes to LAST (using datetime.max)
        # 2. Priority: URGENT > HIGH > MEDIUM > LOW

        priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

        def sort_key(t):
            deadline_val = t.deadline if t.deadline else datetime.max
            priority_val = priority_order.get(t.priority, 99)
            return (deadline_val, priority_val)

        tasks.sort(key=sort_key)

        return tasks

    @staticmethod
    def get_user_tasks(
        user_id: int,
        sort_by: str = "deadline"
    ) -> List[Task]:
        """Get all tasks (pending and completed) for a user, excluding tasks in lists."""
        from datetime import datetime

        # Base query: user's tasks, not in a list, and NOT CANCELLED
        query = (Task.user == user_id) & (Task.task_list.is_null()) & (Task.status != "CANCELLED")

        # Fetch all
        tasks = list(Task.select().where(query))

        # Sort logic:
        # PENDING first, then COMPLETED.
        # Within that: Deadline (earliest first) -> Priority -> Created At

        priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

        def sort_key(t):
            # Status: Pending (0) < Completed (1)
            status_val = 0 if t.status == TaskStatus.PENDING else 1

            # Deadline: None is "far future" for Pending, but maybe irrelevant for completed?
            # Let's keep consistent.
            deadline_val = t.deadline if t.deadline else datetime.max

            priority_val = priority_order.get(t.priority, 99)

            return (status_val, deadline_val, priority_val)

        tasks.sort(key=sort_key)
        return tasks

    @staticmethod
    def get_task_by_id(task_id: int) -> Optional[Task]:
        return Task.get_or_none(Task.id == task_id)

    @staticmethod
    def update_task_status(task_id: int, status: str) -> bool:
        query = Task.update(status=status).where(Task.id == task_id)
        return query.execute() > 0

    @staticmethod
    def delete_task(task_id: int) -> bool:
        query = Task.delete().where(Task.id == task_id)
        return query.execute() > 0

    @staticmethod
    def delete_all_pending_tasks(
        user_id: int, time_filter: TimeFilter = TimeFilter.ALL
    ) -> int:
        from datetime import datetime, timedelta

        query = (
            (Task.user == user_id)
            & (Task.status == TaskStatus.PENDING)
            & (Task.task_list.is_null())
        )

        now = datetime.now()

        if time_filter == TimeFilter.TODAY:
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            query &= Task.deadline <= end_of_day

        elif time_filter == TimeFilter.WEEK:
            end_of_week = now + timedelta(days=7)
            query &= Task.deadline <= end_of_week

        elif time_filter == TimeFilter.MONTH:
            end_of_month = now + timedelta(days=30)
            query &= Task.deadline <= end_of_month

        elif time_filter == TimeFilter.YEAR:
            end_of_year = now + timedelta(days=365)
            query &= Task.deadline <= end_of_year

        return Task.delete().where(query).execute()

    @staticmethod
    def edit_task(task_id: int, update_data: TaskSchema) -> bool:
        # Dump only set fields (partial update)
        updates = update_data.model_dump(exclude_unset=True)
        # Also remove explicit None if any slipped through (though unset handles it usually)
        updates = {k: v for k, v in updates.items() if v is not None}

        if not updates:
            return False

        # Filter to allowed fields (safety check, though Schema enforces structure)
        allowed_fields = {"title", "description", "deadline", "priority", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed_fields}

        return Task.update(**updates).where(Task.id == task_id).execute() > 0

    @staticmethod
    def find_tasks_by_keyword(
        user_id: int, keyword: str, list_id: int = None
    ) -> List[Task]:
        query = (Task.user == user_id) & (Task.status == TaskStatus.PENDING)

        if list_id:
            query &= Task.task_list == list_id
        else:
            query &= Task.task_list.is_null()

        query &= (Task.title.contains(keyword)) | (Task.description.contains(keyword))
        return list(Task.select().where(query))

    @staticmethod
    def create_list(user_id: int, title: str) -> TaskList:
        return TaskList.create(title=title, owner=user_id)

    @staticmethod
    async def share_list(list_id: int, target_query: str) -> tuple[bool, str]:
        """
        Share a list with a user found by username or name.
        Returns (Success, Message)
        """
        query_str = target_query.strip().replace("@", "")

        # 1. Try Exact Username
        target_user = User.get_or_none(User.username == query_str)

        # 2. If not found, Fuzzy Search
        if not target_user:
            candidates = list(
                User.select().where(
                    (fn.Lower(User.first_name).contains(query_str.lower()))
                    | (fn.Lower(User.last_name).contains(query_str.lower()))
                    | (fn.Lower(User.username).contains(query_str.lower()))
                )
            )

            if len(candidates) == 0:
                return False, f"Usuario '{target_query}' no encontrado."

            if len(candidates) > 1:
                # Try to refine: check exact First Name match
                exact_name = [
                    u
                    for u in candidates
                    if u.first_name and u.first_name.lower() == query_str.lower()
                ]
                if len(exact_name) == 1:
                    target_user = exact_name[0]
                else:
                    names = [
                        f"{u.first_name} {u.last_name or ''} (@{u.username or '-'})"
                        for u in candidates[:3]
                    ]
                    msg = ", ".join(names)
                    if len(candidates) > 3:
                        msg += "..."
                    return False, f"Encontré varios usuarios: {msg}. Sé más específico."

            if not target_user and len(candidates) == 1:
                target_user = candidates[0]

        if not target_user:
            return False, f"Usuario '{target_query}' no encontrado."

        # Check if already shared
        exists = (
            SharedAccess.select()
            .where(
                (SharedAccess.task_list == list_id) & (SharedAccess.user == target_user)
            )
            .exists()
        )
        if exists:
            return (
                False,
                f"La lista ya está compartida con @{target_user.username or target_user.first_name}.",
            )

        SharedAccess.create(
            user=target_user,
            task_list=list_id,
            status="PENDING",
        )

        # Notify the recipient
        try:
             list_obj = TaskList.get_by_id(list_id)
             owner = list_obj.owner
             owner_name = owner.username or owner.first_name
             await notify_user(
                 target_user.telegram_id,
                 f"📩 Has sido invitado por @{owner_name} a unirte a la lista '*{list_obj.title}*'.\n"
                 f"Usa `/join {list_id}` para unirte o `/reject {list_id}` para rechazar."
             )
        except Exception as e:
            logger.error(f"Failed to notify user shared: {e}")

        return (
            True,
            f"Invitación enviada a @{target_user.username or target_user.first_name}.",
        )

    @staticmethod
    async def respond_to_invite(user_id: int, list_id: int, accept: bool) -> tuple[bool, str]:
        """
        Accept or Reject a list invitation.
        """
        user = User.get_or_none(User.telegram_id == user_id)
        if not user:
            return False, "Usuario no encontrado."

        try:
            access = SharedAccess.get(
                (SharedAccess.user == user) & (SharedAccess.task_list == list_id)
            )
        except SharedAccess.DoesNotExist:
            return False, "No tienes una invitación pendiente para esta lista."

        tlist = TaskList.get_by_id(list_id)
        user_name = user.username or user.first_name

        if accept:
            access.status = "ACCEPTED"
            access.save()

            # Notify owner and members
            members = TaskManager.get_list_members(list_id)
            for m in members:
                if m.telegram_id != user.telegram_id:
                    await notify_user(
                        m.telegram_id,
                        f"👤 @{user_name} se ha unido a la lista '*{tlist.title}*'."
                    )
            return True, f"Te has unido a la lista '*{tlist.title}*'."
        else:
            access.delete_instance()
            # Notify owner (and members? usually just owner needs to know rejection)
            # "Todos los usuarios son notificados si esto pasa" -> rejection is less critical for members, but prompts says "Someone joins or rejects... members receive notification".
            members = TaskManager.get_list_members(list_id)
            for m in members:
                 if m.telegram_id != user.telegram_id: # Usually just owner + accepted members
                     await notify_user(
                        m.telegram_id,
                        f"👤 @{user_name} ha rechazado la invitación a '*{tlist.title}*'."
                     )
            return True, f"Has rechazado la invitación a '*{tlist.title}*'."

    @staticmethod
    async def leave_list(user_id: int, list_id: int) -> tuple[bool, str]:
        """
        Leave a shared list.
        """
        user = User.get_or_none(User.telegram_id == user_id)
        if not user:
            return False, "Usuario no encontrado."

        try:
            # Only delete if it exists
            access = SharedAccess.get(
                (SharedAccess.user == user) & (SharedAccess.task_list == list_id)
            )
            access.delete_instance()

            tlist = TaskList.get_by_id(list_id)
            user_name = user.username or user.first_name

            tlist = TaskList.get_by_id(list_id)
            user_name = user.username or user.first_name

            # Notify owner and members
            members = TaskManager.get_list_members(list_id)
            for m in members:
                if m.telegram_id != user.telegram_id:
                    await notify_user(
                        m.telegram_id,
                        f"👋 @{user_name} ha salido de la lista '*{tlist.title}*'."
                    )
            return True, f"Has salido de la lista '*{tlist.title}*'."

        except SharedAccess.DoesNotExist:
            return False, "No eres miembro de esta lista."

    @staticmethod
    def get_list_members(list_id: int) -> List[User]:
        owner = TaskList.get(TaskList.id == list_id).owner
        shared = (
            User.select()
            .join(SharedAccess)
            .where(
                (SharedAccess.task_list == list_id)
                & (SharedAccess.status == "ACCEPTED")
            )
        )
        return [owner] + list(shared)

    @staticmethod
    def find_list_by_name(user_id: int, name: str) -> Optional[TaskList]:
        # 1. Try DB search (Title contains name)
        # e.g. List="Shopping List", name="Shopping"
        owned = (
            TaskList.select()
            .where(
                (TaskList.owner == user_id)
                & (fn.Lower(TaskList.title).contains(name.lower()))
            )
            .first()
        )
        if owned:
            return owned

        # 2. Search shared lists
        shared = (
            TaskList.select()
            .join(SharedAccess)
            .where(
                (SharedAccess.user == user_id)
                & (SharedAccess.status == "ACCEPTED")
                & (fn.Lower(TaskList.title).contains(name.lower()))
            )
            .first()
        )
        if shared:
            return shared

        # 3. Reverse search: check if any list title is contained in the search term
        all_lists = TaskManager.get_lists(user_id)
        name_norm = name.lower()

        # Helper to clean up query
        def clean(s):
            stopwords = [
                "lista",
                "list",
                "de",
                "la",
                "el",
                "the",
                "una",
                "un",
                "los",
                "las",
            ]
            s = s.lower()
            for w in stopwords:
                s = s.replace(w, "")
            return s.strip()

        clean_name = clean(name)

        for task_list in all_lists:
            title_norm = task_list.title.lower()

            # Case A: Exact match of cleaned name
            if clean_name == title_norm:
                return task_list

            # Case B: List title is a word inside the query
            # e.g. List="Compra", Query="lista de la compra"
            if title_norm in name_norm:
                return task_list

            # Case C: Query is inside List title (already covered by DB contains usually, but case insensitive here)
            if clean_name in title_norm:
                return task_list

        # 4. Fallback: return first owned list if any
        fallback = TaskList.select().where(TaskList.owner == user_id).first()
        if fallback:
            return fallback
        return None
        return None

    @staticmethod
    def get_lists(user_id: int) -> List[TaskList]:
        # Owned lists
        owned = list(TaskList.select().where(TaskList.owner == user_id))

        # Shared lists
        shared = list(
            TaskList.select()
            .join(SharedAccess)
            .where((SharedAccess.user == user_id) & (SharedAccess.status == "ACCEPTED"))
        )
        return owned + shared

    @staticmethod
    def delete_list(user_id: int, list_id: int) -> bool:
        """
        Delete a list owned by the user.
        Cascades to SharedAccess but TASKS in the list might need to be handled.
        Option: Delete tasks (default).
        """
        try:
            # Check ownership
            lst = TaskList.get_or_none(TaskList.id == list_id)
            if not lst:
                return False

            if lst.owner.telegram_id != user_id:
                # Not owner
                return False

            # Delete tasks first (or rely on Cascade if configured? Peewee defaults vary, safe to manual)
            Task.delete().where(Task.task_list == list_id).execute()

            # Shared Access should cascade if DB constraints set, but let's manual delete to be safe
            SharedAccess.delete().where(SharedAccess.task_list == list_id).execute()

            ls_count = lst.delete_instance()
            return ls_count > 0
        except Exception as e:
            logger.error(f"Error deleting list {list_id}: {e}")
            return False

    @staticmethod
    def get_pending_invites(user_id: int) -> List[dict]:
        """
        Get pending invitations for a user.
        Returns list of dicts with list info.
        """
        # Join SharedAccess with TaskList to get title, and TaskList owner to get owner name
        query = (
            SharedAccess.select(SharedAccess, TaskList, User)
            .join(TaskList, on=(SharedAccess.task_list == TaskList.id))
            .join(User, on=(TaskList.owner == User.telegram_id)) # Owner of list
            .where(
                (SharedAccess.user == user_id)
                & (SharedAccess.status == "PENDING")
            )
        )

        results = []
        for access in query:
            # access.task_list is valid because of join
            tlist = access.task_list
            owner = tlist.owner
            results.append({
                "list_id": tlist.id,
                "list_name": tlist.title,
                "owner_name": owner.username or owner.first_name or "Unknown",
                "invited_at": str(access.id) # Dummy for now or check created_at if model has it
            })
        return results

    @staticmethod
    def get_tasks_in_list(list_id: int) -> List[Task]:
        return list(
            Task.select()
            .where(Task.task_list == list_id)
            .order_by(Task.status, Task.created_at)
        )
