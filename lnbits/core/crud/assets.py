from lnbits.core.db import db
from lnbits.core.models.assets import Asset, AssetFilters, AssetInfo
from lnbits.db import Connection, Filters, Page


async def create_asset(
    entry: Asset,
    conn: Connection | None = None,
) -> None:
    await (conn or db).insert("assets", entry)


async def get_user_asset_info(
    user_id: str,
    asset_id: str,
    conn: Connection | None = None,
) -> AssetInfo | None:
    return await (conn or db).fetchone(
        query="SELECT * from assets WHERE id = :asset_id AND user_id = :user_id",
        values={"asset_id": asset_id, "user_id": user_id},
        model=AssetInfo,
    )


async def get_asset_info(
    asset_id: str, conn: Connection | None = None
) -> AssetInfo | None:
    return await (conn or db).fetchone(
        query="SELECT * from assets WHERE id = :asset_id",
        values={"asset_id": asset_id},
        model=AssetInfo,
    )


async def get_user_asset(
    user_id: str,
    asset_id: str,
    conn: Connection | None = None,
) -> Asset | None:
    return await (conn or db).fetchone(
        query="SELECT * from assets WHERE id = :asset_id AND user_id = :user_id",
        values={"asset_id": asset_id, "user_id": user_id},
        model=Asset,
    )


async def get_public_asset(
    asset_id: str,
    conn: Connection | None = None,
) -> Asset | None:
    return await (conn or db).fetchone(
        query="SELECT * from assets WHERE id = :asset_id AND is_public = true",
        values={"asset_id": asset_id},
        model=Asset,
    )


async def get_public_asset_info(
    asset_id: str,
    conn: Connection | None = None,
) -> AssetInfo | None:
    return await (conn or db).fetchone(
        query="SELECT * from assets WHERE id = :asset_id AND is_public = true",
        values={"asset_id": asset_id},
        model=AssetInfo,
    )


async def update_user_asset_info(
    asset: AssetInfo,
) -> AssetInfo:
    await db.update("assets", asset)
    return asset


async def delete_user_asset(
    user_id: str, asset_id: str, conn: Connection | None = None
) -> None:
    await (conn or db).execute(
        query="DELETE FROM assets WHERE id = :asset_id AND user_id = :user_id",
        values={"asset_id": asset_id, "user_id": user_id},
    )


async def get_user_assets(
    user_id: str,
    filters: Filters[AssetFilters] | None = None,
    conn: Connection | None = None,
) -> Page[AssetInfo]:
    filters = filters or Filters()
    filters.sortby = filters.sortby or "created_at"
    return await (conn or db).fetch_page(
        query="SELECT * FROM assets",
        where=["user_id = :user_id"],
        values={"user_id": user_id},
        filters=filters,
        model=AssetInfo,
        table_name="assets",
    )


async def get_user_assets_count(user_id: str) -> int:
    result = await db.execute(
        query="SELECT COUNT(*) as count FROM assets WHERE user_id = :user_id",
        values={"user_id": user_id},
    )
    row = result.mappings().first()
    return row.get("count", 0)
