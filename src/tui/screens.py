from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Label,
    Button,
    Input,
    Static,
)
import logging

from src.database.models import User, Task, TaskList
from src.utils.schema import TaskStatus, UserStatus

# Configure logger also here if run independently, though it inherits if imported (but this is main script often)
logger = logging.getLogger("inspect_db")

# Highlight duration in seconds
HIGHLIGHT_DURATION = 5.0


class EditUserModal(ModalScreen):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("up", "manual_focus_previous", "Previous"),
        ("down", "manual_focus_next", "Next"),
    ]

    def action_manual_focus_previous(self):
        self.focus_previous()

    def action_manual_focus_next(self):
        self.focus_next()

    def action_cancel(self):
        self.dismiss()

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    def compose(self) -> ComposeResult:

        user = User.get_or_none(User.telegram_id == self.user_id)

        username = user.username if user and user.username else ""
        first_name = user.first_name if user and user.first_name else ""
        last_name = user.last_name if user and user.last_name else ""

        with Container(classes="modal"):
            yield Label(f"Editing User {self.user_id}")
            yield Label("Username:")
            yield Input(value=username, id="username")
            yield Label("First Name:")
            yield Input(value=first_name, id="first_name")
            yield Label("Last Name:")
            yield Input(value=last_name, id="last_name")

            yield Button("Save Changes", id="save", variant="primary")
            yield Button("Whitelist", id="whitelist", variant="success")
            yield Button("Blacklist", id="blacklist", variant="warning")
            yield Button("Kick (Delete)", id="kick", variant="error")
            yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:

        user = User.get_or_none(User.telegram_id == self.user_id)
        if not user:
            self.dismiss()
            return

        if event.button.id == "save":
            user.username = self.query_one("#username", Input).value
            user.first_name = self.query_one("#first_name", Input).value
            user.last_name = self.query_one("#last_name", Input).value
            user.save()
            logger.info(
                f"User {self.user_id} manual update: username={user.username}, name={user.first_name} {user.last_name}"
            )
            self.app.notify(f"User {self.user_id} Updated")
            self.dismiss()

        elif event.button.id == "whitelist":
            status = UserStatus.WHITELISTED
            user.status = status
            user.save()
            logger.info(f"User {self.user_id} manual whitelist")
            self.app.notify(f"User {self.user_id} Whitelisted")
            self.dismiss()
        elif event.button.id == "blacklist":
            status = UserStatus.BLACKLISTED
            user.status = status
            user.save()
            logger.info(f"User {self.user_id} manual blacklist")
            self.app.notify(f"User {self.user_id} Blacklisted")
            self.dismiss()
        elif event.button.id == "kick":
            from src.database.models import Task

            count = Task.delete().where(Task.user == user).execute()
            user.delete_instance()
            logger.warning(f"User {self.user_id} manual KICK (deleted {count} tasks)")
            self.app.notify(f"User {self.user_id} KICKED")
            self.dismiss()
        elif event.button.id == "cancel":
            self.dismiss()


class EditTaskModal(ModalScreen):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("up", "manual_focus_previous", "Previous"),
        ("down", "manual_focus_next", "Next"),
    ]

    def action_manual_focus_previous(self):
        self.focus_previous()

    def action_manual_focus_next(self):
        self.focus_next()

    def action_cancel(self):
        self.dismiss()

    def __init__(self, task_id: int):
        super().__init__()
        self.task_id = task_id

    def compose(self) -> ComposeResult:

        task = Task.get_or_none(Task.id == self.task_id)

        title = task.title if task else ""
        deadline = (
            task.deadline.strftime("%Y-%m-%d %H:%M") if task and task.deadline else ""
        )
        priority = task.priority if task else "MEDIUM"

        with Container(classes="modal"):
            yield Label(f"Editing Task {self.task_id}")
            yield Label("Title:")
            yield Input(value=title, id="title")
            yield Label("Deadline (YYYY-MM-DD HH:MM):")
            yield Input(value=deadline, id="deadline")
            yield Label("Priority (LOW/MEDIUM/HIGH/URGENT):")
            yield Input(value=priority, id="priority")

            yield Button("Save Changes", id="save", variant="primary")
            yield Button("Mark Completed", id="complete", variant="success")
            yield Button("Mark Pending", id="pending", variant="warning")
            yield Button("Delete", id="delete", variant="error")
            yield Button("Cancel", id="cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from datetime import datetime

        task = Task.get_or_none(Task.id == self.task_id)

        if not task:
            self.dismiss()
            return

        if event.button.id == "save":
            task.title = self.query_one("#title", Input).value
            task.priority = self.query_one("#priority", Input).value.upper()

            deadline_str = self.query_one("#deadline", Input).value
            if deadline_str.strip():
                try:
                    task.deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    self.app.notify("Invalid Deadline Format. Use YYYY-MM-DD HH:MM")
                    return
            else:
                task.deadline = None

            task.save()
            logger.info(
                f"Task {self.task_id} manual update: title='{task.title}' status={task.status}"
            )
            self.app.notify(f"Task {self.task_id} Updated")
            self.dismiss()

        elif event.button.id == "complete":
            task.status = TaskStatus.COMPLETED
            task.save()
            logger.info(f"Task {self.task_id} manually marked COMPLETED")
            self.app.notify(f"Task {self.task_id} Completed")
            self.dismiss()
        elif event.button.id == "pending":
            task.status = TaskStatus.PENDING
            task.save()
            logger.info(f"Task {self.task_id} manually marked PENDING")
            self.app.notify(f"Task {self.task_id} Pending")
            self.dismiss()
        elif event.button.id == "delete":
            task.delete_instance()
            logger.info(f"Task {self.task_id} manually DELETED")
            self.app.notify(f"Task {self.task_id} Deleted")
            self.dismiss()
        elif event.button.id == "cancel":
            self.dismiss()


class ListDetailModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Close")]

    def action_cancel(self):
        self.dismiss()

    def __init__(self, list_id: int):
        super().__init__()
        self.list_id = list_id

    def compose(self) -> ComposeResult:
        tl = TaskList.get_by_id(self.list_id)
        with Container(classes="modal"):
            yield Label(f"List: {tl.title}", classes="modal-header")
            yield DataTable(id="list_items_table")
            yield Button("Close", id="close", variant="primary")

    def on_mount(self) -> None:
        table = self.query_one("#list_items_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Title", "Status")

        tasks = Task.select().where(Task.task_list == self.list_id)

        for t in tasks:
            status = "✅" if t.status == TaskStatus.COMPLETED else "⏳"
            table.add_row(str(t.id), t.title, status)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class ConfirmScreen(ModalScreen[bool]):
    """A modal dialog to confirm an action."""

    def __init__(self, message: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.message = message

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("left", "toggle_focus", "Focus Previous"),
        ("right", "toggle_focus", "Focus Next"),
    ]

    def action_cancel(self):
        self.dismiss(False)

    def action_toggle_focus(self):
        # Explicitly toggle focus between buttons
        current = self.focused
        if current and current.id == "confirm":
             self.query_one("#cancel", Button).focus()
        else:
             self.query_one("#confirm", Button).focus()

    def compose(self) -> ComposeResult:
        with Container(classes="modal"):
            yield Static(self.message, classes="confirm-message")
            with Horizontal(classes="buttons"):
                yield Button("Confirm", variant="error", id="confirm")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)


