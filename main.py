from pathlib import Path
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.data.chatbot_seed import seed_chatbot_questions
from app.db.database import SessionLocal
from app.routers import (
    auth,
    bank_accounts,
    chatbot,
    cards,
    dashboard,
    email_config,
    google_oauth,
    pages,
    pdf,
    sms,
    sms_receiver,
    transactions,
    users,
)
from app.services.scheduler_service import shutdown_scheduler, start_scheduler

logger = logging.getLogger(__name__)

app = FastAPI(title="FinAdvisor", version="1.0.0")

base_dir = Path(__file__).resolve().parent
static_dir = base_dir / "static"
uploads_dir = Path(settings.upload_dir)
if not uploads_dir.is_absolute():
    uploads_dir = base_dir / uploads_dir
uploads_dir.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

app.include_router(users.router)
app.include_router(auth.router)
app.include_router(cards.router)
app.include_router(bank_accounts.router)
app.include_router(transactions.router)
app.include_router(sms.router)
app.include_router(pdf.router)
app.include_router(dashboard.router)
app.include_router(pages.router)
app.include_router(chatbot.router)
app.include_router(email_config.router)
app.include_router(google_oauth.router)
app.include_router(sms_receiver.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check the server logs for details."},
    )


@app.on_event("startup")
async def startup_event() -> None:
    async with SessionLocal() as session:
        await seed_chatbot_questions(session)
    start_scheduler(settings.email_check_interval_minutes)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    shutdown_scheduler()
