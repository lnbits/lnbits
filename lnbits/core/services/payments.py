import asyncio
import time
from datetime import datetime, timedelta, timezone

from bolt11 import Bolt11, MilliSatoshi, Tags
from bolt11 import decode as bolt11_decode
from bolt11 import encode as bolt11_encode
from lnurl import LnurlErrorResponse, LnurlSuccessResponse
from lnurl import execute_withdraw as lnurl_withdraw
from loguru import logger

from lnbits.core.crud.payments import get_daily_stats
from lnbits.core.db import db
from lnbits.core.models import PaymentDailyStats, PaymentFilters
from lnbits.core.models.payments import CreateInvoice
from lnbits.db import Connection, Filters
from lnbits.decorators import check_user_extension_access
from lnbits.exceptions import InvoiceError, PaymentError, UnsupportedError
from lnbits.fiat import get_fiat_provider
from lnbits.helpers import check_callback_url
from lnbits.settings import settings
from lnbits.tasks import create_task, internal_invoice_queue_put
from lnbits.utils.crypto import fake_privkey, random_secret_and_hash, verify_preimage
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis, satoshis_amount_as_fiat
from lnbits.wallets import fake_wallet, get_funding_source
from lnbits.wallets.base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
)

from ..crud import (
    check_internal,
    create_payment,
    get_payments,
    get_standalone_payment,
    get_wallet,
    get_wallet_payment,
    is_internal_status_success,
    update_payment,
)
from ..models import (
    CreatePayment,
    Payment,
    PaymentState,
    Wallet,
)
from .notifications import send_payment_notification_in_background

payment_lock = asyncio.Lock()
wallets_payments_lock: dict[str, asyncio.Lock] = {}


async def pay_invoice(
    *,
    wallet_id: str,
    payment_request: str,
    max_sat: int | None = None,
    extra: dict | None = None,
    description: str = "",
    tag: str = "",
    labels: list[str] | None = None,
    conn: Connection | None = None,
) -> Payment:
    if settings.lnbits_only_allow_incoming_payments:
        raise PaymentError("Only incoming payments allowed.", status="failed")
    invoice = _validate_payment_request(payment_request, max_sat)
    if not invoice.amount_msat:
        raise ValueError("Missig invoice amount.")

    async with db.reuse_conn(conn) if conn else db.connect() as new_conn:
        amount_msat = invoice.amount_msat
        wallet = await _check_wallet_for_payment(wallet_id, tag, amount_msat, new_conn)
        if not wallet.can_send_payments:
            raise PaymentError(
                "Wallet does not have permission to pay invoices.",
                status="failed",
            )

        if await is_internal_status_success(invoice.payment_hash, new_conn):
            raise PaymentError("Internal invoice already paid.", status="failed")

        _, extra = await calculate_fiat_amounts(amount_msat / 1000, wallet, extra=extra)

        create_payment_model = CreatePayment(
            wallet_id=wallet.source_wallet_id,
            bolt11=payment_request,
            payment_hash=invoice.payment_hash,
            amount_msat=-amount_msat,
            expiry=invoice.expiry_date,
            memo=description or invoice.description or "",
            extra=extra,
            labels=labels,
        )

    payment = await _pay_invoice(wallet.source_wallet_id, create_payment_model, conn)

    async with db.reuse_conn(conn) if conn else db.connect() as new_conn:
        await _credit_service_fee_wallet(wallet, payment, new_conn)

    return payment


async def create_payment_request(
    wallet_id: str, invoice_data: CreateInvoice
) -> Payment:
    """
    Create a lightning invoice or a fiat payment request.
    """
    if invoice_data.fiat_provider:
        return await create_fiat_invoice(wallet_id, invoice_data)

    return await create_wallet_invoice(wallet_id, invoice_data)


