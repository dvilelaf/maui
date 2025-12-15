
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
    from src.webapp.auth import get_current_user

    # Handlers: start, help, app, handle_message, handle_voice = 5
    # If using builder mock, the app instance returned should be the one where add_handler is called.
    # Check chain: builder.token().post_init().build() returns app_mock.
    # The instruction provided a malformed line:
    # assert app_mock.add_handler.call_count >= 1 # Relax assertion to > 0 if mocking is complexverrides[get_current_user] = lambda: USER_ID
    # Assuming the intent was to add the assertion and keep the dependency override.
    # Note: app_mock is not defined in this fixture, so this line would cause an error.
    # I'm adding it as commented out to reflect the instruction's content while maintaining syntactical correctness.
    # assert app_mock.add_handler.call_count >= 1 # Relax assertion to > 0 if mocking is complex
    app.dependency_overrides[get_current_user] = lambda: USER_ID

    # Patch the attributes of the singleton instance to verify calls
    with mock.patch.object(real_coordinator, 'task_manager', mock_coordinator.task_manager):
             with TestClient(app) as c:
                 yield c

    # Cleanup
    app.dependency_overrides = {}

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
    # Add other fields required by Schema if needed
    t1.priority = "MEDIUM"
    t1.created_at = datetime.now()


    t2 = mock.Mock()
    t2.id = 2
    t2.title = "Completed Task"
    t2.status = TaskStatus.COMPLETED
    t2.deadline = None
    t2.task_list = None
    t2.priority = "MEDIUM"
    t2.created_at = datetime.now()

    # We must patch the new method get_user_tasks
    mock_coordinator.task_manager.get_user_tasks.return_value = [t1, t2]

    response = client.get(f"/api/tasks") # Remove trailing slash
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
    response = client.post(f"/api/tasks/add", json=payload) # Remove USER_ID


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
    response = client.post(f"/api/tasks/{TASK_ID}/delete") # Remove json body, use URL

    assert response.status_code == 200

    # The endpoint calls delete_task(user_id, task_id)
    # user_id comes from dependency override (USER_ID = 599142)
    mock_coordinator.task_manager.delete_task.assert_called_with(USER_ID, TASK_ID)

    pass

