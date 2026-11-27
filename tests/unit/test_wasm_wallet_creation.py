import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from lnbits.core.crud.extensions import create_user_extension, get_user_extension
from lnbits.core.crud.wallets import get_wallet, get_wallets_ids
from lnbits.core.models.extensions import UserExtension
from lnbits.core.services.payments import update_wallet_balance
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.wallets.fake import FakeWallet

CREATE = "wallet.create_and_spend"
SPEND = "wallet.pay_invoice_background"


@pytest.fixture
async def assignment(app, from_user):
    entry = UserExtension(
        user=from_user.id, extension=f"orders_{uuid4().hex[:8]}", active=True
    )
    await create_user_extension(entry)
    return entry


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("context", "limit"), [("user", 0), ("schedule", 50), ("websocket", 100)]
)
async def test_create_wallet_adds_standard_spending_grant(
    assignment, context, limit, settings
):
    settings.lnbits_max_outgoing_payment_amount_sats = limit
    api = ExtensionAPIHost(
        ExtensionHostAPI(
            assignment.extension, [CREATE], context=context, user_id=assignment.user
        )
    )
    wallets = await asyncio.gather(
        api.invoke("create-wallet", {"name": "Orders"}), api.invoke("create-wallet")
    )
    wallet = await get_wallet(wallets[0]["walletId"])
    assert wallet and wallet.user == assignment.user and wallet.name == "Orders"
    assert wallet.is_lightning_wallet and set(wallets[0]) == {"walletId"}
    entry = await get_user_extension(assignment.user, assignment.extension)
    assert entry and set(entry.permissions) == {SPEND}
    grants = entry.permissions[SPEND]
    assert {g["wallet_id"] for g in grants} == {w["walletId"] for w in wallets}
    for grant in grants:
        assert grant["enabled"] and grant["destination_policy"] == "external_allowed"
        assert grant["max_amount"] == limit


@pytest.mark.anyio
async def test_created_wallet_uses_normal_invoice_and_payment_permissions(
    assignment, from_wallet, mocker, http_client, user_headers_from
):
    backend = FakeWallet()
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source", return_value=backend
    )
    api = ExtensionAPIHost(
        ExtensionHostAPI(
            assignment.extension,
            [CREATE, SPEND, "wallet.create_invoice"],
            context="schedule",
            user_id=assignment.user,
        )
    )
    wallet_id = (await api.invoke("create-wallet"))["walletId"]
    invoice = await api.invoke(
        "create-invoice",
        {"walletId": wallet_id, "amount": 2, "memo": "", "tag": "orders"},
    )
    assert invoice["paymentRequest"]
    wallet = await get_wallet(wallet_id)
    assert wallet
    await update_wallet_balance(wallet, 100)
    external = await backend.create_invoice(2)
    payment = {"walletId": from_wallet.id, "paymentRequest": external.payment_request}
    denied = await api.invoke("pay-invoice", payment)
    assert not denied["ok"]
    paid = await api.invoke("pay-invoice", {**payment, "walletId": wallet_id})
    assert paid["success"] and paid["paymentHash"] == external.checking_id

    entry = await get_user_extension(assignment.user, assignment.extension)
    assert entry
    (grant,) = entry.permissions[SPEND]
    mocker.patch("lnbits.core.views.extension_api._require_active_wasm_extension")
    response = await http_client.delete(
        f"/api/v1/extension/{assignment.extension}/permissions/user/{grant['id']}",
        headers=user_headers_from,
    )
    assert response.status_code == 200
    denied = await api.invoke("pay-invoice", {**payment, "walletId": wallet_id})
    assert not denied["ok"] and "missing" in denied["error"]


@pytest.mark.anyio
async def test_failed_grant_leaves_wallet(assignment, mocker):
    api = ExtensionAPIHost(
        ExtensionHostAPI(assignment.extension, [CREATE], user_id=assignment.user)
    )
    before = await get_wallets_ids(assignment.user)
    mocker.patch(
        "lnbits.core.crud.extensions.update_user_extension",
        side_effect=RuntimeError("grant write failed"),
    )
    with pytest.raises(RuntimeError, match="grant write failed"):
        await api.invoke("create-wallet")
    assert len(await get_wallets_ids(assignment.user)) == len(before) + 1
    entry = await get_user_extension(assignment.user, assignment.extension)
    assert entry and not entry.permissions


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("context", "user", "permissions"),
    [
        ("user", "alice", [SPEND]),
        ("event", "alice", [CREATE]),
        ("schedule", None, [CREATE]),
        ("websocket", None, [CREATE]),
        ("user", None, [CREATE]),
    ],
)
async def test_create_wallet_requires_permission_and_user_context(
    context, user, permissions
):
    api = ExtensionAPIHost(
        ExtensionHostAPI("orders", permissions, context=context, user_id=user)
    )
    with pytest.raises(PermissionError):
        await api.invoke("create-wallet")


@pytest.mark.anyio
async def test_create_wallet_rejects_supplied_user():
    api = ExtensionAPIHost(ExtensionHostAPI("orders", [CREATE], user_id="alice"))
    with pytest.raises(ValidationError):
        await api.invoke("create-wallet", {"userId": "someone-else"})
