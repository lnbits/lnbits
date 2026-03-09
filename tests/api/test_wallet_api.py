from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.models.users import Account
from lnbits.core.services.users import create_user_account


def _admin_headers(adminkey: str) -> dict[str, str]:
    return {"X-Api-Key": adminkey, "Content-type": "application/json"}


@pytest.mark.anyio
async def test_wallet_api_share_invite_reject_accept_and_delete(http_client: AsyncClient):
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
    reset = await http_client.put(f"/api/v1/wallet/reset/{extra_wallet.id}?usr={user.id}")
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
    assert response.json()["detail"] == "Shared wallet ID is required for shared wallets."
