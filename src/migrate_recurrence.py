from src.utils.config import Config
from src.database.core import db, init_db
from peewee import OperationalError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    logger.info(f"Connecting to database at {db_path}")

    # Init generic db wrapper
    init_db(db_path)

    # Get actual database object
    database = db.obj

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
            logger.error(f"OperationalError during migration: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    migrate()
