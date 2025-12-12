
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.database.access import TaskManager
from src.database.models import User, TaskList

@pytest.mark.asyncio
async def test_share_list_notifies_user(test_db, mocker):
    # Setup
    owner = User.create(telegram_id=100, first_name="Owner", username="owner")
    target = User.create(telegram_id=200, first_name="Target", username="target")
    tl = TaskList.create(title="SharedStuff", owner=owner)

    # Mock notify_user in access.py
    # Since it is imported/defined at module level, we patch 'src.database.access.notify_user'
    mock_notify = mocker.patch("src.database.access.notify_user", new_callable=AsyncMock)

    # Call share_list (which we expect to be async now)
    # Note: If code isn't updated yet, this test will fail as share_list is currently sync.
    # We write the test assuming the contract we ARE BUILDING.
    # If the function is sync in current code, we might need 'await' to be conditional or fail.
    # But since we are TDD-ish, we expect this to drive the change.

    # Executing call
    success, msg = await TaskManager.share_list(tl.id, "target")

    assert success
    assert "Invitación enviada" in msg

    # Verify notification
    mock_notify.assert_called_once()
    args, _ = mock_notify.call_args
    assert args[0] == 200 # Target ID
    # Code prefers username over first name
    assert "owner" in args[1] # Message mentions owner
    assert "SharedStuff" in args[1] # Message mentions list title
