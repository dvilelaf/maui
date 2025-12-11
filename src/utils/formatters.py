from datetime import datetime, timedelta
import pytz

PRIORITY_MAP = {
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🟠",
    "URGENT": "🔴"
}

DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

def format_datetime_es(dt: datetime) -> str:
    """
    Format a datetime object into a human-readable Spanish string.
    e.g., "Hoy a las 14:00", "Mañana a las 09:30", "El Lunes a las 20:00", "El 5 de Enero"
    """
    if not dt:
        return "Sin fecha"

    now = datetime.now()
    # Normalize comparison by ignoring seconds/microseconds if needed,
    # but strictly we care about calendar days.

    # Check if it's the same day
    if dt.date() == now.date():
        day_str = "Hoy"
    elif dt.date() == (now + timedelta(days=1)).date():
        day_str = "Mañana"
    elif dt.date() == (now - timedelta(days=1)).date():
        day_str = "Ayer"
    elif now < dt < now + timedelta(days=7):
        # Within next 7 days
        day_str = f"El {DAYS_ES[dt.weekday()]}"
    else:
        # Full date
        day_str = f"El {dt.day} de {MONTHS_ES[dt.month]}"

    time_str = dt.strftime("%H:%M")
    return f"{day_str} a las {time_str}"

def format_task_es(task) -> str:
    """
    Returns a formatted string for a task.
    """
    date_str = format_datetime_es(task.deadline)
    priority_str = PRIORITY_MAP.get(task.priority, "⚪")

    title = task.title
    if title:
        title = title[0].upper() + title[1:]

    return f"• *{title}* \n  ⏳ {date_str}  |  {priority_str}\n\n"
