import asyncio
import base64
import json
import secrets
from time import time
from uuid import uuid4

import jwt
import pytest
from coincurve import PrivateKey
from fastapi_sso.sso.base import OpenID

from lnbits.core.crud.settings import set_settings_field
from lnbits.core.crud.users import (
    get_account,
    get_two_factor_config,
    save_two_factor_config,
    update_account,
)
from lnbits.core.models.users import AccessTokenPayload, Account, TwoFactorConfig
from lnbits.core.services.two_factor import (
    issue_challenge,
    reset_two_factor,
    sync_two_factor_policy,
    totp,
    verify_factor,
)
from lnbits.core.services.users import create_user_account
from lnbits.core.views.auth_api import _handle_sso_login
from lnbits.core.views.user_api import api_users_reset_password
from lnbits.helpers import create_access_token
from lnbits.settings import AuthMethods
from lnbits.utils.nostr import sign_event

pytestmark = pytest.mark.anyio


@pytest.fixture
async def factor_account(http_client, settings):
    settings.totp_encryption_key = uuid4().hex
    settings.lnbits_two_factor_enabled = True
    settings.lnbits_two_factor_mandatory = False
    settings.auth_allowed_methods = [
        AuthMethods.username_and_password.value,
        AuthMethods.user_id_only.value,
    ]
    account = Account(id=uuid4().hex, username="mfa_" + uuid4().hex[:8])
    account.hash_password("secret1234")
    await create_user_account(account)
    return account


async def login(client, account):
    return await client.post(
        "/api/v1/auth", json={"username": account.username, "password": "secret1234"}
    )


async def enroll(client, account):
    response = await login(client, account)
    assert response.status_code == 200
    setup = await client.post("/api/v1/auth/2fa/setup")
    assert setup.status_code == 200, setup.text
    secret = base64.b32decode(setup.json()["secret"])
    response = await client.post(
        "/api/v1/auth/2fa/confirm",
        json={"code": totp(secret).generate(int(time())).decode()},
    )
    assert response.status_code == 200, response.text
    return secret, response.json()


@pytest.mark.parametrize("stored", [False, True])
async def test_two_factor_concurrent_challenges_are_preserved(factor_account, stored):
    if stored:
        await save_two_factor_config(factor_account.id, TwoFactorConfig())

    challenges = await asyncio.wait_for(
        asyncio.gather(
            issue_challenge(factor_account.id),
            issue_challenge(factor_account.id),
        ),
        timeout=10,
    )
    config = await get_two_factor_config(factor_account.id)
    assert len(config.challenges) == 2
    assert set(config.challenges) == {challenge.jti for challenge in challenges}


async def test_two_factor_enrollment_privacy_and_account_updates(
    http_client, factor_account
):
    account = factor_account
    secret, enrollment = await enroll(http_client, account)
    assert len(enrollment["recovery_codes"]) == 10
    config = await get_two_factor_config(account.id)
    assert config.secret and not config.pending_secret
    assert base64.b32encode(secret).decode() not in config.json()
    assert all(code not in config.json() for code in enrollment["recovery_codes"])
    assert (await http_client.get("/api/v1/auth")).status_code == 200
    profile = await http_client.patch("/api/v1/auth/ui", json={"theme": "test"})
    assert profile.status_code == 200
    assert "two_factor" not in profile.json()
    saved = await get_account(account.id)
    assert saved
    await update_account(saved)
    assert await get_two_factor_config(account.id) == config


async def test_two_factor_login_challenge_and_recovery_replay(
    http_client, factor_account
):
    _, enrollment = await enroll(http_client, factor_account)
    http_client.cookies.clear()
    response = await login(http_client, factor_account)
    assert response.json()["two_factor_required"]
    assert "access_token" not in response.json()
    challenge = http_client.cookies["two_factor_challenge"]
    headers = {"Authorization": f"Bearer {challenge}"}
    assert (await http_client.get("/api/v1/auth", headers=headers)).status_code == 401
    assert (await http_client.get("/api/v1/auth")).status_code == 401
    code = enrollment["recovery_codes"][0]
    response = await http_client.post("/api/v1/auth/2fa/verify", json={"code": code})
    assert response.status_code == 200
    assert (await http_client.get("/api/v1/auth")).status_code == 200
    assert (
        await http_client.post(
            "/api/v1/auth/2fa/verify",
            headers=headers,
            json={"code": enrollment["recovery_codes"][1]},
        )
    ).status_code == 401
    await login(http_client, factor_account)
    assert (
        await http_client.post("/api/v1/auth/2fa/verify", json={"code": code})
    ).status_code == 401


