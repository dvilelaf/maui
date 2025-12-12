
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.database.access import (
    resolve_user,
    confirm_action,
    kick_user,
    update_status,
    UserManager,
    TaskManager,
    notify_user
)
from src.utils.schema import UserStatus, TaskSchema
from src.database.models import User, Task, TaskList, SharedAccess

@pytest.fixture
def mock_input(mocker):
    return mocker.patch("builtins.input")

@pytest.mark.asyncio
async def test_notify_user_error(mocker):
    mocker.patch("src.database.access.Bot", side_effect=Exception("Bot Error"))
    # Should not raise
    await notify_user(123, "msg")

def test_resolve_user(test_db):
    u = User.create(telegram_id=100, username="test_u")

    assert resolve_user("100") == u
    assert resolve_user("@test_u") == u
    assert resolve_user("test_u") == u
    assert resolve_user("999") is None

def test_confirm_action(mock_input):
    mock_input.return_value = "y"
    assert confirm_action("Prompt") is True
    mock_input.return_value = "n"
    assert confirm_action("Prompt") is False

def test_kick_user(test_db, mock_input, mocker):
    u = User.create(telegram_id=200, username="kicked")
    Task.create(user=u, title="T1")

    mock_input.return_value = "y"

    # Spy on prints or logger?
    # Logic: user should be deleted.
    kick_user(200)
    assert User.get_or_none(User.telegram_id == 200) is None

    # Test not found
    kick_user(999) # Should print not found, safe

    # Test cancelled
    u2 = User.create(telegram_id=201)
    mock_input.return_value = "n"
    kick_user(201)
    assert User.get_or_none(User.telegram_id == 201) is not None

    # Test Exception
    mock_input.return_value = "y"
    mocker.patch("src.database.models.User.delete_instance", side_effect=Exception("Del Error"))
    kick_user(201) # Should handle error

def test_update_status(test_db, mocker):
    u = User.create(telegram_id=300, status="PENDING")

    mock_notify = mocker.patch("src.database.access.notify_user")

    # Whitelist
    update_status(u, UserStatus.WHITELISTED)
    assert u.status == UserStatus.WHITELISTED
    mock_notify.assert_called()

    # Blacklist
    update_status(u, UserStatus.BLACKLISTED)
    assert u.status == UserStatus.BLACKLISTED

    # Exception coverage
    mocker.patch("src.database.models.User.save", side_effect=Exception("Save Error"))
    update_status(u, UserStatus.PENDING) # Safe

def test_user_manager_updates(test_db):
    u = UserManager.get_or_create_user(400, "orig", "F", "L")
    assert u.username == "orig"

    # Update fields
    u2 = UserManager.get_or_create_user(400, "new", "F2", "L2")
    assert u2.username == "new"
    assert u2.first_name == "F2"
    assert u2.last_name == "L2"

def test_task_manager_add_task_dupe(test_db):
    u = User.create(telegram_id=500)
    ts = TaskSchema(title="Dupe Task", priority="LOW")

    t1 = TaskManager.add_task(500, ts)
    assert t1 is not None

    # Add duplicate (same title, pending)
    t2 = TaskManager.add_task(500, ts)
    assert t2 is None

    # With list
    tl = TaskList.create(title="MyList", owner=u)
    ts_list = TaskSchema(title="List Task", priority="LOW", list_name="MyList")
    t3 = TaskManager.add_task(500, ts_list)
    assert t3.task_list == tl

def test_find_list_by_name(test_db):
    u = User.create(telegram_id=600, username="owner", first_name="Owner")
    l1 = TaskList.create(title="Groceries List", owner=u)
    l2 = TaskList.create(title="Work", owner=u)

    # Owned exact/partial
    assert TaskManager.find_list_by_name(600, "Groceries").id == l1.id
    assert TaskManager.find_list_by_name(600, "work").id == l2.id

    # Reverse search "list of groceries" -> "Groceries"
    assert TaskManager.find_list_by_name(600, "lista de groceries").id == l1.id

    # Fallback
    assert TaskManager.find_list_by_name(600, "NonExistent").id in [l1.id, l2.id] # returns first found

@pytest.mark.asyncio
async def test_share_list(test_db, mocker):
    mocker.patch("src.database.access.notify_user", new_callable=AsyncMock)
    owner = User.create(telegram_id=700, username="owner700")
    other = User.create(telegram_id=701, username="other701", first_name="Other")
    tl = TaskList.create(title="Shared", owner=owner)

    # Share success
    success, msg = await TaskManager.share_list(tl.id, "other701")
    assert success
    assert "compartida" in msg

    # Check members
    members = TaskManager.get_list_members(tl.id)
    assert other in members

    # Share duplicate
    success, msg = await TaskManager.share_list(tl.id, "other701")
    assert not success
    assert "ya está compartida" in msg

    # Share not found
    success, msg = await TaskManager.share_list(tl.id, "nobody")
    assert not success

    # Fuzzy search multiple
    u3 = User.create(telegram_id=702, first_name="OtherName")
    u4 = User.create(telegram_id=703, first_name="OtherName")

    success, msg = await TaskManager.share_list(tl.id, "OtherName")
    assert success is False
    assert "varios usuarios" in msg

def test_pending_tasks_filters(test_db):
    from datetime import datetime
    from src.utils.schema import TimeFilter
    u = User.create(telegram_id=800)

    # Create tasks with differing deadlines
    now = datetime.now()
    # Today task
    Task.create(user=u, title="Today", deadline=now)
    from datetime import timedelta
    # Week task (6 days)
    Task.create(user=u, title="Week", deadline=now + timedelta(days=6))
    # Month task (20 days)
    Task.create(user=u, title="Month", deadline=now + timedelta(days=20))
    # Year task (300 days)
    # Task.create(user=u, title="Year", deadline=now + timedelta(days=300)) # Simplified

    t_today = TaskManager.get_pending_tasks(800, TimeFilter.TODAY)
    # assert len(t_today) >= 1 # logic verification

    # Priority Filter
    Task.create(user=u, title="HighPrio", priority="HIGH")
    t_high = TaskManager.get_pending_tasks(800, priority_filter="HIGH")
    assert len(t_high) >= 1
    assert t_high[0].priority == "HIGH"

def test_delete_all_filters(test_db):
    from src.utils.schema import TimeFilter
    u = User.create(telegram_id=900)
    Task.create(user=u, title="T1")

    # Delete with filter
    cnt = TaskManager.delete_all_pending_tasks(900, TimeFilter.TODAY)
    # logic verify

    cnt = TaskManager.delete_all_pending_tasks(900, TimeFilter.WEEK)
    cnt = TaskManager.delete_all_pending_tasks(900, TimeFilter.MONTH)
    cnt = TaskManager.delete_all_pending_tasks(900, TimeFilter.YEAR)

def test_edit_task_empty_updates(test_db):
    u = User.create(telegram_id=1000)
    t = Task.create(user=u, title="Orig")
    ts = TaskSchema(title="Orig") # No changes effectively if unset? Or same.
    # We need empty update dict.
    # TaskSchema defaults fields to None.
    ts_empty = TaskSchema() # all None/unset
    res = TaskManager.edit_task(t.id, ts_empty)
    assert res is False

