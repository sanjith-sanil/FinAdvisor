import asyncio
import datetime
import email
import imaplib
import json
import logging
import re
import ssl
from email.header import decode_header
from email.message import Message
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection_log import CollectionLog
from app.models.email_config import EmailConfig
from app.models.enums import CollectionLogType, CollectionSource, EmailAuthType, SmsSourceType, TransactionSource, TransactionType
from app.models.sms_email_raw import SmsEmailRaw
from app.models.transaction import Transaction
from app.services.bank_domain_whitelist import get_bank_info
from app.services.crypto_service import decrypt_text
from app.services.sms_parser_service import looks_like_transaction_alert, parse_sms
from app.services.emi_upsert_service import process_emi_from_email

logger = logging.getLogger(__name__)


IMAP_SERVERS = {
    "gmail.com": ("imap.gmail.com", 993),
    "googlemail.com": ("imap.gmail.com", 993),
    "outlook.com": ("imap-mail.outlook.com", 993),
    "hotmail.com": ("imap-mail.outlook.com", 993),
    "live.com": ("imap-mail.outlook.com", 993),
    "yahoo.com": ("imap.mail.yahoo.com", 993),
    "yahoo.in": ("imap.mail.yahoo.com", 993),
    "rediffmail.com": ("imap.rediffmail.com", 993),
}

GMAIL_FOLDERS = [
    "INBOX",
    "[Gmail]/All Mail",
    "[Gmail]/Promotions",
    "[Gmail]/Updates",
    "[Gmail]/Spam",
]
OUTLOOK_FOLDERS = ["INBOX", "Junk"]
YAHOO_FOLDERS = ["INBOX", "Bulk Mail"]


def get_imap_server(email_address: str) -> tuple[str, int]:
    domain = email_address.split("@")[-1].lower()
    return IMAP_SERVERS.get(domain, (f"imap.{domain}", 993))


# Backward-compatible alias used by existing imports.
_imap_server_for = get_imap_server


def connect_imap(email_address: str, password: str, host: str, port: int) -> imaplib.IMAP4_SSL:
    try:
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(host=host, port=port, ssl_context=context)
        imap.login(email_address, password)
        return imap
    except Exception as exc:
        raise RuntimeError(f"Unable to connect to IMAP server {host}:{port} - {exc}") from exc


def test_connection(email_address: str, password: str, host: str | None = None) -> dict[str, Any]:
    imap_host, imap_port = (host, 993) if host else get_imap_server(email_address)
    try:
        imap = connect_imap(email_address, password, imap_host, imap_port)
        imap.logout()
        return {"success": True, "message": "Connected"}
    except Exception as exc:
        message = str(exc)
        upper = message.upper()
        if "AUTHENTICATE FAILED" in upper or "AUTHENTICATIONFAILED" in upper or "INVALIDCREDENTIALS" in upper:
            message = "Wrong password or App Password needed"
        elif "IMAP NOT ENABLED" in upper:
            message = "Enable IMAP in Gmail settings"
        return {"success": False, "message": message}


def _decode_header(value: str | None) -> str:
    if not value:
        return ""

    output: list[str] = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            output.append(chunk.decode(charset or "utf-8", errors="ignore"))
        else:
            output.append(chunk)
    return "".join(output).strip()


def get_email_body(msg: Message) -> str:
    def _decode_payload(message_part: Message) -> str:
        payload = message_part.get_payload(decode=True)
        if not payload:
            return ""
        return payload.decode(message_part.get_content_charset() or "utf-8", errors="ignore")

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in (part.get("Content-Disposition") or "").lower():
                text = _decode_payload(part)
                if text.strip():
                    return text.strip()
        for part in msg.walk():
            if part.get_content_type() == "text/html" and "attachment" not in (part.get("Content-Disposition") or "").lower():
                html = _decode_payload(part)
                if html.strip():
                    return BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        return ""

    if msg.get_content_type() == "text/html":
        html = _decode_payload(msg)
        return BeautifulSoup(html, "lxml").get_text(" ", strip=True)

    return _decode_payload(msg).strip()


def extract_sender_email(from_header: str) -> str:
    if not from_header:
        return ""
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    return from_header.replace("\"", "").strip().lower()


