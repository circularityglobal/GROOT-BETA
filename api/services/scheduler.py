"""
REFINET Cloud — Task Scheduler Service
Configurable cron/interval task scheduler.
Replaces hardcoded asyncio.sleep loops with a managed, DB-backed system.
Zero external dependencies — uses SQLite + lightweight cron parser.
"""

import asyncio
import importlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from api.models.internal import ScheduledTask

logger = logging.getLogger("refinet.scheduler")


# ── Lightweight Cron Parser ──────────────────────────────────────

def parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    """Parse a single cron field (e.g., '*/5', '1,15', '1-5')."""
    if field == '*':
        return set(range(min_val, max_val + 1))

    values = set()
    for part in field.split(','):
        if '/' in part:
            base, step = part.split('/', 1)
            step = int(step)
            if base == '*':
                start = min_val
            else:
                start = int(base)
            values.update(range(start, max_val + 1, step))
        elif '-' in part:
            start, end = part.split('-', 1)
            values.update(range(int(start), int(end) + 1))
        else:
            values.add(int(part))

    return values


def cron_matches(expression: str, dt: datetime) -> bool:
    """
    Check if a datetime matches a 5-field cron expression.
    Format: minute hour day-of-month month day-of-week
    """
    fields = expression.strip().split()
    if len(fields) != 5:
        return False

    try:
        minutes = parse_cron_field(fields[0], 0, 59)
        hours = parse_cron_field(fields[1], 0, 23)
        days = parse_cron_field(fields[2], 1, 31)
        months = parse_cron_field(fields[3], 1, 12)
        weekdays = parse_cron_field(fields[4], 0, 6)  # 0=Sunday
    except (ValueError, IndexError):
        return False

    # Python weekday: Monday=0, but cron: Sunday=0
    cron_weekday = (dt.weekday() + 1) % 7

    return (
        dt.minute in minutes
        and dt.hour in hours
        and dt.day in days
        and dt.month in months
        and cron_weekday in weekdays
    )


def next_cron_run(expression: str, after: datetime) -> Optional[datetime]:
    """Find the next datetime that matches a cron expression (within 48 hours)."""
    check = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    max_check = after + timedelta(hours=48)

    while check < max_check:
        if cron_matches(expression, check):
            return check
        check += timedelta(minutes=1)

    return None


# ── Scheduler Singleton ──────────────────────────────────────────

