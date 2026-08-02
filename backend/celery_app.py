# backend/celery_app.py
"""
Celery Application for Background Task Processing
Handles analysis generation, report generation, and notifications.
"""
from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "mosaic_studio",
    broker="redis://localhost:6379/1",
    backend="redis://localhost:6379/2",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_max_memory_per_child=200000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
)

# Scheduled tasks
celery_app.conf.beat_schedule = {
    "cleanup-expired-refresh-tokens": {
        "task": "backend.tasks.cleanup_expired_tokens",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    "cleanup-expired-sessions": {
        "task": "backend.tasks.cleanup_expired_sessions",
        "schedule": crontab(hour=3, minute=30),  # Daily at 3:30 AM
    },
    "generate-usage-report": {
        "task": "backend.tasks.generate_usage_report",
        "schedule": crontab(hour=0, minute=0, day_of_week=1),  # Weekly Monday
    },
}


# ── Task Definitions ────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3)
def process_analysis_async(self, analysis_id: str, business_problem: str, tier: str):
    """Background task for processing architecture analysis."""
    import asyncio
    from backend.agents.engine import run_agent_orchestrator
    from backend.database import SessionLocal, Analysis

    async def _run():
        async for _ in run_agent_orchestrator(
            business_problem=business_problem,
            architecture_tier=tier,
            analysis_id=analysis_id,
            db_session_factory=SessionLocal,
        ):
            pass

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())
        loop.close()
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@celery_app.task
def cleanup_expired_tokens():
    """Remove expired refresh tokens from database."""
    from datetime import datetime
    from backend.database import SessionLocal, RefreshToken

    db = SessionLocal()
    try:
        deleted = db.query(RefreshToken).filter(
            RefreshToken.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        print(f"Cleaned up {deleted} expired refresh tokens")
    finally:
        db.close()


@celery_app.task
def cleanup_expired_sessions():
    """Remove expired user sessions from database."""
    from datetime import datetime
    from backend.database import SessionLocal, UserSession

    db = SessionLocal()
    try:
        deleted = db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        print(f"Cleaned up {deleted} expired sessions")
    finally:
        db.close()


@celery_app.task
def generate_usage_report():
    """Generate weekly usage statistics report."""
    from datetime import datetime, timedelta
    from backend.database import SessionLocal, Analysis, User

    db = SessionLocal()
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        total_analyses = db.query(Analysis).filter(
            Analysis.created_at >= week_ago
        ).count()
        completed = db.query(Analysis).filter(
            Analysis.created_at >= week_ago,
            Analysis.status == "completed"
        ).count()
        total_users = db.query(User).count()

        report = {
            "period": f"{week_ago.date()} to {datetime.utcnow().date()}",
            "total_analyses": total_analyses,
            "completed_analyses": completed,
            "success_rate": f"{(completed/total_analyses*100) if total_analyses > 0 else 0:.1f}%",
            "total_users": total_users,
        }
        print(f"Weekly Report: {report}")
        return report
    finally:
        db.close()
