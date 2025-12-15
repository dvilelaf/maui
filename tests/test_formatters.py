
import pytest
from datetime import datetime, timedelta
from src.utils.formatters import (
    format_datetime_es,
    format_task_es,
    format_list_deleted,
    format_task_added,
    format_task_completed,
    format_task_updated,
    format_list_created,
    format_list_not_found,
    format_list_empty,
    format_share_result,
    format_task_deleted
)
from unittest.mock import MagicMock

def test_format_datetime_es():
    now = datetime.now()

    # Hoy
    assert "Hoy" in format_datetime_es(now)
    assert format_datetime_es(None) == "Sin fecha"

    # Mañana
    tomorrow = now + timedelta(days=1)
    assert "Mañana" in format_datetime_es(tomorrow)

    # Ayer
    yesterday = now - timedelta(days=1)
    assert "Ayer" in format_datetime_es(yesterday)

    # Next week (Day name) - assuming within 7 days
    next_week = now + timedelta(days=3)
    # Check if a weekday name is present
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    assert any(day in format_datetime_es(next_week) for day in days)

    # Far future
    far_future = now + timedelta(days=30)
    # Checks specific format logic if needed, simplify for robustness
    assert "de" in format_datetime_es(far_future)

def test_format_task_es():
    task = MagicMock()
    task.id = 1
    task.title = "Test Task"
    task.deadline = datetime.now()
    task.priority = "HIGH"

    output = format_task_es(task)
    assert "Test Task" in output
    assert "🟠" in output # HIGH priority map
    assert "Hoy" in output

def test_format_helper_functions():
    assert "🗑️ Lista eliminada: *MyList*" == format_list_deleted("MyList")
    assert "📋 Lista creada: *NewList*" == format_list_created("NewList")
    assert "No encontré ninguna lista llamada 'LostList'" in format_list_not_found("LostList")
    assert "está vacía" in format_list_empty("EmptyList")

    # Share
    assert "✅" in format_share_result(True, "Success")
    assert "⚠️" in format_share_result(False, "Fail")

    # Task Added
    task = MagicMock(title="Task 1", deadline=None)
    assert "✅ Tarea guardada: *Task 1*" == format_task_added(task)

    task_deadline = MagicMock(title="Task 2", deadline=datetime.now())
    assert "para Hoy" in format_task_added(task_deadline)

    # Task Deleted
    assert "🗑️ Tarea eliminada: *Gone*" == format_task_deleted("Gone")

    # Task Completed
    assert "✅ Tarea completada: *Done*" == format_task_completed("Done")

    # Task Updated
    assert "✏️ Tarea actualizada: *Upd*" in format_task_updated("Upd", [])
    assert "Change1" in format_task_updated("Upd", ["Change1"])
