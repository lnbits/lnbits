import base64
import json
import os
import time
from uuid import uuid4

import jwt
import pytest
import secp256k1
import shortuuid
from httpx import AsyncClient

from lnbits.core.crud.users import (
    get_user_access_control_lists,
    update_user_access_control_list,
)
from lnbits.core.models import AccessTokenPayload, User
from lnbits.core.models.misc import SimpleItem
from lnbits.core.models.users import (
    AccessControlList,
    Account,
    ApiTokenRequest,
    DeleteTokenRequest,
    EndpointAccess,
    LoginUsr,
    UpdateAccessControlList,
    UserAcls,
)
from lnbits.core.services.users import create_user_account
from lnbits.core.views.user_api import api_users_reset_password
from lnbits.helpers import create_access_token
from lnbits.settings import AuthMethods, Settings
from lnbits.utils.nostr import hex_to_npub, sign_event

nostr_event = {
    "kind": 27235,
    "tags": [["u", "http://localhost:5000/nostr"], ["method", "POST"]],
    "created_at": 1727681048,
    "content": "",
    "pubkey": "f6e80df16fa27f1f2774af0ac61b096f8f63ce9116f0a954fca1e25baee84ba9",
    "id": "0fd22355fe63043116fdfceb77be6bf22686aacd16b9e99a10fea6e55ae3f589",
    "sig": "fb7eb47fa8355747f6837e55620103d73ba47b2c3164ab8319d2f164022a9f25"
    "6e00ecda7d3c8945f07b7d6ecc18cfff34c07bc99677309e2b9310d9fc1bb138",
}
private_key = secp256k1.PrivateKey(
    bytes.fromhex("6e00ecda7d3c8945f07b7d6ecc18cfff34c07bc99677309e2b9310d9fc1bb138")
)
assert private_key.pubkey, "Pubkey not created."
pubkey_hex = private_key.pubkey.serialize().hex()[2:]


################################ LOGIN ################################
@pytest.mark.anyio
async def test_login_bad_user(http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": "non_existing_user", "password": "secret1234"}
    )

    assert response.status_code == 401, "User does not exist"
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.anyio
async def test_login_alan_usr(user_alan: User, http_client: AsyncClient):
    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None, "Expected access token after login."

    response = await http_client.get(
        "/api/v1/auth", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 200, "Alan logs in OK."
    alan = response.json()
    assert alan["id"] == user_alan.id
    assert alan["username"] == user_alan.username
    assert alan["email"] == user_alan.email


@pytest.mark.anyio
async def test_login_usr_not_allowed_for_admin_without_credentials(
    http_client: AsyncClient, settings: Settings
):
    # Register a new user
    account = Account(id=uuid4().hex)
    await create_user_account(account)

    # Login with user ID
    login_data = LoginUsr(usr=account.id)
    response = await http_client.post("/api/v1/auth/usr", json=login_data.dict())
    http_client.cookies.clear()
    assert response.status_code == 200, "User logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None, "Expected access token after login."
    headers = {"Authorization": f"Bearer {access_token}"}

    # Simulate the user being an admin without credentials
    settings.lnbits_admin_users = [account.id]

    # Attempt to login with user ID for admin
    response = await http_client.post("/api/v1/auth/usr", json=login_data.dict())

    assert response.status_code == 403
    assert (
        response.json().get("detail") == "Admin users cannot login with user id only."
    )

    response = await http_client.get("/admin/api/v1/settings", headers=headers)
    assert response.status_code == 403
    assert (
        response.json().get("detail") == "Admin users must have credentials configured."
    )

    # User only access should not be allowed
    response = await http_client.get(
        f"/admin/api/v1/settings?usr={settings.super_user}"
    )
    assert response.status_code == 403
    assert (
        response.json().get("detail") == "User id only access for admins is forbidden."
    )

    response = await http_client.get("/api/v1/status", headers=headers)
    assert response.status_code == 200, "Admin user can access regular endpoints."


@pytest.mark.anyio
async def test_login_usr_not_allowed(
    user_alan: User, http_client: AsyncClient, settings: Settings
):
    # exclude 'user_id_only'
    settings.auth_allowed_methods = [AuthMethods.username_and_password.value]

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 403, "Login method not allowed."
    assert response.json().get("detail") == "Login by 'User ID' not allowed."

    settings.auth_allowed_methods = AuthMethods.all()

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})
    assert response.status_code == 200, "Login with 'usr' allowed."
    assert (
        response.json().get("access_token") is not None
    ), "Expected access token after login."


@pytest.mark.anyio
async def test_login_alan_username_password_ok(
    user_alan: User, http_client: AsyncClient, settings: Settings
):
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )

    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None

    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    access_token_payload = AccessTokenPayload(**payload)

    assert access_token_payload.sub == "alan", "Subject is Alan."
    assert access_token_payload.email == "alan@lnbits.com"
    assert access_token_payload.auth_time, "Auth time should be set by server."
    assert (
        0 <= time.time() - access_token_payload.auth_time <= 5
    ), "Auth time should be very close to now()."

    response = await http_client.get(
        "/api/v1/auth", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200, "User exits."
    user = User(**response.json())
    assert user.username == "alan", "Username check."
    assert user.email == "alan@lnbits.com", "Email check."
    assert not user.pubkey, "No pubkey."
    assert not user.admin, "Not admin."
    assert not user.super_user, "Not superuser."
    assert user.has_password, "Password configured."
    assert (
        len(user.wallets) == 1
    ), f"Expected 1 default wallet, not {len(user.wallets)}."


@pytest.mark.anyio
async def test_login_alan_email_password_ok(user_alan: User, http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.email, "password": "secret1234"}
    )

    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None


