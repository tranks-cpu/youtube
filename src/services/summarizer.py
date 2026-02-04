import logging
from pathlib import Path
from typing import Optional

from src.db.models import Video
from src.services.claude_cli import call_claude
from src.services.transcript import get_transcript

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


async def summarize_video(video: Video) -> Optional[str]:
    """Summarize a video using Claude CLI."""
    transcript = get_transcript(video.video_id)
    if not transcript:
        logger.warning(f"No transcript available for video {video.video_id}")
        return None

    summary_type = get_summary_type(video.duration_seconds)
    try:
        prompt_template = load_prompt(summary_type)
    except FileNotFoundError as e:
        logger.error(str(e))
        return None

    prompt = prompt_template.format(
        title=video.title,
        video_id=video.video_id,
        duration_minutes=(video.duration_seconds or 0) // 60,
        transcript=transcript,
    )

    summary = await call_claude(prompt)
    if not summary:
        logger.error(f"Failed to generate summary for video {video.video_id}")
        return None

    return summary


async def summarize_by_url(video_url: str) -> tuple[Optional[str], Optional[Video]]:
    """Summarize a video from URL."""
    from src.services.youtube import extract_video_id, get_video_info

    video_id = extract_video_id(video_url)
    if not video_id:
        return None, None

    video = get_video_info(video_id)
    if not video:
        return None, None

    summary = await summarize_video(video)
    return summary, video
