
import pytest
from datetime import datetime, timedelta
from src.database.repositories.task_repository import TaskManager
from src.database.models import User, Task, TaskList, SharedAccess, TaskStatus
from src.utils.schema import TaskSchema, TimeFilter

@pytest.fixture
def edge_data(test_db):
    u = User.create(username="u", telegram_id=999)
    t = Task.create(title="T", user=u)
    return u, t

def test_edit_task_edges(edge_data):
    u, t = edge_data

    # Non-existent
    res = TaskManager.edit_task(u.telegram_id, 99999, TaskSchema(title="X"))
    assert res is False

    # Empty updates
    # Use object with only None fields if possible, or filtered out logic
    # schema excludes unset. So if we pass default, it is empty?
    # TaskSchema has optional fields.
    # If we pass nothing?
    # TaskSchema(title="T") -> title is set.
    # We need a schema where model_dump(exclude_unset=True) is empty.
    # But TaskSchema requires title?
    # title is Optional[str] = None in some schemas? NO, TaskSchema creation usually requires title.
    # Let's check schema.
    pass

def test_update_status_edges(edge_data):
    u, _ = edge_data
    res = TaskManager.update_task_status(u.telegram_id, 99999, "COMPLETED")
    assert res is False

def test_recurrence_leap_year(edge_data):
    u, _ = edge_data
    # Create task on Feb 29, 2024 (Leap y)
    d = datetime(2024, 2, 29, 12, 0)
    t = Task.create(title="Leap", user=u, deadline=d, recurrence="YEARLY", status="PENDING")

    # Complete it
    TaskManager.update_task_status(u.telegram_id, t.id, "COMPLETED")

    # Check new task
    new_t = Task.select().where(Task.title == "Leap", Task.status == "PENDING").first()
    assert new_t is not None
    # Should be 2025-02-28
    assert new_t.deadline.year == 2025
    assert new_t.deadline.month == 2
    assert new_t.deadline.day == 28

def test_delete_filters_long_term(edge_data):
    u, _ = edge_data
    now = datetime.now()
    # Create tasks far in future
    t_month = Task.create(title="Month", user=u, deadline=now + timedelta(days=20), status="PENDING")
    t_year = Task.create(title="Year", user=u, deadline=now + timedelta(days=100), status="PENDING")

    # Delete Month
    cnt = TaskManager.delete_all_pending_tasks(u.telegram_id, TimeFilter.MONTH)
    assert cnt >= 1
    assert Task.get_or_none(Task.id == t_month.id) is None
    assert Task.get_or_none(Task.id == t_year.id) is not None

    # Delete Year
    TaskManager.delete_all_pending_tasks(u.telegram_id, TimeFilter.YEAR)
    assert Task.get_or_none(Task.id == t_year.id) is None

def test_get_pending_invites(test_db):
    owner = User.create(telegram_id=1, username="owner")
    invitee = User.create(telegram_id=2, username="invitee")

    # Create list and share pending
    l = TaskList.create(title="L", owner=owner)
    SharedAccess.create(user=invitee, task_list=l, status="PENDING")

    invites = TaskManager.get_pending_invites(invitee.telegram_id)
    assert len(invites) == 1
    assert invites[0]["list_name"] == "L"
    assert invites[0]["owner_name"] == "owner"
