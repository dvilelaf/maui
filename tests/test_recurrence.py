
import pytest
from datetime import datetime, timedelta
from src.database.models import User, Task, TaskList, TaskStatus
from src.database.repositories.task_repository import TaskManager
import calendar

@pytest.fixture
def user(test_db):
    return User.create(username="testuser", telegram_id=123)

@pytest.fixture
def task_list(test_db, user):
    return TaskList.create(title="Inbox", owner=user)

def test_recurrence_daily(test_db, user, task_list):
    # Setup
    deadline = datetime(2025, 1, 1, 10, 0, 0)
    task = Task.create(
        user=user,
        task_list=task_list,
        title="Daily Task",
        recurrence="DAILY",
        deadline=deadline,
        status=TaskStatus.PENDING
    )

    # Action: Complete Task
    success = TaskManager.update_task_status(user.telegram_id, task.id, TaskStatus.COMPLETED)
    assert success is True

    # Verify: Old task is completed
    task = Task.get(Task.id == task.id)
    assert task.status == TaskStatus.COMPLETED

    # Verify: New task spawned
    new_tasks = Task.select().where(
        (Task.title == "Daily Task") &
        (Task.status == TaskStatus.PENDING) &
        (Task.id != task.id)
    )
    assert new_tasks.count() == 1
    new_task = new_tasks.first()

    # Verify deadline is +1 day
    expected_date = deadline + timedelta(days=1)
    assert new_task.deadline == expected_date
    assert new_task.recurrence == "DAILY"

def test_recurrence_weekly(test_db, user, task_list):
    deadline = datetime(2025, 1, 1, 10, 0, 0) # Wednesday
    task = Task.create(
        user=user, task_list=task_list, title="Weekly Task",
        recurrence="WEEKLY", deadline=deadline, status=TaskStatus.PENDING
    )

    TaskManager.update_task_status(user.telegram_id, task.id, TaskStatus.COMPLETED)

    new_task = Task.select().where((Task.title == "Weekly Task") & (Task.status == TaskStatus.PENDING)).first()
    assert new_task is not None
    assert new_task.deadline == deadline + timedelta(weeks=1)

def test_recurrence_monthly(test_db, user, task_list):
    # Jan 15 -> Feb 15
    deadline = datetime(2025, 1, 15, 10, 0, 0)
    task = Task.create(
        user=user, task_list=task_list, title="Monthly Task",
        recurrence="MONTHLY", deadline=deadline, status=TaskStatus.PENDING
    )

    TaskManager.update_task_status(user.telegram_id, task.id, TaskStatus.COMPLETED)

    new_task = Task.select().where((Task.title == "Monthly Task") & (Task.status == TaskStatus.PENDING)).first()
    assert new_task.deadline == datetime(2025, 2, 15, 10, 0, 0)

def test_recurrence_monthly_end_of_month(test_db, user, task_list):
    # Jan 31 -> Feb 28 (2025 is not leap)
    deadline = datetime(2025, 1, 31, 10, 0, 0)
    task = Task.create(
        user=user, task_list=task_list, title="Monthly End",
        recurrence="MONTHLY", deadline=deadline, status=TaskStatus.PENDING
    )

    TaskManager.update_task_status(user.telegram_id, task.id, TaskStatus.COMPLETED)

    new_task = Task.select().where((Task.title == "Monthly End") & (Task.status == TaskStatus.PENDING)).first()
    assert new_task.deadline == datetime(2025, 2, 28, 10, 0, 0)

def test_recurrence_yearly(test_db, user, task_list):
    deadline = datetime(2025, 6, 1, 10, 0, 0)
    task = Task.create(
        user=user, task_list=task_list, title="Yearly Task",
        recurrence="YEARLY", deadline=deadline, status=TaskStatus.PENDING
    )

    TaskManager.update_task_status(user.telegram_id, task.id, TaskStatus.COMPLETED)

    new_task = Task.select().where((Task.title == "Yearly Task") & (Task.status == TaskStatus.PENDING)).first()
    assert new_task.deadline == datetime(2026, 6, 1, 10, 0, 0)

def test_simple_completion_no_recurrence(test_db, user, task_list):
    task = Task.create(
        user=user, task_list=task_list, title="Once Task",
        recurrence=None, status=TaskStatus.PENDING
    )

    TaskManager.update_task_status(user.telegram_id, task.id, TaskStatus.COMPLETED)

    # Should NOT spawn new task
    count = Task.select().where(Task.title == "Once Task").count()
    assert count == 1 # Just the completed one

def test_idempotency_does_not_double_spawn(test_db, user, task_list):
    # If I call 'complete' on an already completed recurring task, it should not spawn again.
    task = Task.create(
        user=user, task_list=task_list, title="Double Tap",
        recurrence="DAILY", deadline=datetime.now(), status=TaskStatus.COMPLETED
    )

    # Attempt to complete again
    TaskManager.update_task_status(user.telegram_id, task.id, TaskStatus.COMPLETED)

    # Should be 1 total (itself), no new spawns because it was already completed
    # Wait, update_task_status might check if status != COMPLETED.
    # Let's verify the logic in repository:
    # "if status == TaskStatus.COMPLETED and task.recurrence and task.status != TaskStatus.COMPLETED"
    # So yes, it prevents it.

    count = Task.select().where(Task.title == "Double Tap").count()
    assert count == 1
