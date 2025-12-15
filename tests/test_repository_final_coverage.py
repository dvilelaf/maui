import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from src.database.repositories.task_repository import TaskManager
from src.database.models import User, Task, TaskList, SharedAccess
from src.utils.schema import TaskSchema, TaskStatus
from datetime import datetime

@pytest.fixture
def mock_objects():
    user = MagicMock(spec=User)
    user.telegram_id = 123
    user.username = "owner"
    user.first_name = "Owner"

    other_user = MagicMock(spec=User)
    other_user.telegram_id = 456
    other_user.username = "other"

    task_list = MagicMock(spec=TaskList)
    task_list.id = 1
    task_list.title = "My List"
    task_list.owner_id = 123
    task_list.owner = user

    task_in_list = MagicMock(spec=Task)
    task_in_list.id = 10
    task_in_list.user_id = 123
    task_in_list.task_list = task_list
    task_in_list.status = TaskStatus.PENDING
    task_in_list.recurrence = "DAILY"
    task_in_list.deadline = datetime.now()
    task_in_list.position = 1

    return user, other_user, task_list, task_in_list

def test_get_task_by_id_calls_get_or_none():
    with patch('src.database.repositories.task_repository.Task.get_or_none') as mock_get:
        TaskManager.get_task_by_id(999)
        mock_get.assert_called_once()

def test_check_access_owner_of_list(mock_objects):
    """Test owner accessing a task that is in their list (even if user_id on task might differ, though usually same)"""
    user, _, task_list, task_in_list = mock_objects
    # Simulate task being owned by someone else but in MY list (unlikely model but possible for check logic)
    task_in_list.user_id = 999

    # Assert check_task_access returns True because task.task_list.owner_id == user_id (123)
    assert TaskManager._check_task_access(123, task_in_list) is True

def test_recurrence_spawn_exception(mock_objects):
    """Cover lines 226-227: Exception during recurrence spawn"""
    user, _, task_list, task_in_list = mock_objects

    with patch('src.database.repositories.task_repository.Task.get_or_none', return_value=task_in_list):
        with patch('src.database.repositories.task_repository.TaskManager._check_task_access', return_value=True):
             # Mock save to return True
             task_in_list.save = MagicMock(return_value=1)

             # Mock Task.create to raise Exception
             with patch('src.database.repositories.task_repository.Task.create', side_effect=Exception("Spawn Fail")):
                 # Should catch exception and still log error (check logs if possible, or just ensure no crash)
                 success = TaskManager.update_task_status(123, 10, TaskStatus.COMPLETED)
                 assert success is True # Main task status update succeeds even if spawn fails

def test_find_tasks_by_keyword_no_access_to_list():
    """Cover line 332: return [] if no access to list"""
    with patch('src.database.repositories.task_repository.TaskList.get_or_none') as mock_list_get:
        # Mock finding a list but not owning it
        tlist = MagicMock()
        tlist.owner_id = 999
        mock_list_get.return_value = tlist

        # Mock SharedAccess exists returning False
        with patch('src.database.repositories.task_repository.SharedAccess.select') as mock_select:
             mock_select.return_value.where.return_value.exists.return_value = False

             results = TaskManager.find_tasks_by_keyword(123, "stuff", list_id=5)
             assert results == []

@pytest.mark.asyncio
async def test_share_list_not_found():
    """Cover line 368: List not found"""
    with patch('src.database.repositories.task_repository.TaskList.get_or_none', return_value=None):
        success, msg = await TaskManager.share_list(123, 1, "@u")
        assert not success
        assert "no encontrada" in msg

@pytest.mark.asyncio
async def test_share_list_multiple_matches_exact():
    """Cover line 400: Multiple candidates but one exact match"""
    user1 = MagicMock(first_name="John", username="j1")
    user2 = MagicMock(first_name="Johnny", username="j2")

    with patch('src.database.repositories.task_repository.TaskList.get_or_none') as mock_list_get:
        mock_list_get.return_value.owner_id = 123

        with patch('src.database.repositories.task_repository.User.get_or_none', return_value=None): # No direct match
             with patch('src.database.repositories.task_repository.User.select') as mock_select:
                 # Return list of candidates
                 mock_select.return_value.where.return_value = [user1, user2]

                 # Logic for exact match filtering:
                 # Code: if u.first_name.lower() == query.lower()
                 # Let's search for "John"

                 # Mock SharedAccess exists = False
                 with patch('src.database.repositories.task_repository.SharedAccess.select') as mock_sa:
                      mock_sa.return_value.where.return_value.exists.return_value = False
                      with patch('src.database.repositories.task_repository.SharedAccess.create'):
                           with patch('src.database.repositories.task_repository.notify_user'):
                                success, msg = await TaskManager.share_list(123, 1, "John")
                                assert success
                                assert "j1" in msg

