import asyncio
import os
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

# Ensure test encryption key is set for crypto service
os.environ["EMAIL_ENCRYPTION_KEY"] = "P1d6vFm90K3rL4_Xj5w8u7t2Y1z4q7A0B3c6E9h2J5M="
os.environ["SECRET_KEY"] = "test_secret_key_for_jwt_testing_purposes_only"

# Register SQLite compilers for PostgreSQL-specific types
@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

from app.core.security import create_access_token
from app.db.base import Base
from app.db.database import get_db
from app.models import (
    BankAccount,
    BudgetGoal,
    Card,
    CardBenefit,
    CardEmi,
    ChatbotMessage,
    ChatbotQuestionTemplate,
    ChatbotSession,
    CollectionLog,
    EmailConfig,
    Notification,
    PdfUpload,
    SmsEmailRaw,
    Transaction,
    User,
)
from main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        id=uuid.uuid4(),
        customer_id=f"CUST{uuid.uuid4().int % 10**8:08d}",
        full_name="Test User",
        email=f"test_{uuid.uuid4().hex[:6]}@example.com",
        phone_number="+919876543210",
        password_hash=pwd_context.hash("Password123!"),
        sms_webhook_key=f"sms_key_{uuid.uuid4().hex}",
        current_streak=3,
        longest_streak=5,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        id=uuid.uuid4(),
        customer_id=f"CUST{uuid.uuid4().int % 10**8:08d}",
        full_name="Other User",
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        phone_number="+919876543211",
        password_hash=pwd_context.hash("Password123!"),
        sms_webhook_key=f"sms_key_{uuid.uuid4().hex}",
        current_streak=1,
        longest_streak=1,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user_headers(other_user: User) -> dict[str, str]:
    token = create_access_token(other_user.id)
    return {"Authorization": f"Bearer {token}"}
