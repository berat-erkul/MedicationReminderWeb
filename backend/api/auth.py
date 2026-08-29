"""Device self-registration → returns a per-user access token."""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from database.session import get_session
from messaging.telegram import telegram_client
from models.entities import User
from models.schemas import RegisterRequest, RegisterResponse
from utils.config import get_settings
from utils.helpers import normalize_phone, secret_ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
async def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> User:
    """Register (or re-attach) a device to a user, keyed by Telegram chat_id.

    Returns the user's access token; the app stores it and sends it as a
    Bearer token on every request.

    Gate: when REGISTRATION_SECRET is set, `invite_code` must match — this is
    what keeps a public deployment family-only. Unset → open (LAN/dev).
    """
    settings = get_settings()
    if not secret_ok(settings.registration_secret, payload.invite_code):
        logger.warning("Geçersiz davet koduyla kayıt denemesi (chat=%s)", payload.phone)
        raise HTTPException(status_code=403, detail="Geçersiz davet kodu")
    if not settings.registration_secret:
        logger.warning("REGISTRATION_SECRET ayarlı değil — kayıt herkese açık")

    phone = normalize_phone(payload.phone)
    user = session.exec(select(User).where(User.phone == phone)).first()
    is_new = user is None

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

    greeting = "Hoş geldin" if is_new else "Tekrar hoş geldin"
    sent = await telegram_client.send_message(
        phone,
        f"✅ Bağlantı başarılı!\n\n{greeting} {user.name}, İlaç Hatırlatıcı uygulaman "
        f"bu Telegram sohbetine bağlandı. İlaç saatlerinde buradan hatırlatma alacaksın.",
    )
    if sent is None:
        # Chat id yanlış olabilir ya da bot henüz bu kullanıcıyla konuşmamış
        # (Telegram, bota hiç /start atmamış chat_id'lere mesaj göndermeyi reddeder).
        logger.warning("Register sonrası Telegram doğrulama mesajı gönderilemedi (chat=%s)", phone)

    return user
