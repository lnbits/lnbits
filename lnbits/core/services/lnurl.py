from time import time

from lnurl import (
    LnAddress,
    Lnurl,
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlPayResponse,
    LnurlResponseException,
    LnurlSuccessResponse,
    LnurlWithdrawResponse,
    execute_pay_request,
    execute_withdraw,
    handle,
)
from loguru import logger

from lnbits.core.crud import update_wallet
from lnbits.core.models import CreateLnurlPayment, Wallet
from lnbits.core.models.lnurl import StoredPayLink
from lnbits.helpers import check_callback_url
from lnbits.settings import settings
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis


async def perform_withdraw(lnurl: str, payment_request: str) -> None:
    """
    Perform an LNURL withdraw to the given LNURL-withdraw link.
    :param lnurl: The LNURL-withdraw link. bech32 or lud17 format.
    :param payment_request: The BOLT11 payment request to pay.
    :raises LnurlResponseException: If the LNURL-withdraw process fails.
    """
    res = await handle(lnurl, user_agent=settings.user_agent, timeout=10)
    if isinstance(res, LnurlErrorResponse):
        raise LnurlResponseException(res.reason)
    if not isinstance(res, LnurlWithdrawResponse):
        raise LnurlResponseException("Invalid LNURL-withdraw response.")
    try:
        check_callback_url(res.callback)
    except ValueError as exc:
        raise LnurlResponseException(f"Invalid callback URL: {exc!s}") from exc
    res2 = await execute_withdraw(
        res, payment_request, user_agent=settings.user_agent, timeout=10
    )
    if isinstance(res2, LnurlErrorResponse):
        raise LnurlResponseException(res2.reason)
    if not isinstance(res2, LnurlSuccessResponse):
        raise LnurlResponseException("Invalid LNURL-withdraw success response.")


async def get_pr_from_lnurl(
    lnurl: str, amount_msat: int, comment: str | None = None
) -> str:
    res = await handle(lnurl, user_agent=settings.user_agent, timeout=10)
    if isinstance(res, LnurlErrorResponse):
        raise LnurlResponseException(res.reason)
    if not isinstance(res, LnurlPayResponse):
        raise LnurlResponseException(
            "Invalid LNURL response. Expected LnurlPayResponse."
        )
    res2 = await execute_pay_request(
        res,
        msat=amount_msat,
        comment=comment,
        user_agent=settings.user_agent,
        timeout=10,
    )
    if isinstance(res2, LnurlErrorResponse):
        raise LnurlResponseException(res2.reason)
    return res2.pr


async def fetch_lnurl_pay_request(
    data: CreateLnurlPayment, wallet: Wallet | None = None
) -> tuple[LnurlPayResponse, LnurlPayActionResponse]:
    """
    Pay an LNURL payment request.
    optional `wallet` is used to store the pay link in the wallet's stored links.

    raises `LnurlResponseException` if pay request fails
    """
    if not data.res and data.lnurl:
        res = await handle(data.lnurl, user_agent=settings.user_agent, timeout=5)
        if isinstance(res, LnurlErrorResponse):
            raise LnurlResponseException(res.reason)
        if not isinstance(res, LnurlPayResponse):
            raise LnurlResponseException(
                "Invalid LNURL response. Expected LnurlPayResponse."
            )
        data.res = res
    if not data.res:
        raise LnurlResponseException("No LNURL pay request provided.")

    if data.unit and data.unit != "sat":
        # shift to float with 2 decimal places
        amount = round(data.amount / 1000, 2)
        amount_msat = await fiat_amount_as_satoshis(amount, data.unit)
        amount_msat *= 1000
    else:
        amount_msat = data.amount

    res2 = await execute_pay_request(
        data.res,
        msat=amount_msat,
        comment=data.comment,
        user_agent=settings.user_agent,
        timeout=10,
    )

    if wallet:
        await store_paylink(data.res, res2, wallet, data.lnurl)

    return data.res, res2


async def store_paylink(
    res: LnurlPayResponse,
    res2: LnurlPayActionResponse,
    wallet: Wallet,
    lnurl: LnAddress | Lnurl | None = None,
) -> None:

    if res2.disposable is not False:
        return  # do not store disposable LNURL pay links

    logger.debug(f"storing lnurl pay link for wallet {wallet.id}. ")

    stored_paylink = None
    # If we have only a LnurlPayResponse, we can use its lnaddress
    # because the lnurl is not available.
    if not lnurl:
        for _data in res.metadata.list():
            if _data[0] == "text/identifier":
                stored_paylink = StoredPayLink(
                    lnurl=LnAddress(_data[1]), label=res.metadata.text
                )
        if not stored_paylink:
            logger.warning(
                "No lnaddress found in metadata for LNURL pay link. "
                "Skipping storage."
            )
            return  # skip if lnaddress not found in metadata
    else:
        if isinstance(lnurl, Lnurl):
            _lnurl = str(lnurl.lud17 or lnurl.bech32)
        else:
            _lnurl = str(lnurl)
        stored_paylink = StoredPayLink(lnurl=_lnurl, label=res.metadata.text)

    # update last_used if its already stored
    for pl in wallet.stored_paylinks.links:
        if pl.lnurl == stored_paylink.lnurl:
            pl.last_used = int(time())
            await update_wallet(wallet)
            logger.debug(
                "Updated last used time for LNURL "
                f"pay link {stored_paylink.lnurl} in wallet {wallet.id}."
            )
            return

    # if not already stored, append it
    if not any(stored_paylink.lnurl == pl.lnurl for pl in wallet.stored_paylinks.links):
        wallet.stored_paylinks.links.append(stored_paylink)
        await update_wallet(wallet)
        logger.debug(
            f"Stored LNURL pay link {stored_paylink.lnurl} for wallet {wallet.id}."
        )
