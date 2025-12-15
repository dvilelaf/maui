
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.services.coordinator import Coordinator
from src.utils.schema import TaskSchema, TaskStatus, TimeFilter, UserIntent, TaskExtractionResponse, UserStatus
from src.database.repositories.user_repository import UserManager
from src.database.repositories.task_repository import TaskManager
from src.database.models import User, Task, TaskList
from datetime import datetime, timedelta

@pytest.fixture
def coordinator(mock_gemini, test_db, mock_bot):
    with patch("src.services.llm_provider.LLMFactory.get_provider") as mock_factory:
        mock_provider = MagicMock()
        mock_factory.return_value = mock_provider
        coord = Coordinator()
        # Ensure we can mock process_input
        coord.llm = mock_provider
        return coord

@pytest.fixture
def user(test_db):
    user = UserManager.get_or_create_user(12345, "testuser", "Test", "User")
    user.status = UserStatus.WHITELISTED
    user.save()
    return user

@pytest.mark.asyncio
async def test_handle_add_task(coordinator, user):
    """Test ADD_TASK intent."""
    extraction = TaskExtractionResponse(
        intent=UserIntent.ADD_TASK,
        is_relevant=True,
        formatted_task=TaskSchema(title="New Task")
    )

    response = await coordinator.handle_message(user.telegram_id, "testuser", "msg", extractions=[extraction])

    assert "✅" in response
    assert "New Task" in response
    assert Task.select().count() == 1

@pytest.mark.asyncio
async def test_handle_add_task_to_list(coordinator, user):
    """Test adding task to a specific list."""
    TaskManager.create_list(user.telegram_id, "Shopping")

    extraction = TaskExtractionResponse(
        intent=UserIntent.ADD_TASK,
        is_relevant=True,
        formatted_task=TaskSchema(title="Milk", list_name="Shopping")
    )

    response = await coordinator.handle_message(user.telegram_id, "user", "add milk to shopping", extractions=[extraction])

    assert "✅" in response
    assert "Shopping" in response
    assert "Milk" in response

    # Verify DB
    tlist = TaskManager.find_list_by_name(user.telegram_id, "Shopping")
    tasks = TaskManager.get_tasks_in_list(tlist.id)
    assert len(tasks) == 1
    assert tasks[0].title == "Milk"

@pytest.mark.asyncio
async def test_handle_query_tasks(coordinator, user):
    """Test QUERY_TASKS intent."""
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Task A"))

    extraction = TaskExtractionResponse(
        intent=UserIntent.QUERY_TASKS,
        is_relevant=True
    )

    response = await coordinator.handle_message(user.telegram_id, "user", "list tasks", extractions=[extraction])

    assert "Task A" in response
    assert "pendientes" in response

@pytest.mark.asyncio
async def test_handle_query_specific_list(coordinator, user):
    """Test querying a specific list via natural language."""
    tlist = TaskManager.create_list(user.telegram_id, "Groceries")
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Bread", list_name="Groceries"))

    extraction = TaskExtractionResponse(
        intent=UserIntent.QUERY_TASKS,
        is_relevant=True,
        formatted_task=TaskSchema(list_name="Groceries")
    )

    response = await coordinator.handle_message(user.telegram_id, "testuser", "show groceries", extractions=[extraction])

    assert "📝" in response
    assert "Groceries" in response
    assert "Bread" in response
    # Should NOT show general tasks if they existed

@pytest.mark.asyncio
async def test_handle_unknown(coordinator, user):
    extraction = TaskExtractionResponse(
        intent=UserIntent.UNKNOWN,
        is_relevant=False,
        reasoning="Idk"
    )
    response = await coordinator.handle_message(user.telegram_id, "user", "blah", extractions=[extraction])
    assert response == "Idk"

