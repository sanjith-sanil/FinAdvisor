import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    email = f"newuser_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "full_name": "New User",
        "email": email,
        "phone_number": "+919876543200",
        "password": "StrongPassword123!",
        "confirm_password": "StrongPassword123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email
    assert "access_token" in data
    assert data["customer_id"].startswith("CUST")


@pytest.mark.asyncio
async def test_register_password_mismatch(client: AsyncClient):
    payload = {
        "full_name": "Mismatched Pass User",
        "email": f"mismatch_{uuid.uuid4().hex[:6]}@example.com",
        "phone_number": "+919876543200",
        "password": "Password123!",
        "confirm_password": "DifferentPassword456!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "Passwords do not match" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user):
    payload = {
        "full_name": "Duplicate User",
        "email": test_user.email,
        "phone_number": "+919876543200",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    payload = {
        "email": test_user.email,
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert "access_token" in data
    assert data["current_streak"] >= 1


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_user):
    payload = {
        "email": test_user.email,
        "password": "WrongPassword999!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]
