import pytest
from unittest.mock import MagicMock, AsyncMock
from src.bot.handlers import start_command, help_command, webapp_command, handle_message, handle_voice
from src.services.coordinator import Coordinator
from src.database.models import User
from src.utils.schema import TaskStatus, UserStatus

@pytest.fixture
def mock_update(mocker):
    update = AsyncMock()
    # Use MagicMock for effective_user so methods like mention_html are synchronous
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.effective_user.last_name = "User"
    update.effective_user.mention_html.return_value = "Test User"

    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    update.message.reply_markdown = AsyncMock()
    update.message.reply_chat_action = AsyncMock()
    return update

@pytest.fixture
def mock_context(mocker):
    context = AsyncMock()
    context.bot_data = {} # Simulating bot_data
    return context

@pytest.mark.asyncio
async def test_start_command(mock_update, mock_context, test_db, mocker):
    # Mock Coordinator.handle_message to avoid calling Gemini
    # But start command handles registration directly via generic flow?
    # Actually handlers use global 'coordinator' usually?
    # No, handlers.py imports 'coordinator' instance from main? Or instantiates it?
    # Let's check handlers.py structure. It likely imports a global or is composed.

    # Wait, usually handlers are just functions.
    # I need to see how `coordinator` is accessed in handlers.py.
    # Assuming it's imported globally or I need to patch it.

    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value

    await start_command(mock_update, mock_context)

    # Verify manager call instead of DB, since manager is mocked
    mock_coord.user_manager.get_or_create_user.assert_called_with(
        12345, "testuser", "Test", "User"
    )

    # Configure mock user status to ensure we hit the welcome message path
    mock_user = mock_coord.user_manager.get_or_create_user.return_value
    mock_user.status = "APPROVED" # Anything not PENDING or BLACKLISTED

    # Verify reply
    # The code calls reply_html, so we should verify that.
    mock_update.message.reply_html.assert_called_once()
    args = mock_update.message.reply_html.call_args[0]
    assert "Hola" in args[0]
    # Should point to Mini App
    assert "Mini App" in args[0]

@pytest.mark.asyncio
async def test_help_command(mock_update, mock_context):
    await help_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    # Updated help message mentions Mini App
    assert "Mini App" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_webapp_command(mock_update, mock_context):
    await webapp_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    assert "aplicación web" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_handle_message_text(mock_update, mock_context, mocker):
    mock_update.message.text = "Hello"
    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    mock_coord.handle_message = AsyncMock(return_value="Response")

    from src.bot.handlers import handle_message
    await handle_message(mock_update, mock_context)

    mock_coord.handle_message.assert_called()
    mock_update.message.reply_chat_action.assert_called_with(action="typing")
    mock_update.message.reply_markdown.assert_called_with("Response")

@pytest.mark.asyncio
async def test_handle_message_no_text(mock_update, mock_context):
    mock_update.message.text = None
    from src.bot.handlers import handle_message
    await handle_message(mock_update, mock_context)
    mock_update.message.reply_markdown.assert_not_called()

@pytest.mark.asyncio
async def test_handle_voice(mock_update, mock_context, mocker):
    mock_voice = MagicMock()
    mock_voice.file_id = "voice_file_id"
    mock_update.message.voice = mock_voice
    mock_update.message.audio = None

    mock_file = AsyncMock()
    mock_file.download_as_bytearray.return_value = b"audio_data"
    mock_context.bot.get_file.return_value = mock_file

    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    mock_coord.handle_message = AsyncMock(return_value="Voice Response")

    from src.bot.handlers import handle_voice
    await handle_voice(mock_update, mock_context)

    mock_context.bot.get_file.assert_called_with("voice_file_id")
    mock_coord.handle_message.assert_called()
    assert mock_coord.handle_message.call_args[1]["is_voice"] is True
    mock_update.message.reply_markdown.assert_called_with("Voice Response")

@pytest.mark.asyncio
async def test_handle_voice_no_voice(mock_update, mock_context):
    mock_update.message.voice = None
    mock_update.message.audio = None
    from src.bot.handlers import handle_voice
    await handle_voice(mock_update, mock_context)
    mock_update.message.reply_markdown.assert_not_called()

@pytest.mark.asyncio
async def test_handle_voice_error(mock_update, mock_context, mocker):
    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    # Simulate an error during processing
    mock_coord.handle_message.side_effect = Exception("Voice processing failed")

    # Setup voice update
    mock_update.message.voice = MagicMock()
    mock_update.message.voice.file_id = "voice_123"

    # Mocking get_file to return a valid file object
    mock_file = AsyncMock()
    mock_file.download_as_bytearray.return_value = b"audio_data"
    mock_context.bot.get_file.return_value = mock_file

    from src.bot.handlers import handle_voice
    await handle_voice(mock_update, mock_context)

    # Should reply with error message (which calls reply_text in the except block)
    # The actual code calls: await update.message.reply_text("Lo siento, hubo un error al procesar tu audio.")
    assert mock_update.message.reply_text.call_count == 1
    args = mock_update.message.reply_text.call_args
    # The actual message in handler is: "Lo siento, hubo un error al procesar tu audio. Por favor intenta de nuevo."
    assert "hubo un error al procesar tu audio" in args[0][0]

@pytest.mark.asyncio
async def test_start_command_pending_user(mock_update, mock_context, mocker):
    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    mock_user = mock_coord.user_manager.get_or_create_user.return_value
    mock_user.status = UserStatus.PENDING
    mock_user.first_name = "PendingUser"

    await start_command(mock_update, mock_context)

    # Needs to verify it sends the pending message
    # "Gracias por registrarte"
    mock_update.message.reply_text.assert_called_once()
    args = mock_update.message.reply_text.call_args[0][0]
    assert "Gracias por registrarte" in args

@pytest.mark.asyncio
async def test_start_command_blacklisted_user(mock_update, mock_context, mocker):
    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    mock_user = mock_coord.user_manager.get_or_create_user.return_value
    mock_user.status = UserStatus.BLACKLISTED

    await start_command(mock_update, mock_context)

    # Should simply return without sending the welcome message logic (or any specific message defined)
    # The code says: return # Ignore.
    # So strictly:
    mock_update.message.reply_html.assert_not_called()
    mock_update.message.reply_text.assert_not_called()
