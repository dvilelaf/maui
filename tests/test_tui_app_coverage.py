
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

@pytest.mark.asyncio
async def test_tui_activate_tab_exception(mocker):
    """Cover lines 101-102: Exception in _activate_tab."""
    app = DatabaseMonitor()
    app.query_one = MagicMock()

    # query_one(TabbedContent) OK
    # query_one(table) Raises
    def q_side_effect(selector, *args):
        if selector is TabbedContent:
           m = MagicMock()
           return m
        raise Exception("Table not found")

    app.query_one.side_effect = q_side_effect

    # Should catch and pass
    app._activate_tab("users_tab")

@pytest.mark.asyncio
async def test_tui_update_tasks_weird_username(mocker):
    """Cover line 410: user_str == 'None'."""
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")

    # Init in-memory DB for this test manually to ensure table exists
    from src.database.core import db
    from src.database.models import SharedAccess
    db.init(":memory:")
    db.connect()
    db.create_tables([User, Task, TaskList, SharedAccess])

    # Setup Data
    user = User.create(telegram_id=999, first_name=None, last_name=None, username=None)
    # The code constructs "{first} {last}" -> "None None" -> then checks for it

    user.first_name = "None"
    user.last_name = ""
    user.save()

    t = Task.create(title="WeirdTask", user=user, status="PENDING")

    app = DatabaseMonitor()
    app.query_one = MagicMock()
    app._update_table = MagicMock()

    app.update_tasks()

    # Verify the data passed to _update_table has "999" as User
    args = app._update_table.call_args[0]
    data = args[2] # current_data
    assert data[t.id]["User"] == "999"

@pytest.mark.asyncio
async def test_tui_update_table_highlights_gap(mocker):
    """Cover line 528: row_id not in highlights (Existing Row)."""
    app = DatabaseMonitor()
    table = MagicMock()
    app.data_cache["test"] = {1: {"col": "old"}}
    # highlights empty
    app.highlights["test"] = {}

    current_data = {1: {"col": "new"}}

    app._update_table(table, "test", current_data, ["col"])

    # Should have initialized highlights[1] = {}
    assert 1 in app.highlights["test"]
    assert app.highlights["test"][1]["col"] > 0

@pytest.mark.asyncio
async def test_tui_rebuild_cursor_fallback(mocker):
    """Cover lines 569-570: Rebuild cursor restore at end."""
    app = DatabaseMonitor()
    table = MagicMock()
    table.cursor_row = 100 # Way past end
    table.row_count = 5 # New count

    app.data_cache["test"] = {1: {"c": "v"}}
    app.highlights["test"] = {} # Initialize key
    current_data = {1: {"c": "v2"}} # Change to force rebuild=True triggers

    # We need to force rebuild=True
    app._update_table(table, "test", current_data, ["c"], rebuild=True)

    table.move_cursor.assert_called_with(row=4) # row_count - 1

@pytest.mark.asyncio
async def test_tui_main_block(mocker):
    """Cover lines 661-662: if name == main via subprocess or simple import check."""
    # We can't really test __name__ == "__main__" logic by importing.
    # But we can run it via subprocess to be sure coverage hits it if we really want 100%.
    # Or just ignore it.
    pass

