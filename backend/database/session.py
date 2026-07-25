from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from utils.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# Ensure SQLite parent directory exists
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, echo=settings.debug, connect_args=connect_args)


def init_db() -> None:
    # Import models so SQLModel metadata is populated
    from models import entities  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Lightweight SQLite migrations: add new columns + backfill tokens/owners
    on existing databases (create_all doesn't ALTER existing tables)."""
    import secrets

    from sqlmodel import Session, select

    from models.entities import Medicine, Schedule, User

    with engine.begin() as conn:
        user_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)")}
        if "access_token" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN access_token VARCHAR")
        med_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(medicines)")}
        if "user_id" not in med_cols:
            conn.exec_driver_sql("ALTER TABLE medicines ADD COLUMN user_id INTEGER")

    with Session(engine) as session:
        for user in session.exec(select(User).where(User.access_token.is_(None))).all():
            user.access_token = secrets.token_urlsafe(24)
            session.add(user)
        session.commit()
        # Best-effort: assign each ownerless medicine to a user via its schedule.
        for med in session.exec(select(Medicine).where(Medicine.user_id.is_(None))).all():
            sched = session.exec(
                select(Schedule).where(Schedule.medicine_id == med.id)
            ).first()
            if sched:
                med.user_id = sched.user_id
                session.add(med)
        session.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
