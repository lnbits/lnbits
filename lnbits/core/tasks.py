import asyncio
from asyncio import Future
from typing import Dict, Optional

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from lnbits import bolt11
from lnbits.core.crud import (
    check_internal,
    check_internal_pending,
    create_payment,
    delete_wallet_payment,
    get_balance_notify,
    get_standalone_payment,
    get_wallet,
    get_wallet_payment,
    get_webpush_subscriptions_for_user,
    update_payment_details,
    update_payment_status,
)
from lnbits.core.db import db
from lnbits.core.models import Payment
from lnbits.core.services import (
    PaymentFailure,
    calculate_fiat_amounts,
    fee_reserve,
    get_balance_delta,
    send_payment_notification,
    switch_to_voidwallet,
)
from lnbits.settings import get_wallet_class, settings
from lnbits.tasks import (
    SseListenersDict,
    create_permanent_task,
    create_task,
    register_invoice_listener,
    send_push_notification,
)

api_invoice_listeners: Dict[str, asyncio.Queue] = SseListenersDict(
    "api_invoice_listeners"
)


def register_killswitch():
    """
    Registers a killswitch which will check lnbits-status repository for a signal from
    LNbits and will switch to VoidWallet if the killswitch is triggered.
    """
    logger.debug("Starting killswitch task")
    create_permanent_task(killswitch_task)


async def killswitch_task():
    while True:
        WALLET = get_wallet_class()
        if settings.lnbits_killswitch and WALLET.__class__.__name__ != "VoidWallet":
            with httpx.Client() as client:
                try:
                    r = client.get(settings.lnbits_status_manifest, timeout=4)
                    r.raise_for_status()
                    if r.status_code == 200:
                        ks = r.json().get("killswitch")
                        if ks and ks == 1:
                            logger.error(
                                "Switching to VoidWallet. Killswitch triggered."
                            )
                            await switch_to_voidwallet()
                except (httpx.ConnectError, httpx.RequestError):
                    logger.error(
                        "Cannot fetch lnbits status manifest."
                        f" {settings.lnbits_status_manifest}"
                    )
        await asyncio.sleep(settings.lnbits_killswitch_interval * 60)


async def register_watchdog():
    """
    Registers a watchdog which will check lnbits balance and nodebalance
    and will switch to VoidWallet if the watchdog delta is reached.
    """
    # TODO: implement watchdog properly
    # logger.debug("Starting watchdog task")
    # create_permanent_task(watchdog_task)


async def watchdog_task():
    while True:
        WALLET = get_wallet_class()
        if settings.lnbits_watchdog and WALLET.__class__.__name__ != "VoidWallet":
            try:
                delta, *_ = await get_balance_delta()
                logger.debug(f"Running watchdog task. current delta: {delta}")
                if delta + settings.lnbits_watchdog_delta <= 0:
                    logger.error(f"Switching to VoidWallet. current delta: {delta}")
                    await switch_to_voidwallet()
            except Exception as e:
                logger.error("Error in watchdog task", e)
        await asyncio.sleep(settings.lnbits_watchdog_interval * 60)


def register_task_listeners():
    """
    Registers an invoice listener queue for the core tasks. Incoming payments in this
    queue will eventually trigger the signals sent to all other extensions
    and fulfill other core tasks such as dispatching webhooks.
    """
    invoice_paid_queue = asyncio.Queue(5)
    # we register invoice_paid_queue to receive all incoming invoices
    register_invoice_listener(invoice_paid_queue, "core/tasks.py")
    # register a worker that will react to invoices
    create_task(wait_for_paid_invoices(invoice_paid_queue))


