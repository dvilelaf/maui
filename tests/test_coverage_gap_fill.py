
import pytest
from unittest.mock import MagicMock, patch, ANY, AsyncMock
from src.tui.app import DatabaseMonitor
from src.database.models import User, Task, TaskList
from src.utils.schema import TaskStatus
import time

@pytest.mark.asyncio
async def test_app_update_tasks_edge_cases(mocker):
    # Test update_tasks with specific user data scenarios
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")
    app = DatabaseMonitor()

    # ONE: "None None" -> telegram_id (Line 412)
    mock_task_1 = MagicMock(spec=Task)
    mock_task_1.id = 1
    mock_task_1.title = "Task 1"
    mock_task_1.priority = "LOW"
    mock_task_1.deadline = None
    mock_task_1.status = TaskStatus.PENDING
    mock_task_1.user = MagicMock(spec=User)
    mock_task_1.user.username = None
    mock_task_1.user.first_name = None
    mock_task_1.user.last_name = None
    mock_task_1.user.telegram_id = 1000

    # TWO: "None" -> telegram_id (Line 415)
    # user_str = f"{t.user.first_name} {t.user.last_name}" -> "None "
    # strip() -> "None"
    mock_task_2 = MagicMock(spec=Task)
    mock_task_2.id = 2
    mock_task_2.title = "Task 2"
    mock_task_2.priority = "HIGH"
    mock_task_2.deadline = None
    mock_task_2.status = TaskStatus.PENDING
    mock_task_2.user = MagicMock(spec=User)
    mock_task_2.user.username = None
    mock_task_2.user.first_name = "None"
    mock_task_2.user.last_name = ""
    mock_task_2.user.telegram_id = 2000

    # Mock Select Query
    mock_query = MagicMock()
    mock_query.__iter__.return_value = [mock_task_1, mock_task_2]

    mocker.patch("src.database.models.Task.select").return_value.join.return_value.where.return_value = mock_query

    # Mock query_one to return table
    mock_table = MagicMock()
    app.query_one = MagicMock(return_value=mock_table)
    app.data_cache = {"users": {}, "tasks": {}, "lists": {}}
    app.highlights = {"users": {}, "tasks": {}, "lists": {}}

    # Run update
    app.update_tasks()

    # Verify proper string formatting happened (checking args passed to _update_table indirectly)
    # Check cache update
    assert 1 in app.data_cache["tasks"]
    assert app.data_cache["tasks"][1]["User"] == "1000"

    assert 2 in app.data_cache["tasks"]
    assert app.data_cache["tasks"][2]["User"] == "2000"

@pytest.mark.asyncio
async def test_update_table_highlight_logic(mocker):
    mocker.patch("src.tui.app.DatabaseMonitor.init_db")
    app = DatabaseMonitor()
    app.is_first_refresh = False # Enable highlights

    table = MagicMock()
    table.columns.keys.return_value = ["Col1"]
    # Ensure get_row_index succeeds for "existing" checks
    table.get_row_index.return_value = 0

    app.data_cache["test"] = {}
    app.highlights["test"] = {}

    # 1. New Row
    data_1 = {1: {"Col1": "Val1"}}
    app._update_table(table, "test", data_1, ["Col1"])

    # Check highlight set
    assert 1 in app.highlights["test"]
    assert "Col1" in app.highlights["test"][1]

    # 2. Existing valid row in cache, BUT missing from highlights (Line 530)
    # Manually corrupt state:
    app.data_cache["test"][2] = {"Col1": "Old"}
    # Row 2 is in cache, but NOT in highlights dict

    data_2 = {2: {"Col1": "New"}}
    app._update_table(table, "test", data_2, ["Col1"])

    # Should have re-created highlight entry (line 530 hit)
    assert 2 in app.highlights["test"]
    assert "Col1" in app.highlights["test"][2]

    # 3. Update Row (Change value)
    data_2 = {1: {"Col1": "Val2"}}
    time.sleep(0.01) # ensure ts diff

    app._update_table(table, "test", data_2, ["Col1"])

    # Should update cell
    table.update_cell.assert_called()

    # 4. No Change, but highlight active (should refresh to check expiry)
    # We rely on timestamp.
    app._update_table(table, "test", data_2, ["Col1"])

    # 5. Highlight Expired
    # Manually set old timestamp
    app.highlights["test"][1]["Col1"] = time.time() - 10.0
    app._update_table(table, "test", data_2, ["Col1"])

    # Should clean up highlight
    assert "Col1" not in app.highlights["test"][1]