@pytest.mark.anyio
async def test_login_alan_password_nok(user_alan: User, http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "bad_pasword"}
    )

    assert response.status_code == 401, "User does not exist"
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.anyio
async def test_login_username_password_not_allowed(
    user_alan: User, http_client: AsyncClient, settings: Settings
):
    # exclude 'username_password'
    settings.auth_allowed_methods = [AuthMethods.user_id_only.value]

    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )

    assert response.status_code == 403, "Login method not allowed."
    assert (
        response.json().get("detail") == "Login by 'Username and Password' not allowed."
    )

    settings.auth_allowed_methods = AuthMethods.all()

    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )
    assert response.status_code == 200, "Username and password is allowed."
    assert response.json().get("access_token") is not None


@pytest.mark.anyio
async def test_login_alan_change_auth_secret_key(
    user_alan: User, http_client: AsyncClient, settings: Settings
):
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )

    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None

    initial_auth_secret_key = settings.auth_secret_key

    settings.auth_secret_key = shortuuid.uuid()

    response = await http_client.get(
        "/api/v1/auth", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 401, "Access token not valid anymore."
    assert response.json().get("detail") == "Invalid access token."

    settings.auth_secret_key = initial_auth_secret_key

    response = await http_client.get(
        "/api/v1/auth", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200, "Access token valid again."


################################ REGISTER WITH PASSWORD ################################
@pytest.mark.anyio
async def test_register_ok(http_client: AsyncClient):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    access_token = response.json().get("access_token")
    assert response.status_code == 200, "User created."
    assert response.json().get("access_token") is not None

    response = await http_client.get(
        "/api/v1/auth", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200, "User exits."
    user = User(**response.json())
    assert user.username == f"u21.{tiny_id}", "Username check."
    assert user.email == f"u21.{tiny_id}@lnbits.com", "Email check."
    assert not user.pubkey, "No pubkey check."
    assert not user.admin, "Not admin."
    assert not user.super_user, "Not superuser."
    assert user.has_password, "Password configured."
    assert (
        len(user.wallets) == 1
    ), f"Expected 1 default wallet, not {len(user.wallets)}."


@pytest.mark.anyio
async def test_register_email_twice(http_client: AsyncClient):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    assert response.json().get("access_token") is not None

    tiny_id_2 = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id_2}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 400, "Not allowed."
    assert response.json().get("detail") == "Email already exists."


@pytest.mark.anyio
async def test_register_username_twice(http_client: AsyncClient):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    assert response.json().get("access_token") is not None

    tiny_id_2 = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id_2}@lnbits.com",
        },
    )
    assert response.status_code == 400, "Not allowed."
    assert response.json().get("detail") == "Username already exists."


@pytest.mark.anyio
async def test_register_passwords_do_not_match(http_client: AsyncClient):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret0000",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 400, "Bad passwords."
    assert response.json().get("detail") == "Passwords do not match."


@pytest.mark.anyio
async def test_register_bad_email(http_client: AsyncClient):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": "not_an_email_lnbits.com",
        },
    )

    assert response.status_code == 400, "Bad email."
    assert response.json().get("detail") == "Invalid email."


################################ CHANGE PASSWORD ################################
@pytest.mark.anyio
async def test_change_password_ok(http_client: AsyncClient, settings: Settings):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    access_token_payload = AccessTokenPayload(**payload)

    response = await http_client.put(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "username": f"u21.{tiny_id}",
            "user_id": access_token_payload.usr,
            "password_old": "secret1234",
            "password": "secret0000",
            "password_repeat": "secret0000",
        },
    )

    assert response.status_code == 200, "Password changed."
    user = User(**response.json())
    assert user.username == f"u21.{tiny_id}", "Username check."
    assert user.email == f"u21.{tiny_id}@lnbits.com", "Email check."

    response = await http_client.post(
        "/api/v1/auth", json={"username": f"u21.{tiny_id}", "password": "secret1234"}
    )

    assert response.status_code == 401, "Old password does not work"
    assert response.json().get("detail") == "Invalid credentials."

    response = await http_client.post(
        "/api/v1/auth", json={"username": f"u21.{tiny_id}", "password": "secret0000"}
    )

    assert response.status_code == 200, "New password works."
    assert response.json().get("access_token") is not None, "Access token created."


@pytest.mark.anyio
async def test_change_password_not_authenticated(http_client: AsyncClient):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.put(
        "/api/v1/auth/password",
        json={
            "username": f"u21.{tiny_id}",
            "user_id": "0000",
            "password_old": "secret1234",
            "password": "secret0000",
            "password_repeat": "secret0000",
        },
    )

    assert response.status_code == 401, "User not authenticated."
    assert response.json().get("detail") == "Missing user ID or access token."


@pytest.mark.anyio
async def test_alan_change_password_old_nok(user_alan: User, http_client: AsyncClient):
    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None

    response = await http_client.put(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "username": user_alan.username,
            "user_id": user_alan.id,
            "password_old": "secret0000",
            "password": "secret0001",
            "password_repeat": "secret0001",
        },
    )

    assert response.status_code == 400, "Old password bad."
    assert response.json().get("detail") == "Invalid old password."


@pytest.mark.anyio
async def test_alan_change_password_different_user(
    user_alan: User, http_client: AsyncClient
):
    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None

    response = await http_client.put(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "username": user_alan.username,
            "user_id": user_alan.id[::-1],
            "password_old": "secret1234",
            "password": "secret0001",
            "password_repeat": "secret0001",
        },
    )

    assert response.status_code == 400, "Different user id."
    assert response.json().get("detail") == "Invalid user ID."


