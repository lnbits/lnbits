import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from subprocess import CalledProcessError

import pytest
from bolt11 import decode

from lnbits.core.crud import get_payments, get_standalone_payment, get_wallet
from lnbits.core.services import payments as service
from lnbits.exceptions import InvoiceError
from lnbits.settings import settings
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets import lnbits
from lnbits.wallets.lnbits import LNbitsWallet

from ..helpers import funding_source, is_fake
from .helpers import docker_lightning_cli, lnbits_lnd_endpoint


@pytest.fixture
async def lnbits_lnd_wallet(app, monkeypatch: pytest.MonkeyPatch):
    """Downstream payment services funded by an upstream LNbits on LND."""
    monkeypatch.setattr(settings, "lnbits_endpoint", lnbits_lnd_endpoint)
    wallet = LNbitsWallet()
    monkeypatch.setattr(service, "get_funding_source", lambda: wallet)
    try:
        yield wallet
    finally:
        await wallet.cleanup()


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
@pytest.mark.skipif(
    funding_source.__class__.__name__ != "LNbitsWallet",
    reason="this only works for LNbitsWallet",
)
@pytest.mark.parametrize(
    ("description_hash", "unhashed_description"),
    [
        (None, b"hold metadata"),
        (b"e" * 32, None),
        (b"e" * 32, b"hold metadata"),
    ],
)
async def test_settle_real_hold_invoice_upstream(
    app,
    lnbits_lnd_wallet: LNbitsWallet,
    from_wallet,
    monkeypatch,
    description_hash,
    unhashed_description,
):
    wallet = lnbits_lnd_wallet
    before = await get_wallet(from_wallet.id)
    assert before
    preimage, payment_hash = random_secret_and_hash()
    payment = await service.create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        payment_hash=payment_hash,
        memo="test_settle_upstream_holdinvoice",
        expiry=600,
        description_hash=description_hash,
        unhashed_description=unhashed_description,
    )
    invoice = decode(payment.bolt11)
    assert invoice.payment_hash == payment_hash
    assert invoice.amount_msat == 1_000_000
    assert invoice.expiry == 600
    assert invoice.description_hash == (
        description_hash.hex()
        if description_hash
        else hashlib.sha256(unhashed_description).hexdigest()
    )

    with pytest.raises(InvoiceError):
        await service.settle_hold_invoice(payment, preimage)

    # Establish the websocket subscription before allowing settlement.
    connected = asyncio.Event()
    connect = lnbits.connect

    @asynccontextmanager
    async def subscribed(*args, **kwargs):
        async with connect(*args, **kwargs) as websocket:
            if asyncio.current_task() is paid:
                connected.set()
            yield websocket

    monkeypatch.setattr(lnbits, "connect", subscribed)
    stream = wallet.paid_invoices_stream()
    paid = asyncio.create_task(anext(stream))
    try:
        await asyncio.wait_for(connected.wait(), timeout=10)
        async with _paying(wallet, payment.bolt11, payment_hash) as payer:
            await _wait_for_invoice_state(payment_hash, "ACCEPTED", payer)
            await _assert_pending_without_credit(
                payment_hash, from_wallet.id, before.balance_msat
            )
            assert (await wallet.get_invoice_status(payment_hash)).pending
            assert (await service.settle_hold_invoice(payment, preimage)).ok
            await _wait_for_invoice_state(payment_hash, "SETTLED")
            result = await asyncio.wait_for(payer, timeout=15)
            assert result["status"] == "SUCCEEDED", result
            assert result["payment_preimage"] == preimage

            # Preserve actual upstream websocket coverage and reconcile downstream.
            assert await asyncio.wait_for(paid, timeout=10) == payment_hash
            for _ in range(2):
                updated = await service.update_invoice_from_paid_invoices_stream(
                    payment_hash
                )
                assert updated and updated.success
                await service.update_pending_payment(updated)
            stored = await get_standalone_payment(payment_hash, incoming=True)
            assert stored and stored.success
            assert stored.preimage == preimage
            after = await get_wallet(from_wallet.id)
            assert after and after.balance_msat == before.balance_msat + 1_000_000
            records = await get_payments(wallet_id=from_wallet.id, incoming=True)
            assert len([p for p in records if p.payment_hash == payment_hash]) == 1
            assert (await wallet.get_invoice_status(payment_hash)).success
    finally:
        paid.cancel()
        await asyncio.gather(paid, return_exceptions=True)
        await stream.aclose()


