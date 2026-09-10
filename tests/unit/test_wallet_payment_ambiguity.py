from types import SimpleNamespace
from typing import Any, cast

import grpc
import httpx
import pytest
from pyln.client import RpcError
from pytest_mock.plugin import MockerFixture

import lnbits.wallets.breez as breez_wallet_module
import lnbits.wallets.breez_liquid as breez_liquid_wallet_module
from lnbits.wallets.alby import AlbyWallet
from lnbits.wallets.base import PaymentPendingStatus
from lnbits.wallets.blink import BlinkWallet
from lnbits.wallets.boltz import BoltzWallet
from lnbits.wallets.boltz_grpc_files import boltzrpc_pb2
from lnbits.wallets.corelightning import CoreLightningWallet
from lnbits.wallets.eclair import EclairWallet
from lnbits.wallets.lnd_grpc_files.lightning_pb2 import Payment as LndPayment
from lnbits.wallets.lndgrpc import LndWallet
from lnbits.wallets.lndrest import LndRestWallet
from lnbits.wallets.lnpay import LNPayWallet
from lnbits.wallets.lntips import LnTipsWallet
from lnbits.wallets.nwc import NWCError, NWCWallet
from lnbits.wallets.opennode import OpenNodeWallet
from lnbits.wallets.phoenixd import PhoenixdWallet
from lnbits.wallets.spark import SparkWallet
from lnbits.wallets.sparkl2 import SparkL2Wallet
from lnbits.wallets.strike import StrikeWallet
from lnbits.wallets.zbd import ZBDWallet


def _response(status_code: int, **kwargs) -> httpx.Response:
    request = httpx.Request("POST", "https://wallet.test/pay")
    return httpx.Response(status_code, request=request, **kwargs)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, None),
        (401, False),
        (403, False),
        (404, False),
        (405, False),
        (408, None),
        (409, None),
        (422, None),
        (429, None),
        (500, None),
    ],
)
async def test_alby_only_treats_definite_http_rejection_as_failed(
    mocker: MockerFixture, status_code: int, expected: bool | None
):
    wallet = object.__new__(AlbyWallet)
    wallet.endpoint = "https://wallet.test"
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(status_code, json={"message": "error"})
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected


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
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, False),
        (401, False),
        (403, False),
        (404, False),
        (405, False),
        (408, None),
        (409, None),
        (422, None),
        (429, None),
        (500, None),
    ],
)
async def test_eclair_only_treats_request_rejections_as_failed(
    mocker: MockerFixture, status_code: int, expected: bool | None
):
    wallet = object.__new__(EclairWallet)
    wallet.url = "https://wallet.test"
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(status_code, json={"error": "invoice has expired"})
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected
    assert response.error_message == "invoice has expired"


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
    ("error", "expected"),
    [
        (
            {
                "code": 2,
                "message": "invoice not for current active network 'regtest'",
            },
            False,
        ),
        ({"code": 2, "message": "invoice expired"}, False),
        ({"code": 3, "message": "invalid payment request"}, False),
        ({"code": 2, "message": "payment stream interrupted"}, None),
        ({"code": 14, "message": "transport unavailable"}, None),
    ],
)
async def test_lndrest_only_pre_dispatch_rpc_errors_are_failed(
    mocker: MockerFixture,
    settings,
    error: dict,
    expected: bool | None,
):
    settings.lnd_rest_allow_self_payment = False
    wallet = object.__new__(LndRestWallet)
    wallet.endpoint = "https://wallet.test"
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(500, json={"error": error}),
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected
    assert response.error_message == error["message"]


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
    ("error", "expected"),
    [
        (
            {
                "code": 0,
                "message": "destination is not reachable",
                "attempts": [{"status": "failed"}],
            },
            False,
        ),
        (
            {
                "code": 0,
                "message": "payment is still running",
                "attempts": [{"status": "pending"}],
            },
            None,
        ),
        ({"code": 0, "message": "unclassified RPC error"}, None),
        ({"code": 205, "message": "unable to find a route"}, False),
    ],
)
async def test_corelightning_only_terminal_rpc_errors_are_failed(
    mocker: MockerFixture,
    error: dict,
    expected: bool | None,
):
    wallet = object.__new__(CoreLightningWallet)
    wallet.pay = "pay"
    wallet.pay_failure_error_codes = [-32602, 201, 203, 205, 206, 207, 210]
    cast(Any, wallet).ln = SimpleNamespace(
        call=mocker.Mock(side_effect=RpcError("pay", {}, cast(Any, error)))
    )
    mocker.patch(
        "lnbits.wallets.corelightning.bolt11_decode",
        return_value=SimpleNamespace(
            payment_hash="payment-hash",
            amount_msat=1_000,
            description="",
        ),
    )
    mocker.patch.object(
        wallet, "get_payment_status", return_value=PaymentPendingStatus()
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, None),
        (401, False),
        (403, False),
        (404, False),
        (405, False),
        (408, None),
        (409, None),
        (422, None),
        (429, None),
        (500, None),
    ],
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
@pytest.mark.parametrize("wallet_class", [LnTipsWallet, OpenNodeWallet, ZBDWallet])
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(400, None), (401, False), (422, None)],
)
async def test_http_wallets_only_fail_definite_request_rejections(
    mocker: MockerFixture,
    wallet_class: type[LnTipsWallet | OpenNodeWallet | ZBDWallet],
    status_code: int,
    expected: bool | None,
):
    wallet = object.__new__(wallet_class)
    wallet.endpoint = "https://wallet.test"
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(status_code, json={"message": "error"})
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected


