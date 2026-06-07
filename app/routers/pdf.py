import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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

router = APIRouter(prefix="/api/v1/pdf", tags=["pdf"])


@router.post("/upload", response_model=PdfUploadOut)
async def upload_pdf(
    user_id: uuid.UUID,
    bank_name: str | None = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> PdfUploadOut:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

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

    transactions = parse_pdf(file_path)
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
            bank_code=bank_code
        )
        db.add(t)
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
async def reparse_upload(upload_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> PdfUploadOut:
    upload = await db.get(PdfUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload.status = PdfStatus.processing
    await db.commit()

    transactions = parse_pdf(upload.file_path)
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

    upload.status = PdfStatus.completed
    upload.total_transactions_parsed = len(transactions)
    await db.commit()
    await db.refresh(upload)
    return upload
