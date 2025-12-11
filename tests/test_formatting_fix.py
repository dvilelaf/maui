
import pytest
from unittest.mock import MagicMock
from src.services.coordinator import Coordinator
from src.database.models import User, TaskList

def test_get_lists_summary_bullets(test_db):
    coord = Coordinator()
    user = User.create(telegram_id=99999, first_name="Test")
    TaskList.create(title="List A", owner=user)
    TaskList.create(title="List B", owner=user)

    summary = coord.get_lists_summary(99999)

    assert "• *List A*" in summary
    assert "• *List B*" in summary
    assert "1." not in summary # Should not have numbers
    assert "   _(Vacía)_" in summary
