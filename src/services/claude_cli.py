import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 120


async def call_claude(prompt: str, model: str = "sonnet") -> Optional[str]:
    """Call Claude CLI with the given prompt."""
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

        if process.returncode != 0:
            logger.error(f"Claude CLI error: {stderr.decode('utf-8')}")
            return None

        return stdout.decode("utf-8").strip()

    except asyncio.TimeoutError:
        logger.error(f"Claude CLI timeout after {TIMEOUT_SECONDS} seconds")
        if process:
            process.kill()
        return None
    except FileNotFoundError:
        logger.error("Claude CLI not found. Make sure 'claude' is installed and in PATH")
        return None
    except Exception as e:
        logger.error(f"Claude CLI unexpected error: {e}")
        return None
