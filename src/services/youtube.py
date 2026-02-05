import logging
import re
from datetime import datetime
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import Config
from src.db.models import Channel, Video

logger = logging.getLogger(__name__)


def get_youtube_client():
    return build("youtube", "v3", developerKey=Config.YOUTUBE_API_KEY)


def parse_duration(duration: str) -> int:
    """Parse ISO 8601 duration to seconds."""
    pattern = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
    match = pattern.match(duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def extract_channel_identifier(url: str) -> Optional[tuple[str, str]]:
    """Extract channel identifier from URL. Returns (type, value)."""
    patterns = [
        (r"youtube\.com/channel/([A-Za-z0-9_-]+)", "channel_id"),
        (r"youtube\.com/@([A-Za-z0-9_-]+)", "handle"),
        (r"youtube\.com/c/([A-Za-z0-9_-]+)", "custom_url"),
        (r"youtube\.com/user/([A-Za-z0-9_-]+)", "username"),
    ]
    for pattern, id_type in patterns:
        match = re.search(pattern, url)
        if match:
            return (id_type, match.group(1))
    return None


def get_channel_info(url: str) -> Optional[Channel]:
    """Get channel information from URL."""
    try:
        youtube = get_youtube_client()
        identifier = extract_channel_identifier(url)

        if not identifier:
            logger.error(f"Could not parse channel URL: {url}")
            return None

        id_type, value = identifier

        if id_type == "channel_id":
            response = youtube.channels().list(
                part="snippet,contentDetails",
                id=value,
            ).execute()
        elif id_type == "handle":
            response = youtube.channels().list(
                part="snippet,contentDetails",
                forHandle=value,
            ).execute()
        elif id_type == "username":
            response = youtube.channels().list(
                part="snippet,contentDetails",
                forUsername=value,
            ).execute()
        else:
            response = youtube.search().list(
                part="snippet",
                q=value,
                type="channel",
                maxResults=1,
            ).execute()
            if response.get("items"):
                channel_id = response["items"][0]["snippet"]["channelId"]
                response = youtube.channels().list(
                    part="snippet,contentDetails",
                    id=channel_id,
                ).execute()

        if not response.get("items"):
            logger.error(f"Channel not found: {url}")
            return None

        item = response["items"][0]
        return Channel(
            id=None,
            channel_id=item["id"],
            channel_name=item["snippet"]["title"],
            uploads_playlist_id=item["contentDetails"]["relatedPlaylists"]["uploads"],
        )

    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting channel info: {e}")
        return None


def get_video_info(video_id: str) -> Optional[Video]:
    """Get video information by ID."""
    try:
        youtube = get_youtube_client()
        response = youtube.videos().list(
            part="snippet,contentDetails",
            id=video_id,
        ).execute()

        if not response.get("items"):
            return None

        item = response["items"][0]
        snippet = item["snippet"]
        published_at = datetime.fromisoformat(
            snippet["publishedAt"].replace("Z", "+00:00")
        )

        # 썸네일 URL (고화질 우선)
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        )

        return Video(
            id=None,
            video_id=video_id,
            channel_id=snippet["channelId"],
            title=snippet["title"],
            duration_seconds=parse_duration(item["contentDetails"]["duration"]),
            published_at=published_at,
            channel_name=snippet["channelTitle"],
            thumbnail_url=thumbnail_url,
        )

    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_latest_videos(uploads_playlist_id: str, max_results: int = 10) -> list[Video]:
    """Get latest videos from uploads playlist."""
    try:
        youtube = get_youtube_client()
        response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=max_results,
        ).execute()

        videos = []
        video_ids = [
            item["snippet"]["resourceId"]["videoId"]
            for item in response.get("items", [])
        ]

        if not video_ids:
            return []

        details_response = youtube.videos().list(
            part="snippet,contentDetails",
            id=",".join(video_ids),
        ).execute()

        for item in details_response.get("items", []):
            snippet = item["snippet"]

            # 라이브 진행 중이거나 예정된 영상은 스킵
            live_status = snippet.get("liveBroadcastContent", "none")
            if live_status in ("live", "upcoming"):
                logger.debug(f"Skipping live/upcoming: {snippet['title']} ({live_status})")
                continue

            published_at = datetime.fromisoformat(
                snippet["publishedAt"].replace("Z", "+00:00")
            )
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("maxres", {}).get("url")
                or thumbnails.get("high", {}).get("url")
                or thumbnails.get("medium", {}).get("url")
                or f"https://img.youtube.com/vi/{item['id']}/hqdefault.jpg"
            )
            videos.append(
                Video(
                    id=None,
                    video_id=item["id"],
                    channel_id=snippet["channelId"],
                    title=snippet["title"],
                    duration_seconds=parse_duration(item["contentDetails"]["duration"]),
                    published_at=published_at,
                    channel_name=snippet["channelTitle"],
                    thumbnail_url=thumbnail_url,
                )
            )

        return videos

    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error getting latest videos: {e}")
        return []