@pytest.mark.anyio
async def test_alan_change_password_auth_threshold_expired(
    user_alan: User, http_client: AsyncClient, settings: Settings
):

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None

    settings.auth_credetials_update_threshold = 1
    time.sleep(1.1)
    response = await http_client.put(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "username": user_alan.username,
            "user_id": user_alan.id,
            "password_old": "secret1234",
            "password": "secret1234",
            "password_repeat": "secret1234",
        },
    )

    assert response.status_code == 400
    assert (
        response.json().get("detail") == "You can only update your credentials"
        " in the first 1 seconds."
        " Please login again or ask a new reset key!"
    )


################################ REGISTER PUBLIC KEY ################################


@pytest.mark.anyio
async def test_register_nostr_ok(http_client: AsyncClient, settings: Settings):
    event = {**nostr_event}
    event["created_at"] = int(time.time())

    private_key = secp256k1.PrivateKey(bytes.fromhex(os.urandom(32).hex()))
    assert private_key.pubkey, "Pubkey not created."
    pubkey_hex = private_key.pubkey.serialize().hex()[2:]
    event_signed = sign_event(event, pubkey_hex, private_key)
    base64_event = base64.b64encode(json.dumps(event_signed).encode()).decode("ascii")
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event}"},
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    access_token_payload = AccessTokenPayload(**payload)
    assert access_token_payload.auth_time, "Auth time should be set by server."
    assert (
        0 <= time.time() - access_token_payload.auth_time <= 5
    ), "Auth time should be very close to now()."

    response = await http_client.get(
        "/api/v1/auth", headers={"Authorization": f"Bearer {access_token}"}
    )

    user = User(**response.json())
    assert user.username is None, "No username."
    assert user.email is None, "No email."
    assert user.pubkey == pubkey_hex, "Pubkey check."
    assert not user.admin, "Not admin."
    assert not user.super_user, "Not superuser."
    assert not user.has_password, "Password configured."
    assert (
        len(user.wallets) == 1
    ), f"Expected 1 default wallet, not {len(user.wallets)}."


@pytest.mark.anyio
async def test_register_nostr_not_allowed(http_client: AsyncClient, settings: Settings):
    # exclude 'nostr_auth_nip98'
    settings.auth_allowed_methods = [AuthMethods.username_and_password.value]
    response = await http_client.post(
        "/api/v1/auth/nostr",
        json={},
    )

    assert response.status_code == 403, "User not authenticated."
    assert response.json().get("detail") == "Login with Nostr Auth not allowed."

    settings.auth_allowed_methods = AuthMethods.all()


@pytest.mark.anyio
async def test_register_nostr_bad_header(http_client: AsyncClient):
    response = await http_client.post("/api/v1/auth/nostr")

    assert response.status_code == 400, "Missing header."
    assert response.json().get("detail") == "Nostr Auth header missing."

    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": "Bearer xyz"},
    )

    assert response.status_code == 400, "Non nostr header."
    assert response.json().get("detail") == "Invalid Authorization scheme."

    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": "nostr xyz"},
    )
    assert response.status_code == 400, "Nostr not base64."
    assert response.json().get("detail") == "Nostr login event cannot be parsed."


@pytest.mark.anyio
async def test_register_nostr_bad_event(http_client: AsyncClient, settings: Settings):
    settings.auth_allowed_methods = AuthMethods.all()
    base64_event = base64.b64encode(json.dumps(nostr_event).encode()).decode("ascii")
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event}"},
    )
    assert response.status_code == 400, "Nostr event expired."
    assert (
        response.json().get("detail")
        == f"More than {settings.auth_credetials_update_threshold}"
        " seconds have passed since the event was signed."
    )

    corrupted_event = {**nostr_event}
    corrupted_event["content"] = "xyz"
    base64_event = base64.b64encode(json.dumps(corrupted_event).encode()).decode(
        "ascii"
    )
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event}"},
    )
    assert response.status_code == 400, "Nostr event signature invalid."
    assert response.json().get("detail") == "Nostr login event is not valid."


@pytest.mark.anyio
async def test_register_nostr_bad_event_kind(http_client: AsyncClient):
    event_bad_kind = {**nostr_event}
    event_bad_kind["kind"] = "12345"

    event_bad_kind_signed = sign_event(event_bad_kind, pubkey_hex, private_key)
    base64_event_bad_kind = base64.b64encode(
        json.dumps(event_bad_kind_signed).encode()
    ).decode("ascii")
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event_bad_kind}"},
    )
    assert response.status_code == 400, "Nostr event kind invalid."
    assert response.json().get("detail") == "Invalid event kind."


@pytest.mark.anyio
async def test_register_nostr_bad_event_tag_u(http_client: AsyncClient):
    event_bad_kind = {**nostr_event}
    event_bad_kind["created_at"] = int(time.time())

    event_bad_kind["tags"] = [["u", "http://localhost:5000/nostr"]]

    event_bad_tag_signed = sign_event(event_bad_kind, pubkey_hex, private_key)
    base64_event_tag_kind = base64.b64encode(
        json.dumps(event_bad_tag_signed).encode()
    ).decode("ascii")
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event_tag_kind}"},
    )
    assert response.status_code == 400, "Nostr event tag missing."
    assert response.json().get("detail") == "Tag 'method' is missing."

    event_bad_kind["tags"] = [["u", "http://localhost:5000/nostr"], ["method", "XYZ"]]

    event_bad_tag_signed = sign_event(event_bad_kind, pubkey_hex, private_key)
    base64_event_tag_kind = base64.b64encode(
        json.dumps(event_bad_tag_signed).encode()
    ).decode("ascii")
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event_tag_kind}"},
    )
    assert response.status_code == 400, "Nostr event tag invalid."
    assert response.json().get("detail") == "Invalid value for tag 'method'."


