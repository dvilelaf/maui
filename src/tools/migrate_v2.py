from src.database.core import db, init_db
from src.database.models import Task, TaskList, SharedAccess
from src.utils.config import Config
from playhouse.migrate import SqliteMigrator, migrate


def run_migration():
    print("Starting migration to V2 (Lists & Sharing)...")
    db_path = Config.DATABASE_URL
    if db_path.startswith("sqlite:///"):
        db_path = db_path.replace("sqlite:///", "")

    print(f"Using database path: {db_path}")
    import os

    print(f"Absolute path: {os.path.abspath(db_path)}")

    init_db(db_path)

    database = db.obj
    migrator = SqliteMigrator(database)

    # 1. Create new tables
    print("Creating TaskList and SharedAccess tables...")
    database.create_tables([TaskList, SharedAccess], safe=True)

    # 2. Add column to Task
    # Check if column exists first to avoid error? Or just try/except
    try:
        print("Adding task_list column to Task table...")
        task_list_field = Task._meta.fields["task_list"]
        migrate(migrator.add_column("task", "task_list_id", task_list_field))
        print("Column added successfully.")
    except Exception as e:
        print(f"Skipping column addition (might already exist): {e}")

    print("Migration complete.")


if __name__ == "__main__":
    run_migration()
