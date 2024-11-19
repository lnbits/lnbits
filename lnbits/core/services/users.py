from pathlib import Path
from typing import Optional
from uuid import uuid4

from loguru import logger

from lnbits.core.models.extensions import UserExtension
from lnbits.settings import (
    EditableSettings,
    SuperSettings,
    send_admin_user_to_saas,
    settings,
)

from ..crud import (
    create_account,
    create_admin_settings,
    create_user_extension,
    create_wallet,
    get_account,
    get_account_by_email,
    get_account_by_pubkey,
    get_account_by_username,
    get_super_settings,
    get_user_extensions,
    get_user_from_account,
    update_account,
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

    return await create_user_account_no_ckeck(account, wallet_name)


async def create_user_account_no_ckeck(
    account: Optional[Account] = None, wallet_name: Optional[str] = None
) -> User:

    if account:
        account.validate_fields()
        if account.username and await get_account_by_username(account.username):
            raise ValueError("Username already exists.")

        if account.email and await get_account_by_email(account.email):
            raise ValueError("Email already exists.")

        if account.pubkey and await get_account_by_pubkey(account.pubkey):
            raise ValueError("Pubkey already exists.")

        if not account.id:
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


async def update_user_account(account: Account) -> Account:
    account.validate_fields()

    existing_account = await get_account(account.id)
    if not existing_account:
        raise ValueError("User does not exist.")

    account.password_hash = existing_account.password_hash

    if existing_account.username and not account.username:
        raise ValueError("Cannot remove username.")

    if account.username:
        existing_account = await get_account_by_username(account.username)
        if existing_account and existing_account.id != account.id:
            raise ValueError("Username already exists.")
    elif existing_account.username:
        raise ValueError("Cannot remove username.")

    if account.email:
        existing_account = await get_account_by_email(account.email)
        if existing_account and existing_account.id != account.id:
            raise ValueError("Email already exists.")

    if account.pubkey:
        existing_account = await get_account_by_pubkey(account.pubkey)
        if existing_account and existing_account.id != account.id:
            raise ValueError("Pubkey already exists.")

    return await update_account(account)


async def update_user_extensions(user_id: str, extensions: list[str]):
    user_extensions = await get_user_extensions(user_id)
    for user_ext in user_extensions:
        if user_ext.active:
            if user_ext.extension not in extensions:
                user_ext.active = False
                await update_user_extension(user_ext)
        else:
            if user_ext.extension in extensions:
                user_ext.active = True
                await update_user_extension(user_ext)

    user_extension_ids = [ue.extension for ue in user_extensions]
    for ext in extensions:
        if ext in user_extension_ids:
            continue
        user_extension = UserExtension(user=user_id, extension=ext, active=True)
        await create_user_extension(user_extension)


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
