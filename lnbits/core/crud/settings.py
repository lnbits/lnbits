import json
from typing import Any, Optional

from loguru import logger

from lnbits.core.db import db
from lnbits.db import dict_to_model
from lnbits.settings import (
    AdminSettings,
    EditableSettings,
    SettingsField,
    SuperSettings,
    settings,
)


async def get_super_settings() -> Optional[SuperSettings]:
    data = await get_settings_by_tag("core")
    if data:
        super_user = await get_settings_field("super_user")
        super_user_id = super_user.value if super_user else None
        settings_dict = {"super_user": super_user_id, **data}
        return dict_to_model(settings_dict, SuperSettings)
    return None


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


async def update_admin_settings(
    data: EditableSettings, tag: Optional[str] = "core"
) -> None:
    editable_settings = await get_settings_by_tag("core") or {}
    editable_settings.update(data.dict(exclude_unset=True))
    for key, value in editable_settings.items():
        try:
            await set_settings_field(key, value, tag)
        except Exception as exc:
            logger.warning(exc)
            logger.warning(f"Failed to update settings for '{tag}.{key}'.")


async def update_super_user(super_user: str) -> SuperSettings:
    await set_settings_field("super_user", super_user)
    settings = await get_super_settings()
    assert settings, "updated super_user settings could not be retrieved"
    return settings


async def delete_admin_settings(tag: Optional[str] = "core") -> None:
    await db.execute(
        "DELETE FROM system_settings WHERE tag = :tag",
        {"tag": tag},
    )


async def reset_core_settings() -> None:
    await db.execute(
        """
        DELETE FROM system_settings WHERE tag = 'core'
        AND id NOT IN (
            'super_user',
            'lnbits_webpush_pubkey',
            'lnbits_webpush_privkey'
        )
        """,
    )


async def create_admin_settings(super_user: str, new_settings: dict) -> SuperSettings:
    data = {"super_user": super_user, **new_settings}
    for key, value in data.items():
        await set_settings_field(key, value)

    settings = await get_super_settings()
    assert settings, "created admin settings could not be retrieved"
    return settings


async def get_settings_field(
    id_: str, tag: Optional[str] = "core"
) -> Optional[SettingsField]:

    row: dict = await db.fetchone(
        """
            SELECT * FROM system_settings
            WHERE  id = :id AND tag = :tag
        """,
        {"id": id_, "tag": tag},
    )
    if not row:
        return None
    return SettingsField(id=row["id"], value=json.loads(row["value"]), tag=row["tag"])


async def set_settings_field(
    id_: str, value: Optional[Any], tag: Optional[str] = "core"
):
    value = json.dumps(value) if value is not None else None
    await db.execute(
        """
        INSERT INTO system_settings (id, value, tag)
        VALUES (:id, :value, :tag)
        ON CONFLICT (id, tag) DO UPDATE SET value = :value
        """,
        {"id": id_, "value": value, "tag": tag or "core"},
    )


async def get_settings_by_tag(tag: str) -> Optional[dict[str, Any]]:
    rows: list[dict] = await db.fetchall(
        "SELECT * FROM system_settings WHERE tag = :tag", {"tag": tag}
    )
    if len(rows) == 0:
        return None
    data: dict[str, Any] = {}
    for row in rows:
        try:
            data[row["id"]] = json.loads(row["value"]) if row["value"] else None
        except Exception as _:
            logger.warning(
                f"""Failed to load settings value for '{tag}.{row["id"]}'."""
            )
    data.pop("super_user")
    return data
