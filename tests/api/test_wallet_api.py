from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.crud.wallets import create_wallet, get_wallet
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
async def test_wallet_api_creates_fiat_wallet_and_rejects_placeholders(
    http_client: AsyncClient,
):
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
        json={"name": "Euros", "wallet_type": "fiat", "currency": "eur"},
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

    for wallet_type in (WalletType.ONCHAIN, WalletType.LIQUID):
        unavailable = await http_client.post(
            f"/api/v1/wallet?usr={user.id}",
            json={"name": wallet_type.value, "wallet_type": wallet_type.value},
        )
        assert unavailable.status_code == 400
        assert unavailable.json()["detail"] == (
            f"Wallet type '{wallet_type.value}' is not available yet."
        )


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
        InvoiceError, match="Lightning payments cannot be received by a fiat wallet"
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
