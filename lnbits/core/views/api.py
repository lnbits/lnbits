import asyncio
import base64
import hashlib
import json
import uuid
from http import HTTPStatus
from io import BytesIO
from typing import Dict, List, Optional, Union
from urllib.parse import ParseResult, parse_qs, unquote, urlencode, urlparse, urlunparse

import httpx
import pyqrcode
from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
from sse_starlette.sse import EventSourceResponse
from starlette.responses import RedirectResponse, StreamingResponse

from lnbits import bolt11, lnurl
from lnbits.core.db import core_app_extra, db
from lnbits.core.helpers import (
    migrate_extension_database,
    stop_extension_background_work,
)
from lnbits.core.models import (
    ConversionData,
    CreateInvoice,
    CreateLnurl,
    CreateLnurlAuth,
    CreateWallet,
    CreateWebPushSubscription,
    DecodePayment,
    Payment,
    PaymentFilters,
    PaymentHistoryPoint,
    Query,
    User,
    Wallet,
    WalletType,
    WebPushSubscription,
)
from lnbits.db import Filters, Page
from lnbits.decorators import (
    WalletTypeInfo,
    check_admin,
    get_key_type,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.extension_manager import (
    CreateExtension,
    Extension,
    ExtensionRelease,
    InstallableExtension,
    fetch_github_release_config,
    get_valid_extensions,
)
from lnbits.helpers import generate_filter_params_openapi, url_for
from lnbits.settings import settings
from lnbits.utils.exchange_rates import (
    currencies,
    fiat_amount_as_satoshis,
    satoshis_amount_as_fiat,
)

from ..crud import (
    DateTrunc,
    add_installed_extension,
    create_account,
    create_tinyurl,
    create_wallet,
    create_webpush_subscription,
    delete_dbversion,
    delete_installed_extension,
    delete_tinyurl,
    delete_wallet,
    delete_webpush_subscription,
    drop_extension_db,
    get_dbversions,
    get_payments,
    get_payments_history,
    get_payments_paginated,
    get_standalone_payment,
    get_tinyurl,
    get_tinyurl_by_url,
    get_wallet_for_key,
    get_webpush_subscription,
    save_balance_check,
    update_pending_payments,
    update_wallet,
)
from ..services import (
    InvoiceFailure,
    PaymentFailure,
    check_transaction_status,
    create_invoice,
    pay_invoice,
    perform_lnurlauth,
    websocketManager,
    websocketUpdater,
)
from ..tasks import api_invoice_listeners

api_router = APIRouter()


@api_router.get("/api/v1/health", status_code=HTTPStatus.OK)
async def health():
    return


@api_router.get("/api/v1/wallet")
async def api_wallet(wallet: WalletTypeInfo = Depends(get_key_type)):
    if wallet.wallet_type == WalletType.admin:
        return {
            "id": wallet.wallet.id,
            "name": wallet.wallet.name,
            "balance": wallet.wallet.balance_msat,
        }
    else:
        return {"name": wallet.wallet.name, "balance": wallet.wallet.balance_msat}


@api_router.put("/api/v1/wallet/{new_name}")
async def api_update_wallet_name(
    new_name: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    await update_wallet(wallet.wallet.id, new_name)
    return {
        "id": wallet.wallet.id,
        "name": wallet.wallet.name,
        "balance": wallet.wallet.balance_msat,
    }


@api_router.patch("/api/v1/wallet", response_model=Wallet)
async def api_update_wallet(
    name: Optional[str] = Body(None),
    currency: Optional[str] = Body(None),
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    return await update_wallet(wallet.wallet.id, name, currency)


@api_router.delete("/api/v1/wallet")
async def api_delete_wallet(
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> None:
    await delete_wallet(
        user_id=wallet.wallet.user,
        wallet_id=wallet.wallet.id,
    )


@api_router.post("/api/v1/wallet", response_model=Wallet)
async def api_create_wallet(
    data: CreateWallet,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> Wallet:
    return await create_wallet(user_id=wallet.wallet.user, wallet_name=data.name)


@api_router.post("/api/v1/account", response_model=Wallet)
async def api_create_account(data: CreateWallet) -> Wallet:
    if len(settings.lnbits_allowed_users) > 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Account creation is disabled.",
        )
    account = await create_account()
    return await create_wallet(user_id=account.id, wallet_name=data.name)


@api_router.get(
    "/api/v1/payments",
    name="Payment List",
    summary="get list of payments",
    response_description="list of payments",
    response_model=List[Payment],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments(
    wallet: WalletTypeInfo = Depends(get_key_type),
    filters: Filters = Depends(parse_filters(PaymentFilters)),
):
    await update_pending_payments(wallet.wallet.id)
    return await get_payments(
        wallet_id=wallet.wallet.id,
        pending=True,
        complete=True,
        filters=filters,
    )


@api_router.get(
    "/api/v1/payments/history",
    name="Get payments history",
    response_model=List[PaymentHistoryPoint],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_history(
    wallet: WalletTypeInfo = Depends(get_key_type),
    group: DateTrunc = Query("day"),
    filters: Filters[PaymentFilters] = Depends(parse_filters(PaymentFilters)),
):
    await update_pending_payments(wallet.wallet.id)
    return await get_payments_history(wallet.wallet.id, group, filters)


@api_router.get(
    "/api/v1/payments/paginated",
    name="Payment List",
    summary="get paginated list of payments",
    response_description="list of payments",
    response_model=Page[Payment],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_paginated(
    wallet: WalletTypeInfo = Depends(get_key_type),
    filters: Filters = Depends(parse_filters(PaymentFilters)),
):
    await update_pending_payments(wallet.wallet.id)
    page = await get_payments_paginated(
        wallet_id=wallet.wallet.id,
        pending=True,
        complete=True,
        filters=filters,
    )
    return page


async def api_payments_create_invoice(data: CreateInvoice, wallet: Wallet):
    description_hash = b""
    unhashed_description = b""
    memo = data.memo or settings.lnbits_site_title
    if data.description_hash or data.unhashed_description:
        if data.description_hash:
            try:
                description_hash = bytes.fromhex(data.description_hash)
            except ValueError:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="'description_hash' must be a valid hex string",
                )
        if data.unhashed_description:
            try:
                unhashed_description = bytes.fromhex(data.unhashed_description)
            except ValueError:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="'unhashed_description' must be a valid hex string",
                )
        # do not save memo if description_hash or unhashed_description is set
        memo = ""

    async with db.connect() as conn:
        try:
            payment_hash, payment_request = await create_invoice(
                wallet_id=wallet.id,
                amount=data.amount,
                memo=memo,
                currency=data.unit,
                description_hash=description_hash,
                unhashed_description=unhashed_description,
                expiry=data.expiry,
                extra=data.extra,
                webhook=data.webhook,
                internal=data.internal,
                conn=conn,
            )
            # NOTE: we get the checking_id with a seperate query because create_invoice
            # does not return it and it would be a big hustle to change its return type
            # (used across extensions)
            payment_db = await get_standalone_payment(payment_hash, conn=conn)
            assert payment_db is not None, "payment not found"
            checking_id = payment_db.checking_id
        except InvoiceFailure as e:
            raise HTTPException(status_code=520, detail=str(e))
        except Exception as exc:
            raise exc

    invoice = bolt11.decode(payment_request)

    lnurl_response: Union[None, bool, str] = None
    if data.lnurl_callback:
        if data.lnurl_balance_check is not None:
            await save_balance_check(wallet.id, data.lnurl_balance_check)

        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    data.lnurl_callback,
                    params={
                        "pr": payment_request,
                        "balanceNotify": url_for(
                            f"/withdraw/notify/{urlparse(data.lnurl_callback).netloc}",
                            external=True,
                            wal=wallet.id,
                        ),
                    },
                    timeout=10,
                )
                if r.is_error:
                    lnurl_response = r.text
                else:
                    resp = json.loads(r.text)
                    if resp["status"] != "OK":
                        lnurl_response = resp["reason"]
                    else:
                        lnurl_response = True
            except (httpx.ConnectError, httpx.RequestError) as ex:
                logger.error(ex)
                lnurl_response = False

    return {
        "payment_hash": invoice.payment_hash,
        "payment_request": payment_request,
        # maintain backwards compatibility with API clients:
        "checking_id": checking_id,
        "lnurl_response": lnurl_response,
    }


async def api_payments_pay_invoice(bolt11: str, wallet: Wallet):
    try:
        payment_hash = await pay_invoice(wallet_id=wallet.id, payment_request=bolt11)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=str(e))
    except PaymentFailure as e:
        raise HTTPException(status_code=520, detail=str(e))
    except Exception as exc:
        raise exc

    return {
        "payment_hash": payment_hash,
        # maintain backwards compatibility with API clients:
        "checking_id": payment_hash,
    }


@api_router.post(
    "/api/v1/payments",
    summary="Create or pay an invoice",
    description="""
        This endpoint can be used both to generate and pay a BOLT11 invoice.
        To generate a new invoice for receiving funds into the authorized account,
        specify at least the first four fields in the POST body: `out: false`,
        `amount`, `unit`, and `memo`. To pay an arbitrary invoice from the funds
        already in the authorized account, specify `out: true` and use the `bolt11`
        field to supply the BOLT11 invoice to be paid.
    """,
    status_code=HTTPStatus.CREATED,
)
async def api_payments_create(
    wallet: WalletTypeInfo = Depends(require_invoice_key),
    invoiceData: CreateInvoice = Body(...),
):
    if invoiceData.out is True and wallet.wallet_type == WalletType.admin:
        if not invoiceData.bolt11:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="BOLT11 string is invalid or not given",
            )
        return await api_payments_pay_invoice(
            invoiceData.bolt11, wallet.wallet
        )  # admin key
    elif not invoiceData.out:
        # invoice key
        return await api_payments_create_invoice(invoiceData, wallet.wallet)
    else:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Invoice (or Admin) key required.",
        )


@api_router.post("/api/v1/payments/lnurl")
async def api_payments_pay_lnurl(
    data: CreateLnurl, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    domain = urlparse(data.callback).netloc

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                data.callback,
                params={"amount": data.amount, "comment": data.comment},
                timeout=40,
            )
            if r.is_error:
                raise httpx.ConnectError("LNURL callback connection error")
        except (httpx.ConnectError, httpx.RequestError):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Failed to connect to {domain}.",
            )

    params = json.loads(r.text)
    if params.get("status") == "ERROR":
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} said: '{params.get('reason', '')}'",
        )

    if not params.get("pr"):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} did not return a payment request.",
        )

    invoice = bolt11.decode(params["pr"])
    if invoice.amount_msat != data.amount:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                (
                    f"{domain} returned an invalid invoice. Expected"
                    f" {data.amount} msat, got {invoice.amount_msat}."
                ),
            ),
        )

    extra = {}

    if params.get("successAction"):
        extra["success_action"] = params["successAction"]
    if data.comment:
        extra["comment"] = data.comment
    assert data.description is not None, "description is required"
    payment_hash = await pay_invoice(
        wallet_id=wallet.wallet.id,
        payment_request=params["pr"],
        description=data.description,
        extra=extra,
    )

    return {
        "success_action": params.get("successAction"),
        "payment_hash": payment_hash,
        # maintain backwards compatibility with API clients:
        "checking_id": payment_hash,
    }


