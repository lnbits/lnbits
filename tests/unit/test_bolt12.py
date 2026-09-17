"""BOLT12 offer detection and send path (lnbits#2581)."""

from unittest.mock import AsyncMock

import pytest
from bech32 import CHARSET, convertbits

from lnbits.core.crud import create_wallet, get_standalone_payment, get_wallet
from lnbits.core.models import PaymentState, ValidatedPaymentRequest
from lnbits.core.services import create_user_account, pay_invoice, pay_offer
from lnbits.core.services.payments import (
    _validate_offer_payment_request,
    _validate_payment_request,
    update_wallet_balance,
)
from lnbits.exceptions import PaymentError
from lnbits.settings import Settings
from lnbits.utils.bolt12 import (
    get_bolt12_offer_description,
    is_bolt12_offer,
    looks_like_bolt12_offer,
    parse_bolt12_offer,
)
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.base import Feature, PaymentResponse
from lnbits.wallets.fake import FakeWallet
from tests.helpers import BOLT12_OFFER, BOLT12_OFFER_WITH_DESCRIPTION

VALID_OFFER = BOLT12_OFFER

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
async def test_validate_offer_payment_request(app):
    pr = _validate_offer_payment_request(
        "lightning:" + VALID_OFFER.upper(), amount_sat=21
    )
    second = _validate_offer_payment_request(VALID_OFFER, amount_sat=21)

    assert isinstance(pr, ValidatedPaymentRequest)
    assert pr.is_offer is True
    assert pr.payment_request == VALID_OFFER
    assert pr.amount_msat == 21_000
    assert pr.expiry_date is None
    assert pr.description == ""
    assert len(pr.payment_hash) == 64
    assert pr.payment_hash != second.payment_hash


def test_validate_payment_request_rejects_offer():
    with pytest.raises(PaymentError, match="Bolt11 decoding failed"):
        _validate_payment_request(VALID_OFFER, max_sat=21)


@pytest.mark.anyio
async def test_pay_invoice_rejects_offer(app, to_wallet):
    with pytest.raises(PaymentError, match="Bolt11 decoding failed"):
        await pay_invoice(
            wallet_id=to_wallet.id, payment_request=VALID_OFFER, max_sat=21
        )


@pytest.mark.anyio
async def test_pay_offer_rejects_invoice(app, to_wallet):
    with pytest.raises(PaymentError, match="Invalid BOLT12 offer"):
        await pay_offer(wallet_id=to_wallet.id, offer=BOLT11, amount_sat=21)


@pytest.mark.anyio
async def test_pay_offer_rejects_malformed_offer(app, to_wallet):
    with pytest.raises(PaymentError, match="Invalid BOLT12 offer"):
        await pay_offer(
            wallet_id=to_wallet.id,
            offer="lno1!!!not-bech32",
            amount_sat=21,
        )


@pytest.mark.anyio
async def test_pay_offer_requires_amount(app, to_wallet):
    with pytest.raises(PaymentError, match="Amount is required to pay a BOLT12 offer"):
        await pay_offer(
            wallet_id=to_wallet.id,
            offer=VALID_OFFER,
        )


@pytest.mark.anyio
async def test_pay_offer_rejects_zero_amount(app, to_wallet):
    with pytest.raises(PaymentError, match="Amount is required to pay a BOLT12 offer"):
        await pay_offer(
            wallet_id=to_wallet.id,
            offer=VALID_OFFER,
            amount_sat=0,
        )


@pytest.mark.anyio
async def test_pay_offer_enforces_amount_ceiling(app, to_wallet, settings: Settings):
    settings.lnbits_max_outgoing_payment_amount_sats = 100
    with pytest.raises(PaymentError, match="too high"):
        await pay_offer(
            wallet_id=to_wallet.id,
            offer=VALID_OFFER,
            amount_sat=200,
        )


@pytest.mark.anyio
async def test_pay_offer_rejects_without_bolt12_feature(app, to_wallet, monkeypatch):
    monkeypatch.setattr(FakeWallet, "features", None)
    with pytest.raises(
        PaymentError, match="Funding source does not support BOLT12 offers"
    ) as excinfo:
        await pay_offer(
            wallet_id=to_wallet.id,
            offer=VALID_OFFER,
            amount_sat=21,
        )
    assert "Phoenixd" in excinfo.value.message
    assert "LNbits" in excinfo.value.message


