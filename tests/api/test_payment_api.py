import json
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from lnbits.core.crud.payments import create_payment, get_payment, get_payments
from lnbits.core.models import Account, CreateInvoice, PaymentFilters, PaymentState
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
from lnbits.db import Filter, Filters
from lnbits.wallets.base import InvoiceResponse

ZERO_AMOUNT_INVOICE = (
    "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
    "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
    "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
    "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
    "6hjxepwp93cq398l3s"
)


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
async def test_payment_external_id_is_stored_and_validated():
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]

    first_payment = await create_wallet_invoice(
        wallet.id,
        CreateInvoice(
            out=False,
            amount=21,
            memo="external reference",
            external_id="provider_payment_123",
        ),
    )
    second_payment = await create_wallet_invoice(
        wallet.id,
        CreateInvoice(
            out=False,
            amount=22,
            memo="external reference newest",
            external_id="provider_payment_123",
        ),
    )

    assert first_payment.external_id == "provider_payment_123"
    assert second_payment.external_id == "provider_payment_123"
    stored_payments = await get_payments(
        wallet_id=wallet.id,
        filters=Filters(
            filters=[
                Filter.parse_query(
                    "external_id", ["provider_payment_123"], PaymentFilters
                )
            ],
            model=PaymentFilters,
            sortby="created_at",
            direction="desc",
        ),
    )
    assert [payment.checking_id for payment in stored_payments] == [
        second_payment.checking_id,
        first_payment.checking_id,
    ]

    with pytest.raises(ValidationError, match="Invalid external id"):
        CreateInvoice(out=False, amount=21, external_id="provider payment 123")


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


@pytest.mark.anyio
async def test_payment_extra_update_appends_new_keys(
    client,
    to_wallet,
    adminkey_headers_to,
):
    payment_hash = uuid4().hex
    checking_id = await _create_payment(
        to_wallet.id,
        amount_msat=1_000,
        payment_hash=payment_hash,
        tag="splitpayments",
    )

    response = await client.patch(
        "/api/v1/payments/extra",
        headers=adminkey_headers_to,
        json={
            "payment_hash": payment_hash,
            "extra": {"child": "daughter", "compliance_note": "reviewed"},
        },
    )

    assert response.status_code == 200
    extra = response.json()["extra"]
    assert extra["tag"] == "splitpayments"
    assert extra["child"] == "daughter"
    assert extra["compliance_note"] == "reviewed"

    payment = await get_payment(checking_id)
    assert payment.extra == extra


@pytest.mark.anyio
async def test_payment_extra_update_creates_extra_when_missing(
    client,
    to_wallet,
    adminkey_headers_to,
):
    payment_hash = uuid4().hex
    checking_id = await _create_payment(
        to_wallet.id,
        amount_msat=1_000,
        payment_hash=payment_hash,
    )

    response = await client.patch(
        "/api/v1/payments/extra",
        headers=adminkey_headers_to,
        json={"payment_hash": payment_hash, "extra": {"note": "reviewed"}},
    )

    assert response.status_code == 200
    assert response.json()["extra"] == {"note": "reviewed"}

    payment = await get_payment(checking_id)
    assert payment.extra == {"note": "reviewed"}


@pytest.mark.anyio
async def test_payment_extra_update_rejects_existing_keys(
    client,
    to_wallet,
    adminkey_headers_to,
):
    payment_hash = uuid4().hex
    checking_id = await _create_payment(
        to_wallet.id,
        amount_msat=1_000,
        payment_hash=payment_hash,
        tag="original",
    )

    response = await client.patch(
        "/api/v1/payments/extra",
        headers=adminkey_headers_to,
        json={"payment_hash": payment_hash, "extra": {"tag": "overwritten"}},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Extra keys already exist: tag."

    payment = await get_payment(checking_id)
    assert payment.extra == {"tag": "original"}


@pytest.mark.anyio
async def test_payment_extra_update_requires_admin_key(
    client,
    to_wallet,
    inkey_headers_to,
):
    payment_hash = uuid4().hex
    await _create_payment(
        to_wallet.id,
        amount_msat=1_000,
        payment_hash=payment_hash,
    )

    response = await client.patch(
        "/api/v1/payments/extra",
        headers=inkey_headers_to,
        json={"payment_hash": payment_hash, "extra": {"note": "invoice key"}},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid adminkey."


@pytest.mark.anyio
async def test_payment_extra_update_is_wallet_scoped(
    client,
    from_wallet,
    adminkey_headers_to,
):
    payment_hash = uuid4().hex
    await _create_payment(
        from_wallet.id,
        amount_msat=1_000,
        payment_hash=payment_hash,
    )

    response = await client.patch(
        "/api/v1/payments/extra",
        headers=adminkey_headers_to,
        json={"payment_hash": payment_hash, "extra": {"note": "wrong wallet"}},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment does not exist."


@pytest.mark.anyio
async def test_payment_extra_update_requires_successful_payment(
    client,
    to_wallet,
    adminkey_headers_to,
):
    payment_hash = uuid4().hex
    await _create_payment(
        to_wallet.id,
        amount_msat=1_000,
        payment_hash=payment_hash,
        status=PaymentState.PENDING,
    )

    response = await client.patch(
        "/api/v1/payments/extra",
        headers=adminkey_headers_to,
        json={"payment_hash": payment_hash, "extra": {"note": "too early"}},
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"] == "Payment extra can only be updated after success."
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
