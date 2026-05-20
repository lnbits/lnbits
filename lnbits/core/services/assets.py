import base64
import io
from uuid import uuid4

import filetype
from fastapi import UploadFile
from loguru import logger
from PIL import Image

from lnbits.core.crud.assets import create_asset, get_user_assets_count
from lnbits.core.models.assets import Asset
from lnbits.settings import settings

IMAGE_MIME_TYPE_ALIASES = {
    "heic": "image/heic",
    "heics": "image/heics",
    "heif": "image/heif",
    "image/jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
}
PIL_IMAGE_FORMAT_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
}


async def create_user_asset(user_id: str, file: UploadFile, is_public: bool) -> Asset:
    if not file.content_type:
        raise ValueError("File must have a content type.")

    content_type = normalize_asset_mime_type(file.content_type)
    filename = file.filename or "unnamed"

    if content_type not in allowed_asset_mime_types():
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

    stored_mime_type = detect_image_mime_type(contents)
    if stored_mime_type != content_type:
        logger.warning(
            "Image MIME type mismatch: declared={}, detected={}",
            content_type,
            stored_mime_type,
        )
        raise ValueError(
            "Image file content does not match declared file type. "
            f"Declared: '{content_type}', detected: '{stored_mime_type}'."
        )

    thumb_buffer = thumbnail_from_bytes(contents)

    asset = Asset(
        id=uuid4().hex,
        user_id=user_id,
        mime_type=stored_mime_type,
        is_public=is_public,
        name=filename,
        size_bytes=len(contents),
        thumbnail_base64=(
            base64.b64encode(thumb_buffer.getvalue()).decode("utf-8")
            if thumb_buffer
            else None
        ),
        data=contents,
    )

    await create_asset(asset)
    return asset


def normalize_asset_mime_type(content_type: str) -> str:
    content_type = content_type.split(";", 1)[0].strip().lower()
    return IMAGE_MIME_TYPE_ALIASES.get(content_type, content_type)


def allowed_asset_mime_types() -> set[str]:
    return {
        mime_type
        for mime_type in (
            normalize_asset_mime_type(mime_type)
            for mime_type in settings.lnbits_assets_allowed_mime_types
        )
        if mime_type.startswith("image/")
    }


def detect_image_mime_type(contents: bytes) -> str:
    kind = filetype.guess(contents)
    mime_type = normalize_asset_mime_type(kind.mime) if kind else None

    if mime_type and mime_type in PIL_IMAGE_FORMAT_MIME_TYPES.values():
        verify_pil_image(contents, mime_type)
        return mime_type

    if mime_type and mime_type.startswith("image/"):
        return mime_type

    try:
        with Image.open(io.BytesIO(contents)) as image:
            image.verify()
            mime_type = PIL_IMAGE_FORMAT_MIME_TYPES.get(image.format or "")
    except Exception as exc:
        raise ValueError(
            "Image file content does not match declared file type."
        ) from exc

    if not mime_type:
        raise ValueError("Image file content does not match declared file type.")

    return mime_type


def verify_pil_image(contents: bytes, mime_type: str) -> None:
    try:
        with Image.open(io.BytesIO(contents)) as image:
            image.verify()
            detected_mime_type = PIL_IMAGE_FORMAT_MIME_TYPES.get(image.format or "")
    except Exception as exc:
        raise ValueError(
            "Image file content does not match declared file type."
        ) from exc

    if detected_mime_type != mime_type:
        raise ValueError("Image file content does not match declared file type.")


def thumbnail_from_bytes(contents: bytes) -> io.BytesIO | None:
    try:
        image = Image.open(io.BytesIO(contents))

        thumbnail_width = min(256, settings.lnbits_asset_thumbnail_width)
        thumbnail_height = min(256, settings.lnbits_asset_thumbnail_height)
        image.thumbnail((thumbnail_width, thumbnail_height))

        # Save thumbnail to an in-memory buffer
        thumb_buffer = io.BytesIO()
        thumbnail_format = settings.lnbits_asset_thumbnail_format or "PNG"
        image.save(thumb_buffer, format=thumbnail_format)
        thumb_buffer.seek(0)
        return thumb_buffer
    except Exception as exc:
        logger.warning(f"Failed to create thumbnail: {exc}")
        return None
