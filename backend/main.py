import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import admin, medicines, reminders, schedules, users
from database.session import init_db
from messaging.poller import start_polling, stop_polling
from scheduler.jobs import start_scheduler, stop_scheduler
from utils.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    start_scheduler()
    start_polling()
    logger.info("Application started")
    yield
    stop_polling()
    stop_scheduler()
    logger.info("Application stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api")
app.include_router(medicines.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(reminders.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "backend"}
