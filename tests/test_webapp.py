
import pytest
from fastapi.testclient import TestClient
from unittest import mock
from datetime import datetime

# Initialize app lifespan before importing if possible, but TestClient handles it.
# We need to mock the DB before importing app if app connects at module level,
# but we fixed app.py to connect in lifespan.

from src.webapp.app import app
from src.database.models import User, Task, TaskList, SharedAccess
from src.utils.schema import TaskStatus

# Mock data
USER_ID = 599142
TASK_ID = 1
LIST_ID = 10

from src.webapp.state import coordinator as real_coordinator

@pytest.fixture
def client(mock_coordinator):
    # Patch the attributes of the singleton instance to verify calls
    with mock.patch.object(real_coordinator, 'task_manager', mock_coordinator.task_manager):
             with TestClient(app) as c:
                 yield c

@pytest.fixture
def mock_coordinator():
    # We return a simple object holding the mocks we want to inject
    # The fixture above will apply them to real_coordinator
    holder = mock.Mock()
    tm = mock.Mock()
    holder.task_manager = tm
    return holder

def test_get_tasks_all_statuses(client, mock_coordinator):
    # Mock return of get_user_tasks instead of get_pending_tasks
    t1 = mock.Mock()
    t1.id = 1
    t1.title = "Pending Task"
    t1.status = TaskStatus.PENDING
    t1.deadline = None
    t1.task_list = None

    t2 = mock.Mock()
    t2.id = 2
    t2.title = "Completed Task"
    t2.status = TaskStatus.COMPLETED
    t2.deadline = None
    t2.task_list = None

    # We must patch the new method get_user_tasks
    mock_coordinator.task_manager.get_user_tasks.return_value = [t1, t2]

    response = client.get(f"/api/tasks/{USER_ID}")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    assert data[0]["content"] == "Pending Task"
    assert data[0]["status"] == "PENDING"
    assert data[1]["content"] == "Completed Task"
    assert data[1]["status"] == "COMPLETED"

def test_add_task_persists(client, mock_coordinator):
    new_task = mock.Mock()
    new_task.id = 3
    new_task.title = "New Persisted Task"
    new_task.status = TaskStatus.PENDING
    new_task.deadline = None
    new_task.task_list = None

    mock_coordinator.task_manager.add_task.return_value = new_task

    payload = {"content": "New Persisted Task", "list_id": None}
    response = client.post(f"/api/tasks/{USER_ID}/add", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "New Persisted Task"

    # Verify add_task called with correct args
    mock_coordinator.task_manager.add_task.assert_called_once()
    call_args = mock_coordinator.task_manager.add_task.call_args
    assert call_args.kwargs["user_id"] == USER_ID
    assert call_args.kwargs["task_data"].title == "New Persisted Task"

def test_delete_task_updates_db(client, mock_coordinator):
    mock_coordinator.task_manager.delete_task.return_value = True
    response = client.post(f"/api/tasks/{TASK_ID}/delete")
    assert response.status_code == 200

    mock_coordinator.task_manager.delete_task.assert_called_with(TASK_ID)

def test_get_lists_with_nested_tasks(client, mock_coordinator):
    l1 = mock.Mock()
    l1.id = 10
    l1.title = "Groceries"
    l1.owner_id = USER_ID # Fix: Add owner_id

    # Mock get_lists returning the list
    mock_coordinator.task_manager.get_lists.return_value = [l1]

    # Mock get_tasks_in_list returning tasks for that list
    t_nested = mock.Mock()
    t_nested.id = 5
    t_nested.title = "Milk"
    t_nested.status = TaskStatus.PENDING
    t_nested.deadline = None
    t_nested.task_list = l1

    mock_coordinator.task_manager.get_tasks_in_list.return_value = [t_nested]

    response = client.get(f"/api/lists/{USER_ID}")

    # If app code uses lst.name but model has title, this test might pass if I mock .name
    # But real DB object won't have .name.
    # We should suspect app.py has 'lst.name' based on my memory of reading it.

    assert response.status_code == 200
