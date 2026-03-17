from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import os

scheduler = BackgroundScheduler()
_processor = None


def set_processor(fn):
    global _processor
    _processor = fn


def scheduled_job():
    if _processor:
        print("[Scheduler] Running scheduled email fetch...")
        _processor()
    else:
        print("[Scheduler] No processor registered.")


def start_scheduler(interval_minutes=30):
    if not scheduler.running:
        scheduler.add_job(
            scheduled_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="email_fetch_job",
            name="Fetch and process emails",
            replace_existing=True,
        )
        scheduler.start()
        print(f"[Scheduler] Started. Emails will be fetched every {interval_minutes} minutes.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("[Scheduler] Stopped.")


def get_next_run():
    try:
        job = scheduler.get_job("email_fetch_job")
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
    except Exception:
        pass
    return None