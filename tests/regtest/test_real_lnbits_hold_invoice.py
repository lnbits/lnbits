import asyncio
from subprocess import CalledProcessError

import pytest

from lnbits.settings import settings
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.lnbits import LNbitsWallet

from ..helpers import funding_source, is_fake
from .helpers import lnbits_lnd_endpoint, pay_real_invoice


@pytest.fixture
async def lnbits_lnd_wallet(monkeypatch: pytest.MonkeyPatch):
    """LNbitsWallet with an upstream LNbits that supports hold invoices."""
    monkeypatch.setattr(settings, "lnbits_endpoint", lnbits_lnd_endpoint)
    wallet = LNbitsWallet()
    yield wallet
    await wallet.cleanup()


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
@pytest.mark.skipif(
    funding_source.__class__.__name__ != "LNbitsWallet",
    reason="this only works for LNbitsWallet",
)
async def test_settle_real_hold_invoice_upstream(app, lnbits_lnd_wallet: LNbitsWallet):
    wallet = lnbits_lnd_wallet
    preimage, payment_hash = random_secret_and_hash()
    invoice = await wallet.create_hold_invoice(
        amount=1000, payment_hash=payment_hash, memo="test_settle_upstream_holdinvoice"
    )
    assert invoice.ok is True
    assert invoice.checking_id == payment_hash
    assert invoice.payment_request

    # invoice should still be open
    response = await wallet.settle_hold_invoice(preimage=preimage)
    assert response.ok is False

    stream = wallet.paid_invoices_stream()
    paid = asyncio.ensure_future(anext(stream))

    def pay_invoice():
        assert invoice.payment_request
        pay_real_invoice(invoice.payment_request)

    async def settle():
        # retry until the payment is held by the upstream node
        error_message = None
        for _ in range(10):
            await asyncio.sleep(1)
            response = await wallet.settle_hold_invoice(preimage=preimage)
            if response.ok:
                return
            error_message = response.error_message
        raise AssertionError(f"settle failed: {error_message}")

    await asyncio.gather(asyncio.to_thread(pay_invoice), settle())

    # the upstream LNbits notifies the settlement over its websocket
    assert await asyncio.wait_for(paid, timeout=10) == payment_hash
    await stream.aclose()

    status = await wallet.get_invoice_status(payment_hash)
    assert status.success


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
@pytest.mark.skipif(
    funding_source.__class__.__name__ != "LNbitsWallet",
    reason="this only works for LNbitsWallet",
)
async def test_cancel_real_hold_invoice_upstream(app, lnbits_lnd_wallet: LNbitsWallet):
    wallet = lnbits_lnd_wallet
    _, payment_hash = random_secret_and_hash()
    invoice = await wallet.create_hold_invoice(
        amount=1000, payment_hash=payment_hash, memo="test_cancel_upstream_holdinvoice"
    )
    assert invoice.ok is True

    def pay_invoice():
        assert invoice.payment_request
        try:
            pay_real_invoice(invoice.payment_request)
        except CalledProcessError:
            pass  # the payment fails once the invoice is cancelled

    async def cancel():
        await asyncio.sleep(1)
        response = await wallet.cancel_hold_invoice(payment_hash=payment_hash)
        assert response.ok is True

    await asyncio.gather(asyncio.to_thread(pay_invoice), cancel())

    status = await wallet.get_invoice_status(payment_hash)
    assert status.failed
