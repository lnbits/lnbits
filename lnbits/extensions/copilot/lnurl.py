import json
import hashlib
import math
from fastapi import Request
import hashlib
from http import HTTPStatus

from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
import base64
from lnurl import (
    LnurlPayResponse,
    LnurlPayActionResponse,
    LnurlErrorResponse,
)  # type: ignore
from lnurl.types import LnurlPayMetadata
from lnbits.core.services import create_invoice
from .models import Copilots, CreateCopilotData
from . import copilot_ext
from .crud import get_copilot
from typing import Optional
from fastapi.params import Depends
from fastapi.param_functions import Query


@copilot_ext.get(
    "/lnurl/{cp_id}", response_class=HTMLResponse, name="copilot.lnurl_response"
)
async def lnurl_response(req: Request, cp_id: str = Query(None)):
    cp = await get_copilot(cp_id)
    if not cp:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Copilot not found"
        )

    payResponse = {
        "tag": "payRequest",
        "callback": req.url_for("copilot.lnurl_callback", cp_id=cp_id),
        "metadata": LnurlPayMetadata(json.dumps([["text/plain", str(cp.lnurl_title)]])),
        "maxSendable": 50000000,
        "minSendable": 10000,
    }

    if cp.show_message:
        payResponse["commentAllowed"] = 300
    return json.dumps(payResponse)


@copilot_ext.get(
    "/lnurl/cb/{cp_id}", response_class=HTMLResponse, name="copilot.lnurl_callback"
)
async def lnurl_callback(
    cp_id: str = Query(None), amount: str = Query(None), comment: str = Query(None)
):
    cp = await get_copilot(cp_id)
    if not cp:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Copilot not found"
        )
    amount_received = int(amount)

    if amount_received < 10000:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Amount {round(amount_received / 1000)} is smaller than minimum 10 sats.",
        )
    elif amount_received / 1000 > 10000000:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Amount {round(amount_received / 1000)} is greater than maximum 50000.",
        )
    comment = ""
    if comment:
        if len(comment or "") > 300:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Got a comment with {len(comment)} characters, but can only accept 300",
            )
        if len(comment) < 1:
            comment = "none"
    payment_hash, payment_request = await create_invoice(
        wallet_id=cp.wallet,
        amount=int(amount_received / 1000),
        memo=cp.lnurl_title,
        description_hash=hashlib.sha256(
            (
                LnurlPayMetadata(json.dumps([["text/plain", str(cp.lnurl_title)]]))
            ).encode("utf-8")
        ).digest(),
        extra={"tag": "copilot", "copilot": cp.id, "comment": comment},
    )
    payResponse = {
        "pr": payment_request,
        "routes": [],
    }
    return json.dumps(payResponse)
