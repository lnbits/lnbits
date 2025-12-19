import base64
import io
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from lnbits.core.crud.assets import create_asset, get_user_assets_count
from lnbits.core.models.assets import Asset
from lnbits.settings import settings


async def create_user_asset(user_id: str, file: UploadFile, is_public: bool) -> Asset:
    if not file.content_type:
        raise ValueError("File must have a content type.")
    if file.content_type.lower() not in settings.lnbits_assets_allowed_mime_types:
        raise ValueError(f"File type '{file.content_type}' not allowed.")

    if not settings.is_unlimited_assets_user(user_id):
        user_assets_count = await get_user_assets_count(user_id)
        if user_assets_count >= settings.lnbits_max_assets_per_user:
            raise ValueError(
                f"Max upload count of {settings.lnbits_max_assets_per_user} exceeded."
            )

    contents = await file.read()
    if len(contents) > settings.lnbits_max_asset_size_mb * 1024 * 1024:
        raise ValueError(
            f"File limit of {settings.lnbits_max_asset_size_mb}MB exceeded."
        )

    image = Image.open(io.BytesIO(contents))

    thumbnail_width = min(256, settings.lnbits_asset_thumbnail_width)
    thumbnail_height = min(256, settings.lnbits_asset_thumbnail_height)
    image.thumbnail((thumbnail_width, thumbnail_height))

    # Save thumbnail to an in-memory buffer
    thumb_buffer = io.BytesIO()
    thumbnail_format = settings.lnbits_asset_thumbnail_format or "PNG"
    image.save(thumb_buffer, format=thumbnail_format)
    thumb_buffer.seek(0)

    asset = Asset(
        id=uuid4().hex,
        user_id=user_id,
        mime_type=file.content_type,
        is_public=is_public,
        name=file.filename or "unnamed",
        size_bytes=len(contents),
        thumbnail_base64=base64.b64encode(thumb_buffer.getvalue()).decode("utf-8"),
        data=contents,
    )

    await create_asset(asset)
    return asset
