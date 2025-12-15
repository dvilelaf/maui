
import pytest
from unittest.mock import patch, MagicMock
from src.webapp.auth import validate_telegram_data
from fastapi.testclient import TestClient
from src.webapp.app import app
from src.webapp.auth import get_current_user

# Helper to generate mock init_data (not real HMAC but structure)
def mock_init_data(valid=True):
    # This is hard to fake without knowing the key logic or mocking hmac.
    # We will mock the validation function itself partially or test logic branches by patching internal hmac.
    pass

def test_validate_telegram_data_invalid():
    # Empty
    assert validate_telegram_data("", "token") is None
    # Bad format
    assert validate_telegram_data("invalid", "token") is None
    # No hash
    assert validate_telegram_data("key=val", "token") is None

    # Hash mismatch
    # We need a string that parses but fails hash check
    # "hash=abc&user={}"
    with patch("src.webapp.auth.hmac") as mock_hmac:
        mock_hmac.new.return_value.hexdigest.return_value = "def" # Mismatch
        assert validate_telegram_data("hash=abc&user={}", "token") is None

    # Valid hash but invalid user json
    with patch("src.webapp.auth.hmac") as mock_hmac:
        mock_hmac.new.return_value.hexdigest.return_value = "abc"
        # Mock digest for secret key too
        mock_hmac.new.return_value.digest.return_value = b"secret"

        # "hash=abc&user=BADJSON"
        # Note: validate_telegram_data sorts keys.
        # "hash" is popped. "user=BADJSON" remains.
        assert validate_telegram_data("hash=abc&user=BADJSON", "token") is None

@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: 123
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}

def test_dashboard_route(client):
    # Test dashboard/all route logic
    # Mock get_dashboard_items
    with patch("src.webapp.state.coordinator.task_manager.get_dashboard_items") as mock_get:
        # Return mixed items
        # item['data'] must be object with attributes
        task_data = MagicMock()
        task_data.id = 1
        task_data.title = "Task"
        task_data.status = "PENDING"
        task_data.priority = "HIGH"
        task_data.deadline = None

        list_data = MagicMock()
        list_data.id = 2
        list_data.title = "List"
        list_data.color = "red"
        # Mock tasks.count()
        list_data.tasks.count.return_value = 5

        # Items structure: type, data, position, created_at
        from datetime import datetime
        items = [
            {"type": "task", "data": task_data, "position": 0, "created_at": datetime.now()},
            {"type": "list", "data": list_data, "position": 1, "created_at": datetime.now()}
        ]
        mock_get.return_value = items

        res = client.get("/api/dashboard/all")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        assert data[0]["type"] == "task"
        assert data[1]["type"] == "list"
        assert data[1]["task_count"] == 5

def test_dashboard_reorder_fail(client):
    # Test reorder exception (lines 131-132)
    # Patch Task.update. Since it's imported locally inside function, checking src.database.models.Task works if patched at call time.
    with patch("src.database.models.Task.update") as mock_upd:
        mock_upd.side_effect = Exception("Atomic Fail")
        res = client.post("/api/dashboard/reorder", json={
            "user_id": 123,
            "items": [{"type": "task", "id": 1}]
        })
        assert res.status_code == 500

def test_dashboard_items_logic(client):
    # Hitting lines 80-84 in dashboard.py?
    # get_dashboard_items logic in repository is covered by test_repository_extended.
    # We need to hit router lines.
    # Lines 80-84 might be `get_dated_items` endpoint or similar?
    pass
