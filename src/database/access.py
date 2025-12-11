from datetime import datetime
from typing import List, Optional
from src.database.models import User, Task
from src.database.core import db

class UserManager:
    @staticmethod
    def get_or_create_user(telegram_id: int, username: str = None) -> User:
        user, created = User.get_or_create(
            telegram_id=telegram_id,
            defaults={'username': username}
        )
        if not created and username and user.username != username:
            user.username = username
            user.save()
        return user

class TaskManager:
    @staticmethod
    def add_task(user_id: int, task_data: dict) -> Task:
        # task_data should hopefully match the fields or be a Pydantic model dump
        # The prompt extraction returns a formatted task, which we will dump to dict
        new_task = Task.create(
            user=user_id,
            title=task_data.get('title'),
            description=task_data.get('description'),
            priority=task_data.get('priority', 'MEDIUM'),
            deadline=task_data.get('deadline'),
            status="PENDING",
            created_at=datetime.now()
        )
        return new_task

    @staticmethod
    def get_pending_tasks(user_id: int, time_filter: str = "ALL") -> List[Task]:
        from datetime import datetime, timedelta

        query = (Task.user == user_id) & (Task.status == "PENDING")

        now = datetime.now()

        if time_filter == "TODAY":
            # Deadline <= Today 23:59:59 (and not none)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            query &= (Task.deadline <= end_of_day)

        elif time_filter == "WEEK":
            # Deadline <= Now + 7 days
            end_of_week = now + timedelta(days=7)
            query &= (Task.deadline <= end_of_week)

        elif time_filter == "MONTH":
             # Deadline <= Now + 30 days
            end_of_month = now + timedelta(days=30)
            query &= (Task.deadline <= end_of_month)

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
    def delete_all_pending_tasks(user_id: int, time_filter: str = "ALL") -> int:
        from datetime import datetime, timedelta

        query = (Task.user == user_id) & (Task.status == "PENDING")

        now = datetime.now()

        if time_filter == "TODAY":
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            query &= (Task.deadline <= end_of_day)

        elif time_filter == "WEEK":
            end_of_week = now + timedelta(days=7)
            query &= (Task.deadline <= end_of_week)

        elif time_filter == "MONTH":
            end_of_month = now + timedelta(days=30)
            query &= (Task.deadline <= end_of_month)

        return Task.delete().where(query).execute()

    @staticmethod
    def edit_task(task_id: int, **kwargs) -> bool:
        if not kwargs:
            return False

        # Filter kwargs to only allow valid fields
        allowed_fields = {'title', 'description', 'deadline', 'priority', 'status'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        return Task.update(**updates).where(Task.id == task_id).execute() > 0

    @staticmethod
    def find_tasks_by_keyword(user_id: int, keyword: str) -> List[Task]:
        return list(Task.select().where(
            (Task.user == user_id) &
            (Task.status == "PENDING") &
            ((Task.title.contains(keyword)) | (Task.description.contains(keyword)))
        ))
