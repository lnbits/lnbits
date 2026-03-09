import json
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi import HTTPException

from lnbits.core.crud.payments import create_payment
from lnbits.core.models import Account, CreateInvoice, PaymentState
from lnbits.core.models.payments import CancelInvoice, CreatePayment, SettleInvoice
from lnbits.core.models.users import AccountId
from lnbits.core.models.wallets import KeyType, WalletTypeInfo
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.core.services.users import create_user_account
from lnbits.core.views.payment_api import (
    api_all_payments_paginated,
    api_payments_cancel,
    api_payments_counting_stats,
    api_payments_daily_stats,
    api_payments_fee_reserve,
    api_payments_settle,
    api_payments_wallets_stats,
)
from lnbits.db import Filters
from lnbits.wallets.base import InvoiceResponse

ZERO_AMOUNT_INVOICE = (
    "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
    "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
    "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
    "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
    "6hjxepwp93cq398l3s"
)


async def _create_payment(
    wallet_id: str,
    *,
    amount_msat: int,
    status: PaymentState = PaymentState.SUCCESS,
    payment_hash: str | None = None,
    tag: str | None = None,
) -> str:
    checking_id = f"checking_{uuid4().hex[:8]}"
    await create_payment(
        checking_id=checking_id,
        data=CreatePayment(
            wallet_id=wallet_id,
            payment_hash=payment_hash or uuid4().hex,
            bolt11=f"bolt11_{checking_id}",
            amount_msat=amount_msat,
            memo=f"payment_{checking_id}",
            extra={"tag": tag} if tag else {},
        ),
        status=status,
    )
    return checking_id


@pytest.mark.anyio
async def test_payment_api_stats_and_all_paginated(admin_user):
    first_user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    second_user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    first_wallet = first_user.wallets[0]
    second_wallet = second_user.wallets[0]

    await _create_payment(first_wallet.id, amount_msat=2_000, tag="coffee")
    await _create_payment(first_wallet.id, amount_msat=-1_000, tag="coffee")
    await _create_payment(second_wallet.id, amount_msat=5_000, tag="books")

    count_stats = await api_payments_counting_stats(
        count_by="tag",
        filters=Filters(limit=20),
        account_id=AccountId(id=first_user.id),
    )
    assert any(item.field == "coffee" for item in count_stats)
    assert all(item.field != "books" for item in count_stats)

    wallet_stats = await api_payments_wallets_stats(
        filters=Filters(limit=20), account_id=AccountId(id=first_user.id)
    )
    assert any(item.wallet_id == first_wallet.id for item in wallet_stats)
    assert all(item.wallet_id != second_wallet.id for item in wallet_stats)

    daily_stats = await api_payments_daily_stats(
        account_id=AccountId(id=first_user.id),
        filters=Filters(limit=20),
    )
    assert daily_stats
    assert daily_stats[0].payments_count >= 1

    regular_page = await api_all_payments_paginated(
        filters=Filters(limit=20), account_id=AccountId(id=first_user.id)
    )
    assert regular_page.total >= 2
    assert all(payment.wallet_id == first_wallet.id for payment in regular_page.data)

    admin_page = await api_all_payments_paginated(
        filters=Filters(limit=50), account_id=AccountId(id=admin_user.id)
    )
    wallet_ids = {payment.wallet_id for payment in admin_page.data}
    assert first_wallet.id in wallet_ids
    assert second_wallet.id in wallet_ids


@pytest.mark.anyio
async def test_payment_api_fee_reserve_and_hold_invoice_actions(mocker):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]

    invoice = await create_wallet_invoice(
        wallet.id, CreateInvoice(out=False, amount=42, memo="reserve")
    )
    reserve = await api_payments_fee_reserve(invoice.bolt11)
    assert json.loads(reserve.body)["fee_reserve"] >= 0

    with pytest.raises(HTTPException, match="Invoice has no amount."):
        await api_payments_fee_reserve(ZERO_AMOUNT_INVOICE)

    preimage = "11" * 32
    payment_hash = sha256(bytes.fromhex(preimage)).hexdigest()
    await _create_payment(
        wallet.id,
        amount_msat=1_000,
        payment_hash=payment_hash,
        status=PaymentState.PENDING,
    )
    settle_mock = mocker.patch(
        "lnbits.core.views.payment_api.settle_hold_invoice",
        mocker.AsyncMock(
            return_value=InvoiceResponse(
                ok=True,
                checking_id="settled",
                preimage=preimage,
            )
        ),
    )

    settled = await api_payments_settle(
        SettleInvoice(preimage=preimage),
        WalletTypeInfo(key_type=KeyType.admin, wallet=wallet),
    )
    assert settled.success is True
    settle_mock.assert_awaited_once()

    cancel_hash = (uuid4().hex * 2)[:64]
    await _create_payment(
        wallet.id,
        amount_msat=2_000,
        payment_hash=cancel_hash,
        status=PaymentState.PENDING,
    )
    cancel_mock = mocker.patch(
        "lnbits.core.views.payment_api.cancel_hold_invoice",
        mocker.AsyncMock(
            return_value=InvoiceResponse(
                ok=False,
                checking_id="cancelled",
                error_message="cancelled",
            )
        ),
    )

    cancelled = await api_payments_cancel(
        CancelInvoice(payment_hash=cancel_hash),
        WalletTypeInfo(key_type=KeyType.admin, wallet=wallet),
    )
    assert cancelled.failed is True
    cancel_mock.assert_awaited_once()
