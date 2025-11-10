import base64
import io
from http import HTTPStatus
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image

from lnbits.core.crud.assets import create_asset, get_asset_info, get_user_assets
from lnbits.core.models.assets import Asset, AssetExtra, AssetFilters, AssetInfo
from lnbits.core.models.users import User
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_admin,
    check_user_exists,
    parse_filters,
)

asset_router = APIRouter(
    prefix="/asset/api/v1", dependencies=[Depends(check_admin)], tags=["Asset"]
)

upload_file_param = File(...)


@asset_router.get(
    "/{asset_id}",
    name="Get user asset",
    summary="Get user asset by ID",
)
async def api_get_asset(
    asset_id: str,
    user: User = Depends(check_user_exists),
) -> AssetInfo:
    asset_info = await get_asset_info(user.id, asset_id)
    if not asset_info:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Asset not found.")
    return asset_info


@asset_router.get(
    "",
    name="Get user assets",
    summary="Get paginated list user assets",
)
async def api_get_user_assets(
    user: User = Depends(check_user_exists),
    filters: Filters = Depends(parse_filters(AssetFilters)),
) -> Page[AssetInfo]:
    return await get_user_assets(user.id, filters=filters)


@asset_router.post(
    "",
    name="Upload",
    summary="Upload user assets",
)
async def api_upload_asset(
    user: User = Depends(check_user_exists),
    file: UploadFile = upload_file_param,
) -> AssetInfo:
    if not file.content_type:
        raise ValueError("Image file must have a content type.")
    if not file.content_type.startswith("image/"):
        raise ValueError("Only image files are allowed.")

    contents = await file.read()

    # Open the image from bytes
    image = Image.open(io.BytesIO(contents))
    # Create thumbnail (preserves aspect ratio)
    image.thumbnail((128, 128))
    # Save thumbnail to an in-memory buffer
    thumb_buffer = io.BytesIO()
    image.save(thumb_buffer, format=image.format or "JPEG")
    thumb_buffer.seek(0)

    asset = Asset(
        id=uuid4().hex,
        user_id=user.id,
        asset_type="image",
        name=file.filename or "unnamed",
        size=len(contents),
        extra=AssetExtra(description="Uploaded image", mime_type=file.content_type),
        thumbnail_base64=base64.b64encode(thumb_buffer.getvalue()).decode("utf-8"),
        data=contents,
    )

    await create_asset(asset)

    asset_info = await get_asset_info(user.id, asset.id)
    if not asset_info:
        raise ValueError("Failed to retrieve asset info after upload.")

    return asset_info
