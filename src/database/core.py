from peewee import DatabaseProxy, SqliteDatabase
import os
from pathlib import Path

# Use a proxy to initialize the database later
db = DatabaseProxy()


def init_db(db_name="maui.db"):
    """
    Initialize the database connection.
    For this project, we are sticking to SQLite.
    """
    database = SqliteDatabase(db_name)
    db.initialize(database)
    return db
