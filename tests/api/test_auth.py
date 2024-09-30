import base64
import json
import time

import jwt
import pytest
import secp256k1
import shortuuid
from httpx import AsyncClient

from lnbits.core.models import AccessTokenPayload, User
from lnbits.settings import AuthMethods, settings
from lnbits.utils.nostr import sign_event

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

settings.auth_allowed_methods = AuthMethods.all()


################################ LOGIN ################################
@pytest.mark.asyncio
async def test_login_bad_user(http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": "non_existing_user", "password": "secret1234"}
    )

    assert response.status_code == 401, "User does not exist"
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_login_usr_not_allowed(user_alan: User, http_client: AsyncClient):
    # exclude 'user_id_only'
    settings.auth_allowed_methods = [AuthMethods.username_and_password.value]

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 401, "Login method not allowed."
    assert response.json().get("detail") == "Login by 'User ID' not allowed."

    settings.auth_allowed_methods = AuthMethods.all()

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})
    assert response.status_code == 200, "Login with 'usr' allowed."
    assert (
        response.json().get("access_token") is not None
    ), "Expected access token after login."


@pytest.mark.asyncio
async def test_login_alan_username_password_ok(
    user_alan: User, http_client: AsyncClient
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
    assert len(user.wallets) == 1, "One default wallet."


@pytest.mark.asyncio
async def test_login_alan_email_password_ok(user_alan: User, http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.email, "password": "secret1234"}
    )

    assert response.status_code == 200, "Alan logs in OK"
    access_token = response.json().get("access_token")
    assert access_token is not None


@pytest.mark.asyncio
async def test_login_alan_password_nok(user_alan: User, http_client: AsyncClient):
    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "bad_pasword"}
    )

    assert response.status_code == 401, "User does not exist"
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.asyncio
async def test_login_username_password_not_allowed(
    user_alan: User, http_client: AsyncClient
):
    # exclude 'username_password'
    settings.auth_allowed_methods = [AuthMethods.user_id_only.value]

    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )

    assert response.status_code == 401, "Login method not allowed."
    assert (
        response.json().get("detail") == "Login by 'Username and Password' not allowed."
    )

    settings.auth_allowed_methods = AuthMethods.all()

    response = await http_client.post(
        "/api/v1/auth", json={"username": user_alan.username, "password": "secret1234"}
    )
    assert response.status_code == 200, "Username and password is allowed."
    assert response.json().get("access_token") is not None


@pytest.mark.asyncio
async def test_login_alan_change_auth_secret_key(
    user_alan: User, http_client: AsyncClient
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
@pytest.mark.asyncio
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
    assert len(user.wallets) == 1, "One default wallet."


@pytest.mark.asyncio
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
    assert response.status_code == 403, "Not allowed."
    assert response.json().get("detail") == "Email already exists."


@pytest.mark.asyncio
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
    assert response.status_code == 403, "Not allowed."
    assert response.json().get("detail") == "Username already exists."


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
@pytest.mark.asyncio
async def test_change_password_ok(http_client: AsyncClient):
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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

    assert response.status_code == 403, "Old password bad."
    assert response.json().get("detail") == "Invalid credentials."


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_alan_change_password_auth_threshold_expired(
    user_alan: User, http_client: AsyncClient
):

    response = await http_client.post("/api/v1/auth/usr", json={"usr": user_alan.id})

    assert response.status_code == 200, "Alan logs in OK."
    access_token = response.json().get("access_token")
    assert access_token is not None

    initial_update_threshold = settings.auth_credetials_update_threshold
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

    settings.auth_credetials_update_threshold = initial_update_threshold

    assert response.status_code == 403, "Treshold expired."
    assert (
        response.json().get("detail") == "You can only update your credentials"
        " in the first 1 seconds after login."
        " Please login again!"
    )


################################ REGISTER PUBLIC KEY ################################
@pytest.mark.asyncio
async def test_register_nostr_not_allowed(http_client: AsyncClient):
    # exclude 'nostr_auth_nip98'
    settings.auth_allowed_methods = [AuthMethods.username_and_password.value]
    response = await http_client.post(
        "/api/v1/auth/nostr",
        json={},
    )

    assert response.status_code == 401, "User not authenticated."
    assert response.json().get("detail") == "Login with Nostr Auth not allowed."

    settings.auth_allowed_methods = AuthMethods.all()


@pytest.mark.asyncio
async def test_register_nostr_bad_header(http_client: AsyncClient):
    response = await http_client.post("/api/v1/auth/nostr")

    assert response.status_code == 401, "Missing header."
    assert response.json().get("detail") == "Nostr Auth header missing."

    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": "Bearer xyz"},
    )

    assert response.status_code == 401, "Non nostr header."
    assert response.json().get("detail") == "Authorization header is not nostr."

    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": "nostr xyz"},
    )
    assert response.status_code == 401, "Nostr not base64."
    assert response.json().get("detail") == "Nostr login event cannot be parsed."


@pytest.mark.asyncio
async def test_register_nostr_bad_event(http_client: AsyncClient):
    settings.auth_allowed_methods = AuthMethods.all()
    base64_event = base64.b64encode(json.dumps(nostr_event).encode()).decode("ascii")
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event}"},
    )
    assert response.status_code == 401, "Nostr event expired."
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
    assert response.status_code == 401, "Nostr event signature invalid."
    assert response.json().get("detail") == "Nostr login event is not valid."

    private_key = secp256k1.PrivateKey(
        bytes.fromhex(
            "6e00ecda7d3c8945f07b7d6ecc18cfff34c07bc99677309e2b9310d9fc1bb138"
        )
    )
    event_bad_kind = {**nostr_event}
    event_bad_kind["kind"] = "12345"
    print("### private_key.pubkey.hex()", private_key.pubkey.serialize().hex()[2:])
    event_bad_kind_signed = sign_event(
        event_bad_kind, private_key.pubkey.serialize().hex()[2:], private_key
    )
    base64_event_bad_kind = base64.b64encode(
        json.dumps(event_bad_kind_signed).encode()
    ).decode("ascii")
    response = await http_client.post(
        "/api/v1/auth/nostr",
        headers={"Authorization": f"nostr {base64_event_bad_kind}"},
    )
    assert response.status_code == 401, "Nostr event kind invalid."
    assert response.json().get("detail") == "Invalid event kind."


################################ CHANGE PUBLIC KEY ################################
@pytest.mark.asyncio
async def test_change_pubkey_not_authenticated(http_client: AsyncClient):
    pass
