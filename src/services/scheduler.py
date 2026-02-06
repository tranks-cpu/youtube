import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

# 한국 시간대
KST = ZoneInfo("Asia/Seoul")

from src.bot.formatters import fix_html_tags, format_video_summary, split_message
from src.config import Config
from src.db.repositories import (
    ChannelRepository,
    SchedulerStateRepository,
    VideoRepository,
)
from src.services.summarizer import summarize_video
from src.services.youtube import get_latest_videos, is_channel_live

logger = logging.getLogger(__name__)

DAILY_JOB_NAME = "daily_summary_job"


async def run_scheduled_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute the scheduled summary job."""
    state = SchedulerStateRepository.get()
    if state.is_paused:
        logger.info("Scheduler is paused, skipping job")
        return

    logger.info("Starting scheduled job")
    channels = ChannelRepository.get_all()

    for channel in channels:
        logger.info(f"Processing channel: {channel.channel_name}")

        # 채널이 라이브 중이면 스킵 (다음 시간에 다시 체크)
        if is_channel_live(channel.uploads_playlist_id):
            logger.info(f"Channel is live, skipping: {channel.channel_name}")
            continue

        videos = get_latest_videos(channel.uploads_playlist_id, max_results=5)

        for video in videos:
            # 이미 DB에 있으면 스킵 (중복 처리 방지)
            if VideoRepository.exists(video.video_id):
                logger.debug(f"Video already processed: {video.video_id}")
                continue

            # Shorts (60초 이하) 스킵
            if video.duration_seconds and video.duration_seconds <= 60:
                logger.debug(f"Shorts video, skipping: {video.title} ({video.duration_seconds}s)")
                continue

            logger.info(f"New video found: {video.title}")
            VideoRepository.create(video)

            summary, error = await summarize_video(video)
            if error:
                # 관리자에게 에러 알림
                await context.bot.send_message(
                    chat_id=Config.ADMIN_CHAT_ID,
                    text=error.to_admin_message(),
                    parse_mode="HTML",
                )
                logger.warning(f"Failed to summarize: {video.title} - {error.error_type}")
            elif summary:
                from src.bot.formatters import split_summary_for_photo

                message = format_video_summary(video, summary)
                caption, body = split_summary_for_photo(message)
                caption = fix_html_tags(caption)

                # 썸네일 + 캡션 전송
                if video.thumbnail_url:
                    try:
                        await context.bot.send_photo(
                            chat_id=Config.TARGET_CHAT_ID,
                            photo=video.thumbnail_url,
                            caption=caption,
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send thumbnail: {e}")
                        await context.bot.send_message(
                            chat_id=Config.TARGET_CHAT_ID,
                            text=caption,
                            parse_mode="HTML",
                        )
                else:
                    await context.bot.send_message(
                        chat_id=Config.TARGET_CHAT_ID,
                        text=caption,
                        parse_mode="HTML",
                    )

                # 상세 요약 전송
                if body:
                    parts = split_message(body)
                    for part in parts:
                        await context.bot.send_message(
                            chat_id=Config.TARGET_CHAT_ID,
                            text=fix_html_tags(part),
                            parse_mode="HTML",
                        )

                VideoRepository.mark_summarized(video.video_id)
                logger.info(f"Summary sent for: {video.title}")

    SchedulerStateRepository.update_last_run()
    logger.info("Scheduled job completed")


def setup_scheduler(application: Application) -> None:
    """Set up the daily scheduler jobs."""
    job_queue = application.job_queue

    for hour, minute in Config.SCHEDULE_TIMES:
        job_queue.run_daily(
            run_scheduled_job,
            time=time(hour=hour, minute=minute, tzinfo=KST),
            name=f"{DAILY_JOB_NAME}_{hour:02d}{minute:02d}",
        )
    logger.info(f"Scheduler set up for {len(Config.SCHEDULE_TIMES)} jobs (KST timezone)")


def reschedule_daily_job(application: Application, hour: int, minute: int) -> None:
    """Reschedule the daily job to a new time."""
    job_queue = application.job_queue

    current_jobs = job_queue.get_jobs_by_name(DAILY_JOB_NAME)
    for job in current_jobs:
        job.schedule_removal()

    job_queue.run_daily(
        run_scheduled_job,
        time=time(hour=hour, minute=minute, tzinfo=KST),
        name=DAILY_JOB_NAME,
    )
    logger.info(f"Scheduler rescheduled to {hour:02d}:{minute:02d} KST")
