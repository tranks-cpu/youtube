from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Channel:
    id: Optional[int]
    channel_id: str
    channel_name: str
    uploads_playlist_id: str
    created_at: Optional[datetime] = None


@dataclass
class Video:
    id: Optional[int]
    video_id: str
    channel_id: str
    title: str
    duration_seconds: Optional[int] = None
    published_at: Optional[datetime] = None
    summarized_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class SchedulerState:
    id: int
    is_paused: bool
    last_run_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
