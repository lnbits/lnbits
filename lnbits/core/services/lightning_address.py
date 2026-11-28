import asyncio
import json
import re
from enum import Enum
from http import HTTPStatus

import httpx
from fastapi import Query, Request
from lnurl import (
    CallbackUrl,
    LightningInvoice,
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlPayMetadata,
    LnurlPayResponse,
    MilliSatoshi,
)
from loguru import logger
from pydantic import TypeAdapter, ValidationError
from starlette.types import ASGIApp

from lnbits.core.crud.wallets import (
    get_wallet,
    get_wallet_id_by_ln_address,
    update_wallet,
)
from lnbits.core.db import core_app_extra
from lnbits.core.models.payments import CreateInvoice
from lnbits.core.models.wallets import Wallet
from lnbits.core.services.payments import (
    create_invoice,
    create_wallet_invoice,
    pay_invoice,
)
from lnbits.db import Connection
from lnbits.exceptions import PaymentError
from lnbits.settings import RedirectPath, settings

MAX_SENDABLE_MSAT = 2_100_000_000_000_000_000
COMMENT_ALLOWED = 799
LIGHTNING_ADDRESS_REGEX = re.compile(r"^[a-z0-9_.-]{1,210}$")
EXTENSION_LNURL_PROBE_TIMEOUT_SECONDS = 2.0


class ExtensionLnAddressStatus(str, Enum):
    AVAILABLE = "available"
    TAKEN = "taken"
    UNAVAILABLE = "unavailable"


async def set_wallet_lightning_address(
    *,
    wallet: Wallet,
    local_part: str,
    allow_blacklisted: bool = False,
    charge: bool = False,
    conn: Connection | None = None,
) -> Wallet:
    if not settings.ln_address_creation_allowed:
        raise ValueError("Wallet Lightning Addresses are disabled.")
    if not wallet.is_lightning_wallet or wallet.deleted:
        raise ValueError("Lightning Address can only be set for active wallets.")

    local_part = await _validate_local_part(
        local_part, wallet.id, allow_blacklisted, conn=conn
    )
    if wallet.lightning_address == local_part:
        return wallet

    if charge:
        await _charge_for_lightning_address(wallet)

    wallet.lightning_address = local_part
    return await update_wallet(wallet, conn=conn)


async def wallet_lightning_address_response(
    username: str, request: Request
) -> LnurlPayResponse | LnurlErrorResponse:
    local_part, tag = split_tagged_local_part(username)
    wallet_id = await get_wallet_id_by_ln_address(local_part)
    if not wallet_id:
        return LnurlErrorResponse(reason="Lightning address not found.")

    tagged_local_part = local_part
    if tag:
        tagged_local_part = f"{tagged_local_part}+{tag}"

    callback = request.url_for(
        "lnurl.api_wallet_lightning_address_callback",
        username=tagged_local_part,
    )
    identifier = _lightning_address_for_request(request, tagged_local_part)
    return LnurlPayResponse(
        callback=TypeAdapter(CallbackUrl).validate_python(str(callback)),
        minSendable=MilliSatoshi(1000),
        maxSendable=MilliSatoshi(MAX_SENDABLE_MSAT),
        metadata=LnurlPayMetadata(json.dumps(_metadata(identifier, tag))),
        commentAllowed=COMMENT_ALLOWED,
    )


