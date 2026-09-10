from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.crud.payments import create_payment
from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.models import CreatePayment, PaymentState
from lnbits.core.models.users import Account
from lnbits.core.models.wallet_types import WalletType
from lnbits.core.services import update_wallet_balance
from lnbits.core.services.payments import create_invoice, pay_invoice
from lnbits.core.services.users import create_user_account
from lnbits.exceptions import InvoiceError, PaymentError
from lnbits.settings import settings


@pytest.mark.anyio
async def test_wallet_api_share_invite_reject_accept_and_delete(
    http_client: AsyncClient,
):
    owner = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"owner_{uuid4().hex[:8]}",
            email=f"owner_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    invited = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"invited_{uuid4().hex[:8]}",
            email=f"invited_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    source_wallet = owner.wallets[0]
    owner_headers = _admin_headers(source_wallet.adminkey)

    invite = await http_client.put(
        "/api/v1/wallet/share/invite",
        headers=owner_headers,
        json={
            "username": invited.username,
            "permissions": ["view-payments"],
            "status": "invite_sent",
        },
    )
    assert invite.status_code == 200
    share_request = invite.json()
    assert share_request["request_id"]

    reject = await http_client.delete(
        f"/api/v1/wallet/share/invite/{share_request['request_id']}?usr={invited.id}"
    )
    assert reject.status_code == 200
    assert reject.json()["success"] is True

    removed_share = await http_client.delete(
        f"/api/v1/wallet/share/{share_request['request_id']}",
        headers=owner_headers,
    )
    assert removed_share.status_code == 200
    assert removed_share.json()["success"] is True

    invite = await http_client.put(
        "/api/v1/wallet/share/invite",
        headers=owner_headers,
        json={
            "username": invited.username,
            "permissions": ["view-payments", "receive-payments"],
            "status": "invite_sent",
        },
    )
    assert invite.status_code == 200
    share_request = invite.json()

    create_shared = await http_client.post(
        f"/api/v1/wallet?usr={invited.id}",
        json={
            "name": "shared",
            "wallet_type": "lightning-shared",
            "shared_wallet_id": source_wallet.id,
        },
    )
    assert create_shared.status_code == 200
    mirror_wallet = create_shared.json()
    assert mirror_wallet["shared_wallet_id"] == source_wallet.id

    approve = await http_client.put(
        "/api/v1/wallet/share",
        headers=owner_headers,
        json={
            "username": invited.username,
            "shared_with_wallet_id": mirror_wallet["id"],
            "permissions": ["view-payments", "receive-payments"],
            "status": "approved",
        },
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    delete_share = await http_client.delete(
        f"/api/v1/wallet/share/{share_request['request_id']}",
        headers=owner_headers,
    )
    assert delete_share.status_code == 200
    assert delete_share.json()["success"] is True
    assert await get_wallet(mirror_wallet["id"]) is None


@pytest.mark.anyio
async def test_wallet_api_paginated_update_reset_and_store_paylinks(
    http_client: AsyncClient,
):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    extra_wallet = await create_wallet(user_id=user.id, wallet_name="second")
    first_wallet = user.wallets[0]

    page = await http_client.get(f"/api/v1/wallet/paginated?usr={user.id}&limit=10")
    assert page.status_code == 200
    assert page.json()["total"] >= 2

    renamed = await http_client.put(
        "/api/v1/wallet/renamed-wallet",
        headers=_admin_headers(first_wallet.adminkey),
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "renamed-wallet"

    original_admin_key = extra_wallet.adminkey
    reset = await http_client.put(
        f"/api/v1/wallet/reset/{extra_wallet.id}?usr={user.id}"
    )
    assert reset.status_code == 200
    assert reset.json()["adminkey"] != original_admin_key

    stored = await http_client.put(
        f"/api/v1/wallet/stored_paylinks/{extra_wallet.id}",
        headers=_admin_headers(reset.json()["adminkey"]),
        json={
            "links": [
                {
                    "lnurl": "alice@example.com",
                    "label": "Alice",
                }
            ]
        },
    )
    assert stored.status_code == 200
    assert stored.json()[0]["lnurl"] == "alice@example.com"

    forbidden = await http_client.put(
        f"/api/v1/wallet/stored_paylinks/{extra_wallet.id}",
        headers=_admin_headers(first_wallet.adminkey),
        json={"links": []},
    )
    assert forbidden.status_code == 403

    updated = await http_client.patch(
        "/api/v1/wallet",
        headers=_admin_headers(first_wallet.adminkey),
        json={"icon": "bolt", "color": "amber", "pinned": True},
    )
    assert updated.status_code == 200
    assert updated.json()["extra"]["icon"] == "bolt"
    assert updated.json()["extra"]["color"] == "amber"
    assert updated.json()["extra"]["pinned"] is True


@pytest.mark.anyio
async def test_wallet_api_custom_lightning_address_owner_rules(
    http_client: AsyncClient,
):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]
    headers = _admin_headers(wallet.adminkey)

    settings.lnbits_ln_address_mode = "core_first"
    settings.lnbits_allow_custom_wallet_lightning_addresses = False
    disabled = await http_client.patch(
        "/api/v1/wallet",
        headers=headers,
        json={"lightning_address": "custom.name"},
    )
    assert disabled.status_code == 403

    settings.lnbits_allow_custom_wallet_lightning_addresses = True
    settings.lnbits_wallet_lightning_address_blacklist = ["admin"]
    blacklisted = await http_client.patch(
        "/api/v1/wallet",
        headers=headers,
        json={"lightning_address": "admin"},
    )
    assert blacklisted.status_code == 400

    invalid = await http_client.patch(
        "/api/v1/wallet",
        headers=headers,
        json={"lightning_address": "custom+tag"},
    )
    assert invalid.status_code == 400

    existing_wallet = await create_wallet(
        user_id=user.id,
        wallet_name="existing lightning address",
    )
    existing = await http_client.patch(
        "/api/v1/wallet",
        headers=_admin_headers(existing_wallet.adminkey),
        json={"lightning_address": "pay.link"},
    )
    assert existing.status_code == 200

    conflict = await http_client.patch(
        "/api/v1/wallet",
        headers=headers,
        json={"lightning_address": "pay.link"},
    )
    assert conflict.status_code == 400

    updated = await http_client.patch(
        "/api/v1/wallet",
        headers=headers,
        json={"lightning_address": "custom.name"},
    )
    assert updated.status_code == 200
    assert updated.json()["lightning_address"] == "custom.name"


@pytest.mark.anyio
async def test_wallet_api_custom_lightning_address_charges_fee(
    http_client: AsyncClient,
):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    fee_user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"fees_{uuid4().hex[:8]}",
            email=f"fees_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]
    fee_wallet = fee_user.wallets[0]
    await update_wallet_balance(wallet=wallet, amount=2_000)

    settings.lnbits_ln_address_mode = "core_first"
    settings.lnbits_allow_custom_wallet_lightning_addresses = True
    settings.lnbits_charge_wallet_lightning_addresses = True
    settings.lnbits_wallet_lightning_address_price_sats = 1_000
    settings.lnbits_service_fee_wallet = fee_wallet.id

    updated = await http_client.patch(
        "/api/v1/wallet",
        headers=_admin_headers(wallet.adminkey),
        json={"lightning_address": "paid.name"},
    )
    assert updated.status_code == 200
    assert updated.json()["lightning_address"] == "paid.name"

    charged_wallet = await get_wallet(wallet.id)
    credited_wallet = await get_wallet(fee_wallet.id)
    assert charged_wallet
    assert credited_wallet
    assert charged_wallet.balance == 1_000
    assert credited_wallet.balance == 1_000

    settings.lnbits_service_fee_wallet = None
    missing_fee_wallet = await http_client.patch(
        "/api/v1/wallet",
        headers=_admin_headers(wallet.adminkey),
        json={"lightning_address": "paid.other"},
    )
    assert missing_fee_wallet.status_code == 400
    assert missing_fee_wallet.json()["detail"] == (
        "Lightning Address fee wallet is not configured."
    )


@pytest.mark.anyio
async def test_wallet_api_shared_wallet_requires_source_id(http_client: AsyncClient):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )

    response = await http_client.post(
        f"/api/v1/wallet?usr={user.id}",
        json={"wallet_type": "lightning-shared"},
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"] == "Shared wallet ID is required for shared wallets."
    )


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["receive-only", "fiat"])
async def test_wallet_api_creates_fiat_wallet_and_rejects_placeholders(
    http_client: AsyncClient,
    wallet_type: str,
):
    settings.lnbits_allow_fiat_wallets = True
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"typed_{uuid4().hex[:8]}",
            email=f"typed_{uuid4().hex[:8]}@lnbits.com",
        )
    )

    default_response = await http_client.post(
        f"/api/v1/wallet?usr={user.id}",
        json={"name": "Default Lightning"},
    )
    assert default_response.status_code == 200
    assert default_response.json()["wallet_type"] == WalletType.LIGHTNING.value

    response = await http_client.post(
        f"/api/v1/wallet?usr={user.id}",
        json={"name": "Euros", "wallet_type": wallet_type, "currency": "eur"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["wallet_type"] == WalletType.FIAT.value
    assert data["currency"] == "EUR"
    assert data["lightning_address"] is None
    assert data["extra"]["icon"] == "credit_card"

    wallet = await get_wallet(data["id"])
    assert wallet
    assert wallet.can_receive_payments is True
    assert wallet.can_send_payments is False
    await update_wallet_balance(wallet, 10)
    with pytest.raises(
        ValueError, match="Wallet does not have permission to spend funds"
    ):
        await update_wallet_balance(wallet, -1)

    for placeholder_type in (WalletType.ONCHAIN, WalletType.LIQUID):
        unavailable = await http_client.post(
            f"/api/v1/wallet?usr={user.id}",
            json={
                "name": placeholder_type.value,
                "wallet_type": placeholder_type.value,
            },
        )
        assert unavailable.status_code == 400
        assert unavailable.json()["detail"] == (
            f"Wallet type '{placeholder_type.value}' is not available yet."
        )


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["receive-only", "fiat"])
@pytest.mark.parametrize(
    "enabled,provider_enabled,provider_allowed,expected_status",
    [
        (False, False, True, 400),
        (True, False, True, 200),
        (False, True, True, 200),
        (True, True, True, 200),
        (False, True, False, 400),
        (True, True, False, 200),
    ],
)
async def test_fiat_wallet_availability(
    http_client: AsyncClient,
    wallet_type: str,
    enabled: bool,
    provider_enabled: bool,
    provider_allowed: bool,
    expected_status: int,
):
    user = await create_user_account()
    settings.lnbits_allow_fiat_wallets = enabled
    settings.stripe_enabled = provider_enabled
    settings.paypal_enabled = False
    settings.square_enabled = False
    settings.revolut_enabled = False
    settings.stripe_limits.allowed_users = [] if provider_allowed else [uuid4().hex]

    response = await http_client.post(
        f"/api/v1/wallet?usr={user.id}",
        json={"name": "Receive only", "wallet_type": wallet_type},
    )
    assert response.status_code == expected_status
    assert settings.to_public().allow_fiat_wallets is enabled
    if expected_status == 400:
        assert response.json()["detail"] == (
            "Fiat wallets are not enabled for this account."
        )
    else:
        wallet = await get_wallet(response.json()["id"])
        assert wallet
        # Turning creation off does not change an existing wallet's permissions.
        settings.lnbits_allow_fiat_wallets = False
        settings.stripe_enabled = False
        assert wallet.can_receive_payments
        assert not wallet.can_send_payments


@pytest.mark.anyio
@pytest.mark.parametrize("provider_enabled", [False, True])
async def test_superuser_can_create_fiat_wallet_without_enabling_user_access(
    http_client: AsyncClient, superuser_token: str, provider_enabled: bool
):
    settings.lnbits_allow_fiat_wallets = False
    settings.stripe_enabled = provider_enabled
    settings.paypal_enabled = False
    settings.square_enabled = False
    settings.revolut_enabled = False
    settings.stripe_limits.allowed_users = [uuid4().hex]

    response = await http_client.post(
        "/api/v1/wallet",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"name": "Superuser cash", "wallet_type": "fiat", "currency": "USD"},
    )
    assert response.status_code == 200
    wallet = await get_wallet(response.json()["id"])
    assert wallet and wallet.is_fiat_wallet
    assert not wallet.can_send_payments
    assert not settings.lnbits_allow_fiat_wallets

    if provider_enabled:
        invoice = await http_client.post(
            "/api/v1/payments",
            headers={"X-Api-Key": wallet.adminkey},
            json={"out": False, "amount": 5, "unit": "USD", "fiat_provider": "stripe"},
        )
        assert invoice.status_code == 400
        assert "not available for this user" in invoice.text


