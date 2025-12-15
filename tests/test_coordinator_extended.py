
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.services.coordinator import Coordinator
from src.utils.schema import TaskExtractionResponse, UserIntent, TaskSchema, TimeFilter

@pytest.fixture
def coord(mocker):
    # Mock LLM and Managers
    mocker.patch("src.services.coordinator.LLMFactory")
    coord = Coordinator()
    coord.user_manager = MagicMock()
    # Return valid default user
    valid_user = MagicMock()
    valid_user.status = "WHITELISTED"
    coord.user_manager.get_or_create_user.return_value = valid_user

    coord.task_manager = MagicMock()
    coord.llm = MagicMock()
    return coord

@pytest.mark.asyncio
async def test_create_list(coord):
    # Setup Extraction
    ext = TaskExtractionResponse(
        intent=UserIntent.CREATE_LIST,
        is_relevant=True,
        target_search_term="New List"
    )

    # Run
    res = await coord.handle_message(123, "user", "Create list", extractions=[ext])

    # Verify
    coord.task_manager.create_list.assert_called_with(123, "New List")
    assert "creada" in res.lower()

@pytest.mark.asyncio
async def test_share_list_validation(coord):
    # Missing args
    ext = TaskExtractionResponse(intent=UserIntent.SHARE_LIST, is_relevant=True)
    res = await coord.handle_message(123, "user", "Share", extractions=[ext])
    assert "necesito el nombre" in res.lower()

    # List not found
    ext = TaskExtractionResponse(
        intent=UserIntent.SHARE_LIST,
        is_relevant=True,
        target_search_term="Ghost List",
        formatted_task=TaskSchema(title="dummy", shared_with=["@bob"])
    )
    coord.task_manager.find_list_by_name.return_value = None

    res = await coord.handle_message(123, "user", "Share", extractions=[ext])
    assert "no encontré" in res.lower()

@pytest.mark.asyncio
async def test_add_task_duplicate(coord):
    ext = TaskExtractionResponse(
        intent=UserIntent.ADD_TASK,
        is_relevant=True,
        formatted_task=TaskSchema(title="Dup Task")
    )
    # Return None to simulate duplicate
    coord.task_manager.add_task.return_value = None

    res = await coord.handle_message(123, "user", "Add Dup", extractions=[ext])
    assert "ya tienes" in res.lower()

@pytest.mark.asyncio
async def test_join_list_validation(coord):
    # Invalid ID
    ext = TaskExtractionResponse(intent=UserIntent.JOIN_LIST, is_relevant=True, target_search_term="abc")
    res = await coord.handle_message(123, "user", "Join abc", extractions=[ext])
    assert "necesito el id" in res.lower()

@pytest.mark.asyncio
async def test_delete_list_all(coord):
    ext = TaskExtractionResponse(intent=UserIntent.DELETE_LIST, is_relevant=True, target_search_term="ALL")
    coord.task_manager.delete_all_lists.return_value = 5

    res = await coord.handle_message(123, "user", "Del all", extractions=[ext])
    assert "eliminado 5" in res.lower()

@pytest.mark.asyncio
async def test_cancel_task_all(coord):
    ext = TaskExtractionResponse(
        intent=UserIntent.CANCEL_TASK,
        is_relevant=True,
        target_search_term="ALL",
        time_filter=TimeFilter.TODAY
    )
    coord.task_manager.delete_all_pending_tasks.return_value = 3

    res = await coord.handle_message(123, "user", "Del all tasks", extractions=[ext])
    assert "eliminado 3 tareas para hoy" in res

@pytest.mark.asyncio
async def test_edit_task_flow(coord):
    # Task found
    task_mock = MagicMock()
    task_mock.title = "Old Title"
    task_mock.id = 100
    coord.task_manager.find_tasks_by_keyword.return_value = [task_mock]

    ext = TaskExtractionResponse(
        intent=UserIntent.EDIT_TASK,
        is_relevant=True,
        target_search_term="Old",
        formatted_task=TaskSchema(title="New Title")
    )
    coord.task_manager.edit_task.return_value = True

    res = await coord.handle_message(123, "user", "Edit", extractions=[ext])

    coord.task_manager.edit_task.assert_called()
    assert "Actualizada" in res or "Old Title" in res

@pytest.mark.asyncio
async def test_user_not_whitelisted(coord):
    invalid_user = MagicMock()
    invalid_user.status = "PENDING"
    coord.user_manager.get_or_create_user.return_value = invalid_user

    res = await coord.handle_message(123, "user", "Hi")
    assert "pendiente de aprobación" in res
