import pytest
import pytest_asyncio
from loguru import logger

from lnbits.core.crud import get_wallet
from tests.conftest import adminkey_headers_from, client, invoice
from tests.extensions.invoices.conftest import accounting_invoice, invoices_wallet
from tests.helpers import credit_wallet
from tests.mocks import WALLET


@pytest.mark.asyncio
async def test_invoices_unknown_invoice(client):
    response = await client.get("/invoices/pay/u")
    assert response.json() == {"detail": "Invoice does not exist."}


@pytest.mark.asyncio
async def test_invoices_api_create_invoice_valid(client, invoices_wallet):
    query = {
        "status": "open",
        "currency": "EUR",
        "company_name": "LNBits, Inc.",
        "first_name": "Ben",
        "last_name": "Arc",
        "email": "ben@legend.arc",
        "items": [
            {"amount": 2.34, "description": "Item 1"},
            {"amount": 0.98, "description": "Item 2"},
        ],
    }

    status = query["status"]
    currency = query["currency"]
    fname = query["first_name"]
    total = sum(d["amount"] for d in query["items"])

    response = await client.post(
        "/invoices/api/v1/invoice",
        json=query,
        headers={"X-Api-Key": invoices_wallet.inkey},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["status"] == status
    assert data["wallet"] == invoices_wallet.id
    assert data["currency"] == currency
    assert data["first_name"] == fname
    assert sum(d["amount"] / 100 for d in data["items"]) == total


@pytest.mark.asyncio
async def test_invoices_api_partial_pay_invoice(
    client, accounting_invoice, adminkey_headers_from
):
    invoice_id = accounting_invoice["id"]
    amount_to_pay = int(5.05 * 100)  # mock invoice total amount is 10 USD

    # ask for an invoice
    response = await client.post(
        f"/invoices/api/v1/invoice/{invoice_id}/payments?famount={amount_to_pay}"
    )
    assert response.status_code < 300
    data = response.json()
    payment_hash = data["payment_hash"]

    # pay the invoice
    data = {"out": True, "bolt11": data["payment_request"]}
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code < 300
    assert len(response.json()["payment_hash"]) == 64
    assert len(response.json()["checking_id"]) > 0

    # check invoice is paid
    response = await client.get(
        f"/invoices/api/v1/invoice/{invoice_id}/payments/{payment_hash}"
    )
    assert response.status_code == 200
    assert response.json()["paid"] == True

    # check invoice status
    response = await client.get(f"/invoices/api/v1/invoice/{invoice_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "open"


####
#
# TEST FAILS FOR NOW, AS LISTENERS ARE NOT WORKING ON TESTING
#
###

# @pytest.mark.asyncio
# async def test_invoices_api_full_pay_invoice(client, accounting_invoice, adminkey_headers_to):
#     invoice_id = accounting_invoice["id"]
#     print(accounting_invoice["id"])
#     amount_to_pay = int(10.20 * 100)

#     # ask for an invoice
#     response = await client.post(
#         f"/invoices/api/v1/invoice/{invoice_id}/payments?famount={amount_to_pay}"
#     )
#     assert response.status_code == 201
#     data = response.json()
#     payment_hash = data["payment_hash"]

#     # pay the invoice
#     data = {"out": True, "bolt11": data["payment_request"]}
#     response = await client.post(
#         "/api/v1/payments", json=data, headers=adminkey_headers_to
#     )
#     assert response.status_code < 300
#     assert len(response.json()["payment_hash"]) == 64
#     assert len(response.json()["checking_id"]) > 0

#     # check invoice is paid
#     response = await client.get(
#         f"/invoices/api/v1/invoice/{invoice_id}/payments/{payment_hash}"
#     )
#     assert response.status_code == 200
#     assert response.json()["paid"] == True

#     # check invoice status
#     response = await client.get(f"/invoices/api/v1/invoice/{invoice_id}")
#     assert response.status_code == 200
#     data = response.json()

#     print(data)
#     assert data["status"] == "paid"
