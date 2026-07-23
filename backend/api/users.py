from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database.session import get_session
from models.entities import User
from models.schemas import UserCreate, UserRead, UserUpdate
from utils.helpers import normalize_phone

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(session: Session = Depends(get_session)) -> list[User]:
    return list(session.exec(select(User).order_by(User.name)).all())


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, session: Session = Depends(get_session)) -> User:
    phone = normalize_phone(payload.phone)
    existing = session.exec(select(User).where(User.phone == phone)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Phone already registered")

    user = User(name=payload.name, phone=phone, timezone=payload.timezone)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, payload: UserUpdate, session: Session = Depends(get_session)
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    if "phone" in data and data["phone"]:
        data["phone"] = normalize_phone(data["phone"])
    for key, value in data.items():
        setattr(user, key, value)

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, session: Session = Depends(get_session)) -> None:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(user)
    session.commit()