def _parse_email_date(value: str | None) -> datetime.datetime:
    if not value:
        return datetime.datetime.now(datetime.timezone.utc)
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return parsed or datetime.datetime.now(datetime.timezone.utc)
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


def _extract_msg_ids(search_data: list[bytes]) -> list[bytes]:
    if not search_data:
        return []
    joined = b" ".join(search_data).strip()
    if not joined:
        return []
    return joined.split()


async def fetch_all_bank_emails_from_folder(
    imap: imaplib.IMAP4_SSL,
    folder_name: str,
    first_sync: bool,
    user_id,
    db: AsyncSession,
) -> dict[str, int]:
    results = {"scanned": 0, "bank_found": 0, "transactions_saved": 0}

    try:
        status, _ = imap.select(folder_name)
        if status != "OK":
            logger.debug("Skipping folder %s - not available", folder_name)
            return results
    except Exception:
        logger.debug("Skipping folder %s - select failed", folder_name)
        return results

    if first_sync:
        status, data = imap.search(None, "ALL")
    else:
        date_30_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%d-%b-%Y")
        status, data = imap.search(None, "SINCE", date_30_days_ago)

    if status != "OK":
        return results

    message_ids = _extract_msg_ids(data)
    for msg_id in reversed(message_ids):
        results["scanned"] += 1
        try:
            fetch_status, payload = imap.fetch(msg_id, "(RFC822)")
            if fetch_status != "OK" or not payload:
                continue

            raw_email_bytes = None
            for item in payload:
                if isinstance(item, tuple) and len(item) >= 2:
                    raw_email_bytes = item[1]
                    break
            if not raw_email_bytes:
                continue

            msg = email.message_from_bytes(raw_email_bytes)
            from_header = _decode_header(msg.get("From", ""))
            sender_email = extract_sender_email(from_header)
            subject = _decode_header(msg.get("Subject", ""))
            message_id = (msg.get("Message-ID") or "").strip().strip("<>")
            received_at = _parse_email_date(msg.get("Date"))
            body = get_email_body(msg)

            bank_info = get_bank_info(sender_email)
            if not bank_info:
                continue
            results["bank_found"] += 1

            if message_id:
                existing_stmt = select(SmsEmailRaw).where(
                    SmsEmailRaw.user_id == user_id,
                    SmsEmailRaw.message_id == message_id,
                )
                existing_raw = (await db.execute(existing_stmt)).scalar_one_or_none()
                if existing_raw:
                    continue

            raw_entry = SmsEmailRaw(
                user_id=user_id,
                source_type=SmsSourceType.email,
                sender=sender_email,
                raw_content=body[:5000],
                subject=subject,
                message_id=message_id or None,
                bank_name=bank_info["bank_name"],
                bank_code=bank_info["bank_code"],
                received_at=received_at,
                is_processed=False,
            )
            db.add(raw_entry)
            await db.flush()

            combined_text = f"{subject} {body}".strip()
            parsed = parse_sms(combined_text, sender=sender_email) if looks_like_transaction_alert(combined_text) else None
            if parsed and parsed.get("amount") is not None:
                transaction_type = TransactionType.credit if parsed.get("transaction_type") == "credit" else TransactionType.debit
                transaction = Transaction(
                    user_id=user_id,
                    transaction_type=transaction_type,
                    amount=parsed.get("amount"),
                    merchant_name=parsed.get("merchant_name"),
                    description=body[:2000],
                    balance_after=parsed.get("balance_after"),
                    reference_number=parsed.get("reference_number"),
                    transaction_date=parsed.get("transaction_date") or received_at,
                    source=TransactionSource.email,
                    bank_name=bank_info["bank_name"],
                    bank_code=bank_info["bank_code"],
                    sender_email=sender_email,
                    raw_message=combined_text[:2000],
                )
                db.add(transaction)
                await db.flush()

                raw_entry.is_processed = True
                raw_entry.parsed_transaction_id = transaction.id
                results["transactions_saved"] += 1

            # --- EMI extraction (runs regardless of transaction parsing) ---
            try:
                emi_count = await process_emi_from_email(
                    db=db,
                    user_id=user_id,
                    bank_code=bank_info["bank_code"],
                    email_body=body,
                    email_subject=subject,
                    source_raw_id=raw_entry.id,
                )
                if emi_count:
                    results["transactions_saved"] += 0  # not a transaction, just log
                    logger.info(
                        "EMI: %d record(s) upserted from email %s",
                        emi_count,
                        msg_id,
                    )
            except Exception:
                logger.exception("EMI processing failed for email %s", msg_id)

        except Exception:
            logger.exception("Failed to process email %s from folder %s", msg_id, folder_name)
            continue

    return results


