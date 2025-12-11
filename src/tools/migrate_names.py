from src.database.core import db
from playhouse.migrate import migrate, SqliteMigrator
from peewee import CharField

def run_migration():
    print("Running migration to add first_name and last_name columns...")
    migrator = SqliteMigrator(db)

    # Check if columns exist first to avoid errors?
    # Peewee migrator doesn't have "add_column_if_not_exists", so we catch error or check pragma
    # But simple way is just try add

    try:
        migrate(
            migrator.add_column('user', 'first_name', CharField(null=True)),
            migrator.add_column('user', 'last_name', CharField(null=True)),
        )
        print("Migration successful.")
    except Exception as e:
        print(f"Migration failed (maybe columns exist?): {e}")

if __name__ == "__main__":
    from src.database.core import init_db
    from src.utils.config import Config
    init_db(Config.DATABASE_URL.replace("sqlite:///", ""))
    run_migration()
