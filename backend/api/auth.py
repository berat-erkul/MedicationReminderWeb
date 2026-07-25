"""Device self-registration → returns a per-user access token."""

import secrets

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from database.session import get_session
from models.entities import User
from models.schemas import RegisterRequest, RegisterResponse
from utils.helpers import normalize_phone

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> User:
    """Register (or re-attach) a device to a user, keyed by Telegram chat_id.

    Returns the user's access token; the app stores it and sends it as a
    Bearer token on every request.
    """
    phone = normalize_phone(payload.phone)
    user = session.exec(select(User).where(User.phone == phone)).first()

    if user is None:
        user = User(
            name=payload.name,
            phone=phone,
            timezone=payload.timezone,
            access_token=secrets.token_urlsafe(24),
        )
        session.add(user)
    else:
        # Same person re-installing: keep data, update name, ensure a token.
        user.name = payload.name
        if not user.access_token:
            user.access_token = secrets.token_urlsafe(24)
        session.add(user)

    session.commit()
    session.refresh(user)
    return user