class TaskScheduler:
    """
    Singleton task scheduler that runs as a background asyncio task.
    Checks for due tasks every 10 seconds and dispatches them.
    """

    _instance = None
    _running = False

    @classmethod
    def get(cls) -> "TaskScheduler":
        if cls._instance is None:
            cls._instance = TaskScheduler()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None
        cls._running = False

    async def start(self):
        """Start the scheduler master loop."""
        if TaskScheduler._running:
            return
        TaskScheduler._running = True
        logger.info("Scheduler started")

        while TaskScheduler._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}")
            await asyncio.sleep(10)

    async def stop(self):
        """Stop the scheduler."""
        TaskScheduler._running = False
        logger.info("Scheduler stopped")

    async def _tick(self):
        """Check all enabled tasks and fire those that are due."""
        from api.database import get_internal_session

        now = datetime.now(timezone.utc)

        with get_internal_session() as db:
            tasks = db.query(ScheduledTask).filter(
                ScheduledTask.is_enabled == True,  # noqa: E712
            ).all()

            for task in tasks:
                if self._is_due(task, now):
                    asyncio.create_task(self._execute(task.name, task.handler_path, task.handler_args))
                    task.last_run_at = now
                    task.run_count += 1
                    self._compute_next_run(task, now)
                    db.flush()

            db.commit()

    def _is_due(self, task: ScheduledTask, now: datetime) -> bool:
        """Check if a task is due to run."""
        if task.next_run_at and task.next_run_at <= now:
            return True

        # First run — no next_run_at set yet
        if task.next_run_at is None:
            if task.task_type == "interval":
                return task.last_run_at is None
            elif task.task_type == "cron":
                return cron_matches(task.schedule, now)
            elif task.task_type == "once":
                return task.run_count == 0

        return False

    def _compute_next_run(self, task: ScheduledTask, now: datetime):
        """Compute the next run time for a task."""
        if task.task_type == "interval":
            try:
                interval_seconds = int(task.schedule)
                task.next_run_at = now + timedelta(seconds=interval_seconds)
            except ValueError:
                task.is_enabled = False

        elif task.task_type == "cron":
            next_time = next_cron_run(task.schedule, now)
            task.next_run_at = next_time
            if not next_time:
                logger.warning(f"Task {task.name}: no next cron match found within 48h")

        elif task.task_type == "once":
            task.is_enabled = False  # Disable after single run

    async def _execute(self, task_name: str, handler_path: str, handler_args: Optional[str]):
        """Execute a scheduled task by dynamically importing and calling the handler."""
        try:
            module_path, func_name = handler_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            handler = getattr(module, func_name)

            args = {}
            if handler_args:
                import json
                args = json.loads(handler_args)

            # Call handler — it may need a DB session
            if asyncio.iscoroutinefunction(handler):
                await handler(**args)
            else:
                handler(**args)

            # Update result
            self._update_result(task_name, "success", None)
            logger.debug(f"Scheduled task '{task_name}' completed successfully")

        except Exception as e:
            self._update_result(task_name, "error", str(e))
            logger.error(f"Scheduled task '{task_name}' failed: {e}")

    def _update_result(self, task_name: str, result: str, error: Optional[str]):
        """Update the last_result and last_error for a task."""
        try:
            from api.database import get_internal_session
            with get_internal_session() as db:
                task = db.query(ScheduledTask).filter(
                    ScheduledTask.name == task_name,
                ).first()
                if task:
                    task.last_result = result
                    task.last_error = error
                    task.updated_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception as e:
            logger.error(f"Failed to update task result for {task_name}: {e}")


# ── CRUD for Admin API ───────────────────────────────────────────

def list_scheduled_tasks(db: Session) -> list[dict]:
    """List all scheduled tasks."""
    tasks = db.query(ScheduledTask).order_by(ScheduledTask.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "task_type": t.task_type,
            "schedule": t.schedule,
            "handler_path": t.handler_path,
            "is_enabled": t.is_enabled,
            "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
            "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None,
            "last_result": t.last_result,
            "run_count": t.run_count,
        }
        for t in tasks
    ]


def create_scheduled_task(
    db: Session,
    name: str,
    task_type: str,
    schedule: str,
    handler_path: str,
    handler_args: Optional[str] = None,
    created_by: Optional[str] = None,
) -> ScheduledTask:
    """Create a new scheduled task."""
    task = ScheduledTask(
        name=name,
        task_type=task_type,
        schedule=schedule,
        handler_path=handler_path,
        handler_args=handler_args,
        is_enabled=True,
        created_by=created_by,
    )
    db.add(task)
    db.flush()
    return task


def toggle_scheduled_task(db: Session, task_id: str, enabled: bool) -> bool:
    """Enable or disable a scheduled task."""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        return False
    task.is_enabled = enabled
    task.updated_at = datetime.now(timezone.utc)
    db.flush()
    return True


def delete_scheduled_task(db: Session, task_id: str) -> bool:
    """Delete a scheduled task."""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        return False
    db.delete(task)
    db.flush()
    return True


# ── Default Tasks Seeder ─────────────────────────────────────────

