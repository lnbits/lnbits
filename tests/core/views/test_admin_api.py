import pytest

from lnbits.settings import settings


@pytest.mark.asyncio
async def test_admin_get_settings_permission_denied(client, to_user):
    response = await client.get(f"/admin/api/v1/settings/?usr={to_user.id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_get_settings(client, to_superuser):
    response = await client.get(f"/admin/api/v1/settings/?usr={to_superuser.id}")
    assert response.status_code == 200
    result = response.json()
    assert "super_user" not in result


@pytest.mark.asyncio
async def test_admin_update_settings(client, to_superuser):
    new_site_title = "UPDATED SITETITLE"
    response = await client.put(
        f"/admin/api/v1/settings/?usr={to_superuser.id}",
        json={"lnbits_site_title": new_site_title},
    )
    assert response.status_code == 200
    result = response.json()
    assert "status" in result
    assert result.get("status") == "Success"
    assert settings.lnbits_site_title == new_site_title


@pytest.mark.asyncio
async def test_admin_update_noneditable_settings(client, to_superuser):
    response = await client.put(
        f"/admin/api/v1/settings/?usr={to_superuser.id}",
        json={"super_user": "UPDATED"},
    )
    assert response.status_code == 400
