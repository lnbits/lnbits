import json
from typing import Optional

from lnbits.core.db import db
from lnbits.settings import (
    AdminSettings,
    EditableSettings,
    SuperSettings,
    settings,
)


async def get_super_settings() -> Optional[SuperSettings]:
    row: dict = await db.fetchone("SELECT * FROM settings")
    if not row:
        return None
    editable_settings = json.loads(row["editable_settings"])
    return SuperSettings(**{"super_user": row["super_user"], **editable_settings})


async def get_admin_settings(is_super_user: bool = False) -> Optional[AdminSettings]:
    sets = await get_super_settings()
    if not sets:
        return None
    row_dict = dict(sets)
    row_dict.pop("super_user")
    row_dict.pop("auth_all_methods")

    admin_settings = AdminSettings(
        is_super_user=is_super_user,
        lnbits_allowed_funding_sources=settings.lnbits_allowed_funding_sources,
        **row_dict,
    )
    return admin_settings


async def delete_admin_settings() -> None:
    await db.execute("DELETE FROM settings")


async def update_admin_settings(data: EditableSettings) -> None:
    row: dict = await db.fetchone("SELECT editable_settings FROM settings")
    editable_settings = json.loads(row["editable_settings"]) if row else {}
    editable_settings.update(data.dict(exclude_unset=True))
    await db.execute(
        "UPDATE settings SET editable_settings = :settings",
        {"settings": json.dumps(editable_settings)},
    )


async def update_super_user(super_user: str) -> SuperSettings:
    await db.execute(
        "UPDATE settings SET super_user = :user",
        {"user": super_user},
    )
    settings = await get_super_settings()
    assert settings, "updated super_user settings could not be retrieved"
    return settings


async def create_admin_settings(super_user: str, new_settings: dict):
    await db.execute(
        """
        INSERT INTO settings (super_user, editable_settings)
        VALUES (:user, :settings)
        """,
        {"user": super_user, "settings": json.dumps(new_settings)},
    )
    settings = await get_super_settings()
    assert settings, "created admin settings could not be retrieved"
    return settings
