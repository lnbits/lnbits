import hashlib
from types import SimpleNamespace

import httpx
import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.settings import Settings
from lnbits.wallets.sparkl2 import SparkL2Wallet, SparkSidecarError


@pytest.mark.anyio
async def test_status_returns_stable_available_balance(mocker: MockerFixture):
    wallet = object.__new__(SparkL2Wallet)
    mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(
            return_value={
                "status": "ready",
                "balance_msat": "659160000",
                "available_sats": "659160",
                "owned_sats": "659160",
                "incoming_sats": "0",
            }
        ),
    )

    status = await wallet.status()

    assert status.error_message is None
    assert status.balance_msat == 659_160_000


@pytest.mark.anyio
async def test_status_accepts_recovering_balance_as_zero(mocker: MockerFixture):
    wallet = object.__new__(SparkL2Wallet)
    mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(
            return_value={
                "status": "recovering",
                "balance_msat": "488000",
                "available_sats": "488",
                "owned_sats": "488",
                "incoming_sats": "658672",
            }
        ),
    )

    status = await wallet.status()

    assert status.error_message is None
    assert status.balance_msat == 0


@pytest.mark.anyio
async def test_status_rejects_unknown_readiness(mocker: MockerFixture):
    wallet = object.__new__(SparkL2Wallet)
    mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(
            return_value={
                "status": "initializing",
                "balance_msat": "659160000",
            }
        ),
    )

    status = await wallet.status()

    assert status.error_message == "Spark sidecar is not ready: initializing."
    assert status.balance_msat == 0


@pytest.mark.anyio
async def test_pay_invoice_passes_sidecar_settlement_window(
    settings: Settings, mocker: MockerFixture
):
    wallet = object.__new__(SparkL2Wallet)
    request = mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(
            return_value={
                "checking_id": "sidecar-id",
                "status": "LIGHTNING_PAYMENT_PENDING",
            }
        ),
    )
    mocker.patch(
        "lnbits.wallets.sparkl2.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    settings.spark_l2_pay_wait_ms = 12_000
    settings.spark_l2_pay_poll_ms = 750

    response = await wallet.pay_invoice("bolt11", fee_limit_msat=1_001)

    assert response.pending
    assert response.checking_id == "payment-hash"
    request.assert_awaited_once_with(
        "POST",
        "/v1/payments",
        {
            "bolt11": "bolt11",
            "max_fee_sats": 2,
            "payment_hash": "payment-hash",
            "wait_ms": 12_000,
            "poll_ms": 750,
        },
    )


@pytest.mark.anyio
async def test_pay_invoice_keeps_ambiguous_sidecar_error_pending(
    mocker: MockerFixture,
):
    wallet = object.__new__(SparkL2Wallet)
    mocker.patch(
        "lnbits.wallets.sparkl2.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(side_effect=SparkSidecarError("connection lost")),
    )

    response = await wallet.pay_invoice("bolt11", fee_limit_msat=1_000)

    assert response.pending
    assert response.checking_id == "payment-hash"
    assert response.error_message == ("Ambiguous Spark payment result: connection lost")


@pytest.mark.anyio
async def test_pay_invoice_releases_reserve_only_for_pre_submission_rejection(
    mocker: MockerFixture,
):
    wallet = object.__new__(SparkL2Wallet)
    mocker.patch(
        "lnbits.wallets.sparkl2.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(
            side_effect=SparkSidecarError(
                "payment queue is at capacity",
                payment_submitted=False,
            )
        ),
    )

    response = await wallet.pay_invoice("bolt11", fee_limit_msat=1_000)

    assert response.failed
    assert response.checking_id == "payment-hash"
    assert response.error_message == (
        "Spark payment not submitted: payment queue is at capacity"
    )


@pytest.mark.anyio
async def test_request_preserves_pre_submission_rejection_marker():
    def reject_before_submission(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "error": "Spark payment queue is at capacity",
                "payment_submitted": False,
            },
        )

    wallet = object.__new__(SparkL2Wallet)
    wallet.client = httpx.AsyncClient(
        base_url="http://sidecar",
        transport=httpx.MockTransport(reject_before_submission),
    )

    with pytest.raises(SparkSidecarError) as exc_info:
        await wallet._request("POST", "/v1/payments", {})
    await wallet.client.aclose()

    assert exc_info.value.payment_submitted is False


@pytest.mark.anyio
async def test_pay_invoice_rejects_invalid_bolt11_before_sidecar(
    mocker: MockerFixture,
):
    wallet = object.__new__(SparkL2Wallet)
    request = mocker.patch.object(wallet, "_request", mocker.AsyncMock())
    mocker.patch(
        "lnbits.wallets.sparkl2.bolt11_decode",
        side_effect=ValueError("invalid invoice"),
    )

    response = await wallet.pay_invoice("invalid", fee_limit_msat=1_000)

    assert response.failed
    assert response.checking_id is None
    request.assert_not_awaited()


def test_payment_status_accepts_spark_success_states():
    wallet = object.__new__(SparkL2Wallet)

    assert wallet._map_payment_status("LIGHTNING_PAYMENT_SUCCEEDED").success
    assert wallet._map_payment_status("PREIMAGE_PROVIDED").success
    assert wallet._map_payment_status("TRANSFER_COMPLETED").success
    assert wallet._map_payment_status("TRANSFER_FAILED").failed


def test_invoice_status_accepts_spark_receive_success_states():
    wallet = object.__new__(SparkL2Wallet)

    assert wallet._map_invoice_status("LIGHTNING_PAYMENT_RECEIVED").success
    assert wallet._map_invoice_status("PAYMENT_PREIMAGE_RECOVERED").success
    assert wallet._map_invoice_status("TRANSFER_COMPLETED").success
    assert wallet._map_invoice_status("TRANSFER_FAILED").failed


@pytest.mark.anyio
async def test_payment_preimage_prevents_false_failure(mocker: MockerFixture):
    wallet = object.__new__(SparkL2Wallet)
    preimage = "00" * 32
    payment_hash = hashlib.sha256(bytes.fromhex(preimage)).hexdigest()
    mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(
            return_value={
                "status": "TRANSFER_FAILED",
                "fee_msat": "1000",
                "preimage": preimage,
            }
        ),
    )

    status = await wallet.get_payment_status(payment_hash)

    assert status.success
    assert status.preimage == preimage


@pytest.mark.anyio
async def test_pay_invoice_uses_fee_limit_when_success_fee_is_missing(
    mocker: MockerFixture,
):
    wallet = object.__new__(SparkL2Wallet)
    mocker.patch(
        "lnbits.wallets.sparkl2.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(
            return_value={
                "status": "TRANSFER_COMPLETED",
                "fee_msat": None,
                "preimage": None,
            }
        ),
    )

    response = await wallet.pay_invoice("bolt11", fee_limit_msat=2_500)

    assert response.success
    assert response.fee_msat == 3_000


@pytest.mark.anyio
async def test_payment_status_missing_fee_stays_pending(mocker: MockerFixture):
    wallet = object.__new__(SparkL2Wallet)
    mocker.patch.object(
        wallet,
        "_request",
        mocker.AsyncMock(
            return_value={
                "status": "TRANSFER_COMPLETED",
                "fee_msat": None,
                "preimage": None,
            }
        ),
    )

    status = await wallet.get_payment_status("payment-hash")

    assert status.pending