@pytest.mark.anyio
@pytest.mark.skipif(is_fake, reason="this only works in regtest")
@pytest.mark.skipif(
    funding_source.__class__.__name__ != "LNbitsWallet",
    reason="this only works for LNbitsWallet",
)
async def test_cancel_real_hold_invoice_upstream(
    app, lnbits_lnd_wallet: LNbitsWallet, from_wallet
):
    wallet = lnbits_lnd_wallet
    before = await get_wallet(from_wallet.id)
    assert before
    _, payment_hash = random_secret_and_hash()
    payment = await service.create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        payment_hash=payment_hash,
        memo="test_cancel_upstream_holdinvoice",
    )

    async with _paying(wallet, payment.bolt11, payment_hash) as payer:
        await _wait_for_invoice_state(payment_hash, "ACCEPTED", payer)
        await _assert_pending_without_credit(
            payment_hash, from_wallet.id, before.balance_msat
        )
        assert (await service.cancel_hold_invoice(payment)).ok
        await _wait_for_invoice_state(payment_hash, "CANCELED")
        # lncli exits 1 for a terminal failed payment. Only accept its specific
        # terminal result; command errors and routing failures must fail the test.
        with pytest.raises(CalledProcessError) as failure:
            await asyncio.wait_for(payer, timeout=15)
        assert failure.value.returncode == 1
        assert failure.value.stderr.strip() == "[lncli] FAILED"
        result = json.loads(failure.value.output)
        assert result["status"] == "FAILED", result
        assert (
            result["failure_reason"] == "FAILURE_REASON_INCORRECT_PAYMENT_DETAILS"
        ), result
        assert result["htlcs"], result
        assert all(
            htlc["failure"]["code"] == "INCORRECT_OR_UNKNOWN_PAYMENT_DETAILS"
            for htlc in result["htlcs"]
        ), result
        assert (await wallet.get_invoice_status(payment_hash)).failed
        stored = await get_standalone_payment(payment_hash, incoming=True)
        assert stored and stored.failed
        assert stored.extra["hold_invoice_cancelled"] is True
        after = await get_wallet(from_wallet.id)
        assert after and after.balance_msat == before.balance_msat


async def _assert_pending_without_credit(payment_hash, wallet_id, balance_msat):
    stored = await get_standalone_payment(payment_hash, incoming=True)
    assert stored and stored.pending
    assert (await service.update_pending_payment(stored)).pending
    recipient = await get_wallet(wallet_id)
    assert recipient and recipient.balance_msat == balance_msat


async def _wait_for_invoice_state(payment_hash, expected, payer=None):
    # The upstream LNbits uses lnd-3; lnd-1 is the payer.
    command = [
        "docker",
        "exec",
        "lnbits-lnd-3-1",
        "lncli",
        "--network=regtest",
        "--rpcserver=lnd-3",
        "lookupinvoice",
        payment_hash,
    ]

    async def poll():
        state = None
        for _ in range(100):
            invoice = await _run_json(command)
            state = invoice["state"]
            if state == expected:
                return
            if payer is not None and payer.done():
                raise AssertionError(f"Payer ended before {expected}: {await payer}")
            await asyncio.sleep(0.1)
        raise AssertionError(f"Expected LND {expected}, last state: {state}")

    await asyncio.wait_for(poll(), timeout=20)


@asynccontextmanager
async def _paying(wallet, bolt11, payment_hash):
    payer = asyncio.create_task(
        _run_json(
            [
                *docker_lightning_cli,
                "payinvoice",
                "--force",
                "--json",
                bolt11,
            ]
        )
    )
    try:
        yield payer
    finally:
        try:
            if not payer.done():
                # Release the held HTLC even when an assertion failed.
                await wallet.cancel_hold_invoice(payment_hash)
        finally:
            payer.cancel()
            await asyncio.gather(payer, return_exceptions=True)


async def _run_json(command):
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        if process.returncode:
            raise CalledProcessError(
                process.returncode,
                command,
                output=stdout.decode(),
                stderr=stderr.decode(),
            )
        return json.loads(stdout)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
