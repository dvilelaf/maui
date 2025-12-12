
import pytest
from unittest.mock import AsyncMock
from src.database.repositories.task_repository import TaskManager
from src.database.repositories.user_repository import UserManager
from src.database.models import User, TaskList, SharedAccess

@pytest.mark.asyncio
async def test_full_sharing_workflow(test_db, mocker):
    # Mock notify_user where it is USED
    mock_notify = mocker.patch("src.database.repositories.task_repository.notify_user", new_callable=AsyncMock)

    # Setup Users
    owner = UserManager.get_or_create_user(100, "Owner") # Changed to UserManager and kept original username
    alice = UserManager.get_or_create_user(101, "Alice") # Changed to UserManager
    bob = UserManager.get_or_create_user(102, "Bob") # Changed to UserManager

    # 1. Invite Alice
    # ----------------
    tl = TaskManager.create_list(owner.telegram_id, "Party List")
    success, msg = await TaskManager.share_list(owner.telegram_id, tl.id, "Alice")

    assert success
    assert "Alice" in msg

    # Check status is PENDING
    access = SharedAccess.get(SharedAccess.user == alice, SharedAccess.task_list == tl)
    assert access.status == "PENDING"

    # Check notification to Alice
    assert mock_notify.call_count == 1
    args = mock_notify.call_args_list[-1][0]
    assert args[0] == alice.telegram_id
    assert "invitado" in args[1] or "compartido" in args[1]

    # 2. Alice Joins
    # --------------
    success, msg = await TaskManager.respond_to_invite(alice.telegram_id, tl.id, accept=True)
    assert success
    assert "unido" in msg

    # Check status ACCEPTED
    access = SharedAccess.get(SharedAccess.id == access.id)
    assert access.status == "ACCEPTED"

    # Check notification to Owner (and self?)
    # respond_to_invite should notify owner at least.
    # call_args_list should have grown.
    # We expect notification to owner(100) saying Alice joined.
    found_owner_notif = False
    for call in mock_notify.call_args_list:
        if call[0][0] == owner.telegram_id and "Alice" in call[0][1] and "unido" in call[0][1]:
            found_owner_notif = True
    assert found_owner_notif, "Owner should be notified when Alice joins"

    # 3. Invite Bob and Bob Rejects
    # -----------------------------
    await TaskManager.share_list(owner.telegram_id, tl.id, "Bob")
    access_bob = SharedAccess.get(SharedAccess.user == bob, SharedAccess.task_list == tl)
    assert access_bob.status == "PENDING"

    success, msg = await TaskManager.respond_to_invite(bob.telegram_id, tl.id, accept=False)
    assert success
    assert "rechazado" in msg

    # Check access deleted or CANCELLED/REJECTED?
    # Plan said "delete access record" or maybe update status?
    # Let's say we delete it to keep it clean, or mark REJECTED.
    # If we delete, query gets None.
    assert SharedAccess.get_or_none(SharedAccess.user == bob, SharedAccess.task_list == tl) is None

    # Check notification to Owner
    found_reject_notif = False
    for call in mock_notify.call_args_list:
        if call[0][0] == owner.telegram_id and "Bob" in call[0][1] and "rechazado" in call[0][1]:
            found_reject_notif = True
    assert found_reject_notif, "Owner should be notified when Bob rejects"

    # 4. Alice Leaves
    # ---------------
    mock_notify.reset_mock() # Clear history to verify easier
    success, msg = await TaskManager.leave_list(alice.telegram_id, tl.id)
    assert success
    assert "salido" in msg or "dejado" in msg

    assert SharedAccess.get_or_none(SharedAccess.user == alice, SharedAccess.task_list == tl) is None

    # Check notification to Owner
    mock_notify.assert_called()
    # Should notify owner
    found_leave_notif = False
    for call in mock_notify.call_args_list:
        if call[0][0] == owner.telegram_id and "Alice" in call[0][1]:
            found_leave_notif = True
    assert found_leave_notif
