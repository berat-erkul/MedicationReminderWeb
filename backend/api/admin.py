"""Admin-only API endpoints — full system overview with per-user adherence stats."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, func, select

from database.session import get_session
from models.entities import Medicine, Message, Reminder, Schedule, User
from utils.constants import MessageDirection, ReminderStatus
from utils.helpers import utc_now

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
def admin_overview(
    days: int = Query(default=30, ge=1, le=365, description="Kaç günlük veri"),
    session: Session = Depends(get_session),
) -> dict:
    """
    Tüm kullanıcılar için detaylı ilaç uyum raporu.
    Her kullanıcının ilaçları, programları, hatırlatma istatistikleri ve
    kullanım yüzdeleri dahil.
    """
    now = utc_now()
    period_start = now - timedelta(days=days)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # --- System-wide counts ---
    total_users = session.exec(select(func.count()).select_from(User)).one()
    total_medicines = session.exec(select(func.count()).select_from(Medicine)).one()
    total_schedules = session.exec(
        select(func.count()).select_from(Schedule).where(Schedule.is_active == True)  # noqa: E712
    ).one()

    # --- All reminders in the period ---
    all_reminders = session.exec(
        select(Reminder).where(Reminder.scheduled_for >= period_start)
    ).all()

    # --- Today's reminders ---
    today_reminders = [
        r for r in all_reminders
        if today_start <= r.scheduled_for < today_end
    ]

    # --- Per-user breakdown ---
    users = session.exec(select(User).order_by(User.name)).all()
    user_details = []

    for user in users:
        # User's schedules with medicine info
        schedules = session.exec(
            select(Schedule).where(Schedule.user_id == user.id)
        ).all()

        medicine_schedules = []
        for sched in schedules:
            medicine = session.get(Medicine, sched.medicine_id)
            medicine_schedules.append({
                "schedule_id": sched.id,
                "medicine_id": sched.medicine_id,
                "medicine_name": medicine.name if medicine else "Bilinmiyor",
                "dosage": medicine.dosage if medicine else "",
                "time": str(sched.time)[:5],
                "recurrence": sched.recurrence.value,
                "days_of_week": sched.days_of_week,
                "is_active": sched.is_active,
            })

        # User's reminders in period
        user_reminders = [r for r in all_reminders if r.user_id == user.id]
        completed = sum(1 for r in user_reminders if r.status == ReminderStatus.COMPLETED)
        missed = sum(1 for r in user_reminders if r.status == ReminderStatus.MISSED)
        skipped = sum(1 for r in user_reminders if r.status == ReminderStatus.SKIPPED)
        sent = sum(1 for r in user_reminders if r.status == ReminderStatus.SENT)
        pending = sum(1 for r in user_reminders if r.status == ReminderStatus.PENDING)
        total = len(user_reminders)
        resolved = completed + missed + skipped
        adherence_rate = round((completed / resolved) * 100, 1) if resolved > 0 else 0.0

        # User's today stats
        user_today = [r for r in today_reminders if r.user_id == user.id]
        today_completed = sum(1 for r in user_today if r.status == ReminderStatus.COMPLETED)
        today_missed = sum(1 for r in user_today if r.status == ReminderStatus.MISSED)
        today_pending = sum(
            1 for r in user_today if r.status in (ReminderStatus.SENT, ReminderStatus.PENDING)
        )

        # Per-medicine adherence (for this user, in period)
        medicine_stats = []
        for sched in schedules:
            med = session.get(Medicine, sched.medicine_id)
            sched_reminders = [r for r in user_reminders if r.schedule_id == sched.id]
            med_completed = sum(1 for r in sched_reminders if r.status == ReminderStatus.COMPLETED)
            med_resolved = sum(
                1 for r in sched_reminders
                if r.status in (ReminderStatus.COMPLETED, ReminderStatus.MISSED, ReminderStatus.SKIPPED)
            )
            med_rate = round((med_completed / med_resolved) * 100, 1) if med_resolved > 0 else 0.0

            medicine_stats.append({
                "medicine_name": med.name if med else "Bilinmiyor",
                "dosage": med.dosage if med else "",
                "schedule_time": str(sched.time)[:5],
                "total_reminders": len(sched_reminders),
                "completed": med_completed,
                "missed": sum(1 for r in sched_reminders if r.status == ReminderStatus.MISSED),
                "skipped": sum(1 for r in sched_reminders if r.status == ReminderStatus.SKIPPED),
                "adherence_rate": med_rate,
            })

        # Last message timestamp
        last_msg = session.exec(
            select(Message)
            .where(Message.user_id == user.id)
            .where(Message.direction == MessageDirection.INBOUND)
            .order_by(col(Message.timestamp).desc())
        ).first()

        user_details.append({
            "id": user.id,
            "name": user.name,
            "phone": user.phone,
            "timezone": user.timezone,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "last_response": last_msg.timestamp.isoformat() if last_msg else None,
            "schedules": medicine_schedules,
            "medicine_adherence": medicine_stats,
            "period_stats": {
                "total_reminders": total,
                "completed": completed,
                "missed": missed,
                "skipped": skipped,
                "sent_waiting": sent,
                "pending": pending,
                "adherence_rate": adherence_rate,
            },
            "today": {
                "total": len(user_today),
                "completed": today_completed,
                "missed": today_missed,
                "pending": today_pending,
            },
        })

    # --- Overall adherence ---
    all_resolved = sum(
        1 for r in all_reminders
        if r.status in (ReminderStatus.COMPLETED, ReminderStatus.MISSED, ReminderStatus.SKIPPED)
    )
    all_completed = sum(1 for r in all_reminders if r.status == ReminderStatus.COMPLETED)
    overall_rate = round((all_completed / all_resolved) * 100, 1) if all_resolved > 0 else 0.0

    # --- Daily trend (last N days) ---
    daily_trend = []
    for i in range(min(days, 30)):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_reminders = [r for r in all_reminders if day_start <= r.scheduled_for < day_end]
        day_completed = sum(1 for r in day_reminders if r.status == ReminderStatus.COMPLETED)
        day_resolved = sum(
            1 for r in day_reminders
            if r.status in (ReminderStatus.COMPLETED, ReminderStatus.MISSED, ReminderStatus.SKIPPED)
        )
        daily_trend.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "total": len(day_reminders),
            "completed": day_completed,
            "adherence_rate": round((day_completed / day_resolved) * 100, 1) if day_resolved > 0 else 0.0,
        })

    daily_trend.reverse()  # Oldest first

    return {
        "generated_at": now.isoformat(),
        "period": {
            "start": period_start.isoformat(),
            "end": now.isoformat(),
            "days": days,
        },
        "system": {
            "total_users": total_users,
            "active_users": sum(1 for u in users if u.is_active),
            "total_medicines": total_medicines,
            "active_schedules": total_schedules,
            "total_reminders_in_period": len(all_reminders),
            "overall_adherence_rate": overall_rate,
        },
        "today_summary": {
            "total_reminders": len(today_reminders),
            "completed": sum(1 for r in today_reminders if r.status == ReminderStatus.COMPLETED),
            "missed": sum(1 for r in today_reminders if r.status == ReminderStatus.MISSED),
            "pending": sum(
                1 for r in today_reminders
                if r.status in (ReminderStatus.SENT, ReminderStatus.PENDING)
            ),
        },
        "daily_trend": daily_trend,
        "users": user_details,
    }


@router.get("/users/{user_id}/history")
def user_history(
    user_id: int,
    days: int = Query(default=7, ge=1, le=90),
    session: Session = Depends(get_session),
) -> dict:
    """Tek bir kullanıcının detaylı hatırlatma geçmişi."""
    user = session.get(User, user_id)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")

    since = utc_now() - timedelta(days=days)

    reminders = session.exec(
        select(Reminder)
        .where(Reminder.user_id == user_id)
        .where(Reminder.scheduled_for >= since)
        .order_by(col(Reminder.scheduled_for).desc())
    ).all()

    messages = session.exec(
        select(Message)
        .where(Message.user_id == user_id)
        .where(Message.timestamp >= since)
        .order_by(col(Message.timestamp).desc())
    ).all()

    history = []
    for r in reminders:
        schedule = session.get(Schedule, r.schedule_id)
        medicine = session.get(Medicine, schedule.medicine_id) if schedule else None
        history.append({
            "reminder_id": r.id,
            "medicine": medicine.name if medicine else "Bilinmiyor",
            "dosage": medicine.dosage if medicine else "",
            "scheduled_for": r.scheduled_for.isoformat(),
            "status": r.status.value,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "answered_at": r.answered_at.isoformat() if r.answered_at else None,
            "retry_count": r.retry_count,
        })

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "phone": user.phone,
        },
        "period_days": days,
        "reminders": history,
        "messages": [
            {
                "direction": m.direction.value,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ],
    }
