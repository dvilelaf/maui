
import pytest
from unittest.mock import patch, MagicMock
from src.database.repositories.task_repository import TaskManager
from src.database.models import TaskList

def test_repo_save_exceptions():
    # Mock finding a list, but failing on save
    with patch("src.database.repositories.task_repository.TaskList.get_by_id") as mock_get:
        mock_lst = MagicMock()
        mock_lst.owner_id = 1
        # Mock save to raise exception
        mock_lst.save.side_effect = Exception("Save Error")
        mock_get.return_value = mock_lst

        # Trigger edit_list -> calls save
        res = TaskManager.edit_list(1, 99, "New Name")
        assert res is False

        # Trigger edit_list_color -> calls save
        res = TaskManager.edit_list_color(1, 99, "#000")
        assert res is False

        # Trigger delete_list -> calls delete_instance
        mock_lst.delete_instance.side_effect = Exception("Delete Error")
        res = TaskManager.delete_list(1, 99)
        assert res is False

def test_reorder_exception():
    # Reorder uses atomic transaction.
    # We can patch db.atomic? No, proxy error.
    # We can patch TaskList.update(...) which is called inside.
    with patch("src.database.repositories.task_repository.TaskList.update") as mock_upd:
        mock_upd.side_effect = Exception("Update Error")
        res = TaskManager.reorder_lists(1, [1, 2])
        assert res is False
