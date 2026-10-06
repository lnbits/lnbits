import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.db import db
from lnbits.core.models.users import Account
from lnbits.core.services.users import create_user_account
from lnbits.helpers import sha256s
from lnbits.settings import Settings


async def _new_account() -> Account:
    suffix = uuid4().hex[:8]
    account = Account(
        id=uuid4().hex,
        username=f"reset_{suffix}",
        email=f"reset_{suffix}@lnbits.com",
    )
    account.hash_password("secret1234")
    await create_user_account(account)
    return account


async def _issue_key(
    client: AsyncClient, user_id: str, token: str, *, expiry_minutes: int | None = None
):
    query = f"?expiry_minutes={expiry_minutes}" if expiry_minutes is not None else ""
    return await client.put(
        f"/users/api/v1/user/{user_id}/reset_password{query}",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _reset(client: AsyncClient, key: str):
    return await client.put(
        "/api/v1/auth/reset",
        json={
            "reset_key": key,
            "password": "secret0000",
            "password_repeat": "secret0000",
        },
    )


@pytest.mark.anyio
async def test_reset_key_expiry_limits(
    http_client: AsyncClient, superuser_token: str, admin_user, settings: Settings
):
    regular = await _new_account()
    for expiry in (1, 2, 5, 15, 30, 60):
        response = await _issue_key(
            http_client, regular.id, superuser_token, expiry_minutes=expiry
        )
        assert response.status_code == 200
        key = response.json()
        assert key.startswith("reset_key_")
        row: dict = await db.fetchone(
            "SELECT password_reset_hash, password_reset_issued_at, "
            "password_reset_expires_at FROM accounts WHERE id = :id",
            {"id": regular.id},
        )
        assert row["password_reset_hash"] == sha256s(key)
        assert row["password_reset_hash"] != key
        assert row["password_reset_expires_at"] - row["password_reset_issued_at"] == (
            expiry * 60
        )

    response = await _issue_key(
        http_client, admin_user.id, superuser_token, expiry_minutes=2
    )
    assert response.status_code == 200

    response = await _issue_key(http_client, regular.id, superuser_token)
    assert response.status_code == 200
    defaults: dict = await db.fetchone(
        "SELECT password_reset_issued_at, password_reset_expires_at "
        "FROM accounts WHERE id = :id",
        {"id": regular.id},
    )
    assert (
        defaults["password_reset_expires_at"] - defaults["password_reset_issued_at"]
        == 120
    )

    for expiry in (0, -1, 61):
        response = await _issue_key(
            http_client, regular.id, superuser_token, expiry_minutes=expiry
        )
        assert response.status_code == 400

    response = await _issue_key(
        http_client, admin_user.id, superuser_token, expiry_minutes=3
    )
    assert response.status_code == 400

    response = await _issue_key(
        http_client, settings.super_user, superuser_token, expiry_minutes=1
    )
    assert response.status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("expiry", "elapsed", "promoted", "expected"),
    [(60, 121, False, 200), (1, 60, False, 400), (60, 121, True, 400)],
)
async def test_reset_expiry_is_independent_of_recent_login(
    http_client: AsyncClient,
    superuser_token: str,
    settings: Settings,
    monkeypatch,
    expiry: int,
    elapsed: int,
    promoted: bool,
    expected: int,
):
    target = await _new_account()
    issued = await _issue_key(
        http_client, target.id, superuser_token, expiry_minutes=expiry
    )
    row: dict = await db.fetchone(
        "SELECT password_reset_issued_at FROM accounts WHERE id = :id",
        {"id": target.id},
    )
    settings.auth_credetials_update_threshold = 1
    if promoted:
        settings.lnbits_admin_users.append(target.id)
    monkeypatch.setattr(
        "lnbits.core.crud.users.time", lambda: row["password_reset_issued_at"] + elapsed
    )
    response = await _reset(http_client, issued.json())
    assert response.status_code == expected


@pytest.mark.anyio
async def test_reset_key_issuance_requires_superuser(
    http_client: AsyncClient, superuser_token: str, admin_user, settings: Settings
):
    target = await _new_account()
    response = await http_client.put(f"/users/api/v1/user/{target.id}/reset_password")
    assert response.status_code == 401

    regular_token_response = await http_client.post(
        "/api/v1/auth",
        json={"username": target.username, "password": "secret1234"},
    )
    regular_token = regular_token_response.json()["access_token"]
    response = await _issue_key(http_client, target.id, regular_token)
    assert response.status_code == 403

    admin_login = await http_client.post(
        "/api/v1/auth",
        json={"username": admin_user.username, "password": "secret1234"},
    )
    assert admin_login.status_code == 200
    response = await _issue_key(
        http_client, target.id, admin_login.json()["access_token"]
    )
    assert response.status_code == 403

    response = await _issue_key(http_client, "missing-account", superuser_token)
    assert response.status_code == 404


@pytest.mark.anyio
async def test_reset_key_expired_replaced_reused_and_concurrent(
    http_client: AsyncClient, superuser_token: str
):
    target = await _new_account()
    response = await _issue_key(http_client, target.id, superuser_token)
    old_key = response.json()
    await db.execute(
        "UPDATE accounts SET password_reset_expires_at = 0 WHERE id = :id",
        {"id": target.id},
    )
    response = await _reset(http_client, old_key)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset key."

    response = await _issue_key(http_client, target.id, superuser_token)
    replaced_key = response.json()
    response = await _issue_key(http_client, target.id, superuser_token)
    current_key = response.json()
    for key in (replaced_key, old_key):
        response = await _reset(http_client, key)
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid or expired reset key."

    attempts = await asyncio.gather(
        _reset(http_client, current_key), _reset(http_client, current_key)
    )
    assert sorted(response.status_code for response in attempts) == [200, 400]
    response = await _reset(http_client, current_key)
    assert response.status_code == 400


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("key", "repeat", "detail"),
    [
        ("not-a-reset-key", "secret0000", "This is not a reset key."),
        ("reset_key_unknown", "secret0000", "Invalid or expired reset key."),
        ("reset_key_unknown", "secret1111", "Passwords do not match."),
    ],
)
async def test_invalid_reset_request(
    http_client: AsyncClient, key: str, repeat: str, detail: str
):
    response = await http_client.put(
        "/api/v1/auth/reset",
        json={"reset_key": key, "password": "secret0000", "password_repeat": repeat},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == detail


@pytest.mark.anyio
async def test_password_change_invalidates_reset_key_but_failed_change_does_not(
    http_client: AsyncClient, superuser_token: str
):
    target = await _new_account()
    issued = await _issue_key(http_client, target.id, superuser_token)
    key = issued.json()
    login = await http_client.post(
        "/api/v1/auth",
        json={"username": target.username, "password": "secret1234"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    change = {
        "username": target.username,
        "user_id": target.id,
        "password_old": "wrong-password",
        "password": "secret0000",
        "password_repeat": "secret0000",
    }
    for old_password in (None, "wrong-password"):
        change["password_old"] = old_password
        response = await http_client.put(
            "/api/v1/auth/password", headers=headers, json=change
        )
        assert response.status_code == 400

    response = await _reset(http_client, key)
    assert response.status_code == 200

    issued = await _issue_key(http_client, target.id, superuser_token)
    key = issued.json()
    login = await http_client.post(
        "/api/v1/auth",
        json={"username": target.username, "password": "secret0000"},
    )
    change.update(
        password_old="secret0000", password="secret1111", password_repeat="secret1111"
    )
    response = await http_client.put(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json=change,
    )
    assert response.status_code == 200
    response = await _reset(http_client, key)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset key."
