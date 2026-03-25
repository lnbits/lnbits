from pathlib import Path
from uuid import uuid4

import pytest

from lnbits.core.crud import create_account, delete_account, get_account
from lnbits.core.crud.settings import get_settings_field, set_settings_field
from lnbits.core.db import db
from lnbits.core.models import Account, UpdateSuperuserPassword, UserExtra
from lnbits.core.services.users import check_admin_settings
from lnbits.core.views.auth_api import first_install
from lnbits.settings import settings


async def _restore_setting_field(field_name: str, original_row) -> None:
    if original_row is None:
        await db.execute(
            "DELETE FROM system_settings WHERE id = :id AND tag = :tag",
            {"id": field_name, "tag": "core"},
        )
        return

    await set_settings_field(field_name, original_row.value, original_row.tag)


def test_has_first_install_token_changed_requires_a_confirmed_mismatch():
    original_token = settings.first_install_token
    original_confirmed = settings.first_install_token_confirmed

    try:
        settings.first_install_token = "new-token"
        settings.first_install_token_confirmed = "old-token"
        assert settings.has_first_install_token_changed() is True

        settings.first_install_token_confirmed = "new-token"
        assert settings.has_first_install_token_changed() is False

        settings.first_install_token_confirmed = None
        assert settings.has_first_install_token_changed() is False

        settings.first_install_token = None
        assert settings.has_first_install_token_changed() is False
    finally:
        settings.first_install_token = original_token
        settings.first_install_token_confirmed = original_confirmed


@pytest.mark.anyio
async def test_first_install_confirms_first_install_token(app):
    temp_super_user = uuid4().hex
    username = f"super_{temp_super_user[:8]}"
    original_super_user = settings.super_user
    original_first_install = settings.first_install
    original_first_install_token = settings.first_install_token
    original_first_install_token_confirmed = settings.first_install_token_confirmed
    original_confirmed_row = await get_settings_field("first_install_token_confirmed")

    await create_account(Account(id=temp_super_user, extra=UserExtra(provider="env")))

    try:
        settings.super_user = temp_super_user
        settings.first_install = True
        settings.first_install_token = "expected-token"
        settings.first_install_token_confirmed = None

        response = await first_install(
            UpdateSuperuserPassword(
                username=username,
                password="secret1234",
                password_repeat="secret1234",
                first_install_token="expected-token",
            )
        )

        assert response.status_code == 200
        assert settings.first_install is False
        assert settings.first_install_token_confirmed == "expected-token"

        confirmed_row = await get_settings_field("first_install_token_confirmed")
        assert confirmed_row is not None
        assert confirmed_row.value == "expected-token"

        account = await get_account(temp_super_user)
        assert account is not None
        assert account.username == username
        assert account.extra.provider == "lnbits"
        assert account.verify_password("secret1234")
    finally:
        await _restore_setting_field(
            "first_install_token_confirmed", original_confirmed_row
        )
        settings.super_user = original_super_user
        settings.first_install = original_first_install
        settings.first_install_token = original_first_install_token
        settings.first_install_token_confirmed = original_first_install_token_confirmed
        await delete_account(temp_super_user)


@pytest.mark.anyio
async def test_check_admin_settings_clears_persisted_super_user_when_token_changes(app):
    temp_super_user = uuid4().hex
    original_super_user = settings.super_user
    original_first_install = settings.first_install
    original_first_install_token = settings.first_install_token
    original_first_install_token_confirmed = settings.first_install_token_confirmed
    original_super_user_row = await get_settings_field("super_user")
    original_confirmed_row = await get_settings_field("first_install_token_confirmed")
    super_user_file = Path(settings.lnbits_data_folder) / ".super_user"

    await create_account(
        Account(id=temp_super_user, extra=UserExtra(provider="lnbits"))
    )

    try:
        await set_settings_field("super_user", temp_super_user)
        await set_settings_field("first_install_token_confirmed", "old-token")

        settings.lnbits_admin_ui = True
        settings.super_user = temp_super_user
        settings.first_install = False
        settings.first_install_token = "new-token"
        settings.first_install_token_confirmed = "old-token"

        await check_admin_settings()

        super_user_row = await get_settings_field("super_user")
        assert super_user_row is not None
        assert super_user_row.value
        assert settings.first_install is True
    finally:
        await _restore_setting_field("super_user", original_super_user_row)
        await _restore_setting_field(
            "first_install_token_confirmed", original_confirmed_row
        )
        settings.super_user = original_super_user
        settings.first_install = original_first_install
        settings.first_install_token = original_first_install_token
        settings.first_install_token_confirmed = original_first_install_token_confirmed
        super_user_file.write_text(original_super_user)
        await delete_account(temp_super_user)
