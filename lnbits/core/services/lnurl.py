from lnurl import (
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlPayResponse,
    LnurlResponseException,
    execute_pay_request,
    handle,
)

from lnbits.core.models import CreateLnurlPayment
from lnbits.settings import settings
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis


async def get_pr_from_lnurl(lnurl: str, amount_msat: int) -> str:
    res = await handle(lnurl, user_agent=settings.user_agent, timeout=10)
    if isinstance(res, LnurlErrorResponse):
        raise LnurlResponseException(res.reason)
    if not isinstance(res, LnurlPayResponse):

        raise LnurlResponseException(
            "Invalid LNURL response. Expected LnurlPayResponse."
        )
    res2 = await execute_pay_request(
        res,
        msat=str(amount_msat),
        user_agent=settings.user_agent,
        timeout=10,
    )
    if isinstance(res2, LnurlErrorResponse):
        raise LnurlResponseException(res2.reason)
    if not isinstance(res, LnurlPayActionResponse):
        raise LnurlResponseException(
            "Invalid LNURL pay response. Expected LnurlPayActionResponse."
        )
    return res2.pr


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

    return await execute_pay_request(
        data.res,
        msat=str(amount_msat),
        user_agent=settings.user_agent,
        timeout=10,
    )
