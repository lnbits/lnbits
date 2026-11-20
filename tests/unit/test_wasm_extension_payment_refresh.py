from pathlib import Path
from runpy import run_path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import create_payment, create_wallet, get_payment
from lnbits.core.models import CreatePayment, Payment, PaymentState, Wallet
from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.wallets import WalletPermission, WalletType
from lnbits.core.services import create_user_account
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import RefreshPaymentRequest
from lnbits.core.wasm_ext.api.permissions import validate_extension_permissions
from lnbits.core.wasm_ext.api.registry import get_extension_api_method
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.wallets.base import PaymentSuccessStatus

METHOD = "wallet.refresh_payment"
PERMISSION = "wallet.payments.refresh"
REQUEST = {"wallet_id": "wallet-1", "checking_id": "check-1"}


@pytest.fixture
def payment() -> Payment:
    return Payment(
        checking_id="check-1",
        payment_hash="a" * 64,
        wallet_id="wallet-1",
        amount=-21_000,
        fee=-1_000,
        bolt11="test-invoice",
        preimage="private-preimage",
        extra={"private": "metadata"},
    )


@pytest.fixture
def wallet() -> Wallet:
    return Wallet(
        id="wallet-1",
        user="user-1",
        name="Test wallet",
        adminkey="admin-key",
        inkey="invoice-key",
    )


@pytest.fixture
def refresh_mocks(
    mocker: MockerFixture, wallet: Wallet, payment: Payment
) -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    wallet_lookup = mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", AsyncMock(return_value=wallet)
    )
    payment_lookup = mocker.patch(
        "lnbits.core.crud.payments.get_standalone_payment",
        AsyncMock(return_value=payment),
    )
    refresh = mocker.patch(
        "lnbits.core.services.payments.update_pending_payment", AsyncMock()
    )
    return wallet_lookup, payment_lookup, refresh


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("context", "user_id", "permissions"),
    [
        ("user", None, [PERMISSION]),
        ("event", None, [PERMISSION]),
        ("schedule", None, [PERMISSION]),
        ("user", "user-1", []),
        ("user", "user-1", ["wallet.balance.read", "wallet.payments.watch"]),
    ],
)
async def test_refresh_requires_user_and_permission(
    context, user_id, permissions, refresh_mocks
):
    api = ExtensionHostAPI(
        "demo", permissions, user_id=user_id, context=context, owner_id="owner"
    )

    with pytest.raises(PermissionError):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    for mock in refresh_mocks:
        mock.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("exists", [True, False])
