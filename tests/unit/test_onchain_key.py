import base64
import json
import stat
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from lnbits.core.services import onchain
from lnbits.core.views import admin_api
from lnbits.decorators import check_admin, check_super_user
from lnbits.settings import Settings


@pytest.fixture
def key_store(monkeypatch, tmp_path, settings):
    monkeypatch.setattr(settings, "lnbits_data_folder", str(tmp_path))
    monkeypatch.setattr(settings, "lnbits_onchain_master_key", None)
    monkeypatch.setattr(settings, "lnbits_allow_onchain_payments", False)
    monkeypatch.delenv("WATCHONLY_MASTER_KEY", raising=False)
    records = {}

    async def get_record(name):
        return SimpleNamespace(value=records[name]) if name in records else None

    async def set_record(name, value):
        records[name] = value

    monkeypatch.setattr(onchain, "get_settings_field", get_record)
    monkeypatch.setattr(onchain, "set_settings_field", set_record)
    return records


@pytest.mark.anyio
async def test_generate_persist_confirm_and_disable(key_store, settings):
    assert not (await onchain.onchain_key_status()).configured
    status = await onchain.setup_onchain_key()
    key = onchain.read_onchain_key()
    assert len(key) == 32
    assert stat.S_IMODE(onchain.key_path().stat().st_mode) == 0o600
    assert status.configured and not status.backup_confirmed
    assert (await onchain.setup_onchain_key()).fingerprint == status.fingerprint
    assert onchain.read_onchain_key() == key
    assert base64.b64encode(key).decode() not in json.dumps(key_store)
    settings.lnbits_allow_onchain_payments = True
    with pytest.raises(ValueError, match="back up"):
        await onchain.require_onchain_payments()
    with pytest.raises(ValueError, match="does not match"):
        await onchain.confirm_onchain_key_backup("wrong")
    assert status.fingerprint
    await onchain.confirm_onchain_key_backup(status.fingerprint)
    await onchain.require_onchain_payments()
    settings.lnbits_allow_onchain_payments = False
    with pytest.raises(ValueError, match="disabled"):
        await onchain.require_onchain_payments()
    assert onchain.read_onchain_key() == key


@pytest.mark.anyio
async def test_lost_key_requires_original_backup(key_store):
    status = await onchain.setup_onchain_key()
    encoded = base64.b64encode(onchain.read_onchain_key()).decode()
    assert status.fingerprint
    await onchain.confirm_onchain_key_backup(status.fingerprint)
    onchain.key_path().unlink()
    assert not (await onchain.onchain_key_status()).configured
    with pytest.raises(ValueError, match="original"):
        await onchain.setup_onchain_key()
    with pytest.raises(ValueError, match="does not match"):
        await onchain.setup_onchain_key(base64.b64encode(bytes(32)).decode())
    restored = await onchain.setup_onchain_key(encoded)
    assert restored.configured and restored.backup_confirmed
    assert restored.fingerprint == status.fingerprint


@pytest.mark.anyio
async def test_invalid_and_replaced_keys_fail_closed(key_store):
    status = await onchain.setup_onchain_key()
    original = onchain.key_path().read_text()
    onchain.key_path().write_text("invalid")
    assert not (await onchain.onchain_key_status()).configured
    with pytest.raises(ValueError):
        await onchain.setup_onchain_key()
    onchain.key_path().write_text(base64.b64encode(bytes(32)).decode())
    assert not (await onchain.onchain_key_status()).configured
    with pytest.raises(ValueError):
        await onchain.setup_onchain_key(original)
    assert key_store[onchain.KEY_RECORD]["fingerprint"] == status.fingerprint


@pytest.mark.anyio
async def test_environment_key_and_legacy_migration(key_store, monkeypatch, settings):
    encoded = base64.b64encode(bytes(range(32))).decode()
    monkeypatch.setenv("WATCHONLY_MASTER_KEY", encoded)
    status = await onchain.setup_onchain_key()
    assert status.source == "environment"
    assert not onchain.key_path().exists()
    # Restore a recovery copy to migrate away from environment configuration.
    await onchain.setup_onchain_key(encoded)
    monkeypatch.delenv("WATCHONLY_MASTER_KEY")
    assert (await onchain.onchain_key_status()).source == "file"
    settings.lnbits_onchain_master_key = SecretStr(base64.b64encode(bytes(32)).decode())
    assert not (await onchain.onchain_key_status()).configured
    assert "lnbits_onchain_master_key" not in settings.dict()


def test_env_file_key_loading(tmp_path, monkeypatch):
    monkeypatch.delenv("LNBITS_ONCHAIN_MASTER_KEY", raising=False)
    monkeypatch.delenv("WATCHONLY_MASTER_KEY", raising=False)
    encoded = base64.b64encode(bytes(range(32))).decode()
    env = tmp_path / ".env"
    env.write_text(f"LNBITS_ONCHAIN_MASTER_KEY={encoded}\n")
    loaded = Settings(_env_file=env)  # pyright: ignore[reportCallIssue]
    assert loaded.lnbits_onchain_master_key
    assert loaded.lnbits_onchain_master_key.get_secret_value() == encoded
    assert encoded not in loaded.json()


@pytest.mark.anyio
async def test_admin_key_api_and_settings_gate(key_store, monkeypatch, settings):
    app = FastAPI()
    app.include_router(admin_api.admin_router)
    account = SimpleNamespace(is_super_user=True, username="admin")

    async def admin():
        return account

    async def super_user():
        if not account.is_super_user:
            raise HTTPException(403, "Super user required")
        return account

    app.dependency_overrides[check_admin] = admin
    app.dependency_overrides[check_super_user] = super_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/admin/api/v1/settings", json={"lnbits_allow_onchain_payments": True}
        )
        assert response.status_code == 409
        generated = await client.post("/admin/api/v1/onchain/key")
        assert generated.status_code == 200
        backup = await client.post("/admin/api/v1/onchain/key/backup")
        assert backup.status_code == 200
        assert backup.headers["cache-control"] == "no-store"
        secret = backup.json()["key"]
        assert secret not in generated.text
        assert secret not in (await client.get("/admin/api/v1/onchain/key")).text
        confirmed = await client.post(
            "/admin/api/v1/onchain/key/confirm",
            headers={"X-Onchain-Key-Fingerprint": backup.json()["fingerprint"]},
        )
        assert confirmed.json()["backup_confirmed"] is True
        onchain.key_path().unlink()
        wrong = await client.post(
            "/admin/api/v1/onchain/key",
            headers={"X-Onchain-Recovery-Key": base64.b64encode(bytes(32)).decode()},
        )
        assert wrong.status_code == 409
        restored = await client.post(
            "/admin/api/v1/onchain/key", headers={"X-Onchain-Recovery-Key": secret}
        )
        assert restored.status_code == 200
        assert secret not in restored.text
        account.is_super_user = False
        for method, path in [
            ("GET", ""),
            ("POST", ""),
            ("POST", "/backup"),
            ("POST", "/confirm"),
        ]:
            denied = await client.request(method, f"/admin/api/v1/onchain/key{path}")
            assert denied.status_code == 403
        for method in ("PUT", "PATCH"):
            denied = await client.request(
                method,
                "/admin/api/v1/settings",
                json={"lnbits_allow_onchain_payments": True},
            )
            assert denied.status_code == 403
