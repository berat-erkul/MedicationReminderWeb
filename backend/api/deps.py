"""Auth dependencies.

- get_current_user: resolve the per-device user from a Bearer access token
  (medicine/schedule/reminder endpoints — real per-user isolation).
- require_admin: gate the system-wide endpoints (/api/users, /api/admin,
  /api/dashboard/*) behind the ADMIN_TOKEN via the X-Admin-Token header.
"""

import logging

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session, select

from database.session import get_session
from models.entities import User
from utils.config import get_settings
from utils.helpers import secret_ok

logger = logging.getLogger(__name__)


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


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate for system-wide endpoints. ADMIN_TOKEN unset → open (LAN/dev),
    but logged on every call so a public deploy without it is noisy."""
    settings = get_settings()
    if not secret_ok(settings.admin_token, x_admin_token):
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")
    if not settings.admin_token:
        logger.warning("ADMIN_TOKEN ayarlı değil — sistem geneli uçlar auth'suz")
