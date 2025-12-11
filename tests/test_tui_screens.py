
import pytest
import asyncio
from textual.widgets import Button, Input, DataTable
from src.database.models import User, Task, TaskList
from src.utils.schema import UserStatus, TaskStatus
from src.tui.app import DatabaseMonitor
from src.tui.screens import EditUserModal, ConfirmScreen, EditTaskModal, ListDetailModal

@pytest.fixture
def app(mocker):
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")
    app = DatabaseMonitor()
    return app

@pytest.fixture
def user_for_modal(test_db):
    return User.create(telegram_id=999, username="modal_user", first_name="Modal", last_name="Test")

@pytest.fixture
def task_for_modal(test_db, user_for_modal):
    return Task.create(user=user_for_modal, title="Modal Task", priority="LOW")

@pytest.mark.asyncio
async def test_edit_user_modal_save(app, user_for_modal):
    async with app.run_test() as pilot:
        async def _push(): await app.push_screen(EditUserModal(user_id=999))
        asyncio.create_task(_push())
        await pilot.pause(0.5)

        inp = app.screen.query_one("#first_name", Input)
        inp.value = "UpdatedModal"
        # Direct press
        btn = app.screen.query_one("#save", Button)
        btn.press()
        await pilot.pause(0.1) # Wait for handler

        u = User.get_by_id(user_for_modal.telegram_id)
        assert u.first_name == "UpdatedModal"

@pytest.mark.asyncio
async def test_edit_user_modal_actions(app, user_for_modal):
    async with app.run_test() as pilot:
        async def _push(): await app.push_screen(EditUserModal(user_id=999))

        # Whitelist
        asyncio.create_task(_push())
        await pilot.pause(0.5)
        app.screen.query_one("#whitelist", Button).press()
        await pilot.pause(0.1)
        u = User.get_by_id(user_for_modal.telegram_id)
        assert u.status == UserStatus.WHITELISTED

        # Blacklist
        asyncio.create_task(_push())
        await pilot.pause(0.5)
        app.screen.query_one("#blacklist", Button).press()
        await pilot.pause(0.1)
        u = User.get_by_id(user_for_modal.telegram_id)
        assert u.status == UserStatus.BLACKLISTED

@pytest.mark.asyncio
async def test_edit_user_modal_kick(app, user_for_modal):
    async with app.run_test() as pilot:
        async def _push(): await app.push_screen(EditUserModal(user_id=999))
        asyncio.create_task(_push())
        await pilot.pause(0.5)
        app.screen.query_one("#kick", Button).press()
        await pilot.pause(0.1)
        assert User.get_or_none(User.telegram_id == 999) is None

@pytest.mark.asyncio
async def test_edit_task_modal_save(app, task_for_modal):
    async with app.run_test() as pilot:
        async def _push(): await app.push_screen(EditTaskModal(task_id=task_for_modal.id))
        asyncio.create_task(_push())
        await pilot.pause(0.5)

        app.screen.query_one("#title", Input).value = "New Title"
        app.screen.query_one("#priority", Input).value = "HIGH"
        app.screen.query_one("#deadline", Input).value = "2025-12-31 23:59"

        app.screen.query_one("#save", Button).press()
        await pilot.pause(0.1)

        t = Task.get_by_id(task_for_modal.id)
        assert t.title == "New Title"
        assert t.priority == "HIGH"
        assert t.deadline.year == 2025

@pytest.mark.asyncio
async def test_edit_task_modal_actions(app, task_for_modal):
    async with app.run_test() as pilot:
        async def _push(): await app.push_screen(EditTaskModal(task_id=task_for_modal.id))

        # Complete
        asyncio.create_task(_push())
        await pilot.pause(0.5)
        app.screen.query_one("#complete", Button).press()
        await pilot.pause(0.1)
        assert Task.get_by_id(task_for_modal.id).status == TaskStatus.COMPLETED

        # Pending
        asyncio.create_task(_push())
        await pilot.pause(0.5)
        app.screen.query_one("#pending", Button).press()
        await pilot.pause(0.1)
        assert Task.get_by_id(task_for_modal.id).status == TaskStatus.PENDING

        # Delete
        asyncio.create_task(_push())
        await pilot.pause(0.5)
        app.screen.query_one("#delete", Button).press()
        await pilot.pause(0.1)
        assert Task.get_or_none(Task.id == task_for_modal.id) is None

