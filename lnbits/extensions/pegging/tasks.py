import asyncio
import logging
from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice, websocketUpdater
from lnbits.helpers import get_current_extension_name
from lnbits.tasks import register_invoice_listener

from .crud import get_pegging, get_pegged_currencies, get_peggings
from .kollider_rest_client import KolliderRestClient, Order
from .models import Pegging
from ...core import get_wallet

log = logging.getLogger(__name__)


async def hedge_loop():
    sleep_int = 30
    currencies = ["EUR", "USD"]
    no_hedge_msat = 10_000_000

    while True:
        for c in currencies:
            pegs = await get_pegged_currencies(c)
            logger.debug(f"Hedged {c} wallets: {len(pegs)}")

            for peg in pegs:
                symbol = f"BTC{peg.currency}.PERP"
                wallet = await get_wallet(peg.wallet)
                assert wallet

                percent = float(peg.percent) / 100.0  # TODO: same, type support
                to_hedge_msat = int(percent * wallet.balance_msat)

                c = KolliderRestClient(
                    peg.base_url, peg.api_key, peg.api_secret, peg.api_passphrase
                )

                c.cancel_all_orders(symbol)

                ps = c.get_positions()
                position_fiat = 0.0

                if hasattr(ps, symbol):
                    p = getattr(ps, symbol)
                    position_fiat = int(
                        p.quantity
                    )  # TODO: type conversions in data types of Kollider client

                t = c.get_ticker(symbol)

                if not t:
                    logger.error(f"Couldn't obtain ticker {symbol} from Kollider")
                    continue

                price = float(
                    t.last_price
                )  # TODO: type conversions in data types of Kollider client
                position_msat = int(position_fiat / price * (1_000.0 * 100_000_000.0))

                logger.debug(
                    f"Wallet {peg.wallet} position {position_fiat}{symbol}@{price} - {position_msat} msat"
                )

                # we have to account percentage when determining if we need to put order
                delta_msat = int(to_hedge_msat - position_msat)
                # but persentage also taken into account in update_hedge so hedge_delta goes without it
                hedge_delta = wallet.balance_msat - position_msat

                logger.debug(
                    f"Balance {wallet.balance}sat, position {position_msat/1000}sat,"
                    f" calculated delta {delta_msat/1000}sat, tolerance {no_hedge_msat/1000}sat"
                )

                if delta_msat > no_hedge_msat:
                    logger.debug(
                        f"Adding to {position_fiat}/{position_msat} {hedge_delta}msat@{price} {symbol}"
                    )
                    await update_position(peg, hedge_delta, "Ask")
                elif delta_msat < (-1) * no_hedge_msat:
                    logger.debug(
                        f"Removing from {position_fiat}/{position_msat} {hedge_delta}msat@{price} {symbol}"
                    )
                    await update_position(peg, abs(hedge_delta), "Bid")
                elif wallet.balance_msat < no_hedge_msat and position_msat > 0:
                    to_zero = int(1.0 / percent * position_msat)
                    logger.debug(f"Winding down {position_msat}msat@{price} {symbol}")
                    await update_position(peg, to_zero, "Bid")
                else:
                    continue

            await asyncio.sleep(sleep_int)


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, get_current_extension_name())

    while True:
        payment = await invoice_queue.get()

        hedges = await get_peggings(wallet_ids=payment.wallet_id)

        if hedges:
            await on_paid_invoice(payment, hedges[0])


async def on_paid_invoice(payment: Payment, pegging: Pegging) -> None:
    strippedPayment = {
        "amount": payment.amount,
        "fee": payment.fee,
        "checking_id": payment.checking_id,
        "payment_hash": payment.payment_hash,
        "bolt11": payment.bolt11,
    }
    await websocketUpdater(pegging.id, str(strippedPayment))  # No idea why it is here
    await update_position(pegging, payment.amount, "Ask")


async def update_position(pegging: Pegging, delta_amount: int, side: str) -> None:
    client = KolliderRestClient(
        pegging.base_url, pegging.api_key, pegging.api_secret, pegging.api_passphrase
    )

    symbol = f"BTC{pegging.currency}.PERP"
    t = client.get_ticker(symbol)

    if not t:
        logger.error(f"Couldn't obtain ticker {symbol} from Kollider")
        return

    price = float(t.best_ask if side == "Bid" else t.best_bid)  # TODO, same, types
    percent = float(pegging.percent) / 100.0  # TODO: same, type support

    fiat_amount = int(percent * price * delta_amount / (1_000 * 100_000_000))

    if fiat_amount == 0:
        logger.error(f"Order amount {fiat_amount}. Too few sats?")
        return

    t = client.get_tradeable_symbols()

    mult = 1
    # TODO: possible to hide into client state
    if t and symbol in t:
        mult = 10 ** int(t[symbol]["price_dp"])
    else:
        logger.error(f"Couldn't obtain tradeable symbols")
        return

    price = int(mult * price)

    order = Order(
        symbol=symbol,
        quantity=fiat_amount,
        leverage=100,
        side=side,
        price=price,
    )

    r = client.place_order(order)

    if r and "error" in r:
        logger.error(f"Couldn't place order for wallet {pegging.wallet}")
    else:
        logger.debug(
            f"{pegging.wallet} order placed for {fiat_amount} {symbol} @ {price}"
        )
