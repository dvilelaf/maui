from datetime import datetime
from typing import List, Optional
from src.database.models import User, Task, TaskList, SharedAccess
from src.utils.schema import TaskSchema, TimeFilter, TaskStatus

import logging

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

        query = (Task.user == user_id) & (Task.status == TaskStatus.PENDING)

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

        query = (Task.user == user_id) & (Task.status == TaskStatus.PENDING)

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
    def find_tasks_by_keyword(user_id: int, keyword: str) -> List[Task]:
        return list(
            Task.select().where(
                (Task.user == user_id)
                & (Task.status == TaskStatus.PENDING)
                & (
                    (Task.title.contains(keyword))
                    | (Task.description.contains(keyword))
                )
            )
        )

    @staticmethod
    def create_list(user_id: int, title: str) -> TaskList:
        return TaskList.create(title=title, owner=user_id)

    @staticmethod
    def share_list(list_id: int, target_username: str) -> tuple[bool, str]:
        """
        Returns (Success, Message)
        """
        target_username = target_username.replace("@", "")
        try:
            target_user = User.get(User.username == target_username)
        except User.DoesNotExist:
            return False, f"Usuario @{target_username} no encontrado."

        # Check if already shared
        exists = (
            SharedAccess.select()
            .where(
                (SharedAccess.task_list == list_id) & (SharedAccess.user == target_user)
            )
            .exists()
        )
        if exists:
            return False, f"La lista ya está compartida con @{target_username}."

        SharedAccess.create(
            user=target_user,
            task_list=list_id,
            status="ACCEPTED",  # Auto-accept for now to simplify, or PENDING if strict
        )
        return True, f"Lista compartida con @{target_username}."

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
        # Search owned lists
        owned = (
            TaskList.select()
            .where((TaskList.owner == user_id) & (TaskList.title.contains(name)))
            .first()
        )
        if owned:
            return owned

        # Search shared lists
        shared = (
            TaskList.select()
            .join(SharedAccess)
            .where(
                (SharedAccess.user == user_id)
                & (SharedAccess.status == "ACCEPTED")
                & (TaskList.title.contains(name))
            )
            .first()
        )
        return shared
