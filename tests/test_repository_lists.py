
import pytest
from unittest.mock import MagicMock, patch
from src.database.repositories.task_repository import TaskManager
from src.database.models import User, TaskList, SharedAccess

@pytest.fixture
def repo_list_data(test_db):
    u1 = User.create(username="u1", telegram_id=100)
    u2 = User.create(username="u2", telegram_id=200)

    l1 = TaskList.create(title="L1", owner=u1, position=0)
    l2 = TaskList.create(title="L2", owner=u1, position=1)
    l3 = TaskList.create(title="L3 Shared", owner=u2) # u2 owns

    # Share l3 with u1
    SharedAccess.create(user=u1, task_list=l3, status="ACCEPTED", position=2)

    return u1, [l1, l2, l3]

def test_reorder_lists(repo_list_data):
    u1, lists = repo_list_data
    # Reorder: L2 (id=2), L3 (id=3), L1 (id=1)
    new_order = [lists[1].id, lists[2].id, lists[0].id]

    res = TaskManager.reorder_lists(u1.telegram_id, new_order)
    assert res is True

    # Verify positions
    l1_fresh = TaskList.get_by_id(lists[0].id)
    l2_fresh = TaskList.get_by_id(lists[1].id)
    acc_fresh = SharedAccess.get(SharedAccess.task_list == lists[2].id)

    assert l2_fresh.position == 0
    assert acc_fresh.position == 1 # Shared access update
    assert l1_fresh.position == 2

def test_is_user_in_list(repo_list_data):
    u1, lists = repo_list_data
    l3_shared = lists[2] # Owned by u2, shared with u1

    assert TaskManager.is_user_in_list(u1.telegram_id, l3_shared.id) is True

    # Random user
    assert TaskManager.is_user_in_list(999, l3_shared.id) is False

def test_get_list_members(repo_list_data):
    u1, lists = repo_list_data
    l3_shared = lists[2]

    members = TaskManager.get_list_members(l3_shared.id)
    # Should contain u2 (owner) and u1 (shared)
    ids = {u.telegram_id for u in members}
    assert 200 in ids # Owner
    assert 100 in ids # Shared

def test_delete_all_lists(repo_list_data):
    u1, lists = repo_list_data
    # u1 owns L1 and L2

    count = TaskManager.delete_all_lists(u1.telegram_id)
    assert count == 2

    # Verify deleted
    assert TaskList.get_or_none(TaskList.id == lists[0].id) is None
    assert TaskList.get_or_none(TaskList.id == lists[1].id) is None
    # Shared list L3 (owned by u2) should exist
    assert TaskList.get_or_none(TaskList.id == lists[2].id) is not None

def test_edit_list_color(repo_list_data):
    u1, lists = repo_list_data
    l1 = lists[0]

    res = TaskManager.edit_list_color(u1.telegram_id, l1.id, "#FF0000")
    assert res is True

    l1_fresh = TaskList.get_by_id(l1.id)
    assert l1_fresh.color == "#FF0000"


