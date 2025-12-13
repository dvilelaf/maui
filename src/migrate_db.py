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
            logger.error(f"OperationalError during migration: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    migrate()
