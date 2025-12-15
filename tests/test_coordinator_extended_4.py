
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
async def test_change_notif_time_invalid(coord):
    # Missing formatted_task
    ext = TaskExtractionResponse(intent=UserIntent.CHANGE_NOTIFICATION_TIME, is_relevant=True)
    res = await coord.handle_message(1, "u", "", extractions=[ext])
    assert "No he entendido a qué hora" in res

    # Missing deadline
    ext2 = TaskExtractionResponse(
        intent=UserIntent.CHANGE_NOTIFICATION_TIME,
        is_relevant=True,
        formatted_task=TaskSchema(title="T") # No deadline
    )
    res = await coord.handle_message(1, "u", "", extractions=[ext2])
    assert "No he entendido a qué hora" in res
