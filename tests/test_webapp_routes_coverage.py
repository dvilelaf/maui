
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from src.webapp.app import app
from src.webapp.auth import get_current_user

# Override auth dependency
# This line is removed as the override is now handled within the fixture.

@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: 123
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides = {}

def test_tasks_route_invalid(client):
    # TaskCreate requires 'content'. Sending 'title' should trigger 422.
    res = client.post("/api/tasks/add", json={"title": ""})
    assert res.status_code == 422

    # Test adding task failure
    # Patch coordinator.task_manager
    with patch("src.webapp.state.coordinator.task_manager.add_task") as mock_add:
        mock_add.return_value = None

        # Valid payload: content
        res = client.post("/api/tasks/add", json={"content": "T"})

        # If add_task returns None -> 500 (as per tasks.py line 70)
        # tasks.py: raise HTTPException(status_code=500, detail="Failed to create task")
        assert res.status_code == 500

def test_lists_route_fail(client):
    # Patch coordinator.task_manager
    with patch("src.webapp.state.coordinator.task_manager.create_list") as mock_create:
        mock_create.side_effect = Exception("DB Error")
        res = client.post("/api/lists/add", json={"name": "L"}) # Model ListCreate(name) vs json
        # lists.py: class ListCreate(BaseModel): name: str
        # I sent {"title": "L"} before. Logic says name: str.
        # So correct json is {"name": "L"}.
        assert res.status_code == 500

def test_invites_route(client):
    with patch("src.webapp.state.coordinator.task_manager.get_pending_invites") as mock_get:
        mock_get.return_value = []
        res = client.get("/api/invites")
        assert res.status_code == 200
        assert res.json() == []

def test_complete_task_fail(client):
    with patch("src.webapp.state.coordinator.task_manager.update_task_status") as mock_upd:
        mock_upd.return_value = False
        res = client.post("/api/tasks/1/complete")
        assert res.status_code == 404

class MockTask:
    def __init__(self):
        self.id = 100
        self.title = "T"
        self.status = "PENDING"
        self._task_list = None
        self.deadline = None
        self.save = MagicMock()

    @property
    def task_list(self):
        if self._task_list:
            m = MagicMock()
            m.id = self._task_list
            return m
        return None

    @task_list.setter
    def task_list(self, val):
        self._task_list = val

def test_tasks_route_success(client):
    # Mock add_task with list_id handling
    mock_task = MockTask()

    with patch("src.webapp.state.coordinator.task_manager.add_task") as mock_add:
        mock_add.return_value = mock_task

        # Test 1: Add task with list_id (triggers line 66)
        res = client.post("/api/tasks/add", json={"content": "T", "list_id": 5})
        assert res.status_code == 200
        assert mock_task.task_list.id == 5
        mock_task.save.assert_called()

def test_lists_get(client):
    # Mock get_lists and get_tasks_in_list
    mock_lst = MagicMock()
    mock_lst.id = 1
    mock_lst.title = "L"
    mock_lst.owner_id = 123
    mock_lst.color = None # Trigger default color logic

    with patch("src.webapp.state.coordinator.task_manager.get_lists") as mock_get_lists, \
         patch("src.webapp.state.coordinator.task_manager.get_tasks_in_list") as mock_get_tasks:

        mock_get_lists.return_value = [mock_lst]
        mock_get_tasks.return_value = [] # Empty list

        res = client.get("/api/lists")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["color"] == "#f2f2f2" # Default logic hit

def test_task_modifications(client):
    # Test uncomplete, delete, update

    # Uncomplete
    with patch("src.webapp.state.coordinator.task_manager.update_task_status") as mock_stat:
        mock_stat.return_value = True
        res = client.post("/api/tasks/1/uncomplete")
        assert res.status_code == 200

    # Delete
    with patch("src.webapp.state.coordinator.task_manager.delete_task") as mock_del:
        mock_del.return_value = True
        res = client.post("/api/tasks/1/delete")
        assert res.status_code == 200

    # Update content success
    with patch("src.webapp.state.coordinator.task_manager.edit_task") as mock_edit:
        mock_edit.return_value = True
        res = client.post("/api/tasks/1/update", json={"content": "New", "deadline": "2024-01-01"})
        assert res.status_code == 200

def test_task_failures_and_validators(client):
    # Test validator: empty deadline
    with patch("src.webapp.state.coordinator.task_manager.add_task") as mock_add:
        mock_add.return_value = MagicMock(id=1, title="T", status="P", task_list=None, deadline=None)
        res = client.post("/api/tasks/add", json={"content": "T", "deadline": ""})
        # Should succeed and validator converts to None.
        # Check call args?
        assert res.status_code == 200
        # Check that add_task called with schema deadline=None
        args = mock_add.call_args
        # args[1]['task_data'].deadline should be None
        assert args.kwargs['task_data'].deadline is None

    # Test Uncomplete Fail
    with patch("src.webapp.state.coordinator.task_manager.update_task_status") as mock_stat:
        mock_stat.return_value = False
        res = client.post("/api/tasks/1/uncomplete")
        assert res.status_code == 404

    # Test Delete Fail
    with patch("src.webapp.state.coordinator.task_manager.delete_task") as mock_del:
        mock_del.return_value = False
        res = client.post("/api/tasks/1/delete")
        assert res.status_code == 404