@pytest.mark.asyncio
async def test_resolve_user_edge(test_db):
    from src.database.access import resolve_user

    # Test valid ID string
    u = User.create(telegram_id=555, username="num_user")
    assert resolve_user("555") == u

    # Test non-existent ID
    assert resolve_user("556") is None

    # Test username without @
    assert resolve_user("num_user") == u
    assert resolve_user("@num_user") == u

@pytest.mark.asyncio
async def test_share_list_fuzzy_fail(test_db, mocker):
    from src.database.access import TaskManager
    mocker.patch("src.database.access.notify_user", new_callable=AsyncMock)

    # Create no users
    tl = TaskList.create(title="MyList", owner=User.create(telegram_id=1))

    success, msg = await TaskManager.share_list(tl.id, "NonExistent")
    assert not success
    assert "no encontrado" in msg

@pytest.mark.asyncio
async def test_share_list_complex(test_db, mocker):
    from src.database.access import TaskManager
    mocker.patch("src.database.access.notify_user", new_callable=AsyncMock)

    owner = User.create(telegram_id=3000)
    tl = TaskList.create(title="ShareComplex", owner=owner)

    # Case 1: Multiple candidates, but 1 exact First Name (Line 333)
    u1 = User.create(telegram_id=3001, first_name="John", username="u1")
    u2 = User.create(telegram_id=3002, first_name="Johnny", username="u2")

    # Search "John" matches both fuzzy
    success, msg = await TaskManager.share_list(tl.id, "John")
    assert success
    assert "u1" in msg or "John" in msg

    # Case 2: Many candidates (>3) (Line 338)
    User.create(telegram_id=3003, first_name="Alex A", username="a3")
    User.create(telegram_id=3004, first_name="Alex B", username="a4")
    User.create(telegram_id=3005, first_name="Alex C", username="a5")
    User.create(telegram_id=3006, first_name="Alex D", username="a6")

    success, msg = await TaskManager.share_list(tl.id, "Alex")
    assert not success
    assert "..." in msg

@pytest.mark.asyncio
async def test_find_list_by_name_coverage(test_db):
    from src.database.access import TaskManager, SharedAccess

    owner = User.create(telegram_id=4000)

    # Setup for line 402 (Shared list found)
    other = User.create(telegram_id=4001)
    tl_shared = TaskList.create(title="MyShared", owner=other)
    SharedAccess.create(user=owner, task_list=tl_shared, status="ACCEPTED")

    # Search "MyShared" -> Should hit DB search for shared (Line 402)
    # The first query checks OWNED.
    # The second query checks SHARED.
    res = TaskManager.find_list_by_name(4000, "MyShared")
    assert res.id == tl_shared.id

    # Setup for 422 (Reverse search exact)
    # create list that owned but DB search case sensitive? No, DB search uses contains.
    # We want to hit the python-side loop.
    # find_list_by_name logic:
    # 1. DB search owned (contains)
    # 2. DB search shared (contains)
    # 3. Python loop reverse search.
    # To hit 3, 1 and 2 must fail.
    # But 1 and 2 use contains.
    # Logic in 3: "clean_name == title_norm".
    # e.g. List="Grocery", Query="Grocery list" -> clean="grocery"
    # DB search "Grocery" contains "Grocery list"? No.
    # So 1/2 fail.
    # Python loop: title "Grocery" == "Grocery" (clean).

    tl_loop = TaskList.create(title="Grocery", owner=owner)
    res = TaskManager.find_list_by_name(4000, "Grocery list")
    assert res.id == tl_loop.id

    # Setup for 427 (Query inside title)
    # Query="roce" -> DB contains finds it usually ("Grocery" contains "roce").
    # We need a case where DB fails but python succeeds?
    # Maybe Stopwords?
    # Query="la Grocery" -> clean="grocery".
    # DB: "Grocery" contains "la Grocery"? No.
    # Python: "Grocery" in "grocery"? Yes.

@pytest.mark.asyncio
async def test_add_task_list_not_found(test_db):
    from src.database.access import TaskManager
    from src.utils.schema import TaskSchema

    # Hit line 141 (pass when list not found)
    u = User.create(telegram_id=5000)
    ts = TaskSchema(title="T", list_name="NonExistentList")

    t = TaskManager.add_task(5000, ts)
    assert t.task_list is None


