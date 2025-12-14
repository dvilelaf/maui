from datetime import datetime, timedelta

PRIORITY_MAP = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "URGENT": "🔴"}

DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS_ES = [
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


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

    return f"• [#{task.id}] *{task.title}* \n  ⏳ {date_str}  |  {priority_str}\n\n"


def format_list_created(list_title: str) -> str:
    return f"📋 Lista creada: *{list_title}*"


def format_list_not_found(term: str) -> str:
    return f"❌ No encontré ninguna lista llamada '{term}'."


def format_share_result(success: bool, msg: str) -> str:
    emoji = "✅" if success else "⚠️"
    return f"{emoji} {msg}"


def format_list_empty(list_title: str) -> str:
    return f"📝 La lista *{list_title}* está vacía."


def format_task_added(task, list_title: str = None) -> str:
    deadline_str = f" para {format_datetime_es(task.deadline)}" if task.deadline else ""
    if list_title:
        return f"✅ Añadido a *{list_title}*: {task.title}"
    return f"✅ Tarea guardada: *{task.title}*{deadline_str}"


def format_task_deleted(title: str) -> str:
    return f"🗑️ Tarea eliminada: *{title}*"


def format_task_completed(title: str) -> str:
    return f"✅ Tarea completada: *{title}*"


def format_task_updated(title: str, changes: list[str]) -> str:
    msg = f"✏️ Tarea actualizada: *{title}*"
    if changes:
        msg += "\n" + "\n".join(changes)
    return msg


def format_list_deleted(list_title: str) -> str:
    return f"🗑️ Lista eliminada: *{list_title}*"