@pytest.mark.anyio
async def test_breez_immediate_failed_state_is_failed(mocker: MockerFixture, settings):
    settings.breez_use_trampoline = False
    breez_wallet = cast(Any, breez_wallet_module)
    wallet = object.__new__(breez_wallet.BreezSdkWallet)
    mocker.patch(
        "lnbits.wallets.breez.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    cast(Any, wallet).sdk_services = SimpleNamespace(
        send_payment=mocker.Mock(
            return_value=SimpleNamespace(
                payment=SimpleNamespace(status=breez_wallet.BreezPaymentStatus.FAILED)
            )
        )
    )

    response = await cast(Any, wallet).pay_invoice("bolt11", 1_000)

    assert response.ok is False
    assert response.checking_id == "payment-hash"


@pytest.mark.anyio
async def test_breez_liquid_timed_out_outgoing_payment_is_failed(
    mocker: MockerFixture,
):
    breez_liquid_wallet = cast(Any, breez_liquid_wallet_module)
    wallet = object.__new__(breez_liquid_wallet.BreezLiquidSdkWallet)
    cast(Any, wallet).sdk_services = SimpleNamespace(
        get_payment=mocker.Mock(
            return_value=SimpleNamespace(
                payment_type=breez_liquid_wallet.PaymentType.SEND,
                status=breez_liquid_wallet.PaymentState.TIMED_OUT,
            )
        )
    )

    status = await cast(Any, wallet).get_payment_status("payment-hash")

    assert status.paid is False


