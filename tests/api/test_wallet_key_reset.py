from uuid import UUID, uuid4

import pytest

from lnbits.core.crud.wallets import (
    clear_wallet_cache,
    create_wallet,
    delete_wallet,
    force_delete_wallet,
    get_wallets,
)
from lnbits.core.db import db
from lnbits.core.models.wallets import (
    BaseWallet,
    BaseWalletTypeInfo,
    KeyType,
    WalletType,
)
from lnbits.helpers import create_access_token
from lnbits.utils.cache import cache

RESET_URL = "/admin/api/v1/wallets/reset-keys"


@pytest.fixture
async def reset_wallets(http_client, from_user, admin_user, settings):
    created = []
    owners = [from_user.id, admin_user.id, settings.super_user]
    for deleted in (False, True):
        for index, wallet_type in enumerate(WalletType):
            wallet = await create_wallet(
                user_id=owners[index % len(owners)],
                wallet_type=wallet_type,
                shared_wallet_id=(
                    created[0].id
                    if wallet_type == WalletType.LIGHTNING_SHARED
                    else None
                ),
            )
            created.append(wallet)
            if deleted:
                await delete_wallet(wallet.user, wallet.id)

    before = await db.fetchall("SELECT * FROM wallets ORDER BY id")
    try:
        yield before, created
    finally:
        # Other API tests retain session-scoped wallet objects and their keys.
        current = await db.fetchall("SELECT * FROM wallets", model=BaseWallet)
        for wallet in current:
            clear_wallet_cache(wallet)
        for row in before:
            await db.execute(
                f"""UPDATE wallets SET adminkey = :adminkey, inkey = :inkey,
                updated_at = {db.timestamp_placeholder('updated_at')}
                WHERE id = :id""",  # noqa: S608
                {key: row[key] for key in ("id", "adminkey", "inkey", "updated_at")},
            )
        for wallet in created:
            await force_delete_wallet(wallet.id)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "auth",
    ["anonymous", "invalid", "user", "admin", "adminkey", "inkey", "superkey"],
)
async def test_bulk_key_reset_requires_superuser(
    http_client,
    auth,
    user_headers_from,
    admin_user,
    from_wallet,
    settings,
    mocker,
):
    reset = mocker.patch(
        "lnbits.core.views.admin_api.reset_all_wallet_keys",
        new_callable=mocker.AsyncMock,
    )
    headers = {}
    if auth == "invalid":
        headers = {"Authorization": "Bearer invalid"}
    elif auth == "user":
        headers = user_headers_from
    elif auth == "admin":
        token = create_access_token({"sub": admin_user.username, "usr": admin_user.id})
        headers = {"Authorization": f"Bearer {token}"}
    elif auth in ("adminkey", "inkey"):
        headers = {"X-Api-Key": getattr(from_wallet, auth)}
    elif auth == "superkey":
        wallets = await get_wallets(settings.super_user)
        headers = {"X-Api-Key": wallets[0].adminkey}

    response = await http_client.post(RESET_URL, headers=headers)
    assert response.status_code == (403 if auth in ("user", "admin") else 401)
    reset.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("token_source", ["header", "cookie"])
