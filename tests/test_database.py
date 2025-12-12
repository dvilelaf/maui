import pytest
from unittest.mock import MagicMock, AsyncMock
from src.database.models import User, Task, TaskList, SharedAccess
from src.database.access import UserManager, TaskManager
from src.utils.schema import TaskSchema, TimeFilter, UserStatus, TaskStatus
from datetime import datetime, timedelta

@pytest.fixture
def user(test_db):
    return UserManager.get_or_create_user(12345, "testuser", "Test", "User")

def test_register_user(test_db):
    user = UserManager.get_or_create_user(111, "newuser", "New", "User")
    assert user.telegram_id == 111
    assert user.username == "newuser"

    # Test duplicate registration (should update or return existing)
    user2 = UserManager.get_or_create_user(111, "newuser", "New", "User")
    assert user2.telegram_id == 111
    assert User.select().count() == 1

def test_add_task(test_db, user):
    task_data = TaskSchema(title="Buy Milk", priority="HIGH")
    task = TaskManager.add_task(user.telegram_id, task_data)

    assert task.title == "Buy Milk"
    assert task.priority == "HIGH"
    assert task.status == TaskStatus.PENDING
    assert task.user == user

def test_get_pending_tasks(test_db, user):
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Task 1"))
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Task 2"))

    tasks = TaskManager.get_pending_tasks(user.telegram_id)
    assert len(tasks) == 2
    assert tasks[0].title == "Task 1"

def test_task_list_separation(test_db, user):
    """Verify that tasks in a list do NOT appear in general pending tasks."""
    # Create a general task
    TaskManager.add_task(user.telegram_id, TaskSchema(title="General Task"))

    # Create a list and add a task to it
    tlist = TaskManager.create_list(user.telegram_id, "Shopping")
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Milk", list_name="Shopping"))

    # Check general tasks
    pending = TaskManager.get_pending_tasks(user.telegram_id)
    assert len(pending) == 1
    assert pending[0].title == "General Task"

    # Check list tasks
    list_tasks = TaskManager.get_tasks_in_list(tlist.id)
    assert len(list_tasks) == 1
    assert list_tasks[0].title == "Milk"

@pytest.mark.asyncio
async def test_share_list(test_db, user, mocker):
    # Mock notify
    mocker.patch("src.database.access.notify_user", new_callable=AsyncMock)
    # Create another user
    other = UserManager.get_or_create_user(67890, "friend", "Best", "Friend")

    tlist = TaskManager.create_list(user.telegram_id, "Shared List")

    # Share exact match
    success, msg = await TaskManager.share_list(tlist.id, "friend")
    assert success
    assert "Invitación enviada" in msg

    # Accept invite
    await TaskManager.respond_to_invite(other.telegram_id, tlist.id, True)

    # Verify access
    shared_lists = TaskManager.get_lists(other.telegram_id)
    assert len(shared_lists) == 1
    assert shared_lists[0].title == "Shared List"

@pytest.mark.asyncio
async def test_share_list_fuzzy(test_db, user, mocker):
    """Test fuzzy matching for sharing."""
    mocker.patch("src.database.access.notify_user", new_callable=AsyncMock)
    UserManager.get_or_create_user(999, "dave123", "David", "Vilela")

    tlist = TaskManager.create_list(user.telegram_id, "Project")

    # Share by First Name
    success, msg = await TaskManager.share_list(tlist.id, "David")
    assert success
    assert "David" in msg or "dave123" in msg

def test_find_list_by_name(test_db, user):
    TaskManager.create_list(user.telegram_id, "Shopping List")

    # Exact
    l1 = TaskManager.find_list_by_name(user.telegram_id, "Shopping List")
    assert l1 is not None

    # Partial
    l2 = TaskManager.find_list_by_name(user.telegram_id, "Shopping")
    assert l2 is not None
    assert l2.id == l1.id

    # Normalized (e.g. "lista de la compra" -> matches "Compra" if exists, or "Shopping" if synonym logic existed but here mainly stopword removal)
    # Actually logic removes stopwords. "lista de la Shopping" -> "Shopping"
    l3 = TaskManager.find_list_by_name(user.telegram_id, "lista de la Shopping")
    assert l3 is not None

def test_resolve_user(test_db):
    u = UserManager.get_or_create_user(123, "john_doe", "John", "Doe")

    # ID
    from src.database.access import resolve_user
    assert resolve_user("123") == u

    # Username with @
    assert resolve_user("@john_doe") == u

    # Username without @
    assert resolve_user("john_doe") == u

    # Not found
    assert resolve_user("999") is None

