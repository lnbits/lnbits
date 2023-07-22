import asyncio
import json
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import httpx
from cryptography.hazmat.primitives import serialization
from fastapi import Depends, WebSocket
from lnurl import LnurlErrorResponse
from lnurl import decode as decode_lnurl
from loguru import logger
from py_vapid import Vapid
from py_vapid.utils import b64urlencode

from lnbits import bolt11
from lnbits.core.db import db
from lnbits.db import Connection
from lnbits.decorators import WalletTypeInfo, require_admin_key
from lnbits.helpers import url_for
from lnbits.settings import (
    EditableSettings,
    SuperSettings,
    readonly_variables,
    send_admin_user_to_saas,
    settings,
)
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis, satoshis_amount_as_fiat
from lnbits.wallets import FAKE_WALLET, get_wallet_class, set_wallet_class
from lnbits.wallets.base import PaymentStatus

from .crud import (
    check_internal,
    create_account,
    create_admin_settings,
    create_payment,
    create_wallet,
    get_account,
    get_super_settings,
    get_total_balance,
    get_wallet,
    get_wallet_payment,
    update_admin_settings,
    update_payment_status,
    update_super_user,
)
from .helpers import to_valid_user_id
from .models import Payment, Wallet


class PaymentFailure(Exception):
    pass


class InvoiceFailure(Exception):
    pass


async def calculate_fiat_amounts(
    amount: float,
    wallet_id: str,
    currency: Optional[str] = None,
    extra: Optional[Dict] = None,
    conn: Optional[Connection] = None,
) -> Tuple[int, Optional[Dict]]:
    wallet = await get_wallet(wallet_id, conn=conn)
    assert wallet, "invalid wallet_id"
    wallet_currency = wallet.currency or settings.lnbits_default_accounting_currency

    if currency and currency != "sat":
        amount_sat = await fiat_amount_as_satoshis(amount, currency)
        extra = extra or {}
        if currency != wallet_currency:
            extra["fiat_currency"] = currency
            extra["fiat_amount"] = round(amount, ndigits=3)
            extra["fiat_rate"] = amount_sat / amount
    else:
        amount_sat = int(amount)

    if wallet_currency:
        if wallet_currency == currency:
            fiat_amount = amount
        else:
            fiat_amount = await satoshis_amount_as_fiat(amount_sat, wallet_currency)
        extra = extra or {}
        extra["wallet_fiat_currency"] = wallet_currency
        extra["wallet_fiat_amount"] = round(fiat_amount, ndigits=3)
        extra["wallet_fiat_rate"] = amount_sat / fiat_amount

    logger.debug(
        f"Calculated fiat amounts {wallet.id=} {amount=} {currency=}: {extra=}"
    )

    return amount_sat, extra


async def create_invoice(
    *,
    wallet_id: str,
    amount: float,
    currency: Optional[str] = "sat",
    memo: str,
    description_hash: Optional[bytes] = None,
    unhashed_description: Optional[bytes] = None,
    expiry: Optional[int] = None,
    extra: Optional[Dict] = None,
    webhook: Optional[str] = None,
    internal: Optional[bool] = False,
    conn: Optional[Connection] = None,
) -> Tuple[str, str]:
    if not amount > 0:
        raise InvoiceFailure("Amountless invoices not supported.")

    if await get_wallet(wallet_id, conn=conn) is None:
        raise InvoiceFailure("Wallet does not exist.")

    invoice_memo = None if description_hash else memo

    # use the fake wallet if the invoice is for internal use only
    wallet = FAKE_WALLET if internal else get_wallet_class()

    amount_sat, extra = await calculate_fiat_amounts(
        amount, wallet_id, currency=currency, extra=extra, conn=conn
    )

    ok, checking_id, payment_request, error_message = await wallet.create_invoice(
        amount=amount_sat,
        memo=invoice_memo,
        description_hash=description_hash,
        unhashed_description=unhashed_description,
        expiry=expiry or settings.lightning_invoice_expiry,
    )
    if not ok or not payment_request or not checking_id:
        raise InvoiceFailure(error_message or "unexpected backend error.")

    invoice = bolt11.decode(payment_request)

    amount_msat = 1000 * amount_sat
    await create_payment(
        wallet_id=wallet_id,
        checking_id=checking_id,
        payment_request=payment_request,
        payment_hash=invoice.payment_hash,
        amount=amount_msat,
        memo=memo,
        extra=extra,
        webhook=webhook,
        conn=conn,
    )

    return invoice.payment_hash, payment_request


