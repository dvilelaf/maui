
import pytest
from datetime import datetime, timedelta
from src.utils.formatters import format_datetime_es, format_task_es
from unittest.mock import MagicMock

def test_format_datetime_es_none():
    assert format_datetime_es(None) == "Sin fecha"

def test_format_datetime_es_today():
    now = datetime.now()
    expected = f"Hoy a las {now.strftime('%H:%M')}"
    assert format_datetime_es(now) == expected

def test_format_datetime_es_tomorrow():
    tmr = datetime.now() + timedelta(days=1)
    expected = f"Mañana a las {tmr.strftime('%H:%M')}"
    assert format_datetime_es(tmr) == expected

def test_format_datetime_es_yesterday():
    yest = datetime.now() - timedelta(days=1)
    expected = f"Ayer a las {yest.strftime('%H:%M')}"
    assert format_datetime_es(yest) == expected

def test_format_datetime_es_weekday():
    # 3 days from now is likely within the week (unless looking back, but code handles future)
    future = datetime.now() + timedelta(days=3)
    # This might fail if "3 days from now" wraps around to "next week" logic?
    # Code says: now < dt < now + 7 days
    # So yes, should be "El <Day>"
    days_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    day_name = days_es[future.weekday()]
    expected = f"El {day_name} a las {future.strftime('%H:%M')}"
    assert format_datetime_es(future) == expected

def test_format_datetime_es_full_date():
    future = datetime.now() + timedelta(days=30)
    # Should be "El <Day> de <Month>"
    months_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    expected_start = f"El {future.day} de {months_es[future.month]}"
    assert format_datetime_es(future).startswith(expected_start)

def test_format_task_es():
    task = MagicMock()
    task.id = 1
    task.title = "Test Task"
    task.priority = "HIGH"
    task.deadline = datetime.now()

    formatted = format_task_es(task)

    assert "[#1]" in formatted
    assert "Test Task" in formatted
    assert "🟠" in formatted # High priority icon
    assert "Hoy" in formatted

def test_format_task_es_defaults():
    task = MagicMock()
    task.id = 2
    task.title = "Basic Task"
    task.priority = None
    task.deadline = None

    formatted = format_task_es(task)

    assert "Basic Task" in formatted
    assert "⚪" in formatted # Default icon
    assert "Sin fecha" in formatted
