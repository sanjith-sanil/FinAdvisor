import datetime
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.utils.files import save_upload_file

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _generate_customer_id() -> str:
    return f"CUST{uuid.uuid4().int % 10**8:08d}"


@router.post("/", response_model=UserOut)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> UserOut:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    customer_id = _generate_customer_id()
    user = User(customer_id=customer_id, **payload.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # --- Daily Login Streak Logic ---
    today = datetime.date.today()
    if not user.last_login_date:
        user.current_streak = 1
        user.longest_streak = 1
        user.last_login_date = today
        await db.commit()
        await db.refresh(user)
    elif user.last_login_date != today:
        delta = today - user.last_login_date
        old_streak = user.current_streak or 0
        if delta.days == 1:
            user.current_streak = old_streak + 1
        else:
            user.current_streak = 1
            
        user.longest_streak = max(user.longest_streak or 0, user.current_streak)
        user.last_login_date = today
        await db.commit()
        await db.refresh(user)
        
        # Publish live notification alert for streak milestone
        try:
            import json
            from app.services.notification_service import notification_hub
            await notification_hub.publish(
                str(user.id),
                json.dumps({
                    "id": f"streak-{user.id}-{today}",
                    "title": "Streak Active! 🔥",
                    "meta": f"You're on a {user.current_streak}-day login streak! Keep it up.",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "type": "reminder",
                    "unread": True
                })
            )
        except Exception:
            pass

    return user


@router.get("/{user_id}/stats")
async def get_user_stats(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    from sqlalchemy import func
    from app.models.card import Card
    from app.models.transaction import Transaction
    
    card_count = (await db.execute(
        select(func.count(Card.id)).where(Card.user_id == user_id, Card.is_active.is_(True))
    )).scalar() or 0
    
    from app.models.transaction import scope_active_transactions
    txn_stmt = select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
    txn_stmt = scope_active_transactions(txn_stmt)
    txn_count = (await db.execute(txn_stmt)).scalar() or 0
    
    return {
        "cards_count": card_count,
        "transactions_count": txn_count
    }


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}")
async def permanent_delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"status": "deleted", "message": "User deleted permanently"}


@router.post("/{user_id}/avatar", response_model=UserOut)
async def upload_avatar(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    file_path = save_upload_file(file, prefix="avatar-")
    user.profile_picture_url = file_path
    await db.commit()
    await db.refresh(user)
    return user


from pydantic import BaseModel

class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


@router.post("/{user_id}/change-password")
async def change_password(
    user_id: uuid.UUID,
    payload: ChangePasswordPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="User password not configured")

    from app.routers.auth import pwd_context, _hash_password
    if not pwd_context.verify(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user.password_hash = _hash_password(payload.new_password)
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    return {"success": True, "message": "Password changed successfully"}


import csv
import io
from fastapi.responses import StreamingResponse
from app.models.transaction import Transaction

@router.get("/{user_id}/export-data")
async def export_data(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch all user transactions
    from app.models.transaction import scope_active_transactions
    stmt = select(Transaction).where(Transaction.user_id == user_id)
    stmt = scope_active_transactions(stmt).order_by(Transaction.transaction_date.desc())
    txns = (await db.execute(stmt)).scalars().all()

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Transaction Date", "Description", "Amount", "Type", "Source", "Bank Name", "Bank Code"
    ])

    # Write rows
    for txn in txns:
        writer.writerow([
            txn.transaction_date.isoformat() if txn.transaction_date else "",
            txn.description or "",
            txn.amount or 0.0,
            txn.transaction_type.value if txn.transaction_type else "",
            txn.source.value if txn.source else "",
            txn.bank_name or "",
            txn.bank_code or ""
        ])

    output.seek(0)

    filename = f"finadvisor_export_{user_id}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/{user_id}/badges")