async def subscribe_wallet_invoices(request: Request, wallet: Wallet):
    """
    Subscribe to new invoices for a wallet. Can be wrapped in EventSourceResponse.
    Listenes invoming payments for a wallet and yields jsons with payment details.
    """
    this_wallet_id = wallet.id

    payment_queue: asyncio.Queue[Payment] = asyncio.Queue(0)

    uid = f"{this_wallet_id}_{str(uuid.uuid4())[:8]}"
    logger.debug(f"adding sse listener for wallet: {uid}")
    api_invoice_listeners[uid] = payment_queue

    try:
        while True:
            if await request.is_disconnected():
                await request.close()
                break
            payment: Payment = await payment_queue.get()
            if payment.wallet_id == this_wallet_id:
                logger.debug("sse listener: payment received", payment)
                yield dict(data=payment.json(), event="payment-received")
    except asyncio.CancelledError:
        logger.debug(f"removing listener for wallet {uid}")
    except Exception as exc:
        logger.error(f"Error in sse: {exc}")
    finally:
        api_invoice_listeners.pop(uid)


@api_router.get("/api/v1/payments/sse")
async def api_payments_sse(
    request: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    return EventSourceResponse(
        subscribe_wallet_invoices(request, wallet.wallet),
        ping=20,
        media_type="text/event-stream",
    )


# TODO: refactor this route into a public and admin one
@api_router.get("/api/v1/payments/{payment_hash}")
async def api_payment(payment_hash, X_Api_Key: Optional[str] = Header(None)):
    # We use X_Api_Key here because we want this call to work with and without keys
    # If a valid key is given, we also return the field "details", otherwise not
    wallet = await get_wallet_for_key(X_Api_Key) if isinstance(X_Api_Key, str) else None
    wallet = wallet if wallet and not wallet.deleted else None
    # we have to specify the wallet id here, because postgres and sqlite return
    # internal payments in different order and get_standalone_payment otherwise
    # just fetches the first one, causing unpredictable results
    payment = await get_standalone_payment(
        payment_hash, wallet_id=wallet.id if wallet else None
    )
    if payment is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Payment does not exist."
        )
    await check_transaction_status(payment.wallet_id, payment_hash)
    payment = await get_standalone_payment(
        payment_hash, wallet_id=wallet.id if wallet else None
    )
    if not payment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Payment does not exist."
        )
    elif not payment.pending:
        if wallet and wallet.id == payment.wallet_id:
            return {"paid": True, "preimage": payment.preimage, "details": payment}
        return {"paid": True, "preimage": payment.preimage}

    try:
        await payment.check_status()
    except Exception:
        if wallet and wallet.id == payment.wallet_id:
            return {"paid": False, "details": payment}
        return {"paid": False}

    if wallet and wallet.id == payment.wallet_id:
        return {
            "paid": not payment.pending,
            "preimage": payment.preimage,
            "details": payment,
        }
    return {"paid": not payment.pending, "preimage": payment.preimage}