async def wait_for_paid_invoices(invoice_paid_queue: asyncio.Queue):
    """
    This worker dispatches events to all extensions,
    dispatches webhooks and balance notifys.
    """
    while True:
        payment = await invoice_paid_queue.get()
        logger.trace("received invoice paid event")
        # send information to sse channel
        await dispatch_api_invoice_listeners(payment)
        wallet = await get_wallet(payment.wallet_id)
        if wallet:
            await send_payment_notification(wallet, payment)
        # dispatch webhook
        if payment.webhook and not payment.webhook_status:
            await dispatch_webhook(payment)

        # dispatch balance_notify
        url = await get_balance_notify(payment.wallet_id)
        if url:
            async with httpx.AsyncClient() as client:
                try:
                    r = await client.post(url, timeout=4)
                    await mark_webhook_sent(payment, r.status_code)
                except (httpx.ConnectError, httpx.RequestError):
                    pass

        await send_payment_push_notification(payment)


async def dispatch_api_invoice_listeners(payment: Payment):
    """
    Emits events to invoice listener subscribed from the API.
    """
    for chan_name, send_channel in api_invoice_listeners.items():
        try:
            logger.debug(f"sending invoice paid event to {chan_name}")
            send_channel.put_nowait(payment)
        except asyncio.QueueFull:
            logger.error(f"removing sse listener {send_channel}:{chan_name}")
            api_invoice_listeners.pop(chan_name)


class PaymentJob(BaseModel):
    fut: Future = Field(
        default_factory=lambda: asyncio.get_event_loop().create_future()
    )

    wallet_id: str
    payment_request: str
    max_sat: Optional[int]
    memo: str
    extra: Optional[Dict]

    class Config:
        arbitrary_types_allowed = True


payment_queue: asyncio.Queue[PaymentJob] = asyncio.Queue()