async def get_user_badges(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Gather database stats dynamically
    from sqlalchemy import func
    from app.models.card import Card
    from app.models.transaction import Transaction
    from app.models.chatbot import ChatbotMessage
    from app.models.pdf_upload import PdfUpload
    from app.models.budget_goal import BudgetGoal
    from app.services.calculation_service import dashboard_summary
    
    # 1. Cards Count
    card_stmt = select(Card).where(Card.user_id == user_id, Card.is_active.is_(True))
    cards = (await db.execute(card_stmt)).scalars().all()
    card_count = len(cards)
    
    # 2. PDF Uploads Count
    upload_stmt = select(func.count(PdfUpload.id)).where(PdfUpload.user_id == user_id)
    pdf_count = (await db.execute(upload_stmt)).scalar() or 0
    
    # 3. Chatbot Messages Count
    chat_stmt = select(func.count(ChatbotMessage.id)).where(ChatbotMessage.user_id == user_id)
    chat_count = (await db.execute(chat_stmt)).scalar() or 0
    
    # 4. Budget Goals Count
    budget_stmt = select(BudgetGoal).where(BudgetGoal.user_id == user_id)
    budgets = (await db.execute(budget_stmt)).scalars().all()
    
    # 5. Financial Health Score
    summary = {}
    try:
        summary = await dashboard_summary(db, user_id)
    except Exception:
        pass
    health_score = summary.get("financial_health_score", 50)
    
    # Evaluate Badges
    badges = []
    
    # Badge 1: Shield Up (utilization < 30% for all cards)
    has_util_card = False
    shield_up = False
    if card_count > 0:
        has_util_card = True
        shield_up = all(
            (float(c.current_balance or 0) / float(c.credit_limit or 1)) < 0.3 
            for c in cards if c.credit_limit and float(c.credit_limit) > 0
        )
    badges.append({
        "id": "shield_up",
        "title": "Shield Up",
        "description": "Keep utilization below 30% on all cards",
        "icon": "shield",
        "unlocked": shield_up,
        "progress": "Active" if shield_up else ("No cards" if not has_util_card else "Utilization > 30%")
    })
    
    # Badge 2: Streak Master (7-day login streak)
    login_streak = user.current_streak or 0
    badges.append({
        "id": "streak_master",
        "title": "Streak Master",
        "description": "Maintain a 7-day login streak",
        "icon": "flame",
        "unlocked": login_streak >= 7,
        "progress": f"{login_streak}/7 days"
    })
    
    # Badge 3: Card Collector (Added 3+ cards)
    badges.append({
        "id": "card_collector",
        "title": "Card Collector",
        "description": "Add 3 or more credit cards",
        "icon": "layers",
        "unlocked": card_count >= 3,
        "progress": f"{card_count}/3 cards"
    })
    
    # Badge 4: Data Driven (Uploaded first PDF statement)
    badges.append({
        "id": "data_driven",
        "title": "Data Driven",
        "description": "Upload your first PDF statement",
        "icon": "file-text",
        "unlocked": pdf_count >= 1,
        "progress": f"{pdf_count}/1 uploads"
    })
    
    # Badge 5: AI Explorer (Asked chatbot 10 questions)
    badges.append({
        "id": "ai_explorer",
        "title": "AI Explorer",
        "description": "Ask the AI Chatbot 10 questions",
        "icon": "bot",
        "unlocked": chat_count >= 10,
        "progress": f"{chat_count}/10 questions"
    })
    
    # Badge 6: On-Time Payer (At least 1 card & no overdue warnings)
    on_time = card_count > 0 and all(
        (float(c.current_balance or 0) <= 0 or (c.payment_due_date is not None))
        for c in cards
    )
    badges.append({
        "id": "ontime_payer",
        "title": "On-Time Payer",
        "description": "Maintain positive payment status",
        "icon": "check-circle",
        "unlocked": on_time,
        "progress": "Active" if on_time else "No active card data"
    })
    
    # Badge 7: Debt Crusher (No debt or low outstanding debt < 10% limit)
    total_limit = sum(float(c.credit_limit or 0) for c in cards)
    total_outstanding = sum(float(c.current_balance or 0) for c in cards)
    debt_free = card_count > 0 and total_outstanding < (total_limit * 0.10) if total_limit > 0 else False
    badges.append({
        "id": "debt_crusher",
        "title": "Debt Crusher",
        "description": "Keep total outstanding debt below 10% limit",
        "icon": "trending-down",
        "unlocked": debt_free,
        "progress": "Active" if debt_free else "Debt > 10% limit"
    })
    
    # Badge 8: Budget Boss (Stayed under budget for the month)
    budget_boss = len(budgets) > 0 and all(
        float(b.current_spent or 0) <= float(b.monthly_limit or 0)
        for b in budgets
    )
    badges.append({
        "id": "budget_boss",
        "title": "Budget Boss",
        "description": "Stay under budget limits for all categories",
        "icon": "calculator",
        "unlocked": budget_boss,
        "progress": "Active" if budget_boss else (f"0/{len(budgets)} budgets" if len(budgets) == 0 else "Over budget")
    })
    
    # Badge 9: Connected (Set up email auto-collection)
    connected = user.email_collection_configured == True
    badges.append({
        "id": "connected",
        "title": "Connected",
        "description": "Configure email auto-collection for statements",
        "icon": "link",
        "unlocked": connected,
        "progress": "Linked" if connected else "Not configured"
    })
    
    # Badge 10: Perfect Score (Health score reaches 90+)
    badges.append({
        "id": "perfect_score",
        "title": "Perfect Score",
        "description": "Reach a Financial Health Score of 90+",
        "icon": "star",
        "unlocked": health_score >= 90,
        "progress": f"Score: {health_score}/90"
    })
    
    return badges


class BudgetPayload(BaseModel):
    monthly_limit: float


@router.post("/{user_id}/budget")
async def set_user_budget(
    user_id: uuid.UUID,
    payload: BudgetPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    from app.models.budget_goal import BudgetGoal
    import datetime
    
    today = datetime.date.today()
    # Find existing budget for this month/year
    stmt = select(BudgetGoal).where(
        BudgetGoal.user_id == user_id,
        BudgetGoal.month == today.month,
        BudgetGoal.year == today.year
    )
    budget = (await db.execute(stmt)).scalar_one_or_none()
    
    if budget:
        budget.monthly_limit = payload.monthly_limit
    else:
        budget = BudgetGoal(
            user_id=user_id,
            monthly_limit=payload.monthly_limit,
            current_spent=0,
            month=today.month,
            year=today.year
        )
        db.add(budget)
        
    await db.commit()
    return {"success": True, "monthly_limit": float(budget.monthly_limit)}


@router.get("/{user_id}/budget")
async def get_user_budget(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    from app.models.budget_goal import BudgetGoal
    import datetime
    
    today = datetime.date.today()
    stmt = select(BudgetGoal).where(
        BudgetGoal.user_id == user_id,
        BudgetGoal.month == today.month,
        BudgetGoal.year == today.year
    )
    budget = (await db.execute(stmt)).scalar_one_or_none()
    
    if budget:
        return {"monthly_limit": float(budget.monthly_limit), "current_spent": float(budget.current_spent or 0)}
    return {"monthly_limit": 0.0, "current_spent": 0.0}
