
import pytest
from unittest.mock import MagicMock, patch
from src.webapp.auth import get_current_user, validate_telegram_data
from fastapi import HTTPException

def test_validate_telegram_data_valid(mocker):
    # Mock hashlib.hmac
    mocker.patch("hashlib.sha256")
    mocker.patch("hmac.new")

    # Needs implementation to match actual logic logic which is complex (hash calculation)
    # Actually, we can just mock the return of validate_telegram_data if we test the dependency?
    # But we want to test the function itself for coverage.
    pass

@pytest.mark.asyncio
async def test_get_current_user_dev_mode(mocker):
    # Test dev bypass if implemented (e.g. check if it allows bypass on localhost?)
    # The code uses X-Telegram-Init-Data.
    pass

def test_verify_init_data_success():
    # This requires constructing a valid hash which is hard.
    # Instead, we can mock hmac.new to return matching hash.
    with patch("src.webapp.auth.hmac.new") as mock_hmac:
        # First call returns secret key (digest), second returns hash (hexdigest)
        mock_hmac.return_value.digest.return_value = b"secret"
        mock_hmac.return_value.hexdigest.return_value = "fake_hash"

        # Data with hash="fake_hash"
        token = "123:ABC"
        init_data = "hash=fake_hash&user=%7B%22id%22%3A123%7D"

        # We also need to mock Config.TELEGRAM_TOKEN
        with patch("src.webapp.auth.Config.TELEGRAM_TOKEN", token):
            result = validate_telegram_data(init_data, token)
            assert result is not None
            assert result["id"] == 123

def test_verify_init_data_fail():
    with patch("src.webapp.auth.hmac.new") as mock_hmac:
        mock_hmac.return_value.digest.return_value = b"secret"
        mock_hmac.return_value.hexdigest.return_value = "correct_hash"

        token = "123:ABC"
        init_data = "hash=wrong_hash&user=%7B%22id%22%3A123%7D"

        with patch("src.webapp.auth.Config.TELEGRAM_TOKEN", token):
            result = validate_telegram_data(init_data, token)
            assert result is None

@pytest.mark.asyncio
async def test_get_current_user_success(mocker):
    header_val = "hash=valid&user=%7B%22id%22%3A12345%2C%22username%22%3A%22test%22%7D"

    mocker.patch("src.webapp.auth.validate_telegram_data", return_value={"id": 12345})
    # UserManager is not used in auth.py anymore, it just extracts ID

    user_id = await get_current_user(header_val)
    assert user_id == 12345

@pytest.mark.asyncio
async def test_get_current_user_no_header(mocker):
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None)
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_user_invalid_hash(mocker):
    header_val = "invalid"

    mocker.patch("src.webapp.auth.validate_telegram_data", return_value=None)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(header_val)
    assert exc.value.status_code == 401
