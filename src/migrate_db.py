from src.utils.config import Config
from src.database.core import db, init_db
from peewee import OperationalError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    logger.info("Starting database migration...")

    # Get actual database object
    # Assumes db is already initialized by app.py or main block
    database = db.obj

    if not database:
        logger.error("Database not initialized! Cannot migrate.")
        return

    # Migrate: Add 'color' column to 'tasklist'
    logger.info("Attempting to add 'color' column to 'tasklist'...")
    try:
        database.execute_sql(
            "ALTER TABLE tasklist ADD COLUMN color VARCHAR(255) DEFAULT '#ffffff'"
        )
        logger.info("SUCCESS: Column 'color' added.")
    except OperationalError as e:
        if "duplicate column" in str(e):
            logger.info("Column 'color' already exists.")
        else:
            logger.error(f"OperationalError during migration (color): {e}")

    # Migrate: Add 'recurrence' column to 'task'
    logger.info("Attempting to add 'recurrence' column to 'task'...")
    try:
        database.execute_sql(
            "ALTER TABLE task ADD COLUMN recurrence VARCHAR(255) DEFAULT NULL"
        )
        logger.info("SUCCESS: Column 'recurrence' added.")
    except OperationalError as e:
        if "duplicate column" in str(e):
            logger.info("Column 'recurrence' already exists.")
        else:
            logger.error(f"OperationalError during migration (recurrence): {e}")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    logger.info(f"Connecting to database at {db_path}")
    init_db(db_path)
    migrate()