async def wallet_lightning_address_callback(
    username: str,
    request: Request,
    amount: int = Query(...),
) -> LnurlErrorResponse | LnurlPayActionResponse:
    local_part, tag = split_tagged_local_part(username)
    wallet_id = await get_wallet_id_by_ln_address(local_part)
    if not wallet_id:
        return LnurlErrorResponse(reason="Lightning address not found.")

    if amount < 1000:
        return LnurlErrorResponse(reason="Amount is smaller than minimum 1000.")
    if amount > MAX_SENDABLE_MSAT:
        return LnurlErrorResponse(
            reason=f"Amount is greater than maximum {MAX_SENDABLE_MSAT}."
        )

    comment = request.query_params.get("comment")
    if len(comment or "") > COMMENT_ALLOWED:
        return LnurlErrorResponse(
            reason=(
                f"Got a comment with {len(comment or '')} characters, "
                f"but can only accept {COMMENT_ALLOWED}"
            )
        )

    tagged_local_part = local_part
    if tag:
        tagged_local_part = f"{tagged_local_part}+{tag}"
    identifier = _lightning_address_for_request(request, tagged_local_part)
    extra = {
        "tag": "wallet_lightning_address",
        "lnaddress": identifier,
    }
    if tag:
        extra["lnaddress_tag"] = tag
    if comment:
        extra["comment"] = comment

    metadata = LnurlPayMetadata(json.dumps(_metadata(identifier, tag)))
    payment = await create_invoice(
        wallet_id=wallet_id,
        amount=int(amount / 1000),
        memo=f"Payment to {identifier}",
        unhashed_description=metadata.encode(),
        extra=extra,
    )
    invoice = TypeAdapter(LightningInvoice).validate_python(
        LightningInvoice(payment.bolt11)
    )
    return LnurlPayActionResponse(pr=invoice, disposable=False)


def split_tagged_local_part(local_part: str) -> tuple[str, str | None]:
    username, separator, tag = local_part.partition("+")
    if not separator or not tag:
        return username.lower(), None
    return username.lower(), tag


def is_safe_lnurlp_username(username: str) -> bool:
    base_part, _, tag = username.partition("+")
    lower_base = base_part.lower()
    if lower_base in {".", ".."} or not LIGHTNING_ADDRESS_REGEX.fullmatch(lower_base):
        return False
    return not any(ord(ch) <= 32 or ord(ch) == 127 or ch in "/?#\\%" for ch in tag)


async def check_extension_lightning_address(
    local_part: str,
) -> ExtensionLnAddressStatus:
    well_known_path = f"/.well-known/lnurlp/{local_part.strip().lower()}"
    redirect = settings.find_extension_redirect(well_known_path, [])
    if not redirect:
        return ExtensionLnAddressStatus.AVAILABLE

    status, _ = await fetch_extension_lnurlp_response(redirect, well_known_path)
    return status


