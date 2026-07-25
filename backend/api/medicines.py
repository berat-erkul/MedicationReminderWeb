from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from api.deps import get_current_user
from database.session import get_session
from models.entities import Medicine, User
from models.schemas import MedicineCreate, MedicineRead, MedicineUpdate

router = APIRouter(prefix="/medicines", tags=["medicines"])


@router.get("", response_model=list[MedicineRead])
def list_medicines(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[Medicine]:
    stmt = select(Medicine).where(Medicine.user_id == user.id).order_by(Medicine.name)
    return list(session.exec(stmt).all())


@router.post("", response_model=MedicineRead, status_code=201)
def create_medicine(
    payload: MedicineCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Medicine:
    medicine = Medicine(**payload.model_dump(), user_id=user.id)
    session.add(medicine)
    session.commit()
    session.refresh(medicine)
    return medicine


def _owned_medicine(session: Session, medicine_id: int, user: User) -> Medicine:
    medicine = session.get(Medicine, medicine_id)
    if not medicine or medicine.user_id != user.id:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return medicine


@router.get("/{medicine_id}", response_model=MedicineRead)
def get_medicine(
    medicine_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Medicine:
    return _owned_medicine(session, medicine_id, user)


@router.patch("/{medicine_id}", response_model=MedicineRead)
def update_medicine(
    medicine_id: int,
    payload: MedicineUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Medicine:
    medicine = _owned_medicine(session, medicine_id, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(medicine, key, value)
    session.add(medicine)
    session.commit()
    session.refresh(medicine)
    return medicine


@router.delete("/{medicine_id}", status_code=204)
def delete_medicine(
    medicine_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    medicine = _owned_medicine(session, medicine_id, user)
    session.delete(medicine)
    session.commit()