@pytest.mark.anyio
async def test_register_nostr_bad_event_tag_menthod(http_client: AsyncClient):
    event_bad_kind = {**nostr_event}
    event_bad_kind["created_at"] = int(time.time())

    event_bad_kind["tags"] = [["method", "POST"]]

    event_bad_tag_signed = sign_event(event_bad_kind, pubkey_hex, private_key)
    base64_event = base64.b64encode(json.dumps(event_bad_tag_signed).encode()).decode(
        "ascii"
    )
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event}"},
    )
    assert response.status_code == 400, "Nostr event tag missing."
    assert response.json().get("detail") == "Tag 'u' for URL is missing."

    event_bad_kind["tags"] = [["u", "http://demo.lnbits.com/nostr"], ["method", "POST"]]

    event_bad_tag_signed = sign_event(event_bad_kind, pubkey_hex, private_key)
    base64_event = base64.b64encode(json.dumps(event_bad_tag_signed).encode()).decode(
        "ascii"
    )
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event}"},
    )
    assert response.status_code == 400, "Nostr event tag invalid."
    assert (
        response.json().get("detail") == "Invalid value for tag 'u':"
        " 'http://demo.lnbits.com/nostr'."
    )


################################ CHANGE PUBLIC KEY ################################
@pytest.mark.anyio
async def test_change_pubkey_npub_ok(http_client: AsyncClient, settings: Settings):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    access_token_payload = AccessTokenPayload(**payload)

    private_key = secp256k1.PrivateKey(bytes.fromhex(os.urandom(32).hex()))
    assert private_key.pubkey, "Pubkey not created."
    pubkey_hex = private_key.pubkey.serialize().hex()[2:]
    npub = hex_to_npub(pubkey_hex)

    response = await http_client.put(
        "/api/v1/auth/pubkey",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "user_id": access_token_payload.usr,
            "pubkey": npub,
        },
    )

    assert response.status_code == 200, "Pubkey changed."
    user = User(**response.json())
    assert user.username == f"u21.{tiny_id}", "Username check."
    assert user.email == f"u21.{tiny_id}@lnbits.com", "Email check."
    assert user.pubkey == pubkey_hex


@pytest.mark.anyio
async def test_change_pubkey_ok(
    http_client: AsyncClient, user_alan: User, settings: Settings
):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    access_token_payload = AccessTokenPayload(**payload)

    private_key = secp256k1.PrivateKey(bytes.fromhex(os.urandom(32).hex()))
    assert private_key.pubkey, "Pubkey not created."
    pubkey_hex = private_key.pubkey.serialize().hex()[2:]

    response = await http_client.put(
        "/api/v1/auth/pubkey",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "user_id": access_token_payload.usr,
            "pubkey": pubkey_hex,
        },
    )

    assert response.status_code == 200, "Pubkey changed."
    user = User(**response.json())
    assert user.username == f"u21.{tiny_id}", "Username check."
    assert user.email == f"u21.{tiny_id}@lnbits.com", "Email check."
    assert user.pubkey == pubkey_hex

    # Login with nostr
    event = {**nostr_event}
    event["created_at"] = int(time.time())
    event["pubkey"] = pubkey_hex
    event_signed = sign_event(event, pubkey_hex, private_key)
    base64_event = base64.b64encode(json.dumps(event_signed).encode()).decode("ascii")
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event}"},
    )
    assert response.status_code == 200, "User logged in."
    access_token = response.json().get("access_token")
    assert access_token is not None

    response = await http_client.get(
        "/api/v1/auth", headers={"Authorization": f"Bearer {access_token}"}
    )
    user = User(**response.json())
    assert user.username == f"u21.{tiny_id}", "Username check."
    assert user.email == f"u21.{tiny_id}@lnbits.com", "Email check."
    assert user.pubkey == pubkey_hex, "No pubkey."
    assert not user.admin, "Not admin."
    assert not user.super_user, "Not superuser."
    assert user.has_password, "Password configured."
    assert len(user.wallets) == 1, "One default wallet."

    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )

    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None

    response = await http_client.put(
        "/api/v1/auth/pubkey",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "user_id": user_alan.id,
            "pubkey": pubkey_hex,
        },
    )

    assert response.status_code == 400, "Pubkey already used."
    assert response.json().get("detail") == "Public key already in use."


@pytest.mark.anyio
async def test_change_pubkey_not_authenticated(
    http_client: AsyncClient, user_alan: User
):
    response = await http_client.put(
        "/api/v1/auth/pubkey",
        json={
            "user_id": user_alan.id,
            "pubkey": pubkey_hex,
        },
    )

    assert response.status_code == 401, "Must be authenticated to change pubkey."
    assert response.json().get("detail") == "Missing user ID or access token."


@pytest.mark.anyio
async def test_change_pubkey_other_user(http_client: AsyncClient, user_alan: User):
    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None

    response = await http_client.put(
        "/api/v1/auth/pubkey",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "user_id": user_alan.id[::-1],
            "pubkey": pubkey_hex,
        },
    )
    assert response.status_code == 400, "Not your user."
    assert response.json().get("detail") == "Invalid user ID."


@pytest.mark.anyio
async def test_alan_change_pubkey_auth_threshold_expired(
    user_alan: User, http_client: AsyncClient, settings: Settings
):

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None

    settings.auth_credetials_update_threshold = 1
    time.sleep(2.1)
    response = await http_client.put(
        "/api/v1/auth/pubkey",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "user_id": user_alan.id,
            "pubkey": pubkey_hex,
        },
    )

    assert response.status_code == 400, "Treshold expired."
    assert (
        response.json().get("detail") == "You can only update your credentials"
        " in the first 1 seconds."
        " Please login again or ask a new reset key!"
    )


