from http import HTTPStatus

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from lnbits.core.crud.assets import get_asset_info, get_user_asset, get_user_assets
from lnbits.core.models.assets import AssetFilters, AssetInfo
from lnbits.core.models.users import User
from lnbits.core.services.assets import create_user_asset
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_admin,
    check_user_exists,
    parse_filters,
)

asset_router = APIRouter(
    prefix="/api/v1/assets", dependencies=[Depends(check_admin)], tags=["Assets"]
)

upload_file_param = File(...)


@asset_router.get(
    "/paginated",
    name="Get user assets",
    summary="Get paginated list user assets",
)
async def api_get_user_assets(
    user: User = Depends(check_user_exists),
    filters: Filters = Depends(parse_filters(AssetFilters)),
) -> Page[AssetInfo]:
    print("### api_get_user_assets filters:", filters)
    return await get_user_assets(user.id, filters=filters)


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
    "/{asset_id}/binary",
    name="Get user asset binary",
    summary="Get user asset binary data by ID",
)
async def api_get_asset_binary(
    asset_id: str,
    user: User = Depends(check_user_exists),
) -> Response:
    asset = await get_user_asset(user.id, asset_id)
    if not asset:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Asset not found.")

    return Response(
        content=asset.data,
        media_type=asset.extra.mime_type,
        headers={"Content-Disposition": f'inline; filename="{asset.name}"'},
    )


@asset_router.post(
    "",
    name="Upload",
    summary="Upload user assets",
)
async def api_upload_asset(
    user: User = Depends(check_user_exists),
    file: UploadFile = upload_file_param,
) -> AssetInfo:

    asset = await create_user_asset(user.id, file)

    asset_info = await get_asset_info(user.id, asset.id)
    if not asset_info:
        raise ValueError("Failed to retrieve asset info after upload.")

    return asset_info
