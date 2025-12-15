import pytest
from unittest.mock import MagicMock, patch
from src.database.repositories.user_repository import UserManager
from src.database.models import User, UserStatus
from src.webapp.auth import validate_telegram_data, get_current_user
from src.utils.config import Config
from fastapi import HTTPException

# --- User Repository Tests ---

def test_auto_whitelist_logic():
    """Cover lines 53-55 in user_repository.py"""
    telegram_id = 999

    # Patch WHITELISTED_USERS_RAW on the Config instance to include this ID
    # The property WHITELISTED_USERS will parse this string
    with patch.object(Config, 'WHITELISTED_USERS_RAW', str(telegram_id)):
        # Mock User.get_or_create to return a user with PENDING status
        mock_user = MagicMock(spec=User)
        mock_user.username = "test"
        mock_user.status = UserStatus.PENDING
        mock_user.first_name = "T"
        mock_user.last_name = "L"

        with patch('src.database.repositories.user_repository.User.get_or_create', return_value=(mock_user, False)):
            # Call get_or_create_user
            UserManager.get_or_create_user(telegram_id)

            # Assert status was updated to WHITELISTED
            assert mock_user.status == UserStatus.WHITELISTED
            # Assert save was called
            mock_user.save.assert_called()

def test_update_notification_time_not_found():
    """Cover lines 87-91 in user_repository.py"""
    with patch('src.database.repositories.user_repository.User.get', side_effect=User.DoesNotExist):
        result = UserManager().update_notification_time(123, "09:00")
        assert result is False

# --- Auth Tests ---

def test_validate_telegram_data_value_error():
    """Cover lines 20-21 in auth.py: ValueError during parse_qsl"""
    # parse_qsl raises ValueError on some malformed inputs, though hard to trigger with standard strings.
    # We can mock parse_qsl to raise it.
    with patch('src.webapp.auth.parse_qsl', side_effect=ValueError("Bad QSL")):
        result = validate_telegram_data("bad_data", "token")
        assert result is None

def test_validate_telegram_data_missing_user_field():
    """Cover line 47 in auth.py: 'user' key missing"""
    # Create valid hash but exclude 'user' field
    token = "token"
    # To pass the hash check, we need to generate a valid hash for data WITHOUT user
    # Or we can just mock the hash check pass?
    # Let's mock hmac to return matching hashes so we bypass signature verification

    with patch('hmac.new') as mock_hmac:
        # Mock digests to match
        mock_hmac.return_value.hexdigest.return_value = "match"
        # We need parsed_data to NOT have "user" but HAVE "hash" (popped in code)
        # Wait, the code pops "hash" then checks signature.
        # Then checks "user".

        # Actually easier: use valid logic but manual construction
        # data = "auth_date=1&hash=match" -> parsed {"auth_date": "1", "hash": "match"}
        # "user" is missing.
        # Validation checks hash match.
        # If we mock hmac.hexdigest to return "match", it passes.

        with patch('src.webapp.auth.parse_qsl', return_value=[("auth_date", "1"), ("hash", "match")]):
             result = validate_telegram_data("data", token)
             assert result is None

@pytest.mark.asyncio
async def test_get_current_user_no_token_configured():
    """Cover line 73 in auth.py: Config.TELEGRAM_TOKEN missing"""
    # Mock Config.TELEGRAM_TOKEN to be None
    with patch('src.utils.config.Config.TELEGRAM_TOKEN', None):
        with pytest.raises(HTTPException) as excinfo:
            await get_current_user("some_init_data")
        assert excinfo.value.status_code == 500
        assert "No Bot Token" in excinfo.value.detail
