import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    DATABASE_URL = os.getenv("DATABASE_URL", "maui.db")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
