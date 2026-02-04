import asyncio
import logging
from typing import Optional, Tuple

from src.services.errors import ErrorType, SummaryError

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 180  # 3분으로 증가


async def call_claude(prompt: str, model: str = "sonnet") -> Tuple[Optional[str], Optional[SummaryError]]:
    """Call Claude CLI with the given prompt. Returns (result, error)."""
    process = None

    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            "--model",
            model,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=prompt.encode("utf-8")),
            timeout=TIMEOUT_SECONDS,
        )

        stderr_text = stderr.decode("utf-8")

        if process.returncode != 0:
            logger.error(f"Claude CLI error: {stderr_text}")

            # 토큰/사용량 초과 감지
            if "rate" in stderr_text.lower() or "limit" in stderr_text.lower() or "quota" in stderr_text.lower():
                return None, SummaryError(
                    error_type=ErrorType.CLAUDE_TOKEN_LIMIT,
                    message="Claude API 사용량 한도에 도달했습니다.",
                )

            return None, SummaryError(
                error_type=ErrorType.UNKNOWN,
                message=f"Claude 실행 오류: {stderr_text[:200]}",
            )

        return stdout.decode("utf-8").strip(), None

    except asyncio.TimeoutError:
        logger.error(f"Claude CLI timeout after {TIMEOUT_SECONDS} seconds")
        if process:
            try:
                process.kill()
            except Exception:
                pass
        return None, SummaryError(
            error_type=ErrorType.TIMEOUT,
            message=f"요약 생성이 {TIMEOUT_SECONDS}초를 초과하여 중단되었습니다.",
        )
    except FileNotFoundError:
        logger.error("Claude CLI not found. Make sure 'claude' is installed and in PATH")
        return None, SummaryError(
            error_type=ErrorType.BOT_INACTIVE,
            message="Claude CLI가 설치되어 있지 않습니다.",
        )
    except Exception as e:
        logger.error(f"Claude CLI unexpected error: {e}")
        return None, SummaryError(
            error_type=ErrorType.UNKNOWN,
            message=f"예상치 못한 오류: {str(e)}",
        )