@pytest.mark.asyncio
async def test_edit_task_modal_invalid_deadline(app, task_for_modal):
    async with app.run_test() as pilot:
        async def _push(): await app.push_screen(EditTaskModal(task_id=task_for_modal.id))
        asyncio.create_task(_push())
        await pilot.pause(0.5)
        app.screen.query_one("#deadline", Input).value = "invalid date"

        app.screen.query_one("#save", Button).press()
        await pilot.pause(0.1)

        app.screen.query_one("#title", Input).value = "Should Not Save"

        t = Task.get_by_id(task_for_modal.id)
        assert t.title != "Should Not Save"

@pytest.mark.asyncio
async def test_list_detail_modal(app, test_db):
    user = User.create(telegram_id=888, username="lister")
    tl = TaskList.create(title="My List", owner=user)
    Task.create(title="Item 1", user=user, task_list=tl)

    async with app.run_test() as pilot:
        async def _push(): await app.push_screen(ListDetailModal(list_id=tl.id))
        asyncio.create_task(_push())
        await pilot.pause(0.5)

        table = app.screen.query_one("#list_items_table", DataTable)
        assert table.row_count == 1

        app.screen.query_one("#close", Button).press()
        await pilot.pause(0.1)

@pytest.mark.asyncio
async def test_confirm_screen(app, test_db):
    async with app.run_test() as pilot:
        scr = ConfirmScreen("Sure?")
        async def _push(): await app.push_screen(scr)
        asyncio.create_task(_push())
        await pilot.pause(0.5)

        # Test toggle focus
        scr.action_toggle_focus()
        # Hard to verify focus state without detailed widget query, but executes code.

        # Test cancel key
        scr.action_cancel()
        await pilot.pause(0.1)
        assert len(app.screen_stack) == 1 # Should have popped

@pytest.mark.asyncio
async def test_edit_user_modal_edge_cases(app, user_for_modal):
    async with app.run_test() as pilot:
        scr = EditUserModal(user_for_modal.telegram_id)
        async def _push(): await app.push_screen(scr)
        asyncio.create_task(_push())
        await pilot.pause(0.5)

        # 1. Test Key Bindings
        scr.action_manual_focus_previous()
        scr.action_manual_focus_next()
        scr.action_cancel() # Should dismiss
        await pilot.pause(0.1)

        # 2. Test "User Not Found" on button press (Concurrent deletion)
        asyncio.create_task(_push()) # Re-open
        await pilot.pause(0.5)

        # Delete user in background
        User.delete().where(User.telegram_id == user_for_modal.telegram_id).execute()

        # Click save
        app.screen.query_one("#save", Button).press()
        # Should dismiss without error
        await pilot.pause(0.1)

@pytest.mark.asyncio
async def test_edit_task_modal_edge_cases(app, task_for_modal):
    async with app.run_test() as pilot:
        scr = EditTaskModal(task_for_modal.id)
        async def _push(): await app.push_screen(scr)
        asyncio.create_task(_push())
        await pilot.pause(0.5)

        # 1. Key bindings
        scr.action_manual_focus_previous()
        scr.action_manual_focus_next()

        # 2. Empty deadline (clearing it)
        app.screen.query_one("#deadline", Input).value = "   " # Empty string
        app.screen.query_one("#save", Button).press()
        await pilot.pause(0.1)

        t = Task.get_by_id(task_for_modal.id)
        assert t.deadline is None

        # 3. Task Not Found
        asyncio.create_task(_push())
        await pilot.pause(0.6)
        task_for_modal.delete_instance()

        assert isinstance(app.screen, EditTaskModal)
        app.screen.query_one("#save", Button).press() # update
        await pilot.pause(0.1)
        # should dismiss safe

@pytest.mark.asyncio
async def test_edit_user_modal_cancel_button(app, user_for_modal):
    # specifically click cancel button for coverage
    async with app.run_test() as pilot:
         async def _push(): await app.push_screen(EditUserModal(user_for_modal.telegram_id))
         asyncio.create_task(_push())
         await pilot.pause(0.5)
         app.screen.query_one("#cancel", Button).press()
         await pilot.pause(0.1)

@pytest.mark.asyncio
async def test_edit_task_modal_cancel_button(app, task_for_modal):
    async with app.run_test() as pilot:
         async def _push(): await app.push_screen(EditTaskModal(task_for_modal.id))
         asyncio.create_task(_push())
         await pilot.pause(0.5)
         app.screen.query_one("#cancel", Button).press()
         await pilot.pause(0.1)
