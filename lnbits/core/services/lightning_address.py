import json
import re

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
from pydantic import parse_obj_as

from lnbits.core.crud.wallets import (
    get_wallet,
    get_wallet_id_by_ln_address,
    legacy_lnurlp_address_exists,
)
from lnbits.core.db import db
from lnbits.core.models.wallets import Wallet
from lnbits.db import Connection
from lnbits.exceptions import PaymentError
from lnbits.settings import settings

MAX_SENDABLE_MSAT = 2_100_000_000_000_000_000
COMMENT_ALLOWED = 799
LIGHTNING_ADDRESS_REGEX = re.compile(r"^[a-z0-9_.-]{1,210}$")


def normalize_lightning_address_local_part(local_part: str) -> str:
    return local_part.strip().lower()


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


async def validate_lightning_address_local_part(
    *,
    local_part: str,
    wallet: Wallet,
    allow_blacklisted: bool = False,
    conn: Connection | None = None,
) -> str:
    local_part = normalize_lightning_address_local_part(local_part)
    if not local_part:
        raise ValueError("Lightning Address is required.")
    if "+" in local_part:
        raise ValueError("Lightning Address cannot include tags.")
    if "@" in local_part:
        raise ValueError("Enter only the Lightning Address name before @.")
    if not LIGHTNING_ADDRESS_REGEX.match(local_part):
        raise ValueError(
            "Lightning Address can only contain lowercase letters, numbers, "
            "dash, underscore, and dot."
        )
    if not allow_blacklisted and _uses_blacklisted_word(local_part):
        raise ValueError("Lightning Address contains a reserved word.")
    existing_wallet_id = await get_wallet_id_by_ln_address(local_part)
    if existing_wallet_id and existing_wallet_id != wallet.id:
        raise ValueError("Lightning Address is already taken.")
    if await legacy_lnurlp_address_exists(local_part):
        raise ValueError("Lightning Address is already taken.")
    return local_part


async def _charge_for_lightning_address(wallet: Wallet) -> None:
    price_sats = settings.lnbits_wallet_lightning_address_price_sats
    if not settings.lnbits_charge_wallet_lightning_addresses or price_sats <= 0:
        return
    if not settings.lnbits_service_fee_wallet:
        raise ValueError("Lightning Address fee wallet is not configured.")
    if settings.lnbits_service_fee_wallet == wallet.source_wallet_id:
        raise ValueError("Lightning Address fee wallet cannot be the same wallet.")

    from lnbits.core.crud.wallets import get_wallet
    from lnbits.core.models.payments import CreateInvoice
    from lnbits.core.services.payments import create_wallet_invoice, pay_invoice

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


async def set_wallet_lightning_address(
    *,
    wallet: Wallet,
    local_part: str,
    allow_blacklisted: bool = False,
    charge: bool = False,
    conn: Connection | None = None,
) -> Wallet:
    # todo: recheck
    if not settings.ln_address_creation_allowed:
        raise ValueError("Wallet Lightning Addresses are disabled.")
    if not wallet.is_lightning_wallet or wallet.deleted:
        raise ValueError("Lightning Address can only be set for active wallets.")

    local_part = await validate_lightning_address_local_part(
        local_part=local_part,
        wallet=wallet,
        allow_blacklisted=allow_blacklisted,
        conn=conn,
    )
    if wallet.lightning_address == local_part:
        return wallet

    if charge:
        await _charge_for_lightning_address(wallet)

    wallet.lightning_address = local_part
    await (conn or db).update("wallets", wallet)

    return await get_wallet(wallet.id, conn=conn) or wallet


def lightning_address_for_request(request: Request, local_part: str) -> str:
    return f"{local_part}@{request.url.netloc}"


def _split_tagged_local_part(local_part: str) -> tuple[str, str | None]:
    username, separator, tag = local_part.partition("+")
    if not separator or not tag:
        return username.lower(), None
    return username.lower(), tag


def _metadata(identifier: str, tag: str | None = None) -> list[list[str]]:
    metadata = [
        ["text/plain", f"Payment to {identifier}"],
        ["text/identifier", identifier],
    ]
    if tag:
        metadata.append(["text/tag", tag])
    return metadata


async def wallet_lightning_address_response(
    username: str, request: Request
) -> LnurlPayResponse | LnurlErrorResponse:
    local_part, tag = _split_tagged_local_part(username)
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
    identifier = lightning_address_for_request(request, tagged_local_part)
    return LnurlPayResponse(
        callback=parse_obj_as(CallbackUrl, str(callback)),
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
    local_part, tag = _split_tagged_local_part(username)
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
    identifier = lightning_address_for_request(request, tagged_local_part)
    extra = {
        "tag": "wallet_lightning_address",
        "lnaddress": identifier,
    }
    if tag:
        extra["lnaddress_tag"] = tag
    if comment:
        extra["comment"] = comment

    from lnbits.core.services.payments import create_invoice

    metadata = LnurlPayMetadata(json.dumps(_metadata(identifier, tag)))
    payment = await create_invoice(
        wallet_id=wallet_id,
        amount=int(amount / 1000),
        memo=f"Payment to {identifier}",
        unhashed_description=metadata.encode(),
        extra=extra,
    )
    invoice = parse_obj_as(LightningInvoice, LightningInvoice(payment.bolt11))
    return LnurlPayActionResponse(pr=invoice, disposable=False)
