"""Run exactly one scheduler process, separately from the web workers."""
import logging
import os
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    from modules.db.reschedule_repository import run_daily_reschedule_job
    scheduler = BlockingScheduler(
        timezone="Asia/Bangkok", executors={'default': ThreadPoolExecutor(1)},
        job_defaults={'coalesce': True, 'max_instances': 1, 'misfire_grace_time': 3600},
    )
    scheduler.add_job(run_daily_reschedule_job, 'cron', hour=0, minute=5, id='reschedule')
    if os.getenv('LINE_CHANNEL_ACCESS_TOKEN'):
        from modules.line_utils import run_morning_reminder_job
        scheduler.add_job(run_morning_reminder_job, 'cron', hour=8, minute=0, id='reminder')
    scheduler.start()


if __name__ == '__main__':
    main()