def test_update_status(test_db, user, mocker):
    mocker.patch("src.database.access.notify_user") # Mock async notify
    from src.database.access import update_status

    update_status(user, UserStatus.WHITELISTED)
    assert user.status == UserStatus.WHITELISTED

    update_status(user, UserStatus.BLACKLISTED)
    assert user.status == UserStatus.BLACKLISTED

def test_delete_task(test_db, user):
    t = TaskManager.add_task(user.telegram_id, TaskSchema(title="Delete Me"))
    assert TaskManager.delete_task(t.id) is True
    assert Task.get_or_none(Task.id == t.id) is None

def test_delete_all_pending_tasks(test_db, user):
    TaskManager.add_task(user.telegram_id, TaskSchema(title="T1"))
    TaskManager.add_task(user.telegram_id, TaskSchema(title="T2"))

    # Test Time Filter (ALL)
    count = TaskManager.delete_all_pending_tasks(user.telegram_id)
    assert count == 2
    assert len(TaskManager.get_pending_tasks(user.telegram_id)) == 0

def test_edit_task(test_db, user):
    t = TaskManager.add_task(user.telegram_id, TaskSchema(title="Old"))

    # Update title
    TaskManager.edit_task(t.id, TaskSchema(title="New"))
    t_db = Task.get_by_id(t.id)
    assert t_db.title == "New"

    # Update status
    TaskManager.edit_task(t.id, TaskSchema(status=TaskStatus.COMPLETED))
    t_db = Task.get_by_id(t.id)
    assert t_db.status == TaskStatus.COMPLETED

def test_find_tasks_by_keyword(test_db, user):
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Buy Apples"))
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Sell Oranges", description="Juicy apples"))

    # Match title
    res = TaskManager.find_tasks_by_keyword(user.telegram_id, "Apples")
    assert len(res) == 2 # "Buy Apples" and "Sell Oranges" (desc contains apples)

    # Case insensitive check (Code uses .contains which is case sensitive in standard SQLite unless configured? Peewee contains is usually LIKE which is CI in SQLite default)
    # Let's verify behavior. If it fails I'll know.
    # Actually Peewee contains maps to LIKE '...'. SQLite LIKE is case-insensitive for ASCII.

    res2 = TaskManager.find_tasks_by_keyword(user.telegram_id, "oranges")
    assert len(res2) == 1

@pytest.mark.asyncio
async def test_notify_user(mocker):
    mock_bot = mocker.patch("src.database.access.Bot")
    mock_instance = mock_bot.return_value
    mock_instance.send_message = AsyncMock()

    from src.database.access import notify_user
    await notify_user(123, "Test")
    mock_instance.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_notify_user_failure(mocker):
    mock_bot = mocker.patch("src.database.access.Bot")
    mock_instance = mock_bot.return_value
    mock_instance.send_message = AsyncMock(side_effect=Exception("Fail"))

    from src.database.access import notify_user
    # Should check log, but main goal is no crash
    await notify_user(123, "Test")

def test_kick_user(test_db, mocker):
    from src.database.access import kick_user, UserManager

    # 1. User not found
    kick_user(9999) # Should just print return

    # 2. Cancelled
    u1 = UserManager.get_or_create_user(8881, "kick_cancel")
    mocker.patch("builtins.input", return_value="n")
    kick_user(8881)
    assert User.get_or_none(User.telegram_id == 8881) is not None

    # 3. Success
    u2 = UserManager.get_or_create_user(8882, "kick_success")
    TaskManager.add_task(8882, TaskSchema(title="Task to Delete"))
    mocker.patch("builtins.input", return_value="y")
    kick_user(8882)
    assert User.get_or_none(User.telegram_id == 8882) is None
    assert Task.select().where(Task.user == 8882).count() == 0

def test_add_task_duplicate(test_db):
    user = UserManager.get_or_create_user(700, "dupe_tester")
    t1 = TaskManager.add_task(700, TaskSchema(title="Unique Task"))
    assert t1 is not None

    # Add same title (case insensitive test implied by code but here exact match)
    t2 = TaskManager.add_task(700, TaskSchema(title="Unique Task"))
    assert t2 is None

