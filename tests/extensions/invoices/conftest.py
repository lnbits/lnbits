import pytest
import pytest_asyncio

from lnbits.core.crud import create_account, create_wallet
from lnbits.extensions.invoices.crud import (
    create_invoice_internal,
    create_invoice_items,
)
from lnbits.extensions.invoices.models import CreateInvoiceData


@pytest_asyncio.fixture
async def invoices_wallet():
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="invoices_test")

    return wallet


@pytest_asyncio.fixture
async def accounting_invoice(invoices_wallet):
    invoice_data = CreateInvoiceData(
        status="open",
        currency="USD",
        company_name="LNBits, Inc",
        first_name="Ben",
        last_name="Arc",
        items=[{"amount": 10.20, "description": "Item costs 10.20"}],
    )
    invoice = await create_invoice_internal(
        wallet_id=invoices_wallet.id, data=invoice_data
    )
    items = await create_invoice_items(invoice_id=invoice.id, data=invoice_data.items)

    invoice_dict = invoice.dict()
    invoice_dict["items"] = items
    return invoice_dict
