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
    for txn in transactions:
        db.add(
            Transaction(
                user_id=user_id,
                transaction_type=txn["transaction_type"],
                amount=txn["amount"],
                description=txn["description"],
                transaction_date=txn["transaction_date"],
                balance_after=txn["balance_after"],
                source=TransactionSource.pdf_upload,
            )
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
    for txn in transactions:
        db.add(
            Transaction(
                user_id=upload.user_id,
                transaction_type=txn["transaction_type"],
                amount=txn["amount"],
                description=txn["description"],
                transaction_date=txn["transaction_date"],
                balance_after=txn["balance_after"],
                source=TransactionSource.pdf_upload,
            )
        )

    upload.status = PdfStatus.completed
    upload.total_transactions_parsed = len(transactions)
    await db.commit()
    await db.refresh(upload)
    return upload
