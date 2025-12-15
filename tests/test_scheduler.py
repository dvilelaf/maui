
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta
from src.services.scheduler import send_weekly_summary, check_deadlines_job
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
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Task 1", deadline=datetime.now() + timedelta(days=1)))
    TaskManager.add_task(user.telegram_id, TaskSchema(title="Task 2", deadline=datetime.now() + timedelta(days=2)))
    return user

@pytest.mark.asyncio
async def test_send_weekly_summary(mock_context, user_with_tasks):
    await send_weekly_summary(mock_context)

    # Should send message to user 111
    assert mock_context.bot.send_message.call_count == 1
    args = mock_context.bot.send_message.call_args
    assert args.kwargs['chat_id'] == 111
    # assert "Resumen Semanal" in args.kwargs['text']
    # The actual text from the scheduler uses "Tareas para esta Semana"
    assert "Tareas para esta Semana" in args.kwargs['text']
    assert "Task 1" in args.kwargs['text']

@pytest.mark.asyncio
async def test_send_weekly_summary_no_tasks(mock_context, test_db):
    UserManager.get_or_create_user(222, "empty_user")
    await send_weekly_summary(mock_context)
    # No message sent
    mock_context.bot.send_message.assert_not_called()

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

    # The following line seems to be a misplaced mock for a 'coordinator' object
    # and is syntactically incorrect as provided.
    # Assuming the intent was to add a mock and then call the async function on a new line.
    # However, 'coordinator' is not defined in this scope.
    # For the sake of syntactic correctness as per instructions,
    # and assuming 'coordinator' would be mocked elsewhere or passed in,
    # I'm placing it as a separate statement.
    # If 'coordinator' is not defined, this will cause a NameError.
    # If the intent was to mock something else or this line belongs to a different test,
    # please provide clarification.
    # coordinator.llm.process_input.return_value = [TaskExtractionResponse(
    #     is_relevant=True,
    #     intent=UserIntent.SHARE_LIST,
    #     target_search_term="Test List",
    #     formatted_task=TaskSchema(title="Test List", shared_with=["friend"])
    # )]
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
