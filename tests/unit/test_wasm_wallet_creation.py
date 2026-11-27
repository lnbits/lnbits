import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from lnbits.core.crud.extensions import (
    create_user_extension,
    get_user_extension,
    update_user_extension_state,
)
from lnbits.core.crud.wallets import create_wallet, get_wallet, get_wallets_ids
from lnbits.core.models.extensions import (
    ExtensionPermission,
    InstallableExtension,
    UserExtension,
)
from lnbits.core.services.payments import update_wallet_balance
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.helpers import sha256s
from lnbits.wallets.fake import FakeWallet

PERMISSION = "wallet.create_and_spend"
BACKGROUND = "wallet.pay_invoice_background"


@pytest.fixture
async def assignment(app, from_user):
    entry = UserExtension(
        user=from_user.id, extension=f"orders_{uuid4().hex[:8]}", active=True
    )
    await create_user_extension(entry)
    return entry


@pytest.mark.anyio
@pytest.mark.parametrize("context", ["user", "schedule", "websocket"])
async def test_create_wallet_invoice_and_pay(assignment, mocker, context, settings):
    backend = FakeWallet()
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source", return_value=backend
    )
    api = ExtensionAPIHost(
        ExtensionHostAPI(
            assignment.extension, [PERMISSION], context=context, user_id=assignment.user
        )
    )
    created = await api.invoke("create-wallet", {"name": "Orders"})
    assert set(created) == {"walletId"}
    wallet = await get_wallet(created["walletId"])
    assert wallet and wallet.user == assignment.user
    assert wallet.created_by_extension == assignment.extension
    assert wallet.name == "Orders" and wallet.is_lightning_wallet
    entry = await get_user_extension(assignment.user, assignment.extension)
    assert entry
    (grant,) = entry.permissions[BACKGROUND]
    assert grant["wallet_id"] == wallet.id and grant["enabled"]
    assert grant["destination_policy"] == "external_allowed"
    assert grant["max_amount"] == settings.lnbits_max_outgoing_payment_amount_sats

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
async def test_created_wallet_grant_can_be_limited_and_revoked(
    assignment, http_client, user_headers_from, mocker
):
    installed = InstallableExtension(
        id=assignment.extension,
        name="Orders",
        version="1.0",
        active=True,
        permissions=[ExtensionPermission(id=PERMISSION)],
    )
    mocker.patch(
        "lnbits.core.views.extension_api._require_active_wasm_extension",
        return_value=installed,
    )
    mocker.patch(
        "lnbits.core.views.extension_api.get_installed_extension",
        return_value=installed,
    )
    api = ExtensionAPIHost(
        ExtensionHostAPI(installed.id, [PERMISSION], user_id=assignment.user)
    )
    wallets = await asyncio.gather(
        api.invoke("create-wallet"), api.invoke("create-wallet")
    )
    url = f"/api/v1/extension/{installed.id}/permissions"
    response = await http_client.get(url, headers=user_headers_from)
    assert response.status_code == 200
    grants = response.json()["user_permissions"][BACKGROUND]
    assert {g["wallet_id"] for g in grants} == {w["walletId"] for w in wallets}
    grant = grants[0]
    change = {
        "wallet_id": grant["wallet_id"],
        "max_amount": 1,
        "destination_policy": "external_allowed",
    }
    response = await http_client.post(
        url + "/background-payment", json=change, headers=user_headers_from
    )
    assert response.status_code == 200
    assert response.json()["grant"]["id"] == grant["id"]
    response = await http_client.post(
        url + "/check",
        json={"permissions": [{"id": BACKGROUND, "grant": change}]},
        headers=user_headers_from,
    )
    assert response.status_code == 200 and response.json()["permissions"][0]["approved"]
    stale_entry = await get_user_extension(assignment.user, installed.id)
    assert stale_entry
    external = await FakeWallet().create_invoice(2)
    payment = {
        "walletId": grant["wallet_id"],
        "paymentRequest": external.payment_request,
    }
    denied = await api.invoke("pay-invoice", payment)
    assert not denied["ok"] and "exceeds max amount" in denied["error"]
    response = await http_client.delete(
        url + "/user/" + grant["id"], headers=user_headers_from
    )
    assert response.status_code == 200
    await update_user_extension_state(stale_entry)
    denied = await api.invoke("pay-invoice", payment)
    assert not denied["ok"] and "missing wallet background grant" in denied["error"]
    ordinary = await create_wallet(user_id=assignment.user)
    response = await http_client.post(
        url + "/background-payment",
        json={**change, "wallet_id": ordinary.id},
        headers=user_headers_from,
    )
    assert response.status_code == 403
    invoice = await api.invoke(
        "create-invoice",
        {"walletId": grant["wallet_id"], "amount": 2, "memo": "", "tag": installed.id},
    )
    assert invoice["paymentRequest"]


@pytest.mark.anyio
async def test_wallet_creation_rolls_back_if_grant_write_fails(assignment, mocker):
    before = await get_wallets_ids(assignment.user)
    api = ExtensionAPIHost(
        ExtensionHostAPI(assignment.extension, [PERMISSION], user_id=assignment.user)
    )
    mocker.patch(
        "lnbits.core.crud.extensions.update_user_extension",
        side_effect=RuntimeError("grant write failed"),
    )
    with pytest.raises(RuntimeError, match="grant write failed"):
        await api.invoke("create-wallet")
    assert await get_wallets_ids(assignment.user) == before


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
