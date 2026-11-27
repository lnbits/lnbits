import pytest
from pydantic import ValidationError

from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.services.payments import update_wallet_balance
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.helpers import sha256s
from lnbits.wallets.fake import FakeWallet

PERMISSION = "wallet.create_and_spend"


@pytest.mark.anyio
@pytest.mark.parametrize("context", ["user", "schedule", "websocket"])
async def test_create_wallet_invoice_and_pay(app, from_user, mocker, context):
    backend = FakeWallet()
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source", return_value=backend
    )
    api = ExtensionAPIHost(
        ExtensionHostAPI("orders", [PERMISSION], context=context, user_id=from_user.id)
    )
    created = await api.invoke("create-wallet", {"name": "Orders"})
    assert set(created) == {"walletId"}
    wallet = await get_wallet(created["walletId"])
    assert wallet and wallet.user == from_user.id
    assert wallet.created_by_extension == "orders"
    assert wallet.name == "Orders" and wallet.is_lightning_wallet

    invoice = await api.invoke(
        "create-invoice",
        {"walletId": wallet.id, "amount": 21, "memo": "Order", "tag": "orders"},
    )
    assert invoice["paymentRequest"]
    await update_wallet_balance(wallet, 1000)
    # A backend invoice with no receiving wallet in LNbits takes the external path.
    external = await backend.create_invoice(21, memo="External")
    assert external.payment_request
    paid = await api.invoke(
        "pay-invoice",
        {"walletId": wallet.id, "paymentRequest": external.payment_request},
    )
    assert paid["ok"] and paid["success"]
    assert paid["paymentHash"] == external.checking_id


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("context", "user_id", "permissions"),
    [
        ("user", "alice", ["wallet.pay_invoice", "wallet.create_invoice"]),
        ("user", None, [PERMISSION]),
        ("event", None, [PERMISSION]),
        ("event", "alice", [PERMISSION]),
        ("schedule", None, [PERMISSION]),
        ("websocket", None, [PERMISSION]),
    ],
)
async def test_create_wallet_requires_grant_and_user_context(
    mocker, context, user_id, permissions
):
    create = mocker.patch("lnbits.core.crud.wallets.create_wallet")
    api = ExtensionAPIHost(
        ExtensionHostAPI(
            "orders",
            permissions,
            context=context,
            user_id=user_id,
            owner_id=sha256s("alice"),
        )
    )
    with pytest.raises(PermissionError):
        await api.invoke("create-wallet", {})
    create.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["userId", "createdByExtension", "walletType"])
async def test_create_wallet_rejects_caller_supplied_identity_or_type(mocker, field):
    create = mocker.patch("lnbits.core.crud.wallets.create_wallet")
    api = ExtensionAPIHost(ExtensionHostAPI("orders", [PERMISSION], user_id="alice"))
    with pytest.raises(ValidationError):
        await api.invoke("create-wallet", {field: "other"})
    create.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("extension", "user", "permissions", "context", "use_created_wallet"),
    [
        ("orders", "alice", [PERMISSION], "user", False),
        ("other", "alice", [PERMISSION], "schedule", True),
        ("orders", "bob", [PERMISSION], "websocket", True),
        ("orders", "alice", [], "user", True),
        ("orders", None, [PERMISSION], "event", True),
    ],
)
async def test_automatic_wallet_access_is_scoped(
    app, from_wallet, mocker, extension, user, permissions, context, use_created_wallet
):
    wallet = (
        await create_wallet(user_id=from_wallet.user, created_by_extension="orders")
        if use_created_wallet
        else from_wallet
    )
    user_id = from_wallet.user if user == "alice" else user
    api = ExtensionAPIHost(
        ExtensionHostAPI(
            extension,
            permissions,
            user_id=user_id,
            context=context,
            owner_id=sha256s(from_wallet.user),
        )
    )
    invoice = mocker.patch("lnbits.core.services.payments.create_payment_request")
    pay = mocker.patch("lnbits.core.services.payments.pay_invoice")
    with pytest.raises(PermissionError):
        await api.invoke(
            "create-invoice",
            {"walletId": wallet.id, "amount": 1, "memo": "", "tag": extension},
        )
    if user == "bob":
        with pytest.raises(PermissionError):
            await api.invoke(
                "pay-invoice", {"walletId": wallet.id, "paymentRequest": "unused"}
            )
    else:
        result = await api.invoke(
            "pay-invoice", {"walletId": wallet.id, "paymentRequest": "unused"}
        )
        assert not result["ok"]
    invoice.assert_not_awaited()
    pay.assert_not_awaited()
