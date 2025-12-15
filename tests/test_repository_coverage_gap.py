import pytest
from unittest.mock import MagicMock, patch
from src.database.repositories.task_repository import TaskManager
from src.database.models import User, Task, TaskList, SharedAccess
from src.utils.schema import TaskSchema

@pytest.fixture
def mock_db_objects():
    user = User(telegram_id=123, username="testuser", first_name="Test")
    task_list = TaskList(id=1, title="My List", owner=user, owner_id=123)
    task = Task(id=1, title="My Task", user=user, user_id=123, task_list=task_list)
    return user, task_list, task

def test_edit_task_no_updates(mock_db_objects):
    user, _, task = mock_db_objects

    # Test edit_task returns False if updates dictionary is empty (after filtering allowed)
    # TaskSchema with all None fields
    schema = TaskSchema()

    with patch('src.database.repositories.task_repository.Task.get_or_none', return_value=task):
        with patch('src.database.repositories.task_repository.TaskManager._check_task_access', return_value=True):
             result = TaskManager.edit_task(123, 1, schema)
             assert result is False

def test_unauthorized_list_actions(mock_db_objects):
    user, task_list, _ = mock_db_objects
    other_user_id = 456

    with patch('src.database.repositories.task_repository.TaskList.get_by_id', return_value=task_list):
        # Delete failure
        assert TaskManager.delete_list(other_user_id, 1) is False

        # Rename failure
        assert TaskManager.edit_list(other_user_id, 1, "New Name") is False

        # Color failure
        assert TaskManager.edit_list_color(other_user_id, 1, "#000000") is False

@pytest.mark.asyncio
async def test_leave_list_user_not_found():
    with patch('src.database.repositories.task_repository.User.get_or_none', return_value=None):
        success, msg = await TaskManager.leave_list(999, 1)
        assert not success
        assert "Usuario no encontrado" in msg

@pytest.mark.asyncio
async def test_respond_invite_user_not_found():
    with patch('src.database.repositories.task_repository.User.get_or_none', return_value=None):
        success, msg = await TaskManager.respond_to_invite(999, 1, True)
        assert not success
        assert "Usuario no encontrado" in msg

def test_is_user_in_list_not_found():
    with patch('src.database.repositories.task_repository.TaskList.get_or_none', return_value=None):
        assert TaskManager.is_user_in_list(123, 999) is False

def test_delete_all_lists_exception():
    with patch('src.database.repositories.task_repository.TaskList.select', side_effect=Exception("DB Error")):
        count = TaskManager.delete_all_lists(123)
        assert count == 0

def test_edit_task_not_found():
    with patch('src.database.repositories.task_repository.Task.get_or_none', return_value=None):
        assert TaskManager.edit_task(123, 999, TaskSchema(title="T")) is False
