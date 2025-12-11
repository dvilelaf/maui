from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label, Button, Input, TabbedContent, TabPane
from textual.containers import Container
from textual.screen import ModalScreen
from rich.text import Text
import os
import time
import logging

from src.database.core import db, init_db
from src.database.models import User, Task
from src.utils.config import Config
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
        from src.database.models import User

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
        from src.database.models import User

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
        from src.database.models import Task

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
        from src.database.models import Task
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


class DatabaseMonitor(App):
    CSS = """
    Screen {
        layout: vertical;
        align: center middle;
    }
    .modal {
        padding: 2;
        border: solid white;
        width: 80;
        height: auto;
        max-height: 90%;
        background: $surface;
        # align is handled by parent container (Screen) mostly, but let's keep it safe
        # Textual containers justify/align content.
        # So Screen (parent) aligns .modal (child).
    }
    Button {
        margin: 1;
        width: 100%;
    }
    DataTable {
        height: 1fr;
        border: solid green;
    }
    Label {
        padding: 1;
        background: $primary;
        color: $text;
        text-align: center;
        width: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
        ("left", "previous_tab", "Prev Tab"),
        ("right", "next_tab", "Next Tab"),
        ("up", "scroll_up", "Up"),
        ("down", "scroll_down", "Down"),
    ]

    def _activate_tab(self, tab_id: str):
        self.query_one(TabbedContent).active = tab_id
        # Auto-select first row
        table_id = "#users_table" if tab_id == "users_tab" else "#tasks_table"
        table = self.query_one(table_id, DataTable)
        table.focus()
        if table.row_count > 0:
            table.move_cursor(row=0)

    def action_previous_tab(self):
        self._activate_tab("users_tab")

    def action_next_tab(self):
        self._activate_tab("tasks_tab")

    def action_scroll_up(self):
        try:
            active_tab = self.query_one(TabbedContent).active
            table_id = "#users_table" if active_tab == "users_tab" else "#tasks_table"
            table = self.query_one(table_id, DataTable)
            table.focus()
            table.action_cursor_up()
        except Exception:
            pass

    def action_scroll_down(self):
        try:
            active_tab = self.query_one(TabbedContent).active
            table_id = "#users_table" if active_tab == "users_tab" else "#tasks_table"
            table = self.query_one(table_id, DataTable)
            table.focus()
            table.action_cursor_down()
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = event.control
        if table.id == "users_table":
            user_id = int(event.row_key.value)
            self.push_screen(EditUserModal(user_id))

        elif table.id == "tasks_table":
            task_id = int(event.row_key.value)
            self.push_screen(EditTaskModal(task_id))

    def __init__(self):
        super().__init__()
        # Cache for diffing: table_name -> id -> {field: value}
        self.data_cache = {"users": {}, "tasks": {}}
        # Highlight tracker: table_name -> id -> field -> timestamp
        self.highlights = {"users": {}, "tasks": {}}
        self.is_first_refresh = True

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Users", id="users_tab"):
                yield DataTable(id="users_table")
            with TabPane("Tasks", id="tasks_tab"):
                yield DataTable(id="tasks_table")
        yield Footer()

    def on_mount(self) -> None:
        self.init_db()

        # Setup Tables
        users_table = self.query_one("#users_table", DataTable)
        users_table.cursor_type = "row"
        users_table.add_columns(
            "Telegram ID",
            "Username",
            "First Name",
            "Last Name",
            "Status",
            "Notif. Time",
        )

        tasks_table = self.query_one("#tasks_table", DataTable)
        tasks_table.cursor_type = "row"
        # Updated columns for tasks
        tasks_table.add_columns("ID", "User", "Title", "Deadline", "Priority", "Status")

        tasks_table.add_columns("ID", "User", "Title", "Deadline", "Priority", "Status")

        # Start Polling
        self.refresh_data()
        self.is_first_refresh = False
        self.set_interval(1.0, self.refresh_data)

        # Initial Focus
        users_table.focus()
        if users_table.row_count > 0:
            users_table.move_cursor(row=0)

    def init_db(self):
        # Initialize DB with absolute path
        db_url = Config.DATABASE_URL.replace("sqlite:///", "").replace("sqlite:", "")
        db_path = os.path.abspath(db_url)
        init_db(db_path)
        db.connect()

    def refresh_data(self):
        # Always update both to keep cache fresh and prevent "highlight all" on tab switch
        # If performance becomes an issue, we can optimize, but for SQLite this is negligible.
        self.update_users()
        self.update_tasks()

    def update_users(self):
        table = self.query_one("#users_table", DataTable)
        users_query = User.select().dicts()

        current_data = {}
        for user in users_query:
            current_data[user["telegram_id"]] = {
                "Telegram ID": str(user["telegram_id"]),
                "Username": user["username"] or "-",
                "First Name": user["first_name"] or "-",
                "Last Name": user["last_name"] or "-",
                "Status": user["status"],
                "Notif. Time": str(user["notification_time"]),
            }

        self._update_table(
            table,
            "users",
            current_data,
            [
                "Telegram ID",
                "Username",
                "First Name",
                "Last Name",
                "Status",
                "Notif. Time",
            ],
        )

    def update_tasks(self):
        table = self.query_one("#tasks_table", DataTable)

        # Joins to get username
        # Peewee select with join
        query = Task.select(Task, User).join(User)

        current_data = {}

        try:
            # Helper for priority
            priority_map = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "URGENT": "🔴"}

            for t in query:
                user_str = (
                    f"{t.user.username}"
                    if t.user.username
                    else f"{t.user.first_name} {t.user.last_name}"
                )
                # Handle case where all are None
                if user_str.strip() == "None None":
                    user_str = str(t.user.telegram_id)
                elif user_str.strip() == "None":
                    user_str = str(t.user.telegram_id)

                prio = priority_map.get(t.priority, t.priority)
                deadline = t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else "-"

                current_data[t.id] = {
                    "ID": str(t.id),
                    "User": user_str,
                    "Title": t.title,
                    "Priority": prio,
                    "Deadline": deadline,
                    "Status": t.status,
                }
        except Exception:
            # self.notify(str(e)) # Debug
            return

        self._update_table(
            table,
            "tasks",
            current_data,
            ["ID", "User", "Title", "Deadline", "Priority", "Status"],
        )

    def _update_table(
        self, table: DataTable, table_name: str, current_data: dict, columns: list
    ):
        """
        Generic update logic with diffing and highlighting.
        """
        cache = self.data_cache[table_name]
        highlights = self.highlights[table_name]
        now = time.time()

        # 1. Update Columns/Rows logic
        # Textual DataTable manages rows by Key. We can use ID as key.

        # Check for deleted rows
        cached_ids = set(cache.keys())
        current_ids = set(current_data.keys())

        for deleted_id in cached_ids - current_ids:
            if table.is_valid_row_index(table.get_row_index(str(deleted_id))):
                table.remove_row(str(deleted_id))
            del cache[deleted_id]
            if deleted_id in highlights:
                del highlights[deleted_id]

        # Check for new or updated rows
        for row_id, new_row in current_data.items():
            str_id = str(row_id)

            # --- HIGHLIGHT LOGIC ---
            # Detect changes field by field
            if row_id not in cache:
                # NEW ROW
                cache[row_id] = new_row
                # Init highlights for all fields
                ts = 0 if self.is_first_refresh else now
                highlights[row_id] = {col: ts for col in columns}
                # Add row
                # Initially highlighted only if NOT first refresh
                is_initially_highlighted = not self.is_first_refresh
                rendered_cells = [
                    self._render_cell(new_row[col], is_initially_highlighted)
                    for col in columns
                ]
                table.add_row(*rendered_cells, key=str_id)
            else:
                # EXISTING ROW
                old_row = cache[row_id]
                changes_found = False

                # Update highlights timestamp if changed
                if row_id not in highlights:
                    highlights[row_id] = {}

                for col in columns:
                    if old_row.get(col) != new_row.get(col):
                        highlights[row_id][col] = now
                        changes_found = True

                # Retrieve timestamps
                row_highlights = highlights[row_id]

                # Check if we need to redraw row cells
                # We redraw if data changed OR if highlight expired (to clear style)
                # It's expensive to update every second if nothing changed.
                # But we need to "un-highlight" after 5 seconds.

                # Logic: Is any field currently highlighted?
                # If yes, we must refresh that cell to see if it should expire.
                # If val changed, we must refresh.

                should_refresh_row = changes_found

                # Also check expirations
                for col, ts in list(row_highlights.items()):
                    if now - ts <= HIGHLIGHT_DURATION:
                        should_refresh_row = True  # It is highlighted, so we keep refreshing to eventually catch expiration?
                        # Actually, we rely on polling.
                    else:
                        # Expired. If it was just expired, we need one last refresh to clear it.
                        # We can just remove it from dict?
                        # Only if we know it was previously highlighted.
                        # Simple approach: Always update cell if it is in highlights dict.
                        # If it expires, remove from dict.
                        should_refresh_row = True
                        del row_highlights[col]

                if should_refresh_row:
                    column_keys = list(table.columns.keys())

                    for i, col in enumerate(columns):
                        ts = row_highlights.get(col, 0)
                        is_highlighted = now - ts <= HIGHLIGHT_DURATION

                        val = new_row[col]
                        # Special formatting for Status if tasks or users
                        if col == "Status":
                            if table_name == "tasks":
                                status_style = (
                                    "green"
                                    if val == TaskStatus.COMPLETED
                                    else "yellow"
                                    if val == TaskStatus.PENDING
                                    else "dim"
                                )
                                val = f"[{status_style}]{val}[/{status_style}]"
                            elif table_name == "users":
                                status_style = (
                                    "green"
                                    if val == UserStatus.WHITELISTED
                                    else "red"
                                    if val == UserStatus.BLACKLISTED
                                    else "yellow"
                                )
                                val = f"[{status_style}]{val}[/{status_style}]"

                        rendered = self._render_cell(val, is_highlighted)
                        table.update_cell(str_id, column_keys[i], rendered)

                cache[row_id] = new_row

    def _render_cell(self, value: str, highlighted: bool) -> Text:
        """Helper to style a cell."""
        # Value might contain markup already (e.g. status), so Text.from_markup
        text = Text.from_markup(str(value))
        if highlighted:
            text.style = "bold white on red"
        return text


if __name__ == "__main__":
    app = DatabaseMonitor()
    app.run()
