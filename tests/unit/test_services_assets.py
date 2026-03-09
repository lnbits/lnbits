from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile
from PIL import Image
from pytest_mock.plugin import MockerFixture
from starlette.datastructures import Headers

from lnbits.core.crud import create_account
from lnbits.core.crud.assets import get_user_asset, get_user_assets_count
from lnbits.core.models import Account
from lnbits.core.services.assets import create_user_asset, thumbnail_from_bytes
from lnbits.settings import Settings


async def _create_user() -> str:
    user_id = uuid4().hex
    await create_account(Account(id=user_id, username=f"user_{user_id[:8]}"))
    return user_id


def _make_upload_file(
    contents: bytes,
    *,
    filename: str,
    content_type: str | None,
) -> UploadFile:
    headers = (
        Headers({"content-type": content_type}) if content_type is not None else None
    )
    return UploadFile(BytesIO(contents), filename=filename, headers=headers)


@pytest.mark.anyio
async def test_create_user_asset_validates_upload_constraints(
    settings: Settings, mocker: MockerFixture
):
    file_without_type = _make_upload_file(b"hello", filename="a.txt", content_type=None)
    with pytest.raises(ValueError, match="File must have a content type."):
        await create_user_asset("user-1", file_without_type, is_public=False)

    bad_type = _make_upload_file(
        b"hello",
        filename="bad.bin",
        content_type="application/x-msdownload",
    )
    with pytest.raises(
        ValueError, match="File type 'application/x-msdownload' not allowed."
    ):
        await create_user_asset("user-1", bad_type, is_public=False)

    original_max_assets = settings.lnbits_max_assets_per_user
    original_max_size = settings.lnbits_max_asset_size_mb
    original_no_limit_users = list(settings.lnbits_assets_no_limit_users)
    try:
        settings.lnbits_max_assets_per_user = 1
        settings.lnbits_max_asset_size_mb = 1
        settings.lnbits_assets_no_limit_users = []
        limited_user = await _create_user()
        allowed_type = _make_upload_file(
            b"hello", filename="ok.txt", content_type="text/plain"
        )
        await create_user_asset(limited_user, allowed_type, is_public=False)

        blocked_by_count = _make_upload_file(
            b"again",
            filename="again.txt",
            content_type="text/plain",
        )
        with pytest.raises(ValueError, match="Max upload count of 1 exceeded."):
            await create_user_asset(limited_user, blocked_by_count, is_public=False)

        settings.lnbits_max_asset_size_mb = 0.000001
        oversized_user = await _create_user()
        large_file = _make_upload_file(
            b"0123456789",
            filename="ok.txt",
            content_type="text/plain",
        )
        with pytest.raises(ValueError, match="File limit of 1e-06MB exceeded."):
            await create_user_asset(oversized_user, large_file, is_public=False)
    finally:
        settings.lnbits_max_assets_per_user = original_max_assets
        settings.lnbits_max_asset_size_mb = original_max_size
        settings.lnbits_assets_no_limit_users = original_no_limit_users


@pytest.mark.anyio
async def test_create_user_asset_success(mocker: MockerFixture):
    user_id = await _create_user()
    mocker.patch(
        "lnbits.core.services.assets.thumbnail_from_bytes",
        return_value=None,
    )
    file = _make_upload_file(b"hello", filename="hello.txt", content_type="text/plain")

    asset = await create_user_asset(user_id, file, is_public=True)
    stored = await get_user_asset(user_id, asset.id)

    assert asset.id
    assert asset.user_id == user_id
    assert asset.name == "hello.txt"
    assert asset.size_bytes == 5
    assert asset.data == b"hello"
    assert asset.is_public is True
    assert stored is not None
    assert stored.id == asset.id
    assert stored.data == b"hello"
    assert await get_user_assets_count(user_id) == 1


def test_thumbnail_from_bytes_success_and_failure():
    image = Image.new("RGB", (512, 512), color="red")
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    thumbnail = thumbnail_from_bytes(buffer.getvalue())

    assert thumbnail is not None
    assert isinstance(thumbnail.getvalue(), bytes)
    assert thumbnail_from_bytes(b"not-an-image") is None
