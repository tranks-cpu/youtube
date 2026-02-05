import logging
from datetime import time

from telegram.ext import Application, ContextTypes

from src.bot.formatters import fix_html_tags, format_video_summary, split_message
from src.config import Config
from src.db.repositories import (
    ChannelRepository,
    SchedulerStateRepository,
    VideoRepository,
)
from src.services.summarizer import summarize_video
from src.services.youtube import get_latest_videos

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

        # 가장 최근 적재된 영상 날짜 조회
        latest_published = VideoRepository.get_latest_published_at(channel.channel_id)
        logger.info(f"Latest video in DB: {latest_published}")

        videos = get_latest_videos(channel.uploads_playlist_id, max_results=5)

        for video in videos:
            # 이미 DB에 있으면 스킵
            if VideoRepository.exists(video.video_id):
                logger.debug(f"Video already processed: {video.video_id}")
                continue

            # DB에 영상이 있고, 현재 영상이 그보다 오래됐으면 스킵
            if latest_published and video.published_at:
                # timezone-aware 비교를 위해 naive datetime으로 변환
                video_pub = video.published_at.replace(tzinfo=None) if video.published_at.tzinfo else video.published_at
                latest_pub = latest_published.replace(tzinfo=None) if latest_published.tzinfo else latest_published

                if video_pub <= latest_pub:
                    logger.debug(f"Video older than latest in DB, skipping: {video.title}")
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
            time=time(hour=hour, minute=minute),
            name=f"{DAILY_JOB_NAME}_{hour:02d}{minute:02d}",
        )
        logger.info(f"Scheduler set up for {hour:02d}:{minute:02d}")


def reschedule_daily_job(application: Application, hour: int, minute: int) -> None:
    """Reschedule the daily job to a new time."""
    job_queue = application.job_queue

    current_jobs = job_queue.get_jobs_by_name(DAILY_JOB_NAME)
    for job in current_jobs:
        job.schedule_removal()

    job_queue.run_daily(
        run_scheduled_job,
        time=time(hour=hour, minute=minute),
        name=DAILY_JOB_NAME,
    )
    logger.info(f"Scheduler rescheduled to {hour:02d}:{minute:02d}")
