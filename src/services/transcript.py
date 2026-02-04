import logging
from typing import Optional, Tuple

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from src.services.errors import ErrorType, SummaryError

logger = logging.getLogger(__name__)

PREFERRED_LANGUAGES = ["ko", "en", "ja"]


def get_transcript(video_id: str) -> Tuple[Optional[str], Optional[SummaryError]]:
    """Fetch transcript for a YouTube video. Returns (transcript, error)."""
    api = YouTubeTranscriptApi()

    try:
        transcript = api.fetch(video_id, languages=PREFERRED_LANGUAGES)
        full_text = " ".join(entry.text for entry in transcript)
        return full_text, None

    except NoTranscriptFound:
        # Try without language preference
        try:
            transcript = api.fetch(video_id)
            full_text = " ".join(entry.text for entry in transcript)
            return full_text, None
        except Exception:
            logger.warning(f"No transcript found for video {video_id}")
            return None, SummaryError(
                error_type=ErrorType.NO_TRANSCRIPT,
                message="이 영상에는 사용 가능한 자막이 없습니다.",
                video_id=video_id,
            )

    except TranscriptsDisabled:
        logger.warning(f"Transcripts are disabled for video {video_id}")
        return None, SummaryError(
            error_type=ErrorType.NO_TRANSCRIPT,
            message="이 영상은 자막이 비활성화되어 있습니다.",
            video_id=video_id,
        )
    except VideoUnavailable:
        logger.warning(f"Video {video_id} is unavailable")
        return None, SummaryError(
            error_type=ErrorType.NO_TRANSCRIPT,
            message="영상을 찾을 수 없거나 비공개 상태입니다.",
            video_id=video_id,
        )
    except Exception as e:
        logger.error(f"Error fetching transcript for {video_id}: {e}")
        return None, SummaryError(
            error_type=ErrorType.UNKNOWN,
            message=f"자막 추출 중 오류 발생: {str(e)}",
            video_id=video_id,
        )
