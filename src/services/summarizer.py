import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from src.db.models import Video
from src.services.claude_cli import call_claude
from src.services.transcript import get_transcript
from src.services.errors import ErrorType, SummaryError

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
THRESHOLD_SECONDS = 30 * 60  # 30 minutes


def load_prompt() -> str:
    """Load prompt template from file."""
    prompt_file = PROMPTS_DIR / "summary.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


def format_duration(seconds: Optional[int]) -> str:
    """Format duration as human readable string."""
    if not seconds:
        return "알 수 없음"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}시간 {minutes}분 {secs}초"
    elif minutes > 0:
        return f"{minutes}분 {secs}초"
    return f"{secs}초"


def get_min_sections(duration_seconds: Optional[int]) -> int:
    """Determine minimum sections based on video duration."""
    if duration_seconds is None:
        return 6
    if duration_seconds < 10 * 60:  # 10분 미만
        return 3
    if duration_seconds < 30 * 60:  # 30분 미만
        return 6
    if duration_seconds < 60 * 60:  # 1시간 미만
        return 8
    return 10  # 1시간 이상


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

    try:
        prompt_template = load_prompt()
    except FileNotFoundError as e:
        logger.error(str(e))
        return None, SummaryError(
            error_type=ErrorType.UNKNOWN,
            message=f"프롬프트 파일을 찾을 수 없습니다: {e}",
            video_title=video.title,
            video_id=video.video_id,
        )

    # 메타 정보 포맷팅
    now = datetime.now()
    if video.published_at:
        if isinstance(video.published_at, str):
            uploaded_at = video.published_at[:10]
        else:
            uploaded_at = video.published_at.strftime("%Y-%m-%d")
    else:
        uploaded_at = "알 수 없음"
    summarized_at = now.strftime("%Y-%m-%d %H:%M")

    prompt = prompt_template.format(
        title=video.title,
        video_id=video.video_id,
        channel_name=video.channel_name or "알 수 없음",
        runtime=format_duration(video.duration_seconds),
        uploaded_at=uploaded_at,
        summarized_at=summarized_at,
        min_sections=get_min_sections(video.duration_seconds),
        transcript=transcript,
    )

    summary, error = await call_claude(prompt)
    if error:
        error.video_title = video.title
        error.video_id = video.video_id
        logger.error(f"Failed to generate summary for video {video.video_id}")
        return None, error

    # 앞뒤 불필요한 텍스트 제거 및 HTML 태그 수정
    from src.bot.formatters import fix_html_tags
    import re

    summary = clean_summary_output(summary)

    # & 문자 이스케이프 (이미 &amp; 등으로 되어있지 않은 경우만)
    summary = re.sub(r'&(?!amp;|lt;|gt;|quot;)', '&amp;', summary)

    # 닫히지 않은 HTML 태그 수정
    summary = fix_html_tags(summary)

    return summary, None


def clean_summary_output(text: str) -> str:
    """Remove unwanted text before/after the actual summary."""
    # "📺 YouTube"로 시작하도록 앞부분 제거
    marker_start = "📺 YouTube"
    if marker_start in text:
        idx = text.find(marker_start)
        text = text[idx:]

    # 마지막 불릿 포인트 이후의 설명 제거
    lines = text.split("\n")
    result_lines = []
    last_content_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        # 실제 콘텐츠가 있는 라인 추적
        if stripped and (
            stripped.startswith("📺") or
            stripped.startswith("▶️") or
            stripped.startswith("🔗") or
            stripped.startswith("📅") or
            stripped.startswith("⏱️") or
            stripped.startswith("📌") or
            stripped.startswith("🏷️") or
            stripped.startswith("📖") or
            stripped.startswith("•") or
            (stripped and not stripped.startswith("---") and not stripped.lower().startswith("this "))
        ):
            last_content_idx = i
        result_lines.append(line)

    # "---" 이후나 영어 설명 문장 제거
    final_lines = []
    for line in result_lines[:last_content_idx + 1]:
        if line.strip() == "---":
            break
        if line.strip().lower().startswith("this summary") or line.strip().lower().startswith("based on"):
            continue
        final_lines.append(line)

    return "\n".join(final_lines).strip()


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
