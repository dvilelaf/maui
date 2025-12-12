import pytest
from unittest.mock import AsyncMock, MagicMock
from src.database.repositories.task_repository import TaskManager
from src.database.repositories.user_repository import UserManager
from src.tools.admin import (
    resolve_user,
    confirm_action,
    kick_user,
    update_status,
)
from src.database.models import User, Task, TaskList, SharedAccess
from src.utils.schema import TaskSchema, UserStatus

@pytest.fixture
def mock_input(mocker):
    return mocker.patch("builtins.input")

@pytest.mark.asyncio
async def test_notify_user_exception(mocker, caplog):
    mocker.patch("src.services.notification_service.Bot", side_effect=Exception("Bot Error"))

    from src.services.notification_service import notify_user
    await notify_user(111, "msg")
    assert "Failed to send notification" in caplog.text

def test_resolve_user_branches(test_db):
    u = UserManager.get_or_create_user(999, "digit_user")
    assert resolve_user("999") == u
    assert resolve_user("@digit_user") == u
    assert resolve_user("digit_user") == u
    assert resolve_user("nonexistent") is None

def test_confirm_action_yes(mocker):
    mocker.patch("builtins.input", return_value="y")
    assert confirm_action("?") is True

def test_confirm_action_no(mocker):
    mocker.patch("builtins.input", return_value="n")
    assert confirm_action("?") is False

def test_kick_user_not_found(mocker, capsys, test_db):
    kick_user(123456)
    captured = capsys.readouterr()
    assert "not found" in captured.out

def test_kick_user_cancel(mocker, test_db, capsys):
    u = UserManager.get_or_create_user(555, "safe")
    mocker.patch("src.tools.admin.confirm_action", return_value=False)
    kick_user(555)
    captured = capsys.readouterr()
    assert "cancelled" in captured.out
    assert User.get_or_none(User.telegram_id==555) is not None

def test_kick_user_exception(mocker, test_db, capsys):
    u = UserManager.get_or_create_user(666, "err")
    mocker.patch("src.tools.admin.confirm_action", return_value=True)
    mocker.patch("src.database.models.Task.delete", side_effect=Exception("Delete Error"))

    kick_user(666)
    captured = capsys.readouterr()
    assert "Error kicking" in captured.out

def test_update_status_branches(test_db, mocker):
    u = UserManager.get_or_create_user(777, "status_test")
    mock_notify = mocker.patch("src.tools.admin.notify_user", new_callable=AsyncMock)

    # Whitelist
    update_status(u, UserStatus.WHITELISTED)
    mock_notify.assert_called_with(777, "✅ ¡Tu cuenta ha sido aprobada! Ya puedes usar Maui para gestionar tus tareas.")

    # Blacklist
    update_status(u, UserStatus.BLACKLISTED)
    mock_notify.assert_called_with(777, "⛔ Tu solicitud de acceso ha sido denegada.")

    # Other (no notify)
    mock_notify.reset_mock()
    update_status(u, UserStatus.PENDING)
    mock_notify.assert_not_called()

def test_update_status_exception(test_db, mocker, capsys):
    u = UserManager.get_or_create_user(778, "status_err")
    mocker.patch("src.database.models.User.save", side_effect=Exception("Save Error"))
    update_status(u, UserStatus.WHITELISTED)
    captured = capsys.readouterr()
    assert "Error updating" in captured.out

@pytest.mark.asyncio
async def test_share_list(test_db, mocker):
    mocker.patch("src.database.repositories.task_repository.notify_user", new_callable=AsyncMock)
    u = UserManager.get_or_create_user(1, "u1")
    l = TaskManager.create_list(1, "L1")
    u2 = UserManager.get_or_create_user(2, "u2")

    success, msg = await TaskManager.share_list(1, l.id, "u2")
    assert success