@pytest.mark.anyio
async def test_pay_offer_debits_wallet_and_is_reusable(app):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)

    extra = {"reference": "order-1"}
    first = await pay_offer(
        wallet_id=wallet.id,
        offer=VALID_OFFER,
        amount_sat=21,
        extra=extra,
        description="first offer pay",
        labels=["offers"],
        external_id="offer-order-1",
    )
    assert first.status == PaymentState.SUCCESS.value
    assert first.amount == -21_000
    assert first.bolt11 == VALID_OFFER
    assert first.extra.get("bolt12") is True
    assert first.checking_id != first.bolt11
    assert first.payment_hash != VALID_OFFER
    assert len(first.payment_hash) == 64
    stored = await get_standalone_payment(first.checking_id)
    assert stored
    assert stored.success
    assert stored.memo == "first offer pay"
    assert stored.extra["reference"] == "order-1"
    assert stored.labels == ["offers"]
    assert stored.external_id == "offer-order-1"
    assert extra == {"reference": "order-1"}

    second = await pay_offer(
        wallet_id=wallet.id,
        offer="lightning:" + VALID_OFFER.upper(),
        amount_sat=7,
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


def test_offer_description_from_spec_vectors():
    assert get_bolt12_offer_description(BOLT12_OFFER) is None
    assert get_bolt12_offer_description(BOLT12_OFFER_WITH_DESCRIPTION) == "Test vectors"
    assert (
        get_bolt12_offer_description(
            "lightning:" + BOLT12_OFFER_WITH_DESCRIPTION.upper()
        )
        == "Test vectors"
    )


def test_offer_description_preserves_utf8_and_extended_length():
    description = "  Café ☕\n" * 100
    value = description.encode("utf-8")
    offer = _encode_offer(b"\x0a\xfd" + len(value).to_bytes(2, "big") + value)
    assert get_bolt12_offer_description(offer) == description


@pytest.mark.parametrize(
    "field_type",
    [b"\xfd\x01\x01", b"\xfe\x00\x01\x00\x00", b"\xff\x00\x00\x00\x01\x00\x00\x00\x00"],
)
def test_offer_description_skips_unknown_fields(field_type):
    offer = _encode_offer(b"\x0a\x01a" + field_type + b"\x03abc")
    assert get_bolt12_offer_description(offer) == "a"


@pytest.mark.parametrize(
    "payload",
    [
        b"\x0a\x05abc",  # Truncated description.
        b"\x0a\x02\xff\xff",  # Invalid UTF-8.
        b"\x0a\x01a\x0a\x01b",  # Duplicate description.
        b"\x0a\x01a\x08\x00",  # Out-of-order fields.
        b"\x0a\xfd\x00",  # Truncated BigSize length.
        b"\x0a\xfd\x00\x01a",  # Non-canonical BigSize length.
        b"\x0a\x03abc\x16",  # Incomplete record after description.
        b"\x0a\xff\xff\xff\xff\xff\xff\xff\xff\xff",  # Oversized length.
    ],
)
def test_offer_description_rejects_malformed_tlv(payload):
    with pytest.raises(PaymentError, match="Invalid BOLT12 offer"):
        get_bolt12_offer_description(_encode_offer(payload))


def test_offer_description_rejects_invalid_padding():
    with pytest.raises(PaymentError, match="Invalid BOLT12 offer encoding"):
        get_bolt12_offer_description(BOLT12_OFFER + "p")


@pytest.mark.anyio
@pytest.mark.parametrize("payer_note", [None, "", "  ", "  Thanks ☕\n" * 100])
async def test_pay_offer_memo_and_description(app, monkeypatch, payer_note):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)
    preimage, payment_hash = random_secret_and_hash()
    backend = AsyncMock(return_value=PaymentResponse(True, payment_hash, 0, preimage))
    monkeypatch.setattr(FakeWallet, "pay_offer", backend)
    extra = {
        "internal_memo": "Private memo",
        "payer_note": "Old note",
        "bolt12_offer_description": "Old description",
    }
    original_extra = dict(extra)

    payment = await pay_offer(
        wallet_id=wallet.id,
        offer=BOLT12_OFFER_WITH_DESCRIPTION,
        amount_sat=21,
        payer_note=payer_note,
        extra=extra,
    )

    backend.assert_awaited_once_with(
        BOLT12_OFFER_WITH_DESCRIPTION,
        fee_limit_msat=20000,
        amount_msat=21000,
        payer_note=payer_note or None,
    )
    stored = await get_standalone_payment(payment.checking_id)
    assert stored and stored.success
    assert stored.memo == (payer_note or "Test vectors")
    assert stored.extra["internal_memo"] == "Private memo"
    if payer_note:
        assert stored.extra["payer_note"] == payer_note
        assert stored.extra["bolt12_offer_description"] == "Test vectors"
    else:
        assert "payer_note" not in stored.extra
        assert "bolt12_offer_description" not in stored.extra
    assert extra == original_extra


@pytest.mark.anyio
async def test_pay_offer_unsupported_note_preserves_balance(app):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id)
    await update_wallet_balance(wallet, 1000)

    with pytest.raises(PaymentError, match="Payer notes are not supported"):
        await pay_offer(
            wallet_id=wallet.id,
            offer=BOLT12_OFFER_WITH_DESCRIPTION,
            amount_sat=21,
            payer_note="For the recipient",
        )
    after = await get_wallet(wallet.id)
    assert after and after.balance == 1000


def _encode_offer(payload: bytes) -> str:
    encoded = convertbits(payload, 8, 5)
    assert encoded is not None
    return "lno1" + "".join(CHARSET[value] for value in encoded)
