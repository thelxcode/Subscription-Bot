# config.py
import os

class Config:
    # Telegram API Credentials (Get these from https://telegram.org)
    API_ID = int(os.getenv("API_ID", "1234567"))
    API_HASH = os.getenv("API_HASH", "abcdef1234567890abcdef1234567890")

    # Bot Token (Get this from @BotFather on Telegram)
    BOT_TOKEN = os.getenv("BOT_TOKEN", "1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ")

    # MongoDB Connection URI String
    DB_URL = os.getenv("DB_URL", "mongodb://localhost:27017")