@pytest.mark.anyio
@pytest.mark.parametrize("wallet_type", ["fiat", "receive-only"])
@pytest.mark.parametrize("has_receipt", [False, True])
async def test_fiat_wallet_currency_is_fixed_at_creation(
    http_client: AsyncClient, wallet_type: str, has_receipt: bool
):
    from lnbits.core.db import db

    user = await create_user_account()
    wallet = await create_wallet(
        user_id=user.id,
        wallet_type=WalletType.FIAT,
        currency="GBP",
        wallet_name="Original",
    )
    if wallet_type == "receive-only":
        await db.execute(
            "UPDATE wallets SET wallet_type = :type WHERE id = :id",
            {"type": wallet_type, "id": wallet.id},
        )
    if has_receipt:
        await create_payment(
            checking_id=f"internal_cash_{uuid4().hex}",
            data=CreatePayment(
                wallet_id=wallet.id,
                payment_hash=uuid4().hex,
                bolt11="",
                amount_msat=1000,
                memo="GBP receipt",
                extra={"wallet_fiat_currency": "GBP", "wallet_fiat_amount": "5"},
            ),
            status=PaymentState.SUCCESS,
        )

    headers = _admin_headers(wallet.adminkey)
    for currency in ("USD", "", "invalid"):
        response = await http_client.patch(
            "/api/v1/wallet",
            headers=headers,
            json={"currency": currency, "name": "Rejected change"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Fiat wallet currency cannot be changed after creation."
        )
        stored = await get_wallet(wallet.id)
        assert stored and stored.currency == "GBP" and stored.name == "Original"

    # Omitting currency, explicit null, or the unchanged currency must still allow
    # ordinary settings updates, including requests that send the whole form.
    for fields in ({}, {"currency": None}, {"currency": "GBP"}):
        response = await http_client.patch(
            "/api/v1/wallet",
            headers=headers,
            json={**fields, "name": "Renamed", "icon": "payments", "pinned": True},
        )
        assert response.status_code == 200
        assert response.json()["currency"] == "GBP"
        stored = await get_wallet(wallet.id)
        assert stored and stored.currency == "GBP" and stored.name == "Renamed"
        assert stored.extra.icon == "payments" and stored.extra.pinned


@pytest.mark.anyio
async def test_lightning_wallet_accounting_currency_remains_editable(
    http_client: AsyncClient,
):
    user = await create_user_account()
    wallet = user.wallets[0]
    for currency in ("GBP", "USD", ""):
        response = await http_client.patch(
            "/api/v1/wallet",
            headers=_admin_headers(wallet.adminkey),
            json={"currency": currency},
        )
        assert response.status_code == 200
        stored = await get_wallet(wallet.id)
        assert stored and stored.currency == currency


@pytest.mark.anyio
async def test_development_wallet_alias_remains_fiat():
    from lnbits.core.db import db

    user = await create_user_account()
    wallet = await create_wallet(user_id=user.id, wallet_type=WalletType.FIAT)
    await db.execute(
        "UPDATE wallets SET wallet_type = 'receive-only' WHERE id = :id",
        {"id": wallet.id},
    )

    restored = await get_wallet(wallet.id)
    assert restored
    assert restored.wallet_type == "fiat"
    assert restored.is_fiat_wallet
    assert restored.is_receive_only_wallet
    assert restored.can_receive_payments
    assert not restored.can_send_payments


@pytest.mark.anyio
async def test_wallet_payment_types_are_isolated():
    user = await create_user_account()
    lightning_wallet = user.wallets[0]
    fiat_wallet = await create_wallet(
        user_id=user.id, wallet_type=WalletType.FIAT, currency="USD"
    )

    with pytest.raises(
        InvoiceError, match="Fiat payments cannot be received by a lightning wallet"
    ):
        await create_invoice(
            wallet_id=lightning_wallet.id,
            amount=1,
            currency="USD",
            memo="fiat",
            internal=True,
            fiat_provider="stripe",
        )

    with pytest.raises(
        InvoiceError,
        match="Lightning payments cannot be received by a fiat wallet",
    ):
        await create_invoice(
            wallet_id=fiat_wallet.id,
            amount=1,
            memo="lightning",
            internal=True,
        )

    lightning_invoice = await create_invoice(
        wallet_id=lightning_wallet.id,
        amount=1,
        memo="lightning",
        internal=True,
    )
    with pytest.raises(
        PaymentError, match="Wallet does not have permission to pay invoices"
    ):
        await pay_invoice(
            wallet_id=fiat_wallet.id,
            payment_request=lightning_invoice.bolt11,
        )


def _admin_headers(adminkey: str) -> dict[str, str]:
    return {"X-Api-Key": adminkey, "Content-type": "application/json"}
