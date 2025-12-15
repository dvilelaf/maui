
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from peewee import OperationalError

from src.migrate_recurrence import migrate
from src.bot.handlers import start_command, handle_admin_action
from src.utils.config import Config
from src.utils.schema import UserStatus

# --- Migration Tests ---

def test_migrate_recurrence_success():
    """Test successful migration adding recurrence column."""
    with patch("src.migrate_recurrence.db") as mock_db:
        mock_db.obj.execute_sql = MagicMock()
        migrate()
        mock_db.obj.execute_sql.assert_called_with(
            "ALTER TABLE task ADD COLUMN recurrence VARCHAR(255) DEFAULT NULL"
        )

def test_migrate_recurrence_duplicate_column():
    """Test migration handling OperationalError 'duplicate column'."""
    with patch("src.migrate_recurrence.db") as mock_db:
        # Simulate OperationalError "duplicate column"
        mock_db.obj.execute_sql.side_effect = OperationalError("duplicate column name")
        # Should not raise
        migrate()

def test_migrate_recurrence_other_operational_error():
    """Test migration handling other OperationalErrors."""
    with patch("src.migrate_recurrence.db") as mock_db:
        mock_db.obj.execute_sql.side_effect = OperationalError("Something else")
        # Should catch and log error
        migrate()

        mock_db.obj.execute_sql.side_effect = Exception("Boom")
        # Should catch and log error
        migrate()

# --- migrate_db Tests ---
from src.migrate_db import migrate as migrate_db_func

def test_migrate_db_no_database():
    """Cover lines 17-19: No database init."""
    with patch("src.migrate_db.db") as mock_db:
        mock_db.obj = None
        migrate_db_func() # Should log error and return

def test_migrate_db_success():
    """Cover lines 24-27, 37-40: Success."""
    with patch("src.migrate_db.db") as mock_db:
        mock_db.obj.execute_sql = MagicMock()
        migrate_db_func()
        assert mock_db.obj.execute_sql.call_count == 2 # Color and Recurrence

def test_migrate_db_duplicate_columns():
    """Cover lines 29-30, 42-43: Duplicate columns."""
    with patch("src.migrate_db.db") as mock_db:
        mock_db.obj.execute_sql.side_effect = OperationalError("duplicate column name")
        migrate_db_func()
        # Should catch and log info

def test_migrate_db_other_operational_error():
    """Cover lines 32, 45: Other OpErrors."""
    with patch("src.migrate_db.db") as mock_db:
        mock_db.obj.execute_sql.side_effect = OperationalError("Disk full")
        migrate_db_func()

def test_migrate_db_general_exception():
    """Cover lines 47-48: General Exception."""
    with patch("src.migrate_db.db") as mock_db:
        # First call succeeds (None), second raises Exception
        mock_db.obj.execute_sql.side_effect = [None, Exception("System Failure")]
        migrate_db_func()

# --- Bot Handler Tests ---

@pytest.mark.asyncio
async def test_start_command_notify_admin_exception(mocker):
    """Cover lines 62-63: Exception when notifying admin."""
    # Setup
    update = MagicMock()
    context = MagicMock()
    user = MagicMock(id=123, username="tester", first_name="Test", last_name="User")
    user.mention_html.return_value = "@test"
    update.effective_user = user
    update.message.reply_text = AsyncMock()


    # Mock Coordinator/User Manager returning PENDING user
    mock_coord = MagicMock()
    mock_user_db = MagicMock(status=UserStatus.PENDING)
    mock_coord.user_manager.get_or_create_user.return_value = mock_user_db

    with patch("src.bot.handlers.get_coordinator", return_value=mock_coord):
        with patch("src.bot.handlers.Config.ADMIN_USER", 999):
             # Mock send_message to RAISE exception
             context.bot.send_message.side_effect = Exception("Telegram API Down")

             await start_command(update, context)

             # usage check
             context.bot.send_message.assert_called_once()
             # Error should be logged but not raised

@pytest.mark.asyncio
async def test_handle_admin_action_notify_user_exception(mocker):
    """Cover lines 228-229: Exception when notifying approved user."""
    # Setup
    update = MagicMock()
    context = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    update.effective_user.id = 999 # is admin

    query.data = "ADMIN_APPROVE_555"
    query.message.text = "Request"

    mock_coord = MagicMock()
    with patch("src.bot.handlers.get_coordinator", return_value=mock_coord):
        with patch("src.bot.handlers.Config.ADMIN_USER", 999):
             # Mock send_message to RAISE exception
             context.bot.send_message.side_effect = Exception("User blocked bot")

             await handle_admin_action(update, context)

             mock_coord.user_manager.update_status.assert_called_with(555, UserStatus.WHITELISTED)
             # Should finish without error
