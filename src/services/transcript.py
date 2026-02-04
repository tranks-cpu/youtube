import logging
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)

PREFERRED_LANGUAGES = ["ko", "en", "ja"]


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript for a YouTube video."""
    api = YouTubeTranscriptApi()

    try:
        transcript = api.fetch(video_id, languages=PREFERRED_LANGUAGES)
        full_text = " ".join(entry.text for entry in transcript)
        return full_text

    except NoTranscriptFound:
        # Try without language preference
        try:
            transcript = api.fetch(video_id)
            full_text = " ".join(entry.text for entry in transcript)
            return full_text
        except Exception:
            logger.warning(f"No transcript found for video {video_id}")
            return None

    except TranscriptsDisabled:
        logger.warning(f"Transcripts are disabled for video {video_id}")
        return None
    except VideoUnavailable:
        logger.warning(f"Video {video_id} is unavailable")
        return None
    except Exception as e:
        logger.error(f"Error fetching transcript for {video_id}: {e}")
        return None
