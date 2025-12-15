
import pytest
from unittest.mock import patch
import os
from src.utils.config import Config

@pytest.fixture
def clean_env():
    # Helper to create fresh settings
    pass

def test_db_url_docker():
    with patch("src.utils.config.os.path.isdir") as mock_isdir:
        mock_isdir.return_value = True
        # Logic is in validate_db_url(cls, v).
        # It's a field_validator.
        # We can call it directly on Settings class? Or instantiate Settings.
        # But we need to pass no value for DATABASE_URL to let it use default logic?
        # Default is None. validator runs on None?
        # "validate_db_url(cls, v)" checks "if v and v.strip()".
        # If default is None, it falls through to logic.

        # We need to construct Settings with DATABASE_URL=None (default).
        # But BaseSettings might read env.
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            # We call the validator method directly to avoid env interference
            # validation_db_url is a classmethod.
            from src.utils.config import Settings
            res = Settings.validate_db_url(None)
            assert res == "/app/data/maui.db"

def test_webapp_url_scheme():
    from src.utils.config import Settings
    res = Settings.validate_webapp_url("localhost:8080")
    assert res == "https://localhost:8080"

def test_empty_lists():
    from src.utils.config import Settings
    s = Settings(GEMINI_API_KEYS="", WHITELISTED_USERS="")
    assert s.GEMINI_API_KEYS == []
    assert s.WHITELISTED_USERS == []

def test_whitelisted_users_invalid():
    from src.utils.config import Settings
    s = Settings(WHITELISTED_USERS="123,abc")
    # Should catch ValueError and return []
    assert s.WHITELISTED_USERS == [123]
