from lnbits.core.db import db
from lnbits.core.models.assets import Asset, AssetFilters, AssetInfo
from lnbits.db import Connection, Filters, Page


async def create_asset(
    entry: Asset,
    conn: Connection | None = None,
) -> None:
    await (conn or db).insert("assets", entry)


async def get_asset_info(
    user_id: str,
    asset_id: str,
    conn: Connection | None = None,
) -> AssetInfo | None:
    return await (conn or db).fetchone(
        query="SELECT * from assets WHERE id = :asset_id AND user_id = :user_id",
        values={"asset_id": asset_id, "user_id": user_id},
        model=AssetInfo,
    )


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


async def get_user_assets_count(user_id: str) -> int:
    result = await db.execute(
        query="SELECT COUNT(*) as count FROM assets WHERE user_id = :user_id",
        values={"user_id": user_id},
    )
    row = result.mappings().first()
    print(f"### get_user_assets_count row: {row}")
    return row.get("count", 0)
