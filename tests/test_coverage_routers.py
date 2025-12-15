import pytest
from unittest.mock import MagicMock, patch
from src.webapp.routers.dashboard import get_dated_items, reorder_mixed, ReorderMixedRequest, ReorderItem
from src.webapp.routers.lists import leave_list, update_list_color, update_list, share_list, reorder_lists_endpoint, ReorderRequest, ListColorUpdate, ListUpdate, ShareRequest
from src.webapp.routers.tasks import add_task, update_task_content, TaskCreate, TaskUpdate
from fastapi import HTTPException
from datetime import datetime
from src.utils.schema import TaskSchema

# --- Dashboard Tests ---

@pytest.mark.asyncio
async def test_get_dated_items_with_list_metadata():
    """Cover lines 46-48 in dashboard.py: task with associated list"""
    mock_task = MagicMock()
    mock_task.id = 1
    mock_task.title = "Task"
    mock_task.priority = "HIGH"
    mock_task.status = "PENDING"
    mock_task.deadline = datetime.now()
    mock_task.task_list.id = 10
    mock_task.task_list.title = "List"
    mock_task.task_list.color = "#fff"

    with patch('src.webapp.state.coordinator.task_manager.get_dated_items', return_value=[mock_task]):
        items = await get_dated_items(user_id=1)
        # Result is list of DICTS
        assert items[0]["list_id"] == 10
        assert items[0]["list_name"] == "List"

@pytest.mark.asyncio
async def test_reorder_mixed_shared_list():
    """Cover line 126 in dashboard.py: reorder shared list"""
    req = ReorderMixedRequest(user_id=1, items=[ReorderItem(type="list", id=10)])

    # Patch the entire DB object to avoid Proxy attributes read-only error
    with patch('src.database.models.db') as mock_db:
        mock_db.atomic.return_value.__enter__.return_value = None

        with patch('src.database.models.TaskList.update') as mock_update:
            # First update (Owned) returns 0 rows modified
            mock_update.return_value.where.return_value.execute.return_value = 0

            with patch('src.database.models.SharedAccess.update') as mock_shared_update:
                 await reorder_mixed(req, user_id=1)
                 mock_shared_update.assert_called()

# --- Lists Tests (Error Handling) ---

@pytest.mark.asyncio
async def test_leave_list_failure():
    """Cover line 81 in lists.py"""
    with patch('src.webapp.state.coordinator.task_manager.leave_list', return_value=(False, "Err")):
        with pytest.raises(HTTPException) as exc:
            await leave_list(1, 1)
        assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_update_list_color_failure():
    """Cover line 100 in lists.py"""
    with patch('src.webapp.state.coordinator.task_manager.edit_list_color', return_value=False):
        with pytest.raises(HTTPException) as exc:
            await update_list_color(1, ListColorUpdate(color="red"), user_id=1)
        assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_update_list_failure():
    """Cover line 113 in lists.py"""
    with patch('src.webapp.state.coordinator.task_manager.edit_list', return_value=False):
        with pytest.raises(HTTPException) as exc:
            await update_list(1, ListUpdate(name="New"), user_id=1)
        assert exc.value.status_code == 430

@pytest.mark.asyncio
async def test_share_list_failure():
    """Cover line 127 in lists.py"""
    with patch('src.webapp.state.coordinator.task_manager.share_list', return_value=(False, "Err")):
         with pytest.raises(HTTPException):
             await share_list(1, ShareRequest(username="u"), user_id=1)

@pytest.mark.asyncio
async def test_reorder_lists_failure():
    """Cover line 141 in lists.py"""
    with patch('src.webapp.state.coordinator.task_manager.reorder_lists', return_value=False):
        with pytest.raises(HTTPException):
            await reorder_lists_endpoint(ReorderRequest(list_ids=[]), user_id=1)

# --- Tasks Tests ---

def test_task_validators():
    """Cover lines 23 (deadline empty -> None) and 134-136 (recurrence empty -> None)"""
    # TaskCreate validator
    t = TaskCreate(content="c", deadline="")
    assert t.deadline is None

    # TaskUpdate validator (recurrence)
    u = TaskUpdate(recurrence="")
    assert u.recurrence is None

    # TaskUpdate deadline
    u2 = TaskUpdate(deadline="")
    assert u2.deadline is None

    # Coverage for line 23: if v == "" return None. Wait, what if v is not empty?
    t2 = TaskCreate(content="c", deadline="2025-01-01")
    assert t2.deadline == "2025-01-01"

    # Coverage for line 136 in tasks.py: return v (recurrence not empty)
    u3 = TaskUpdate(recurrence="daily")
    assert u3.recurrence == "daily"

@pytest.mark.asyncio
async def test_add_task_with_list_save():
    """Cover lines 65-67 in tasks.py: setting task list on create"""

    # Custom Mock to simulate Peewee behavior (assign int, retrieve obj with id=int)
    class PeeweeMock(MagicMock):
        _list = None
        @property
        def task_list(self):
            if isinstance(self._list, int):
                m = MagicMock()
                m.id = self._list
                return m
            # If never set (None), return None to simulate 'if new_task.task_list' check
            # BUT mock usually returns a truthy mock
            # We want to start as None (falsy) if not set?
            # Code: `if new_task.task_list else None`
            return self._list

        @task_list.setter
        def task_list(self, val):
            self._list = val

    mock_task = PeeweeMock()
    mock_task.id = 1
    mock_task.title = "T"
    mock_task.status = "PENDING"
    mock_task.deadline = None
    # Initialize task_list to None effectively
    mock_task.task_list = None

    with patch('src.webapp.state.coordinator.task_manager.add_task', return_value=mock_task):
        # Pass list_id in create
        resp = await add_task(TaskCreate(content="c", list_id=10), user_id=1)

        # Check that we set it
        assert mock_task._list == 10
        mock_task.save.assert_called()
        # Check Response ID
        assert resp.list_id == 10

@pytest.mark.asyncio
async def test_update_task_content_list_mapping():
    """Cover lines 188 (mapping) and 195 (failure) in tasks.py"""

    # Test mapping list_id -> task_list_id
    with patch('src.webapp.state.coordinator.task_manager.edit_task', return_value=True) as mock_edit:
        await update_task_content(1, TaskUpdate(list_id=5), user_id=1)

        # Check that edit_task was called with TaskSchema containing task_list_id=5
        args = mock_edit.call_args
        schema = args[0][2] # 3rd arg is schema
        assert schema.task_list_id == 5

    # Test Failure
    with patch('src.webapp.state.coordinator.task_manager.edit_task', return_value=False):
        with pytest.raises(HTTPException):
             await update_task_content(1, TaskUpdate(content="c"), user_id=1)
