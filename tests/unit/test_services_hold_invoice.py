import asyncio
import hashlib
import json
import time
from unittest.mock import AsyncMock

import httpx
import pytest
from bolt11 import Bolt11, MilliSatoshi, TagChar, Tags, decode, encode

from lnbits.core.crud import (
    create_wallet,
    get_payments,
    get_standalone_payment,
    get_wallet,
)
from lnbits.core.models import CreateInvoice
from lnbits.core.services import create_user_account, notifications
from lnbits.core.services import payments as service
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.lnbits import LNbitsWallet


@pytest.fixture
async def recipient(app):
    user = await create_user_account()
    return await create_wallet(user_id=user.id)


@pytest.fixture
async def upstream(monkeypatch):
    state = {"status": "pending"}

    def handler(request):
        if request.url.path.endswith("/settle"):
            state["status"] = "success"
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/cancel"):
            state["status"] = "failed"
            return httpx.Response(200, json={"ok": True})
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"paid": state["status"] == "success", "status": state["status"]},
            )
        data = json.loads(request.content)
        return httpx.Response(
            201,
            json={"checking_id": data["payment_hash"], "bolt11": _invoice(data)},
        )

    wallet = object.__new__(LNbitsWallet)
    wallet.endpoint = "http://upstream.test"
    async with httpx.AsyncClient(
        base_url=wallet.endpoint, transport=httpx.MockTransport(handler)
    ) as wallet.client:
        monkeypatch.setattr(service, "get_funding_source", lambda: wallet)
        yield wallet


@pytest.mark.anyio
@pytest.mark.parametrize("expiry", [None, 0, 600])
@pytest.mark.parametrize(
    ("description_hash", "unhashed_description"),
    [(None, None), (None, b"metadata"), (b"e" * 32, None), (b"e" * 32, b"metadata")],
)
async def test_hold_service_forwards_optional_fields(
    recipient,
    upstream,
    settings,
    monkeypatch,
    expiry,
    description_hash,
    unhashed_description,
):
    settings.lightning_invoice_expiry = 1800
    create_hold = AsyncMock(wraps=upstream.create_hold_invoice)
    monkeypatch.setattr(upstream, "create_hold_invoice", create_hold)
    _, payment_hash = random_secret_and_hash()
    payment = await service.create_wallet_invoice(
        recipient.id,
        CreateInvoice(
            amount=1000,
            memo="hold",
            payment_hash=payment_hash,
            expiry=expiry,
            description_hash=description_hash.hex() if description_hash else None,
            unhashed_description=(
                unhashed_description.hex() if unhashed_description else None
            ),
        ),
    )
    create_hold.assert_awaited_once_with(
        amount=1000,
        memo=None if description_hash else ("" if unhashed_description else "hold"),
        payment_hash=payment_hash,
        description_hash=description_hash,
        unhashed_description=unhashed_description,
        expiry=expiry or 1800,
    )
    invoice = decode(payment.bolt11)
    assert invoice.payment_hash == payment_hash
    assert invoice.amount_msat == 1_000_000
    assert invoice.expiry == (expiry or 1800)
    assert invoice.description_hash == (
        description_hash.hex()
        if description_hash
        else (
            hashlib.sha256(unhashed_description).hexdigest()
            if unhashed_description
            else None
        )
    )


@pytest.mark.anyio
@pytest.mark.parametrize("settle", [True, False])
async def test_hold_service_accounting(recipient, upstream, settle, monkeypatch):
    preimage, payment_hash = random_secret_and_hash()
    payment = await service.create_invoice(
        wallet_id=recipient.id, amount=1000, memo="hold", payment_hash=payment_hash
    )
    assert payment.extra["hold_invoice"] is True
    payment = await get_standalone_payment(payment_hash, incoming=True)
    assert payment

    notified = asyncio.Event()
    messages = []

    async def notify(wallet, received):
        if wallet.id == recipient.id:
            messages.append((wallet.balance_msat, received))
            notified.set()

    async def paid_invoices():
        yield payment_hash

    monkeypatch.setattr(upstream, "paid_invoices_stream", paid_invoices)
    monkeypatch.setattr(notifications, "send_ws_payment_notification", notify)

    # Upstream reports accepted HTLCs as unpaid/pending until settlement.
    payment = await service.update_pending_payment(payment)
    assert payment.pending
    balance = await get_wallet(recipient.id)
    assert balance and balance.balance_msat == 0
    await service.fundingsource_invoice_producer()
    assert not messages

    if settle:
        assert (await service.settle_hold_invoice(payment, preimage)).ok
        # Exercise the same reconciliation used by the funding-source stream,
        # including a repeated notification and a subsequent polling update.
        for _ in range(2):
            notified.clear()
            await service.fundingsource_invoice_producer()
            await asyncio.wait_for(notified.wait(), timeout=5)
            assert messages[-1][0] == 1_000_000
            assert messages[-1][1].payment_hash == payment_hash
            assert messages[-1][1].success
            updated = await get_standalone_payment(payment_hash, incoming=True)
            assert updated and updated.success
            assert updated.preimage == preimage
            assert updated.extra["hold_invoice_settled"] is True
            await service.update_pending_payment(updated)
    else:
        assert (await service.cancel_hold_invoice(payment)).ok
        updated = await service.update_pending_payment(payment)
        assert updated.failed
        assert updated.extra["hold_invoice_cancelled"] is True
        assert (
            await service.update_invoice_from_paid_invoices_stream(payment_hash) is None
        )
        assert not messages

    stored = await get_standalone_payment(payment_hash, incoming=True)
    assert stored
    assert stored.success if settle else stored.failed
    balance = await get_wallet(recipient.id)
    assert balance and balance.balance_msat == (1_000_000 if settle else 0)
    assert len(await get_payments(wallet_id=recipient.id, incoming=True)) == 1


def _invoice(data):
    tags = Tags()
    tags.add(TagChar.payment_hash, data["payment_hash"])
    tags.add(TagChar.payment_secret, "cd" * 32)
    tags.add(TagChar.expire_time, data["expiry"])
    if data.get("description_hash"):
        tags.add(TagChar.description_hash, data["description_hash"])
    else:
        tags.add(TagChar.description, data["memo"])
    return encode(
        Bolt11(
            currency="bcrt",
            amount_msat=MilliSatoshi(data["amount"] * 1000),
            date=int(time.time()),
            tags=tags,
        ),
        private_key="ab" * 32,
    )
