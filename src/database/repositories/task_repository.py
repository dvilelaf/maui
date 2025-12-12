from datetime import datetime, timedelta
from typing import List, Optional
from peewee import fn
import logging

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
    def get_user_tasks(
        user_id: int,
        sort_by: str = "deadline"
    ) -> List[Task]:
        """Get all tasks (pending and completed) for a user, excluding tasks in lists."""

        query = (Task.user == user_id) & (Task.task_list.is_null()) & (Task.status != "CANCELLED")
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
        updates = update_data.model_dump(exclude_unset=True)
        updates = {k: v for k, v in updates.items() if v is not None}

        if not updates:
            return False

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
        query_str = target_query.strip().replace("@", "")

        target_user = User.get_or_none(User.username == query_str)

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
            members = TaskManager.get_list_members(list_id)
            for m in members:
                 if m.telegram_id != user.telegram_id:
                     await notify_user(
                        m.telegram_id,
                        f"👤 @{user_name} ha rechazado la invitación a '*{tlist.title}*'."
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
                "lista", "list", "de", "la", "el", "the", "una", "un", "los", "las",
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

        # Shared lists
        shared = list(
            TaskList.select()
            .join(SharedAccess)
            .where((SharedAccess.user == user_id) & (SharedAccess.status == "ACCEPTED"))
        )
        return owned + shared

    @staticmethod
    def delete_list(user_id: int, list_id: int) -> bool:
        try:
            lst = TaskList.get_or_none(TaskList.id == list_id)
            if not lst:
                return False

            if lst.owner.telegram_id != user_id:
                return False

            Task.delete().where(Task.task_list == list_id).execute()
            SharedAccess.delete().where(SharedAccess.task_list == list_id).execute()
            ls_count = lst.delete_instance()
            return ls_count > 0
        except Exception as e:
            logger.error(f"Error deleting list {list_id}: {e}")
            return False

    @staticmethod
    def get_pending_invites(user_id: int) -> List[dict]:
        query = (
            SharedAccess.select(SharedAccess, TaskList, User)
            .join(TaskList, on=(SharedAccess.task_list == TaskList.id))
            .join(User, on=(TaskList.owner == User.telegram_id))
            .where(
                (SharedAccess.user == user_id)
                & (SharedAccess.status == "PENDING")
            )
        )

        results = []
        for access in query:
            tlist = access.task_list
            owner = tlist.owner
            results.append({
                "list_id": tlist.id,
                "list_name": tlist.title,
                "owner_name": owner.username or owner.first_name or "Unknown",
                "invited_at": str(access.id)
            })
        return results

    @staticmethod
    def get_tasks_in_list(list_id: int) -> List[Task]:
        return list(
            Task.select()
            .where(Task.task_list == list_id)
            .order_by(Task.status, Task.created_at)
        )