def seed_default_tasks(db: Session):
    """Seed default scheduled tasks if they don't exist."""
    defaults = [
        {
            "name": "p2p_cleanup",
            "task_type": "interval",
            "schedule": "60",
            "handler_path": "api.services.scheduler.p2p_cleanup_handler",
        },
        {
            "name": "health_monitor",
            "task_type": "interval",
            "schedule": "60",
            "handler_path": "api.services.scheduler.health_check_handler",
        },
        {
            "name": "auth_cleanup",
            "task_type": "interval",
            "schedule": "3600",
            "handler_path": "api.services.scheduler.auth_cleanup_handler",
        },
        {
            "name": "agent_memory_cleanup",
            "task_type": "interval",
            "schedule": "300",
            "handler_path": "api.services.scheduler.memory_cleanup_handler",
        },
        {
            "name": "api_counter_reset",
            "task_type": "interval",
            "schedule": "86400",
            "handler_path": "api.services.scheduler.api_counter_reset_handler",
        },
        {
            "name": "telemetry_prune",
            "task_type": "interval",
            "schedule": "86400",
            "handler_path": "api.services.scheduler.telemetry_prune_handler",
        },
    ]

    for d in defaults:
        existing = db.query(ScheduledTask).filter(
            ScheduledTask.name == d["name"],
        ).first()
        if not existing:
            create_scheduled_task(db, **d, created_by="system")
            logger.info(f"Seeded default scheduled task: {d['name']}")


# ── Built-in Handlers ────────────────────────────────────────────

def auth_cleanup_handler():
    """Cleanup expired SIWE nonces and refresh tokens."""
    from api.auth.siwe import cleanup_expired_nonces
    from api.auth.jwt import cleanup_expired_refresh_tokens
    from api.database import get_public_session

    with get_public_session() as db:
        nonces = cleanup_expired_nonces(db)
        tokens = cleanup_expired_refresh_tokens(db)
        db.commit()
        if nonces or tokens:
            logger.info(f"Auth cleanup: {nonces} nonces, {tokens} refresh tokens removed")


def memory_cleanup_handler():
    """Cleanup expired working memory entries."""
    from api.services.agent_memory import cleanup_expired_working
    from api.database import get_public_session

    with get_public_session() as db:
        cleaned = cleanup_expired_working(db)
        db.commit()
        if cleaned:
            logger.info(f"Agent memory cleanup: {cleaned} expired entries removed")


def p2p_cleanup_handler():
    """Cleanup stale P2P peers."""
    try:
        from api.services.p2p import P2PNetwork
        cleaned = P2PNetwork.get().cleanup_stale_peers()
        if cleaned:
            logger.info(f"P2P cleanup: {cleaned} stale peers removed")
    except Exception as e:
        logger.warning(f"P2P cleanup skipped: {e}")


async def health_check_handler():
    """Run system health check and log results."""
    from api.services.monitor import run_health_check
    from api.database import get_internal_session

    with get_internal_session() as int_db:
        try:
            await run_health_check(int_db)
            int_db.commit()
        except Exception as e:
            logger.warning(f"Health check handler error: {e}")


def api_counter_reset_handler():
    """Reset daily API key request counters. Should run once per day."""
    from api.database import get_public_session
    from api.models.public import ApiKey
    from datetime import date

    today = date.today()
    with get_public_session() as db:
        keys = db.query(ApiKey).filter(
            ApiKey.is_active == True,  # noqa: E712
        ).all()

        reset_count = 0
        for key in keys:
            last_reset = getattr(key, "last_reset_date", None)
            if last_reset != today:
                key.requests_today = 0
                if hasattr(key, "last_reset_date"):
                    key.last_reset_date = today
                reset_count += 1

        db.commit()
        if reset_count:
            logger.info(f"API counter reset: {reset_count} keys reset for {today}")


def telemetry_prune_handler():
    """Prune old IoT telemetry records beyond 30-day retention window."""
    from api.database import get_public_session
    from api.models.public import IoTTelemetry
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    with get_public_session() as db:
        old_count = db.query(IoTTelemetry).filter(
            IoTTelemetry.received_at < cutoff,
        ).count()

        if old_count == 0:
            return

        db.query(IoTTelemetry).filter(
            IoTTelemetry.received_at < cutoff,
        ).delete(synchronize_session=False)
        db.commit()
        logger.info(f"Telemetry prune: {old_count} records older than 30 days removed")
