from datetime import datetime
from typing import Optional

from src.db.database import get_db
from src.db.models import Channel, Video, SchedulerState


class ChannelRepository:
    @staticmethod
    def create(channel: Channel) -> Channel:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO channels (channel_id, channel_name, uploads_playlist_id)
                VALUES (?, ?, ?)
                """,
                (channel.channel_id, channel.channel_name, channel.uploads_playlist_id),
            )
            channel.id = cursor.lastrowid
            return channel

    @staticmethod
    def get_by_channel_id(channel_id: str) -> Optional[Channel]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)
            )
            row = cursor.fetchone()
            if row:
                return Channel(
                    id=row["id"],
                    channel_id=row["channel_id"],
                    channel_name=row["channel_name"],
                    uploads_playlist_id=row["uploads_playlist_id"],
                    created_at=row["created_at"],
                )
            return None

    @staticmethod
    def get_all() -> list[Channel]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channels ORDER BY created_at")
            return [
                Channel(
                    id=row["id"],
                    channel_id=row["channel_id"],
                    channel_name=row["channel_name"],
                    uploads_playlist_id=row["uploads_playlist_id"],
                    created_at=row["created_at"],
                )
                for row in cursor.fetchall()
            ]

    @staticmethod
    def delete(channel_id: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
            return cursor.rowcount > 0


class VideoRepository:
    @staticmethod
    def create(video: Video) -> Video:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO videos (video_id, channel_id, title, duration_seconds, published_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    video.video_id,
                    video.channel_id,
                    video.title,
                    video.duration_seconds,
                    video.published_at,
                ),
            )
            video.id = cursor.lastrowid
            return video

    @staticmethod
    def get_by_video_id(video_id: str) -> Optional[Video]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            if row:
                return Video(
                    id=row["id"],
                    video_id=row["video_id"],
                    channel_id=row["channel_id"],
                    title=row["title"],
                    duration_seconds=row["duration_seconds"],
                    published_at=row["published_at"],
                    summarized_at=row["summarized_at"],
                    created_at=row["created_at"],
                )
            return None

    @staticmethod
    def exists(video_id: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM videos WHERE video_id = ?", (video_id,)
            )
            return cursor.fetchone() is not None

    @staticmethod
    def mark_summarized(video_id: str) -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE videos SET summarized_at = ? WHERE video_id = ?",
                (datetime.now(), video_id),
            )

    @staticmethod
    def get_unsummarized_videos() -> list[Video]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM videos
                WHERE summarized_at IS NULL
                ORDER BY published_at DESC
                """
            )
            return [
                Video(
                    id=row["id"],
                    video_id=row["video_id"],
                    channel_id=row["channel_id"],
                    title=row["title"],
                    duration_seconds=row["duration_seconds"],
                    published_at=row["published_at"],
                    summarized_at=row["summarized_at"],
                    created_at=row["created_at"],
                )
                for row in cursor.fetchall()
            ]

    @staticmethod
    def get_latest_published_at(channel_id: str) -> Optional[datetime]:
        """Get the most recent published_at date for a channel."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT MAX(published_at) as latest
                FROM videos
                WHERE channel_id = ?
                """,
                (channel_id,),
            )
            row = cursor.fetchone()
            if row and row["latest"]:
                # Handle string or datetime
                latest = row["latest"]
                if isinstance(latest, str):
                    return datetime.fromisoformat(latest.replace("Z", "+00:00"))
                return latest
            return None


class SchedulerStateRepository:
    @staticmethod
    def get() -> SchedulerState:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scheduler_state WHERE id = 1")
            row = cursor.fetchone()
            return SchedulerState(
                id=row["id"],
                is_paused=bool(row["is_paused"]),
                last_run_at=row["last_run_at"],
                updated_at=row["updated_at"],
            )

    @staticmethod
    def set_paused(is_paused: bool) -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE scheduler_state
                SET is_paused = ?, updated_at = ?
                WHERE id = 1
                """,
                (is_paused, datetime.now()),
            )

    @staticmethod
    def update_last_run() -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE scheduler_state
                SET last_run_at = ?, updated_at = ?
                WHERE id = 1
                """,
                (datetime.now(), datetime.now()),
            )