async def process_user_email_account(
    user_id,
    email_config_id,
    db: AsyncSession,
    update_status: bool = True,
) -> dict[str, Any]:
    started_at = datetime.datetime.now(datetime.timezone.utc)

    email_config = await db.get(EmailConfig, email_config_id)
    if not email_config or email_config.user_id != user_id:
        raise RuntimeError("Email configuration not found")
    if email_config.auth_type != EmailAuthType.imap_password:
        raise RuntimeError("Only IMAP-based sync is supported by this processor")

    if update_status:
        email_config.sync_status = "syncing"
        email_config.last_sync_error = None
        email_config.last_error = None
        await db.commit()

    first_sync = not bool(email_config.first_sync_done)
    total_scanned = 0
    total_bank_emails = 0
    total_transactions = 0

    try:
        password = decrypt_text(email_config.password_encrypted or "")
        imap_host, imap_port = get_imap_server(email_config.email_address)
        if email_config.imap_server:
            imap_host = email_config.imap_server
        if email_config.imap_port:
            imap_port = int(email_config.imap_port)

        imap = await asyncio.to_thread(connect_imap, email_config.email_address, password, imap_host, imap_port)

        folders: list[str]
        host_lower = imap_host.lower()
        if "gmail" in host_lower:
            folders = GMAIL_FOLDERS
        elif "outlook" in host_lower:
            folders = OUTLOOK_FOLDERS
        elif "yahoo" in host_lower:
            folders = YAHOO_FOLDERS
        else:
            folders = ["INBOX"]

        for folder in folders:
            folder_result = await fetch_all_bank_emails_from_folder(imap, folder, first_sync, user_id, db)
            total_scanned += folder_result["scanned"]
            total_bank_emails += folder_result["bank_found"]
            total_transactions += folder_result["transactions_saved"]

            email_config.total_emails_scanned = (email_config.total_emails_scanned or 0) + folder_result["scanned"]
            email_config.transactions_found_total = (email_config.transactions_found_total or 0) + folder_result["transactions_saved"]
            await db.commit()

        await asyncio.to_thread(imap.logout)

        email_config.last_checked = datetime.datetime.now(datetime.timezone.utc)
        email_config.first_sync_done = True
        if update_status:
            email_config.sync_status = "completed"
            email_config.last_sync_error = None
            email_config.last_error = None
        email_config.emails_processed_total = (email_config.emails_processed_total or 0) + total_bank_emails
        email_config.transactions_found_total = (email_config.transactions_found_total or 0) + total_transactions

        duration_ms = int((datetime.datetime.now(datetime.timezone.utc) - started_at).total_seconds() * 1000)
        db.add(
            CollectionLog(
                user_id=user_id,
                log_type=CollectionLogType.email_check,
                source=CollectionSource.imap,
                emails_checked=total_scanned,
                transactions_found=total_transactions,
                non_bank_emails_rejected=max(total_scanned - total_bank_emails, 0),
                bank_emails_found=total_bank_emails,
                duplicates_skipped=0,
                error_message=None,
                duration_ms=duration_ms,
            )
        )
        await db.commit()

        return {
            "total_emails_scanned": total_scanned,
            "bank_emails_found": total_bank_emails,
            "transactions_saved": total_transactions,
            "first_sync": first_sync,
            "processed": total_scanned,
            "transactions_found": total_transactions,
            "error": None,
        }
    except Exception as exc:
        logger.exception("Email sync failed for user %s", user_id)
        if update_status:
            email_config.sync_status = "error"
            email_config.last_sync_error = str(exc)
            email_config.last_error = str(exc)
        email_config.last_checked = datetime.datetime.now(datetime.timezone.utc)

        duration_ms = int((datetime.datetime.now(datetime.timezone.utc) - started_at).total_seconds() * 1000)
        db.add(
            CollectionLog(
                user_id=user_id,
                log_type=CollectionLogType.error,
                source=CollectionSource.imap,
                emails_checked=total_scanned,
                transactions_found=total_transactions,
                non_bank_emails_rejected=max(total_scanned - total_bank_emails, 0),
                bank_emails_found=total_bank_emails,
                duplicates_skipped=0,
                error_message=str(exc),
                duration_ms=duration_ms,
            )
        )
        await db.commit()
        raise


