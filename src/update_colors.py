from src.utils.config import Config
from src.database.core import db, init_db

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_colors():
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    init_db(db_path)
    database = db.obj

    # Update all white or null colors to light gray
    logger.info("Updating colors to #f2f2f2...")
    database.execute_sql(
        "UPDATE tasklist SET color = '#f2f2f2' WHERE color = '#ffffff' OR color IS NULL OR color = ''"
    )
    logger.info("Colors updated.")


if __name__ == "__main__":
    update_colors()
