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


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
