
import pytest
from unittest.mock import MagicMock
from peewee import SqliteDatabase
from src.database.core import db
from src.database.models import User, Task, TaskList, SharedAccess

@pytest.fixture
def test_db():
    # Use an in-memory database for tests
    test_db = SqliteDatabase(':memory:')
    db.initialize(test_db)

    # Create tables
    db.connect()
    db.create_tables([User, Task, TaskList, SharedAccess])

    yield db

    # Teardown
    db.close()

@pytest.fixture
def mock_gemini(mocker):
    # Mock the GenerativeModel class
    mock_model_cls = mocker.patch("google.generativeai.GenerativeModel")
    mock_model_instance = mock_model_cls.return_value

    # Setup default response for generate_content
    mock_response = MagicMock()
    mock_response.text = '{"intent": "UNKNOWN", "is_relevant": false}' # Default JSON response
    mock_model_instance.generate_content.return_value = mock_response

    return mock_model_instance

@pytest.fixture
def mock_bot(mocker):
    # Mock telegram.Bot
    mock_bot = mocker.patch("telegram.Bot")
    return mock_bot.return_value

@pytest.fixture(autouse=True)
def mock_config(mocker):
    """
    Ensure Config is mocked to safe defaults for all tests,
    overriding any local .env values that might cause crashes (like missing keys).
    """
    # Patch the RAW fields because they are what backend logic reads or what properties use
    from src.utils.config import Config
    mocker.patch.object(Config, "LLM_PROVIDER_RAW", "gemini")
    mocker.patch.object(Config, "GEMINI_API_KEYS_RAW", "fake_key")
    mocker.patch.object(Config, "GROQ_API_KEY", "fake_groq_key")
    return Config
