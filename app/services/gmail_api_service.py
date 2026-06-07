import base64
import datetime
import email
import json
import logging
from email.utils import parseaddr
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection_log import CollectionLog
from app.models.email_config import EmailConfig
from app.models.enums import CollectionLogType, CollectionSource, SmsSourceType, TransactionSource, TransactionType
from app.models.sms_email_raw import SmsEmailRaw
from app.models.transaction import Transaction
from app.core.config import settings
from app.services.bank_domain_whitelist import get_all_bank_domains, get_bank_info, is_bank_email
from app.services.crypto_service import decrypt_text, encrypt_text
from app.services.sms_parser_service import looks_like_transaction_alert, parse_sms
from app.services.emi_upsert_service import process_emi_from_email

logger = logging.getLogger(__name__)


class GmailAPIService:
    def get_credentials(self, refresh_token_encrypted: str, access_token_encrypted: str | None = None,
                        expiry: datetime.datetime | None = None) -> Credentials:
        refresh_token = decrypt_text(refresh_token_encrypted)
        token = decrypt_text(access_token_encrypted) if access_token_encrypted else None
        creds = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds

    def _extract_body(self, payload: dict[str, Any]) -> str:
        def _decode_data(data: str | None) -> str:
            if not data:
                return ""
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        plain_parts: list[str] = []
        html_parts: list[str] = []
        stack = [payload]

        while stack:
            part = stack.pop()
            stack.extend(part.get("parts", []) or [])
            data = part.get("body", {}).get("data")
            if not data:
                continue

            mime_type = part.get("mimeType")
            if mime_type == "text/plain":
                plain_parts.append(_decode_data(data))
            elif mime_type == "text/html":
                html_parts.append(BeautifulSoup(_decode_data(data), "lxml").get_text(" ", strip=True))

        if plain_parts:
            return "\n".join(part.strip() for part in plain_parts if part.strip())
        if html_parts:
            return "\n".join(part.strip() for part in html_parts if part.strip())
        return _decode_data(payload.get("body", {}).get("data")).strip()

    def fetch_bank_emails(
        self,
        credentials: Credentials,
        last_checked: datetime.datetime | None,
        *,
        force_full_sync: bool = False,
        max_messages: int = 500,
    ) -> list[dict[str, Any]]:
        service = build("gmail", "v1", credentials=credentials)
        base_query = "in:anywhere -in:trash newer_than:365d"
        if last_checked and not force_full_sync:
            safe_since = last_checked - datetime.timedelta(minutes=5)
            base_query += f" after:{int(safe_since.timestamp())}"

        message_ids: list[str] = []
        seen_ids: set[str] = set()
        domains = get_all_bank_domains()
        domain_batches = [domains[index : index + 8] for index in range(0, len(domains), 8)]
        for batch in domain_batches:
            if len(message_ids) >= max_messages:
                break

            query = f"{base_query} {{{' '.join(f'from:{domain}' for domain in batch)}}}"
            page_token = None
            while len(message_ids) < max_messages:
                response = (
                    service.users()
                    .messages()
                    .list(
                        userId="me",
                        q=query,
                        maxResults=min(100, max_messages - len(message_ids)),
                        pageToken=page_token,
                    )
                    .execute()
                )
                for message in response.get("messages", []):
                    message_id = message.get("id")
                    if message_id and message_id not in seen_ids:
                        seen_ids.add(message_id)
                        message_ids.append(message_id)
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        if not message_ids:
            query = base_query
            response = service.users().messages().list(userId="me", q=query, maxResults=100).execute()
            message_ids = [message["id"] for message in response.get("messages", []) if message.get("id")]

        results: list[dict[str, Any]] = []
        for gmail_id in message_ids:
            metadata = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=gmail_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Message-ID", "Date"],
                )
                .execute()
            )
            payload = metadata.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            sender = headers.get("from", "")
            subject = headers.get("subject", "")
            sender_email = parseaddr(sender)[1].strip().lower()
            header_message_id = (headers.get("message-id") or "").strip().strip("<>") or metadata.get("id")
            date_header = headers.get("date")
            received_at = datetime.datetime.now(datetime.timezone.utc)
            if date_header:
                try:
                    parsed = email.utils.parsedate_to_datetime(date_header)
                    if parsed and parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                    received_at = parsed or received_at
                except Exception:
                    received_at = datetime.datetime.now(datetime.timezone.utc)

            body = ""
            if is_bank_email(sender_email):
                full = service.users().messages().get(userId="me", id=gmail_id, format="full").execute()
                body = self._extract_body(full.get("payload", {}))

            results.append(
                {
                    "message_id": header_message_id,
                    "sender": sender,
                    "subject": subject,
                    "body": body,
                    "received_at": received_at,
                    "gmail_id": metadata.get("id"),
                }
            )
        return results

    def mark_as_read(self, credentials: Credentials, message_id: str) -> None:
        service = build("gmail", "v1", credentials=credentials)
        try:
            service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        except HttpError as exc:
            if "insufficientPermissions" in str(exc):
                return
            raise

    async def process_gmail_oauth(
        self,
        db: AsyncSession,
        email_config: EmailConfig,
        *,
        force_full_sync: bool = False,
    ) -> dict:
        started = datetime.datetime.now(datetime.timezone.utc)
        stats = {
            "total_emails_scanned": 0,
            "bank_emails_found": 0,
            "non_bank_skipped": 0,
            "transactions_saved": 0,
            "duplicates_skipped": 0,
            "parse_failed": 0,
        }
        error_message = None
        try:
            creds = self.get_credentials(
                email_config.oauth_refresh_token_encrypted or "",
                email_config.oauth_access_token_encrypted,
                email_config.oauth_token_expiry,
            )
            email_config.oauth_access_token_encrypted = encrypt_text(creds.token or "")
            email_config.oauth_token_expiry = creds.expiry
            messages = self.fetch_bank_emails(creds, email_config.last_checked, force_full_sync=force_full_sync)
            for message in messages:
                stats["total_emails_scanned"] += 1
                sender_email = parseaddr(message.get("sender", ""))[1].strip().lower()
                logger.debug("Checking email from: %s", sender_email or "unknown")

                if not is_bank_email(sender_email):
                    stats["non_bank_skipped"] += 1
                    logger.debug("Non-bank domain rejected: %s", sender_email or "unknown")
                    continue

                bank_info = get_bank_info(sender_email)
                if not bank_info:
                    stats["non_bank_skipped"] += 1
                    continue
                stats["bank_emails_found"] += 1
                logger.info("Bank email accepted: %s (%s)", sender_email, bank_info["bank_name"])

                stmt = select(SmsEmailRaw).where(
                    SmsEmailRaw.user_id == email_config.user_id,
                    SmsEmailRaw.message_id == message.get("message_id"),
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()
                if existing:
                    stats["duplicates_skipped"] += 1
                    logger.info("Duplicate skipped: %s", message.get("message_id"))
                    continue
                raw = SmsEmailRaw(
                    user_id=email_config.user_id,
                    source_type=SmsSourceType.email,
                    raw_content=message.get("body", ""),
                    sender=sender_email,
                    bank_name=bank_info["bank_name"],
                    bank_code=bank_info["bank_code"],
                    subject=message.get("subject"),
                    message_id=message.get("message_id"),
                    received_at=message.get("received_at"),
                )
                db.add(raw)
                body = message.get("body", "")
                subject = message.get("subject", "")
                parse_text = f"{subject}\n{body}".strip()
                parsed = parse_sms(parse_text, sender=sender_email) if looks_like_transaction_alert(parse_text) else None
                if not parsed:
                    stats["parse_failed"] += 1
                    logger.debug("Parse failed for: %s", subject)
                    raw.is_processed = False
                else:
                    txn = Transaction(
                        user_id=email_config.user_id,
                        transaction_type=TransactionType.credit if parsed.get("transaction_type") == "credit" else TransactionType.debit,
                        amount=parsed.get("amount"),
                        merchant_name=parsed.get("merchant_name"),
                        description=body,
                        transaction_date=parsed.get("transaction_date") or message.get("received_at") or datetime.datetime.now(datetime.timezone.utc),
                        balance_after=parsed.get("balance_after"),
                        reference_number=parsed.get("reference_number"),
                        bank_name=bank_info["bank_name"],
                        bank_code=bank_info["bank_code"],
                        sender_email=sender_email,
                        source=TransactionSource.email,
                        raw_message=parse_text,
                    )
                    db.add(txn)
                    await db.flush()
                    raw.parsed_transaction_id = txn.id
                    raw.is_processed = True
                    stats["transactions_saved"] += 1
                    logger.info(
                        "Transaction saved: Rs.%s at %s from %s",
                        parsed.get("amount"),
                        parsed.get("merchant_name") or "Unknown Merchant",
                        bank_info["bank_name"],
                    )

                # --- EMI extraction ---
                try:
                    raw_id = raw.id if raw.id else None
                    emi_count = await process_emi_from_email(
                        db=db,
                        user_id=email_config.user_id,
                        bank_code=bank_info["bank_code"],
                        email_body=body,
                        email_subject=subject,
                        source_raw_id=raw_id,
                    )
                    if emi_count:
                        logger.info(
                            "EMI: %d record(s) upserted from Gmail message %s",
                            emi_count,
                            message.get("message_id"),
                        )
                except Exception:
                    logger.exception(
                        "EMI processing failed for Gmail message %s",
                        message.get("message_id"),
                    )
                try:
                    self.mark_as_read(creds, message.get("gmail_id", ""))
                except HttpError as exc:
                    if "insufficientPermissions" not in str(exc):
                        raise
            email_config.last_checked = datetime.datetime.now(datetime.timezone.utc)
            email_config.first_sync_done = True
            email_config.sync_status = "completed"
            email_config.last_sync_error = None
            email_config.total_emails_scanned = (
                (email_config.total_emails_scanned or 0) + stats["total_emails_scanned"]
            )
            email_config.emails_processed_total = (
                (email_config.emails_processed_total or 0) + stats["total_emails_scanned"]
            )
            email_config.transactions_found_total = (
                (email_config.transactions_found_total or 0) + stats["transactions_saved"]
            )
            email_config.last_error = None
            await db.commit()
        except Exception as exc:
            error_message = str(exc)
            email_config.sync_status = "error"
            email_config.last_sync_error = error_message
            email_config.last_error = error_message
            await db.commit()
        duration = int((datetime.datetime.now(datetime.timezone.utc) - started).total_seconds() * 1000)
        log = CollectionLog(
            user_id=email_config.user_id,
            log_type=CollectionLogType.email_check if not error_message else CollectionLogType.error,
            source=CollectionSource.oauth,
            emails_checked=stats["total_emails_scanned"],
            transactions_found=stats["transactions_saved"],
            non_bank_emails_rejected=stats["non_bank_skipped"],
            bank_emails_found=stats["bank_emails_found"],
            duplicates_skipped=stats["duplicates_skipped"],
            error_message=error_message,
            duration_ms=duration,
        )
        db.add(log)
        await db.commit()
        logger.info(
            "Email scan complete for user %s: %s scanned, %s bank emails, %s non-bank skipped, %s transactions saved",
            email_config.user_id,
            stats["total_emails_scanned"],
            stats["bank_emails_found"],
            stats["non_bank_skipped"],
            stats["transactions_saved"],
        )
        return {
            **stats,
            "processed": stats["total_emails_scanned"],
            "transactions_found": stats["transactions_saved"],
            "error": error_message,
        }
