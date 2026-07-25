from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from api.deps import get_current_user
from database.session import get_session
from models.entities import Medicine, Schedule, User
from models.schemas import ScheduleCreate, ScheduleRead, ScheduleUpdate

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[Schedule]:
    stmt = select(Schedule).where(Schedule.user_id == user.id).order_by(Schedule.time)
    return list(session.exec(stmt).all())


@router.post("", response_model=ScheduleRead, status_code=201)
def create_schedule(
    payload: ScheduleCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Schedule:
    medicine = session.get(Medicine, payload.medicine_id)
    if not medicine or medicine.user_id != user.id:
        raise HTTPException(status_code=404, detail="Medicine not found")

    data = payload.model_dump()
    data["user_id"] = user.id  # ignore any client-supplied user_id
    schedule = Schedule(**data)
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


def _owned_schedule(session: Session, schedule_id: int, user: User) -> Schedule:
    schedule = session.get(Schedule, schedule_id)
    if not schedule or schedule.user_id != user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(
    schedule_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Schedule:
    return _owned_schedule(session, schedule_id, user)


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Schedule:
    schedule = _owned_schedule(session, schedule_id, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(schedule, key, value)
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    schedule = _owned_schedule(session, schedule_id, user)
    session.delete(schedule)
    session.commit()
