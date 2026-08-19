import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_set_and_get_user_budget(client: AsyncClient, test_user, auth_headers):
    payload = {"monthly_limit": 50000.0}
    # Set budget
    res_set = await client.post(f"/api/v1/users/{test_user.id}/budget", json=payload, headers=auth_headers)
    assert res_set.status_code == 200
    assert res_set.json()["monthly_limit"] == 50000.0

    # Get budget
    res_get = await client.get(f"/api/v1/users/{test_user.id}/budget", headers=auth_headers)
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["monthly_limit"] == 50000.0
    assert "current_spent" in data
