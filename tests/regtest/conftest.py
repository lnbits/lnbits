import pytest

from .helpers import (
    get_hold_invoice,
    get_real_invoice,
    get_real_invoice_noroute,
    is_boltz_wallet,
    sync_boltz_liquid_chain,
)


@pytest.fixture
def sync_boltz_wallet():
    if is_boltz_wallet:
        sync_boltz_liquid_chain()


@pytest.fixture(scope="function")
async def hold_invoice(sync_boltz_wallet):
    invoice = get_hold_invoice(100)
    yield invoice
    del invoice


@pytest.fixture(scope="function")
async def real_invoice(sync_boltz_wallet):
    invoice = get_real_invoice(100)
    yield {"bolt11": invoice["payment_request"]}
    del invoice


@pytest.fixture(scope="function")
async def real_amountless_invoice():
    invoice = get_real_invoice(0)
    yield invoice["payment_request"]
    del invoice


@pytest.fixture(scope="function")
async def real_invoice_noroute():
    invoice = get_real_invoice_noroute(100)
    yield {
        "bolt11": invoice["payment_request"],
        "payment_hash": invoice["r_hash"],
    }
    del invoice