async def create_fiat_invoice(
    wallet_id: str, invoice_data: CreateInvoice, conn: Connection | None = None
) -> Payment:
    fiat_provider_name = invoice_data.fiat_provider
    if not fiat_provider_name:
        raise ValueError("Fiat provider is required for fiat invoices.")
    if not settings.is_fiat_provider_enabled(fiat_provider_name):
        raise ValueError(
            f"Fiat provider '{fiat_provider_name}' is not enabled.",
        )

    if invoice_data.unit == "sat":
        raise ValueError("Fiat provider cannot be used with satoshis.")
    amount_sat = await fiat_amount_as_satoshis(invoice_data.amount, invoice_data.unit)
    await _check_fiat_invoice_limits(amount_sat, fiat_provider_name, conn)

    invoice_data.internal = True  # use FakeWallet for fiat invoices
    if not invoice_data.memo:
        invoice_data.memo = settings.lnbits_site_title + f" ({fiat_provider_name})"

    internal_payment = await create_wallet_invoice(wallet_id, invoice_data)

    fiat_provider = await get_fiat_provider(fiat_provider_name)
    if not fiat_provider:
        raise InvoiceError("No fiat provider found.", status="failed")

    fiat_invoice = await fiat_provider.create_invoice(
        amount=invoice_data.amount,
        payment_hash=internal_payment.payment_hash,
        currency=invoice_data.unit,
        memo=invoice_data.memo,
        extra=invoice_data.extra or {},
    )

    if fiat_invoice.failed:
        logger.warning(fiat_invoice.error_message)
        internal_payment.status = PaymentState.FAILED
        await update_payment(internal_payment, conn=conn)
        raise ValueError(
            f"Cannot create payment request for '{fiat_provider_name}'.",
        )

    internal_payment.fee = -abs(
        service_fee_fiat(internal_payment.msat, fiat_provider_name)
    )

    internal_payment.fiat_provider = fiat_provider_name
    internal_payment.extra["fiat_checking_id"] = fiat_invoice.checking_id
    # todo: move to payent
    internal_payment.extra["fiat_payment_request"] = fiat_invoice.payment_request
    new_checking_id = (
        f"fiat_{fiat_provider_name}_"
        f"{fiat_invoice.checking_id or internal_payment.checking_id}"
    )
    await update_payment(internal_payment, new_checking_id, conn=conn)
    internal_payment.checking_id = new_checking_id

    return internal_payment


async def create_wallet_invoice(wallet_id: str, data: CreateInvoice) -> Payment:
    description_hash = None
    unhashed_description = None
    memo = data.memo or settings.lnbits_site_title
    if data.description_hash or data.unhashed_description:
        if data.description_hash:
            try:
                description_hash = bytes.fromhex(data.description_hash)
            except ValueError as exc:
                raise ValueError(
                    "'description_hash' must be a valid hex string"
                ) from exc
        if data.unhashed_description:
            try:
                unhashed_description = bytes.fromhex(data.unhashed_description)
            except ValueError as exc:
                raise ValueError(
                    "'unhashed_description' must be a valid hex string",
                ) from exc
        # do not save memo if description_hash or unhashed_description is set
        memo = ""

    payment = await create_invoice(
        wallet_id=wallet_id,
        amount=data.amount,
        memo=memo,
        currency=data.unit,
        description_hash=description_hash,
        unhashed_description=unhashed_description,
        expiry=data.expiry,
        extra=data.extra,
        webhook=data.webhook,
        internal=data.internal,
        payment_hash=data.payment_hash,
        labels=data.labels,
    )

    if data.lnurl_withdraw:
        try:
            check_callback_url(data.lnurl_withdraw.callback)
            res = await lnurl_withdraw(
                data.lnurl_withdraw,
                payment.bolt11,
                user_agent=settings.user_agent,
                timeout=10,
            )
            if isinstance(res, LnurlErrorResponse):
                payment.extra["lnurl_response"] = res.reason
                payment.status = "failed"
            elif isinstance(res, LnurlSuccessResponse):
                payment.extra["lnurl_response"] = True
                payment.status = "success"
        except Exception as exc:
            payment.extra["lnurl_response"] = str(exc)
            payment.status = "failed"
        # updating to payment here would run into a race condition
        # with the payment listeners and they will overwrite each other

    return payment


