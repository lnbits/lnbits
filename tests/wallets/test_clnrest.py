from hashlib import sha256

import pytest

from lnbits.settings import settings
from lnbits.utils.crypto import random_secret_and_hash
from lnbits.wallets.clnrest import (
    CLNRestWallet,
    _highest_paid_pay_index,
    _msat_to_int,
    _select_best_pay,
)


def _wallet() -> CLNRestWallet:
    wallet = CLNRestWallet.__new__(CLNRestWallet)
    wallet.readonly_headers = {"rune": "readonly"}
    wallet.invoice_headers = {"rune": "invoice"}
    wallet.last_pay_index = 0
    wallet._listener_bootstrapped = False
    return wallet


def test_clnrest_msat_normalization():
    assert _msat_to_int(1234) == 1234
    assert _msat_to_int(1234.9) == 1234
    assert _msat_to_int("1234") == 1234
    assert _msat_to_int("1234msat") == 1234
    assert _msat_to_int({"msat": 1234}) == 1234
    assert _msat_to_int({"amount_msat": "1234msat"}) == 1234


def test_clnrest_select_best_pay_prefers_complete():
    pays = [
        {"status": "failed"},
        {"status": "pending"},
        {"status": "complete", "preimage": "abc"},
    ]

    assert _select_best_pay(pays)["status"] == "complete"


def test_clnrest_highest_paid_pay_index_ignores_unpaid_and_invalid():
    invoices = [
        {"status": "unpaid", "pay_index": 100},
        {"status": "paid", "pay_index": 7},
        {"status": "paid", "pay_index": "12"},
        {"status": "paid", "pay_index": "invalid"},
        {"status": "expired", "pay_index": 99},
    ]

    assert _highest_paid_pay_index(invoices) == 12


@pytest.mark.anyio
async def test_clnrest_bootstrap_uses_highest_existing_pay_index(mocker):
    wallet = _wallet()
    fetch_bootstrap = mocker.AsyncMock(
        return_value={
            "invoices": [
                {"status": "paid", "pay_index": 11},
                {"status": "unpaid"},
                {"status": "paid", "pay_index": 42},
            ]
        }
    )
    wallet._fetch_bootstrap_invoices = fetch_bootstrap

    await wallet._bootstrap_listener_index()

    assert wallet.last_pay_index == 42
    assert wallet._listener_bootstrapped is True
    fetch_bootstrap.assert_awaited_once_with()


@pytest.mark.anyio
async def test_clnrest_bootstrap_preserves_explicit_pay_index(mocker):
    wallet = _wallet()
    wallet.last_pay_index = 27
    fetch_bootstrap = mocker.AsyncMock()
    wallet._fetch_bootstrap_invoices = fetch_bootstrap

    await wallet._bootstrap_listener_index()

    assert wallet.last_pay_index == 27
    assert wallet._listener_bootstrapped is True
    fetch_bootstrap.assert_not_awaited()


@pytest.mark.anyio
async def test_clnrest_bootstrap_failure_does_not_enable_zero_cursor(mocker):
    wallet = _wallet()
    wallet._fetch_bootstrap_invoices = mocker.AsyncMock(
        side_effect=RuntimeError("CLN unavailable")
    )

    with pytest.raises(RuntimeError, match="CLN unavailable"):
        await wallet._bootstrap_listener_index()

    assert wallet.last_pay_index == 0
    assert wallet._listener_bootstrapped is False


def test_clnrest_paid_event_rejects_stale_pay_index():
    wallet = _wallet()
    wallet.last_pay_index = 42

    event = {
        "status": "paid",
        "payment_hash": "11" * 32,
        "pay_index": 42,
    }

    assert wallet._parse_paid_invoice_event(event) is None


def test_clnrest_paid_event_accepts_new_pay_index():
    wallet = _wallet()
    wallet.last_pay_index = 42
    payment_hash = "11" * 32

    event = {
        "status": "paid",
        "payment_hash": payment_hash,
        "pay_index": 43,
    }

    assert wallet._parse_paid_invoice_event(event) == (payment_hash, 43)


