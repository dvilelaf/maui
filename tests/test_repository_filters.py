
import pytest
from datetime import datetime, timedelta
from src.database.repositories.task_repository import TaskManager
from src.database.models import Task, User, TaskList, TaskStatus
from src.utils.schema import TimeFilter

@pytest.fixture
def filter_data(test_db):
    user = User.create(username="filter_user", telegram_id=800)

    now = datetime.now()
    t_today = Task.create(title="Today", user=user, deadline=now, status=TaskStatus.PENDING)
    t_tomorrow = Task.create(title="Tomorrow", user=user, deadline=now + timedelta(days=1), status=TaskStatus.PENDING)
    t_next_month = Task.create(title="Next Month", user=user, deadline=now + timedelta(days=40), status=TaskStatus.PENDING)

    return user, [t_today, t_tomorrow, t_next_month]

def test_delete_pending_today(filter_data):
    user, tasks = filter_data

    # Delete TODAY only
    count = TaskManager.delete_all_pending_tasks(user.telegram_id, TimeFilter.TODAY)

    # Should delete "Today" task. "Tomorrow" is > end of today?
    # If now is 23:30, tomorrow is +24h.
    # The filter logic constructs end_of_day.

    assert count == 1
    assert Task.get_or_none(Task.id == tasks[0].id) is None
    assert Task.get_or_none(Task.id == tasks[1].id) is not None

def test_delete_pending_week(filter_data):
    user, tasks = filter_data
    # Delete WEEK
    # Reset data or rely on previous test having deleted one? Better to create fresh.
    # But fixture executes once per test if requesting 'filter_data' again? No, scoping.
    # Fixture default scope is function. So new data every test.

    count = TaskManager.delete_all_pending_tasks(user.telegram_id, TimeFilter.WEEK)
    # Today and Tomorrow should be in week. Next month not.
    assert count == 2

def test_get_pending_priority_filter(filter_data):
    user, _ = filter_data
    Task.create(title="High Priority", user=user, priority="HIGH", status="PENDING")

    tasks = TaskManager.get_pending_tasks(user.telegram_id, priority_filter="HIGH")
    assert len(tasks) == 1
    assert tasks[0].priority == "HIGH"

@pytest.mark.asyncio
async def test_share_list_errors(test_db):
    u1 = User.create(username="u1", telegram_id=1001)
    u2 = User.create(username="u2", telegram_id=1002)
    lst = TaskList.create(title="My List", owner=u1)

    # Self share
    # (The code might verify owner vs target logic? Or just fail to find self via query if not handled)
    # share_list takes a string query.

    # Unowned list
    res, msg = await TaskManager.share_list(u2.telegram_id, lst.id, "u1")
    assert res is False
    assert "No tienes permiso" in msg

    # User not found
    res, msg = await TaskManager.share_list(u1.telegram_id, lst.id, "ghost")
    assert res is False
    assert "no encontrado" in msg

    # Ambiguous user
    # Create similar users
    User.create(first_name="John", username="john1", telegram_id=2001)
    User.create(first_name="John", username="john2", telegram_id=2002)

    # Search "John"
    res, msg = await TaskManager.share_list(u1.telegram_id, lst.id, "John")
    assert res is False
    assert "varios usuarios" in msg

@pytest.mark.asyncio
async def test_leave_list_errors(test_db):
    u1 = User.create(username="u1", telegram_id=1001)
    lst = TaskList.create(title="My List", owner=u1)

    # Leave owned list
    res, msg = await TaskManager.leave_list(u1.telegram_id, lst.id)
    assert res is False
    assert "creador" in msg

    # Leave list not member
    u2 = User.create(username="u2", telegram_id=1002)
    res, msg = await TaskManager.leave_list(u2.telegram_id, lst.id)
    assert res is False
    assert "No eres miembro" in msg
