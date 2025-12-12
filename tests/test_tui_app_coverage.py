
import pytest
from textual.widgets import DataTable, TabbedContent
from textual.coordinate import Coordinate
from unittest.mock import MagicMock
from src.tui.app import DatabaseMonitor
from src.database.models import User, Task, TaskList


@pytest.mark.asyncio
async def test_tui_delete_edge_cases_mocked(test_db, mocker):
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")
    app = DatabaseMonitor()

    # We can't easily pilot these specific failures, so we use direct method calls with mocked query_one
    # We need to ensure logic doesn't crash accessing app internals before mount?
    # action_delete uses self.query_one.

    app.query_one = MagicMock()
    app.notify = MagicMock()
    app.push_screen = MagicMock()

    # Case 1: No active tab (line 110)
    # app.query_one(TabbedContent).active -> None
    tab_mock = MagicMock()
    tab_mock.active = None
    app.query_one.return_value = tab_mock

    app.action_delete()
    # Should return early

    # Case 2: Table Lookup Exception (lines 115-116)
    # query_one(TabbedContent) OK, but query_one(table_id) Fails
    tab_mock.active = "users_tab"

    def q_side_effect(selector, *args):
        if selector is TabbedContent:
            return tab_mock
        if "table" in str(selector):
            raise Exception("Table fail")
        return MagicMock() # default

    app.query_one.side_effect = q_side_effect
    app.action_delete()
    # Should catch and return

    # Case 3: Cursor Row None (Lines 121-122)
    # Table found, but cursor_row is None
    table_mock = MagicMock()
    table_mock.cursor_row = None

    def q_side_effect_3(selector, *args):
        if selector is TabbedContent:
            return tab_mock
        if "table" in str(selector):
            return table_mock
        return MagicMock()

    app.query_one.side_effect = q_side_effect_3
    app.action_delete()
    app.notify.assert_called_with("No item selected.")

    # Case 4: Exception getting key (143-145)
    table_mock.cursor_row = 0
    table_mock.coordinate_to_cell_key.side_effect = Exception("Key Error")
    app.action_delete()
    app.notify.assert_called_with("Could not determine selected item ID.")

    # Case 5: Row Key None/Empty (148)
    table_mock.coordinate_to_cell_key.side_effect = None
    table_mock.coordinate_to_cell_key.return_value.row_key.value = ""
    app.action_delete()
    # returns

    # Case 6: Exception getting item name (164-165) and Lists tab
    # We need a valid key to proceed to name resolution
    table_mock.coordinate_to_cell_key.return_value.row_key.value = "999"

    # Fail User lookup
    # Mock active tab to specific
    # Mock active tab to specific
    tab_mock.active = "users_tab"
    mocker.patch("src.database.models.User.get_by_id", side_effect=Exception("DB Fail"))
    app.action_delete()
    # Should pass exception and show confirm screen with fallback name "999"
    app.push_screen.assert_called()
    args = app.push_screen.call_args[0]
    assert "999" in args[0].message

@pytest.mark.asyncio
async def test_tui_tab_wrapping(test_db, mocker):
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")
    app = DatabaseMonitor()
    async with app.run_test() as pilot:
        # Default is users_tab (idx 0)

        # Prev tab -> Should go to last (lists_tab)
        app.action_previous_tab()
        assert app.query_one(TabbedContent).active == "lists_tab"

        # Next tab -> Should go to users_tab
        app.action_next_tab()
        assert app.query_one(TabbedContent).active == "users_tab"

        # Next x2 -> tasks, lists
        app.action_next_tab()
        assert app.query_one(TabbedContent).active == "tasks_tab"

@pytest.mark.asyncio
async def test_tui_list_delete_formatting(test_db, mocker):
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")
    # Setup list
    user = User.create(telegram_id=1, first_name="Owner", status="APPROVED")
    tlist = TaskList.create(title="DeleteMeList", owner=user)

    app = DatabaseMonitor()
    async with app.run_test() as pilot:
        # Switch to lists tab
        app.action_previous_tab() # Goes to last (lists)
        assert app.query_one(TabbedContent).active == "lists_tab"

        # Wait for data
        app.refresh_data()
        table = app.query_one("#lists_table", DataTable)
        table.move_cursor(row=0)

        # Trigger delete to hit lines 161-165
        await pilot.press("d")

        # Check confirmation message
        assert len(app.screen_stack) > 1
        msg = app.screen_stack[-1].message
        assert "Delete List" in msg or "List" in msg
        assert "DeleteMeList" in msg

@pytest.mark.asyncio
async def test_tui_row_selection_coverage(test_db, mocker):
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")
    app = DatabaseMonitor()

    # Mock push_screen to verify calls
    mocker.patch.object(app, 'push_screen')

    # Since we don't run app, we simulate the handler directly
    # Mock Event
    table = MagicMock()
    table.id = "users_table"

    from textual.widgets import DataTable
    # Mock the RowSelected event structure
    event = MagicMock()
    event.control = table
    event.row_key.value = "1"

    app.on_data_table_row_selected(event)

    # Check if EditUserModal was pushed
    assert app.push_screen.call_count == 1
    args, _ = app.push_screen.call_args
    from src.tui.screens import EditUserModal
    assert isinstance(args[0], EditUserModal)
    assert args[0].user_id == 1

@pytest.mark.asyncio
async def test_tui_perform_delete_cancellation(test_db, mocker):
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")
    app = DatabaseMonitor()
    app.notify = MagicMock()

    # confirmed=False
    app.perform_delete(False, "users", 1)

    # Should just return, no notify
    app.notify.assert_not_called()
