import datetime
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_transactions(client: AsyncClient, test_user, auth_headers):
    payload = {
        "user_id": str(test_user.id),
        "transaction_type": "debit",
        "amount": 2500.0,
        "merchant_name": "Flipkart",
        "merchant_category": "Shopping",
        "transaction_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "manual",
    }
    # Create transaction
    res_create = await client.post("/api/v1/transactions/", json=payload, headers=auth_headers)
    assert res_create.status_code == 200
    txn_data = res_create.json()
    assert txn_data["merchant_name"] == "Flipkart"
    assert txn_data["amount"] == 2500.0
    txn_id = txn_data["id"]

    # List transactions
    res_list = await client.get(f"/api/v1/transactions/?user_id={test_user.id}", headers=auth_headers)
    assert res_list.status_code == 200
    txns = res_list.json()
    assert len(txns) >= 1
    assert any(t["id"] == txn_id for t in txns)


@pytest.mark.asyncio
async def test_daily_spending_endpoint(client: AsyncClient, test_user, auth_headers):
    # Daily spending query
    res = await client.get(f"/api/v1/transactions/daily-spending?user_id={test_user.id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "days" in data
    assert "thresholds" in data
    assert "p25" in data["thresholds"]


@pytest.mark.asyncio
async def test_export_csv_endpoint(client: AsyncClient, test_user, auth_headers):
    res = await client.get(f"/api/v1/transactions/export/csv?user_id={test_user.id}", headers=auth_headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
