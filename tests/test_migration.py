
import pytest
from unittest.mock import MagicMock, patch
from peewee import OperationalError
from src.migrate_db import migrate

def test_migrate_success():
    with patch("src.migrate_db.db") as mock_db_wrapper:
        mock_database = MagicMock()
        mock_db_wrapper.obj = mock_database

        migrate()

        # Verify calls
        # 1. Color column
        # 2. Recurrence column
        assert mock_database.execute_sql.call_count == 2
        mock_database.execute_sql.assert_any_call("ALTER TABLE tasklist ADD COLUMN color VARCHAR(255) DEFAULT '#ffffff'")
        mock_database.execute_sql.assert_any_call("ALTER TABLE task ADD COLUMN recurrence VARCHAR(255) DEFAULT NULL")

def test_migrate_duplicate_column():
    with patch("src.migrate_db.db") as mock_db_wrapper:
        mock_database = MagicMock()
        mock_db_wrapper.obj = mock_database

        # Simulate "duplicate column" error
        mock_database.execute_sql.side_effect = OperationalError("duplicate column name: color")

        migrate()

        # Should not raise
        assert mock_database.execute_sql.call_count >= 1

def test_migrate_db_not_initialized():
    with patch("src.migrate_db.db") as mock_db_wrapper:
        mock_db_wrapper.obj = None

        # Should return early and log error
        with patch("src.migrate_db.logger") as mock_logger:
            migrate()
            mock_logger.error.assert_called_with("Database not initialized! Cannot migrate.")
