from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database.session import get_session
from models.entities import Medicine, Schedule, User
from models.schemas import ScheduleCreate, ScheduleRead, ScheduleUpdate

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    user_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[Schedule]:
    stmt = select(Schedule)
    if user_id is not None:
        stmt = stmt.where(Schedule.user_id == user_id)
    return list(session.exec(stmt.order_by(Schedule.time)).all())


@router.post("", response_model=ScheduleRead, status_code=201)
def create_schedule(payload: ScheduleCreate, session: Session = Depends(get_session)) -> Schedule:
    if not session.get(User, payload.user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if not session.get(Medicine, payload.medicine_id):
        raise HTTPException(status_code=404, detail="Medicine not found")

    schedule = Schedule(**payload.model_dump())
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: int, session: Session = Depends(get_session)) -> Schedule:
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int, payload: ScheduleUpdate, session: Session = Depends(get_session)
) -> Schedule:
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(schedule, key, value)

    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, session: Session = Depends(get_session)) -> None:
    schedule = session.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    session.delete(schedule)
    session.commit()
