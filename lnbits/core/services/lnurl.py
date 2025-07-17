from lnurl import LnurlPayActionResponse
from lnurl import execute_pay_request as lnurlp

from lnbits.core.models import CreateLnurlPayment
from lnbits.settings import settings
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis


async def fetch_lnurl_pay_request(data: CreateLnurlPayment) -> LnurlPayActionResponse:
    """
    Pay an LNURL payment request.

    raises `LnurlResponseException` if pay request fails
    """

    if data.unit and data.unit != "sat":
        # shift to float with 2 decimal places
        amount = round(data.amount / 1000, 2)
        amount_msat = await fiat_amount_as_satoshis(amount, data.unit)
        amount_msat *= 1000
    else:
        amount_msat = data.amount

    return await lnurlp(
        data.res,
        msat=str(amount_msat),
        user_agent=settings.user_agent,
        timeout=5,
    )
