import pytest
import pytest_asyncio

from lnbits.core.crud import get_wallet
from tests.conftest import client, invoice
from tests.extensions.invoices.conftest import invoices_wallet
from tests.helpers import credit_wallet
from tests.mocks import WALLET


@pytest.mark.asyncio
async def test_create_invoice_valid(client, invoices_wallet):
    query = {
        "status": "open",
        "currency": "EUR",
        "company_name": "LNBits, Inc.",
        "first_name": "Ben",
        "last_name": "Arc",
        "email": "ben@legend.arc",
        "items": [
            {"amount": 2.34, "description": "Item 1"},
            {"amount": 0.98, "description": "Item 2"}
        ]
    }

    status = query["status"]
    currency = query["currency"]
    fname = query["first_name"]
    total = sum(d['amount'] for d in query["items"])

    response = await client.post("/invoices/api/v1/invoice", json=query, headers={"X-Api-Key": invoices_wallet.inkey})
    assert response.status_code == 201
    data = response.json()
    
    assert data["status"] == status
    assert data["wallet"] == invoices_wallet.id
    assert data["currency"] == currency
    assert data["first_name"] == fname
    assert sum(d["amount"] / 100 for d in data["items"]) == total
