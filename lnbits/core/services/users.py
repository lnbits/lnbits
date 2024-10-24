from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from loguru import logger

from lnbits.core.extensions.models import UserExtension
from lnbits.settings import (
    EditableSettings,
    SuperSettings,
    send_admin_user_to_saas,
    settings,
)

from ..crud import (
    create_account,
    create_admin_settings,
    create_wallet,
    get_account,
    get_account_by_email,
    get_account_by_pubkey,
    get_account_by_username,
    get_super_settings,
    get_user_from_account,
    update_super_user,
    update_user_extension,
)
from ..helpers import to_valid_user_id
from ..models import (
    Account,
    User,
    UserExtra,
)
from .settings import update_cached_settings


async def create_user_account(
    account: Optional[Account] = None, wallet_name: Optional[str] = None
) -> User:
    if not settings.new_accounts_allowed:
        raise ValueError("Account creation is disabled.")
    if account:
        if account.username and await get_account_by_username(account.username):
            raise ValueError("Username already exists.")

        if account.email and await get_account_by_email(account.email):
            raise ValueError("Email already exists.")

        if account.pubkey and await get_account_by_pubkey(account.pubkey):
            raise ValueError("Pubkey already exists.")

        if account.id:
            user_uuid4 = UUID(hex=account.id, version=4)
            assert user_uuid4.hex == account.id, "User ID is not valid UUID4 hex string"
        else:
            account.id = uuid4().hex

    account = await create_account(account)
    await create_wallet(
        user_id=account.id,
        wallet_name=wallet_name or settings.lnbits_default_wallet_name,
    )

    for ext_id in settings.lnbits_user_default_extensions:
        user_ext = UserExtension(user=account.id, extension=ext_id, active=True)
        await update_user_extension(user_ext)

    user = await get_user_from_account(account)
    assert user, "Cannot find user for account."

    return user


async def check_admin_settings():
    if settings.super_user:
        settings.super_user = to_valid_user_id(settings.super_user).hex

    if settings.lnbits_admin_ui:
        settings_db = await get_super_settings()
        if not settings_db:
            # create new settings if table is empty
            logger.warning("Settings DB empty. Inserting default settings.")
            settings_db = await init_admin_settings(settings.super_user)
            logger.warning("Initialized settings from environment variables.")

        if settings.super_user and settings.super_user != settings_db.super_user:
            # .env super_user overwrites DB super_user
            settings_db = await update_super_user(settings.super_user)

        update_cached_settings(settings_db.dict())

        # saving superuser to {data_dir}/.super_user file
        with open(Path(settings.lnbits_data_folder) / ".super_user", "w") as file:
            file.write(settings.super_user)

        # callback for saas
        if (
            settings.lnbits_saas_callback
            and settings.lnbits_saas_secret
            and settings.lnbits_saas_instance_id
        ):
            send_admin_user_to_saas()

        account = await get_account(settings.super_user)
        if account and account.extra and account.extra.provider == "env":
            settings.first_install = True

        logger.success(
            "✔️ Admin UI is enabled. run `poetry run lnbits-cli superuser` "
            "to get the superuser."
        )


async def init_admin_settings(super_user: Optional[str] = None) -> SuperSettings:
    account = None
    if super_user:
        account = await get_account(super_user)
    if not account:
        account_id = super_user or uuid4().hex
        account = Account(
            id=account_id,
            extra=UserExtra(provider="env"),
        )
        await create_account(account)
        await create_wallet(user_id=account.id)

    editable_settings = EditableSettings.from_dict(settings.dict())
    return await create_admin_settings(account.id, editable_settings.dict())
