from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
from time import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bolt11 import Bolt11Exception, MilliSatoshi
from bolt11 import decode as bolt11_decode
from lnurl import (
    InvalidLnurl,
    LnAddress,
    Lnurl,
    LnurlAuthResponse,
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlPayResponse,
    LnurlResponse,
    LnurlResponseException,
    LnurlSuccessResponse,
    LnurlWithdrawResponse,
    lnurlauth_derive_linking_key,
    lnurlauth_derive_linking_key_sign_message,
    lnurlauth_signature,
)
from lnurl.models import LnurlResponseModel
from lnurl.types import CallbackUrl
from loguru import logger
from pydantic import ValidationError, parse_obj_as

from lnbits.core.crud import update_wallet
from lnbits.core.models import CreateLnurlPayment, Wallet
from lnbits.core.models.lnurl import StoredPayLink
from lnbits.helpers import check_callback_url
from lnbits.settings import settings
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis

LNURL_MAX_REDIRECTS = 3
LNURL_MAX_RESPONSE_BYTES = 262_144
LNURL_TOR_SOCKS = "socks5h://127.0.0.1:9050"


async def handle(
    lnurl: str,
    response_class: type[LnurlResponseModel] | None = None,
    user_agent: str | None = None,
    timeout: int | None = None,
    tor_socks: str | None = None,
) -> LnurlResponseModel:
    try:
        if "@" in lnurl:
            lnaddress = LnAddress(lnurl)
            return await _get(
                str(lnaddress.url),
                response_class=response_class,
                user_agent=user_agent,
                timeout=timeout,
                tor_socks=tor_socks,
            )
        parsed_lnurl = Lnurl(lnurl)
    except (ValidationError, ValueError) as exc:
        raise InvalidLnurl from exc

    if parsed_lnurl.is_login:
        callback = parse_obj_as(CallbackUrl, parsed_lnurl.url)
        return LnurlAuthResponse(
            callback=callback, k1=parsed_lnurl.url.query_params["k1"]
        )

    return await _get(
        str(parsed_lnurl.url),
        response_class=response_class,
        user_agent=user_agent,
        timeout=timeout,
        tor_socks=tor_socks,
    )


async def execute_login(
    res: LnurlAuthResponse,
    seed: str | None = None,
    signed_message: str | None = None,
    user_agent: str | None = None,
    timeout: int | None = None,
    tor_socks: str | None = None,
) -> LnurlResponseModel:
    if not res.callback:
        raise LnurlResponseException("LNURLauth callback does not exist")
    host = res.callback.host
    if not host:
        raise LnurlResponseException("Invalid host in LNURLauth callback")
    if seed:
        linking_key, _ = lnurlauth_derive_linking_key(seed=seed, domain=host)
    elif signed_message:
        linking_key, _ = lnurlauth_derive_linking_key_sign_message(
            domain=host, sig=signed_message.encode()
        )
    else:
        raise LnurlResponseException("Seed or signed_message is required for LNURLauth")

    key, sig = lnurlauth_signature(res.k1, linking_key=linking_key)
    return await _get(
        str(res.callback),
        user_agent=user_agent,
        timeout=timeout,
        tor_socks=tor_socks,
        params={"key": key, "sig": sig},
    )