def test_create_list(client, mock_coordinator):
    new_list = mock.Mock()
    new_list.id = 11
    new_list.title = "New List"
    new_list.owner_id = USER_ID

    mock_coordinator.task_manager.create_list.return_value = new_list

    resp = client.post("/api/lists/add", json={"name": "New List"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New List"
    mock_coordinator.task_manager.create_list.assert_called_with(USER_ID, "New List")

def test_delete_list(client, mock_coordinator):
    mock_coordinator.task_manager.delete_list.return_value = True
    resp = client.post(f"/api/lists/{LIST_ID}/delete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

def test_delete_list_fail(client, mock_coordinator):
    mock_coordinator.task_manager.delete_list.return_value = False
    resp = client.post(f"/api/lists/{LIST_ID}/delete")
    assert resp.status_code == 403

def test_leave_list(client, mock_coordinator):
    mock_coordinator.task_manager.leave_list = mock.AsyncMock(return_value=(True, "Left"))
    resp = client.post(f"/api/lists/{LIST_ID}/leave")
    assert resp.status_code == 200
    assert "Left" in resp.json()["message"]

def test_update_list_color(client, mock_coordinator):
    mock_coordinator.task_manager.edit_list_color.return_value = True
    resp = client.post(f"/api/lists/{LIST_ID}/color", json={"color": "#ff0000"})
    assert resp.status_code == 200

def test_update_list_name(client, mock_coordinator):
    mock_coordinator.task_manager.edit_list.return_value = True
    resp = client.post(f"/api/lists/{LIST_ID}/update", json={"name": "Renamed"})
    assert resp.status_code == 200

def test_share_list(client, mock_coordinator):
    mock_coordinator.task_manager.share_list = mock.AsyncMock(return_value=(True, "Shared"))
    resp = client.post(f"/api/lists/{LIST_ID}/share", json={"username": "friend"})
    assert resp.status_code == 200

def test_reorder_lists(client, mock_coordinator):
    mock_coordinator.task_manager.reorder_lists.return_value = True
    resp = client.post("/api/lists/reorder", json={"list_ids": [1, 2, 3]})
    assert resp.status_code == 200

def test_complete_task_endpoint(client, mock_coordinator):
    mock_coordinator.task_manager.update_task_status.return_value = True
    resp = client.post(f"/api/tasks/{TASK_ID}/complete")
    assert resp.status_code == 200

def test_update_task_content_endpoint(client, mock_coordinator):
    mock_coordinator.task_manager.edit_task.return_value = True
    resp = client.post(f"/api/tasks/{TASK_ID}/update", json={"content": "Updated", "deadline": None})
    assert resp.status_code == 200


def test_dashboard_stats(client, mock_coordinator):
    # Coverage for lines 32-51 (get_dashboard_stats)
    # Actually dashboard endpoints are: /dated and /all
    pass # No stats endpoint in viewing dashboard.py

def test_dashboard_dated(client, mock_coordinator):
    # /api/dashboard/dated
    # Coverage for lines 59-88
    t_dated = mock.Mock(status=TaskStatus.PENDING, deadline=datetime.now())
    t_dated.title = "Dated Task"
    t_dated.id = 99
    t_dated.priority = "HIGH"
    t_dated.task_list = None

    mock_coordinator.task_manager.get_dated_items.return_value = [t_dated]

    resp = client.get("/api/dashboard/dated")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

def test_dashboard_all(client, mock_coordinator):
    # /api/dashboard/all
    # Coverage for 108-132
    # Returns all items (tasks and lists)
    t_data = mock.Mock(status=TaskStatus.PENDING, deadline=None)
    t_data.title = "Any Task"
    t_data.id = 100
    t_data.priority = "MEDIUM"

    item = {
        "type": "task",
        "data": t_data,
        "position": 1,
        "created_at": datetime.now()
    }

    mock_coordinator.task_manager.get_dashboard_items.return_value = [item]

    resp = client.get("/api/dashboard/all")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

def test_dashboard_reorder(client, mock_coordinator):
    # /api/dashboard/reorder
    # Coverage for 101-132 in dashboard.py
    # This involves DB interaction because logic is inside endpoint (bad practice, but we test it).
    # We need to mock db.atomic and Task/TaskList/SharedAccess updates.

    # Check imports in dashboard.py: imports db inside function from src.database.models
    # So we patch src.database.models.db

    with mock.patch("src.database.models.db") as mock_db:
        mock_db.atomic.return_value.__enter__.return_value = None

        with mock.patch("src.database.models.Task") as mock_task, \
             mock.patch("src.database.models.TaskList") as mock_list, \
             mock.patch("src.database.models.SharedAccess") as mock_sa:

             payload = {
                 "user_id": USER_ID,
                 "items": [
                     {"type": "task", "id": 1},
                     {"type": "list", "id": 2}
                 ]
             }

             resp = client.post("/api/dashboard/reorder", json=payload)
             assert resp.status_code == 200
             # Verify calls
             mock_task.update.assert_called()
             mock_list.update.assert_called()

def test_invites_endpoints(client, mock_coordinator):
    # GET /api/invites
    mock_coordinator.task_manager.get_pending_invites.return_value = []
    resp = client.get("/api/invites") # Check path prefix
    assert resp.status_code == 200

    # POST /api/invites/{list_id}/respond (accept)
    mock_coordinator.task_manager.respond_to_invite = mock.AsyncMock(return_value=(True, "Joined"))
    resp = client.post(f"/api/invites/{LIST_ID}/respond", json={"accept": True})
    assert resp.status_code == 200

    # POST /api/invites/{list_id}/respond (decline)
    mock_coordinator.task_manager.respond_to_invite = mock.AsyncMock(return_value=(True, "Declined"))
    resp = client.post(f"/api/invites/{LIST_ID}/respond", json={"accept": False})
    assert resp.status_code == 200

    # Check failure cases
    mock_coordinator.task_manager.respond_to_invite = mock.AsyncMock(return_value=(False, "Error"))
    resp = client.post(f"/api/invites/{LIST_ID}/respond", json={"accept": True})
    assert resp.status_code == 400
