from typing import Any

from lnurl import execute_pay_request as lnurlp

from lnbits.core.models import CreateLnurlPayment, Payment
from lnbits.core.services import pay_invoice
from lnbits.settings import settings
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis


async def pay_lnurl(wallet_id: str, data: CreateLnurlPayment) -> Payment:
    """
    Pay an LNURL payment request.

    raises `LnurlResponseException` if pay request fails
    raises `PaymentError` if the payment fails.
    """

    if data.unit and data.unit != "sat":
        # shift to float with 2 decimal places
        amount = round(data.amount / 1000, 2)
        amount_msat = await fiat_amount_as_satoshis(amount, data.unit)
        amount_msat *= 1000
    else:
        amount_msat = data.amount

    res = await lnurlp(
        data.res,
        msat=str(amount_msat),
        user_agent=settings.user_agent,
        timeout=5,
    )

    description = data.res.metadata.text

    extra: dict[str, Any] = {}
    if res.success_action:
        extra["success_action"] = res.success_action.json()
    if data.comment:
        extra["comment"] = data.comment
    if data.unit and data.unit != "sat":
        extra["fiat_currency"] = data.unit
        extra["fiat_amount"] = data.amount / 1000

    payment = await pay_invoice(
        wallet_id=wallet_id,
        payment_request=str(res.pr),
        description=description,
        extra=extra,
    )

    return payment
