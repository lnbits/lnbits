import asyncio

from pydantic import BaseModel
from starlette.exceptions import HTTPException

from lnbits.core.models import Payment
from lnbits.core.services import pay_invoice
from lnbits.extensions.strike.models import StrikeConfiguration, StrikeForward
from lnbits.tasks import register_invoice_listener

from .crud import create_forward, get_configuration_by_wallet, update_forward
from .strike_api import StrikeApiClient


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    config = await get_configuration_by_wallet(payment.wallet_id)
    if not config:
        # there is not configured forwarding for this wallet, ignore
        return

    print(f"Strike - forwarding payment to {config.handle}")

    forward = StrikeForward(
        **{
            "lnbits_wallet": config.lnbits_wallet,
            "handle": config.handle,
            "message": payment.memo,
            "sats_original": payment.sat,
            "msats_fee": payment.fee,
            "amount": float(0),
            "currency": config.currency,
            "status": "processing",
            "id": "none",
            "timestamp": 0,
        }
    )
    forward = await create_forward(forward)

    try:
        success = await forward_payment(config, forward, payment)
    except (HTTPException, Exception) as e:
        error_message = e.detail if e.detail else str(e)
        forward.status = "fail"
        forward.status_info = f"Error: {error_message}"
        await update_forward(forward)
        print(f"Strike - forwarding to {config.handle} failed, error: {error_message}")
        return

    if success:
        forward.status = "success"
        await update_forward(forward)


async def forward_payment(
    config: StrikeConfiguration, forward: StrikeForward, payment: Payment
) -> bool:
    client = StrikeApiClient(config.api_key)
    tickers = await client.get_tickers()
    target_handle = config.handle
    target_currency = config.currency
    rates = filter(
        lambda item: item.sourceCurrency == "BTC"
        and item.targetCurrency == target_currency,
        tickers,
    )

    if rates is None:
        # save error state
        forward.status = "fail"
        forward.status_info = f"No rate for {target_currency}/BTC"
        await update_forward(forward)
        return False

    rate = list(rates)[0].amount
    print(f"RATE {target_currency}/BTC is {rate}")

    safe_spreads = [0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 1, 1.5, 2, 3, 5]

    for spread in safe_spreads:
        forward.spread = spread
        quote = await create_quote(
            client, payment, target_handle, target_currency, rate, spread
        )

        # check that source amount is not larger than original amount
        converted_sats = quote.sourceAmount.amount * 100000000
        forward.sats_forwarded = converted_sats
        forward.amount = quote.targetAmount.amount
        forward.currency = quote.targetAmount.currency
        if converted_sats < payment.sat:
            # converted sats are lower, we are safe to forward this payment
            print(
                f"Converted sats {converted_sats} are lower than original sats: {payment.sat} (fee: {forward.msats_fee})"
            )
            break
        print(
            f"Converted sats {converted_sats} are higher than original sats: {payment.sat}, we need to re-generate quote"
        )

    print(f"Strike - paying invoice {quote.lnInvoice}")

    await pay_invoice(
        wallet_id=payment.wallet_id,
        payment_request=quote.lnInvoice,
        max_sat=payment.sat,
        extra={"tag": "strike"},
        description=f"Forwarded to '{target_handle}': {quote.description}",
    )
    print(f"Strike - invoice paid")
    return True


async def create_quote(
    client: StrikeApiClient,
    payment: Payment,
    handle: str,
    currency: str,
    rate: float,
    safe_spread: float,
):
    fiat_amount = (payment.sat / 100000000) * rate
    fiat_amount = fiat_amount - (fiat_amount * (safe_spread / 100))
    print(f"Computed FIAT amount is {fiat_amount} (spread: {safe_spread}%)")

    invoice_id = await client.issue_invoice(
        handle, fiat_amount, currency, payment.memo or "From LNbits"
    )
    quote = await client.create_quote(invoice_id)
    return quote
