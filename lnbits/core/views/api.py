import hashlib
import json
from http import HTTPStatus
from io import BytesIO
from typing import Dict, List
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse

import httpx
import pyqrcode
from fastapi import (
    APIRouter,
    Depends,
)
from fastapi.exceptions import HTTPException
from starlette.responses import StreamingResponse

from lnbits.core.models import (
    BaseWallet,
    ConversionData,
    CreateLnurlAuth,
    CreateWallet,
    User,
    Wallet,
)
from lnbits.decorators import (
    WalletTypeInfo,
    check_user_exists,
    get_key_type,
    require_admin_key,
)
from lnbits.lnurl import decode as lnurl_decode
from lnbits.settings import settings
from lnbits.utils.exchange_rates import (
    allowed_currencies,
    fiat_amount_as_satoshis,
    satoshis_amount_as_fiat,
)

from ..crud import (
    create_account,
    create_wallet,
)
from ..services import perform_lnurlauth

# backwards compatibility for extension
# TODO: remove api_payment and pay_invoice imports from extensions
from .payment_api import api_payment, pay_invoice  # noqa: F401

api_router = APIRouter(tags=["Core"])


@api_router.get("/api/v1/health", status_code=HTTPStatus.OK)
async def health():
    return


@api_router.get(
    "/api/v1/wallets",
    name="Wallets",
    description="Get basic info for all of user's wallets.",
)
async def api_wallets(user: User = Depends(check_user_exists)) -> List[BaseWallet]:
    return [BaseWallet(**w.dict()) for w in user.wallets]


@api_router.post("/api/v1/account", response_model=Wallet)
async def api_create_account(data: CreateWallet) -> Wallet:
    if not settings.new_accounts_allowed:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Account creation is disabled.",
        )
    account = await create_account()
    return await create_wallet(user_id=account.id, wallet_name=data.name)


@api_router.get("/api/v1/lnurlscan/{code}")
async def api_lnurlscan(code: str, wallet: WalletTypeInfo = Depends(get_key_type)):
    try:
        url = str(lnurl_decode(code))
        domain = urlparse(url).netloc
    except Exception:
        # parse internet identifier (user@domain.com)
        name_domain = code.split("@")
        if len(name_domain) == 2 and len(name_domain[1].split(".")) >= 2:
            name, domain = name_domain
            url = (
                ("http://" if domain.endswith(".onion") else "https://")
                + domain
                + "/.well-known/lnurlp/"
                + name
            )
            # will proceed with these values
        else:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="invalid lnurl"
            )

    # params is what will be returned to the client
    params: Dict = {"domain": domain}

    if "tag=login" in url:
        params.update(kind="auth")
        params.update(callback=url)  # with k1 already in it

        lnurlauth_key = wallet.wallet.lnurlauth_key(domain)
        assert lnurlauth_key.verifying_key
        params.update(pubkey=lnurlauth_key.verifying_key.to_string("compressed").hex())
    else:
        headers = {"User-Agent": settings.user_agent}
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            r = await client.get(url, timeout=5)
            r.raise_for_status()
            if r.is_error:
                raise HTTPException(
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                    detail={"domain": domain, "message": "failed to get parameters"},
                )

        try:
            data = json.loads(r.text)
        except json.decoder.JSONDecodeError:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail={
                    "domain": domain,
                    "message": f"got invalid response '{r.text[:200]}'",
                },
            )

        try:
            tag: str = data.get("tag")
            params.update(**data)
            if tag == "channelRequest":
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail={
                        "domain": domain,
                        "kind": "channel",
                        "message": "unsupported",
                    },
                )
            elif tag == "withdrawRequest":
                params.update(kind="withdraw")
                params.update(fixed=data["minWithdrawable"] == data["maxWithdrawable"])

                # callback with k1 already in it
                parsed_callback: ParseResult = urlparse(data["callback"])
                qs: Dict = parse_qs(parsed_callback.query)
                qs["k1"] = data["k1"]

                # balanceCheck/balanceNotify
                if "balanceCheck" in data:
                    params.update(balanceCheck=data["balanceCheck"])

                # format callback url and send to client
                parsed_callback = parsed_callback._replace(
                    query=urlencode(qs, doseq=True)
                )
                params.update(callback=urlunparse(parsed_callback))
            elif tag == "payRequest":
                params.update(kind="pay")
                params.update(fixed=data["minSendable"] == data["maxSendable"])

                params.update(
                    description_hash=hashlib.sha256(
                        data["metadata"].encode()
                    ).hexdigest()
                )
                metadata = json.loads(data["metadata"])
                for [k, v] in metadata:
                    if k == "text/plain":
                        params.update(description=v)
                    if k in ("image/jpeg;base64", "image/png;base64"):
                        data_uri = f"data:{k},{v}"
                        params.update(image=data_uri)
                    if k in ("text/email", "text/identifier"):
                        params.update(targetUser=v)
                params.update(commentAllowed=data.get("commentAllowed", 0))

        except KeyError as exc:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail={
                    "domain": domain,
                    "message": f"lnurl JSON response invalid: {exc}",
                },
            )

    return params


@api_router.post("/api/v1/lnurlauth")
async def api_perform_lnurlauth(
    data: CreateLnurlAuth, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    err = await perform_lnurlauth(data.callback, wallet=wallet)
    if err:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE, detail=err.reason
        )
    return ""


@api_router.get("/api/v1/currencies")
async def api_list_currencies_available() -> List[str]:
    return allowed_currencies()


@api_router.post("/api/v1/conversion")
async def api_fiat_as_sats(data: ConversionData):
    output = {}
    if data.from_ == "sat":
        output["BTC"] = data.amount / 100000000
        output["sats"] = int(data.amount)
        for currency in data.to.split(","):
            output[currency.strip().upper()] = await satoshis_amount_as_fiat(
                data.amount, currency.strip()
            )
        return output
    else:
        output[data.from_.upper()] = data.amount
        output["sats"] = await fiat_amount_as_satoshis(data.amount, data.from_)
        output["BTC"] = output["sats"] / 100000000
        return output


@api_router.get("/api/v1/qrcode/{data}", response_class=StreamingResponse)
async def img(data):
    qr = pyqrcode.create(data)
    stream = BytesIO()
    qr.svg(stream, scale=3)
    stream.seek(0)

    async def _generator(stream: BytesIO):
        yield stream.getvalue()

    return StreamingResponse(
        _generator(stream),
        headers={
            "Content-Type": "image/svg+xml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
