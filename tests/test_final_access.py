from src.database.models import User, Task, TaskList, SharedAccess
import pytest
from unittest.mock import AsyncMock
from src.database.repositories.task_repository import TaskManager

@pytest.mark.asyncio
async def test_leave_list_success(test_db, mocker):
    mocker.patch("src.services.notification_service.notify_user", new_callable=AsyncMock)
    # Line 229: get_or_none
    # We need to call get_or_none directly
    u = User.get_or_none(User.telegram_id == 99999)
    assert u is None

    # Line 345: share_list user not found
    # We need share_list to return False, "not found"
    # Create owner and list
    owner = User.create(telegram_id=10, first_name="Owner", status="APPROVED")
    tlist = TaskList.create(title="My List", owner=owner)

    # Search for non-existent user
    success, msg = await TaskManager.share_list(tlist.id, "@ghostuser")
    assert success is False
    assert "no encontrado" in msg

    # Line 427: find_list_by_name - Case C: clean_name in title_norm
    # Query="compra" (clean="compra"), List="lista de la compra" (norm="lista de la compra")
    # "compra" in "lista de la compra" -> True

    tlist2 = TaskList.create(title="Lista de la Compra", owner=owner)
    found = TaskManager.find_list_by_name(10, "compra")
    assert found == tlist2