async def create_invoice(
    *,
    wallet_id: str,
    amount: float,
    currency: str | None = "sat",
    memo: str,
    description_hash: bytes | None = None,
    unhashed_description: bytes | None = None,
    expiry: int | None = None,
    extra: dict | None = None,
    webhook: str | None = None,
    internal: bool | None = False,
    payment_hash: str | None = None,
    labels: list[str] | None = None,
    conn: Connection | None = None,
) -> Payment:
    if not amount > 0:
        raise InvoiceError("Amountless invoices not supported.", status="failed")

    user_wallet = await get_wallet(wallet_id, conn=conn)
    if not user_wallet:
        raise InvoiceError(f"Could not fetch wallet '{wallet_id}'.", status="failed")

    if not user_wallet.can_receive_payments:
        raise InvoiceError(
            "Wallet does not have permission to create invoices.",
            status="failed",
        )

    invoice_memo = None if description_hash else memo[:640]

    # use the fake wallet if the invoice is for internal use only
    funding_source = fake_wallet if internal else get_funding_source()

    amount_sat, extra = await calculate_fiat_amounts(
        amount, user_wallet, currency, extra
    )

    if amount_sat > settings.lnbits_max_incoming_payment_amount_sats:
        raise InvoiceError(
            f"Invoice amount {amount_sat} sats is too high. Max allowed: "
            f"{settings.lnbits_max_incoming_payment_amount_sats} sats.",
            status="failed",
        )
    if settings.is_wallet_max_balance_exceeded(
        user_wallet.balance_msat / 1000 + amount_sat
    ):
        raise InvoiceError(
            f"Wallet balance cannot exceed "
            f"{settings.lnbits_wallet_limit_max_balance} sats.",
            status="failed",
        )

    if payment_hash:
        try:
            invoice_response = await funding_source.create_hold_invoice(
                amount=amount_sat,
                memo=invoice_memo,
                payment_hash=payment_hash,
                description_hash=description_hash,
            )
            extra["hold_invoice"] = True
        except UnsupportedError as exc:
            raise InvoiceError(
                "Hold invoices are not supported by the funding source.",
                status="failed",
            ) from exc
    else:
        invoice_response = await funding_source.create_invoice(
            amount=amount_sat,
            memo=invoice_memo,
            description_hash=description_hash,
            unhashed_description=unhashed_description,
            expiry=expiry or settings.lightning_invoice_expiry,
        )
    if (
        not invoice_response.ok
        or not invoice_response.payment_request
        or not invoice_response.checking_id
    ):
        raise InvoiceError(
            message=invoice_response.error_message or "unexpected backend error.",
            status="pending",
        )
    invoice = bolt11_decode(invoice_response.payment_request)

    create_payment_model = CreatePayment(
        wallet_id=user_wallet.source_wallet_id,
        bolt11=invoice_response.payment_request,
        payment_hash=invoice.payment_hash,
        preimage=invoice_response.preimage,
        amount_msat=amount_sat * 1000,
        expiry=invoice.expiry_date,
        memo=memo,
        extra=extra,
        webhook=webhook,
        fee=invoice_response.fee_msat or 0,
        labels=labels,
    )

    payment = await create_payment(
        checking_id=invoice_response.checking_id,
        data=create_payment_model,
        conn=conn,
    )

    return payment


async def update_pending_payments(wallet_id: str):
    pending_payments = await get_payments(
        wallet_id=wallet_id,
        pending=True,
        exclude_uncheckable=True,
    )
    for payment in pending_payments:
        await update_pending_payment(payment)


async def update_pending_payment(payment: Payment) -> Payment:
    status = await payment.check_status()
    if status.failed:
        payment.status = PaymentState.FAILED
        await update_payment(payment)
    elif status.success:
        payment = await update_payment_success_status(payment, status)
    return payment