async def execute_withdraw(
    res: LnurlWithdrawResponse,
    pr: str,
    user_agent: str | None = None,
    timeout: int | None = None,
    tor_socks: str | None = None,
) -> LnurlSuccessResponse:
    try:
        invoice = bolt11_decode(pr)
    except Bolt11Exception as exc:
        raise LnurlResponseException("Invalid withdrawal invoice.") from exc

    amount = invoice.amount_msat or res.minWithdrawable
    if not res.minWithdrawable <= MilliSatoshi(amount) <= res.maxWithdrawable:
        raise LnurlResponseException(
            f"Amount {amount} not in range "
            f"{res.minWithdrawable} - {res.maxWithdrawable}"
        )

    withdraw_res = await _get(
        str(res.callback),
        user_agent=user_agent,
        timeout=timeout,
        tor_socks=tor_socks,
        params={"k1": res.k1, "pr": pr},
    )
    if isinstance(withdraw_res, LnurlErrorResponse):
        raise LnurlResponseException(withdraw_res.reason)
    if not isinstance(withdraw_res, LnurlSuccessResponse):
        raise LnurlResponseException("Invalid LNURL-withdraw response.")
    return withdraw_res


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
    res2 = await _execute_pay_request(
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

    res2 = await _execute_pay_request(
        data.res,
        msat=amount_msat,
        comment=data.comment,
        user_agent=settings.user_agent,
        timeout=10,
    )

    if wallet:
        await _store_paylink(data.res, res2, wallet, data.lnurl)

    return data.res, res2


async def _get(
    url: str,
    *,
    response_class: type[LnurlResponseModel] | None = None,
    user_agent: str | None = None,
    timeout: int | None = None,
    tor_socks: str | None = None,
    params: dict[str, str | int] | None = None,
) -> LnurlResponseModel:
    data = await _request_lnurl_json(
        url,
        user_agent=user_agent,
        timeout=timeout,
        tor_socks=tor_socks,
        params=params,
    )
    try:
        if response_class:
            if not issubclass(response_class, LnurlResponseModel):
                raise TypeError
            return response_class(**data)
        return LnurlResponse.from_dict(data)
    except (
        AttributeError,
        LnurlResponseException,
        TypeError,
        ValidationError,
        ValueError,
    ) as exc:
        raise LnurlResponseException("Invalid LNURL response.") from exc


async def _execute_pay_request(
    res: LnurlPayResponse,
    msat: int,
    comment: str | None = None,
    user_agent: str | None = None,
    timeout: int | None = None,
    tor_socks: str | None = None,
) -> LnurlPayActionResponse:
    if not res.minSendable <= MilliSatoshi(msat) <= res.maxSendable:
        raise LnurlResponseException(
            f"Amount {msat} not in range {res.minSendable} - {res.maxSendable}"
        )

    params: dict[str, str | int] = {"amount": msat}
    if res.commentAllowed and comment:
        if len(comment) > res.commentAllowed:
            raise LnurlResponseException(
                f"Comment length {len(comment)} exceeds allowed length "
                f"{res.commentAllowed}"
            )
        params["comment"] = comment

    pay_res = await _get(
        str(res.callback),
        user_agent=user_agent,
        timeout=timeout,
        tor_socks=tor_socks,
        params=params,
    )
    if isinstance(pay_res, LnurlErrorResponse):
        raise LnurlResponseException(pay_res.reason)
    if not isinstance(pay_res, LnurlPayActionResponse):
        raise LnurlResponseException("Invalid LNURL-pay response.")

    try:
        invoice = bolt11_decode(pay_res.pr)
    except Bolt11Exception as exc:
        raise LnurlResponseException("Invalid invoice in LNURL response.") from exc
    if invoice.amount_msat != int(msat):
        raise LnurlResponseException(
            "LNURL service returned an invalid invoice amount."
        )
    return pay_res


async def _store_paylink(
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


async def _request_lnurl_json(
    url: str,
    *,
    user_agent: str | None,
    timeout: int | None,
    tor_socks: str | None,
    params: dict[str, str | int] | None,
) -> dict[str, Any]:
    try:
        current_url = httpx.URL(url)
        if params:
            current_url = current_url.copy_merge_params(params)
    except httpx.InvalidURL as exc:
        raise LnurlResponseException("Invalid LNURL request URL.") from exc

    for redirect_count in range(LNURL_MAX_REDIRECTS + 1):
        addresses, proxy = await _validate_lnurl_request_url(
            current_url, tor_socks=tor_socks
        )
        status_code, headers, body = await _send_lnurl_request(
            current_url,
            addresses=addresses,
            proxy=proxy,
            user_agent=user_agent,
            timeout=timeout,
        )

        if status_code in {301, 302, 303, 307, 308}:
            location = headers.get("location")
            if not location or redirect_count >= LNURL_MAX_REDIRECTS:
                raise LnurlResponseException("LNURL redirect was not allowed.")
            redirect_url = urljoin(str(current_url), location)
            try:
                current_url = httpx.URL(redirect_url)
            except httpx.InvalidURL as exc:
                raise LnurlResponseException("LNURL redirect was not allowed.") from exc
            _check_lnurl_redirect_rule(current_url)
            continue

        if status_code >= 400:
            raise LnurlResponseException("LNURL request failed.")
        try:
            data = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LnurlResponseException("Invalid LNURL response.") from exc
        if not isinstance(data, dict):
            raise LnurlResponseException("Invalid LNURL response.")
        return data

    raise LnurlResponseException("LNURL redirect was not allowed.")


async def _validate_lnurl_request_url(
    url: httpx.URL, *, tor_socks: str | None
) -> tuple[list[ipaddress.IPv4Address | ipaddress.IPv6Address], str | None]:
    parsed = urlparse(str(url))
    if parsed.username or parsed.password:
        raise LnurlResponseException("LNURL request URL must not include credentials.")
    if not parsed.hostname:
        raise LnurlResponseException("LNURL request target hostname is missing.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise LnurlResponseException("LNURL request target port is invalid.") from exc

    host = parsed.hostname.lower().rstrip(".")
    is_onion = host.endswith(".onion")
    if parsed.scheme not in {"http", "https"}:
        raise LnurlResponseException("LNURL request URL scheme must be HTTP or HTTPS.")
    if is_onion:
        return [], tor_socks or LNURL_TOR_SOCKS

    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = await _resolve_lnurl_host(host, port)

    if not addresses:
        raise LnurlResponseException("LNURL request target could not be resolved.")
    if parsed.scheme != "https" and (
        not settings.lnbits_lnurl_allow_private_ips
        or any(address.is_global for address in addresses)
    ):
        raise LnurlResponseException("LNURL request target is not allowed over HTTP.")
    if not settings.lnbits_lnurl_allow_private_ips and any(
        not address.is_global for address in addresses
    ):
        raise LnurlResponseException(
            "LNURL request target resolves to a private or non-global IP address."
        )
    return addresses, None


async def _resolve_lnurl_host(
    host: str, port: int | None
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    def resolve() -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise LnurlResponseException(
                "LNURL request target could not be resolved."
            ) from exc
        return list({ipaddress.ip_address(info[4][0]) for info in infos})

    return await asyncio.to_thread(resolve)


async def _send_lnurl_request(
    url: httpx.URL,
    *,
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    proxy: str | None,
    user_agent: str | None,
    timeout: int | None,
) -> tuple[int, dict[str, str], bytes]:
    request_urls = [url] if proxy else [url.copy_with(host=str(ip)) for ip in addresses]
    parsed = urlparse(str(url))
    headers = {
        "Host": parsed.netloc,
        "User-Agent": user_agent or "lnbits/lnurl",
    }
    extensions = {"sni_hostname": parsed.hostname}
    last_error: httpx.RequestError | None = None

    for request_url in request_urls:
        try:
            async with httpx.AsyncClient(
                follow_redirects=False,
                proxy=proxy,
                timeout=timeout or 5,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "GET",
                    request_url,
                    headers=headers,
                    extensions=extensions,
                ) as response:
                    body = b""
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        body = await _read_limited_lnurl_response(response)
                    return response.status_code, dict(response.headers), body
        except httpx.RequestError as exc:
            last_error = exc

    raise LnurlResponseException("LNURL request failed.") from last_error


async def _read_limited_lnurl_response(response: httpx.Response) -> bytes:
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > LNURL_MAX_RESPONSE_BYTES:
            raise LnurlResponseException("LNURL response is too large.")
    return bytes(body)


def _check_lnurl_redirect_rule(url: httpx.URL) -> None:
    parsed = urlparse(str(url))
    origin = f"{parsed.scheme}://{parsed.netloc}"
    for rule in settings.lnbits_lnurl_redirect_url_rules:
        try:
            if re.fullmatch(rule, origin):
                return
        except re.error:
            logger.warning(f"Invalid LNURL redirect URL rule: '{rule}'.")
    raise LnurlResponseException("LNURL redirect was not allowed.")