@pytest.mark.anyio
async def test_breez_liquid_prepare_error_is_failed(mocker: MockerFixture):
    breez_liquid_wallet = cast(Any, breez_liquid_wallet_module)
    wallet = object.__new__(breez_liquid_wallet.BreezLiquidSdkWallet)
    mocker.patch(
        "lnbits.wallets.breez_liquid.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    cast(Any, wallet).sdk_services = SimpleNamespace(
        prepare_send_payment=mocker.Mock(side_effect=RuntimeError("cannot prepare"))
    )

    response = await cast(Any, wallet).pay_invoice("bolt11", 1_000)

    assert response.ok is False
    assert response.checking_id == "payment-hash"


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
    mocker.patch(
        "lnbits.wallets.nwc.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
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
    ("provider_status", "expected"),
    [("unpaid", None), ("expired", False), ("paid", True)],
)
async def test_spark_invoice_uses_exact_terminal_status(
    mocker: MockerFixture,
    provider_status: str,
    expected: bool | None,
):
    wallet = object.__new__(SparkWallet)
    mocker.patch.object(
        wallet,
        "listinvoices",
        return_value={"invoices": [{"status": provider_status}]},
    )

    status = await wallet.get_invoice_status("invoice-id")

    assert status.paid is expected


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
@pytest.mark.parametrize(
    ("code", "details", "expected"),
    [
        (
            grpc.StatusCode.INVALID_ARGUMENT,
            "invalid invoice or lnurl: invalid HRP",
            False,
        ),
        (
            grpc.StatusCode.UNKNOWN,
            "boltz error: could not find route to pay invoice",
            False,
        ),
        (grpc.StatusCode.UNKNOWN, "payment response interrupted", None),
        (grpc.StatusCode.ALREADY_EXISTS, "swap already exists", None),
    ],
)
async def test_boltz_only_pre_dispatch_create_swap_errors_are_failed(
    mocker: MockerFixture,
    code: grpc.StatusCode,
    details: str,
    expected: bool | None,
):
    metadata = grpc.aio.Metadata()
    error = grpc.aio.AioRpcError(code, metadata, metadata, details=details)
    wallet = object.__new__(BoltzWallet)
    wallet.metadata = None
    wallet.wallet_id = 1
    cast(Any, wallet).rpc = SimpleNamespace(
        GetPairInfo=mocker.AsyncMock(
            return_value=SimpleNamespace(
                fees=SimpleNamespace(percentage=0, miner_fees=0)
            )
        ),
        CreateSwap=mocker.AsyncMock(side_effect=error),
    )
    mocker.patch(
        "lnbits.wallets.boltz.decode",
        return_value=SimpleNamespace(
            amount_msat=1_000,
            payment_hash="payment-hash",
        ),
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected
    assert response.checking_id == "payment-hash"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (boltzrpc_pb2.ERROR, False),
        (boltzrpc_pb2.PENDING, None),
        (boltzrpc_pb2.SUCCESSFUL, True),
    ],
)
async def test_boltz_resolves_ambiguous_create_swap_error_from_backend_state(
    mocker: MockerFixture,
    state: int,
    expected: bool | None,
):
    metadata = grpc.aio.Metadata()
    error = grpc.aio.AioRpcError(
        grpc.StatusCode.UNKNOWN,
        metadata,
        metadata,
        details='sendrawtransaction RPC error: {"message":"txn-mempool-conflict"}',
    )
    payment_hash = "00" * 32
    wallet = object.__new__(BoltzWallet)
    wallet.metadata = None
    wallet.wallet_id = 1
    cast(Any, wallet).rpc = SimpleNamespace(
        GetPairInfo=mocker.AsyncMock(
            return_value=SimpleNamespace(
                fees=SimpleNamespace(percentage=0, miner_fees=0)
            )
        ),
        CreateSwap=mocker.AsyncMock(side_effect=error),
        GetSwapInfo=mocker.AsyncMock(
            return_value=SimpleNamespace(
                swap=SimpleNamespace(
                    state=state,
                    service_fee=1,
                    onchain_fee=2,
                    status="swap status",
                    preimage="preimage",
                )
            )
        ),
    )
    mocker.patch(
        "lnbits.wallets.boltz.decode",
        return_value=SimpleNamespace(
            amount_msat=1_000,
            payment_hash=payment_hash,
        ),
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected
    assert response.checking_id == payment_hash
    assert response.fee_msat == (3_000 if expected is True else None)
    assert response.preimage == ("preimage" if expected is True else None)


@pytest.mark.anyio
async def test_boltz_error_text_without_terminal_state_is_pending(
    mocker: MockerFixture,
):
    async def swap_updates():
        yield SimpleNamespace(
            swap=SimpleNamespace(state=999, error="unrecognized transient error")
        )

    wallet = object.__new__(BoltzWallet)
    wallet.metadata = None
    wallet.wallet_id = 1
    cast(Any, wallet).rpc = SimpleNamespace(
        GetPairInfo=mocker.AsyncMock(
            return_value=SimpleNamespace(
                fees=SimpleNamespace(percentage=0, miner_fees=0)
            )
        ),
        CreateSwap=mocker.AsyncMock(return_value=SimpleNamespace(id="swap-id")),
        GetSwapInfoStream=mocker.Mock(return_value=swap_updates()),
    )
    mocker.patch(
        "lnbits.wallets.boltz.decode",
        return_value=SimpleNamespace(
            amount_msat=1_000,
            payment_hash="payment-hash",
        ),
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is None


@pytest.mark.anyio
async def test_opennode_terminal_error_status_is_failed(mocker: MockerFixture):
    wallet = object.__new__(OpenNodeWallet)
    cast(Any, wallet).client = SimpleNamespace(
        get=mocker.AsyncMock(
            return_value=_response(
                200,
                json={"data": {"status": "error", "fee": 1}},
            )
        )
    )

    status = await wallet.get_payment_status("withdrawal-id")

    assert status.paid is False


@pytest.mark.anyio
async def test_opennode_terminal_status_does_not_require_provider_id(
    mocker: MockerFixture,
):
    wallet = object.__new__(OpenNodeWallet)
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(
                200,
                json={"data": {"status": "failed"}},
            )
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is False
    assert response.checking_id is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider_status", "expected"),
    [("processing", None), ("completed", True), ("failed", False)],
)
async def test_zbd_preserves_provider_id_and_exact_status(
    mocker: MockerFixture,
    provider_status: str,
    expected: bool | None,
):
    wallet = object.__new__(ZBDWallet)
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(
                200,
                json={
                    "data": {
                        "id": "zbd-payment-id",
                        "status": provider_status,
                        "fee": "10",
                        "preimage": "preimage",
                    }
                },
            )
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is expected
    assert response.checking_id == "zbd-payment-id"


@pytest.mark.anyio
async def test_zbd_terminal_status_does_not_require_provider_id(
    mocker: MockerFixture,
):
    wallet = object.__new__(ZBDWallet)
    cast(Any, wallet).client = SimpleNamespace(
        post=mocker.AsyncMock(
            return_value=_response(
                200,
                json={"data": {"status": "failed"}},
            )
        )
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is False
    assert response.checking_id is None


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


@pytest.mark.anyio
async def test_strike_ambiguous_execution_uses_payment_hash_fallback(
    mocker: MockerFixture,
):
    wallet = object.__new__(StrikeWallet)
    wallet.pending_payments = {}
    mocker.patch(
        "lnbits.wallets.strike.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    mocker.patch.object(
        wallet,
        "_create_payment_quote",
        return_value=("quote-id", None),
    )
    mocker.patch.object(
        wallet,
        "_execute_payment_quote",
        return_value=(None, "request timed out"),
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is None
    assert response.checking_id is None


@pytest.mark.anyio
async def test_strike_terminal_state_does_not_require_payment_id(
    mocker: MockerFixture,
):
    wallet = object.__new__(StrikeWallet)
    wallet.pending_payments = {}
    mocker.patch(
        "lnbits.wallets.strike.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    mocker.patch.object(
        wallet,
        "_create_payment_quote",
        return_value=("quote-id", None),
    )
    mocker.patch.object(
        wallet,
        "_execute_payment_quote",
        return_value=({"state": "FAILED"}, None),
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is False
    assert response.checking_id == "payment-hash"


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["CANCELED", "TIMED_OUT", "UNKNOWN"])
async def test_strike_undocumented_payment_state_is_pending(
    mocker: MockerFixture, state: str
):
    wallet = object.__new__(StrikeWallet)
    wallet.pending_payments = {}
    mocker.patch(
        "lnbits.wallets.strike.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="payment-hash"),
    )
    mocker.patch.object(
        wallet,
        "_create_payment_quote",
        return_value=("quote-id", None),
    )
    mocker.patch.object(
        wallet,
        "_execute_payment_quote",
        return_value=({"state": state, "paymentId": "payment-id"}, None),
    )

    response = await wallet.pay_invoice("bolt11", 1_000)

    assert response.ok is None
    assert response.checking_id == "payment-id"


@pytest.mark.anyio
async def test_strike_persisted_payment_hash_not_found_stays_pending(
    mocker: MockerFixture,
):
    wallet = object.__new__(StrikeWallet)
    wallet.pending_payments = {}
    cast(Any, wallet)._get = mocker.AsyncMock(
        return_value=_response(404, text="Not Found")
    )

    payment_hash = "ab" * 32
    status = await wallet.get_payment_status(payment_hash)

    assert status.paid is None
    cast(Any, wallet)._get.assert_awaited_once_with(f"/payments/{payment_hash}")
