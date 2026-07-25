from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, func, select

from ai.service import ai_service
from api.deps import get_current_user
from database.session import get_session
from models.entities import Medicine, Message, Reminder, Schedule, User
from models.schemas import DashboardStats, MessageRead, ReminderRead
from notify.push import push_notifier
from services.reminder_service import reminder_service
from utils.config import get_settings
from utils.constants import ReminderStatus
from utils.helpers import utc_now

router = APIRouter(tags=["reminders"])


@router.get("/reminders", response_model=list[ReminderRead])
def list_reminders(
    status: ReminderStatus | None = None,
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[Reminder]:
    stmt = select(Reminder).where(Reminder.user_id == user.id)
    if status:
        stmt = stmt.where(Reminder.status == status)
    stmt = stmt.order_by(col(Reminder.scheduled_for).desc()).limit(limit)
    return list(session.exec(stmt).all())


@router.get("/messages", response_model=list[MessageRead])
def list_messages(
    limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.user_id == user.id)
        .order_by(col(Message.timestamp).desc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


@router.post("/reminders/{reminder_id}/complete")
async def complete_reminder(
    reminder_id: int,
    skipped: bool = Query(default=False, description="true → 'almadım', false → 'aldım'"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Mark a reminder taken ('Aldım') or not-taken ('Almadım') from the app."""
    reminder = session.get(Reminder, reminder_id)
    if not reminder or reminder.user_id != user.id:
        raise HTTPException(status_code=404, detail="Reminder not found")
    reminder = await reminder_service.complete_by_app(session, reminder, skipped=skipped)
    return {"ok": True, "reminder_id": reminder.id, "status": reminder.status.value}


@router.get("/app/today")
def app_today(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    """Bugünkü dozlar (mobil ana ekran): kişinin aktif programlarından bugüne
    düşenler + her birinin hatırlatma durumu."""
    user_id = user.id
    tz = ZoneInfo(user.timezone or "Europe/Istanbul")
    now_local = datetime.now(tz)
    weekday = str(now_local.weekday())
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = day_start_local.astimezone(ZoneInfo("UTC"))
    end_utc = (day_start_local + timedelta(days=1)).astimezone(ZoneInfo("UTC"))

    schedules = session.exec(
        select(Schedule)
        .where(Schedule.user_id == user_id)
        .where(Schedule.is_active == True)  # noqa: E712
        .order_by(Schedule.time)
    ).all()

    todays_reminders = session.exec(
        select(Reminder)
        .where(Reminder.user_id == user_id)
        .where(Reminder.scheduled_for >= start_utc)
        .where(Reminder.scheduled_for < end_utc)
    ).all()

    doses = []
    for sched in schedules:
        if sched.days_of_week:
            allowed = {d.strip() for d in sched.days_of_week.split(",") if d.strip()}
            if weekday not in allowed:
                continue
        medicine = session.get(Medicine, sched.medicine_id)
        reminder = next((r for r in todays_reminders if r.schedule_id == sched.id), None)
        doses.append({
            "schedule_id": sched.id,
            "medicine_id": sched.medicine_id,
            "medicine_name": medicine.name if medicine else "Bilinmiyor",
            "dosage": medicine.dosage if medicine else "",
            "time": str(sched.time)[:5],
            "reminder_id": reminder.id if reminder else None,
            "status": reminder.status.value if reminder else "upcoming",
        })

    return {"date": now_local.strftime("%Y-%m-%d"), "user_id": user_id, "doses": doses}


@router.post("/notify/test")
async def notify_test(user: User = Depends(get_current_user)) -> dict:
    """Send a test push so the user can confirm notifications work."""
    settings = get_settings()
    await push_notifier.push(
        title="🔔 Test bildirimi",
        message="İlaç hatırlatıcı push kanalı çalışıyor.",
        user_id=user.id,
        priority=3,
        tags=["bell"],
    )
    return {"ok": True, "topic": settings.ntfy_topic, "enabled": settings.push_enabled}


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(session: Session = Depends(get_session)) -> DashboardStats:
    now = utc_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    total_users = session.exec(select(func.count()).select_from(User)).one()
    active_schedules = session.exec(
        select(func.count()).select_from(Schedule).where(Schedule.is_active == True)  # noqa: E712
    ).one()

    today = session.exec(
        select(Reminder).where(Reminder.scheduled_for >= start).where(Reminder.scheduled_for < end)
    ).all()

    return DashboardStats(
        total_users=total_users,
        active_schedules=active_schedules,
        reminders_today=len(today),
        completed_today=sum(1 for r in today if r.status == ReminderStatus.COMPLETED),
        missed_today=sum(1 for r in today if r.status == ReminderStatus.MISSED),
        pending_replies=sum(1 for r in today if r.status == ReminderStatus.SENT),
    )


@router.get("/reports/weekly")
async def weekly_report(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    since = utc_now() - timedelta(days=7)
    reminders = session.exec(
        select(Reminder).where(Reminder.user_id == user.id).where(Reminder.scheduled_for >= since)
    ).all()

    counts = {
        "total": len(reminders),
        "completed": sum(1 for r in reminders if r.status == ReminderStatus.COMPLETED),
        "skipped": sum(1 for r in reminders if r.status == ReminderStatus.SKIPPED),
        "missed": sum(1 for r in reminders if r.status == ReminderStatus.MISSED),
        "pending": sum(
            1 for r in reminders if r.status in (ReminderStatus.SENT, ReminderStatus.PENDING)
        ),
    }
    rate = round((counts["completed"] / counts["total"]) * 100, 1) if counts["total"] else 0.0
    stats_text = (
        f"Toplam: {counts['total']}\n"
        f"Alındı: {counts['completed']}\n"
        f"Atlandı: {counts['skipped']}\n"
        f"Kaçırıldı: {counts['missed']}\n"
        f"Bekleyen: {counts['pending']}\n"
        f"Uyum oranı: %{rate}"
    )
    summary = await ai_service.weekly_adherence_summary(stats_text)
    return {"period_days": 7, "counts": counts, "adherence_rate": rate, "ai_summary": summary}