async def test_two_factor_user_id_and_cached_session_cannot_bypass(
    http_client, factor_account
):
    old = (await login(http_client, factor_account)).json()["access_token"]
    headers = {"Authorization": f"Bearer {old}"}
    # Populate the authentication cache before enabling this account's factor.
    assert (await http_client.get("/api/v1/auth", headers=headers)).status_code == 200
    await enroll(http_client, factor_account)
    assert (await http_client.get("/api/v1/auth", headers=headers)).status_code == 401
    http_client.cookies.clear()
    assert (
        await http_client.get("/api/v1/auth", params={"usr": factor_account.id})
    ).status_code == 401
    response = await http_client.post(
        "/api/v1/auth/usr", json={"usr": factor_account.id}
    )
    assert response.json()["two_factor_required"]


async def test_two_factor_mandatory_enrollment_only(
    http_client, factor_account, settings
):
    settings.lnbits_two_factor_mandatory = True
    response = await login(http_client, factor_account)
    assert response.json()["enrollment_required"]
    assert (await http_client.get("/api/v1/auth")).status_code == 401
    assert (await http_client.get("/api/v1/auth/2fa/status")).status_code == 200
    await enroll(http_client, factor_account)
    assert (await http_client.get("/api/v1/auth")).status_code == 200
    assert (await http_client.delete("/api/v1/auth/2fa")).status_code == 403
    response = await http_client.post("/api/v1/account", json={"name": "New wallet"})
    assert response.json()["enrollment_required"]
    assert "adminkey" not in response.json()


async def test_two_factor_global_off_and_on(http_client, factor_account, settings):
    await enroll(http_client, factor_account)
    settings.lnbits_two_factor_enabled = False
    response = await login(http_client, factor_account)
    assert "access_token" in response.json()
    assert (await http_client.get("/api/v1/auth")).status_code == 200
    assert (await get_two_factor_config(factor_account.id)).secret
    settings.lnbits_two_factor_enabled = True
    await set_settings_field("two_factor_revision", secrets.token_hex(16), "security")
    assert (await http_client.get("/api/v1/auth")).status_code == 401
    assert (await login(http_client, factor_account)).json()["two_factor_required"]


async def test_two_factor_throttle_survives_new_challenges(http_client, factor_account):
    await enroll(http_client, factor_account)
    for _ in range(5):
        await login(http_client, factor_account)
        response = await http_client.post(
            "/api/v1/auth/2fa/verify", json={"code": "badcode"}
        )
        assert response.status_code == 401
    await login(http_client, factor_account)
    response = await http_client.post(
        "/api/v1/auth/2fa/verify", json={"code": "badcode"}
    )
    assert response.status_code == 429