async def _process_payment(job: PaymentJob) -> str:
    """
    Pay a Lightning invoice.
    First, we create a temporary payment in the database with fees set to the reserve
    fee. We then check whether the balance of the payer would go negative.
    We then attempt to pay the invoice through the backend. If the payment is
    successful, we update the payment in the database with the payment details.
    If the payment is unsuccessful, we delete the temporary payment.
    If the payment is still in flight, we hope that some other process
    will regularly check for the payment.
    """
    invoice = bolt11.decode(job.payment_request)
    fee_reserve_msat = fee_reserve(invoice.amount_msat)
    async with db.connect() as conn:
        temp_id = invoice.payment_hash
        internal_id = f"internal_{invoice.payment_hash}"

        if invoice.amount_msat == 0:
            raise ValueError("Amountless invoices not supported.")
        if job.max_sat and invoice.amount_msat > job.max_sat * 1000:
            raise ValueError("Amount in invoice is too high.")

        _, extra = await calculate_fiat_amounts(
            invoice.amount_msat / 1000, job.wallet_id, extra=job.extra, conn=conn
        )

        payment_kwargs = job.dict(include={"wallet_id", "payment_request", "extra"})
        payment_kwargs.update(
            amount=-invoice.amount_msat,
            payment_hash=invoice.payment_hash,
            memo=job.memo or invoice.description or "",
        )

        # we check if an internal invoice exists that has already been paid
        # (not pending anymore)
        if not await check_internal_pending(invoice.payment_hash, conn=conn):
            raise PaymentFailure("Internal invoice already paid.")

        # check_internal() returns the checking_id of the invoice we're waiting for
        # (pending only)
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
                or internal_invoice.bolt11 != job.payment_request.lower()
            ):
                raise PaymentFailure("Invalid invoice.")

            logger.debug(f"creating temporary internal payment with id {internal_id}")
            # create a new payment from this wallet
            new_payment = await create_payment(
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
                new_payment = await create_payment(
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
        wallet = await get_wallet(job.wallet_id, conn=conn)
        assert wallet, "Wallet for balancecheck could not be fetched"
        if wallet.balance_msat < 0:
            logger.debug("balance is too low, deleting temporary payment")
            if not internal_checking_id and wallet.balance_msat > -fee_reserve_msat:
                raise PaymentFailure(
                    f"You must reserve at least ({round(fee_reserve_msat/1000)} sat) to"
                    " cover potential routing fees."
                )
            raise PermissionError("Insufficient balance.")

    if internal_checking_id:
        logger.debug(f"marking temporary payment as not pending {internal_checking_id}")
        # mark the invoice from the other side as not pending anymore
        # so the other side only has access to his new money when we are sure
        # the payer has enough to deduct from
        await update_payment_status(checking_id=internal_checking_id, pending=False)
        await send_payment_notification(wallet, new_payment)

        # notify receiver asynchronously
        from lnbits.tasks import internal_invoice_queue

        logger.debug(f"enqueuing internal invoice {internal_checking_id}")
        await internal_invoice_queue.put(internal_checking_id)
    else:
        logger.debug(f"backend: sending payment {temp_id}")
        # actually pay the external invoice
        WALLET = get_wallet_class()
        payment = await WALLET.pay_invoice(job.payment_request, fee_reserve_msat)

        if payment.checking_id and payment.checking_id != temp_id:
            logger.warning(
                f"backend sent unexpected checking_id (expected: {temp_id} got:"
                f" {payment.checking_id})"
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
                wallet = await get_wallet(job.wallet_id, conn=conn)
                updated = await get_wallet_payment(
                    job.wallet_id, payment.checking_id, conn=conn
                )
                if wallet and updated:
                    await send_payment_notification(wallet, updated)
                logger.debug(f"payment successful {payment.checking_id}")
        elif payment.checking_id is None and payment.ok is False:
            # payment failed
            logger.warning("backend sent payment failure")
            logger.debug(f"deleting temporary payment {temp_id}")
            await delete_wallet_payment(temp_id, job.wallet_id)
            raise PaymentFailure(
                f"Payment failed: {payment.error_message}"
                or "Payment failed, but backend didn't give us an error message."
            )
        else:
            logger.warning(
                "didn't receive checking_id from backend, payment may be stuck in"
                f" database: {temp_id}"
            )

    return invoice.payment_hash


async def payment_processor():
    while True:
        job = await payment_queue.get()
        try:
            payment = await _process_payment(job)
            job.fut.set_result(payment)
        except (ValueError, PermissionError, PaymentFailure) as e:
            logger.info(
                f"could not process payment {job.payment_request} for {job.wallet_id}"
            )
            job.fut.set_exception(e)
        except Exception as e:
            logger.exception("error processing payment", e)
            job.fut.set_exception(e)
        finally:
            payment_queue.task_done()


async def dispatch_webhook(payment: Payment):
    """
    Dispatches the webhook to the webhook url.
    """
    logger.debug("sending webhook", payment.webhook)

    if not payment.webhook:
        return await mark_webhook_sent(payment, -1)

    async with httpx.AsyncClient() as client:
        data = payment.dict()
        try:
            r = await client.post(payment.webhook, json=data, timeout=40)
            await mark_webhook_sent(payment, r.status_code)
        except (httpx.ConnectError, httpx.RequestError):
            await mark_webhook_sent(payment, -1)


async def mark_webhook_sent(payment: Payment, status: int) -> None:
    await db.execute(
        """
        UPDATE apipayments SET webhook_status = ?
        WHERE hash = ?
        """,
        (status, payment.payment_hash),
    )


async def send_payment_push_notification(payment: Payment):
    wallet = await get_wallet(payment.wallet_id)

    if wallet:
        subscriptions = await get_webpush_subscriptions_for_user(wallet.user)

        amount = int(payment.amount / 1000)

        title = f"LNbits: {wallet.name}"
        body = f"You just received {amount} sat{'s'[:amount^1]}!"

        if payment.memo:
            body += f"\r\n{payment.memo}"

        for subscription in subscriptions:
            url = (
                f"https://{subscription.host}/wallet?usr={wallet.user}&wal={wallet.id}"
            )
            await send_push_notification(subscription, title, body, url)