@api_router.get("/api/v1/lnurlscan/{code}")
async def api_lnurlscan(code: str, wallet: WalletTypeInfo = Depends(get_key_type)):
    try:
        url = lnurl.decode(code)
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
        async with httpx.AsyncClient(follow_redirects=True) as client:
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


@api_router.post("/api/v1/payments/decode", status_code=HTTPStatus.OK)
async def api_payments_decode(data: DecodePayment) -> JSONResponse:
    payment_str = data.data
    try:
        if payment_str[:5] == "LNURL":
            url = lnurl.decode(payment_str)
            return JSONResponse({"domain": url})
        else:
            invoice = bolt11.decode(payment_str)
            return JSONResponse(invoice.data)
    except Exception as exc:
        return JSONResponse(
            {"message": f"Failed to decode: {str(exc)}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )


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
async def api_list_currencies_available():
    if len(settings.lnbits_allowed_currencies) > 0:
        return [
            item
            for item in currencies.keys()
            if item.upper() in settings.lnbits_allowed_currencies
        ]
    return list(currencies.keys())


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


@api_router.websocket("/api/v1/ws/{item_id}")
async def websocket_connect(websocket: WebSocket, item_id: str):
    await websocketManager.connect(websocket, item_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocketManager.disconnect(websocket)


@api_router.post("/api/v1/ws/{item_id}")
async def websocket_update_post(item_id: str, data: str):
    try:
        await websocketUpdater(item_id, data)
        return {"sent": True, "data": data}
    except Exception:
        return {"sent": False, "data": data}


@api_router.get("/api/v1/ws/{item_id}/{data}")
async def websocket_update_get(item_id: str, data: str):
    try:
        await websocketUpdater(item_id, data)
        return {"sent": True, "data": data}
    except Exception:
        return {"sent": False, "data": data}


@api_router.post("/api/v1/extension")
async def api_install_extension(
    data: CreateExtension, user: User = Depends(check_admin)
):
    release = await InstallableExtension.get_extension_release(
        data.ext_id, data.source_repo, data.archive
    )
    if not release:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Release not found"
        )

    if not release.is_version_compatible:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Incompatible extension version"
        )

    ext_info = InstallableExtension(
        id=data.ext_id, name=data.ext_id, installed_release=release, icon=release.icon
    )

    ext_info.download_archive()

    try:
        ext_info.extract_archive()

        extension = Extension.from_installable_ext(ext_info)

        db_version = (await get_dbversions()).get(data.ext_id, 0)
        await migrate_extension_database(extension, db_version)

        await add_installed_extension(ext_info)

        # call stop while the old routes are still active
        await stop_extension_background_work(data.ext_id, user.id)

        if data.ext_id not in settings.lnbits_deactivated_extensions:
            settings.lnbits_deactivated_extensions += [data.ext_id]

        # mount routes for the new version
        core_app_extra.register_new_ext_routes(extension)

        if extension.upgrade_hash:
            ext_info.nofiy_upgrade()

        return extension

    except Exception as ex:
        logger.warning(ex)
        ext_info.clean_extension_files()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=(
                f"Failed to install extension {ext_info.id} "
                f"({ext_info.installed_version})."
            ),
        )


