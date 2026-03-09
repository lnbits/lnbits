from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.crud.wallets import create_wallet, get_wallet, get_wallets
from lnbits.core.models import UpdateBalance
from lnbits.core.models.users import Account
from lnbits.core.services.users import create_user_account
from lnbits.core.views.user_api import api_users_create_user_wallet
from lnbits.settings import settings


@pytest.mark.anyio
async def test_user_api_toggle_admin_and_update_balance(
    http_client: AsyncClient, superuser_token: str
):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]

    promote = await http_client.put(
        f"/users/api/v1/user/{user.id}/admin",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert promote.status_code == 200
    assert settings.is_admin_user(user.id) is True

    demote = await http_client.put(
        f"/users/api/v1/user/{user.id}/admin",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert demote.status_code == 200
    assert settings.is_admin_user(user.id) is False

    balance = await http_client.put(
        "/users/api/v1/balance",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json=UpdateBalance(id=wallet.id, amount=7).dict(),
    )
    assert balance.status_code == 200
    assert balance.json()["success"] is True

    updated_wallet = await get_wallet(wallet.id)
    assert updated_wallet is not None
    assert updated_wallet.balance == 7


@pytest.mark.anyio
async def test_user_api_get_wallets_and_delete_all_wallets(
    http_client: AsyncClient, superuser_token: str
):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    extra_wallet = await create_wallet(user_id=user.id, wallet_name="spare")

    wallets = await http_client.get(
        f"/users/api/v1/user/{user.id}/wallet",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert wallets.status_code == 200
    wallet_ids = {wallet["id"] for wallet in wallets.json()}
    assert extra_wallet.id in wallet_ids

    deleted = await http_client.delete(
        f"/users/api/v1/user/{user.id}/wallets",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True

    active_wallets = await get_wallets(user.id, deleted=False)
    assert active_wallets == []


@pytest.mark.anyio
async def test_user_api_create_wallet_validates_currency():
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )

    with pytest.raises(ValueError, match="Currency 'INVALID' not allowed."):
        await api_users_create_user_wallet(user.id, name="invalid", currency="INVALID")

    wallet = await api_users_create_user_wallet(user.id, name="eur wallet", currency="EUR")
    assert wallet.currency == "EUR"
