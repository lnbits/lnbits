import pytest_asyncio

from .helpers import get_hold_invoice, get_real_invoice


@pytest_asyncio.fixture(scope="function")
async def hold_invoice():
    invoice = get_hold_invoice(100)
    yield invoice
    del invoice


@pytest_asyncio.fixture(scope="function")
async def real_invoice():
    invoice = get_real_invoice(100)
    yield {"bolt11": invoice["payment_request"]}
    del invoice
