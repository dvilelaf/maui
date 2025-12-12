
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.database.models import User, Task, TaskList, SharedAccess
from src.utils.schema import TaskSchema, UserStatus

@pytest.mark.asyncio
async def test_resolve_user_edge(test_db):
    from src.tools.admin import resolve_user
    u = User.create(telegram_id=555, username="num_user")
    assert resolve_user("555") == u
    assert resolve_user("num_user") == u
    assert resolve_user("@num_user") == u

def test_task_manager_find_list_coverage(test_db):
    from src.database.repositories.task_repository import TaskManager
    u = User.create(telegram_id=200, username="lister")
    l = TaskManager.create_list(200, "CleanList")

    assert TaskManager.find_list_by_name(200, "CleanList") == l
    assert TaskManager.find_list_by_name(200, "cleanlist") == l

    # Partial match is supported by legacy logic using LIKE/contains
    assert TaskManager.find_list_by_name(200, "Clean") == l

    # Non-existent falls back to first owned
    assert TaskManager.find_list_by_name(200, "NonExistent") == l

    # Other user finds nothing
    User.create(telegram_id=201, username="other")
    assert TaskManager.find_list_by_name(201, "CleanList") is None

@pytest.mark.asyncio
async def test_notify_exception_handling(mocker, caplog):
    mocker.patch("src.services.notification_service.Bot", side_effect=Exception("Conn err"))
    from src.services.notification_service import notify_user
    await notify_user(1, "test")
    assert "Failed to send notification" in caplog.text

def test_create_list_basic(test_db):
    from src.database.repositories.task_repository import TaskManager
    l = TaskManager.create_list(300, "New List")
    assert l.title == "New List"

@pytest.mark.asyncio
async def test_share_list_fuzzy_multi(test_db, mocker):
    mocker.patch("src.services.notification_service.notify_user", new_callable=AsyncMock)
    from src.database.repositories.task_repository import TaskManager

    owner = User.create(telegram_id=1000)
    tl = TaskList.create(title="MultiShare", owner=owner)

    User.create(telegram_id=1001, first_name="Alice", username="alice_u")
    User.create(telegram_id=1002, first_name="Alicia", username="alicia_u")

    success, msg = await TaskManager.share_list(tl.id, "Ali")
    if success:
        assert "Invitación enviada" in msg
    else:
        assert "Múltiples usuarios" in msg or "varios usuarios" in msg

    success, msg = await TaskManager.share_list(tl.id, "Alice")
    assert success
    # Check for First Name OR Username
    assert "Alice" in msg or "alice_u" in msg

@pytest.mark.asyncio
async def test_leave_list_not_member(test_db):
    from src.database.repositories.task_repository import TaskManager

    owner = User.create(telegram_id=1)
    user = User.create(telegram_id=2)
    tl = TaskList.create(title="MyList", owner=owner)

    success, msg = await TaskManager.leave_list(user.telegram_id, tl.id)
    assert not success
    assert "No eres miembro" in msg or "no eres miembro" in msg

    success, msg = await TaskManager.leave_list(owner.telegram_id, tl.id)
    assert not success
    assert "No eres miembro" in msg or "creador" in msg or "propietario" in msg

@pytest.mark.asyncio
async def test_share_list_fuzzy_fail(test_db, mocker):
    from src.database.repositories.task_repository import TaskManager
    mocker.patch("src.database.repositories.task_repository.notify_user", new_callable=AsyncMock)

    tl = TaskList.create(title="MyList", owner=User.create(telegram_id=1))
    success, msg = await TaskManager.share_list(tl.id, "Nobody")
    assert not success

@pytest.mark.asyncio
async def test_share_list_complex(test_db, mocker):
    from src.database.repositories.task_repository import TaskManager
    mocker.patch("src.database.repositories.task_repository.notify_user", new_callable=AsyncMock)

    owner = User.create(telegram_id=3000)
    tl = TaskList.create(title="ShareComplex", owner=owner)

    u = User.create(telegram_id=3001, username="complex_user")

    success, msg = await TaskManager.share_list(tl.id, "complex")
    assert success
    assert "complex_user" in msg

@pytest.mark.asyncio
async def test_find_list_by_name_coverage(test_db):
    from src.database.repositories.task_repository import TaskManager
    u = User.create(telegram_id=1234, username="finder")

    other = User.create(telegram_id=4001)
    tl_shared = TaskList.create(title="MyShared", owner=other)
    SharedAccess.create(user=u, task_list=tl_shared, status="ACCEPTED")

    l = TaskManager.find_list_by_name(1234, "MyShared")
    assert l.id == tl_shared.id

@pytest.mark.asyncio
async def test_add_task_list_not_found(test_db):
    from src.database.repositories.task_repository import TaskManager
    from src.utils.schema import TaskSchema

    User.create(telegram_id=5000)
    ts = TaskSchema(title="T", list_name="GhostList")
    t = TaskManager.add_task(5000, ts)

    assert t is not None
    # No list created, so it's None
    assert t.task_list is None
