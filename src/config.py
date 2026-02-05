import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_CHAT_ID: int = int(os.getenv("ADMIN_CHAT_ID", "0"))
    TARGET_CHAT_ID: int = int(os.getenv("TARGET_CHAT_ID", "0"))
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
    SCHEDULE_TIMES: list[tuple[int, int]] = [(h, 0) for h in range(24)]  # 매시간 정각
    DATABASE_PATH: Path = DATA_DIR / "bot.db"

    @classmethod
    def validate(cls) -> list[str]:
        errors = []
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        if not cls.ADMIN_CHAT_ID:
            errors.append("ADMIN_CHAT_ID is required")
        if not cls.TARGET_CHAT_ID:
            errors.append("TARGET_CHAT_ID is required")
        if not cls.YOUTUBE_API_KEY:
            errors.append("YOUTUBE_API_KEY is required")
        return errors
