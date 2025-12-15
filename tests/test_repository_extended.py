
import pytest
from src.database.repositories.task_repository import TaskManager
from src.database.repositories.user_repository import UserManager
from src.database.models import Task, TaskList, User, TaskStatus

@pytest.fixture
def repo_data(test_db):
    user = User.create(username="repo_user", telegram_id=999)
    inbox = TaskList.create(title="Inbox", owner=user)
    work = TaskList.create(title="Work", owner=user)

    # Loose pending task
    t1 = Task.create(title="Task 1 Loose", user=user, status=TaskStatus.PENDING, position=1)
    # Loose completed task
    t2 = Task.create(title="Task 2 Loose Done", user=user, status=TaskStatus.COMPLETED, position=2)

    # List task
    t3 = Task.create(title="Task 3 Work", user=user, task_list=work, status=TaskStatus.PENDING, position=1)

    return user, inbox, work, [t1, t2, t3]

def test_task_repo_get_pending_loose(repo_data):
    user, _, _, _ = repo_data
    # Should only return t1 (loose pending)
    tasks = TaskManager.get_pending_tasks(user.telegram_id)
    assert len(tasks) == 1
    assert tasks[0].title == "Task 1 Loose"

def test_task_repo_get_user_tasks(repo_data):
    # get_user_tasks returns all loose tasks (both pending and completed?)
    # Docstring says: "Get all tasks ... for a user, excluding tasks in lists."
    user, _, _, _ = repo_data
    tasks = TaskManager.get_user_tasks(user.telegram_id)
    # Should be t1 and t2
    assert len(tasks) == 2
    titles = {t.title for t in tasks}
    assert "Task 1 Loose" in titles
    assert "Task 2 Loose Done" in titles

def test_task_repo_search_keyword(repo_data):
    user, _, work, _ = repo_data
    # Search loose tasks (Must be PENDING because find_tasks_by_keyword filters only pending)
    # t1 is "Task 1 Loose", t2 is "Task 2 Loose Done" (COMPLETED, so invisible)
    tasks = TaskManager.find_tasks_by_keyword(user.telegram_id, keyword="Loose")
    assert len(tasks) == 1
    assert tasks[0].title == "Task 1 Loose"

    # Search in specific list
    tasks = TaskManager.find_tasks_by_keyword(user.telegram_id, keyword="Work", list_id=work.id)
    assert len(tasks) == 1
    assert tasks[0].title == "Task 3 Work"

def test_user_manager_update_status(repo_data):
    user, _, _, _ = repo_data
    mgr = UserManager()
    res = mgr.update_status(user.telegram_id, "WHITELISTED")
    assert res is True

    u = User.get(User.telegram_id == user.telegram_id)
    assert u.status == "WHITELISTED"

    # Negative test
    res = mgr.update_status(11111, "WHITELISTED")
    assert res is False

def test_user_manager_get_pending(repo_data):
    # Create pending user
    User.create(username="pending_user", telegram_id=888, status="PENDING")

    mgr = UserManager()
    pending = mgr.get_pending_users() # Instance method
    assert len(pending) >= 1
    assert any(u.telegram_id == 888 for u in pending)

def test_delete_task_access(repo_data):
    user, _, _, tasks = repo_data
    t1 = tasks[0] # Owned by user

    res = TaskManager.delete_task(user.telegram_id, t1.id)
    assert res is True

    # Try delete non-existent
    res = TaskManager.delete_task(user.telegram_id, 99999)
    assert res is False

def test_update_notif_time(repo_data):
    user, _, _, _ = repo_data
    mgr = UserManager()
    res = mgr.update_notification_time(user.telegram_id, "09:00")
    assert res is True

    u = User.get(User.telegram_id == user.telegram_id)
    from datetime import time
    assert u.notification_time == time(9, 0)

def test_get_dashboard_items(repo_data):
    user, inbox, _, tasks = repo_data
    # tasks: [t1 (loose pending), t2 (loose done), t3 (in work list)]
    # get_dashboard_items returns loose pending tasks + lists

    items = TaskManager.get_dashboard_items(user.telegram_id)

    # Expect:
    # - t1 (loose pending) -> type=task
    # - t2 (loose done) -> not included?
    #   Wait, get_dashboard_items query: Task.task_list.is_null()
    #   AND it usually filters PENDING? Query in code: Task.select().where((Task.user == user_id) & (Task.task_list.is_null()))
    #   It does NOT filter by status in the snippet I saw! Line 799: Task.select().where((Task.user == user_id) & (Task.task_list.is_null()))
    #   So t2 (DONE) might be included if not filtered.
    #   User requirement: "All" tab.
    #   Let's assume it returns all loose tasks.

    # - Lists: Inbox, Work.

    # Check types
    types = [i["type"] for i in items]
    assert "list" in types
    assert "task" in types

    # Verify content
    task_items = [i for i in items if i["type"] == "task"]
    list_items = [i for i in items if i["type"] == "list"]

    assert len(list_items) >= 2 # Inbox, Work
    assert len(task_items) >= 2 # t1, t2 (if included)

def test_get_dated_items(repo_data):
    user, _, _, tasks = repo_data
    # None of repo_data tasks have deadline?
    # Let's add one
    from datetime import datetime, timedelta
    t_dated = Task.create(
        title="Dated Task", user=user, status=TaskStatus.PENDING,
        deadline=datetime.now() + timedelta(days=1)
    )

    items = TaskManager.get_dated_items(user.telegram_id)
    assert len(items) >= 1
    assert any(t.title == "Dated Task" for t in items)

    # Ensure items without deadline are NOT included
    # t1 from repo_data has no deadline (default null)
    assert not any(t.title == "Task 1 Loose" for t in items)