async def test_bulk_key_reset_rotates_every_wallet(
    http_client, superuser_token, reset_wallets, settings, token_source
):
    before, created = reset_wallets
    settings.auth_authentication_cache_minutes = 1
    active = created[: len(WalletType)]
    balances = await db.fetchall("SELECT * FROM balances ORDER BY wallet_id")
    for wallet in active:
        for key in (wallet.adminkey, wallet.inkey):
            response = await http_client.get(
                "/api/v1/payments", headers={"X-Api-Key": key}
            )
            assert response.status_code == 200
            assert cache.get(f"auth:x-api-key:{key}") is not None

    headers = {}
    if token_source == "header":
        headers = {"Authorization": f"Bearer {superuser_token}"}
    else:
        http_client.cookies.set("cookie_access_token", superuser_token)
    response = await http_client.post(RESET_URL, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"wallets_updated": len(before)}

    after = await db.fetchall("SELECT * FROM wallets ORDER BY id")
    old_keys = {row[field] for row in before for field in ("adminkey", "inkey")}
    new_keys = {row[field] for row in after for field in ("adminkey", "inkey")}
    assert len(new_keys) == len(after) * 2
    assert old_keys.isdisjoint(new_keys)
    for key in new_keys:
        assert UUID(hex=key).version == 4
        assert len(key) == 32
    for old, new in zip(before, after, strict=True):
        assert {
            k: v for k, v in old.items() if k not in ("adminkey", "inkey", "updated_at")
        } == {
            k: v for k, v in new.items() if k not in ("adminkey", "inkey", "updated_at")
        }
    assert await db.fetchall("SELECT * FROM balances ORDER BY wallet_id") == balances

    for wallet in active:
        assert cache.get(f"auth:wallet:{wallet.id}") is None
        for key in (wallet.adminkey, wallet.inkey):
            assert cache.get(f"auth:x-api-key:{key}") is None
            response = await http_client.get(
                "/api/v1/payments", headers={"X-Api-Key": key}
            )
            assert response.status_code == 404
        new = next(row for row in after if row["id"] == wallet.id)
        for field in ("adminkey", "inkey"):
            response = await http_client.get(
                "/api/v1/payments", headers={"X-Api-Key": new[field]}
            )
            assert response.status_code == 200

    # Restoring a deleted wallet must not restore its compromised keys.
    deleted_wallet = created[len(WalletType)]
    await delete_wallet(deleted_wallet.user, deleted_wallet.id, deleted=False)
    try:
        for key in (deleted_wallet.adminkey, deleted_wallet.inkey):
            response = await http_client.get(
                "/api/v1/wallet", headers={"X-Api-Key": key}
            )
            assert response.status_code == 404
    finally:
        await delete_wallet(deleted_wallet.user, deleted_wallet.id)

    # The superuser session still retrieves fresh wallet credentials.
    response = await http_client.get("/api/v1/auth", headers=headers)
    assert response.status_code == 200
    assert all(wallet["adminkey"] in new_keys for wallet in response.json()["wallets"])


@pytest.mark.anyio
async def test_bulk_key_reset_failure_clears_rotated_wallet_cache(
    http_client, superuser_token, reset_wallets, monkeypatch, mocker
):
    before, _ = reset_wallets
    calls = 0
    error = RuntimeError("database update failed")
    warning = mocker.patch("lnbits.core.views.admin_api.logger.warning")
    for row in before:
        wallet = BaseWallet(**row)
        cache.set(f"auth:wallet:{wallet.id}", wallet, expiry=60)
        for key, key_type in (
            (wallet.adminkey, KeyType.admin),
            (wallet.inkey, KeyType.invoice),
        ):
            cache.set(
                f"auth:x-api-key:{key}", BaseWalletTypeInfo(key_type, wallet), expiry=60
            )

    def fail_after_first_wallet():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise error
        return uuid4()

    with monkeypatch.context() as patch:
        patch.setattr("lnbits.core.crud.wallets.uuid4", fail_after_first_wallet)
        response = await http_client.post(
            RESET_URL, headers={"Authorization": f"Bearer {superuser_token}"}
        )
    assert calls == 3
    assert response.status_code == 500
    assert response.json() == {"detail": "Could not reset wallet keys."}
    warning.assert_called_once_with(error)
    after = await db.fetchall("SELECT * FROM wallets ORDER BY id")
    rotated = []
    for old, new in zip(before, after, strict=True):
        if old["adminkey"] == new["adminkey"]:
            assert new == old
            continue
        rotated.append(old["id"])
        assert old["inkey"] != new["inkey"]
        assert cache.get(f"auth:wallet:{old['id']}") is None
        for field in ("adminkey", "inkey"):
            assert cache.get(f"auth:x-api-key:{old[field]}") is None
    assert len(rotated) == 1