async def fetch_extension_lnurlp_response(
    redirect: RedirectPath,
    path: str,
    *,
    app: ASGIApp | None = None,
    base_url: str = "https://127.0.0.1",
) -> tuple[ExtensionLnAddressStatus, LnurlPayResponse | LnurlErrorResponse | None]:
    resolved_app = app or core_app_extra.local_lnurl_app
    if resolved_app is None:
        return ExtensionLnAddressStatus.AVAILABLE, None

    target_path = redirect.new_path_from(path)
    try:
        response = await asyncio.wait_for(
            _get_local_extension_response(resolved_app, base_url, target_path),
            timeout=EXTENSION_LNURL_PROBE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning(
            f"Failed to fetch LNURL response Extension redirect {target_path}: {exc}"
        )
        return ExtensionLnAddressStatus.UNAVAILABLE, None

    return _parse_extension_lnurlp_response(response, target_path)


def _lightning_address_for_request(request: Request, local_part: str) -> str:
    return f"{local_part}@{request.url.netloc}"


async def _validate_local_part(
    local_part: str,
    wallet_id: str,
    allow_blacklisted: bool = False,
    conn: Connection | None = None,
) -> str:
    local_part = local_part.strip().lower()
    if not local_part:
        raise ValueError("Lightning Address is required.")
    if "+" in local_part:
        raise ValueError("Lightning Address cannot include tags.")
    if "@" in local_part:
        raise ValueError("Enter only the Lightning Address name before @.")
    if local_part in {".", ".."} or not LIGHTNING_ADDRESS_REGEX.fullmatch(local_part):
        raise ValueError(
            "Lightning Address can only contain lowercase letters, numbers, "
            "dash, underscore, and dot."
        )
    if not allow_blacklisted and _uses_blacklisted_word(local_part):
        raise ValueError("Lightning Address contains a reserved word.")
    existing_wallet_id = await get_wallet_id_by_ln_address(local_part, conn=conn)
    if existing_wallet_id == wallet_id:
        return local_part
    if existing_wallet_id:
        raise ValueError("Lightning Address is already taken.")

    await _ensure_extension_local_part_available(local_part)
    return local_part


async def _ensure_extension_local_part_available(local_part: str) -> None:
    ext_status = await check_extension_lightning_address(local_part)
    if ext_status == ExtensionLnAddressStatus.TAKEN:
        raise ValueError("Lightning Address is already taken.")
    if ext_status == ExtensionLnAddressStatus.UNAVAILABLE:
        raise ValueError("Could not verify Lightning Address availability.")


async def _get_local_extension_response(
    app: ASGIApp, base_url: str, target_path: str
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url=base_url,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        return await client.get(
            target_path,
            headers={"accept": "application/json"},
        )


def _parse_extension_lnurlp_response(
    response: httpx.Response, target_path: str
) -> tuple[ExtensionLnAddressStatus, LnurlPayResponse | LnurlErrorResponse | None]:
    if response.status_code == HTTPStatus.NOT_FOUND:
        return ExtensionLnAddressStatus.AVAILABLE, None
    if response.status_code != HTTPStatus.OK:
        logger.warning(
            "Unexpected status code from LNURL Extension redirect "
            f"{target_path}: {response.status_code}"
        )
        return ExtensionLnAddressStatus.UNAVAILABLE, None

    try:
        response_data = response.json()
    except ValueError as exc:
        logger.warning(
            f"Invalid JSON from LNURL Extension redirect {target_path}: {exc}"
        )
        return ExtensionLnAddressStatus.UNAVAILABLE, None

    try:
        return (
            ExtensionLnAddressStatus.TAKEN,
            LnurlPayResponse.model_validate(response_data),
        )
    except ValidationError:
        pass

    try:
        return (
            ExtensionLnAddressStatus.AVAILABLE,
            LnurlErrorResponse.model_validate(response_data),
        )
    except ValidationError as exc:
        logger.warning(
            f"Invalid LNURL payload from Extension redirect {target_path}: {exc}"
        )
        return ExtensionLnAddressStatus.UNAVAILABLE, None


def _metadata(identifier: str, tag: str | None = None) -> list[list[str]]:
    metadata = [
        ["text/plain", f"Payment to {identifier}"],
        ["text/identifier", identifier],
    ]
    if tag:
        metadata.append(["text/tag", tag])
    return metadata


async def _charge_for_lightning_address(wallet: Wallet) -> None:
    price_sats = settings.lnbits_wallet_lightning_address_price_sats
    if not settings.lnbits_charge_wallet_lightning_addresses or price_sats <= 0:
        return
    if not settings.lnbits_service_fee_wallet:
        raise ValueError("Lightning Address fee wallet is not configured.")
    if settings.lnbits_service_fee_wallet == wallet.source_wallet_id:
        raise ValueError("Lightning Address fee wallet cannot be the same wallet.")

    fee_wallet = await get_wallet(settings.lnbits_service_fee_wallet)
    if not fee_wallet:
        raise ValueError("Lightning Address fee wallet is not configured.")

    invoice = await create_wallet_invoice(
        settings.lnbits_service_fee_wallet,
        CreateInvoice(
            out=False,
            amount=price_sats,
            memo="Lightning Address fee",
            internal=True,
            extra={
                "tag": "wallet_lightning_address_fee",
                "wallet": wallet.source_wallet_id,
            },
        ),
    )
    try:
        await pay_invoice(
            wallet_id=wallet.source_wallet_id,
            payment_request=invoice.bolt11,
            description="Lightning Address fee",
            tag="wallet_lightning_address_fee",
            extra={
                "tag": "wallet_lightning_address_fee",
                "fee_wallet": settings.lnbits_service_fee_wallet,
            },
        )
    except PaymentError as exc:
        raise ValueError(exc.message) from exc


def _blacklist_words() -> set[str]:
    return {
        word.strip().lower()
        for word in settings.lnbits_wallet_lightning_address_blacklist
        if word.strip()
    }


def _uses_blacklisted_word(local_part: str) -> bool:
    words = _blacklist_words()
    if not words:
        return False
    segments = [segment for segment in re.split(r"[._-]+", local_part) if segment]
    return local_part in words or any(segment in words for segment in segments)