async def check_pending_payments():
    """
    check_pending_payments is called during startup to check for pending payments with
    the backend and also to delete expired invoices. Incoming payments will be
    checked only once, outgoing pending payments will be checked regularly.
    """
    funding_source = get_funding_source()
    if funding_source.__class__.__name__ == "VoidWallet":
        logger.warning("Task: skipping pending check for VoidWallet")
        return
    start_time = time.time()
    pending_payments = await get_payments(
        since=(int(time.time()) - 60 * 60 * 24 * 15),  # 15 days ago
        complete=False,
        pending=True,
        exclude_uncheckable=True,
    )
    count = len(pending_payments)
    if count > 0:
        logger.info(f"Task: checking {count} pending payments of last 15 days...")
        for i, payment in enumerate(pending_payments):
            payment = await update_pending_payment(payment)
            prefix = f"payment ({i+1} / {count})"
            logger.debug(f"{prefix} {payment.status} {payment.checking_id}")
            await asyncio.sleep(0.01)  # to avoid complete blocking
        logger.info(
            f"Task: pending check finished for {count} payments"
            f" (took {time.time() - start_time:0.3f} s)"
        )


def fee_reserve_total(amount_msat: int, internal: bool = False) -> int:
    return fee_reserve(amount_msat, internal) + service_fee(amount_msat, internal)


def fee_reserve(amount_msat: int, internal: bool = False) -> int:
    amount_msat = abs(amount_msat)
    return settings.fee_reserve(amount_msat, internal)


def service_fee(amount_msat: int, internal: bool = False) -> int:
    amount_msat = abs(amount_msat)
    service_fee_percent = settings.lnbits_service_fee
    fee_max = settings.lnbits_service_fee_max * 1000
    if settings.lnbits_service_fee_wallet:
        if internal and settings.lnbits_service_fee_ignore_internal:
            return 0
        fee_percentage = int(amount_msat / 100 * service_fee_percent)
        if fee_max > 0 and fee_percentage > fee_max:
            return fee_max
        else:
            return fee_percentage
    else:
        return 0


def service_fee_fiat(amount_msat: int, fiat_provider_name: str) -> int:
    """
    Calculate the service fee for a fiat provider based on the amount in msat.
    Return the fee in msat.
    """
    limits = settings.get_fiat_provider_limits(fiat_provider_name)
    if not limits:
        return 0
    amount_msat = abs(amount_msat)
    fee_max = limits.service_max_fee_sats * 1000
    if not limits.service_fee_wallet_id:
        return 0

    fee_percentage = int(amount_msat / 100 * limits.service_fee_percent)
    if fee_max > 0 and fee_percentage > fee_max:
        return fee_max
    else:
        return fee_percentage


async def update_wallet_balance(
    wallet: Wallet,
    amount: int,
    conn: Connection | None = None,
):
    if amount == 0:
        raise ValueError("Amount cannot be 0.")

    # negative balance change
    if amount < 0:
        if wallet.balance + amount < 0:
            raise ValueError("Balance change failed, can not go into negative balance.")
        async with db.reuse_conn(conn) if conn else db.connect() as conn:
            payment_secret, payment_hash = random_secret_and_hash()
            invoice = Bolt11(
                currency="bc",
                amount_msat=MilliSatoshi(abs(amount) * 1000),
                date=int(time.time()),
                tags=Tags.from_dict(
                    {
                        "payment_hash": payment_hash,
                        "payment_secret": payment_secret,
                        "description": "Admin debit",
                    }
                ),
            )
            privkey = fake_privkey(settings.fake_wallet_secret)
            bolt11 = bolt11_encode(invoice, privkey)
            await create_payment(
                checking_id=f"internal_{payment_hash}",
                data=CreatePayment(
                    wallet_id=wallet.source_wallet_id,
                    bolt11=bolt11,
                    payment_hash=payment_hash,
                    amount_msat=amount * 1000,
                    memo="Admin debit",
                ),
                status=PaymentState.SUCCESS,
                conn=conn,
            )
        return None

    # positive balance change
    if (
        settings.lnbits_wallet_limit_max_balance > 0
        and wallet.balance + amount > settings.lnbits_wallet_limit_max_balance
    ):
        raise ValueError("Balance change failed, amount exceeds maximum balance.")
    async with db.reuse_conn(conn) if conn else db.connect() as conn:
        payment = await create_invoice(
            wallet_id=wallet.source_wallet_id,
            amount=amount,
            memo="Admin credit",
            internal=True,
            conn=conn,
        )
        payment.status = PaymentState.SUCCESS
        await update_payment(payment, conn=conn)
        await internal_invoice_queue_put(payment.checking_id)