@pytest.mark.anyio
async def test_clnrest_listener_bootstrap_prevents_historical_replay(mocker):
    wallet = _wallet()
    payment_hash = "22" * 32
    wallet._fetch_bootstrap_invoices = mocker.AsyncMock(
        return_value={
            "invoices": [
                {"status": "paid", "pay_index": 1},
                {"status": "paid", "pay_index": 42},
            ]
        }
    )

    async def waitanyinvoice(*args, **kwargs):
        settings.lnbits_running = False
        return {
            "status": "paid",
            "payment_hash": payment_hash,
            "pay_index": 43,
        }

    rpc_mock = mocker.AsyncMock(side_effect=waitanyinvoice)
    wallet._rpc = rpc_mock
    mocker.patch.object(settings, "lnbits_running", True)

    stream = wallet.paid_invoices_stream()
    received_hash = await anext(stream)
    await stream.aclose()

    assert received_hash == payment_hash
    assert wallet.last_pay_index == 43
    rpc_mock.assert_awaited_once_with(
        "waitanyinvoice",
        payload={"lastpay_index": 42},
        headers=wallet.readonly_headers,
        timeout=None,
    )


@pytest.mark.anyio
async def test_clnrest_create_invoice_sets_deschashonly(mocker):
    wallet = _wallet()
    description = b'[["text/plain","zap metadata"]]'
    description_hash = sha256(description).digest()
    preimage, payment_hash = random_secret_and_hash()

    mocker.patch(
        "lnbits.wallets.clnrest.random_secret_and_hash",
        return_value=(preimage, payment_hash),
    )
    rpc_mock = mocker.AsyncMock(
        return_value={
            "payment_hash": payment_hash,
            "bolt11": "lnbc-test-invoice",
        }
    )
    wallet._rpc = rpc_mock

    response = await wallet.create_invoice(
        amount=10,
        memo="",
        description_hash=description_hash,
        unhashed_description=description,
        expiry=600,
    )

    assert response.ok is True
    assert response.checking_id == payment_hash
    assert response.preimage == preimage

    payload = rpc_mock.await_args.kwargs["payload"]
    assert payload["description"] == description.decode()
    assert payload["deschashonly"] is True
    assert payload["amount_msat"] == 10_000
    assert payload["expiry"] == 600


@pytest.mark.anyio
async def test_clnrest_create_invoice_rejects_description_hash_mismatch(mocker):
    wallet = _wallet()
    rpc_mock = mocker.AsyncMock()
    wallet._rpc = rpc_mock

    response = await wallet.create_invoice(
        amount=10,
        description_hash=b"\x00" * 32,
        unhashed_description=b"different description",
    )

    assert response.ok is False
    assert response.error_message == (
        "description_hash does not match unhashed_description"
    )
    rpc_mock.assert_not_awaited()


@pytest.mark.anyio
async def test_clnrest_create_invoice_rejects_preimage_hash_mismatch(mocker):
    wallet = _wallet()
    preimage, payment_hash = random_secret_and_hash()

    mocker.patch(
        "lnbits.wallets.clnrest.random_secret_and_hash",
        return_value=(preimage, payment_hash),
    )
    wallet._rpc = mocker.AsyncMock(
        return_value={
            "payment_hash": "00" * 32,
            "bolt11": "lnbc-test-invoice",
        }
    )

    response = await wallet.create_invoice(amount=10, memo="test")

    assert response.ok is False
    assert response.error_message == (
        "Server error: invoice preimage does not match payment_hash"
    )


@pytest.mark.anyio
async def test_clnrest_listpays_complete_verifies_preimage_and_fee(mocker):
    wallet = _wallet()
    preimage, payment_hash = random_secret_and_hash()
    wallet._rpc = mocker.AsyncMock(
        return_value={
            "pays": [
                {
                    "status": "complete",
                    "preimage": preimage,
                    "amount_msat": 10_000,
                    "amount_sent_msat": 10_123,
                }
            ]
        }
    )

    found, status = await wallet._get_listpays_status(payment_hash)

    assert found is True
    assert status.success is True
    assert status.preimage == preimage
    assert status.fee_msat == 123


@pytest.mark.anyio
async def test_clnrest_listpays_missing_is_distinct_from_pending(mocker):
    wallet = _wallet()
    wallet._rpc = mocker.AsyncMock(return_value={"pays": []})

    found, status = await wallet._get_listpays_status("11" * 32)

    assert found is False
    assert status.paid is None