async def pay_invoice(
    *,
    wallet_id: str,
    payment_request: str,
    max_sat: Optional[int] = None,
    extra: Optional[Dict] = None,
    description: str = "",
    timeout: int = 10,
) -> str:
    """
    The actual work is passed to the payment processor
    we just wait for the result here.
    """

    from .tasks import PaymentJob, payment_queue

    job = PaymentJob(
        wallet_id=wallet_id,
        payment_request=payment_request,
        max_sat=max_sat,
        memo=description,
        extra=extra,
    )

    await payment_queue.put(job)
    return await asyncio.wait_for(job.fut, timeout=timeout)


async def redeem_lnurl_withdraw(
    wallet_id: str,
    lnurl_request: str,
    memo: Optional[str] = None,
    extra: Optional[Dict] = None,
    wait_seconds: int = 0,
    conn: Optional[Connection] = None,
) -> None:
    if not lnurl_request:
        return None

    res = {}

    async with httpx.AsyncClient() as client:
        lnurl = decode_lnurl(lnurl_request)
        r = await client.get(str(lnurl))
        res = r.json()

    try:
        _, payment_request = await create_invoice(
            wallet_id=wallet_id,
            amount=int(res["maxWithdrawable"] / 1000),
            memo=memo or res["defaultDescription"] or "",
            extra=extra,
            conn=conn,
        )
    except Exception:
        logger.warning(
            f"failed to create invoice on redeem_lnurl_withdraw "
            f"from {lnurl}. params: {res}"
        )
        return None

    if wait_seconds:
        await asyncio.sleep(wait_seconds)

    params = {"k1": res["k1"], "pr": payment_request}

    try:
        params["balanceNotify"] = url_for(
            f"/withdraw/notify/{urlparse(lnurl_request).netloc}",
            external=True,
            wal=wallet_id,
        )
    except Exception:
        pass

    async with httpx.AsyncClient() as client:
        try:
            await client.get(res["callback"], params=params)
        except Exception:
            pass