@api_router.delete("/api/v1/extension/{ext_id}")
async def api_uninstall_extension(ext_id: str, user: User = Depends(check_admin)):
    installable_extensions = await InstallableExtension.get_installable_extensions()

    extensions = [e for e in installable_extensions if e.id == ext_id]
    if len(extensions) == 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unknown extension id: {ext_id}",
        )

    # check that other extensions do not depend on this one
    for valid_ext_id in list(map(lambda e: e.code, get_valid_extensions())):
        installed_ext = next(
            (ext for ext in installable_extensions if ext.id == valid_ext_id), None
        )
        if installed_ext and ext_id in installed_ext.dependencies:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"Cannot uninstall. Extension '{installed_ext.name}' "
                    "depends on this one."
                ),
            )

    try:
        # call stop while the old routes are still active
        await stop_extension_background_work(ext_id, user.id)

        if ext_id not in settings.lnbits_deactivated_extensions:
            settings.lnbits_deactivated_extensions += [ext_id]

        for ext_info in extensions:
            ext_info.clean_extension_files()
            await delete_installed_extension(ext_id=ext_info.id)

        logger.success(f"Extension '{ext_id}' uninstalled.")
    except Exception as ex:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(ex)
        )


@api_router.get(
    "/api/v1/extension/{ext_id}/releases", dependencies=[Depends(check_admin)]
)
async def get_extension_releases(ext_id: str):
    try:
        extension_releases: List[
            ExtensionRelease
        ] = await InstallableExtension.get_extension_releases(ext_id)

        return extension_releases

    except Exception as ex:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(ex)
        )