@pytest.mark.asyncio
async def test_handle_create_list(coordinator, user):
    extraction = TaskExtractionResponse(
        intent=UserIntent.CREATE_LIST,
        is_relevant=True,
        formatted_task=TaskSchema(title="Vacation")
    )
    response = await coordinator.handle_message(user.telegram_id, "testuser", "create list Vacation", extractions=[extraction])
    assert "Lista creada" in response
    assert "Vacation" in response
    assert TaskManager.find_list_by_name(user.telegram_id, "Vacation") is not None

@pytest.mark.asyncio
async def test_handle_share_list(coordinator, user):
    # Setup
    coordinator.task_manager.find_list_by_name = MagicMock(return_value=TaskList(id=1, title="Test List"))
    coordinator.task_manager.share_list = AsyncMock(return_value=(True, "Invitación enviada"))
    coordinator.user_manager.get_or_create_user = MagicMock(return_value=MagicMock(telegram_id=12345, status=UserStatus.WHITELISTED))

    # Mocks
    coordinator.llm.process_input.return_value = [TaskExtractionResponse(
        is_relevant=True,
        intent=UserIntent.SHARE_LIST,
        target_search_term="Test List",
        formatted_task=TaskSchema(title="Test List", shared_with=["friend"])
    )]

    response = await coordinator.handle_message(12345, "user", "Compartir lista Test List con friend")

    # Assert
    coordinator.task_manager.share_list.assert_called_with(12345, 1, "friend")
    assert "✅" in response

    # Verify sharing
    # We'd need to check database join table but let's trust the response for now or checking implementation
    # TaskManager.share_list returns (True, msg)

@pytest.mark.asyncio
async def test_handle_share_list_missing_info(coordinator, user):
    extraction = TaskExtractionResponse(
        intent=UserIntent.SHARE_LIST,
        is_relevant=True,
        # Missing formatted_task or target_search_term
    )
    response = await coordinator.handle_message(user.telegram_id, "testuser", "share list", extractions=[extraction])
    assert "necesito el nombre de la lista" in response

@pytest.mark.asyncio
async def test_handle_complete_task(coordinator, user):
    task = TaskManager.add_task(user.telegram_id, TaskSchema(title="Finish Report"))

    extraction = TaskExtractionResponse(
        intent=UserIntent.COMPLETE_TASK,
        is_relevant=True,
        target_search_term="Finish Report"
    )

    response = await coordinator.handle_message(user.telegram_id, "testuser", "complete task Finish Report", extractions=[extraction])
    assert "completada" in response

    task_db = Task.get_by_id(task.id)
    assert task_db.status == TaskStatus.COMPLETED

@pytest.mark.asyncio
async def test_handle_delete_list(coordinator, user):
    """Test DELETE_LIST intent."""
    l = TaskManager.create_list(user.telegram_id, "DeleteMe")
    extraction = TaskExtractionResponse(
        intent=UserIntent.DELETE_LIST,
        is_relevant=True,
        target_search_term="DeleteMe"
    )
    response = await coordinator.handle_message(user.telegram_id, "user", "delete list DeleteMe", extractions=[extraction])
    assert "Lista eliminada" in response
    assert TaskList.get_or_none(TaskList.id == l.id) is None

    assert "Lista eliminada" in response
    assert TaskList.get_or_none(TaskList.id == l.id) is None

@pytest.mark.asyncio
async def test_handle_delete_all_lists(coordinator, user):
    """Test DELETE_LIST intent with ALL target."""
    TaskManager.create_list(user.telegram_id, "L1")
    TaskManager.create_list(user.telegram_id, "L2")

    extraction = TaskExtractionResponse(
        intent=UserIntent.DELETE_LIST,
        is_relevant=True,
        target_search_term="ALL"
    )
    response = await coordinator.handle_message(user.telegram_id, "user", "delete all lists", extractions=[extraction])
    assert "eliminado 2 listas" in response
    assert TaskList.select().where(TaskList.owner == user.telegram_id).count() == 0

