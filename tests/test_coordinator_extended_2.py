
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.services.coordinator import Coordinator
from src.utils.schema import TaskExtractionResponse, UserIntent, TaskSchema

@pytest.fixture
def coord(mocker):
    mocker.patch("src.services.coordinator.LLMFactory")
    c = Coordinator()
    c.user_manager = MagicMock()
    valid_user = MagicMock()
    valid_user.status = "WHITELISTED"
    c.user_manager.get_or_create_user.return_value = valid_user
    c.task_manager = MagicMock()
    # Configure async methods
    c.task_manager.respond_to_invite = AsyncMock()
    c.task_manager.leave_list = AsyncMock()
    c.task_manager.share_list = AsyncMock() # Used in other tests?
    c.llm = MagicMock()
    return c

@pytest.mark.asyncio
async def test_join_list_success(coord):
    ext = TaskExtractionResponse(
        intent=UserIntent.JOIN_LIST, is_relevant=True, target_search_term="10"
    )
    coord.task_manager.respond_to_invite.return_value = (True, "Unido")

    res = await coord.handle_message(123, "u", "join 10", extractions=[ext])
    assert "✅ Unido" in res

@pytest.mark.asyncio
async def test_leave_list_by_id(coord):
    ext = TaskExtractionResponse(
        intent=UserIntent.LEAVE_LIST, is_relevant=True, target_search_term="10"
    )
    coord.task_manager.leave_list.return_value = (True, "Salido")

    res = await coord.handle_message(123, "u", "leave 10", extractions=[ext])
    assert "✅ Salido" in res

@pytest.mark.asyncio
async def test_leave_list_by_name(coord):
    ext = TaskExtractionResponse(
        intent=UserIntent.LEAVE_LIST, is_relevant=True, target_search_term="MyList"
    )
    # Mock finding list
    mock_list = MagicMock()
    mock_list.id = 55
    coord.task_manager.find_list_by_name.return_value = mock_list
    coord.task_manager.leave_list.return_value = (True, "Salido")

    res = await coord.handle_message(123, "u", "leave MyList", extractions=[ext])
    coord.task_manager.find_list_by_name.assert_called_with(123, "MyList")
    coord.task_manager.leave_list.assert_called_with(123, 55)
    assert "✅ Salido" in res

@pytest.mark.asyncio
async def test_delete_list_specific_success(coord):
    ext = TaskExtractionResponse(
        intent=UserIntent.DELETE_LIST, is_relevant=True, target_search_term="OldList"
    )
    mock_list = MagicMock()
    mock_list.id = 66
    mock_list.title = "OldList"
    coord.task_manager.find_list_by_name.return_value = mock_list
    coord.task_manager.delete_list.return_value = True

    res = await coord.handle_message(123, "u", "del OldList", extractions=[ext])
    assert "eliminada" in res or "Deleted" in res # Function format_list_deleted used

@pytest.mark.asyncio
async def test_delete_list_specific_fail(coord):
    ext = TaskExtractionResponse(
        intent=UserIntent.DELETE_LIST, is_relevant=True, target_search_term="OldList"
    )
    mock_list = MagicMock()
    mock_list.id = 66
    coord.task_manager.find_list_by_name.return_value = mock_list
    coord.task_manager.delete_list.return_value = False

    res = await coord.handle_message(123, "u", "del OldList", extractions=[ext])
    assert "No se pudo" in res

@pytest.mark.asyncio
async def test_change_notif_time_success(coord):
    from datetime import datetime
    ext = TaskExtractionResponse(
        intent=UserIntent.CHANGE_NOTIFICATION_TIME,
        is_relevant=True,
        formatted_task=TaskSchema(title="dummy", deadline=datetime(2024,1,1,9,30))
    )
    coord.user_manager.update_notification_time.return_value = True

    res = await coord.handle_message(123, "u", "Time 9:30", extractions=[ext])
    assert "actualizada" in res
