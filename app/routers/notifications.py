import asyncio
import datetime
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.card import Card
from app.models.notification import Notification
from app.models.sms_email_raw import SmsEmailRaw
from app.models.transaction import Transaction
from app.models.user import User
from app.core.security import get_current_user
from app.services.notification_service import notification_hub

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# ---------- GET: read persisted notifications + dynamic (cards/txns) ----------

@router.get("/{user_id}")
async def get_notifications(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    notifications = []

    # 1. Persisted notifications from DB (last 30)
    persisted_stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(desc(Notification.created_at))
        .limit(30)
    )
    persisted = (await db.execute(persisted_stmt)).scalars().all()
    seen_ids = set()
    for n in persisted:
        notifications.append({
            "id": str(n.id),
            "title": n.title,
            "meta": n.message,
            "timestamp": n.created_at.isoformat() if n.created_at else None,
            "type": n.notification_type,
            "unread": not n.is_read,
        })
        seen_ids.add(str(n.id))

    # 2. Card Payment Reminders (dynamic — always computed, not persisted)
    card_stmt = select(Card).where(Card.user_id == user_id, Card.is_active.is_(True))
    cards = (await db.execute(card_stmt)).scalars().all()
    for card in cards:
        if card.payment_due_date:
            today = datetime.date.today()
            due_day = card.payment_due_date
            try:
                due_date = datetime.date(today.year, today.month, due_day)
            except ValueError:
                due_date = datetime.date(today.year, today.month, 28)

            if due_date < today:
                if today.month == 12:
                    due_date = datetime.date(today.year + 1, 1, due_day)
                else:
                    due_date = datetime.date(today.year, today.month + 1, due_day)

            days_left = (due_date - today).days
            if 0 <= days_left <= 7:
                nid = f"due-{card.id}-{due_date}"
                if nid not in seen_ids:
                    notifications.append({
                        "id": nid,
                        "title": "Payment reminder",
                        "meta": f"{card.bank_name} Credit Card • Due in {days_left} day{'s' if days_left != 1 else ''}",
                        "timestamp": datetime.datetime(due_date.year, due_date.month, due_date.day, 9, 0, tzinfo=datetime.timezone.utc).isoformat(),
                        "type": "reminder",
                        "unread": True,
                    })

    notifications.sort(key=lambda x: x["timestamp"] or "", reverse=True)

    # Count unread
    unread_count = sum(1 for n in notifications if n.get("unread"))

    return {"notifications": notifications[:20], "unread_count": unread_count}


# ---------- PATCH: mark all notifications as read ----------

@router.patch("/{user_id}/read")
async def mark_all_read(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    await db.execute(
        update(Notification)
        .where(and_(Notification.user_id == user_id, Notification.is_read.is_(False)))
        .values(is_read=True)
    )
    await db.commit()
    return {"status": "ok", "message": "All notifications marked as read"}


# ---------- PATCH: mark a single notification as read ----------

@router.patch("/{user_id}/read/{notification_id}")
async def mark_one_read(
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    notif = await db.get(Notification, notification_id)
    if not notif or notif.user_id != user_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    await db.commit()
    return {"status": "ok"}


# ---------- SSE: real-time event stream ----------

@router.get("/stream/{user_id}")
async def stream_notifications(
    user_id: str,
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    try:
        req_user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    # Manual JWT authentication for EventSource
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required")
    
    from app.core.security import ALGORITHM
    from jose import JWTError, jwt
    from app.core.config import settings

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub or uuid.UUID(sub) != req_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    async def event_stream():
        while True:
            try:
                message = await asyncio.wait_for(notification_hub.get_queue(user_id).get(), timeout=25)
                yield f"data: {message}\n\n"
            except asyncio.TimeoutError:
                yield ": ping\n\n"
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)
                continue

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