async def test_refresh_requires_owned_wallet(exists, wallet, refresh_mocks):
    wallet_lookup, payment_lookup, refresh = refresh_mocks
    wallet.user = "other-user"
    wallet_lookup.return_value = wallet if exists else None
    api = ExtensionHostAPI("demo", [PERMISSION], user_id="user-1")

    with pytest.raises(PermissionError, match="not allowed"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    payment_lookup.assert_not_awaited()
    refresh.assert_not_awaited()


@pytest.mark.anyio
async def test_refresh_requires_payment_in_wallet(refresh_mocks):
    _, payment_lookup, refresh = refresh_mocks
    payment_lookup.return_value = None
    api = ExtensionHostAPI("demo", [PERMISSION], user_id="user-1")

    with pytest.raises(ValueError, match="not found in this wallet"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    payment_lookup.assert_awaited_once_with("check-1", wallet_id="wallet-1")
    refresh.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("status", list(PaymentState))
async def test_refresh_returns_reconciled_summary(status, payment, refresh_mocks):
    _, payment_lookup, refresh = refresh_mocks
    refresh.return_value = payment.model_copy(update={"status": status, "fee": -21})
    api = ExtensionHostAPI("demo", [PERMISSION], user_id="user-1")

    response = await ExtensionAPIHost(api).invoke(
        "refreshPayment", {"walletId": "wallet-1", "checkingId": "check-1"}
    )

    payment_lookup.assert_awaited_once_with("check-1", wallet_id="wallet-1")
    refresh.assert_awaited_once_with(payment)
    assert response == {
        "checkingId": "check-1",
        "paymentHash": "a" * 64,
        "status": status.value,
        "amountMsat": 21_000,
        "feeMsat": 21,
        "pending": status == PaymentState.PENDING,
        "success": status == PaymentState.SUCCESS,
    }


@pytest.mark.anyio
@pytest.mark.parametrize("status", [PaymentState.SUCCESS, PaymentState.FAILED])
async def test_refresh_skips_completed_payments(status, payment, refresh_mocks):
    payment.status = status
    api = ExtensionHostAPI("demo", [PERMISSION], user_id="user-1")

    response = await ExtensionAPIHost(api).invoke(METHOD, REQUEST)

    assert response["status"] == status.value
    refresh_mocks[2].assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
async def test_refresh_hides_backend_error_details(error_type, refresh_mocks):
    refresh_mocks[2].side_effect = error_type("Private backend details")
    api = ExtensionHostAPI("demo", [PERMISSION], user_id="user-1")

    with pytest.raises(RuntimeError, match="^Unable to refresh payment status\\.$"):
        await ExtensionAPIHost(api).invoke(METHOD, REQUEST)


def test_refresh_does_not_accept_caller_supplied_status():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RefreshPaymentRequest.model_validate({**REQUEST, "status": "success"})


def test_refresh_permission_and_sdk_are_discoverable():
    method = get_extension_api_method(METHOD)
    assert method.require_auth is True
    assert method.required_permission == PERMISSION
    permission = ExtensionPermission(id=PERMISSION)
    assert validate_extension_permissions("demo", [permission]) == [permission]
    codegen = run_path(
        str(
            Path(__file__).resolve().parents[2]
            / "tools/codegen/extension_sdk_typescript.py"
        )
    )
    sdk = codegen["generate_typescript_sdk"](method_ids=[METHOD])
    assert "refreshPayment(input: RefreshPaymentRequest)" in sdk
    assert "Promise<RefreshPaymentResponse>" in sdk
    assert "walletId: string" in sdk
    assert "checkingId: string" in sdk
    assert "return host.host.refreshPayment(input)" in sdk


@pytest.mark.anyio
async def test_refresh_persists_status_and_scopes_payment_lookup(
    app, mocker: MockerFixture
):
    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="Refresh wallet")
    other_wallet = await create_wallet(user_id=user.id, wallet_name="Other wallet")
    payment = await create_payment(
        uuid4().hex,
        CreatePayment(
            wallet_id=wallet.id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=21_000,
            memo="Refresh test",
        ),
    )
    backend = mocker.patch(
        "lnbits.core.services.payments.check_payment_status",
        AsyncMock(return_value=PaymentSuccessStatus(fee_msat=21)),
    )
    api = ExtensionAPIHost(ExtensionHostAPI("demo", [PERMISSION], user_id=user.id))

    with pytest.raises(ValueError, match="not found in this wallet"):
        await api.invoke(
            METHOD, {"wallet_id": other_wallet.id, "checking_id": payment.checking_id}
        )
    backend.assert_not_awaited()
    assert (await get_payment(payment.checking_id)).pending

    response = await api.invoke(
        METHOD, {"wallet_id": wallet.id, "checking_id": payment.checking_id}
    )

    stored = await get_payment(payment.checking_id)
    assert stored.success
    assert stored.fee == 21
    assert response["status"] == "success"
    assert response["feeMsat"] == 21
    backend.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize("can_view", [False, True])
async def test_refresh_respects_shared_wallet_payment_access(
    app, mocker: MockerFixture, wallet: Wallet, can_view: bool
):
    source_user = await create_user_account()
    source_wallet = await create_wallet(
        user_id=source_user.id, wallet_name="Source wallet"
    )
    payment = await create_payment(
        uuid4().hex,
        CreatePayment(
            wallet_id=source_wallet.id,
            payment_hash=uuid4().hex,
            bolt11="",
            amount_msat=21_000,
            memo="Shared refresh test",
        ),
    )
    wallet.wallet_type = WalletType.LIGHTNING_SHARED.value
    wallet.shared_wallet_id = source_wallet.id
    wallet.share_permissions = [WalletPermission.VIEW_PAYMENTS] if can_view else []
    mocker.patch("lnbits.core.crud.wallets.get_wallet", AsyncMock(return_value=wallet))
    mocker.patch("lnbits.core.crud.payments.get_wallet", AsyncMock(return_value=wallet))
    refresh = mocker.patch(
        "lnbits.core.services.payments.update_pending_payment",
        AsyncMock(return_value=payment),
    )
    api = ExtensionAPIHost(ExtensionHostAPI("demo", [PERMISSION], user_id=wallet.user))
    payload = {"wallet_id": wallet.id, "checking_id": payment.checking_id}

    if can_view:
        response = await api.invoke(METHOD, payload)
        assert response["paymentHash"] == payment.payment_hash
        refresh.assert_awaited_once_with(payment)
    else:
        with pytest.raises(ValueError, match="not found in this wallet"):
            await api.invoke(METHOD, payload)
        refresh.assert_not_awaited()
