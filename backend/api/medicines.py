from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database.session import get_session
from models.entities import Medicine
from models.schemas import MedicineCreate, MedicineRead, MedicineUpdate

router = APIRouter(prefix="/medicines", tags=["medicines"])


@router.get("", response_model=list[MedicineRead])
def list_medicines(session: Session = Depends(get_session)) -> list[Medicine]:
    return list(session.exec(select(Medicine).order_by(Medicine.name)).all())


@router.post("", response_model=MedicineRead, status_code=201)
def create_medicine(payload: MedicineCreate, session: Session = Depends(get_session)) -> Medicine:
    medicine = Medicine(**payload.model_dump())
    session.add(medicine)
    session.commit()
    session.refresh(medicine)
    return medicine


@router.get("/{medicine_id}", response_model=MedicineRead)
def get_medicine(medicine_id: int, session: Session = Depends(get_session)) -> Medicine:
    medicine = session.get(Medicine, medicine_id)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return medicine


@router.patch("/{medicine_id}", response_model=MedicineRead)
def update_medicine(
    medicine_id: int, payload: MedicineUpdate, session: Session = Depends(get_session)
) -> Medicine:
    medicine = session.get(Medicine, medicine_id)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(medicine, key, value)

    session.add(medicine)
    session.commit()
    session.refresh(medicine)
    return medicine


@router.delete("/{medicine_id}", status_code=204)
def delete_medicine(medicine_id: int, session: Session = Depends(get_session)) -> None:
    medicine = session.get(Medicine, medicine_id)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    session.delete(medicine)
    session.commit()
