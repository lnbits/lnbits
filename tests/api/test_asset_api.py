from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile
from httpx import AsyncClient
from PIL import Image
from starlette.datastructures import Headers

from lnbits.core.crud.assets import get_user_asset
from lnbits.core.services.assets import create_user_asset


def _png_bytes() -> bytes:
    image = Image.new("RGB", (32, 32), color="blue")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _upload_file(contents: bytes, filename: str, content_type: str) -> UploadFile:
    return UploadFile(
        BytesIO(contents),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


async def _user_headers(client: AsyncClient, user_id: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/usr", json={"usr": user_id})
    client.cookies.clear()
    access_token = response.json()["access_token"]
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-type": "application/json",
    }


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
    assert data.headers["content-disposition"] == 'inline; filename="note.txt"'

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

    missing = await client.get(f"/api/v1/assets/{asset['id']}", headers=user_headers_from)
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
        _upload_file(_png_bytes(), f"private_{uuid4().hex[:8]}.png", "image/png"),
        is_public=False,
    )
    other_user_headers = await _user_headers(client, to_user.id)

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

    thumbnail = await client.get(f"/api/v1/assets/{private_asset.id}/thumbnail")
    assert thumbnail.status_code == 200
    assert thumbnail.content
    assert thumbnail.headers["content-type"] == "image/png"


@pytest.mark.anyio
async def test_asset_api_validates_uploads_and_missing_assets(
    client: AsyncClient,
    user_headers_from: dict[str, str],
):
    invalid = await client.post(
        "/api/v1/assets",
        headers={"Authorization": user_headers_from["Authorization"]},
        files={"file": ("payload.exe", b"boom", "application/x-msdownload")},
    )
    assert invalid.status_code == 400
    assert "not allowed" in invalid.json()["detail"]

    missing = await client.delete(
        f"/api/v1/assets/{uuid4().hex}",
        headers=user_headers_from,
    )
    assert missing.status_code == 404

    missing_thumb = await client.get(f"/api/v1/assets/{uuid4().hex}/thumbnail")
    assert missing_thumb.status_code == 404

    stored = await create_user_asset(
        "missing-user-check",
        _upload_file(b"content", "content.txt", "text/plain"),
        is_public=True,
    )
    fetched = await get_user_asset("missing-user-check", stored.id)
    assert fetched is not None
