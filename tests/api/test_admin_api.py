import pytest
from httpx import AsyncClient

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