async def test_two_factor_concurrent_recovery_has_one_winner(
    http_client, factor_account, settings
):
    _, enrollment = await enroll(http_client, factor_account)
    await login(http_client, factor_account)
    token = http_client.cookies["two_factor_challenge"]
    payload = AccessTokenPayload(
        **jwt.decode(token, settings.auth_secret_key, ["HS256"])
    )
    results = await asyncio.gather(
        *[
            verify_factor(factor_account.id, payload, enrollment["recovery_codes"][0])
            for _ in range(2)
        ],
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1


async def test_two_factor_concurrent_invalid_codes_count_attempts(
    http_client, factor_account
):
    await enroll(http_client, factor_account)
    await login(http_client, factor_account)
    responses = await asyncio.wait_for(
        asyncio.gather(
            *[
                http_client.post("/api/v1/auth/2fa/verify", json={"code": "badcode"})
                for _ in range(2)
            ]
        ),
        timeout=10,
    )
    assert all(response.status_code == 401 for response in responses)
    assert (await get_two_factor_config(factor_account.id)).failures == 2


async def test_two_factor_pending_and_replayed_totp(http_client, factor_account):
    await login(http_client, factor_account)
    setup = await http_client.post("/api/v1/auth/2fa/setup")
    assert not (await get_two_factor_config(factor_account.id)).secret
    secret = base64.b32decode(setup.json()["secret"])
    code = totp(secret).generate(int(time())).decode()
    assert (
        await http_client.post("/api/v1/auth/2fa/confirm", json={"code": code})
    ).status_code == 200
    await login(http_client, factor_account)
    assert (
        await http_client.post("/api/v1/auth/2fa/verify", json={"code": code})
    ).status_code == 401


async def test_two_factor_local_reset_revokes_sessions(
    http_client, factor_account, settings
):
    _, enrollment = await enroll(http_client, factor_account)
    await reset_two_factor(factor_account.id)
    assert (await http_client.get("/api/v1/auth")).status_code == 401
    settings.lnbits_two_factor_mandatory = True
    response = await login(http_client, factor_account)
    assert response.json()["enrollment_required"]
    assert (
        await http_client.post(
            "/api/v1/auth/2fa/verify", json={"code": enrollment["recovery_codes"][0]}
        )
    ).status_code == 401


async def test_two_factor_admin_policy_safeguards(
    http_client, factor_account, settings
):
    settings.lnbits_admin_users = [factor_account.id]
    await login(http_client, factor_account)
    response = await http_client.patch(
        "/admin/api/v1/settings", json={"lnbits_two_factor_mandatory": True}
    )
    assert response.status_code == 400
    await enroll(http_client, factor_account)
    assert (
        await http_client.patch(
            "/admin/api/v1/settings", json={"lnbits_two_factor_mandatory": True}
        )
    ).status_code == 400
    assert (
        await http_client.post("/api/v1/auth/2fa/recovery/acknowledge")
    ).status_code == 200
    assert (
        await http_client.patch(
            "/admin/api/v1/settings", json={"lnbits_two_factor_mandatory": True}
        )
    ).status_code == 200


async def test_two_factor_automation_and_impersonation_cannot_manage(
    http_client, factor_account
):
    await enroll(http_client, factor_account)
    config = await get_two_factor_config(factor_account.id)
    for extra in ({"api_token_id": "automation"}, {"impersonated_by": uuid4().hex}):
        payload = {
            "sub": "",
            "usr": factor_account.id,
            "mfa_revision": config.revision,
            **extra,
        }
        token = create_access_token(payload)
        response = await http_client.get(
            "/api/v1/auth/2fa/status", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403


async def test_two_factor_setup_and_challenge_expire(http_client, factor_account):
    await login(http_client, factor_account)
    setup = await http_client.post("/api/v1/auth/2fa/setup")
    secret = base64.b32decode(setup.json()["secret"])
    config = await get_two_factor_config(factor_account.id)
    config.pending_until = 1
    await save_two_factor_config(factor_account.id, config)
    assert (
        await http_client.post(
            "/api/v1/auth/2fa/confirm",
            json={"code": totp(secret).generate(int(time())).decode()},
        )
    ).status_code == 401
    config = await get_two_factor_config(factor_account.id)
    assert not config.secret
    assert config.failures == 1
    _, enrollment = await enroll(http_client, factor_account)
    await login(http_client, factor_account)
    config = await get_two_factor_config(factor_account.id)
    config.challenges = {}
    await save_two_factor_config(factor_account.id, config)
    assert (
        await http_client.post(
            "/api/v1/auth/2fa/verify", json={"code": enrollment["recovery_codes"][0]}
        )
    ).status_code == 401


async def test_two_factor_sensitive_changes_require_recent_proof(
    http_client, factor_account, settings
):
    _, enrollment = await enroll(http_client, factor_account)
    assert not (await http_client.get("/api/v1/auth/2fa/status")).json()[
        "verification_required"
    ]
    payload = jwt.decode(
        enrollment["access_token"], settings.auth_secret_key, ["HS256"]
    )
    expired_login = dict(payload)
    expired_login["auth_time"] = (
        int(time()) - settings.auth_credetials_update_threshold - 1
    )
    assert (
        await http_client.get(
            "/api/v1/auth/2fa/status",
            headers={"Authorization": f"Bearer {create_access_token(expired_login)}"},
        )
    ).json()["verification_required"]
    payload["mfa_time"] = int(time()) - settings.auth_credetials_update_threshold - 1
    headers = {"Authorization": f"Bearer {create_access_token(payload)}"}
    assert (await http_client.get("/api/v1/auth/2fa/status", headers=headers)).json()[
        "verification_required"
    ]
    assert (await http_client.get("/api/v1/auth", headers=headers)).status_code == 200
    denied = await http_client.post("/api/v1/auth/2fa/recovery", headers=headers)
    assert denied.status_code == 401
    assert denied.headers["two-factor-required"] == "true"
    verified = await http_client.post(
        "/api/v1/auth/2fa/verify",
        headers=headers,
        json={"code": enrollment["recovery_codes"][0]},
    )
    assert verified.status_code == 200
    assert not (await http_client.get("/api/v1/auth/2fa/status")).json()[
        "verification_required"
    ]
    assert (await http_client.post("/api/v1/auth/2fa/recovery")).status_code == 200


async def test_two_factor_password_reset_does_not_bypass(http_client, factor_account):
    await enroll(http_client, factor_account)
    key = await api_users_reset_password(factor_account.id)
    response = await http_client.put(
        "/api/v1/auth/reset",
        json={
            "reset_key": key,
            "password": "changed1234",
            "password_repeat": "changed1234",
        },
    )
    assert response.json()["two_factor_required"]
    assert "access_token" not in response.json()
    assert (await http_client.get("/api/v1/auth")).status_code == 401


async def test_two_factor_sso_does_not_bypass(http_client, factor_account):
    factor_account.email = f"{factor_account.id}@example.com"
    await update_account(factor_account)
    await enroll(http_client, factor_account)
    response = await _handle_sso_login(
        OpenID.parse_obj({"email": factor_account.email})
    )
    assert response.headers["location"] == "/2fa"
    cookies = response.headers.getlist("set-cookie")
    assert any(cookie.startswith("two_factor_challenge=") for cookie in cookies)
    assert not any(
        cookie.startswith("cookie_access_token=") and "Max-Age=0" not in cookie
        for cookie in cookies
    )


async def test_two_factor_nostr_does_not_bypass(http_client, factor_account, settings):
    private_key = PrivateKey(secrets.token_bytes(32))
    factor_account.pubkey = private_key.public_key.format().hex()[2:]
    await update_account(factor_account)
    await enroll(http_client, factor_account)
    settings.auth_allowed_methods.append(AuthMethods.nostr_auth_nip98.value)
    event = sign_event(
        {
            "kind": 27235,
            "created_at": int(time()),
            "content": "",
            "tags": [["u", "http://localhost:5000/nostr"], ["method", "POST"]],
        },
        factor_account.pubkey,
        private_key,
    )
    encoded = base64.b64encode(json.dumps(event).encode()).decode()
    response = await http_client.post(
        "/api/v1/auth/nostr", headers={"Authorization": f"nostr {encoded}"}
    )
    assert response.json()["two_factor_required"]
    assert (await http_client.get("/api/v1/auth")).status_code == 401


async def test_two_factor_wallet_keys_continue_to_work(http_client, factor_account):
    await enroll(http_client, factor_account)
    wallet = (await http_client.get("/api/v1/auth")).json()["wallets"][0]
    http_client.cookies.clear()
    assert (
        await http_client.get("/api/v1/wallet", headers={"X-Api-Key": wallet["inkey"]})
    ).status_code == 200
    assert (
        await http_client.get(
            "/api/v1/auth/2fa/status", headers={"X-Api-Key": wallet["adminkey"]}
        )
    ).status_code == 401


async def test_two_factor_policy_survives_restart_and_global_off(
    http_client, factor_account, settings
):
    initial = await sync_two_factor_policy()
    _, enrollment = await enroll(http_client, factor_account)
    assert await sync_two_factor_policy() == initial
    settings.lnbits_two_factor_enabled = False
    assert await sync_two_factor_policy() != initial
    settings.lnbits_two_factor_enabled = True
    assert await sync_two_factor_policy() != initial
    assert (
        await http_client.get(
            "/api/v1/auth",
            headers={"Authorization": f"Bearer {enrollment['access_token']}"},
        )
    ).status_code == 401


async def test_two_factor_key_and_methods_validation(
    http_client, factor_account, settings
):
    settings.lnbits_admin_users = [factor_account.id]
    await login(http_client, factor_account)
    for field in ("totp_encryption_key", "__dict__", "__fields__"):
        assert (
            await http_client.get(
                "/admin/api/v1/settings/default", params={"field_name": field}
            )
        ).status_code == 403
    settings.lnbits_two_factor_enabled = False
    settings.totp_encryption_key = ""
    assert (
        await http_client.patch(
            "/admin/api/v1/settings", json={"lnbits_two_factor_enabled": True}
        )
    ).status_code == 503
    settings.totp_encryption_key = "ab" * 32
    assert (
        await http_client.patch(
            "/admin/api/v1/settings",
            json={"lnbits_two_factor_enabled": True, "lnbits_two_factor_methods": []},
        )
    ).status_code == 400
