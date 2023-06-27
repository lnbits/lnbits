import asyncio
import json
from io import BytesIO
from typing import Dict, List, Optional, Tuple, TypedDict
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import Depends, WebSocket
from lnurl import LnurlErrorResponse
from lnurl import decode as decode_lnurl
from loguru import logger

from lnbits import bolt11
from lnbits.core.models import PaymentStatus
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
from lnbits.wallets import FAKE_WALLET, get_wallet_class, set_wallet_class
from lnbits.wallets.base import PaymentResponse

from . import db
from .crud import (
    check_internal,
    check_internal_pending,
    create_account,
    create_admin_settings,
    create_payment,
    create_wallet,
    delete_wallet_payment,
    get_account,
    get_standalone_payment,
    get_super_settings,
    get_total_balance,
    get_wallet,
    get_wallet_payment,
    update_payment_details,
    update_payment_status,
    update_super_user,
)
from .helpers import to_valid_user_id
from .models import Payment


class PaymentFailure(Exception):
    pass


class InvoiceFailure(Exception):
    pass


async def create_invoice(
    *,
    wallet_id: str,
    amount: int,  # in satoshis
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

    invoice_memo = None if description_hash else memo

    # use the fake wallet if the invoice is for internal use only
    wallet = FAKE_WALLET if internal else get_wallet_class()

    ok, checking_id, payment_request, error_message = await wallet.create_invoice(
        amount=amount,
        memo=invoice_memo,
        description_hash=description_hash,
        unhashed_description=unhashed_description,
        expiry=expiry or settings.lightning_invoice_expiry,
    )
    if not ok or not payment_request or not checking_id:
        raise InvoiceFailure(error_message or "unexpected backend error.")

    invoice = bolt11.decode(payment_request)

    amount_msat = amount * 1000
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
    conn: Optional[Connection] = None,
) -> str:
    """
    Pay a Lightning invoice.
    First, we create a temporary payment in the database with fees set to the reserve fee.
    We then check whether the balance of the payer would go negative.
    We then attempt to pay the invoice through the backend.
    If the payment is successful, we update the payment in the database with the payment details.
    If the payment is unsuccessful, we delete the temporary payment.
    If the payment is still in flight, we hope that some other process will regularly check for the payment.
    """
    invoice = bolt11.decode(payment_request)
    fee_reserve_msat = fee_reserve(invoice.amount_msat)
    async with (db.reuse_conn(conn) if conn else db.connect()) as conn:
        temp_id = invoice.payment_hash
        internal_id = f"internal_{invoice.payment_hash}"

        if invoice.amount_msat == 0:
            raise ValueError("Amountless invoices not supported.")
        if max_sat and invoice.amount_msat > max_sat * 1000:
            raise ValueError("Amount in invoice is too high.")

        # put all parameters that don't change here
        class PaymentKwargs(TypedDict):
            wallet_id: str
            payment_request: str
            payment_hash: str
            amount: int
            memo: str
            extra: Optional[Dict]

        payment_kwargs: PaymentKwargs = PaymentKwargs(
            wallet_id=wallet_id,
            payment_request=payment_request,
            payment_hash=invoice.payment_hash,
            amount=-invoice.amount_msat,
            memo=description or invoice.description or "",
            extra=extra,
        )

        # we check if an internal invoice exists that has already been paid (not pending anymore)
        if not await check_internal_pending(invoice.payment_hash, conn=conn):
            raise PaymentFailure("Internal invoice already paid.")

        # check_internal() returns the checking_id of the invoice we're waiting for (pending only)
        internal_checking_id = await check_internal(invoice.payment_hash, conn=conn)
        if internal_checking_id:
            # perform additional checks on the internal payment
            # the payment hash is not enough to make sure that this is the same invoice
            internal_invoice = await get_standalone_payment(
                internal_checking_id, incoming=True, conn=conn
            )
            assert internal_invoice is not None
            if (
                internal_invoice.amount != invoice.amount_msat
                or internal_invoice.bolt11 != payment_request.lower()
            ):
                raise PaymentFailure("Invalid invoice.")

            logger.debug(f"creating temporary internal payment with id {internal_id}")
            # create a new payment from this wallet
            await create_payment(
                checking_id=internal_id,
                fee=0,
                pending=False,
                conn=conn,
                **payment_kwargs,
            )
        else:
            logger.debug(f"creating temporary payment with id {temp_id}")
            # create a temporary payment here so we can check if
            # the balance is enough in the next step
            try:
                await create_payment(
                    checking_id=temp_id,
                    fee=-fee_reserve_msat,
                    conn=conn,
                    **payment_kwargs,
                )
            except Exception as e:
                logger.error(f"could not create temporary payment: {e}")
                # happens if the same wallet tries to pay an invoice twice
                raise PaymentFailure("Could not make payment.")

        # do the balance check
        wallet = await get_wallet(wallet_id, conn=conn)
        assert wallet, "Wallet for balancecheck could not be fetched"
        if wallet.balance_msat < 0:
            logger.debug("balance is too low, deleting temporary payment")
            if not internal_checking_id and wallet.balance_msat > -fee_reserve_msat:
                raise PaymentFailure(
                    f"You must reserve at least ({round(fee_reserve_msat/1000)} sat) to cover potential routing fees."
                )
            raise PermissionError("Insufficient balance.")

    if internal_checking_id:
        logger.debug(f"marking temporary payment as not pending {internal_checking_id}")
        # mark the invoice from the other side as not pending anymore
        # so the other side only has access to his new money when we are sure
        # the payer has enough to deduct from
        async with db.connect() as conn:
            await update_payment_status(
                checking_id=internal_checking_id, pending=False, conn=conn
            )

        # notify receiver asynchronously
        from lnbits.tasks import internal_invoice_queue

        logger.debug(f"enqueuing internal invoice {internal_checking_id}")
        await internal_invoice_queue.put(internal_checking_id)
    else:
        logger.debug(f"backend: sending payment {temp_id}")
        # actually pay the external invoice
        WALLET = get_wallet_class()
        payment: PaymentResponse = await WALLET.pay_invoice(
            payment_request, fee_reserve_msat
        )

        if payment.checking_id and payment.checking_id != temp_id:
            logger.warning(
                f"backend sent unexpected checking_id (expected: {temp_id} got: {payment.checking_id})"
            )

        logger.debug(f"backend: pay_invoice finished {temp_id}")
        if payment.checking_id and payment.ok is not False:
            # payment.ok can be True (paid) or None (pending)!
            logger.debug(f"updating payment {temp_id}")
            async with db.connect() as conn:
                await update_payment_details(
                    checking_id=temp_id,
                    pending=payment.ok is not True,
                    fee=payment.fee_msat,
                    preimage=payment.preimage,
                    new_checking_id=payment.checking_id,
                    conn=conn,
                )
                wallet = await get_wallet(wallet_id, conn=conn)
                if wallet:
                    await websocketUpdater(
                        wallet_id,
                        {
                            "wallet_balance": wallet.balance or None,
                            "payment": payment._asdict(),
                        },
                    )
                logger.debug(f"payment successful {payment.checking_id}")
        elif payment.checking_id is None and payment.ok is False:
            # payment failed
            logger.warning("backend sent payment failure")
            async with db.connect() as conn:
                logger.debug(f"deleting temporary payment {temp_id}")
                await delete_wallet_payment(temp_id, wallet_id, conn=conn)
            raise PaymentFailure(
                f"Payment failed: {payment.error_message}"
                or "Payment failed, but backend didn't give us an error message."
            )
        else:
            logger.warning(
                f"didn't receive checking_id from backend, payment may be stuck in database: {temp_id}"
            )

    return invoice.payment_hash


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
    except:
        logger.warning(
            f"failed to create invoice on redeem_lnurl_withdraw from {lnurl}. params: {res}"
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


# WARN: this same value must be used for balance check and passed to WALLET.pay_invoice(), it may cause a vulnerability if the values differ
def fee_reserve(amount_msat: int) -> int:
    reserve_min = settings.lnbits_reserve_fee_min
    reserve_percent = settings.lnbits_reserve_fee_percent
    return max(int(reserve_min), int(amount_msat * reserve_percent / 100.0))


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
            logger.warning("Initialized settings from enviroment variables.")

        if settings.super_user and settings.super_user != settings_db.super_user:
            # .env super_user overwrites DB super_user
            settings_db = await update_super_user(settings.super_user)

        update_cached_settings(settings_db.dict())

        admin_url = f'{settings.lnbits_baseurl}wallet?usr=<ID from ".super_user" file>'
        logger.success(f"✔️ Access super user account at: {admin_url}")

        # saving it to .super_user file
        with open(".super_user", "w") as file:
            file.write(settings.super_user)

        # callback for saas
        if (
            settings.lnbits_saas_callback
            and settings.lnbits_saas_secret
            and settings.lnbits_saas_instance_id
        ):
            send_admin_user_to_saas()


def update_cached_settings(sets_dict: dict):
    for key, value in sets_dict.items():
        if key not in readonly_variables:
            try:
                setattr(settings, key, value)
            except:
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
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
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
