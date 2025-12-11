
import pytest
from src.database.core import init_db, db
from peewee import SqliteDatabase, DatabaseProxy

def test_init_db():
    # Verify init_db initializes the proxy
    # We should use a separate proxy or carefully cleanup to not affect global state if possible,
    # but `db` is global.

    # Check return value
    res = init_db("test_core.db")
    assert isinstance(res, DatabaseProxy)
    assert isinstance(res.obj, SqliteDatabase)
    assert res.obj.database == "test_core.db"

    # Ideally we'd reset it, but it's a proxy.
    # The tests use :memory: usually via fixtures.
    # We can rely on mocks to avoid actual file creation if we want,
    # but simpler to just let it create and maybe cleanup or use tmp_path

def test_init_db_default():
    res = init_db()
    assert res.obj.database == "maui.db"
