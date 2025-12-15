
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.services.coordinator import Coordinator
from src.utils.schema import TaskExtractionResponse, UserIntent, TaskSchema

@pytest.fixture
def coord(mocker):
    mocker.patch("src.services.coordinator.LLMFactory")
    c = Coordinator()
    c.user_manager = MagicMock()
    c.user_manager.get_or_create_user.return_value = MagicMock(status="WHITELISTED")
    c.task_manager = MagicMock()
    # Async methods
    c.task_manager.respond_to_invite = AsyncMock()
    c.task_manager.leave_list = AsyncMock()
    c.llm = MagicMock()
    return c

@pytest.mark.asyncio
async def test_leave_list_empty(coord):
    ext = TaskExtractionResponse(intent=UserIntent.LEAVE_LIST, is_relevant=True, target_search_term="")
    res = await coord.handle_message(1, "u", "", extractions=[ext])
    assert "Dime qué lista" in res

@pytest.mark.asyncio
async def test_leave_list_not_found(coord):
    ext = TaskExtractionResponse(intent=UserIntent.LEAVE_LIST, is_relevant=True, target_search_term="Ghost")

    coord.task_manager.find_list_by_name.return_value = None

    res = await coord.handle_message(1, "u", "", extractions=[ext])
    assert "No encontré" in res

@pytest.mark.asyncio
async def test_delete_list_empty(coord):
    ext = TaskExtractionResponse(intent=UserIntent.DELETE_LIST, is_relevant=True, target_search_term="")
    res = await coord.handle_message(1, "u", "", extractions=[ext])
    assert "Dime qué lista" in res

@pytest.mark.asyncio
async def test_delete_all_empty(coord):
    ext = TaskExtractionResponse(intent=UserIntent.DELETE_LIST, is_relevant=True, target_search_term="ALL")
    coord.task_manager.delete_all_lists.return_value = 0
    res = await coord.handle_message(1, "u", "", extractions=[ext])
    assert "No tienes listas" in res

@pytest.mark.asyncio
async def test_delete_list_not_found(coord):
    ext = TaskExtractionResponse(intent=UserIntent.DELETE_LIST, is_relevant=True, target_search_term="Ghost")
    coord.task_manager.find_list_by_name.return_value = None
    res = await coord.handle_message(1, "u", "", extractions=[ext])
    assert "No encontré" in res

@pytest.mark.asyncio
async def test_change_notif_time_fail(coord):
    from datetime import datetime
    ext = TaskExtractionResponse(
        intent=UserIntent.CHANGE_NOTIFICATION_TIME,
        is_relevant=True,
        formatted_task=TaskSchema(title="dummy", deadline=datetime(2024,1,1,10,0))
    )
    coord.user_manager.update_notification_time.return_value = False
    res = await coord.handle_message(1, "u", "", extractions=[ext])
    assert "Hubo un error" in res
