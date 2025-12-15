import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, time
from src.services.llm_provider import LLMProvider
from src.services.scheduler import send_daily_summary, check_deadlines_job
from src.services.coordinator import Coordinator
from src.utils.schema import UserIntent, TaskExtractionResponse
from src.database.models import Task

# --- LLM Provider Tests ---

def test_llm_provider_abstract():
    """Cover line 15 in llm_provider.py: abstract method pass"""
    class Concrete(LLMProvider):
        def process_input(self, i, m="t"):
            return None

    # Just instantiation to verify inheritance works and abstract method exists
    c = Concrete()
    c.process_input("test")

# --- Scheduler Tests ---

@pytest.mark.asyncio
async def test_send_daily_summary_exec():
    """Cover lines 49-50 in scheduler.py"""
    context = MagicMock()

    with patch('src.services.scheduler._send_summary_helper', new_callable=AsyncMock) as mock_helper:
        await send_daily_summary(context)
        mock_helper.assert_called_once()

@pytest.mark.asyncio
async def test_check_deadlines_skip_midnight():
    """Cover line 78 in scheduler.py: skip midnight deadlines"""
    context = MagicMock()

    # Mock Task with deadline at midnight
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    task = MagicMock(spec=Task)
    # Use real datetime.time() behavior, don't mock .time.return_value on a real datetime
    task.deadline = midnight

    with patch('src.services.scheduler.Task.select') as mock_select:
        # Return our task
        mock_select.return_value.join.return_value.where.return_value = [task]

        await check_deadlines_job(context)

        # Ensure we didn't send a message (continue hit)
        context.bot.send_message.assert_not_called()

# --- Coordinator Tests ---

@pytest.mark.asyncio
async def test_coordinator_list_not_found_race_condition():
    """Cover lines 281-289 in coordinator.py: find_list_by_name returns None"""
    coord = Coordinator()
    # Remove spec= to avoid attribute errors if pydantic field not found in mock spec
    extraction = MagicMock()
    extraction.intent = UserIntent.EDIT_TASK
    extraction.target_search_term = "Task"
    extraction.formatted_task.list_name = "Missing List"

    # find_list_by_name returns None (simulate race condition or bad fuzzy match)
    with patch.object(coord.task_manager, 'find_list_by_name', return_value=None):
         result = await coord._process_single_intent(1, extraction)
         assert "No encontré ninguna lista" in result

@pytest.mark.asyncio
async def test_coordinator_edit_failure():
    """Cover line 371 in coordinator.py: edit_task returns False"""
    coord = Coordinator()
    extraction = MagicMock()
    extraction.intent = UserIntent.EDIT_TASK
    extraction.target_search_term = "Task"
    extraction.formatted_task.list_name = None
    extraction.formatted_task.model_dump.return_value = {} # No changes

    # find_tasks returns 1 candidate
    candidate = MagicMock()
    candidate.id = 1
    candidate.title = "T"

    with patch.object(coord.task_manager, 'find_tasks_by_keyword', return_value=[candidate]):
         with patch.object(coord.task_manager, 'edit_task', return_value=False):
              result = await coord._process_single_intent(1, extraction)
              assert "No se pudo actualizar" in result

def test_get_lists_summary_empty_case_hint():
    """Cover line 431 in coordinator.py: empty lists hint"""
    coord = Coordinator()
    # Mock get_lists returning empty list
    with patch.object(coord.task_manager, 'get_lists', return_value=[]):
        summary = coord.get_lists_summary(1)
        assert "create_list" in summary

def test_get_lists_summary_status_icon():
    """Cover lines 423-424 in coordinator.py"""
    coord = Coordinator()
    mock_list = MagicMock()
    mock_list.owner.telegram_id = 1
    mock_list.title = "L"
    mock_list.tasks.count.return_value = 1

    t1 = MagicMock()
    t1.status = "COMPLETED"
    t1.title = "Done"

    mock_list.tasks.exists.return_value = True
    mock_list.tasks.__iter__.return_value = [t1]

    with patch.object(coord.task_manager, 'get_lists', return_value=[mock_list]):
        summary = coord.get_lists_summary(1)
        assert "✅" in summary
