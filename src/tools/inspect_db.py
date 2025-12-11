from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.widgets import Static
from rich.text import Text
import datetime
import os
import time

from src.database.core import db, init_db
from src.database.models import User, Task
from src.utils.config import Config
from src.utils.schema import TaskStatus

# Highlight duration in seconds
HIGHLIGHT_DURATION = 5.0

class DatabaseMonitor(App):
    CSS = """
    Screen {
        layout: vertical;
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

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self):
        super().__init__()
        # Cache for diffing: table_name -> id -> {field: value}
        self.data_cache = {
             "users": {},
             "tasks": {}
        }
        # Highlight tracker: table_name -> id -> field -> timestamp
        self.highlights = {
             "users": {},
             "tasks": {}
        }
        self.is_first_refresh = True

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("👤 Users")
        yield DataTable(id="users_table")
        yield Label("📋 Tasks")
        yield DataTable(id="tasks_table")
        yield Footer()

    def on_mount(self) -> None:
        self.init_db()

        # Setup Tables
        users_table = self.query_one("#users_table", DataTable)
        users_table.cursor_type = "row"
        users_table.add_columns("Telegram ID", "Username", "Notif. Time")

        tasks_table = self.query_one("#tasks_table", DataTable)
        tasks_table.cursor_type = "row"
        tasks_table.add_columns("ID", "User", "Title", "Deadline", "Priority", "Status")

        # Start Polling
        self.refresh_data()
        self.is_first_refresh = False
        self.set_interval(1.0, self.refresh_data)

    def init_db(self):
        # Initialize DB with absolute path
        db_url = Config.DATABASE_URL.replace("sqlite:///", "").replace("sqlite:", "")
        db_path = os.path.abspath(db_url)
        init_db(db_path)
        db.connect()

    def refresh_data(self):
        self.update_users()
        self.update_tasks()

    def update_users(self):
        table = self.query_one("#users_table", DataTable)
        current_data = {}

        # Fetch Data
        try:
            users = User.select()
            for user in users:
                row_data = {
                    "Telegram ID": str(user.telegram_id),
                    "Username": user.username or "-",
                    "Notif. Time": str(user.notification_time)
                }
                current_data[user.telegram_id] = row_data
        except Exception as e:
            return

        self._update_table(table, "users", current_data, ["Telegram ID", "Username", "Notif. Time"])

    def update_tasks(self):
        table = self.query_one("#tasks_table", DataTable)
        current_data = {}

        try:
            # Reusing the sort logic requested
            tasks = Task.select().order_by(Task.deadline.asc(), Task.priority.desc())

            # Helper for priority
            priority_map = {
                "LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "URGENT": "🔴"
            }

            for task in tasks:
                 prio = priority_map.get(task.priority, task.priority)
                 status_style = "green" if task.status == TaskStatus.COMPLETED else "yellow" if task.status == TaskStatus.PENDING else "dim"
                 # We store raw-ish status for comparison, but render styled
                 # Actually comparison should be on content.
                 # Let's simple format now.

                 deadline = task.deadline.strftime("%Y-%m-%d %H:%M") if task.deadline else "-"

                 row_data = {
                     "ID": str(task.id),
                     "User": task.user.username or str(task.user.telegram_id),
                     "Title": task.title,
                     "Deadline": deadline,
                     "Priority": prio,
                     "Status": task.status # Keep raw for cache, format later?
                     # Only string can be in cache. Let's store what we show.
                 }
                 current_data[task.id] = row_data
        except Exception as e:
            return

        self._update_table(table, "tasks", current_data, ["ID", "User", "Title", "Deadline", "Priority", "Status"])

    def _update_table(self, table: DataTable, table_name: str, current_data: dict, columns: list):
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
                rendered_cells = [self._render_cell(new_row[col], is_initially_highlighted) for col in columns]
                table.add_row(*rendered_cells, key=str_id)
            else:
                # EXISTING ROW
                old_row = cache[row_id]
                changes_found = False

                # Update highlights timestamp if changed
                if row_id not in highlights: highlights[row_id] = {}

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
                         should_refresh_row = True # It is highlighted, so we keep refreshing to eventually catch expiration?
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
                        is_highlighted = (now - ts <= HIGHLIGHT_DURATION)

                        val = new_row[col]
                        # Special formatting for Status if tasks
                        if col == "Status" and table_name == "tasks":
                             status_style = "green" if val == TaskStatus.COMPLETED else "yellow" if val == TaskStatus.PENDING else "dim"
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