async def perform_lnurlauth(
    callback: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
    conn: Optional[Connection] = None,
) -> Optional[LnurlErrorResponse]:
    cb = urlparse(callback)

    k1 = bytes.fromhex(parse_qs(cb.query)["k1"][0])

    key = wallet.wallet.lnurlauth_key(cb.netloc)

    def int_to_bytes_suitable_der(x: int) -> bytes:
        """for strict DER we need to encode the integer with some quirks"""
        b = x.to_bytes((x.bit_length() + 7) // 8, "big")

        if len(b) == 0:
            # ensure there's at least one byte when the int is zero
            return bytes([0])

        if b[0] & 0x80 != 0:
            # ensure it doesn't start with a 0x80 and so it isn't
            # interpreted as a negative number
            return bytes([0]) + b

        return b

    def encode_strict_der(r: int, s: int, order: int):
        # if s > order/2 verification will fail sometimes
        # so we must fix it here see:
        # https://github.com/indutny/elliptic/blob/e71b2d9359c5fe9437fbf46f1f05096de447de57/lib/elliptic/ec/index.js#L146-L147
        if s > order // 2:
            s = order - s

        # now we do the strict DER encoding copied from
        # https://github.com/KiriKiri/bip66 (without any checks)
        r_temp = int_to_bytes_suitable_der(r)
        s_temp = int_to_bytes_suitable_der(s)

        r_len = len(r_temp)
        s_len = len(s_temp)
        sign_len = 6 + r_len + s_len

        signature = BytesIO()
        signature.write(0x30.to_bytes(1, "big", signed=False))
        signature.write((sign_len - 2).to_bytes(1, "big", signed=False))
        signature.write(0x02.to_bytes(1, "big", signed=False))
        signature.write(r_len.to_bytes(1, "big", signed=False))
        signature.write(r_temp)
        signature.write(0x02.to_bytes(1, "big", signed=False))
        signature.write(s_len.to_bytes(1, "big", signed=False))
        signature.write(s_temp)

        return signature.getvalue()

    sig = key.sign_digest_deterministic(k1, sigencode=encode_strict_der)

    async with httpx.AsyncClient() as client:
        assert key.verifying_key, "LNURLauth verifying_key does not exist"
        r = await client.get(
            callback,
            params={
                "k1": k1.hex(),
                "key": key.verifying_key.to_string("compressed").hex(),
                "sig": sig.hex(),
            },
        )
        try:
            resp = json.loads(r.text)
            if resp["status"] == "OK":
                return None

            return LnurlErrorResponse(reason=resp["reason"])
        except (KeyError, json.decoder.JSONDecodeError):
            return LnurlErrorResponse(
                reason=r.text[:200] + "..." if len(r.text) > 200 else r.text
            )


async def check_transaction_status(
    wallet_id: str, payment_hash: str, conn: Optional[Connection] = None
) -> PaymentStatus:
    payment: Optional[Payment] = await get_wallet_payment(
        wallet_id, payment_hash, conn=conn
    )
    if not payment:
        return PaymentStatus(None)
    if not payment.pending:
        # note: before, we still checked the status of the payment again
        return PaymentStatus(True, fee_msat=payment.fee)

    status: PaymentStatus = await payment.check_status()
    return status


# WARN: this same value must be used for balance check and passed to
# WALLET.pay_invoice(), it may cause a vulnerability if the values differ
def fee_reserve(amount_msat: int) -> int:
    reserve_min = settings.lnbits_reserve_fee_min
    reserve_percent = settings.lnbits_reserve_fee_percent
    return max(int(reserve_min), int(amount_msat * reserve_percent / 100.0))


async def send_payment_notification(wallet: Wallet, payment: Payment):
    await websocketUpdater(
        wallet.id,
        json.dumps(
            {
                "wallet_balance": wallet.balance,
                "payment": payment.dict(),
            }
        ),
    )


async def update_wallet_balance(wallet_id: str, amount: int):
    payment_hash, _ = await create_invoice(
        wallet_id=wallet_id,
        amount=amount,
        memo="Admin top up",
        internal=True,
    )
    async with db.connect() as conn:
        checking_id = await check_internal(payment_hash, conn=conn)
        assert checking_id, "newly created checking_id cannot be retrieved"
        await update_payment_status(checking_id=checking_id, pending=False, conn=conn)
        # notify receiver asynchronously
        from lnbits.tasks import internal_invoice_queue

        await internal_invoice_queue.put(checking_id)


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
        if key not in readonly_variables:
            try:
                setattr(settings, key, value)
            except Exception:
                logger.warning(f"Failed overriding setting: {key}, value: {value}")
    if "super_user" in sets_dict:
        setattr(settings, "super_user", sets_dict["super_user"])


async def init_admin_settings(super_user: Optional[str] = None) -> SuperSettings:
    account = None
    if super_user:
        account = await get_account(super_user)
    if not account:
        account = await create_account(user_id=super_user)
    if not account.wallets or len(account.wallets) == 0:
        await create_wallet(user_id=account.id)

    editable_settings = EditableSettings.from_dict(settings.dict())

    return await create_admin_settings(account.id, editable_settings.dict())


class WebsocketConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, item_id: str):
        logger.debug(f"Websocket connected to {item_id}")
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_data(self, message: str, item_id: str):
        for connection in self.active_connections:
            if connection.path_params["item_id"] == item_id:
                await connection.send_text(message)


websocketManager = WebsocketConnectionManager()


async def websocketUpdater(item_id, data):
    return await websocketManager.send_data(f"{data}", item_id)


async def switch_to_voidwallet() -> None:
    WALLET = get_wallet_class()
    if WALLET.__class__.__name__ == "VoidWallet":
        return
    set_wallet_class("VoidWallet")
    settings.lnbits_backend_wallet_class = "VoidWallet"


async def get_balance_delta() -> Tuple[int, int, int]:
    WALLET = get_wallet_class()
    total_balance = await get_total_balance()
    error_message, node_balance = await WALLET.status()
    if error_message:
        raise Exception(error_message)
    return node_balance - total_balance, node_balance, total_balance