################################ RESET PASSWORD ################################
@pytest.mark.anyio
async def test_request_reset_key_ok(http_client: AsyncClient, settings: Settings):
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    access_token_payload = AccessTokenPayload(**payload)
    assert access_token_payload.usr, "User id set."

    reset_key = await api_users_reset_password(access_token_payload.usr)
    assert reset_key, "Reset key created."
    assert reset_key[:10] == "reset_key_", "This is not a reset key."

    response = await http_client.put(
        "/api/v1/auth/reset",
        json={
            "reset_key": reset_key,
            "password": "secret0000",
            "password_repeat": "secret0000",
        },
    )

    assert response.status_code == 200, "Password reset."
    access_token = response.json().get("access_token")
    assert access_token is not None

    response = await http_client.post(
        "/api/v1/auth", json={"username": f"u21.{tiny_id}", "password": "secret1234"}
    )
    assert response.status_code == 401, "Old passord not valid."
    assert response.json().get("detail") == "Invalid credentials."

    response = await http_client.post(
        "/api/v1/auth", json={"username": f"u21.{tiny_id}", "password": "secret0000"}
    )
    assert response.status_code == 200, "Login new password OK."
    access_token = response.json().get("access_token")
    assert access_token is not None


@pytest.mark.anyio
async def test_request_reset_key_user_not_found(http_client: AsyncClient):
    user_id = "926abb2ab59a48ebb2485bcceb58d05e"
    reset_key = await api_users_reset_password(user_id)
    assert reset_key, "Reset key created."
    assert reset_key[:10] == "reset_key_", "This is not a reset key."

    response = await http_client.put(
        "/api/v1/auth/reset",
        json={
            "reset_key": reset_key,
            "password": "secret0000",
            "password_repeat": "secret0000",
        },
    )

    assert response.status_code == 404, "User does not exist."
    assert response.json().get("detail") == "User not found."


@pytest.mark.anyio
async def test_reset_username_password_not_allowed(
    http_client: AsyncClient, settings: Settings
):
    # exclude 'username_password'
    settings.auth_allowed_methods = [AuthMethods.user_id_only.value]

    user_id = "926abb2ab59a48ebb2485bcceb58d05e"
    reset_key = await api_users_reset_password(user_id)
    assert reset_key, "Reset key created."

    response = await http_client.put(
        "/api/v1/auth/reset",
        json={
            "reset_key": reset_key,
            "password": "secret0000",
            "password_repeat": "secret0000",
        },
    )
    settings.auth_allowed_methods = AuthMethods.all()

    assert response.status_code == 403, "Login method not allowed."
    assert (
        response.json().get("detail") == "Auth by 'Username and Password' not allowed."
    )


@pytest.mark.anyio
async def test_reset_username_passwords_do_not_matcj(
    http_client: AsyncClient, user_alan: User
):

    reset_key = await api_users_reset_password(user_alan.id)
    assert reset_key, "Reset key created."

    response = await http_client.put(
        "/api/v1/auth/reset",
        json={
            "reset_key": reset_key,
            "password": "secret0000",
            "password_repeat": "secret-does-not-mathc",
        },
    )

    assert response.status_code == 400, "Passwords do not match."
    assert response.json().get("detail") == "Passwords do not match."


@pytest.mark.anyio
async def test_reset_username_password_bad_key(http_client: AsyncClient):

    response = await http_client.put(
        "/api/v1/auth/reset",
        json={
            "reset_key": "reset_key_xxxxxxxxxxx",
            "password": "secret0000",
            "password_repeat": "secret0000",
        },
    )
    assert response.status_code == 400, "Bad reset key."
    assert response.json().get("detail") == "Invalid reset key."


@pytest.mark.anyio
async def test_reset_password_auth_threshold_expired(
    user_alan: User, http_client: AsyncClient, settings: Settings
):

    reset_key = await api_users_reset_password(user_alan.id)
    assert reset_key, "Reset key created."

    settings.auth_credetials_update_threshold = 1
    time.sleep(1.1)
    response = await http_client.put(
        "/api/v1/auth/reset",
        json={
            "reset_key": reset_key,
            "password": "secret0000",
            "password_repeat": "secret0000",
        },
    )

    assert response.status_code == 400, "Treshold expired."
    assert (
        response.json().get("detail") == "You can only update your credentials"
        " in the first 1 seconds."
        " Please login again or ask a new reset key!"
    )