@api_router.get(
    "/api/v1/extension/release/{org}/{repo}/{tag_name}",
    dependencies=[Depends(check_admin)],
)
async def get_extension_release(org: str, repo: str, tag_name: str):
    try:
        config = await fetch_github_release_config(org, repo, tag_name)
        if not config:
            return {}

        return {
            "min_lnbits_version": config.min_lnbits_version,
            "is_version_compatible": config.is_version_compatible(),
            "warning": config.warning,
        }
    except Exception as ex:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(ex)
        )


@api_router.delete(
    "/api/v1/extension/{ext_id}/db",
    dependencies=[Depends(check_admin)],
)
async def delete_extension_db(ext_id: str):
    try:
        db_version = (await get_dbversions()).get(ext_id, None)
        if not db_version:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Unknown extension id: {ext_id}",
            )
        await drop_extension_db(ext_id=ext_id)
        await delete_dbversion(ext_id=ext_id)
        logger.success(f"Database removed for extension '{ext_id}'")
    except HTTPException as ex:
        logger.error(ex)
        raise ex
    except Exception as ex:
        logger.error(ex)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Cannot delete data for extension '{ext_id}'",
        )


@api_router.post(
    "/api/v1/tinyurl",
    name="Tinyurl",
    description="creates a tinyurl",
)
async def api_create_tinyurl(
    url: str, endless: bool = False, wallet: WalletTypeInfo = Depends(get_key_type)
):
    tinyurls = await get_tinyurl_by_url(url)
    try:
        for tinyurl in tinyurls:
            if tinyurl:
                if tinyurl.wallet == wallet.wallet.inkey:
                    return tinyurl
        return await create_tinyurl(url, endless, wallet.wallet.inkey)
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Unable to create tinyurl"
        )


