import json
import httpx
import base64
from .crud import get_targets, set_targets
from .models import Target, TargetPut
from fastapi import Request
from http import HTTPStatus
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
from typing import Optional
from fastapi.params import Depends
from fastapi.param_functions import Query
from . import splitpayments_ext
from lnbits.decorators import (
    check_user_exists,
    WalletTypeInfo,
    get_key_type,
    api_validate_post_request,
    WalletAdminKeyChecker,
    WalletInvoiceKeyChecker,
)
from lnbits.core.crud import get_wallet, get_wallet_for_key


@splitpayments_ext.get("/api/v1/targets")
async def api_targets_get(wallet: WalletTypeInfo = Depends(WalletAdminKeyChecker())):
    targets = await get_targets(wallet.wallet.id)
    return [target.dict() for target in targets] or []


@splitpayments_ext.put("/api/v1/targets")
async def api_targets_set(
    data: TargetPut, wallet: WalletTypeInfo = Depends(WalletAdminKeyChecker())
):
    targets = []
    for entry in data.targets:
        wallet = await get_wallet(entry.wallet)
        if not wallet:
            wallet = await get_wallet_for_key(entry.wallet, "invoice")
            if not wallet:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Invalid wallet '{entry.wallet}'.",
                )

        if wallet.id == wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Can't split to itself.",
            )

        if entry.percent < 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid percent '{entry.percent}'.",
            )

        targets.append(
            Target(wallet.id, wallet.wallet.id, entry.percent, entry.alias or "")
        )

    percent_sum = sum([target.percent for target in targets])
    if percent_sum > 100:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Splitting over 100%.",
        )

    await set_targets(wallet.wallet.id, targets)
    return ""
