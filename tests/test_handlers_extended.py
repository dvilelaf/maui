
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.bot.handlers import (
    handle_invite_response,
    handle_admin_action,
    admin_command,
    get_coordinator
)
from src.utils.schema import UserStatus

@pytest.fixture
def mock_update_cb(mocker):
    update = AsyncMock()
    update.callback_query = AsyncMock()
    update.callback_query.message.text = "Original Message"
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_user.id = 12345
    return update

@pytest.fixture
def mock_update_admin(mocker):
    update = AsyncMock()
    update.effective_user.id = 999 # Defined as admin
    update.message.reply_text = AsyncMock()
    update.callback_query = AsyncMock()
    update.callback_query.message.text = "Request"
    return update

@pytest.mark.asyncio
async def test_get_coordinator_singleton():
    # Reset singleton first to test creation
    from src.bot import handlers
    handlers._coordinator = None

    c1 = get_coordinator()
    c2 = get_coordinator()
    assert c1 is c2
    assert c1 is not None

@pytest.mark.asyncio
async def test_handle_invite_response_accept(mock_update_cb, mocker):
    mock_update_cb.callback_query.data = "INVITE_ACCEPT_100"

    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    mock_coord.task_manager.respond_to_invite = AsyncMock(return_value=(True, "Exito"))

    await handle_invite_response(mock_update_cb, AsyncMock())

    mock_coord.task_manager.respond_to_invite.assert_called_with(12345, 100, True)
    assert "✅ Exito" in mock_update_cb.callback_query.edit_message_text.call_args[1]['text']

@pytest.mark.asyncio
async def test_handle_invite_response_reject(mock_update_cb, mocker):
    mock_update_cb.callback_query.data = "INVITE_REJECT_100"

    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    mock_coord.task_manager.respond_to_invite = AsyncMock(return_value=(True, "Rechazado"))

    await handle_invite_response(mock_update_cb, AsyncMock())

    mock_coord.task_manager.respond_to_invite.assert_called_with(12345, 100, False)

@pytest.mark.asyncio
async def test_handle_invite_invalid_data(mock_update_cb):
    mock_update_cb.callback_query.data = "INVALID_DATA"
    await handle_invite_response(mock_update_cb, AsyncMock())
    mock_update_cb.callback_query.edit_message_text.assert_not_called()

# --- Admin Tests ---

@pytest.mark.asyncio
async def test_admin_command_unauthorized(mock_update_cb, mocker):
    # User 12345 is not admin (999)
    mocker.patch("src.bot.handlers.Config.ADMIN_USER", 999)

    mock_update_cb.effective_user.id = 12345
    # admin_command uses update.message
    mock_update_cb.message = AsyncMock()
    mock_update_cb.message.reply_text = AsyncMock()

    await admin_command(mock_update_cb, AsyncMock())

    # Should say unauthorized
    args = mock_update_cb.message.reply_text.call_args[0][0]
    assert "No tienes permisos" in args

@pytest.mark.asyncio
async def test_admin_command_authorized_empty(mock_update_admin, mocker):
    mocker.patch("src.bot.handlers.Config.ADMIN_USER", 999)
    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    mock_coord.user_manager.get_pending_users.return_value = []

    await admin_command(mock_update_admin, AsyncMock())

    assert "No hay solicitudes" in mock_update_admin.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_admin_command_authorized_list(mock_update_admin, mocker):
    mocker.patch("src.bot.handlers.Config.ADMIN_USER", 999)
    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value

    mock_user = MagicMock()
    mock_user.telegram_id = 555
    mock_user.first_name = "Bob"
    mock_user.last_name = None
    mock_user.username = "bob"

    mock_coord.user_manager.get_pending_users.return_value = [mock_user]

    await admin_command(mock_update_admin, AsyncMock())

    # First call is header, second is user card
    assert mock_update_admin.message.reply_text.call_count == 2

    # Check if buttons are in the second call
    _, kwargs = mock_update_admin.message.reply_text.call_args_list[1]
    assert "reply_markup" in kwargs

@pytest.mark.asyncio
async def test_handle_admin_action_approve(mock_update_admin, mocker):
    mocker.patch("src.bot.handlers.Config.ADMIN_USER", 999)
    mock_update_admin.callback_query.data = "ADMIN_APPROVE_555"

    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value
    mock_context = AsyncMock()

    await handle_admin_action(mock_update_admin, mock_context)

    mock_coord.user_manager.update_status.assert_called_with(555, UserStatus.WHITELISTED)
    # Check notification sent to user
    mock_context.bot.send_message.assert_called_with(chat_id=555, text=mocker.ANY)

    # Check text argument (could be positional or keyword)
    call_args = mock_update_admin.callback_query.edit_message_text.call_args
    arg_text = call_args.kwargs.get('text') or call_args[0][0]
    assert "aprobado" in arg_text

@pytest.mark.asyncio
async def test_handle_admin_action_reject(mock_update_admin, mocker):
    mocker.patch("src.bot.handlers.Config.ADMIN_USER", 999)
    mock_update_admin.callback_query.data = "ADMIN_REJECT_555"

    mock_coord = mocker.patch("src.bot.handlers.get_coordinator").return_value

    await handle_admin_action(mock_update_admin, AsyncMock())

    mock_coord.user_manager.update_status.assert_called_with(555, UserStatus.BLACKLISTED)

    call_args = mock_update_admin.callback_query.edit_message_text.call_args
    arg_text = call_args.kwargs.get('text') or call_args[0][0]
    assert "rechazado" in arg_text

@pytest.mark.asyncio
async def test_handle_admin_action_unauthorized(mock_update_cb, mocker):
    mocker.patch("src.bot.handlers.Config.ADMIN_USER", 999)
    mock_update_cb.effective_user.id = 12345 # Not 999

    await handle_admin_action(mock_update_cb, AsyncMock())

    assert "No tienes permisos" in mock_update_cb.callback_query.edit_message_text.call_args[0][0]