async def check_wallet_limits(
    wallet_id: str, amount_msat: int, conn: Connection | None = None
):
    await check_time_limit_between_transactions(wallet_id, conn)
    await check_wallet_daily_withdraw_limit(wallet_id, amount_msat, conn)


async def check_time_limit_between_transactions(
    wallet_id: str, conn: Connection | None = None
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
    wallet_id: str, amount_msat: int, conn: Connection | None = None
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


async def calculate_fiat_amounts(
    amount: float,
    wallet: Wallet,
    currency: str | None = None,
    extra: dict | None = None,
) -> tuple[int, dict]:
    wallet_currency = wallet.currency or settings.lnbits_default_accounting_currency
    fiat_amounts: dict = extra or {}
    if currency and currency != "sat":
        amount_sat = await fiat_amount_as_satoshis(amount, currency)
        if currency != wallet_currency:
            fiat_amounts["fiat_currency"] = currency
            fiat_amounts["fiat_amount"] = round(amount, ndigits=3)
            fiat_amounts["fiat_rate"] = amount_sat / amount
            fiat_amounts["btc_rate"] = (amount / amount_sat) * 100_000_000
    else:
        amount_sat = int(amount)

    if wallet_currency:
        try:
            if wallet_currency == currency:
                fiat_amount = amount
            else:
                fiat_amount = await satoshis_amount_as_fiat(amount_sat, wallet_currency)
            fiat_amounts["wallet_fiat_currency"] = wallet_currency
            fiat_amounts["wallet_fiat_amount"] = round(fiat_amount, ndigits=3)
            fiat_amounts["wallet_fiat_rate"] = amount_sat / fiat_amount
            fiat_amounts["wallet_btc_rate"] = (fiat_amount / amount_sat) * 100_000_000
        except Exception as e:
            logger.error(f"Error calculating fiat amount for wallet '{wallet.id}': {e}")

    logger.debug(
        f"Calculated fiat amounts {wallet.id=} {amount=} {currency=}: {fiat_amounts=}"
    )

    return amount_sat, fiat_amounts


async def check_transaction_status(
    wallet_id: str, payment_hash: str, conn: Connection | None = None
) -> PaymentStatus:
    payment: Payment | None = await get_wallet_payment(
        wallet_id, payment_hash, conn=conn
    )
    if not payment:
        return PaymentPendingStatus()

    if payment.status == PaymentState.SUCCESS.value:
        return PaymentSuccessStatus(fee_msat=payment.fee)

    return await payment.check_status()


async def get_payments_daily_stats(
    filters: Filters[PaymentFilters],
    user_id: str | None = None,
) -> list[PaymentDailyStats]:
    data_in, data_out = await get_daily_stats(filters, user_id=user_id)
    balance_total: float = 0

    _none = PaymentDailyStats(date=datetime.now(timezone.utc))
    if len(data_in) == 0 and len(data_out) == 0:
        return []
    if len(data_in) == 0:
        data_in = [_none]
    if len(data_out) == 0:
        data_out = [_none]

    data: list[PaymentDailyStats] = []

    def _tz(dt: datetime) -> datetime:
        return dt.replace(tzinfo=timezone.utc)

    start_date = min(_tz(data_in[0].date), _tz(data_out[0].date))
    end_date = max(_tz(data_in[-1].date), _tz(data_out[-1].date))
    delta = timedelta(days=1)
    while start_date <= end_date:

        data_in_point = next((x for x in data_in if _tz(x.date) == start_date), _none)
        data_out_point = next((x for x in data_out if _tz(x.date) == start_date), _none)

        balance_total += data_in_point.balance + data_out_point.balance
        data.append(
            PaymentDailyStats(
                date=start_date,
                balance=balance_total // 1000,
                balance_in=data_in_point.balance // 1000,
                balance_out=data_out_point.balance // 1000,
                payments_count=data_in_point.payments_count
                + data_out_point.payments_count,
                count_in=data_in_point.payments_count,
                count_out=data_out_point.payments_count,
                fee=(data_in_point.fee + data_out_point.fee) // 1000,
            )
        )

        start_date += delta

    return data


async def _pay_invoice(
    wallet_id: str,
    create_payment_model: CreatePayment,
    conn: Connection | None = None,
):
    async with payment_lock:
        if wallet_id not in wallets_payments_lock:
            wallets_payments_lock[wallet_id] = asyncio.Lock()

    async with wallets_payments_lock[wallet_id]:
        # get the wallet again to make sure we have the latest balance
        wallet = await get_wallet(wallet_id, conn=conn)
        if not wallet:
            raise PaymentError(
                f"Could not fetch wallet '{wallet_id}'.", status="failed"
            )

        payment = await _pay_internal_invoice(wallet, create_payment_model, conn)
        if not payment:
            payment = await _pay_external_invoice(wallet, create_payment_model, conn)
        return payment


async def _pay_internal_invoice(
    wallet: Wallet,
    create_payment_model: CreatePayment,
    conn: Connection | None = None,
) -> Payment | None:
    """
    Pay an internal payment.
    returns None if the payment is not internal.
    """
    # check_internal() returns the payment of the invoice we're waiting for
    # (pending only)
    internal_payment = await check_internal(
        create_payment_model.payment_hash, conn=conn
    )
    if not internal_payment:
        return None

    # perform additional checks on the internal payment
    # the payment hash is not enough to make sure that this is the same invoice
    internal_invoice = await get_standalone_payment(
        internal_payment.checking_id, incoming=True, conn=conn
    )
    if not internal_invoice:
        raise PaymentError("Internal payment not found.", status="failed")

    amount_msat = create_payment_model.amount_msat
    if (
        internal_invoice.amount != abs(amount_msat)
        or internal_invoice.bolt11 != create_payment_model.bolt11.lower()
    ):
        raise PaymentError("Invalid invoice. Bolt11 changed.", status="failed")

    fee_reserve_total_msat = fee_reserve_total(amount_msat, internal=True)
    create_payment_model.fee = abs(fee_reserve_total_msat)

    if wallet.balance_msat < abs(amount_msat) + fee_reserve_total_msat:
        raise PaymentError("Insufficient balance.", status="failed")

    # release the preimage
    create_payment_model.preimage = internal_invoice.preimage

    internal_id = f"internal_{create_payment_model.payment_hash}"
    logger.debug(f"creating temporary internal payment with id {internal_id}")
    payment = await create_payment(
        checking_id=internal_id,
        data=create_payment_model,
        status=PaymentState.SUCCESS,
        conn=conn,
    )

    # mark the invoice from the other side as not pending anymore
    # so the other side only has access to his new money when we are sure
    # the payer has enough to deduct from
    internal_payment.status = PaymentState.SUCCESS
    await update_payment(internal_payment, conn=conn)
    logger.success(f"internal payment successful {internal_payment.checking_id}")

    send_payment_notification_in_background(wallet, payment)

    # notify receiver asynchronously
    from lnbits.tasks import internal_invoice_queue

    logger.debug(f"enqueuing internal invoice {internal_payment.checking_id}")
    await internal_invoice_queue.put(internal_payment.checking_id)

    return payment


async def _pay_external_invoice(
    wallet: Wallet,
    create_payment_model: CreatePayment,
    conn: Connection | None = None,
) -> Payment:
    checking_id = create_payment_model.payment_hash
    amount_msat = create_payment_model.amount_msat

    fee_reserve_total_msat = fee_reserve_total(amount_msat, internal=False)

    if wallet.balance_msat < abs(amount_msat):
        raise PaymentError("Insufficient balance.", status="failed")
    if wallet.balance_msat < abs(amount_msat) + fee_reserve_total_msat:
        raise PaymentError(
            f"You must reserve at least ({round(fee_reserve_total_msat/1000)}"
            "  sat) to cover potential routing fees.",
            status="failed",
        )
    # check if there is already a payment with the same checking_id
    old_payment = await get_standalone_payment(checking_id, conn=conn)
    if old_payment:
        return await _verify_external_payment(old_payment, conn)

    create_payment_model.fee = -abs(fee_reserve_total_msat)
    payment = await create_payment(
        checking_id=checking_id,
        data=create_payment_model,
        conn=conn,
    )

    fee_reserve_msat = fee_reserve(amount_msat, internal=False)

    task = create_task(
        _fundingsource_pay_invoice(checking_id, payment.bolt11, fee_reserve_msat)
    )

    # make sure a hold invoice or deferred payment is not blocking the server
    wait_time = max(1, settings.lnbits_funding_source_pay_invoice_wait_seconds)
    try:
        payment_response = await asyncio.wait_for(task, timeout=wait_time)
    except asyncio.TimeoutError:
        # return pending payment on timeout
        logger.debug(
            f"payment timeout after {wait_time}s, {checking_id} is still pending"
        )
        return payment

    # payment failed
    if (
        payment_response.checking_id is None
        or payment_response.ok is False
        or payment_response.checking_id != checking_id
    ):
        payment.status = PaymentState.FAILED
        await update_payment(payment, conn=conn)
        message = payment_response.error_message or "without an error message."
        raise PaymentError(f"Payment failed: {message}", status="failed")

    if payment_response.success:
        payment = await update_payment_success_status(
            payment, payment_response, conn=conn
        )
        send_payment_notification_in_background(wallet, payment)
        logger.success(f"payment successful {payment_response.checking_id}")

    payment.checking_id = payment_response.checking_id
    return payment


async def update_payment_success_status(
    payment: Payment,
    status: PaymentStatus,
    conn: Connection | None = None,
) -> Payment:
    if status.success:
        service_fee_msat = service_fee(payment.amount, internal=False)
        payment.status = PaymentState.SUCCESS
        payment.fee = -(abs(status.fee_msat or 0) + abs(service_fee_msat))
        payment.preimage = payment.preimage or status.preimage
        await update_payment(payment, conn=conn)
    return payment


async def _fundingsource_pay_invoice(
    checking_id: str, bolt11: str, fee_reserve_msat: int
) -> PaymentResponse:
    logger.debug(f"fundingsource: sending payment {checking_id}")
    funding_source = get_funding_source()
    payment_response: PaymentResponse = await funding_source.pay_invoice(
        bolt11, fee_reserve_msat
    )
    logger.debug(f"backend: pay_invoice finished {checking_id}, {payment_response}")
    return payment_response


async def _verify_external_payment(
    payment: Payment, conn: Connection | None = None
) -> Payment:
    # fail on pending payments
    if payment.pending:
        raise PaymentError("Payment is still pending.", status="pending")
    if payment.success:
        raise PaymentError("Payment already paid.", status="success")

    # payment failed
    status = await payment.check_status()
    if status.failed:
        raise PaymentError(
            "Payment is failed node, retrying is not possible.", status="failed"
        )

    if status.success:
        # payment was successful on the fundingsource
        await update_payment_success_status(payment, status, conn=conn)
        raise PaymentError(
            "Failed payment was already paid on the fundingsource.",
            status="success",
        )

    # status.pending fall through and try again
    return payment


async def _check_wallet_for_payment(
    wallet_id: str,
    tag: str,
    amount_msat: int,
    conn: Connection | None = None,
):
    wallet = await get_wallet(wallet_id, conn=conn)
    if not wallet:
        raise PaymentError(f"Could not fetch wallet '{wallet_id}'.", status="failed")

    # check if the payment is made for an extension that the user disabled
    status = await check_user_extension_access(wallet.user, tag, conn=conn)
    if not status.success:
        raise PaymentError(status.message)

    await check_wallet_limits(wallet_id, amount_msat, conn)
    return wallet


def _validate_payment_request(
    payment_request: str, max_sat: int | None = None
) -> Bolt11:
    try:
        invoice = bolt11_decode(payment_request)
    except Exception as exc:
        raise PaymentError("Bolt11 decoding failed.", status="failed") from exc

    if not invoice.amount_msat or not invoice.amount_msat > 0:
        raise PaymentError("Amountless invoices not supported.", status="failed")

    max_sat = max_sat or settings.lnbits_max_outgoing_payment_amount_sats
    max_sat = min(max_sat, settings.lnbits_max_outgoing_payment_amount_sats)
    if invoice.amount_msat > max_sat * 1000:
        raise PaymentError(
            f"Invoice amount {invoice.amount_msat // 1000} sats is too high. "
            f"Max allowed: {max_sat} sats.",
            status="failed",
        )

    return invoice


async def _credit_service_fee_wallet(
    wallet: Wallet, payment: Payment, conn: Connection | None = None
):
    service_fee_msat = service_fee(payment.amount, internal=payment.is_internal)
    if not settings.lnbits_service_fee_wallet or not service_fee_msat:
        return

    memo = f"""
        Service fee for payment of {abs(payment.sat)} sats.
        Wallet: '{wallet.name}' ({wallet.source_wallet_id})."""

    create_payment_model = CreatePayment(
        wallet_id=settings.lnbits_service_fee_wallet,
        bolt11=payment.bolt11,
        payment_hash=payment.payment_hash,
        amount_msat=abs(service_fee_msat),
        memo=memo,
    )
    await create_payment(
        checking_id=f"service_fee_{payment.payment_hash}",
        data=create_payment_model,
        status=PaymentState.SUCCESS,
        conn=conn,
    )


async def _check_fiat_invoice_limits(
    amount_sat: int, fiat_provider_name: str, conn: Connection | None = None
):
    limits = settings.get_fiat_provider_limits(fiat_provider_name)
    if not limits:
        raise ValueError(
            f"Fiat provider '{fiat_provider_name}' does not have limits configured.",
        )

    min_amount_sat = limits.service_min_amount_sats
    if min_amount_sat and (amount_sat < min_amount_sat):
        raise ValueError(
            f"Minimum amount is {min_amount_sat} " f"sats for '{fiat_provider_name}'.",
        )
    max_amount_sats = limits.service_max_amount_sats
    if max_amount_sats and (amount_sat > max_amount_sats):
        raise ValueError(
            f"Maximum amount is {max_amount_sats} " f"sats for '{fiat_provider_name}'.",
        )

    if limits.service_max_fee_sats > 0 or limits.service_fee_percent > 0:
        if not limits.service_fee_wallet_id:
            raise ValueError(
                f"Fiat provider '{fiat_provider_name}' service fee wallet missing.",
            )
        fees_wallet = await get_wallet(limits.service_fee_wallet_id, conn=conn)
        if not fees_wallet:
            raise ValueError(
                f"Fiat provider '{fiat_provider_name}' service fee wallet not found.",
            )

    if limits.service_faucet_wallet_id:
        faucet_wallet = await get_wallet(limits.service_faucet_wallet_id, conn=conn)
        if not faucet_wallet:
            raise ValueError(
                f"Fiat provider '{fiat_provider_name}' faucet wallet not found.",
            )
        if faucet_wallet.balance < amount_sat:
            raise ValueError(
                f"The amount exceeds the '{fiat_provider_name}'"
                "faucet wallet balance.",
            )


async def settle_hold_invoice(payment: Payment, preimage: str) -> InvoiceResponse:
    if verify_preimage(preimage, payment.payment_hash) is False:
        raise InvoiceError("Invalid preimage.", status="failed")

    funding_source = get_funding_source()
    response = await funding_source.settle_hold_invoice(preimage=preimage)

    if not response.ok:
        raise InvoiceError(
            response.error_message or "Unexpected backend error.", status="failed"
        )

    payment.preimage = preimage
    payment.extra["hold_invoice_settled"] = True
    await update_payment(payment)

    return response


async def cancel_hold_invoice(payment: Payment) -> InvoiceResponse:
    funding_source = get_funding_source()
    response = await funding_source.cancel_hold_invoice(
        payment_hash=payment.payment_hash
    )

    if not response.ok:
        raise InvoiceError(
            response.error_message or "Unexpected backend error.", status="failed"
        )

    payment.status = PaymentState.FAILED
    payment.extra["hold_invoice_cancelled"] = True
    await update_payment(payment)

    return response
