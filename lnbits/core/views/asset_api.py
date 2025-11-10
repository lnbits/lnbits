from http import HTTPStatus

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from lnbits.core.crud.assets import get_asset_info, get_user_assets
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

    asset = await create_user_asset(user.id, file)

    asset_info = await get_asset_info(user.id, asset.id)
    if not asset_info:
        raise ValueError("Failed to retrieve asset info after upload.")

    return asset_info
