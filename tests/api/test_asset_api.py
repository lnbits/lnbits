from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.crud.assets import get_user_asset
from lnbits.core.services.assets import create_user_asset
from tests.helpers import get_png_bytes, get_user_token_headers, make_upload_file


@pytest.mark.anyio
async def test_asset_api_upload_list_update_and_delete(
    client: AsyncClient,
    user_headers_from: dict[str, str],
):
    upload = await client.post(
        "/api/v1/assets?public_asset=false",
        headers={"Authorization": user_headers_from["Authorization"]},
        files={"file": ("note.txt", b"hello world", "text/plain")},
    )
    assert upload.status_code == 200
    asset = upload.json()
    assert asset["name"] == "note.txt"
    assert asset["is_public"] is False

    page = await client.get("/api/v1/assets/paginated", headers=user_headers_from)
    assert page.status_code == 200
    assert any(item["id"] == asset["id"] for item in page.json()["data"])

    info = await client.get(f"/api/v1/assets/{asset['id']}", headers=user_headers_from)
    assert info.status_code == 200
    assert info.json()["name"] == "note.txt"

    data = await client.get(
        f"/api/v1/assets/{asset['id']}/data", headers=user_headers_from
    )
    assert data.status_code == 200
    assert data.content == b"hello world"
    assert data.headers["content-disposition"] == 'attachment; filename="note.txt"'
    assert data.headers["x-content-type-options"] == "nosniff"
    assert data.headers["content-security-policy"].startswith("sandbox")

    updated = await client.put(
        f"/api/v1/assets/{asset['id']}",
        headers=user_headers_from,
        json={"name": "renamed.txt", "is_public": True},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "renamed.txt"
    assert updated.json()["is_public"] is True

    public_data = await client.get(f"/api/v1/assets/{asset['id']}/data")
    assert public_data.status_code == 200
    assert public_data.content == b"hello world"

    deleted = await client.delete(
        f"/api/v1/assets/{asset['id']}", headers=user_headers_from
    )
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True

    missing = await client.get(
        f"/api/v1/assets/{asset['id']}", headers=user_headers_from
    )
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_asset_api_enforces_visibility_and_supports_admin_updates(
    client: AsyncClient,
    from_user,
    to_user,
    superuser_token: str,
):
    private_asset = await create_user_asset(
        from_user.id,
        make_upload_file(
            get_png_bytes(),
            filename=f"private_{uuid4().hex[:8]}.png",
            content_type="image/png",
        ),
        is_public=False,
    )
    other_user_headers = await get_user_token_headers(client, to_user.id)

    anonymous = await client.get(f"/api/v1/assets/{private_asset.id}/data")
    assert anonymous.status_code == 404

    wrong_user = await client.get(
        f"/api/v1/assets/{private_asset.id}/data", headers=other_user_headers
    )
    assert wrong_user.status_code == 404

    admin_updated = await client.put(
        f"/api/v1/assets/{private_asset.id}",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"is_public": True, "name": "admin-visible.png"},
    )
    assert admin_updated.status_code == 200
    assert admin_updated.json()["is_public"] is True
    assert admin_updated.json()["name"] == "admin-visible.png"

    image_data = await client.get(f"/api/v1/assets/{private_asset.id}/data")
    assert image_data.status_code == 200
    assert image_data.headers["content-type"] == "image/png"
    assert image_data.headers["content-disposition"] == (
        'inline; filename="admin-visible.png"'
    )
    assert image_data.headers["x-content-type-options"] == "nosniff"

    thumbnail = await client.get(f"/api/v1/assets/{private_asset.id}/thumbnail")
    assert thumbnail.status_code == 200
    assert thumbnail.content
    assert thumbnail.headers["content-type"] == "image/png"
    assert thumbnail.headers["content-disposition"] == (
        'inline; filename="admin-visible.png"'
    )


@pytest.mark.anyio
async def test_asset_api_blocks_xsl_uploads(
    client: AsyncClient,
    user_headers_from: dict[str, str],
):
    payload = (
        b'<?xml version="1.0"?>'
        b'<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
        b'<xsl:template match="/">'
        b"<script>alert(1)</script>"
        b"</xsl:template>"
        b"</xsl:stylesheet>"
    )

    blocked = await client.post(
        "/api/v1/assets",
        headers={"Authorization": user_headers_from["Authorization"]},
        files={"file": ("payload.xsl", payload, "text/xml")},
    )

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "XSL assets are not allowed."


@pytest.mark.anyio
async def test_asset_api_validates_uploads_and_missing_assets(
    client: AsyncClient,
    to_user,
    user_headers_from: dict[str, str],
):
    invalid = await client.post(
        "/api/v1/assets",
        headers={"Authorization": user_headers_from["Authorization"]},
        files={"file": ("payload.exe", b"boom", "application/x-msdownload")},
    )
    assert invalid.status_code == 400
    assert "not allowed" in invalid.json()["detail"]

    fake_image_headers = await get_user_token_headers(client, to_user.id)
    fake_image = await client.post(
        "/api/v1/assets",
        headers={"Authorization": fake_image_headers["Authorization"]},
        files={"file": ("fake.png", b"<root></root>", "image/png")},
    )
    assert fake_image.status_code == 400
    assert "does not match declared file type" in fake_image.json()["detail"]

    missing = await client.delete(
        f"/api/v1/assets/{uuid4().hex}",
        headers=user_headers_from,
    )
    assert missing.status_code == 404

    missing_thumb = await client.get(f"/api/v1/assets/{uuid4().hex}/thumbnail")
    assert missing_thumb.status_code == 404

    stored = await create_user_asset(
        "missing-user-check",
        make_upload_file(b"content", filename="content.txt", content_type="text/plain"),
        is_public=True,
    )
    fetched = await get_user_asset("missing-user-check", stored.id)
    assert fetched is not None
