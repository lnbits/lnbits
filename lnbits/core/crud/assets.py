from lnbits.core.db import db
from lnbits.core.models.assets import Asset, AssetFilters, AssetInfo
from lnbits.db import Connection, Filters, Page


async def create_asset(
    entry: Asset,
    conn: Connection | None = None,
) -> None:
    await (conn or db).insert("assets", entry)


async def get_user_assets(
    user_id: str,
    filters: Filters[AssetFilters] | None = None,
    conn: Connection | None = None,
) -> Page[AssetInfo]:
    return await (conn or db).fetch_page(
        query="SELECT * from assets WHERE user_id = :user_id",
        values={"user_id": user_id},
        filters=filters,
        model=AssetInfo,
    )
