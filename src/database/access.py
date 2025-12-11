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
    def get_pending_tasks(user_id: int) -> List[Task]:
        return list(Task.select().where(
            (Task.user == user_id) &
            (Task.status == "PENDING")
        ).order_by(Task.deadline.asc(), Task.priority.desc()))

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