@pytest.mark.asyncio
async def test_handle_cancel_task(coordinator, user):
    task = TaskManager.add_task(user.telegram_id, TaskSchema(title="Meeting"))

    extraction = TaskExtractionResponse(
        intent=UserIntent.CANCEL_TASK,
        is_relevant=True,
        target_search_term="Meeting"
    )

    response = await coordinator.handle_message(user.telegram_id, "testuser", "cancel meeting", extractions=[extraction])
    assert "eliminada" in response

    # Peewee soft delete check if implemented as status change or hard delete
    # Access.py delete_task calls query.execute() which deletes row
    assert Task.select().where(Task.id == task.id).count() == 0

@pytest.mark.asyncio
async def test_handle_cancel_all_tasks(coordinator, user):
    TaskManager.add_task(user.telegram_id, TaskSchema(title="T1"))
    TaskManager.add_task(user.telegram_id, TaskSchema(title="T2"))

    extraction = TaskExtractionResponse(
        intent=UserIntent.CANCEL_TASK,
        is_relevant=True,
        target_search_term="ALL",
        time_filter=TimeFilter.ALL
    )

    response = await coordinator.handle_message(user.telegram_id, "testuser", "delete all tasks", extractions=[extraction])
    assert "eliminado 2 tareas" in response
    assert Task.select().count() == 0

@pytest.mark.asyncio
async def test_handle_edit_task(coordinator, user):
    task = TaskManager.add_task(user.telegram_id, TaskSchema(title="Old Title", priority="LOW"))

    extraction = TaskExtractionResponse(
        intent=UserIntent.EDIT_TASK,
        is_relevant=True,
        target_search_term="Old Title",
        formatted_task=TaskSchema(title="New Title", priority="HIGH")
    )

    response = await coordinator.handle_message(user.telegram_id, "testuser", "change title to New Title", extractions=[extraction])
    assert "actualizada" in response
    assert "New Title" in response
    assert "HIGH" in response

    task_db = Task.get_by_id(task.id)
    assert task_db.title == "New Title"
    assert task_db.priority == "HIGH"

@pytest.mark.asyncio
async def test_access_control(coordinator, mocker):
    # PENDING
    mocker.patch.object(coordinator.user_manager, "get_or_create_user",
        return_value=MagicMock(status=UserStatus.PENDING))
    resp = await coordinator.handle_message(1, "u", "msg")
    assert "pendiente de aprobación" in resp

    # BLACKLISTED
    mocker.patch.object(coordinator.user_manager, "get_or_create_user",
        return_value=MagicMock(status=UserStatus.BLACKLISTED))
    resp = await coordinator.handle_message(2, "u2", "msg")
    assert "No tienes permiso" in resp

