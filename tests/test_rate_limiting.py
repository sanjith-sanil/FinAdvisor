import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_login_rate_limiting(client: AsyncClient, test_user):
    payload = {
        "email": test_user.email,
        "password": "Password123!",
    }

    # /auth/login limit is 5/minute
    responses = []
    for _ in range(7):
        res = await client.post("/api/v1/auth/login", json=payload)
        responses.append(res)

    status_codes = [r.status_code for r in responses]
    # At least one request should be rate-limited with HTTP 429
    assert 429 in status_codes
    rate_limited_res = next(r for r in responses if r.status_code == 429)
    assert "Rate limit exceeded" in rate_limited_res.json()["detail"]
