
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.database.repositories.task_repository import TaskManager
from unittest.mock import AsyncMock
from src.database.repositories.task_repository import TaskManager
from src.database.repositories.user_repository import UserManager
from src.database.models import TaskList, SharedAccess

@pytest.fixture
def mock_notify(mocker):
    # Patch where it is USED in TaskManager
    mock_notify = mocker.patch("src.database.repositories.task_repository.notify_user", new_callable=AsyncMock)
    return mock_notify

@pytest.mark.asyncio
async def test_share_list_notifies_user(test_db, mock_notify):
    # Setup
    owner = UserManager.get_or_create_user(telegram_id=100, first_name="Owner", username="owner")
    target = UserManager.get_or_create_user(telegram_id=200, first_name="Target", username="target")
    tl = TaskList.create(title="SharedStuff", owner=owner)

    # Call share_list (which we expect to be async now)
    # Note: If code isn't updated yet, this test will fail as share_list is currently sync.
    # We write the test assuming the contract we ARE BUILDING.
    # If the function is sync in current code, we might need 'await' to be conditional or fail.
    # But since we are TDD-ish, we expect this to drive the change.

    # Executing call
    success, msg = await TaskManager.share_list(owner.telegram_id, tl.id, "target")

    assert success
    assert "Invitación enviada" in msg

    # Verify notification
    mock_notify.assert_called_once()
    args, _ = mock_notify.call_args
    assert args[0] == 200 # Target ID
    # Code prefers username over first name
    assert "owner" in args[1] # Message mentions owner
    assert "SharedStuff" in args[1] # Message mentions list title
