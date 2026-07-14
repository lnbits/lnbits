import json
from types import SimpleNamespace

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import (
    CreateInvoicePublicRequest,
    EmptyRequest,
    PayInvoiceRequest,
    StorageGetRequest,
    WalletBalanceRequest,
)
from lnbits.exceptions import PaymentError
from lnbits.helpers import sha256s


@pytest.mark.anyio
async def test_host_api_filters_public_storage_fields(mocker: MockerFixture):
    storage_mock = mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_public_row",
        mocker.AsyncMock(
            return_value={
                "id": "tip-1",
                "title": "Tip jar",
                "wallet_id": "secret-wallet",
            }
        ),
    )
    api = ExtensionHostAPI(
        "demoext",
        [
            ExtensionPermission(
                id="ext.storage.read_public",
                policies=[{"table_name": "tips", "public_fields": ["id", "title"]}],
            )
        ],
    )

    response = await api.storage_get_public(StorageGetRequest(table="tips", id="tip-1"))

    assert json.loads(response.data_json or "{}") == {
        "id": "tip-1",
        "title": "Tip jar",
    }
    storage_mock.assert_awaited_once_with("demoext", "tips", "tip-1")


@pytest.mark.anyio
async def test_host_api_storage_requires_owner_context_and_uses_user_hash(
    mocker: MockerFixture,
):
    api_without_owner = ExtensionHostAPI(
        "demoext",
        ["ext.storage.read"],
        context="event",
    )
    with pytest.raises(PermissionError, match="owner context"):
        await api_without_owner.storage_get(StorageGetRequest(table="notes", id="1"))

    storage_mock = mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_row",
        mocker.AsyncMock(return_value={"id": "1", "title": "Note"}),
    )
    api = ExtensionHostAPI("demoext", ["ext.storage.read"], user_id="user-1")

    response = await api.storage_get(StorageGetRequest(table="notes", id="1"))

    assert json.loads(response.data_json or "{}") == {"id": "1", "title": "Note"}
    storage_mock.assert_awaited_once_with(
        "demoext",
        "notes",
        "1",
        sha256s("user-1"),
    )


@pytest.mark.anyio
async def test_host_api_wallet_methods_require_permissions_and_user_wallets(
    mocker: MockerFixture,
):
    api_without_permission = ExtensionHostAPI("demoext", [], user_id="user-1")
    with pytest.raises(PermissionError, match="wallet.list"):
        await api_without_permission.wallet_list_user_wallets(EmptyRequest())

    wallet = SimpleNamespace(id="wallet-1", name="Wallet", currency="USD")
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallets",
        mocker.AsyncMock(return_value=[wallet]),
    )
    api = ExtensionHostAPI("demoext", ["wallet.list"], user_id="user-1")

    response = await api.wallet_list_user_wallets(EmptyRequest())

    assert response.wallets[0].id == "wallet-1"
    assert response.wallets[0].name == "Wallet"


@pytest.mark.anyio
async def test_host_api_wallet_balance_rejects_other_users_wallets(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet",
        mocker.AsyncMock(return_value=SimpleNamespace(id="wallet-1", user="other")),
    )
    api = ExtensionHostAPI(
        "demoext",
        ["wallet.balance.read"],
        user_id="user-1",
    )

    with pytest.raises(PermissionError, match="not allowed"):
        await api.wallet_balance(WalletBalanceRequest(wallet_id="wallet-1"))


@pytest.mark.anyio
async def test_host_api_wallet_balance_returns_safe_summary(mocker: MockerFixture):
    wallet = SimpleNamespace(
        id="wallet-1",
        user="user-1",
        name="Wallet",
        currency="USD",
        balance_msat=10_000,
        balance=10,
        withdrawable_balance=8_000,
        can_send_payments=True,
    )
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet",
        mocker.AsyncMock(return_value=wallet),
    )
    api = ExtensionHostAPI(
        "demoext",
        ["wallet.balance.read"],
        user_id="user-1",
    )

    response = await api.wallet_balance(WalletBalanceRequest(wallet_id="wallet-1"))

    assert response.wallet_id == "wallet-1"
    assert response.balance_msat == 10_000
    assert response.withdrawable_msat == 8_000
    assert response.fee_reserve_msat == 2_000
    assert response.can_send_payments is True


@pytest.mark.anyio
async def test_host_api_pay_invoice_checks_wallet_owner_and_returns_payment_errors(
    mocker: MockerFixture,
):
    wallet = SimpleNamespace(id="wallet-1", user="user-1")
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet",
        mocker.AsyncMock(return_value=wallet),
    )
    mocker.patch(
        "lnbits.core.services.payments.pay_invoice",
        mocker.AsyncMock(side_effect=PaymentError("insufficient balance")),
    )
    api = ExtensionHostAPI("demoext", ["wallet.pay_invoice"], user_id="user-1")

    response = await api.wallet_pay_invoice(
        PayInvoiceRequest(
            wallet_id="wallet-1",
            payment_request="lnbc1demo",
            max_sat=None,
            description="Demo",
            extra={"source": "test"},
        )
    )

    assert response.ok is False
    assert response.error == "insufficient balance"


@pytest.mark.anyio
async def test_host_api_public_invoice_uses_granted_source_policy(
    mocker: MockerFixture,
):
    storage_mock = mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_public_row",
        mocker.AsyncMock(return_value={"id": "tip-1", "wallet_id": "wallet-1"}),
    )
    payment = SimpleNamespace(
        payment_hash="hash",
        payment_request="lnbc1demo",
        bolt11="lnbc1fallback",
        checking_id="checking-id",
    )
    create_mock = mocker.patch(
        "lnbits.core.services.payments.create_payment_request",
        mocker.AsyncMock(return_value=payment),
    )
    api = ExtensionHostAPI(
        "demoext",
        [
            ExtensionPermission(
                id="wallet.create_invoice_public",
                policies=[{"table": "tips", "wallet_field": "wallet_id"}],
            )
        ],
    )

    response = await api.wallet_create_invoice_public(
        CreateInvoicePublicRequest(
            source_id="tip-1",
            amount=21,
            currency="sat",
            memo="Tip",
            extra={"note": "thanks"},
        )
    )

    assert response.payment_hash == "hash"
    storage_mock.assert_awaited_once_with("demoext", "tips", "tip-1")
    create_mock.assert_awaited_once()
    assert create_mock.await_args is not None
    wallet_id, invoice = create_mock.await_args.args
    assert wallet_id == "wallet-1"
    assert invoice.extra == {
        "tag": "demoext",
        "source_id": "tip-1",
        "extra_demoext": {"note": "thanks"},
    }
    assert invoice.extension == "demoext"


@pytest.mark.anyio
async def test_host_api_public_invoice_rejects_missing_source_wallet(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_public_row",
        mocker.AsyncMock(return_value={"id": "tip-1"}),
    )
    api = ExtensionHostAPI(
        "demoext",
        [
            ExtensionPermission(
                id="wallet.create_invoice_public",
                policies=[{"table": "tips", "wallet_field": "wallet_id"}],
            )
        ],
    )

    with pytest.raises(PermissionError, match="no valid wallet"):
        await api.wallet_create_invoice_public(
            CreateInvoicePublicRequest(
                source_id="tip-1",
                amount=21,
                currency="sat",
                memo="",
            )
        )
