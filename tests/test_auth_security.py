import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_protected_route_without_token(client: AsyncClient):
    # Accessing cards list without auth header
    res = await client.get("/api/v1/cards/")
    assert res.status_code == 401
    assert "credentials" in res.json().get("detail", "").lower() or "not authenticated" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token(client: AsyncClient):
    # Accessing cards with corrupted JWT
    res = await client.get("/api/v1/cards/", headers={"Authorization": "Bearer invalid_or_corrupted_token"})
    assert res.status_code == 401
    assert "Could not validate credentials" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_cross_user_access_forbidden(client: AsyncClient, test_user, other_user, auth_headers):
    # test_user attempts to access other_user's profile
    res = await client.get(f"/api/v1/users/{other_user.id}", headers=auth_headers)
    assert res.status_code == 403
    assert "Forbidden" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_invalid_request_schema_validation_error(client: AsyncClient, auth_headers):
    # POST transaction with missing required fields
    invalid_payload = {"amount": "not-a-number"}
    res = await client.post("/api/v1/transactions/", json=invalid_payload, headers=auth_headers)
    assert res.status_code == 422
