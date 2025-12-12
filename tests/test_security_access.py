
import pytest
from src.database.repositories.task_repository import TaskManager
from src.database.models import User, Task, TaskList, SharedAccess
from src.utils.schema import TaskSchema, TaskStatus

@pytest.fixture
def users_and_tasks(test_db):
    u1 = User.create(telegram_id=100, username="user1")
    u2 = User.create(telegram_id=200, username="user2")

    t1 = TaskManager.add_task(100, TaskSchema(title="Task 1"))
    t2 = TaskManager.add_task(200, TaskSchema(title="Task 2"))

    l1 = TaskManager.create_list(100, "List 1")

    return u1, u2, t1, t2, l1

def test_delete_other_user_task(users_and_tasks):
    u1, u2, t1, t2, l1 = users_and_tasks

    # User 1 tries to delete User 2's task -> Should Fail
    assert TaskManager.delete_task(u1.telegram_id, t2.id) is False
    # Verify task still exists
    assert Task.get_or_none(Task.id == t2.id) is not None

def test_edit_other_user_task(users_and_tasks):
    u1, u2, t1, t2, l1 = users_and_tasks

    # User 1 tries to edit User 2's task -> Should Fail
    success = TaskManager.edit_task(u1.telegram_id, t2.id, TaskSchema(title="Hacked"))
    assert not success
    # Verify title unchanged
    assert Task.get_by_id(t2.id).title == "Task 2"

def test_update_status_other_user_task(users_and_tasks):
    u1, u2, t1, t2, l1 = users_and_tasks

    # User 1 tries to complete User 2's task -> Should Fail
    success = TaskManager.update_task_status(u1.telegram_id, t2.id, TaskStatus.COMPLETED)
    assert not success
    assert Task.get_by_id(t2.id).status == TaskStatus.PENDING

@pytest.mark.asyncio
async def test_share_other_user_list(users_and_tasks, mocker):
    mocker.patch("src.database.repositories.task_repository.notify_user")
    u1, u2, t1, t2, l1 = users_and_tasks

    # User 2 tries to share User 1's list with himself? Or another.
    # User 2 tries to share List 1 (owned by u1)
    success, msg = await TaskManager.share_list(u2.telegram_id, l1.id, "user2")
    assert not success
    assert "No tienes permiso" in msg

def test_shared_list_access(test_db):
    # Verify a member CAN update a task in a shared list
    owner = User.create(telegram_id=10, username="owner")
    member = User.create(telegram_id=20, username="member")
    other = User.create(telegram_id=30, username="other")

    l = TaskList.create(title="Shared", owner=owner)
    SharedAccess.create(user=member, task_list=l, status="ACCEPTED")

    # Add task to list
    t = TaskManager.add_task(10, TaskSchema(title="Shared Task", list_name="Shared"))

    # 1. Owner can edit
    assert TaskManager.edit_task(10, t.id, TaskSchema(title="Edited by Owner")) is True

    # 2. Member can edit
    assert TaskManager.edit_task(20, t.id, TaskSchema(title="Edited by Member")) is True

    # 3. Non-member cannot edit
    assert TaskManager.edit_task(30, t.id, TaskSchema(title="Hacked")) is False
