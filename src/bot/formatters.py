from typing import Optional

from src.db.models import Channel, Video

TELEGRAM_MAX_LENGTH = 4096


def escape_html(text: str) -> str:
    """Escape only necessary HTML special characters for Telegram."""
    # Telegram only requires &, <, > to be escaped
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Split long message into multiple parts."""
    if len(text) <= max_length:
        return [text]

    parts = []
    current = ""

    paragraphs = text.split("\n\n")
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_length:
            current += para + "\n\n"
        else:
            if current:
                parts.append(current.strip())
            if len(para) > max_length:
                words = para.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= max_length:
                        current += word + " "
                    else:
                        if current:
                            parts.append(current.strip())
                        current = word + " "
            else:
                current = para + "\n\n"

    if current.strip():
        parts.append(current.strip())

    return parts if parts else [text[:max_length]]


def format_video_summary(video: Video, summary: str) -> str:
    """Format video summary message with HTML."""
    duration_str = ""
    if video.duration_seconds:
        minutes = video.duration_seconds // 60
        seconds = video.duration_seconds % 60
        duration_str = f" ({minutes}:{seconds:02d})"

    title = escape_html(video.title)

    # Clean up Claude's output for Telegram HTML
    formatted_summary = clean_summary_html(summary)

    header = (
        f"<b>{title}</b>{duration_str}\n"
        f"https://youtu.be/{video.video_id}\n\n"
    )
    return header + formatted_summary


def clean_summary_html(text: str) -> str:
    """Clean and convert summary to valid Telegram HTML."""
    import re

    # 1. 먼저 잘못된 HTML 엔티티 복원
    text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")

    # 2. 마크다운 **bold**를 HTML로 변환 (Claude가 혼용할 수 있음)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # 3. 특수 문자 이스케이프 (태그 내부가 아닌 텍스트만)
    # & 를 먼저 처리 (이미 &amp; 등으로 되어있지 않은 경우만)
    text = re.sub(r'&(?!amp;|lt;|gt;|quot;)', '&amp;', text)

    # 4. 텔레그램에서 지원하지 않는 HTML 태그 제거
    # 지원: b, i, u, s, code, pre, a
    allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a']

    # 5. 빈 태그 제거 <b></b>
    text = re.sub(r'<b>\s*</b>', '', text)

    return text


def convert_markdown_to_html(text: str) -> str:
    """Convert markdown formatting to Telegram HTML."""
    lines = text.split('\n')
    result = []

    for line in lines:
        # Headers: ## -> bold
        if line.startswith('#### '):
            line = f"<b>{escape_html(line[5:])}</b>"
        elif line.startswith('### '):
            line = f"<b>{escape_html(line[4:])}</b>"
        elif line.startswith('## '):
            line = f"\n<b>📌 {escape_html(line[3:])}</b>"
        elif line.startswith('# '):
            line = f"\n<b>📌 {escape_html(line[2:])}</b>"
        # Bold: **text** -> <b>text</b>
        elif '**' in line:
            import re
            line = escape_html(line)
            # After escaping, ** becomes ** still, so we can replace
            parts = line.split('**')
            if len(parts) >= 3:
                new_line = parts[0]
                for i in range(1, len(parts)):
                    if i % 2 == 1:
                        new_line += '<b>'
                    else:
                        new_line += '</b>'
                    new_line += parts[i]
                line = new_line
        # List items: - item -> • item
        elif line.strip().startswith('- '):
            indent = len(line) - len(line.lstrip())
            content = line.strip()[2:]
            # Handle **bold** in list items
            if '**' in content:
                parts = content.split('**')
                if len(parts) >= 3:
                    new_content = parts[0]
                    for i in range(1, len(parts)):
                        if i % 2 == 1:
                            new_content += '<b>'
                        else:
                            new_content += '</b>'
                        new_content += escape_html(parts[i]) if i % 2 == 0 else parts[i]
                    content = new_content
                else:
                    content = escape_html(content)
            else:
                content = escape_html(content)
            line = ' ' * (indent // 2) + '• ' + content
        # Numbered items
        elif line.strip() and line.strip()[0].isdigit() and '. ' in line:
            line = escape_html(line)
        else:
            line = escape_html(line)

        result.append(line)

    return '\n'.join(result)


def format_channel_list(channels: list[Channel]) -> str:
    """Format channel list message with HTML."""
    if not channels:
        return "등록된 채널이 없습니다."

    lines = ["<b>📺 등록된 채널 목록</b>\n"]
    for i, channel in enumerate(channels, 1):
        name = escape_html(channel.channel_name)
        lines.append(f"{i}. {name}")
        lines.append(f"   <code>{channel.channel_id}</code>")
    return "\n".join(lines)


def format_status(
    is_paused: bool,
    schedule_hour: int,
    schedule_minute: int,
    last_run: Optional[str],
    channel_count: int,
) -> str:
    """Format status message with HTML."""
    status = "⏸ 일시정지" if is_paused else "▶️ 실행 중"
    schedule = f"{schedule_hour:02d}:{schedule_minute:02d}"
    last_run_str = last_run or "없음"

    return (
        f"<b>📊 스케줄러 상태</b>\n\n"
        f"상태: {status}\n"
        f"예약 시간: 매일 {schedule}\n"
        f"마지막 실행: {last_run_str}\n"
        f"등록된 채널: {channel_count}개"
    )


def format_error(message: str) -> str:
    """Format error message."""
    return f"❌ {escape_html(message)}"


def format_success(message: str) -> str:
    """Format success message."""
    return f"✅ {escape_html(message)}"
