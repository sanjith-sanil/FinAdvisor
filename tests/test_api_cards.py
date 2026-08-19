import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_cards(client: AsyncClient, test_user, auth_headers):
    payload = {
        "user_id": str(test_user.id),
        "bank_name": "HDFC Bank",
        "card_holder_name": "Test User",
        "card_type": "credit",
        "card_last4": "4321",
        "card_network": "visa",
        "credit_limit": 150000.0,
        "current_balance": 15000.0,
        "payment_due_date": 15,
        "annual_fee": 1000.0,
        "lounge_access": True,
    }
    # Create card
    res_create = await client.post("/api/v1/cards/", json=payload, headers=auth_headers)
    assert res_create.status_code == 200
    card_data = res_create.json()
    assert card_data["bank_name"] == "HDFC Bank"
    assert card_data["card_last4"] == "4321"
    card_id = card_data["id"]

    # List cards
    res_list = await client.get(f"/api/v1/cards/?user_id={test_user.id}", headers=auth_headers)
    assert res_list.status_code == 200
    cards = res_list.json()
    assert len(cards) >= 1
    assert any(c["id"] == card_id for c in cards)

    # Get card details
    res_detail = await client.get(f"/api/v1/cards/{card_id}/details?user_id={test_user.id}", headers=auth_headers)
    assert res_detail.status_code == 200
    details = res_detail.json()
    assert "utilization_percentage" in details

    # Soft delete card
    res_delete = await client.delete(f"/api/v1/cards/{card_id}?user_id={test_user.id}", headers=auth_headers)
    assert res_delete.status_code == 200


@pytest.mark.asyncio
async def test_create_card_invalid_last4(client: AsyncClient, test_user, auth_headers):
    payload = {
        "user_id": str(test_user.id),
        "bank_name": "HDFC Bank",
        "card_holder_name": "Test User",
        "card_type": "credit",
        "card_last4": "12",  # invalid: must be 4 digits
    }
    response = await client.post("/api/v1/cards/", json=payload, headers=auth_headers)
    assert response.status_code == 422
