from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorType(Enum):
    NO_TRANSCRIPT = "no_transcript"
    YOUTUBE_API_QUOTA = "youtube_api_quota"
    CLAUDE_TOKEN_LIMIT = "claude_token_limit"
    TIMEOUT = "timeout"
    BOT_INACTIVE = "bot_inactive"
    UNKNOWN = "unknown"


@dataclass
class SummaryError:
    error_type: ErrorType
    message: str
    video_title: Optional[str] = None
    video_id: Optional[str] = None

    def to_admin_message(self) -> str:
        """Format error message for admin notification."""
        emoji_map = {
            ErrorType.NO_TRANSCRIPT: "📝",
            ErrorType.YOUTUBE_API_QUOTA: "🔑",
            ErrorType.CLAUDE_TOKEN_LIMIT: "🤖",
            ErrorType.TIMEOUT: "⏱️",
            ErrorType.BOT_INACTIVE: "🔌",
            ErrorType.UNKNOWN: "❓",
        }

        title_map = {
            ErrorType.NO_TRANSCRIPT: "자막 없음",
            ErrorType.YOUTUBE_API_QUOTA: "YouTube API 할당량 초과",
            ErrorType.CLAUDE_TOKEN_LIMIT: "Claude 토큰 한도 초과",
            ErrorType.TIMEOUT: "처리 시간 초과",
            ErrorType.BOT_INACTIVE: "봇 서버 비활성화",
            ErrorType.UNKNOWN: "알 수 없는 오류",
        }

        emoji = emoji_map.get(self.error_type, "❓")
        title = title_map.get(self.error_type, "오류")

        lines = [f"{emoji} <b>오류: {title}</b>"]

        if self.video_title:
            lines.append(f"영상: {self.video_title}")
        if self.video_id:
            lines.append(f"https://youtu.be/{self.video_id}")

        lines.append(f"\n{self.message}")

        # 해결 방법 제안
        solution = self._get_solution()
        if solution:
            lines.append(f"\n💡 <b>해결 방법:</b> {solution}")

        return "\n".join(lines)

    def _get_solution(self) -> str:
        solutions = {
            ErrorType.NO_TRANSCRIPT: "자막이 있는 영상만 요약 가능합니다. 자동 생성 자막도 지원됩니다.",
            ErrorType.YOUTUBE_API_QUOTA: "YouTube API 일일 할당량이 초과되었습니다. 내일 자동으로 복구됩니다.",
            ErrorType.CLAUDE_TOKEN_LIMIT: "Claude API 사용량이 초과되었습니다. 잠시 후 다시 시도하세요.",
            ErrorType.TIMEOUT: "영상이 너무 길어 처리 시간이 초과되었습니다. 짧은 영상을 시도해보세요.",
            ErrorType.BOT_INACTIVE: "봇 서버를 재시작해주세요.",
            ErrorType.UNKNOWN: "로그를 확인하거나 관리자에게 문의하세요.",
        }
        return solutions.get(self.error_type, "")