def test_get_pending_tasks_filters(test_db):
    user = UserManager.get_or_create_user(701, "filter_tester")
    now = datetime.now()

    # Add tasks with diverse deadlines
    TaskManager.add_task(701, TaskSchema(title="Today", deadline=now))
    TaskManager.add_task(701, TaskSchema(title="Week", deadline=now + timedelta(days=5)))
    TaskManager.add_task(701, TaskSchema(title="Month", deadline=now + timedelta(days=20)))
    TaskManager.add_task(701, TaskSchema(title="Year", deadline=now + timedelta(days=200)))
    TaskManager.add_task(701, TaskSchema(title="Way Future", deadline=now + timedelta(days=500)))

    tasks_today = TaskManager.get_pending_tasks(701, TimeFilter.TODAY)
    assert len(tasks_today) == 1
    assert tasks_today[0].title == "Today"

    tasks_week = TaskManager.get_pending_tasks(701, TimeFilter.WEEK)
    assert len(tasks_week) == 2 # Today + Week

    tasks_month = TaskManager.get_pending_tasks(701, TimeFilter.MONTH)
    assert len(tasks_month) == 3

    tasks_year = TaskManager.get_pending_tasks(701, TimeFilter.YEAR)
    assert len(tasks_year) == 4

@pytest.mark.asyncio
async def test_share_list_edge_cases(test_db, mocker):
    mocker.patch("src.database.access.notify_user", new_callable=AsyncMock)
    owner = UserManager.get_or_create_user(800, "owner")
    l = TaskManager.create_list(800, "My List")

    # 1. Not found
    success, msg = await TaskManager.share_list(l.id, "nobody")
    assert not success
    assert "no encontrado" in msg

    # 2. Multiple matches
    UserManager.get_or_create_user(801, "juan_perez")
    UserManager.get_or_create_user(802, "juan_lopez")
    success, msg = await TaskManager.share_list(l.id, "juan")
    assert not success
    assert "varios usuarios" in msg

    # 3. Already shared
    UserManager.get_or_create_user(803, "unique_friend")
    await TaskManager.share_list(l.id, "unique_friend")
    # Try again
    success, msg = await TaskManager.share_list(l.id, "unique_friend")
    assert not success
    assert "ya está compartida" in msg

def test_find_list_by_name_fallbacks(test_db):
    u = UserManager.get_or_create_user(900, "list_finder")
    l1 = TaskManager.create_list(900, "Lista de Compra")
    l2 = TaskManager.create_list(900, "Proyecto X")

    # Exact/Clean match
    found = TaskManager.find_list_by_name(900, "compra")
    assert found.id == l1.id

    # Fallback to first owned
    found_fallback = TaskManager.find_list_by_name(900, "Unknown List")
    assert found_fallback is not None # Should return first owned

    # Make sure we have no lists
    u2 = UserManager.get_or_create_user(901, "poor_user")
    assert TaskManager.find_list_by_name(901, "anything") is None

def test_user_update_fields(test_db):
    u = UserManager.get_or_create_user(555, "initial", "First", "Last")
    # Update first name
    u2 = UserManager.get_or_create_user(555, "initial", "UpdatedFirst", "Last")
    assert u2.first_name == "UpdatedFirst"

    # Update last name
    u3 = UserManager.get_or_create_user(555, "initial", "UpdatedFirst", "UpdatedLast")
    assert u3.last_name == "UpdatedLast"

@pytest.mark.asyncio
async def test_get_list_members(test_db, mocker):
    mocker.patch("src.database.access.notify_user", new_callable=AsyncMock)
    owner = UserManager.get_or_create_user(600, "owner")
    l = TaskManager.create_list(600, "Membership List")

    member = UserManager.get_or_create_user(601, "member")
    member = UserManager.get_or_create_user(601, "member")
    await TaskManager.share_list(l.id, "member")
    # Accept invite
    await TaskManager.respond_to_invite(601, l.id, True)

    members = TaskManager.get_list_members(l.id)
    assert len(members) == 2
    assert owner in members
    assert member in members

def test_kick_user_error(test_db, mocker):
    from src.database.access import kick_user
    u = UserManager.get_or_create_user(99999, "error_kick")

    mocker.patch("builtins.input", return_value="y")
    # Mock Task.delete to raise
    mock_delete = mocker.patch("src.database.models.Task.delete")
    mock_delete.side_effect = Exception("DB Error")

    # Should catch and print error
    kick_user(99999)
    # User should still exist if it failed early (or deleted but errored logging?)
    # The code deletes tasks THEN user. If task delete fails, user remains.
    assert User.get_or_none(User.telegram_id == 99999) is not None
