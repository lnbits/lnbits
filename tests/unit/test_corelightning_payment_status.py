from types import SimpleNamespace
from typing import Any, cast

import pytest

from lnbits.core.crud import get_wallet
from lnbits.core.crud.payments import create_payment, get_standalone_payment
from lnbits.core.models import CreatePayment
from lnbits.core.services.payments import update_pending_payment
from lnbits.wallets.corelightning import CoreLightningWallet


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("pays", "paid"),
    [
        ([], None),
        ([{"payment_hash": "hash", "status": "pending"}], None),
        ([{"payment_hash": "hash", "status": "failed"}], False),
        (
            [
                {
                    "payment_hash": "hash",
                    "status": "complete",
                    "amount_sent_msat": 1010,
                    "amount_msat": 1000,
                    "preimage": "preimage",
                }
            ],
            True,
        ),
    ],
)
async def test_corelightning_payment_status_requires_an_explicit_result(
    mocker, pays, paid
):
    wallet = object.__new__(CoreLightningWallet)
    cast(Any, wallet).ln = SimpleNamespace(
        listpays=mocker.Mock(return_value={"pays": pays})
    )

    status = await wallet.get_payment_status("hash")

    assert status.paid is paid


@pytest.mark.anyio
async def test_corelightning_missing_attempt_keeps_outgoing_balance_reserved(
    app, from_wallet, mocker
):
    payment = await create_payment(
        "cln-unrecorded-attempt",
        CreatePayment(
            wallet_id=from_wallet.id,
            payment_hash="cln-unrecorded-attempt",
            bolt11="test-invoice",
            memo="Pending CLN payment",
            amount_msat=-1000,
            fee=-10,
        ),
    )
    before = await get_wallet(from_wallet.id)
    assert before
    backend = object.__new__(CoreLightningWallet)
    cast(Any, backend).ln = SimpleNamespace(
        listpays=mocker.Mock(return_value={"pays": []})
    )
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source", return_value=backend
    )

    await update_pending_payment(payment)

    stored = await get_standalone_payment(payment.checking_id)
    after = await get_wallet(from_wallet.id)
    assert stored and stored.pending
    assert after and after.balance_msat == before.balance_msat
