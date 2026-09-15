"""BOLT12 offer detection and send path (lnbits#2581)."""

import pytest

from lnbits.core.crud import create_wallet, get_standalone_payment, get_wallet
from lnbits.core.models import PaymentState
from lnbits.core.services import create_user_account, pay_invoice
from lnbits.core.services.bolt12 import (
    is_bolt12_offer,
    looks_like_bolt12_offer,
    parse_bolt12_offer,
)
from lnbits.core.services.payments import update_wallet_balance
from lnbits.exceptions import PaymentError
from lnbits.settings import Settings
from lnbits.wallets.base import Feature
from lnbits.wallets.fake import FakeWallet

# Charset-valid offer (not a live invoice; FakeWallet accepts the shape).
VALID_OFFER = "lno1qgsqvgnwgcg35z6ee2h3yczraddm72xrfua9uve2rlrm9deu7xyfzrcgq9qh"

BOLT11 = (
    "lnbc1pvjluezpp5qqqsyqcyq5rqwzqfqqqsyqcyq5rqwzqfqqqsyqcyq5rqwzqfqypq"
    "dpl2pkx2ctnv5sxxmmwwd5kgetjypeh2ursdae8g6twvus8g6rfwvs8qun0dfjkxaq"
)


def test_parse_offer_accepts_lno1_and_normalizes():
    assert parse_bolt12_offer(VALID_OFFER) == VALID_OFFER
    assert parse_bolt12_offer(" " + VALID_OFFER.upper() + " ") == VALID_OFFER
    assert parse_bolt12_offer("lightning:" + VALID_OFFER) == VALID_OFFER
    assert parse_bolt12_offer("LIGHTNING://" + VALID_OFFER.upper()) == VALID_OFFER
    assert parse_bolt12_offer("lightning:" + VALID_OFFER + "?amount=1") == VALID_OFFER
    pretty = VALID_OFFER[:20] + "+\n  " + VALID_OFFER[20:]
    assert parse_bolt12_offer(pretty) == VALID_OFFER


def test_parse_offer_rejects_invalid_input():
    for value in (
        "",
        "   ",
        "not-an-offer",
        "lnurl1xyz",
        "lni1qgsqvgnwgcg35z6ee2h3yczraddm72xrfua9uve2rlrm9deu7xyfzrc",
        "lno",
        "lno1",
        "lno1!!!",
        "lno1abc1def",
        "Lno1qgsqvgnwgcg35z6ee2h3yczraddm72xrfua9uve2rlrm9deu7xyfzrcgq9qh",
        BOLT11,
    ):
        with pytest.raises(PaymentError, match="Invalid BOLT12 offer"):
            parse_bolt12_offer(value)
        assert is_bolt12_offer(value) is False


def test_looks_like_offer_is_fail_closed_prefix():
    assert looks_like_bolt12_offer(VALID_OFFER) is True
    assert looks_like_bolt12_offer("lno1!!!") is True
    assert looks_like_bolt12_offer("lno") is True
    assert looks_like_bolt12_offer(BOLT11) is False
    assert looks_like_bolt12_offer("lnurl1abc") is False
    assert looks_like_bolt12_offer("lni1abc") is False


@pytest.mark.anyio
async def test_pay_invoice_rejects_malformed_offer(app, to_wallet):
    with pytest.raises(PaymentError, match="Invalid BOLT12 offer"):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request="lno1!!!not-bech32",
            max_sat=21,
        )


@pytest.mark.anyio
async def test_pay_invoice_requires_offer_amount(app, to_wallet):
    with pytest.raises(PaymentError, match="Amount is required to pay a BOLT12 offer"):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=VALID_OFFER,
        )


@pytest.mark.anyio
async def test_pay_invoice_rejects_zero_offer_amount(app, to_wallet):
    with pytest.raises(PaymentError, match="Amount is required to pay a BOLT12 offer"):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=VALID_OFFER,
            max_sat=0,
        )


@pytest.mark.anyio
async def test_pay_invoice_enforces_offer_amount_ceiling(
    app, to_wallet, settings: Settings
):
    settings.lnbits_max_outgoing_payment_amount_sats = 100
    with pytest.raises(PaymentError, match="too high"):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=VALID_OFFER,
            max_sat=200,
        )


@pytest.mark.anyio
async def test_pay_invoice_rejects_offer_without_bolt12_feature(
    app, to_wallet, monkeypatch
):
    monkeypatch.setattr(FakeWallet, "features", None)
    with pytest.raises(
        PaymentError, match="Funding source does not support BOLT12 offers"
    ):
        await pay_invoice(
            wallet_id=to_wallet.id,
            payment_request=VALID_OFFER,
            max_sat=21,
        )


@pytest.mark.anyio
async def test_pay_offer_debits_wallet_and_is_reusable(app):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)

    extra = {"custom": "preserved"}
    first = await pay_invoice(
        wallet_id=wallet.id,
        payment_request=VALID_OFFER,
        max_sat=21,
        description="first offer pay",
        extra=extra,
        labels=["offer"],
        external_id="first-offer-pay",
    )
    assert first.status == PaymentState.SUCCESS.value
    assert first.amount == -21_000
    assert first.bolt11 == VALID_OFFER
    assert first.extra.get("bolt12") is True
    assert extra == {"custom": "preserved"}
    assert first.checking_id != first.bolt11
    stored = await get_standalone_payment(first.checking_id)
    assert stored
    assert stored.success
    assert stored.memo == "first offer pay"
    assert stored.extra["custom"] == "preserved"
    assert stored.labels == ["offer"]
    assert stored.external_id == "first-offer-pay"

    second = await pay_invoice(
        wallet_id=wallet.id,
        payment_request="lightning:" + VALID_OFFER.upper(),
        max_sat=7,
    )
    assert second.status == PaymentState.SUCCESS.value
    assert second.amount == -7_000
    assert second.checking_id != first.checking_id
    assert second.payment_hash != first.payment_hash

    after = await get_wallet(wallet.id)
    assert after
    assert after.balance == 1000 - 21 - 7


def test_fake_wallet_advertises_bolt12():
    assert Feature.bolt12 in (FakeWallet.features or [])
