import datetime
import os
import secrets
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.models.email_config import EmailConfig
from app.models.enums import EmailAuthType
from app.models.user import User
from app.services.crypto_service import encrypt_text

router = APIRouter(prefix="/api/v1/auth/google", tags=["google-oauth"])


def _generate_customer_id() -> str:
    return f"CUST{uuid.uuid4().int % 10**8:08d}"


def _generate_sms_key() -> str:
    return secrets.token_urlsafe(32)


def _build_flow(state: str, scopes: list[str], redirect_uri: str) -> Flow:
    if settings.environment == "development":
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    if not settings.google_client_id or not settings.google_client_secret or not redirect_uri:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=scopes,
        state=state,
    )
    flow.redirect_uri = redirect_uri
    return flow


@router.get("/authorize")
async def authorize(user_id: uuid.UUID) -> RedirectResponse:
    flow = _build_flow(
        state=str(user_id),
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",
        ],
        redirect_uri=settings.google_redirect_uri or "",
    )
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(authorization_url)


@router.get("/callback")
async def callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    state = request.query_params.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")
    flow = _build_flow(
        state=state,
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",
        ],
        redirect_uri=settings.google_redirect_uri or "",
    )
    flow.fetch_token(authorization_response=str(request.url))
    credentials = flow.credentials
    if not credentials.refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh token. Re-consent required.")

    service = build("gmail", "v1", credentials=credentials)
    profile = service.users().getProfile(userId="me").execute()
    email_address = profile.get("emailAddress")

    user = await db.get(User, uuid.UUID(state))
    if not user and email_address:
        stmt = select(User).where(User.email == email_address)
        user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stmt = select(EmailConfig).where(EmailConfig.user_id == user.id)
    config = (await db.execute(stmt)).scalar_one_or_none()
    if not config:
        config = EmailConfig(
            user_id=user.id,
            email_address=email_address,
            auth_type=EmailAuthType.oauth,
            oauth_refresh_token_encrypted=encrypt_text(credentials.refresh_token or ""),
            oauth_access_token_encrypted=encrypt_text(credentials.token or ""),
            oauth_token_expiry=credentials.expiry,
        )
        db.add(config)
    else:
        config.email_address = email_address
        config.auth_type = EmailAuthType.oauth
        config.oauth_refresh_token_encrypted = encrypt_text(credentials.refresh_token or "")
        config.oauth_access_token_encrypted = encrypt_text(credentials.token or "")
        config.oauth_token_expiry = credentials.expiry
        config.is_active = True

    user.email_collection_configured = True
    user.registration_step = max(user.registration_step or 1, 3)
    await db.commit()
    return RedirectResponse(url=f"/register?step=3&user_id={user.id}")


@router.get("/login/authorize")
async def login_authorize() -> RedirectResponse:
    login_redirect_uri = settings.google_login_redirect_uri or f"{settings.server_base_url}/api/v1/auth/google/login/callback"
    flow = _build_flow(
        state="login",
        scopes=[
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid",
        ],
        redirect_uri=login_redirect_uri,
    )
    authorization_url, _ = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="select_account",
    )
    return RedirectResponse(authorization_url)


@router.get("/login/callback")
async def login_callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    try:
        login_redirect_uri = settings.google_login_redirect_uri or f"{settings.server_base_url}/api/v1/auth/google/login/callback"
        flow = _build_flow(
            state="login",
            scopes=[
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
                "openid",
            ],
            redirect_uri=login_redirect_uri,
        )
        flow.fetch_token(authorization_response=str(request.url))
        credentials = flow.credentials
        service = build("oauth2", "v2", credentials=credentials)
        profile = service.userinfo().get().execute()
        email_address = profile.get("email")
        full_name = profile.get("name") or (email_address.split("@")[0] if email_address else "User")
        if not email_address:
            params = urlencode({"google_error": "Missing email from Google"})
            return RedirectResponse(url=f"/login?{params}")

        stmt = select(User).where(User.email == email_address)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if not user:
            user = User(
                customer_id=_generate_customer_id(),
                full_name=full_name,
                email=email_address,
                password_hash=None,
                sms_webhook_key=_generate_sms_key(),
                registration_step=1,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        params = urlencode(
            {
                "google_login": "1",
                "user_id": str(user.id),
                "customer_id": user.customer_id,
                "full_name": user.full_name,
                "email": user.email,
            }
        )
        return RedirectResponse(url=f"/login?{params}")
    except Exception:
        params = urlencode({"google_error": "Google login failed. Please try again."})
        return RedirectResponse(url=f"/login?{params}")