@pytest.mark.asyncio
async def test_share_list_multiple_matches_ambiguous_and_notify_fail():
    """Cover lines 408 (msg truncation) and 460-461 (notify exception)"""
    # Create 4 candidates to trigger truncation
    users = [MagicMock(first_name=f"User{i}", username=f"u{i}") for i in range(4)]

    with patch('src.database.repositories.task_repository.TaskList.get_or_none') as mock_list_get:
        mock_list_get.return_value.owner_id = 123

        # Test Truncation
        with patch('src.database.repositories.task_repository.User.get_or_none', return_value=None):
             with patch('src.database.repositories.task_repository.User.select') as mock_select:
                 mock_select.return_value.where.return_value = users

                 success, msg = await TaskManager.share_list(123, 1, "User")
                 assert not success
                 assert "..." in msg

        # Test Notify Exception (Lines 460-461)
        # Setup: Valid user found, but notify_user raises
        target = users[0]
        with patch('src.database.repositories.task_repository.User.get_or_none', return_value=target):
             with patch('src.database.repositories.task_repository.SharedAccess.select') as mock_sa:
                  mock_sa.return_value.where.return_value.exists.return_value = False
                  with patch('src.database.repositories.task_repository.SharedAccess.create'):
                       with patch('src.database.repositories.task_repository.notify_user', side_effect=Exception("Notify Fail")):
                            # Should catch exception and return success message anyway
                            success, msg = await TaskManager.share_list(123, 1, "Target")
                            assert success # The invite is created locally even if notify fails

@pytest.mark.asyncio
async def test_respond_to_invite_does_not_exist():
    """Cover lines 480-481"""
    with patch('src.database.repositories.task_repository.User.get_or_none', return_value=MagicMock()):
        with patch('src.database.repositories.task_repository.SharedAccess.get', side_effect=SharedAccess.DoesNotExist):
            success, msg = await TaskManager.respond_to_invite(123, 1, True)
            assert not success
            assert "invitación pendiente" in msg

def test_find_list_by_name_matching():
    """Cover lines 626, 628 in reverse search"""
    # Mock get_lists returning mocked lists
    l1 = MagicMock(title="Lista de Compra")
    l2 = MagicMock(title="Trabajo")

    with patch('src.database.repositories.task_repository.TaskManager.get_lists', return_value=[l1, l2]):
        with patch('src.database.repositories.task_repository.TaskList.select') as mock_select:
             # Make DB searches fail to fall through to reverse search
             mock_select.return_value.where.return_value.first.return_value = None
             mock_select.return_value.join.return_value.where.return_value.first.return_value = None

             # Test clean match (e.g. "Compra" matches "Lista de Compra" via stopword removal logic?)
             # Logic: clean("Compra") -> "compra". l1.title.lower() -> "lista de compra".
             # if "compra" in "lista de compra": return l1 (Line 629) - wait I want 626 or 628.
             # 626: if clean_name == title_norm
             # 628: if title_norm in name_norm

             # Case for 626: Exact match after clean
             # "la compra" -> clean -> "compra". If list is "Compra".
             l3 = MagicMock(title="Compra")
             with patch('src.database.repositories.task_repository.TaskManager.get_lists', return_value=[l3]):
                 # "la compra" -> clean "compra" == "compra"
                  found = TaskManager.find_list_by_name(123, "la compra")
                  assert found == l3

             # Case for 628: title_norm in name_norm
             # Name: "Proyecto Alpha Final". List: "Alpha". "alpha" in "proyecto alpha final"
             l4 = MagicMock(title="Alpha")
             with patch('src.database.repositories.task_repository.TaskManager.get_lists', return_value=[l4]):
                  found = TaskManager.find_list_by_name(123, "Proyecto Alpha Final")
                  assert found == l4

def test_is_user_in_list_owner():
    """Cover line 694"""
    with patch('src.database.repositories.task_repository.TaskList.get_or_none') as mock_get:
        mock_get.return_value.owner.telegram_id = 123
        assert TaskManager.is_user_in_list(123, 1) is True
