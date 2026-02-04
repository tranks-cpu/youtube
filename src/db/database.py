import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from src.config import Config


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL,
                channel_name TEXT NOT NULL,
                uploads_playlist_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE NOT NULL,
                channel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                duration_seconds INTEGER,
                published_at TIMESTAMP,
                summarized_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                is_paused BOOLEAN DEFAULT FALSE,
                last_run_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO scheduler_state (id, is_paused)
            VALUES (1, FALSE)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_videos_published_at ON videos(published_at)
        """)
