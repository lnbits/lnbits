import asyncio
import logging
from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice, websocketUpdater
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_pegging, get_wallets, get_peggings
from .kollider_rest_client import KolliderRestClient, Order
from .models import Pegging

log = logging.getLogger(__name__)

async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    wallets = await get_wallets("USD")
    logger.debug(f"Hedged USD wallets: {len(wallets)}")

    while True:
        payment = await invoice_queue.get()

        hedges = await get_peggings(wallet_ids=payment.wallet_id)
        if not hedges:
            # no registered hedge settings
            continue

        payment.extra["peggingId"] = hedges[0].id

        await on_paid_invoice(payment)


async def on_paid_invoice(payment: Payment) -> None:
    pegging_id = payment.extra.get("peggingId")
    assert pegging_id

    pegging = await get_pegging(pegging_id)
    assert pegging


    strippedPayment = {
        "amount": payment.amount,
        "fee": payment.fee,
        "checking_id": payment.checking_id,
        "payment_hash": payment.payment_hash,
        "bolt11": payment.bolt11,
    }

    await websocketUpdater(pegging_id, str(strippedPayment))
    await update_position(pegging, payment.amount, "Ask")



async def update_position(pegging: Pegging, delta_amount: int, side: str) -> None:
    client = KolliderRestClient(pegging.base_url, pegging.api_key, pegging.api_secret, pegging.api_passphrase)
    """
    r = client.get_wallet_balances()
    logger.debug(f"{r}")
    r = client.get_positions()
    logger.debug(f"{r}")
    """
    symbol = f"BTC{pegging.currency}.PERP"
    t = client.get_ticker(symbol)
    if not t:
        logger.error(f"Couldn't obtain ticker {symbol} from Kollider")
        return
    logger.debug(f"ticker {t}")

    price = t.best_ask if side == "Bid" else t.best_bid
    fiat_amount = price*delta_amount/(1_000*100_000_000)

    if fiat_amount == 0:
        logger.error(f"Order amount {fiat_amount}. Too few sats?")
        return

    order = Order(
        symbol=symbol,
        quantity=fiat_amount,
        leverage=100,
        side=side,
        price=price,
    )
    r = client.place_order(order)
    if "error" in r:
        logger.error(f"Couldn't place order for wallet {pegging.wallet}")
    else:
        logger.debug(f"{pegging.wallet} order placed for {fiat_amount} {symbol}")

"""

    payment_hash, payment_request = await create_invoice(
        wallet_id=wallet_id,
        amount=int(tipAmount),
        internal=True,
        memo=f"pegging tip",
    )
    logger.debug(f"pegging: tip invoice created: {payment_hash}")

    checking_id = await pay_invoice(
        payment_request=payment_request,
        wallet_id=payment.wallet_id,
        extra={**payment.extra, "tipSplitted": True},
    )
    logger.debug(f"pegging: tip invoice paid: {checking_id}")

"""