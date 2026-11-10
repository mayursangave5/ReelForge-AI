from __future__ import annotations

from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .pipeline import run_slot


def build_scheduler(mock: bool = False) -> BlockingScheduler:
    tz = ZoneInfo(settings.timezone)
    scheduler = BlockingScheduler(timezone=tz)
    for index, hhmm in enumerate(settings.schedule):
        hour, minute = (int(part) for part in hhmm.split(":"))
        scheduler.add_job(
            run_slot,
            CronTrigger(hour=hour, minute=minute, timezone=tz),
            kwargs={"slot": index, "mock": mock},
            id=f"reel_slot_{index}",
            name=f"Reel {index + 1} at {hhmm}",
            coalesce=True,
            misfire_grace_time=3600,
            max_instances=1,
            replace_existing=True,
        )
    return scheduler


def serve(mock: bool = False, run_now: bool = False) -> None:
    scheduler = build_scheduler(mock=mock)
    print(f"\nScheduler ({settings.timezone}):")
    for index, hhmm in enumerate(settings.schedule):
        print(f"  slot {index}: daily at {hhmm}")
    print(
        f"  approval_mode={settings.approval_mode} "
        f"auto_publish={settings.auto_publish}"
    )
    if run_now:
        print("\nRun-now requested...")
        print(run_slot(0, mock=mock))
    print("\nWaiting for scheduled runs. Press Ctrl+C to stop.\n")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")


if __name__ == "__main__":
    from .cli import main

    raise SystemExit(main(["schedule"]))
