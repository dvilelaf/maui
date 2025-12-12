
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta
from src.services.scheduler import send_weekly_summary, send_pending_alert, check_deadlines_job
from src.database.models import User, Task
from src.database.repositories.task_repository import TaskManager
from src.database.repositories.user_repository import UserManager
from src.utils.schema import TaskSchema, TaskStatus

@pytest.fixture
def mock_context(mocker):
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    return context

@pytest.fixture
def user_with_tasks(test_db):
    user = UserManager.get_or_create_user(111, "scheduler_user", "Test", "User")
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Task 1"))
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Task 2", deadline=datetime.now() + timedelta(days=2)))
    return user

@pytest.mark.asyncio
async def test_send_weekly_summary(mock_context, user_with_tasks):
    await send_weekly_summary(mock_context)

    # Should send message to user 111
    assert mock_context.bot.send_message.call_count == 1
    args = mock_context.bot.send_message.call_args
    assert args.kwargs['chat_id'] == 111
    assert "Resumen Semanal" in args.kwargs['text']
    assert "Task 1" in args.kwargs['text']

@pytest.mark.asyncio
async def test_send_weekly_summary_no_tasks(mock_context, test_db):
    UserManager.get_or_create_user(222, "empty_user")
    await send_weekly_summary(mock_context)
    # No message sent
    mock_context.bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_send_pending_alert(mock_context, user_with_tasks):
    await send_pending_alert(mock_context)

    assert mock_context.bot.send_message.call_count == 1
    args = mock_context.bot.send_message.call_args
    assert "Tienes tareas pendientes" in args.kwargs['text']

@pytest.mark.asyncio
async def test_check_deadlines_job(mock_context, user_with_tasks):
    # Add a task expiring in 30 mins (within 1 hour threshold)
    expiring_soon = TaskSchema(
        title="Urgent Task",
        deadline=datetime.now() + timedelta(minutes=30)
    )
    t = TaskManager.add_task(user_with_tasks.telegram_id, expiring_soon)

    # Add task expiring in 2 hours (outside threshold)
    not_expiring = TaskSchema(
        title="Later Task",
        deadline=datetime.now() + timedelta(hours=2)
    )
    TaskManager.add_task(user_with_tasks.telegram_id, not_expiring)

    await check_deadlines_job(mock_context)

    # Should alert only for Urgent Task
    assert mock_context.bot.send_message.call_count == 1
    args = mock_context.bot.send_message.call_args
    assert "Urgent Task" in args.kwargs['text']

    # Verify DB update
    t_db = Task.get_by_id(t.id)
    assert t_db.reminder_sent is True

@pytest.mark.asyncio
async def test_check_deadlines_already_sent(mock_context, user_with_tasks):
    # Task expiring soon but already reminded
    t = TaskManager.add_task(user_with_tasks.telegram_id, TaskSchema(
        title="Reminded Task",
        deadline=datetime.now() + timedelta(minutes=10)
    ))
    t.reminder_sent = True
    t.save()

    await check_deadlines_job(mock_context)
    mock_context.bot.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_send_weekly_summary_error(mock_context, user_with_tasks):
    # Mock send_message to raise exception
    mock_context.bot.send_message.side_effect = Exception("Telegram Error")

    # Should not raise exception (caught and logged)
    await send_weekly_summary(mock_context)
    assert mock_context.bot.send_message.called

@pytest.mark.asyncio
async def test_send_pending_alert_error(mock_context, user_with_tasks):
    mock_context.bot.send_message.side_effect = Exception("Telegram Error")
    await send_pending_alert(mock_context)
    assert mock_context.bot.send_message.called

@pytest.mark.asyncio
async def test_check_deadlines_job_error(mock_context, user_with_tasks):
    # Add pending task to trigger send attempt
    t = TaskManager.add_task(user_with_tasks.telegram_id, TaskSchema(
        title="Urgent",
        deadline=datetime.now() + timedelta(minutes=30)
    ))

    mock_context.bot.send_message.side_effect = Exception("Telegram Error")

    await check_deadlines_job(mock_context)

    # Verify reminder_sent is NOT updated on failure?
    # Logic:
    # try: await send...; task.reminder_sent = True; task.save() except: log
    # So if send fails, reminder_sent remains False (default).

    t_db = Task.get_by_id(t.id)
    assert t_db.reminder_sent is False
