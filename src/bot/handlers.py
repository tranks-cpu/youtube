import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from src.bot.formatters import (
    format_channel_list,
    format_error,
    format_status,
    format_success,
    format_video_summary,
    split_message,
)
from src.bot.middleware import admin_only
from src.config import Config
from src.db.repositories import (
    ChannelRepository,
    SchedulerStateRepository,
    VideoRepository,
)
from src.services.summarizer import summarize_by_url, summarize_video
from src.services.youtube import get_channel_info

logger = logging.getLogger(__name__)

# Conversation states
WAITING_CHANNEL_URL = 1
WAITING_VIDEO_URL = 2
WAITING_SCHEDULE_TIME = 3
WAITING_REMOVE_CHANNEL = 4


def main_menu_keyboard():
    """Create main menu inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("➕ 채널 추가", callback_data="menu_add_channel"),
            InlineKeyboardButton("➖ 채널 삭제", callback_data="menu_remove_channel"),
        ],
        [
            InlineKeyboardButton("📺 채널 목록", callback_data="menu_list_channels"),
            InlineKeyboardButton("📝 영상 요약", callback_data="menu_summarize"),
        ],
        [
            InlineKeyboardButton("⏰ 시간 설정", callback_data="menu_set_time"),
            InlineKeyboardButton("📊 상태", callback_data="menu_status"),
        ],
        [
            InlineKeyboardButton("⏸ 일시정지", callback_data="menu_pause"),
            InlineKeyboardButton("▶️ 재개", callback_data="menu_resume"),
        ],
        [
            InlineKeyboardButton("🚀 지금 실행", callback_data="menu_run_now"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_button():
    """Create back button keyboard."""
    keyboard = [[InlineKeyboardButton("◀️ 메뉴로 돌아가기", callback_data="menu_back")]]
    return InlineKeyboardMarkup(keyboard)


def cancel_button():
    """Create cancel button keyboard."""
    keyboard = [[InlineKeyboardButton("❌ 취소", callback_data="cancel")]]
    return InlineKeyboardMarkup(keyboard)


@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command - show main menu."""
    await update.message.reply_text(
        "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


@admin_only
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle menu button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "menu_back":
        # 기존 메시지의 버튼만 제거 (내용 보존)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        # 새 메시지로 메뉴 전송
        await query.message.reply_text(
            "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    elif data == "cancel":
        # 기존 메시지의 버튼만 제거
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        # 새 메시지로 메뉴 전송
        await query.message.reply_text(
            "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    elif data == "menu_add_channel":
        await query.edit_message_text(
            "<b>➕ 채널 추가</b>\n\n"
            "추가할 YouTube 채널 URL을 입력하세요.\n\n"
            "예시:\n"
            "• https://youtube.com/@channelname\n"
            "• https://youtube.com/channel/UC...",
            reply_markup=cancel_button(),
            parse_mode="HTML",
        )
        return WAITING_CHANNEL_URL

    elif data == "menu_remove_channel":
        channels = ChannelRepository.get_all()
        if not channels:
            await query.edit_message_text(
                "등록된 채널이 없습니다.",
                reply_markup=back_button(),
                parse_mode="HTML",
            )
            return ConversationHandler.END

        keyboard = []
        for channel in channels:
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑 {channel.channel_name}",
                    callback_data=f"remove_{channel.channel_id}",
                )
            ])
        keyboard.append([InlineKeyboardButton("◀️ 돌아가기", callback_data="menu_back")])

        await query.edit_message_text(
            "<b>➖ 채널 삭제</b>\n\n삭제할 채널을 선택하세요:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
        return WAITING_REMOVE_CHANNEL

    elif data == "menu_list_channels":
        channels = ChannelRepository.get_all()
        await query.edit_message_text(
            format_channel_list(channels),
            reply_markup=back_button(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    elif data == "menu_summarize":
        await query.edit_message_text(
            "<b>📝 영상 요약</b>\n\n"
            "요약할 YouTube 영상 URL을 입력하세요.\n\n"
            "예시:\n"
            "• https://youtu.be/xxxxx\n"
            "• https://youtube.com/watch?v=xxxxx",
            reply_markup=cancel_button(),
            parse_mode="HTML",
        )
        return WAITING_VIDEO_URL

    elif data == "menu_set_time":
        await query.edit_message_text(
            "<b>⏰ 스케줄 시간 설정</b>\n\n"
            "자동 요약 실행 시간을 입력하세요.\n\n"
            "형식: <code>HH:MM</code> (24시간제)\n"
            "예시: <code>09:30</code>, <code>22:00</code>",
            reply_markup=cancel_button(),
            parse_mode="HTML",
        )
        return WAITING_SCHEDULE_TIME

    elif data == "menu_status":
        state = SchedulerStateRepository.get()
        channels = ChannelRepository.get_all()
        last_run = str(state.last_run_at) if state.last_run_at else None

        await query.edit_message_text(
            format_status(
                is_paused=state.is_paused,
                schedule_hour=Config.SCHEDULE_HOUR,
                schedule_minute=Config.SCHEDULE_MINUTE,
                last_run=last_run,
                channel_count=len(channels),
            ),
            reply_markup=back_button(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    elif data == "menu_pause":
        SchedulerStateRepository.set_paused(True)
        await query.edit_message_text(
            format_success("스케줄러가 일시정지되었습니다."),
            reply_markup=back_button(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    elif data == "menu_resume":
        SchedulerStateRepository.set_paused(False)
        await query.edit_message_text(
            format_success("스케줄러가 재개되었습니다."),
            reply_markup=back_button(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    elif data == "menu_run_now":
        await query.edit_message_text(
            "🔄 수동 실행 중...",
            parse_mode="HTML",
        )
        from src.services.scheduler import run_scheduled_job
        await run_scheduled_job(context)
        await query.edit_message_text(
            format_success("수동 실행이 완료되었습니다."),
            reply_markup=back_button(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    return ConversationHandler.END


@admin_only
async def handle_channel_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle channel URL input."""
    url = update.message.text.strip()

    await update.message.reply_text("🔍 채널 정보를 확인하는 중...")

    channel = get_channel_info(url)
    if not channel:
        await update.message.reply_text(
            format_error("채널을 찾을 수 없습니다. 다시 시도해주세요."),
            reply_markup=cancel_button(),
            parse_mode="HTML",
        )
        return WAITING_CHANNEL_URL

    existing = ChannelRepository.get_by_channel_id(channel.channel_id)
    if existing:
        await update.message.reply_text(
            format_error(f"이미 등록된 채널입니다: {existing.channel_name}"),
            parse_mode="HTML",
        )
        await update.message.reply_text(
            "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    ChannelRepository.create(channel)
    await update.message.reply_text(
        format_success(f"채널이 추가되었습니다!\n\n📺 {channel.channel_name}"),
        parse_mode="HTML",
    )
    await update.message.reply_text(
        "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


@admin_only
async def handle_video_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle video URL input for summarization."""
    url = update.message.text.strip()

    await update.message.reply_text("📝 요약을 생성하는 중... (최대 3분 소요)")

    summary, video, error = await summarize_by_url(url)

    if error:
        await update.message.reply_text(
            error.to_admin_message(),
            parse_mode="HTML",
        )
        await update.message.reply_text(
            "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if not video or not summary:
        await update.message.reply_text(
            format_error("요약 생성에 실패했습니다."),
            parse_mode="HTML",
        )
        await update.message.reply_text(
            "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    message = format_video_summary(video, summary)
    parts = split_message(message)

    # 채널로 요약 전송
    for part in parts:
        await context.bot.send_message(
            chat_id=Config.TARGET_CHAT_ID,
            text=part,
            parse_mode="HTML",
        )

    # 관리자에게 완료 알림
    await update.message.reply_text(
        format_success("요약이 채널로 전송되었습니다!"),
        parse_mode="HTML",
    )
    await update.message.reply_text(
        "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

    return ConversationHandler.END


@admin_only
async def handle_schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle schedule time input."""
    text = update.message.text.strip()

    try:
        if ":" in text:
            hour, minute = text.split(":")
        else:
            hour, minute = text.split()

        hour = int(hour)
        minute = int(minute)

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError()

    except (ValueError, IndexError):
        await update.message.reply_text(
            format_error("올바른 형식으로 입력해주세요. (예: 09:30)"),
            reply_markup=cancel_button(),
            parse_mode="HTML",
        )
        return WAITING_SCHEDULE_TIME

    from src.services.scheduler import reschedule_daily_job
    reschedule_daily_job(context.application, hour, minute)

    await update.message.reply_text(
        format_success(f"스케줄 시간이 {hour:02d}:{minute:02d}로 변경되었습니다."),
        parse_mode="HTML",
    )
    await update.message.reply_text(
        "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


@admin_only
async def handle_remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle channel removal callback."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "menu_back":
        # 기존 메시지의 버튼만 제거
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        # 새 메시지로 메뉴 전송
        await query.message.reply_text(
            "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data.startswith("remove_"):
        channel_id = data[7:]
        channel = ChannelRepository.get_by_channel_id(channel_id)

        if channel:
            ChannelRepository.delete(channel_id)
            # 기존 메시지 수정
            await query.edit_message_text(
                format_success(f"채널이 삭제되었습니다: {channel.channel_name}"),
                parse_mode="HTML",
            )
            # 새 메시지로 메뉴 전송
            await query.message.reply_text(
                "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text(
                format_error("채널을 찾을 수 없습니다."),
                reply_markup=back_button(),
                parse_mode="HTML",
            )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation."""
    await update.message.reply_text(
        "<b>🎬 YouTube 요약 봇</b>\n\n원하는 작업을 선택하세요:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


# Legacy command handlers for direct commands
@admin_only
async def cmd_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add_channel command."""
    if not context.args:
        await update.message.reply_text(
            "<b>➕ 채널 추가</b>\n\n"
            "추가할 YouTube 채널 URL을 입력하세요.\n\n"
            "사용법: /add_channel <URL>",
            parse_mode="HTML",
        )
        return

    url = context.args[0]
    channel = get_channel_info(url)

    if not channel:
        await update.message.reply_text(
            format_error("채널을 찾을 수 없습니다."),
            parse_mode="HTML",
        )
        return

    existing = ChannelRepository.get_by_channel_id(channel.channel_id)
    if existing:
        await update.message.reply_text(
            format_error(f"이미 등록된 채널입니다: {existing.channel_name}"),
            parse_mode="HTML",
        )
        return

    ChannelRepository.create(channel)
    await update.message.reply_text(
        format_success(f"채널 추가됨: {channel.channel_name}"),
        parse_mode="HTML",
    )


@admin_only
async def cmd_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /summarize command."""
    if not context.args:
        await update.message.reply_text(
            "<b>📝 영상 요약</b>\n\n사용법: /summarize <영상 URL>",
            parse_mode="HTML",
        )
        return

    url = context.args[0]
    await update.message.reply_text("📝 요약을 생성하는 중... (최대 3분 소요)")

    summary, video, error = await summarize_by_url(url)

    if error:
        await update.message.reply_text(
            error.to_admin_message(),
            parse_mode="HTML",
        )
        return

    if not video or not summary:
        await update.message.reply_text(
            format_error("요약 생성에 실패했습니다."),
            parse_mode="HTML",
        )
        return

    message = format_video_summary(video, summary)
    parts = split_message(message)

    # 채널로 요약 전송
    for part in parts:
        await context.bot.send_message(
            chat_id=Config.TARGET_CHAT_ID,
            text=part,
            parse_mode="HTML",
        )

    # 관리자에게 완료 알림
    await update.message.reply_text(
        format_success("요약이 채널로 전송되었습니다!"),
        parse_mode="HTML",
    )
