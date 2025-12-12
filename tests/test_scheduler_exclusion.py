
import pytest
from unittest.mock import AsyncMock, MagicMock, ANY
from src.services.scheduler import check_deadlines_job
from src.database.models import Task, User, TaskList
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_check_deadlines_excludes_lists(test_db, mocker):
    # Setup context
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    # Create User
    user = User.create(telegram_id=123456789, first_name="TestUser")

    now = datetime.now()
    soon = now + timedelta(minutes=30)

    # Task 1: General task (Should trigger reminder)
    t1 = Task.create(
        user=user,
        title="General Task",
        status="PENDING",
        deadline=soon,
        reminder_sent=False,
        task_list=None
    )

    # Task 2: List task (Should NOT trigger reminder)
    # Create list first
    tl = TaskList.create(title="Shopping", owner=user)
    t2 = Task.create(
        user=user,
        title="Buy Bread",
        status="PENDING",
        deadline=soon, # Same deadline
        reminder_sent=False,
        task_list=tl
    )

    # Run job
    await check_deadlines_job(context)

    # Verification
    # Should have sent exactly ONE message (for t1)
    assert context.bot.send_message.call_count == 1

    # Verify call args to ensure it was t1
    args, kwargs = context.bot.send_message.call_args
    assert "General Task" in kwargs['text']
    assert "Buy Bread" not in kwargs['text']

    # Verify DB state
    t1_refresh = Task.get_by_id(t1.id)
    t2_refresh = Task.get_by_id(t2.id)

    assert t1_refresh.reminder_sent is True
    assert t2_refresh.reminder_sent is False
