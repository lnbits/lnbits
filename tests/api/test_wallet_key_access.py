from uuid import uuid4

import jwt
import pytest
from httpx import AsyncClient

from lnbits.core.crud.users import (
    delete_account,
    get_user_access_control_lists,
    update_user_access_control_list,
)
from lnbits.core.crud.wallets import create_wallet, force_delete_wallet, get_wallet
from lnbits.core.models import AccessTokenPayload, User
from lnbits.core.models.misc import SimpleItem
from lnbits.core.models.users import AccessControlList, Account, EndpointAccess
from lnbits.core.services.users import create_user_account
from lnbits.helpers import create_access_token
from lnbits.settings import AuthMethods, Settings


@pytest.fixture
async def wallet_key_user(http_client: AsyncClient):
    account = Account(id=uuid4().hex, username=f"keys_{uuid4().hex[:8]}")
    account.hash_password("secret1234")
    user = await create_user_account(account)
    user.wallets.append(await create_wallet(user_id=user.id, wallet_name="Second"))
    try:
        yield user
    finally:
        for wallet in user.wallets:
            await force_delete_wallet(wallet.id)
        await delete_account(user.id)


@pytest.fixture(
    params=[
        ("/api/v1/wallets", "/api/v1/wallets", None),
        ("/api/v1/wallet/paginated", "/api/v1/wallet", "data"),
        ("/api/v1/auth", "/api/v1/auth", "wallets"),
        ("/users/api/v1/user/{user_id}", "/users/api/v1", "wallets"),
        ("/users/api/v1/user/{user_id}/wallet", "/users/api/v1", None),
    ]
)
def wallet_key_endpoint(request, wallet_key_user: User, settings: Settings):
    path, acl_path, wallet_field = request.param
    if path.startswith("/users/"):
        settings.lnbits_admin_users = [wallet_key_user.id]
    return path.format(user_id=wallet_key_user.id), acl_path, wallet_field


@pytest.mark.anyio
@pytest.mark.parametrize("token_source", ["header", "cookie"])
async def test_wallet_keys_require_current_endpoint_write_access(
    http_client: AsyncClient,
    wallet_key_user: User,
    wallet_key_endpoint: tuple[str, str, str | None],
    token_source: str,
    settings: Settings,
):
    settings.auth_authentication_cache_minutes = 1
    path, acl_path, wallet_field = wallet_key_endpoint
    user = wallet_key_user
    session_token = create_access_token({"sub": user.username, "usr": user.id})
    session_headers = {"Authorization": f"Bearer {session_token}"}
    response = await http_client.get(path, headers=session_headers)
    assert response.status_code == 200
    original = response.json()
    http_client.cookies.set("cookie_access_token", session_token)
    response = await http_client.get(path)
    assert response.status_code == 200
    assert response.json() == original
    http_client.cookies.clear()
    original_wallets = original[wallet_field] if wallet_field else original
    assert len(original_wallets) == 2
    for wallet in original_wallets:
        stored = user.get_wallet(wallet["id"])
        assert stored
        assert wallet["adminkey"] == stored.adminkey
        assert wallet["inkey"] == stored.inkey

    token_id = uuid4().hex
    token = create_access_token(
        AccessTokenPayload(sub=user.username or "", api_token_id=token_id).dict()
    )
    endpoint = EndpointAccess(path=acl_path, name="Wallet response", read=True)
    acl = AccessControlList(
        id=uuid4().hex,
        name="Wallet keys",
        endpoints=[
            endpoint,
            # Write access elsewhere must not grant access to these keys.
            EndpointAccess(path="/api/v1/payments", name="Payments", write=True),
        ],
        token_id_list=[SimpleItem(id=token_id, name="Wallet token")],
    )
    acls = await get_user_access_control_lists(user.id)
    acls.access_control_list = [acl]
    await update_user_access_control_list(acls)

    headers = {}
    if token_source == "header":
        headers = {"Authorization": f"Bearer {token}"}
        # A full session cookie must not override a restricted bearer token.
        http_client.cookies.set("cookie_access_token", session_token)
    else:
        http_client.cookies.set("cookie_access_token", token)

    # A grant followed by a downgrade exercises previously cached authentication.
    for write in (False, True, False):
        endpoint.write = write
        await update_user_access_control_list(acls)
        response = await http_client.get(path, headers=headers)
        assert response.status_code == 200
        result = response.json()
        wallets = result[wallet_field] if wallet_field else result
        assert len(wallets) == 2
        if wallet_field:
            # Updating the ACL also updates the account's updated_at timestamp.
            ignored = {wallet_field, "updated_at"}
            assert {k: v for k, v in result.items() if k not in ignored} == {
                k: v for k, v in original.items() if k not in ignored
            }
        originals = {wallet["id"]: wallet for wallet in original_wallets}
        for wallet in wallets:
            expected = originals[wallet["id"]]
            if not write:
                expected = {
                    **expected,
                    "adminkey": "*" * 32,
                    "inkey": "*" * 32,
                }
            assert wallet == expected

    # Read access is still required even when write access is granted.
    endpoint.read = False
    endpoint.write = True
    await update_user_access_control_list(acls)
    response = await http_client.get(path, headers=headers)
    assert response.status_code == 403

    endpoint.read = True
    acl.delete_token_by_id(token_id)
    await update_user_access_control_list(acls)
    response = await http_client.get(path, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid token id."

    # Redaction must not alter persisted credentials or unrestricted responses.
    http_client.cookies.clear()
    response = await http_client.get(path, headers=session_headers)
    assert response.status_code == 200
    restored = response.json()
    assert (restored[wallet_field] if wallet_field else restored) == original_wallets
    for wallet in user.wallets:
        stored = await get_wallet(wallet.id)
        assert stored
        assert stored.adminkey == wallet.adminkey
        assert stored.inkey == wallet.inkey


@pytest.mark.anyio
async def test_wallet_keys_with_user_id_authentication(
    http_client: AsyncClient,
    wallet_key_user: User,
    settings: Settings,
):
    settings.auth_allowed_methods = [AuthMethods.user_id_only.value]
    for path, wallet_field in (
        ("/api/v1/wallets", None),
        ("/api/v1/wallet/paginated", "data"),
        ("/api/v1/auth", "wallets"),
    ):
        response = await http_client.get(path, params={"usr": wallet_key_user.id})
        assert response.status_code == 200
        result = response.json()
        wallets = result[wallet_field] if wallet_field else result
        assert len(wallets) == 2
        for wallet in wallets:
            stored = wallet_key_user.get_wallet(wallet["id"])
            assert stored
            assert wallet["adminkey"] == stored.adminkey
            assert wallet["inkey"] == stored.inkey


@pytest.mark.anyio
@pytest.mark.parametrize("token", [None, "invalid_token", "expired"])
async def test_wallet_keys_reject_missing_or_invalid_authentication(
    http_client: AsyncClient,
    wallet_key_endpoint: tuple[str, str, str | None],
    token: str | None,
    wallet_key_user: User,
    settings: Settings,
):
    path, _, _ = wallet_key_endpoint
    if token == "expired":
        token = jwt.encode(
            {"sub": wallet_key_user.username, "api_token_id": uuid4().hex, "exp": 0},
            settings.auth_secret_key,
            "HS256",
        )
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = await http_client.get(path, headers=headers)
    assert response.status_code == 401