@pytest.mark.asyncio
async def test_create_list_fallback(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(
        intent=UserIntent.CREATE_LIST,
        is_relevant=True,
        formatted_task=None # No title
    )
    resp = await coordinator.handle_message(123, "test", "irrelevant", extractions=[extract])
    resp = await coordinator.handle_message(123, "test", "irrelevant", extractions=[extract])
    assert "Nueva Lista" in resp

@pytest.mark.asyncio
async def test_create_list_fallback_target(coordinator, mocker):
    """Test CREATE_LIST where name is in target_search_term."""
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(
        intent=UserIntent.CREATE_LIST,
        is_relevant=True,
        target_search_term="TargetName",
        formatted_task=None
    )
    resp = await coordinator.handle_message(123, "test", "irrelevant", extractions=[extract])
    assert "TargetName" in resp
    assert TaskManager.find_list_by_name(123, "TargetName") is not None

@pytest.mark.asyncio
async def test_share_list_errors(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    # Missing info
    extract = TaskExtractionResponse(
        intent=UserIntent.SHARE_LIST,
        is_relevant=True,
        target_search_term=None # Missing list name
    )
    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "necesito el nombre" in resp

    # List not found
    extract.target_search_term = "NonExistent"
    extract.formatted_task = TaskSchema(title="dummy", shared_with=["someone"])
    mocker.patch.object(coordinator.task_manager, "find_list_by_name", return_value=None)

    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "No encontré ninguna lista" in resp

@pytest.mark.asyncio
async def test_query_list_empty(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(
        intent=UserIntent.QUERY_TASKS,
        is_relevant=True,
        formatted_task=TaskSchema(title="d", list_name="EmptyList")
    )
    # Found list but empty tasks
    mocker.patch.object(coordinator.task_manager, "find_list_by_name", return_value=MagicMock(id=1, title="EmptyList"))
    mocker.patch.object(coordinator.task_manager, "get_tasks_in_list", return_value=[])

    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "está vacía" in resp

@pytest.mark.asyncio
async def test_add_task_duplicate_coordinator(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(
        intent=UserIntent.ADD_TASK,
        is_relevant=True,
        formatted_task=TaskSchema(title="Dupe")
    )
    mocker.patch.object(coordinator.task_manager, "add_task", return_value=None)
    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "Ya tienes una tarea" in resp

@pytest.mark.asyncio
async def test_edit_task_changes(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    # Setup candidate
    original = MagicMock(id=1, title="Old Title", description="Old Desc", status=TaskStatus.PENDING, deadline=None, priority="LOW")
    mocker.patch.object(coordinator.task_manager, "find_tasks_by_keyword", return_value=[original])
    mocker.patch.object(coordinator.task_manager, "edit_task", return_value=True)

    # Edit Title and Priority
    extract = TaskExtractionResponse(
        intent=UserIntent.EDIT_TASK,
        is_relevant=True,
        target_search_term="Old",
        formatted_task=TaskSchema(title="New Title", priority="HIGH")
    )

    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "Actualizada" in resp or "actualizada" in resp
    assert "Old Title -> New Title" in resp
    assert "LOW -> HIGH" in resp

@pytest.mark.asyncio
async def test_cancel_all_filter(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(
        intent=UserIntent.CANCEL_TASK,
        is_relevant=True,
        target_search_term="ALL",
        time_filter=TimeFilter.TODAY
    )
    mocker.patch.object(coordinator.task_manager, "delete_all_pending_tasks", return_value=5)
    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "eliminado 5 tareas" in resp
    assert "para hoy" in resp

@pytest.mark.asyncio
async def test_handle_no_extraction(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    # Mock gemini
    mocker.patch.object(coordinator.llm, "process_input", return_value=[TaskExtractionResponse(intent=UserIntent.UNKNOWN, is_relevant=False)])
    resp = await coordinator.handle_message(123, "u", "raw", extractions=None)
    assert "No he entendido" in resp

@pytest.mark.asyncio
async def test_query_list_not_found(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(
        intent=UserIntent.QUERY_TASKS,
        is_relevant=True,
        formatted_task=TaskSchema(list_name="Missing")
    )
    mocker.patch.object(coordinator.task_manager, "find_list_by_name", return_value=None)
    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "No encontré ninguna lista" in resp

@pytest.mark.asyncio
async def test_edit_task_deadline(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))

    # Old deadline
    old_date = datetime.now()
    original = MagicMock(id=1, title="T", description="D", status=TaskStatus.PENDING, deadline=old_date, priority="LOW")

    mocker.patch.object(coordinator.task_manager, "find_tasks_by_keyword", return_value=[original])
    mocker.patch.object(coordinator.task_manager, "edit_task", return_value=True)

    # New deadline
    new_date = old_date + timedelta(days=1)
    extract = TaskExtractionResponse(
        intent=UserIntent.EDIT_TASK,
        is_relevant=True,
        target_search_term="T",
        formatted_task=TaskSchema(deadline=new_date)
    )

    response = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "Fecha:" in response
    assert "->" in response

@pytest.mark.asyncio
async def test_edit_task_no_target(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(
        intent=UserIntent.EDIT_TASK,
        is_relevant=True,
        target_search_term=None
    )
    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "no sé cuál" in resp

def test_get_lists_summary(coordinator, mocker):
    # Empty
    mocker.patch.object(coordinator.task_manager, "get_lists", return_value=[])
    # New behavior: hints at creation instead of just saying "No lists"
    assert "/create_list" in coordinator.get_lists_summary(123)

    # With lists
    l1 = MagicMock(title="L1", owner=MagicMock(telegram_id=123))
    l1.tasks.count.return_value = 5
    mocker.patch.object(coordinator.task_manager, "get_lists", return_value=[l1])

    resp = coordinator.get_lists_summary(123)
    assert "L1" in resp
    assert "5 elementos" in resp
    assert "Propietario" in resp

@pytest.mark.asyncio
async def test_handle_edit_task_with_list_scope(coordinator, mocker):
    """Cover lines 281-285 in coordinator.py: find task scoped to list"""
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))

    # Setup list and task
    mock_list = MagicMock(id=99, title="ScopeList")
    mocker.patch.object(coordinator.task_manager, "find_list_by_name", return_value=mock_list)

    mock_task = MagicMock(id=1, title="T")
    mocker.patch.object(coordinator.task_manager, "find_tasks_by_keyword", return_value=[mock_task])
    mocker.patch.object(coordinator.task_manager, "edit_task", return_value=True)

    extract = TaskExtractionResponse(
        intent=UserIntent.EDIT_TASK,
        is_relevant=True,
        target_search_term="T",
        formatted_task=TaskSchema(list_name="ScopeList", title="NewT")
    )

    await coordinator.handle_message(123, "u", "txt", extractions=[extract])

    # Verify find_tasks was called with list_id=99
    coordinator.task_manager.find_tasks_by_keyword.assert_called_with(123, "T", list_id=99)

@pytest.mark.asyncio
async def test_cancel_all_zero(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(
        intent=UserIntent.CANCEL_TASK,
        is_relevant=True,
        target_search_term="ALL"
    )
    mocker.patch.object(coordinator.task_manager, "delete_all_pending_tasks", return_value=0)
    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "No tienes tareas" in resp

@pytest.mark.asyncio
async def test_task_modification_errors(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    extract = TaskExtractionResponse(intent=UserIntent.CANCEL_TASK, is_relevant=True, target_search_term="Missing")

    # Not found
    mocker.patch.object(coordinator.task_manager, "find_tasks_by_keyword", return_value=[])
    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "No encontré ninguna tarea" in resp

    # Multiple
    mocker.patch.object(coordinator.task_manager, "find_tasks_by_keyword", return_value=[MagicMock(), MagicMock()])
    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "Encontré varias tareas" in resp

@pytest.mark.asyncio
async def test_edit_task_description_status(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))
    original = MagicMock(id=1, title="T", description="Old Desc", status=TaskStatus.PENDING, deadline=None, priority="LOW")
    mocker.patch.object(coordinator.task_manager, "find_tasks_by_keyword", return_value=[original])
    mocker.patch.object(coordinator.task_manager, "edit_task", return_value=True)

    extract = TaskExtractionResponse(
        intent=UserIntent.EDIT_TASK,
        is_relevant=True,
        target_search_term="T",
        formatted_task=TaskSchema(description="New Desc", status=TaskStatus.COMPLETED)
    )

    resp = await coordinator.handle_message(123, "u", "txt", extractions=[extract])
    assert "Descripción actualizada" in resp
    assert "Estado:" in resp

@pytest.mark.asyncio
async def test_get_task_summary_filters(coordinator, mocker):
    mocker.patch.object(coordinator.user_manager, "get_or_create_user", return_value=MagicMock(status=UserStatus.WHITELISTED))

    # Empty with filter
    mocker.patch.object(coordinator.task_manager, "get_pending_tasks", return_value=[])
    resp = coordinator.get_task_summary(123, priority_filter="HIGH")
    assert "Prioridad HIGH" in resp # in filter text
    assert "No tienes tareas" in resp
