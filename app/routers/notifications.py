import asyncio
import datetime
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.card import Card
from app.models.sms_email_raw import SmsEmailRaw
from app.models.transaction import Transaction
from app.models.user import User
from app.core.security import get_current_user
from app.services.notification_service import notification_hub

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/{user_id}")
async def get_notifications(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    notifications = []

    # 1. Card Payment Reminders (due in next 7 days)
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
                notifications.append({
                    "id": f"due-{card.id}-{due_date}",
                    "title": "Payment reminder",
                    "meta": f"{card.bank_name} Credit Card • Due in {days_left} day{'s' if days_left != 1 else ''}",
                    "timestamp": datetime.datetime(due_date.year, due_date.month, due_date.day, 9, 0, tzinfo=datetime.timezone.utc).isoformat(),
                    "type": "reminder",
                    "unread": True
                })

    # 2. Statement & Email Parsing History
    email_stmt = (
        select(SmsEmailRaw)
        .where(SmsEmailRaw.user_id == user_id, SmsEmailRaw.source_type == "email")
        .order_by(desc(SmsEmailRaw.received_at))
        .limit(10)
    )
    emails = (await db.execute(email_stmt)).scalars().all()
    for email in emails:
        is_emi = "emi" in (email.subject or "").lower() or "emi" in (email.raw_content or "").lower()
        title = "Statement parsed" if is_emi else "Bank email parsed"
        ts = email.received_at or email.created_at
        notifications.append({
            "id": f"email-{email.id}",
            "title": title,
            "meta": f"{email.bank_name or 'Bank'} • {email.subject or 'Statement Details'}",
            "timestamp": ts.isoformat() if ts else None,
            "type": "statement",
            "unread": not email.is_processed
        })

    # 3. Dynamic Transactions
    from app.models.transaction import scope_active_transactions
    txn_stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
    )
    txn_stmt = scope_active_transactions(txn_stmt).order_by(desc(Transaction.transaction_date), desc(Transaction.created_at)).limit(10)
    txns = (await db.execute(txn_stmt)).scalars().all()
    for txn in txns:
        ts = txn.transaction_date or txn.created_at
        notifications.append({
            "id": f"txn-{txn.id}",
            "title": "Transaction alert",
            "meta": f"{txn.bank_name or 'Bank'} • ₹{txn.amount} at {txn.merchant_name or 'Merchant'}",
            "timestamp": ts.isoformat() if ts else None,
            "type": "transaction",
            "unread": True
        })

    notifications.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return notifications[:15]


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