async def reparse_email_raws(db: AsyncSession, user_id, since_days: int = 30) -> dict[str, int]:
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=since_days)
    stmt = select(SmsEmailRaw).where(
        SmsEmailRaw.user_id == user_id,
        SmsEmailRaw.source_type == SmsSourceType.email,
        or_(SmsEmailRaw.received_at.is_(None), SmsEmailRaw.received_at >= cutoff),
    )
    raws = (await db.execute(stmt)).scalars().all()

    updated = 0
    created = 0
    deleted = 0
    scanned = 0

    for raw in raws:
        scanned += 1
        combined = f"{raw.subject or ''} {raw.raw_content or ''}".strip()
        parsed = parse_sms(combined, sender=raw.sender) if looks_like_transaction_alert(combined) else None
        if not parsed:
            if raw.parsed_transaction_id:
                txn = await db.get(Transaction, raw.parsed_transaction_id)
                if txn:
                    await db.delete(txn)
                    deleted += 1
                raw.parsed_transaction_id = None
            raw.is_processed = False
            continue

        txn_type = TransactionType.credit if parsed.get("transaction_type") == "credit" else TransactionType.debit
        txn = None
        if raw.parsed_transaction_id:
            txn = await db.get(Transaction, raw.parsed_transaction_id)
        if txn:
            txn.transaction_type = txn_type
            txn.amount = parsed.get("amount") or txn.amount
            if parsed.get("merchant_name"):
                txn.merchant_name = parsed.get("merchant_name")
            if parsed.get("balance_after") is not None:
                txn.balance_after = parsed.get("balance_after")
            if parsed.get("reference_number"):
                txn.reference_number = parsed.get("reference_number")
            if parsed.get("transaction_date"):
                txn.transaction_date = parsed.get("transaction_date")
            updated += 1
        else:
            txn = Transaction(
                user_id=user_id,
                transaction_type=txn_type,
                amount=parsed.get("amount"),
                merchant_name=parsed.get("merchant_name"),
                description=(raw.raw_content or "")[:2000],
                balance_after=parsed.get("balance_after"),
                reference_number=parsed.get("reference_number"),
                transaction_date=parsed.get("transaction_date") or raw.received_at or datetime.datetime.now(datetime.timezone.utc),
                source=TransactionSource.email,
                bank_name=raw.bank_name,
                bank_code=raw.bank_code,
                sender_email=raw.sender,
                raw_message=combined[:2000],
            )
            db.add(txn)
            await db.flush()
            raw.parsed_transaction_id = txn.id
            created += 1

        raw.is_processed = True

    if updated or created or deleted:
        email_txn_count = (
            await db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.user_id == user_id,
                    Transaction.source == TransactionSource.email,
                )
            )
        ).scalar_one()
        configs = (
            await db.execute(
                select(EmailConfig).where(
                    EmailConfig.user_id == user_id,
                    EmailConfig.auth_type.in_([EmailAuthType.imap_password, EmailAuthType.oauth]),
                )
            )
        ).scalars()
        for config in configs:
            config.transactions_found_total = int(email_txn_count or 0)
        await db.commit()

    return {"scanned": scanned, "updated": updated, "created": created, "deleted": deleted}


class EmailCollectorService:
    async def test_connection(self, email_address: str, password: str, imap_server: str | None) -> dict[str, Any]:
        host = imap_server
        return await asyncio.to_thread(test_connection, email_address, password, host)

    async def fetch_and_parse_emails(self, db: AsyncSession, email_config: EmailConfig) -> dict[str, Any]:
        return await process_user_email_account(email_config.user_id, email_config.id, db)
