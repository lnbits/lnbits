import base64
import io
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from lnbits.core.crud.assets import create_asset, get_user_assets_count
from lnbits.core.models.assets import Asset


async def create_user_asset(user_id: str, file: UploadFile, is_public: bool) -> Asset:
    user_assets_count = await get_user_assets_count(user_id)
    # todo: settings for max assets per user
    if user_assets_count >= 200:
        raise ValueError("Reached maximum number of allowed asset uploads.")
    if not file.content_type:
        raise ValueError("Image file must have a content type.")
    # todo: settings for allowed mime types
    if not file.content_type.startswith("image/"):
        raise ValueError("Only image files are allowed.")
    contents = await file.read()
    # todo: settings for max file size
    if len(contents) > 5 * 1024 * 1024:
        raise ValueError("File size exceeds the maximum limit of 5MB.")

    # Open the image from bytes
    image = Image.open(io.BytesIO(contents))
    # Create thumbnail (preserves aspect ratio)
    # todo: settings for thumbnail size
    image.thumbnail((128, 128))
    # Save thumbnail to an in-memory buffer
    thumb_buffer = io.BytesIO()
    # todo: settings for thumbnail format
    image.save(thumb_buffer, format=image.format or "PNG")
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
