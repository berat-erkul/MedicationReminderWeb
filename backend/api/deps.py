"""Auth dependency: resolve the current user from a Bearer access token.

Each device registers once and stores its token; every data request carries it,
and the API scopes results to that user — real per-user isolation.
"""

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from database.session import get_session
from models.entities import User


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Yetkilendirme gerekli")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    user = session.exec(select(User).where(User.access_token == token)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    return user
