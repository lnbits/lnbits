from fastapi import APIRouter, Depends

from lnbits.core.crud.assets import get_user_assets
from lnbits.core.models.assets import AssetFilters, AssetInfo
from lnbits.core.models.users import User
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_admin,
    check_user_exists,
    parse_filters,
)

audit_router = APIRouter(
    prefix="/audit/api/v1", dependencies=[Depends(check_admin)], tags=["Audit"]
)


@audit_router.get(
    "",
    name="Get user assets",
    summary="Get paginated list user assets",
)
async def api_get_audit(
    user: User = Depends(check_user_exists),
    filters: Filters = Depends(parse_filters(AssetFilters)),
) -> Page[AssetInfo]:
    return await get_user_assets(user.id, filters)
