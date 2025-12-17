import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException
from src.utils.config import Config


def validate_telegram_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Validates the Telegram Web App initData string.
    Returns the user dict if valid, None otherwise.
    """
    if not init_data:
        return None

    try:
        parsed_data = dict(parse_qsl(init_data))
    except ValueError:
        return None

    if "hash" not in parsed_data:
        return None

    received_hash = parsed_data.pop("hash")

    # Data-check-string is a chain of key=value pairs, sorted alphabetically
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

    # Secret key is HMAC-SHA256 of bot token with "WebAppData" as key
    secret_key = hmac.new(
        key=b"WebAppData", msg=bot_token.encode(), digestmod=hashlib.sha256
    ).digest()

    # Integrity check: HMAC-SHA256 of data_check_string with secret_key
    calculated_hash = hmac.new(
        key=secret_key, msg=data_check_string.encode(), digestmod=hashlib.sha256
    ).hexdigest()

    if calculated_hash != received_hash:
        return None

    # Parse user data
    user_data_str = parsed_data.get("user")
    if not user_data_str:
        return None

    try:
        return json.loads(user_data_str)
    except json.JSONDecodeError:
        return None


async def get_current_user(
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"),
) -> int:
    """
    FastAPI Dependency to get the authenticated user ID.
    Raises 401 if invalid.
    """
    if not x_telegram_init_data:
        # Development fallback only if absolutely needed, but better to fail secure.
        # If user visits via browser without Telegram, they can't authenticate.
        # Check if we have a development bypass in Config? (Not currently).
        raise HTTPException(status_code=401, detail="Missing authentication header")

    if not Config.TELEGRAM_TOKEN:
        raise HTTPException(
            status_code=500, detail="Server misconfiguration: No Bot Token"
        )

    user_data = validate_telegram_data(x_telegram_init_data, Config.TELEGRAM_TOKEN)

    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid authentication signature")

    return int(user_data["id"])