################################ ACL ################################
@pytest.mark.anyio
async def test_api_update_user_acl_success(http_client: AsyncClient, user_alan: User):
    # Login to get access token
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )
    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create a new ACL
    data = UpdateAccessControlList(
        id="", name="New ACL", password="secret1234", endpoints=[]
    )
    response = await http_client.put(
        "/api/v1/auth/acl",
        json=data.dict(),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200, "ACL should be created successfully."
    user_acls = UserAcls(**response.json())
    assert any(
        acl.name == "New ACL" for acl in user_acls.access_control_list
    ), "ACL should be in the list."


@pytest.mark.anyio
async def test_api_update_user_acl_invalid_password(
    http_client: AsyncClient, user_alan: User
):
    # Login to get access token
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )
    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Attempt to create a new ACL with an invalid password
    data = UpdateAccessControlList(
        id="", name="New ACL", password="wrong_password", endpoints=[]
    )
    response = await http_client.put(
        "/api/v1/auth/acl",
        json=data.dict(),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 401
    ), "Invalid password should result in unauthorized error."
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.anyio
async def test_api_update_user_acl_update_existing(
    http_client: AsyncClient, user_alan: User
):
    # Login to get access token
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )
    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create a new ACL
    data = UpdateAccessControlList(
        id="", name="New ACL", password="secret1234", endpoints=[]
    )
    response = await http_client.put(
        "/api/v1/auth/acl",
        json=data.dict(),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200, "ACL should be created successfully."
    user_acls = UserAcls(**response.json())
    acl = next(acl for acl in user_acls.access_control_list if acl.name == "New ACL")

    # Update the existing ACL
    data = UpdateAccessControlList(
        id=acl.id, name="Updated ACL", password="secret1234", endpoints=[]
    )
    response = await http_client.put(
        "/api/v1/auth/acl",
        json=data.dict(),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200, "ACL should be updated successfully."
    user_acls = UserAcls(**response.json())
    assert any(
        acl.name == "Updated ACL" for acl in user_acls.access_control_list
    ), "ACL should be updated in the list."


@pytest.mark.anyio
async def test_api_update_user_acl_missing_password(
    http_client: AsyncClient, user_alan: User
):
    # Login to get access token
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )
    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Attempt to create a new ACL with a missing password
    data = UpdateAccessControlList(id="", name="New ACL", password="", endpoints=[])
    response = await http_client.put(
        "/api/v1/auth/acl",
        json=data.dict(),
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert (
        response.status_code == 401
    ), "Missing password should result in unauthorized error."
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.anyio
async def test_api_get_user_acls_success(http_client: AsyncClient):
    # Register a new user to obtain the access token
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Get user ACLs
    response = await http_client.get(
        "/api/v1/auth/acl", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200, "ACLs fetched successfully."
    user_acls = UserAcls(**response.json())
    assert user_acls.id is not None, "User ID should be set."
    assert isinstance(user_acls.access_control_list, list), "ACL should be a list."


@pytest.mark.anyio
async def test_api_get_user_acls_no_auth(http_client: AsyncClient):
    # Attempt to get user ACLs without authentication
    response = await http_client.get("/api/v1/auth/acl")
    assert response.status_code == 401, "Unauthorized access."


@pytest.mark.anyio
async def test_api_get_user_acls_invalid_token(http_client: AsyncClient):
    # Attempt to get user ACLs with an invalid token
    response = await http_client.get(
        "/api/v1/auth/acl", headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401, "Unauthorized access."


@pytest.mark.anyio
async def test_api_get_user_acls_empty_acl(http_client: AsyncClient):
    # Register a new user to obtain the access token
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Get user ACLs
    response = await http_client.get(
        "/api/v1/auth/acl", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200, "ACLs fetched successfully."
    user_acls = UserAcls(**response.json())
    assert user_acls.id is not None, "User ID should be set."
    assert len(user_acls.access_control_list) == 0, "ACL should be empty."


@pytest.mark.anyio
async def test_api_get_user_acls_with_acl(http_client: AsyncClient):
    # Register a new user to obtain the access token
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create a new ACL for the user
    acl_data = UpdateAccessControlList(
        id="",
        name="Test ACL",
        endpoints=[],
        password="secret1234",
    )
    response = await http_client.put(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json=acl_data.dict(),
    )
    assert response.status_code == 200, "ACL created successfully."

    # Get user ACLs
    response = await http_client.get(
        "/api/v1/auth/acl", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200, "ACLs fetched successfully."
    user_acls = UserAcls(**response.json())
    assert user_acls.id is not None, "User ID should be set."
    assert len(user_acls.access_control_list) == 1, "ACL should contain one item."
    assert user_acls.access_control_list[0].name == "Test ACL", "ACL name should match."


@pytest.mark.anyio
async def test_api_get_user_acls_sorted(http_client: AsyncClient):
    # Register a new user to obtain the access token
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )

    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create some ACLs for the user
    acl_names = ["zeta", "alpha", "gamma"]
    for name in acl_names:
        response = await http_client.put(
            "/api/v1/auth/acl",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"id": name, "name": name, "password": "secret1234"},
        )
        assert (
            response.status_code == 200
        ), f"ACL '{name}' should be created successfully."

    # Get the user's ACLs
    response = await http_client.get(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200, "ACLs retrieved."
    user_acls = UserAcls(**response.json())

    # Check that the ACLs are sorted alphabetically by name
    acl_names_sorted = sorted(acl_names)
    retrieved_acl_names = [acl.name for acl in user_acls.access_control_list]
    assert (
        retrieved_acl_names == acl_names_sorted
    ), "ACLs are not sorted alphabetically by name."


@pytest.mark.anyio
async def test_api_delete_user_acl_success(http_client: AsyncClient):
    # Register a new user to obtain the access token
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create an ACL for the user
    response = await http_client.put(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "id": "Test ACL",
            "name": "Test ACL",
            "password": "secret1234",
        },
    )

    assert response.status_code == 200, "ACL created."
    acl_id = response.json()["access_control_list"][0]["id"]

    # Delete the ACL
    response = await http_client.request(
        "DELETE",
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "id": acl_id,
            "password": "secret1234",
        },
    )
    assert response.status_code == 200, "ACL deleted."


@pytest.mark.anyio
async def test_api_delete_user_acl_invalid_password(http_client: AsyncClient):
    # Register a new user to obtain the access token
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create an ACL for the user
    response = await http_client.put(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "id": "Test ACL",
            "name": "Test ACL",
            "password": "secret1234",
        },
    )
    assert response.status_code == 200, "ACL created."
    acl_id = response.json()["access_control_list"][0]["id"]

    # Attempt to delete the ACL with an invalid password
    response = await http_client.request(
        "DELETE",
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "id": acl_id,
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401, "Invalid credentials."


@pytest.mark.anyio
async def test_api_delete_user_acl_nonexistent_acl(http_client: AsyncClient):
    # Register a new user to obtain the access token
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Attempt to delete a nonexistent ACL
    response = await http_client.request(
        "DELETE",
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "id": "nonexistent_acl_id",
            "password": "secret1234",
        },
    )
    assert response.status_code == 200, "ACL deleted."


@pytest.mark.anyio
async def test_api_delete_user_acl_missing_password(http_client: AsyncClient):
    # Register a new user to obtain the access token
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create an ACL for the user
    response = await http_client.put(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "id": "Test ACL",
            "name": "Test ACL",
            "password": "secret1234",
        },
    )
    assert response.status_code == 200, "ACL created."
    acl_id = response.json()["access_control_list"][0]["id"]

    # Attempt to delete the ACL without providing a password
    response = await http_client.request(
        "DELETE",
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "id": acl_id,
        },
    )
    assert response.status_code == 400, "Missing password."


