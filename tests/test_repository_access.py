
import pytest
from src.database.repositories.task_repository import TaskManager
from src.database.models import User, TaskList, Task, SharedAccess

@pytest.fixture
def access_data(test_db):
    owner = User.create(username="owner", telegram_id=100)
    member = User.create(username="member", telegram_id=200)
    outsider = User.create(username="outsider", telegram_id=300)

    lst = TaskList.create(title="List", owner=owner)
    t_in_list = Task.create(title="Task In List", user=owner, task_list=lst)

    t_loose = Task.create(title="Loose Task", user=owner)

    return owner, member, outsider, lst, t_in_list, t_loose

def test_access_owner(access_data):
    owner, _, _, _, t_in_list, t_loose = access_data
    assert TaskManager._check_task_access(owner.telegram_id, t_in_list) is True
    assert TaskManager._check_task_access(owner.telegram_id, t_loose) is True

def test_access_shared_accepted(access_data):
    owner, member, _, lst, t_in_list, t_loose = access_data

    # Share list
    SharedAccess.create(user=member, task_list=lst, status="ACCEPTED")

    # Member should have access to task in list
    assert TaskManager._check_task_access(member.telegram_id, t_in_list) is True

    # Member should NOT have access to loose task of owner
    assert TaskManager._check_task_access(member.telegram_id, t_loose) is False

def test_access_shared_pending(access_data):
    owner, member, _, lst, t_in_list, _ = access_data

    # Share list PENDING
    SharedAccess.create(user=member, task_list=lst, status="PENDING")

    # Member should NOT have access yet
    assert TaskManager._check_task_access(member.telegram_id, t_in_list) is False

def test_access_outsider(access_data):
    _, _, outsider, _, t_in_list, _ = access_data
    assert TaskManager._check_task_access(outsider.telegram_id, t_in_list) is False

def test_edit_task_denied(access_data):
    _, _, outsider, _, t_in_list, _ = access_data
    from src.utils.schema import TaskSchema

    res = TaskManager.edit_task(outsider.telegram_id, t_in_list.id, TaskSchema(title="Hacked"))
    assert res is False

    # Verify not changed
    t = Task.get_by_id(t_in_list.id)
    assert t.title == "Task In List"
