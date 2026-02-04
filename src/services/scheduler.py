import logging
from datetime import time

from telegram.ext import Application, ContextTypes

from src.bot.formatters import format_video_summary, split_message
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

        videos = get_latest_videos(channel.uploads_playlist_id, max_results=5)

        for video in videos:
            if VideoRepository.exists(video.video_id):
                logger.debug(f"Video already processed: {video.video_id}")
                continue

            logger.info(f"New video found: {video.title}")
            VideoRepository.create(video)

            summary = await summarize_video(video)
            if summary:
                message = format_video_summary(video, summary)
                parts = split_message(message)

                for part in parts:
                    await context.bot.send_message(
                        chat_id=Config.TARGET_CHAT_ID,
                        text=part,
                    )

                VideoRepository.mark_summarized(video.video_id)
                logger.info(f"Summary sent for: {video.title}")
            else:
                logger.warning(f"Failed to summarize: {video.title}")

    SchedulerStateRepository.update_last_run()
    logger.info("Scheduled job completed")


def setup_scheduler(application: Application) -> None:
    """Set up the daily scheduler job."""
    job_queue = application.job_queue

    job_queue.run_daily(
        run_scheduled_job,
        time=time(hour=Config.SCHEDULE_HOUR, minute=Config.SCHEDULE_MINUTE),
        name=DAILY_JOB_NAME,
    )
    logger.info(
        f"Scheduler set up for {Config.SCHEDULE_HOUR:02d}:{Config.SCHEDULE_MINUTE:02d}"
    )


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
