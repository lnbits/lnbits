from types import SimpleNamespace
from typing import Any, cast

import grpc
import httpx
import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.wallets.base import PaymentPendingStatus
from lnbits.wallets.blink import BlinkWallet
from lnbits.wallets.boltz import BoltzWallet
from lnbits.wallets.boltz_grpc_files import boltzrpc_pb2
from lnbits.wallets.lnd_grpc_files.lightning_pb2 import Payment as LndPayment
from lnbits.wallets.lndgrpc import LndWallet
from lnbits.wallets.lndrest import LndRestWallet
from lnbits.wallets.lnpay import LNPayWallet
from lnbits.wallets.nwc import NWCError, NWCWallet
from lnbits.wallets.phoenixd import PhoenixdWallet
from lnbits.wallets.sparkl2 import SparkL2Wallet
from lnbits.wallets.strike import StrikeWallet


def _response(status_code: int, **kwargs) -> httpx.Response:
    request = httpx.Request("POST", "https://wallet.test/pay")
    return httpx.Response(status_code, request=request, **kwargs)


@pytest.mark.anyio
async def test_blink_keeps_unconfirmed_payment_pending(mocker: MockerFixture):
    wallet = object.__new__(BlinkWallet)
    wallet._wallet_id = "wallet-id"
    wallet.endpoint = "https://wallet.test"
    mocker.patch(
        "lnbits.wallets.blink.bolt11_lib.decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    mocker.patch.object(
        wallet,
        "_graphql_query",
        return_value={"data": {"lnInvoicePaymentSend": {"errors": []}}},
    )
    mocker.patch.object(
        wallet, "get_payment_status", return_value=PaymentPendingStatus()
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is None
    assert response.checking_id == "payment-hash"


@pytest.mark.anyio
async def test_lndrest_unknown_payment_state_is_pending(
    mocker: MockerFixture, settings
):
    settings.lnd_rest_allow_self_payment = False
    wallet = object.__new__(LndRestWallet)
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(
                200,
                json={
                    "result": {
                        "status": "FUTURE_STATUS",
                        "payment_hash": "payment-hash",
                        "payment_preimage": "",
                        "fee_msat": "0",
                    }
                },
            )
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is None
    assert response.checking_id == "payment-hash"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("code", "details", "expected"),
    [
        (
            grpc.StatusCode.UNKNOWN,
            "invoice not for current active network 'regtest'",
            False,
        ),
        (grpc.StatusCode.UNKNOWN, "invoice expired", False),
        (grpc.StatusCode.INVALID_ARGUMENT, "invalid payment request", False),
        (grpc.StatusCode.PERMISSION_DENIED, "permission denied", False),
        (grpc.StatusCode.UNAUTHENTICATED, "invalid macaroon", False),
        (grpc.StatusCode.UNAVAILABLE, "transport is closing", None),
        (grpc.StatusCode.DEADLINE_EXCEEDED, "deadline exceeded", None),
        (grpc.StatusCode.ALREADY_EXISTS, "payment is in flight", None),
        (grpc.StatusCode.UNKNOWN, "payment stream interrupted", None),
    ],
)
async def test_lndgrpc_only_pre_dispatch_rpc_errors_are_failed(
    mocker: MockerFixture,
    settings,
    code: grpc.StatusCode,
    details: str,
    expected: bool | None,
):
    settings.lnd_grpc_allow_self_payment = False
    metadata = grpc.aio.Metadata()
    error = grpc.aio.AioRpcError(code, metadata, metadata, details=details)
    wallet = object.__new__(LndWallet)
    cast(Any, wallet).router_rpc = SimpleNamespace(
        SendPaymentV2=mocker.Mock(
            return_value=SimpleNamespace(read=mocker.AsyncMock(side_effect=error))
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected


@pytest.mark.anyio
async def test_lndgrpc_in_flight_payment_is_pending(mocker: MockerFixture, settings):
    settings.lnd_grpc_allow_self_payment = False
    wallet = object.__new__(LndWallet)
    cast(Any, wallet).router_rpc = SimpleNamespace(
        SendPaymentV2=mocker.Mock(
            return_value=SimpleNamespace(
                read=mocker.AsyncMock(
                    return_value=SimpleNamespace(
                        status=LndPayment.PaymentStatus.IN_FLIGHT,
                        payment_hash="payment-hash",
                    )
                )
            )
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is None
    assert response.checking_id == "payment-hash"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(400, False), (500, None)],
)
async def test_lnpay_only_treats_client_rejection_as_failed(
    mocker: MockerFixture, status_code: int, expected: bool | None
):
    wallet = object.__new__(LNPayWallet)
    wallet.wallet_key = "wallet-key"
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(status_code, json={"message": "error"})
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected


@pytest.mark.anyio
async def test_lnpay_malformed_payment_response_is_pending(mocker: MockerFixture):
    wallet = object.__new__(LNPayWallet)
    wallet.wallet_key = "wallet-key"
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(return_value=_response(200, content=b"not-json"))
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("code", "expected"),
    [("PAYMENT_FAILED", False), ("INTERNAL", None), ("OTHER", None)],
)
async def test_nwc_only_explicit_payment_failure_is_failed(
    mocker: MockerFixture, code: str, expected: bool | None
):
    wallet = object.__new__(NWCWallet)
    cast(Any, wallet).conn = SimpleNamespace(
        call=mocker.AsyncMock(side_effect=NWCError(code, "error"))
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected


@pytest.mark.anyio
async def test_phoenix_request_error_is_pending(mocker: MockerFixture):
    wallet = object.__new__(PhoenixdWallet)
    wallet.endpoint = "https://wallet.test"
    request = httpx.Request("POST", "https://wallet.test/payinvoice")
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            side_effect=httpx.ReadError("read failed", request=request)
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is None


@pytest.mark.anyio
async def test_spark_sidecar_missing_checking_id_is_pending(mocker: MockerFixture):
    wallet = object.__new__(SparkL2Wallet)
    mocker.patch.object(wallet, "_request", return_value={"status": "PENDING"})

    response = await wallet.pay_invoice("not-a-bolt11", 1_000)

    assert response.ok is None
    assert response.checking_id is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (boltzrpc_pb2.SwapState.ERROR, False),
        (999, None),
    ],
)
async def test_boltz_only_known_terminal_swap_state_is_failed(
    mocker: MockerFixture, state: int, expected: bool | None
):
    wallet = object.__new__(BoltzWallet)
    wallet.metadata = None
    cast(Any, wallet).rpc = SimpleNamespace(
        GetSwapInfo=mocker.AsyncMock(
            return_value=SimpleNamespace(swap=SimpleNamespace(state=state))
        )
    )

    status = await wallet.get_payment_status("00" * 32)

    assert status.paid is expected


@pytest.mark.anyio
async def test_strike_invalid_fallback_identifier_is_pending(mocker: MockerFixture):
    wallet = object.__new__(StrikeWallet)
    wallet.pending_payments = {}
    cast(Any, wallet)._get = mocker.AsyncMock(
        return_value=_response(
            400,
            json={
                "data": {
                    "code": "INVALID_DATA",
                    "validationErrors": {
                        "paymentId": [
                            {
                                "code": "INVALID_DATA",
                                "message": "paymentId is not valid.",
                            }
                        ]
                    },
                }
            },
        )
    )

    status = await wallet._get_payment_status_by_checking_id("payment-hash")

    assert status.paid is None
