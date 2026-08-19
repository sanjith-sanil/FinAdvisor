import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_user_badges(client: AsyncClient, test_user, auth_headers):
    res = await client.get(f"/api/v1/users/{test_user.id}/badges", headers=auth_headers)
    assert res.status_code == 200
    badges = res.json()
    assert isinstance(badges, list)
    assert len(badges) == 10  # 10 milestone badges

    badge_ids = [b["id"] for b in badges]
    assert "shield_up" in badge_ids
    assert "streak_master" in badge_ids
    assert "card_collector" in badge_ids
    assert "data_driven" in badge_ids
    assert "budget_boss" in badge_ids

    # Each badge should have required fields
    for badge in badges:
        assert "title" in badge
        assert "description" in badge
        assert "icon" in badge
        assert "unlocked" in badge
        assert "progress" in badge
