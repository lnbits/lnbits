import base64
from http import HTTPStatus

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from lnbits.core.crud.assets import (
    delete_user_asset,
    get_asset_info,
    get_public_asset,
    get_public_asset_info,
    get_user_asset,
    get_user_asset_info,
    get_user_assets,
    update_user_asset_info,
)
from lnbits.core.models.assets import AssetFilters, AssetInfo, AssetUpdate
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.users import AccountId
from lnbits.core.services.assets import create_user_asset
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_account_id_exists,
    optional_user_id,
    parse_filters,
)

asset_router = APIRouter(prefix="/api/v1/assets", tags=["Assets"])

upload_file_param = File(...)


@asset_router.get(
    "/paginated",
    name="Get user assets",
    summary="Get paginated list user assets",
)
async def api_get_user_assets(
    account_id: AccountId = Depends(check_account_id_exists),
    filters: Filters = Depends(parse_filters(AssetFilters)),
) -> Page[AssetInfo]:
    return await get_user_assets(account_id.id, filters=filters)


@asset_router.get(
    "/{asset_id}",
    name="Get user asset",
    summary="Get user asset by ID",
)
async def api_get_asset(
    asset_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> AssetInfo:
    asset_info = await get_user_asset_info(account_id.id, asset_id)
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
    user_id: str | None = Depends(optional_user_id),
) -> Response:
    asset = None
    if user_id:
        asset = await get_user_asset(user_id, asset_id)

    if not asset:
        asset = await get_public_asset(asset_id)

    if not asset:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Asset not found.")

    return Response(
        content=asset.data,
        media_type=asset.mime_type,
        headers={"Content-Disposition": f'inline; filename="{asset.name}"'},
    )


@asset_router.get(
    "/{asset_id}/thumbnail",
    name="Get user asset thumbnail",
    summary="Get user asset thumbnail data by ID",
)
async def api_get_asset_thumbnail(
    asset_id: str,
    user_id: str | None = Depends(optional_user_id),
) -> Response:
    asset_info = None
    if user_id:
        asset_info = await get_user_asset_info(user_id, asset_id)

    if not asset_info:
        asset_info = await get_public_asset_info(asset_id)

    if not asset_info:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Asset not found.")

    return Response(
        content=(
            base64.b64decode(asset_info.thumbnail_base64)
            if asset_info.thumbnail_base64
            else b""
        ),
        media_type=asset_info.mime_type,
        headers={"Content-Disposition": f'inline; filename="{asset_info.name}"'},
    )


@asset_router.put(
    "/{asset_id}",
    name="Update user asset",
    summary="Update user asset by ID",
)
async def api_update_asset(
    asset_id: str,
    data: AssetUpdate,
    account_id: AccountId = Depends(check_account_id_exists),
) -> AssetInfo:
    if account_id.is_admin_id:
        asset_info = await get_asset_info(asset_id)
    else:
        asset_info = await get_user_asset_info(account_id.id, asset_id)

    if not asset_info:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Asset not found.")

    asset_info.name = data.name or asset_info.name
    asset_info.is_public = (
        asset_info.is_public if data.is_public is None else data.is_public
    )
    await update_user_asset_info(asset_info)
    return asset_info


@asset_router.post(
    "",
    name="Upload",
    summary="Upload user assets",
)
async def api_upload_asset(
    account_id: AccountId = Depends(check_account_id_exists),
    file: UploadFile = upload_file_param,
    public_asset: bool = False,
) -> AssetInfo:
    asset = await create_user_asset(account_id.id, file, public_asset)

    asset_info = await get_user_asset_info(account_id.id, asset.id)
    if not asset_info:
        raise ValueError("Failed to retrieve asset info after upload.")

    return asset_info


@asset_router.delete(
    "/{asset_id}",
    name="Delete user asset",
    summary="Delete user asset by ID",
)
async def api_delete_asset(
    asset_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:
    asset = await get_user_asset(account_id.id, asset_id)
    if not asset:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Asset not found.")

    await delete_user_asset(account_id.id, asset_id)
    return SimpleStatus(success=True, message="Asset deleted successfully.")
