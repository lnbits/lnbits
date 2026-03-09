from pathlib import Path

import pytest
from httpx import AsyncClient

from lnbits.server import server_restart
from lnbits.settings import Settings


@pytest.mark.anyio
async def test_admin_get_settings_permission_denied(client, from_user):
    response = await client.get(f"/admin/api/v1/settings?usr={from_user.id}")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_admin_get_settings(client: AsyncClient, superuser_token: str):
    response = await client.get(
        "/admin/api/v1/settings",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    result = response.json()
    assert "super_user" not in result


@pytest.mark.anyio
async def test_admin_update_settings(
    client: AsyncClient, superuser_token: str, settings: Settings
):
    new_site_title = "UPDATED SITETITLE"
    response = await client.put(
        "/admin/api/v1/settings",
        json={"lnbits_site_title": new_site_title},
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    result = response.json()
    assert "status" in result
    assert result.get("status") == "Success"
    assert settings.lnbits_site_title == new_site_title


@pytest.mark.anyio
async def test_admin_update_noneditable_settings(
    client: AsyncClient,
    superuser_token: str,
):
    response = await client.put(
        "/admin/api/v1/settings",
        json={"super_user": "UPDATED"},
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_admin_audit_monitor_and_test_email(
    client: AsyncClient, superuser_token: str, mocker
):
    mocker.patch(
        "lnbits.core.views.admin_api.get_balance_delta",
        mocker.AsyncMock(
            return_value={"lnbits_balance_sats": 21, "node_balance_sats": 13}
        ),
    )
    mocker.patch(
        "lnbits.core.views.admin_api.send_email_notification",
        mocker.AsyncMock(return_value={"status": "queued"}),
    )

    audit = await client.get(
        "/admin/api/v1/audit",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert audit.status_code == 200
    assert audit.json()["lnbits_balance_sats"] == 21

    monitor = await client.get(
        "/admin/api/v1/monitor",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert monitor.status_code == 200
    assert "invoice_listeners" in monitor.json()

    test_email = await client.get(
        "/admin/api/v1/testemail",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert test_email.status_code == 200
    assert test_email.json()["status"] == "queued"


@pytest.mark.anyio
async def test_admin_partial_reset_restart_and_backup(
    client: AsyncClient,
    superuser_token: str,
    settings: Settings,
    tmp_path,
):
    response = await client.patch(
        "/admin/api/v1/settings",
        json={"lnbits_site_title": "PATCHED TITLE"},
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Success"

    default_value = await client.get(
        "/admin/api/v1/settings/default",
        params={"field_name": "lnbits_site_title"},
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert default_value.status_code == 200
    assert "default_value" in default_value.json()

    backup_path = Path("lnbits-backup.zip")
    original_data_folder = settings.lnbits_data_folder

    try:
        data_folder = tmp_path / "backup_data"
        data_folder.mkdir(parents=True, exist_ok=True)
        (data_folder / "sample.txt").write_text("backup me")
        settings.lnbits_data_folder = str(data_folder)

        backup = await client.get(
            "/admin/api/v1/backup",
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert backup.status_code == 200
        assert backup.headers["content-type"] == "application/zip"
        assert backup.content.startswith(b"PK")
        assert backup_path.is_file()
    finally:
        settings.lnbits_data_folder = original_data_folder
        backup_path.unlink(missing_ok=True)

    server_restart.clear()
    restart = await client.get(
        "/admin/api/v1/restart",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert restart.status_code == 200
    assert restart.json()["status"] == "Success"
    assert server_restart.is_set() is True
    server_restart.clear()


@pytest.mark.anyio
async def test_admin_delete_settings_requires_superuser(
    client: AsyncClient, superuser_token: str
):
    server_restart.clear()
    response = await client.delete(
        "/admin/api/v1/settings",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    assert server_restart.is_set() is True
    server_restart.clear()