################################ TOKEN ################################
@pytest.mark.anyio
async def test_api_create_user_api_token_success(
    http_client: AsyncClient, settings: Settings
):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create a new ACL
    acl_data = UpdateAccessControlList(
        id="", password="secret1234", name="Test ACL", endpoints=[]
    )
    response = await http_client.put(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json=acl_data.dict(),
    )
    assert response.status_code == 200, "ACL created."
    acl_id = response.json()["access_control_list"][0]["id"]

    # Create API token
    token_request = ApiTokenRequest(
        acl_id=acl_id,
        token_name="Test Token",
        expiration_time_minutes=60,
        password="secret1234",
    )
    response = await http_client.post(
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=token_request.dict(),
    )
    assert response.status_code == 200, "API token created."
    api_token = response.json().get("api_token")
    assert api_token is not None

    # Verify the token exists
    response = await http_client.get(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200, "ACLs fetched successfully."
    acls = UserAcls(**response.json())
    # Decode the access token to get the user ID
    payload: dict = jwt.decode(api_token, settings.auth_secret_key, ["HS256"])

    # Check the expiration time
    expiration_time = payload.get("exp")
    assert expiration_time is not None, "Expiration time should be set."
    assert (
        0 <= 3600 - (expiration_time - time.time()) <= 5
    ), "Expiration time should be 60 minutes from now."

    token_id = payload["api_token_id"]
    assert any(
        token_id in [token.id for token in acl.token_id_list]
        for acl in acls.access_control_list
    ), "API token should be part of at least one ACL."


@pytest.mark.anyio
async def test_acl_api_token_access(user_alan: User, http_client: AsyncClient):
    user_acls = await get_user_access_control_lists(user_alan.id)
    acl = AccessControlList(id=uuid4().hex, name="Test ACL", endpoints=[])
    user_acls.access_control_list = [acl]

    api_token_id = uuid4().hex
    payload = AccessTokenPayload(
        sub=user_alan.username or user_alan.id,
        api_token_id=api_token_id,
        auth_time=int(time.time()),
    )

    api_token = create_access_token(data=payload.dict(), token_expire_minutes=10)
    acl.token_id_list.append(SimpleItem(id=api_token_id, name="Test Token"))
    await update_user_access_control_list(user_acls)

    headers = {"Authorization": f"Bearer {api_token}"}
    response = await http_client.get("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 403, "Path not allowed."
    assert response.json()["detail"] == "Path not allowed."

    # Grant read access
    endpoint = EndpointAccess(path="/api/v1/auth", name="Get User ACLs", read=True)
    acl.endpoints.append(endpoint)
    await update_user_access_control_list(user_acls)

    response = await http_client.get("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 200, "Access granted."

    response = await http_client.put("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 403, "Method not allowed."

    response = await http_client.post(
        "/api/v1/auth/acl/token", headers=headers, json={}
    )
    assert response.status_code == 403, "Method not allowed."

    response = await http_client.patch("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 403, "Method not allowed."

    response = await http_client.delete("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 403, "Method not allowed."

    # Grant write access
    endpoint.write = True
    await update_user_access_control_list(user_acls)
    response = await http_client.get("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 200, "Access granted."

    response = await http_client.put("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 400, "Access granted, validation error expected."

    response = await http_client.post(
        "/api/v1/auth/acl/token", headers=headers, json={}
    )
    assert response.status_code == 400, "Access granted, validation error expected."

    response = await http_client.patch("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 400, "Access granted, validation error expected."

    response = await http_client.delete("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 400, "Access granted, validation error expected."

    # Revoke read access
    endpoint.read = False
    await update_user_access_control_list(user_acls)
    response = await http_client.get("/api/v1/auth/acl", headers=headers)
    assert response.status_code == 403, "Method not allowed."

    response = await http_client.put("/api/v1/auth/acl", headers=headers)
    assert (
        response.status_code == 400
    ), "Access still granted, validation error expected."


@pytest.mark.anyio
async def test_api_create_user_api_token_invalid_password(http_client: AsyncClient):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create a new ACL
    acl_data = UpdateAccessControlList(
        password="secret1234", id="", name="Test ACL", endpoints=[]
    )
    response = await http_client.put(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json=acl_data.dict(),
    )
    assert response.status_code == 200, "ACL created."
    acl_id = response.json()["access_control_list"][0]["id"]

    # Create API token with invalid password
    token_request = ApiTokenRequest(
        acl_id=acl_id,
        token_name="Test Token",
        expiration_time_minutes=60,
        password="wrongpassword",
    )
    response = await http_client.post(
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=token_request.dict(),
    )
    assert response.status_code == 401, "Invalid credentials."


@pytest.mark.anyio
async def test_api_create_user_api_token_invalid_acl_id(http_client: AsyncClient):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create API token with invalid ACL ID
    token_request = ApiTokenRequest(
        acl_id="invalid_acl_id",
        token_name="Test Token",
        expiration_time_minutes=60,
        password="secret1234",
    )
    response = await http_client.post(
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=token_request.dict(),
    )
    assert response.status_code == 401, "Invalid ACL id."


@pytest.mark.anyio
async def test_api_create_user_api_token_expiration_time_invalid(
    http_client: AsyncClient,
):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Create a new ACL
    acl_data = UpdateAccessControlList(
        id="", password="secret1234", name="Test ACL", endpoints=[]
    )
    response = await http_client.put(
        "/api/v1/auth/acl",
        headers={"Authorization": f"Bearer {access_token}"},
        json=acl_data.dict(),
    )
    assert response.status_code == 200, "ACL created."
    acl_id = response.json()["access_control_list"][0]["id"]

    # Create API token with invalid expiration time
    token_request = ApiTokenRequest(
        acl_id=acl_id,
        token_name="Test Token",
        expiration_time_minutes=-1,
        password="secret1234",
    )
    response = await http_client.post(
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=token_request.dict(),
    )
    assert response.status_code == 400, "Expiration time must be in the future."


@pytest.mark.anyio
async def test_api_delete_user_api_token_success(
    http_client: AsyncClient, settings: Settings
):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Decode the access token to get the user ID
    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    user_id = payload["usr"]

    # Create a new ACL
    acl_data = UpdateAccessControlList(
        id="", name="Test ACL", endpoints=[], password="secret1234"
    )
    user_acls = await get_user_access_control_lists(user_id)
    user_acls.access_control_list.append(acl_data)
    await update_user_access_control_list(user_acls)

    # Create a new API token
    api_token_request = ApiTokenRequest(
        acl_id=acl_data.id,
        token_name="Test Token",
        expiration_time_minutes=60,
        password="secret1234",
    )
    response = await http_client.post(
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=api_token_request.dict(),
    )
    assert response.status_code == 200, "API token created."
    api_token_id = response.json().get("id")
    assert api_token_id is not None

    # Delete the API token
    delete_token_request = DeleteTokenRequest(
        acl_id=acl_data.id, id=api_token_id, password="secret1234"
    )
    response = await http_client.request(
        "DELETE",
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=delete_token_request.dict(),
    )
    assert response.status_code == 200, "API token deleted."


@pytest.mark.anyio
async def test_api_delete_user_api_token_invalid_password(
    http_client: AsyncClient, settings: Settings
):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Decode the access token to get the user ID
    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    user_id = payload["usr"]

    # Create a new ACL
    acl_data = UpdateAccessControlList(
        id="", name="Test ACL", endpoints=[], password="secret1234"
    )
    user_acls = await get_user_access_control_lists(user_id)
    user_acls.access_control_list.append(acl_data)
    await update_user_access_control_list(user_acls)

    # Create a new API token
    api_token_request = ApiTokenRequest(
        acl_id=acl_data.id,
        token_name="Test Token",
        expiration_time_minutes=60,
        password="secret1234",
    )
    response = await http_client.post(
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=api_token_request.dict(),
    )
    assert response.status_code == 200, "API token created."
    api_token_id = response.json().get("id")
    assert api_token_id is not None

    # Attempt to delete the API token with an invalid password
    delete_token_request = DeleteTokenRequest(
        acl_id=acl_data.id, id=api_token_id, password="wrong_password"
    )
    response = await http_client.request(
        "DELETE",
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=delete_token_request.dict(),
    )
    assert response.status_code == 401, "Invalid credentials."


@pytest.mark.anyio
async def test_api_delete_user_api_token_invalid_acl_id(
    http_client: AsyncClient,
):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Attempt to delete an API token with an invalid ACL ID
    delete_token_request = DeleteTokenRequest(
        acl_id="invalid_acl_id", id="invalid_token_id", password="secret1234"
    )
    response = await http_client.request(
        "DELETE",
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=delete_token_request.dict(),
    )
    assert response.status_code == 401, "Invalid ACL id."


@pytest.mark.anyio
async def test_api_delete_user_api_token_missing_token_id(
    http_client: AsyncClient, settings: Settings
):
    # Register a new user
    tiny_id = shortuuid.uuid()[:8]
    response = await http_client.post(
        "/api/v1/auth/register",
        json={
            "username": f"u21.{tiny_id}",
            "password": "secret1234",
            "password_repeat": "secret1234",
            "email": f"u21.{tiny_id}@lnbits.com",
        },
    )
    assert response.status_code == 200, "User created."
    access_token = response.json().get("access_token")
    assert access_token is not None

    # Decode the access token to get the user ID
    payload: dict = jwt.decode(access_token, settings.auth_secret_key, ["HS256"])
    user_id = payload["usr"]

    # Create a new ACL
    acl_data = UpdateAccessControlList(
        id="", name="Test ACL", endpoints=[], password="secret1234"
    )
    user_acls = await get_user_access_control_lists(user_id)
    user_acls.access_control_list.append(acl_data)
    await update_user_access_control_list(user_acls)

    # Attempt to delete an API token with a missing token ID
    delete_token_request = DeleteTokenRequest(
        acl_id=acl_data.id, id="", password="secret1234"
    )
    response = await http_client.request(
        "DELETE",
        "/api/v1/auth/acl/token",
        headers={"Authorization": f"Bearer {access_token}"},
        json=delete_token_request.dict(),
    )
    assert response.status_code == 200, "Does noting if token not found."