@api_router.get(
    "/api/v1/tinyurl/{tinyurl_id}",
    name="Tinyurl",
    description="get a tinyurl by id",
)
async def api_get_tinyurl(
    tinyurl_id: str, wallet: WalletTypeInfo = Depends(get_key_type)
):
    try:
        tinyurl = await get_tinyurl(tinyurl_id)
        if tinyurl:
            if tinyurl.wallet == wallet.wallet.inkey:
                return tinyurl
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Wrong key provided."
        )
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Unable to fetch tinyurl"
        )


@api_router.delete(
    "/api/v1/tinyurl/{tinyurl_id}",
    name="Tinyurl",
    description="delete a tinyurl by id",
)
async def api_delete_tinyurl(
    tinyurl_id: str, wallet: WalletTypeInfo = Depends(get_key_type)
):
    try:
        tinyurl = await get_tinyurl(tinyurl_id)
        if tinyurl:
            if tinyurl.wallet == wallet.wallet.inkey:
                await delete_tinyurl(tinyurl_id)
                return {"deleted": True}
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Wrong key provided."
        )
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Unable to delete"
        )


@api_router.get(
    "/t/{tinyurl_id}",
    name="Tinyurl",
    description="redirects a tinyurl by id",
)
async def api_tinyurl(tinyurl_id: str):
    tinyurl = await get_tinyurl(tinyurl_id)
    if tinyurl:
        response = RedirectResponse(url=tinyurl.url)
        return response
    else:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="unable to find tinyurl"
        )


@api_router.post("/api/v1/webpush", status_code=HTTPStatus.CREATED)
async def api_create_webpush_subscription(
    request: Request,
    data: CreateWebPushSubscription,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> WebPushSubscription:
    subscription = json.loads(data.subscription)
    endpoint = subscription["endpoint"]
    host = urlparse(str(request.url)).netloc

    subscription = await get_webpush_subscription(endpoint, wallet.wallet.user)
    if subscription:
        return subscription
    else:
        return await create_webpush_subscription(
            endpoint,
            wallet.wallet.user,
            data.subscription,
            host,
        )


@api_router.delete("/api/v1/webpush", status_code=HTTPStatus.OK)
async def api_delete_webpush_subscription(
    request: Request,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    endpoint = unquote(
        base64.b64decode(str(request.query_params.get("endpoint"))).decode("utf-8")
    )
    await delete_webpush_subscription(endpoint, wallet.wallet.user)
