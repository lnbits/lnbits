import time
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from cryptography.hazmat.primitives import serialization
from loguru import logger
from py_vapid import Vapid
from py_vapid.utils import b64urlencode

from lnbits.core.extensions.models import UserExtension
from lnbits.db import Connection
from lnbits.exceptions import PaymentError
from lnbits.settings import (
    EditableSettings,
    SuperSettings,
    readonly_variables,
    send_admin_user_to_saas,
    settings,
)
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis, satoshis_amount_as_fiat
from lnbits.wallets import get_funding_source, set_funding_source
from lnbits.wallets.base import (
    PaymentPendingStatus,
    PaymentStatus,
    PaymentSuccessStatus,
)

from ..crud import (
    create_account,
    create_admin_settings,
    create_wallet,
    get_account,
    get_account_by_email,
    get_account_by_pubkey,
    get_account_by_username,
    get_payments,
    get_super_settings,
    get_total_balance,
    get_user_from_account,
    get_wallet_payment,
    update_admin_settings,
    update_super_user,
    update_user_extension,
)
from ..helpers import to_valid_user_id
from ..models import (
    Account,
    BalanceDelta,
    Payment,
    PaymentState,
    User,
    UserExtra,
    Wallet,
)


async def calculate_fiat_amounts(
    amount: float,
    wallet: Wallet,
    currency: Optional[str] = None,
    extra: Optional[dict] = None,
) -> tuple[int, dict]:
    wallet_currency = wallet.currency or settings.lnbits_default_accounting_currency
    fiat_amounts: dict = extra or {}
    if currency and currency != "sat":
        amount_sat = await fiat_amount_as_satoshis(amount, currency)
        if currency != wallet_currency:
            fiat_amounts["fiat_currency"] = currency
            fiat_amounts["fiat_amount"] = round(amount, ndigits=3)
            fiat_amounts["fiat_rate"] = amount_sat / amount
    else:
        amount_sat = int(amount)

    if wallet_currency:
        if wallet_currency == currency:
            fiat_amount = amount
        else:
            fiat_amount = await satoshis_amount_as_fiat(amount_sat, wallet_currency)
        fiat_amounts["wallet_fiat_currency"] = wallet_currency
        fiat_amounts["wallet_fiat_amount"] = round(fiat_amount, ndigits=3)
        fiat_amounts["wallet_fiat_rate"] = amount_sat / fiat_amount

    logger.debug(
        f"Calculated fiat amounts {wallet.id=} {amount=} {currency=}: {fiat_amounts=}"
    )

    return amount_sat, fiat_amounts


async def check_wallet_limits(
    wallet_id: str, amount_msat: int, conn: Optional[Connection] = None
):
    await check_time_limit_between_transactions(wallet_id, conn)
    await check_wallet_daily_withdraw_limit(wallet_id, amount_msat, conn)


async def check_time_limit_between_transactions(
    wallet_id: str, conn: Optional[Connection] = None
):
    limit = settings.lnbits_wallet_limit_secs_between_trans
    if not limit or limit <= 0:
        return
    payments = await get_payments(
        since=int(time.time()) - limit,
        wallet_id=wallet_id,
        limit=1,
        conn=conn,
    )
    if len(payments) == 0:
        return
    raise PaymentError(
        status="failed",
        message=f"The time limit of {limit} seconds between payments has been reached.",
    )


async def check_wallet_daily_withdraw_limit(
    wallet_id: str, amount_msat: int, conn: Optional[Connection] = None
):
    limit = settings.lnbits_wallet_limit_daily_max_withdraw
    if not limit:
        return
    if limit < 0:
        raise ValueError("It is not allowed to spend funds from this server.")

    payments = await get_payments(
        since=int(time.time()) - 60 * 60 * 24,
        outgoing=True,
        wallet_id=wallet_id,
        limit=1,
        conn=conn,
    )
    if len(payments) == 0:
        return

    total = 0
    for pay in payments:
        total += pay.amount
    total = total - amount_msat
    if limit * 1000 + total < 0:
        raise ValueError(
            "Daily withdrawal limit of "
            + str(settings.lnbits_wallet_limit_daily_max_withdraw)
            + " sats reached."
        )


async def check_transaction_status(
    wallet_id: str, payment_hash: str, conn: Optional[Connection] = None
) -> PaymentStatus:
    payment: Optional[Payment] = await get_wallet_payment(
        wallet_id, payment_hash, conn=conn
    )
    if not payment:
        return PaymentPendingStatus()

    if payment.status == PaymentState.SUCCESS.value:
        return PaymentSuccessStatus(fee_msat=payment.fee)

    return await payment.check_status()


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


async def check_webpush_settings():
    if not settings.lnbits_webpush_privkey:
        vapid = Vapid()
        vapid.generate_keys()
        privkey = vapid.private_pem()
        assert vapid.public_key, "VAPID public key does not exist"
        pubkey = b64urlencode(
            vapid.public_key.public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        )
        push_settings = {
            "lnbits_webpush_privkey": privkey.decode(),
            "lnbits_webpush_pubkey": pubkey,
        }
        update_cached_settings(push_settings)
        await update_admin_settings(EditableSettings(**push_settings))

    logger.info("Initialized webpush settings with generated VAPID key pair.")
    logger.info(f"Pubkey: {settings.lnbits_webpush_pubkey}")


def update_cached_settings(sets_dict: dict):
    for key, value in sets_dict.items():
        if key in readonly_variables:
            continue
        if key not in settings.dict().keys():
            continue
        try:
            setattr(settings, key, value)
        except Exception:
            logger.warning(f"Failed overriding setting: {key}, value: {value}")
    if "super_user" in sets_dict:
        settings.super_user = sets_dict["super_user"]


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


async def switch_to_voidwallet() -> None:
    funding_source = get_funding_source()
    if funding_source.__class__.__name__ == "VoidWallet":
        return
    set_funding_source("VoidWallet")
    settings.lnbits_backend_wallet_class = "VoidWallet"


async def get_balance_delta() -> BalanceDelta:
    funding_source = get_funding_source()
    status = await funding_source.status()
    lnbits_balance = await get_total_balance()
    return BalanceDelta(
        lnbits_balance_msats=lnbits_balance,
        node_balance_msats=status.balance_msat,
    )
