
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from src.services.scheduler import check_deadlines_job
from src.database.models import Task, User, TaskList, SharedAccess

@pytest.fixture
def mock_context():
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    return context

@pytest.fixture
def mock_task_manager(mocker):
    # Mock the global task_manager instance in scheduler.py
    return mocker.patch("src.services.scheduler.task_manager")

@pytest.mark.asyncio
async def test_check_deadlines_job_shared_list(mock_context, mock_task_manager, mocker):
    # Setup Data
    now = datetime.now()
    deadline = now + timedelta(minutes=30)

    owner = MagicMock(spec=User)
    owner.telegram_id = 111

    member = MagicMock(spec=User)
    member.telegram_id = 999

    task_list = MagicMock(spec=TaskList)
    task_list.id = 123

    task = MagicMock(spec=Task)
    task.id = 1
    task.title = "Shared Task"
    task.deadline = deadline
    task.reminder_sent = False
    task.task_list = task_list
    task.user = owner
    # task.deadline is a real datetime, so .time() works automatically

    # Mock Task.select query result
    # We need to mock the entire chain: Task.select().join().where()
    # Easiest way is to patch Task.select to return a mock that is iterable
    mock_select = MagicMock()
    mock_join = MagicMock()
    mock_where = MagicMock()

    # Iterate over our task
    mock_where.__iter__.return_value = [task]

    mock_join.where.return_value = mock_where
    mock_select.join.return_value = mock_join

    with patch("src.services.scheduler.Task.select", return_value=mock_select):
        # Mock get_list_members to return owner and member
        mock_task_manager.get_list_members.return_value = [owner, member]

        # Run Function
        await check_deadlines_job(mock_context)

        # Verify Notifications
        # Should be called twice: once for owner, once for member
        assert mock_context.bot.send_message.call_count == 2

        # Check calls
        calls = mock_context.bot.send_message.call_args_list
        chat_ids = [call.kwargs['chat_id'] for call in calls]
        assert 111 in chat_ids
        assert 999 in chat_ids

        # Verify reminder_sent updated
        assert task.reminder_sent is True
        task.save.assert_called_once()

@pytest.mark.asyncio
async def test_check_deadlines_job_private_list(mock_context, mock_task_manager):
    # Setup Data
    now = datetime.now()
    deadline = now + timedelta(minutes=30)

    owner = MagicMock(spec=User)
    owner.telegram_id = 555

    task_list = MagicMock(spec=TaskList)
    task_list.id = 456

    task = MagicMock(spec=Task)
    task.id = 2
    task.title = "Private List Task"
    task.deadline = deadline
    task.reminder_sent = False
    task.task_list = task_list # It is in a list
    task.user = owner
    task.user = owner
    # task.deadline is a real datetime

    mock_select = MagicMock()
    mock_join = MagicMock()
    mock_where = MagicMock()
    mock_where.__iter__.return_value = [task]
    mock_join.where.return_value = mock_where
    mock_select.join.return_value = mock_join

    with patch("src.services.scheduler.Task.select", return_value=mock_select):
        # Mock members returns just owner
        mock_task_manager.get_list_members.return_value = [owner]

        await check_deadlines_job(mock_context)

        # Verify
        assert mock_context.bot.send_message.call_count == 1
        assert mock_context.bot.send_message.call_args.kwargs['chat_id'] == 555
        assert task.reminder_sent is True

