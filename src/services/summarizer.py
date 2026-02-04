import logging
from pathlib import Path
from typing import Optional, Tuple

from src.db.models import Video
from src.services.claude_cli import call_claude
from src.services.transcript import get_transcript
from src.services.errors import ErrorType, SummaryError

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
THRESHOLD_SECONDS = 30 * 60  # 30 minutes


def load_prompt(prompt_type: str) -> str:
    """Load prompt template from file."""
    prompt_file = PROMPTS_DIR / f"{prompt_type}.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


def get_summary_type(duration_seconds: Optional[int]) -> str:
    """Determine summary type based on video duration."""
    if duration_seconds is None or duration_seconds < THRESHOLD_SECONDS:
        return "structured"
    return "detailed"


async def summarize_video(video: Video) -> Tuple[Optional[str], Optional[SummaryError]]:
    """Summarize a video using Claude CLI. Returns (summary, error)."""
    transcript, error = get_transcript(video.video_id)
    if error:
        error.video_title = video.title
        error.video_id = video.video_id
        logger.warning(f"No transcript available for video {video.video_id}")
        return None, error

    if not transcript:
        return None, SummaryError(
            error_type=ErrorType.NO_TRANSCRIPT,
            message="자막을 가져올 수 없습니다.",
            video_title=video.title,
            video_id=video.video_id,
        )

    summary_type = get_summary_type(video.duration_seconds)
    try:
        prompt_template = load_prompt(summary_type)
    except FileNotFoundError as e:
        logger.error(str(e))
        return None, SummaryError(
            error_type=ErrorType.UNKNOWN,
            message=f"프롬프트 파일을 찾을 수 없습니다: {e}",
            video_title=video.title,
            video_id=video.video_id,
        )

    prompt = prompt_template.format(
        title=video.title,
        video_id=video.video_id,
        duration_minutes=(video.duration_seconds or 0) // 60,
        transcript=transcript,
    )

    summary, error = await call_claude(prompt)
    if error:
        error.video_title = video.title
        error.video_id = video.video_id
        logger.error(f"Failed to generate summary for video {video.video_id}")
        return None, error

    return summary, None


async def summarize_by_url(video_url: str) -> Tuple[Optional[str], Optional[Video], Optional[SummaryError]]:
    """Summarize a video from URL. Returns (summary, video, error)."""
    from src.services.youtube import extract_video_id, get_video_info

    video_id = extract_video_id(video_url)
    if not video_id:
        return None, None, SummaryError(
            error_type=ErrorType.UNKNOWN,
            message="올바른 YouTube URL이 아닙니다.",
        )

    video = get_video_info(video_id)
    if not video:
        return None, None, SummaryError(
            error_type=ErrorType.YOUTUBE_API_QUOTA,
            message="영상 정보를 가져올 수 없습니다. API 할당량을 확인하세요.",
            video_id=video_id,
        )

    summary, error = await summarize_video(video)
    return summary, video, error
