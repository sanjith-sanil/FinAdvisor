import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.enums import PdfStatus, TransactionSource
from app.models.pdf_upload import PdfUpload
from app.models.transaction import Transaction
from app.schemas.pdf_upload import PdfUploadOut
from app.services.pdf_parser_service import parse_pdf
from app.utils.files import save_upload_file
from app.services.balance_sync_service import (
    resolve_transaction_accounts,
    sync_balances_for_transaction,
)
from app.services.emi_upsert_service import process_emi_from_pdf

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])


@router.post("/upload", response_model=PdfUploadOut)
async def upload_pdf(
    user_id: uuid.UUID,
    card_id: uuid.UUID | None = Query(None),
    bank_name: str | None = None,
    password: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> PdfUploadOut:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    from app.models.card import Card
    card = None
    if card_id:
        card = await db.get(Card, card_id)
        if card and not bank_name:
            bank_name = card.bank_name

    file_path = save_upload_file(file, prefix="statement-")
    upload = PdfUpload(
        user_id=user_id,
        filename=file.filename,
        file_path=file_path,
        bank_name=bank_name,
        status=PdfStatus.processing,
    )
    db.add(upload)
    await db.flush()

    # Retrieve all user decryption passwords (stored card passwords + generated candidates)
    from app.services.emi_upsert_service import _get_user_decryption_passwords
    passwords = await _get_user_decryption_passwords(db, user_id)
    
    # Prioritize the password of the selected card if available
    if card and card.statement_password_encrypted:
        from app.services.crypto_service import decrypt_text
        try:
            card_pwd = decrypt_text(card.statement_password_encrypted)
            if card_pwd:
                passwords = [card_pwd] + [p for p in passwords if p != card_pwd]
        except Exception:
            pass

    if password:
        passwords = [password] + [p for p in passwords if p != password]

    try:
        transactions = parse_pdf(file_path, passwords=passwords)
    except Exception as e:
        upload.status = PdfStatus.failed
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"PDF parsing/decryption failed: {str(e)}"
        )

    bank_code = None
    if bank_name:
        for k in ["HDFC", "SBI", "ICICI", "AXIS", "KOTAK", "YES", "INDUSIND", "IDFC"]:
            if k in bank_name.upper():
                bank_code = k
                break

    for txn in transactions:
        t = Transaction(
            user_id=user_id,
            transaction_type=txn["transaction_type"],
            amount=txn["amount"],
            description=txn["description"],
            transaction_date=txn["transaction_date"],
            balance_after=txn["balance_after"],
            source=TransactionSource.pdf_upload,
            bank_name=bank_name,
            bank_code=bank_code,
            card_id=card.id if card else None
        )
        db.add(t)
        if not t.card_id:
            await resolve_transaction_accounts(db, t)
        await db.flush()
        if t.card_id or t.bank_account_id:
            await sync_balances_for_transaction(
                db=db,
                user_id=user_id,
                card_id=t.card_id,
                bank_account_id=t.bank_account_id,
                amount=t.amount,
                txn_type=t.transaction_type,
                operation="insert"
            )
 
    if bank_code:
        await process_emi_from_pdf(
            db=db,
            user_id=user_id,
            bank_code=bank_code,
            file_path=file_path,
            filename=file.filename,
            passwords=passwords,
        )

    upload.status = PdfStatus.completed
    upload.total_transactions_parsed = len(transactions)
    await db.commit()
    await db.refresh(upload)
    return upload



@router.get("/uploads", response_model=list[PdfUploadOut])
async def list_uploads(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[PdfUploadOut]:
    stmt = select(PdfUpload).where(PdfUpload.user_id == user_id)
    return (await db.execute(stmt)).scalars().all()


@router.get("/uploads/{upload_id}", response_model=PdfUploadOut)
async def upload_status(upload_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PdfUploadOut:
    upload = await db.get(PdfUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload


@router.post("/uploads/{upload_id}/reparse", response_model=PdfUploadOut)
async def reparse_upload(
    upload_id: uuid.UUID,
    password: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PdfUploadOut:
    upload = await db.get(PdfUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.status = PdfStatus.processing
    await db.commit()

    from app.services.emi_upsert_service import _get_user_decryption_passwords
    passwords = await _get_user_decryption_passwords(db, upload.user_id)
    if password:
        passwords = [password] + [p for p in passwords if p != password]

    try:
        transactions = parse_pdf(upload.file_path, passwords=passwords)
    except Exception as e:
        upload.status = PdfStatus.failed
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"PDF parsing/decryption failed: {str(e)}"
        )

    bank_code = None
    if upload.bank_name:
        for k in ["HDFC", "SBI", "ICICI", "AXIS", "KOTAK", "YES", "INDUSIND", "IDFC"]:
            if k in upload.bank_name.upper():
                bank_code = k
                break

    for txn in transactions:
        t = Transaction(
            user_id=upload.user_id,
            transaction_type=txn["transaction_type"],
            amount=txn["amount"],
            description=txn["description"],
            transaction_date=txn["transaction_date"],
            balance_after=txn["balance_after"],
            source=TransactionSource.pdf_upload,
            bank_name=upload.bank_name,
            bank_code=bank_code
        )
        db.add(t)
        await resolve_transaction_accounts(db, t)
        await db.flush()
        if t.card_id or t.bank_account_id:
            await sync_balances_for_transaction(
                db=db,
                user_id=upload.user_id,
                card_id=t.card_id,
                bank_account_id=t.bank_account_id,
                amount=t.amount,
                txn_type=t.transaction_type,
                operation="insert"
            )

    if bank_code:
        await process_emi_from_pdf(
            db=db,
            user_id=upload.user_id,
            bank_code=bank_code,
            file_path=upload.file_path,
            filename=upload.filename,
            passwords=passwords,
        )

    upload.status = PdfStatus.completed
    upload.total_transactions_parsed = len(transactions)
    await db.commit()
    await db.refresh(upload)
    return upload
