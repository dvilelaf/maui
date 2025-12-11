import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    _keys = os.getenv("GEMINI_API_KEY", "")
    GEMINI_API_KEYS = [k.strip() for k in _keys.split(",") if k.strip()]
    GEMINI_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    DATABASE_URL = os.getenv("DATABASE_URL", "maui.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
