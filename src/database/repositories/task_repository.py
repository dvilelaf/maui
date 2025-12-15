from datetime import datetime, timedelta
from typing import List, Optional
from peewee import fn, JOIN
import logging

from src.database.core import db
from src.database.models import User, Task, TaskList, SharedAccess
from src.utils.schema import TaskSchema, TimeFilter, TaskStatus
from src.services.notification_service import notify_user

logger = logging.getLogger(__name__)


class TaskManager:
    @staticmethod
    def add_task(user_id: int, task_data: TaskSchema) -> Optional[Task]:
        # task_data is now a validated Pydantic model

        # Resolve List if specified
        target_list_id = None
        if task_data.list_name:
            found_list = TaskManager.find_list_by_name(user_id, task_data.list_name)
            if found_list:
                target_list_id = found_list.id
            else:
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

        # Determine position: Append to end of "loose tasks" for this user
        new_pos = 0
        if not target_list_id:
            max_pos = (
                Task.select(fn.MAX(Task.position))
                .where((Task.user == user_id) & (Task.task_list.is_null()))
                .scalar()
                or 0
            )
            new_pos = max_pos + 1

        new_task = Task.create(
            user=user_id,
            title=task_data.title,
            description=task_data.description,
            priority=task_data.priority,
            deadline=task_data.deadline,
            status=TaskStatus.PENDING,
            recurrence=task_data.recurrence,
            created_at=datetime.now(),
            task_list=target_list_id,
            position=new_pos,
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

        if priority_filter:
            query &= Task.priority == priority_filter

        tasks = list(Task.select().where(query))

        priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

        def sort_key(t):
            deadline_val = t.deadline if t.deadline else datetime.max
            priority_val = priority_order.get(t.priority, 99)
            return (deadline_val, priority_val)

        tasks.sort(key=sort_key)

        return tasks

    @staticmethod
    def get_user_tasks(user_id: int, sort_by: str = "deadline") -> List[Task]:
        """Get all tasks (pending and completed) for a user, excluding tasks in lists."""

        query = (
            (Task.user == user_id)
            & (Task.task_list.is_null())
            & (Task.status != "CANCELLED")
        )
        tasks = list(Task.select().where(query))

        priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

        def sort_key(t):
            status_val = 0 if t.status == TaskStatus.PENDING else 1
            deadline_val = t.deadline if t.deadline else datetime.max
            priority_val = priority_order.get(t.priority, 99)
            return (status_val, deadline_val, priority_val)

        tasks.sort(key=sort_key)
        return tasks

    @staticmethod
    def get_task_by_id(task_id: int) -> Optional[Task]:
        return Task.get_or_none(Task.id == task_id)

    @staticmethod
    def _check_task_access(user_id: int, task: Task) -> bool:
        """Check if user has write access to the task."""
        if task.user_id == user_id:
            return True

        # If in a list, check shared access
        if task.task_list:
            # Check owner
            if task.task_list.owner_id == user_id:
                return True
            # Check if member
            is_member = (
                SharedAccess.select()
                .where(
                    (SharedAccess.task_list == task.task_list)
                    & (SharedAccess.user == user_id)
                    & (SharedAccess.status == "ACCEPTED")
                )
                .exists()
            )
            return is_member

        return False

    @staticmethod
    def update_task_status(user_id: int, task_id: int, status: str) -> bool:
        task = Task.get_or_none(Task.id == task_id)
        if not task:
            return False

        if not TaskManager._check_task_access(user_id, task):
            return False

        if status == TaskStatus.COMPLETED and task.recurrence and task.status != TaskStatus.COMPLETED:
            # Handle Recurrence: Spawn new task
            try:
                # Calculate next deadline
                # If no deadline, recurrence is meaningless? Or maybe just reminder?
                # Assume deadline exists if recurrence is set, or default to created_at + interval
                base_date = task.deadline if task.deadline else datetime.now()
                next_date = None

                if task.recurrence == "DAILY":
                    next_date = base_date + timedelta(days=1)
                elif task.recurrence == "WEEKLY":
                    next_date = base_date + timedelta(weeks=1)
                elif task.recurrence == "MONTHLY":
                    import calendar
                    # Add 1 month preserving day
                    month = base_date.month - 1 + 1
                    year = base_date.year + month // 12
                    month = month % 12 + 1
                    day = min(base_date.day, calendar.monthrange(year, month)[1])
                    next_date = base_date.replace(year=year, month=month, day=day)
                elif task.recurrence == "YEARLY":
                    # Add 1 year
                    try:
                        next_date = base_date.replace(year=base_date.year + 1)
                    except ValueError:
                        # Handle leap year (Feb 29 -> Feb 28)
                        next_date = base_date.replace(year=base_date.year + 1, day=28)

                if next_date:
                    # Create the next task
                    next_task = Task.create(
                        user=task.user,
                        title=task.title,
                        description=task.description,
                        priority=task.priority,
                        deadline=next_date,
                        status=TaskStatus.PENDING,
                        recurrence=task.recurrence,
                        task_list=task.task_list,
                        # We append to end of list or similar pos
                        position=task.position + 1 if task.position else 0
                    )
                    logger.info(f"Recurring Task Spawned: {next_task.id} for {next_date}")
            except Exception as e:
                logger.error(f"Failed to spawn recurring task: {e}")

        task.status = status
        return task.save() > 0

    @staticmethod
    def delete_task(user_id: int, task_id: int) -> bool:
        task = Task.get_or_none(Task.id == task_id)
        if not task:
            return False

        if not TaskManager._check_task_access(user_id, task):
            return False

        return task.delete_instance() > 0

    @staticmethod
    def delete_all_pending_tasks(
        user_id: int, time_filter: TimeFilter = TimeFilter.ALL
    ) -> int:
        # Only deletes OWNED tasks that are NOT in a list
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
    def edit_task(user_id: int, task_id: int, update_data: TaskSchema) -> bool:
        task = Task.get_or_none(Task.id == task_id)
        if not task:
            return False

        if not TaskManager._check_task_access(user_id, task):
            return False

        updates = update_data.model_dump(exclude_unset=True)
        # updates = {k: v for k, v in updates.items() if v is not None} # Removed to allow setting fields to None (e.g. deadline)

        if not updates:
            return False

        allowed_fields = {"title", "description", "deadline", "priority", "status"}

        for k, v in updates.items():
            if k in allowed_fields:
                setattr(task, k, v)

        return task.save() > 0

    @staticmethod
    def find_tasks_by_keyword(
        user_id: int, keyword: str, list_id: int = None
    ) -> List[Task]:
        # Secure search
        query = Task.status == TaskStatus.PENDING

        if list_id:
            # Check access to list
            has_access = False
            tlist = TaskList.get_or_none(TaskList.id == list_id)
            if tlist:
                if tlist.owner_id == user_id:
                    has_access = True
                else:
                    has_access = (
                        SharedAccess.select()
                        .where(
                            (SharedAccess.task_list == list_id)
                            & (SharedAccess.user == user_id)
                            & (SharedAccess.status == "ACCEPTED")
                        )
                        .exists()
                    )

            if not has_access:
                return []

            query &= Task.task_list == list_id
        else:
            # Only personal tasks
            query &= (Task.user == user_id) & (Task.task_list.is_null())

        query &= (Task.title.contains(keyword)) | (Task.description.contains(keyword))
        return list(Task.select().where(query))

    @staticmethod
    def create_list(user_id: int, title: str) -> TaskList:
        # Determine next position
        max_pos_owned = (
            TaskList.select(fn.MAX(TaskList.position))
            .where(TaskList.owner == user_id)
            .scalar()
            or 0
        )
        max_pos_shared = (
            SharedAccess.select(fn.MAX(SharedAccess.position))
            .where((SharedAccess.user == user_id) & (SharedAccess.status == "ACCEPTED"))
            .scalar()
            or 0
        )
        next_pos = max(max_pos_owned, max_pos_shared) + 1

        return TaskList.create(title=title, owner=user_id, position=next_pos)

    @staticmethod
    async def share_list(
        user_id: int, list_id: int, target_query: str
    ) -> tuple[bool, str]:
        # Validate ownership
        tlist = TaskList.get_or_none(TaskList.id == list_id)
        if not tlist:
            return False, "Lista no encontrada."

        if tlist.owner_id != user_id:
            return False, "No tienes permiso para compartir esta lista."

        query_str = target_query.strip().replace("@", "")

        target_user = User.get_or_none(User.username == query_str)

        # Fallback: Try Telegram ID if numeric
        if not target_user and query_str.isdigit():
            target_user = User.get_or_none(User.telegram_id == int(query_str))

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

        try:
            owner = tlist.owner
            owner_name = owner.username or owner.first_name

            # Interactive Buttons
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            kb = [
                [
                    InlineKeyboardButton(
                        "✅ Aceptar", callback_data=f"INVITE_ACCEPT_{list_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Rechazar", callback_data=f"INVITE_REJECT_{list_id}"
                    ),
                ]
            ]
            markup = InlineKeyboardMarkup(kb)

            await notify_user(
                target_user.telegram_id,
                f"📩 Has sido invitado por @{owner_name} a unirte a la lista '*{tlist.title}*'.",
                reply_markup=markup,
            )
        except Exception as e:
            logger.error(f"Failed to notify user shared: {e}")

        return (
            True,
            f"Invitación enviada a @{target_user.username or target_user.first_name}.",
        )

    @staticmethod
    async def respond_to_invite(
        user_id: int, list_id: int, accept: bool
    ) -> tuple[bool, str]:
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

            # Set position
            max_pos_owned = (
                TaskList.select(fn.MAX(TaskList.position))
                .where(TaskList.owner == user.telegram_id)
                .scalar()
                or 0
            )
            max_pos_shared = (
                SharedAccess.select(fn.MAX(SharedAccess.position))
                .where(
                    (SharedAccess.user == user.telegram_id)
                    & (SharedAccess.status == "ACCEPTED")
                )
                .scalar()
                or 0
            )
            access.position = max(max_pos_owned, max_pos_shared) + 1
            access.save()

            members = TaskManager.get_list_members(list_id)
            for m in members:
                if m.telegram_id != user.telegram_id:
                    await notify_user(
                        m.telegram_id,
                        f"👤 @{user_name} se ha unido a la lista '*{tlist.title}*'.",
                    )
            return True, f"Te has unido a la lista '*{tlist.title}*'."
        else:
            access.delete_instance()
            members = TaskManager.get_list_members(list_id)
            for m in members:
                if m.telegram_id != user.telegram_id:
                    await notify_user(
                        m.telegram_id,
                        f"👤 @{user_name} ha rechazado la invitación a '*{tlist.title}*'.",
                    )
            return True, f"Has rechazado la invitación a '*{tlist.title}*'."

    @staticmethod
    async def leave_list(user_id: int, list_id: int) -> tuple[bool, str]:
        user = User.get_or_none(User.telegram_id == user_id)
        if not user:
            return False, "Usuario no encontrado."

        try:
            access = SharedAccess.get(
                (SharedAccess.user == user) & (SharedAccess.task_list == list_id)
            )
            access.delete_instance()

            tlist = TaskList.get_by_id(list_id)
            user_name = user.username or user.first_name

            members = TaskManager.get_list_members(list_id)
            for m in members:
                if m.telegram_id != user.telegram_id:
                    await notify_user(
                        m.telegram_id,
                        f"👋 @{user_name} ha salido de la lista '*{tlist.title}*'.",
                    )
            return True, f"Has salido de la lista '*{tlist.title}*'."

        except SharedAccess.DoesNotExist:
            # Check if owner
            tlist = TaskList.get_or_none(TaskList.id == list_id)
            if tlist and tlist.owner_id == user_id:
                return False, "Como creador, no puedes salirte. Usa 'Borrar Lista'."
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
        # 1. Try DB search
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

        # 3. Reverse search
        all_lists = TaskManager.get_lists(user_id)
        name_norm = name.lower()

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
            if clean_name == title_norm:
                return task_list
            if title_norm in name_norm:
                return task_list
            if clean_name in title_norm:
                return task_list

        # 4. Fallback
        fallback = TaskList.select().where(TaskList.owner == user_id).first()
        if fallback:
            return fallback
        return None

    @staticmethod
    def get_lists(user_id: int) -> List[TaskList]:
        # Owned lists
        owned = list(TaskList.select().where(TaskList.owner == user_id))
        for task_list in owned:
            task_list._sort_pos = task_list.position

        # Shared lists
        # Query SharedAccess to get position and joined TaskList securely
        shared_accesses = (
            SharedAccess.select(SharedAccess, TaskList)
            .join(TaskList)
            .where((SharedAccess.user == user_id) & (SharedAccess.status == "ACCEPTED"))
        )

        shared = []
        for sa in shared_accesses:
            t_list = sa.task_list
            t_list._sort_pos = sa.position
            shared.append(t_list)

        # Merge and sort
        combined = owned + shared
        combined.sort(key=lambda x: (x._sort_pos if x._sort_pos is not None else 0))
        return combined

    @staticmethod
    def reorder_lists(user_id: int, list_ids: List[int]) -> bool:
        """Update positions for a list of list IDs."""
        try:
            with db.atomic():
                for index, list_id in enumerate(list_ids):
                    # Try update Owned
                    res_owned = (
                        TaskList.update(position=index)
                        .where((TaskList.id == list_id) & (TaskList.owner == user_id))
                        .execute()
                    )

                    if res_owned == 0:
                        # Try update Shared
                        SharedAccess.update(position=index).where(
                            (SharedAccess.task_list == list_id)
                            & (SharedAccess.user == user_id)
                        ).execute()
            return True
        except Exception as e:
            logger.error(f"Error reordering lists: {e}")
            return False

    @staticmethod
    def is_user_in_list(user_id: int, list_id: int) -> bool:
        lst = TaskList.get_or_none(TaskList.id == list_id)
        if not lst:
            return False
        if lst.owner.telegram_id == user_id:
            return True

        access = SharedAccess.get_or_none(
            (SharedAccess.task_list == list_id)
            & (SharedAccess.user == user_id)
            & (SharedAccess.status == "ACCEPTED")
        )
        return access is not None

    @staticmethod
    def delete_all_lists(user_id: int) -> int:
        """Deletes all lists owned by the user. Returns count of deleted lists."""
        try:
            # Get lists owned by user
            lists = TaskList.select().where(TaskList.owner == user_id)
            count = 0
            for lst in lists:
                # Reuse delete_list logic for safety/consistency
                if TaskManager.delete_list(user_id, lst.id):
                    count += 1
            logger.info(f"Deleted {count} lists for User={user_id}")
            return count
        except Exception as e:
            logger.error(f"Error deleting all lists: {e}")
            return 0

    @staticmethod
    def delete_list(user_id: int, list_id: int) -> bool:
        try:
            target_list = TaskList.get_by_id(list_id)
            if target_list.owner_id != user_id:
                logger.warning(f"Unauthorized list delete attempt by {user_id}")
                return False

            # Delete list (cascade deletes tasks usually, but let's be safe)
            # Peewee cascade depends on foreign key definition.
            # Explicit delete of tasks first if needed, but our model might have ON DELETE CASCADE
            # Let's rely on model definition or delete manually to be safe?
            # actually peewee's delete_instance recursive=True does the trick usually

            # Delete associated SharedAccess entries
            SharedAccess.delete().where(SharedAccess.task_list == target_list).execute()

            # Delete tasks
            Task.delete().where(Task.task_list == target_list).execute()

            target_list.delete_instance()
            logger.info(f"List DELETED: ID={list_id} by User={user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting list: {e}")
            return False

    @staticmethod
    def edit_list(user_id: int, list_id: int, new_name: str) -> bool:
        try:
            target_list = TaskList.get_by_id(list_id)
            if target_list.owner_id != user_id:
                logger.warning(f"Unauthorized list rename attempt by {user_id}")
                return False

            target_list.title = new_name
            target_list.save()
            logger.info(
                f"List RENAMED: ID={list_id} NewName='{new_name}' by User={user_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Error renaming list: {e}")
            return False

    @staticmethod
    def edit_list_color(user_id: int, list_id: int, color_hex: str) -> bool:
        try:
            target_list = TaskList.get_by_id(list_id)
            if target_list.owner_id != user_id:
                logger.warning(f"Unauthorized list color change attempt by {user_id}")
                return False

            target_list.color = color_hex
            target_list.save()
            return True
        except Exception as e:
            logger.error(f"Error changing list color: {e}")
            return False

    @staticmethod
    def get_pending_invites(user_id: int) -> List[dict]:
        query = (
            SharedAccess.select(SharedAccess, TaskList, User)
            .join(TaskList, on=(SharedAccess.task_list == TaskList.id))
            .join(User, on=(TaskList.owner == User.telegram_id))
            .where((SharedAccess.user == user_id) & (SharedAccess.status == "PENDING"))
        )

        results = []
        for access in query:
            tlist = access.task_list
            owner = tlist.owner
            results.append(
                {
                    "list_id": tlist.id,
                    "list_name": tlist.title,
                    "owner_name": owner.username or owner.first_name or "Unknown",
                    "invited_at": str(access.id),
                }
            )
        return results

    @staticmethod
    def get_dashboard_items(user_id: int) -> List[dict]:
        """Returns mixed Tasks and Lists for the 'All' / Todo tab."""
        # 1. Get Tasks (loose tasks, no list)
        tasks = list(
            Task.select().where((Task.user == user_id) & (Task.task_list.is_null()))
        )

        # 2. Get Lists
        lists = TaskManager.get_lists(user_id)

        items = []
        for t in tasks:
            items.append(
                {
                    "type": "task",
                    "data": t,
                    "created_at": t.created_at,
                    "position": t.position or 0,
                }
            )

        for lst in lists:
            items.append(
                {
                    "type": "list",
                    "data": lst,
                    "created_at": lst.created_at,
                    "position": getattr(lst, "_sort_pos", 0) or 0,
                }
            )

        # Sort by position, then created_at
        # Normalizing positions might be tricky if they are on different scales,
        # but the reorder logic will eventually unify them.
        # Initial sort: Position primarily.
        items.sort(key=lambda x: (x["position"], x["created_at"]))

        return items

    @staticmethod
    def get_dated_items(user_id: int) -> List[Task]:
        """Returns all tasks (loose or inside lists) that have a deadline."""
        query = Task.deadline.is_null(False)

        # Access control: Owned tasks OR tasks in lists user has access to
        # A simple way is to check:
        # 1. Owned by user
        # 2. OR in a list where user is a member

        # Subquery for shared list IDs
        shared_list_ids = SharedAccess.select(SharedAccess.task_list).where(
            (SharedAccess.user == user_id) & (SharedAccess.status == "ACCEPTED")
        )

        # Tasks user owns directly
        cond_owned = Task.user == user_id

        # Tasks in shared lists (even if created by others)
        cond_shared = Task.task_list.in_(shared_list_ids)

        tasks = list(
            Task.select(Task, TaskList)
            .join(
                TaskList, on=(Task.task_list == TaskList.id), join_type=JOIN.LEFT_OUTER
            )
            .where(query & (cond_owned | cond_shared))
            .order_by(Task.deadline, Task.priority)
        )

        return tasks

    @staticmethod
    def get_tasks_in_list(list_id: int) -> List[Task]:
        return list(
            Task.select()
            .where(Task.task_list == list_id)
            .order_by(Task.status.asc(), Task.created_at)
        )
