from http import HTTPStatus

from fastapi import Request
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_wallet, get_wallet_for_key
from lnbits.decorators import WalletTypeInfo, require_admin_key

from . import splitpayments_ext
from .crud import get_targets, set_targets
from .models import Target, TargetPut


@splitpayments_ext.get("/api/v1/targets")
async def api_targets_get(wallet: WalletTypeInfo = Depends(require_admin_key)):
    targets = await get_targets(wallet.wallet.id)
    return [target.dict() for target in targets] or []


@splitpayments_ext.put("/api/v1/targets")
async def api_targets_set(
    req: Request, wal: WalletTypeInfo = Depends(require_admin_key)
):
    body = await req.json()
    targets = []
    data = TargetPut.parse_obj(body["targets"])
    for entry in data.__root__:
        wallet = await get_wallet(entry.wallet)
        if not wallet:
            wallet = await get_wallet_for_key(entry.wallet, "invoice")
            if not wallet:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Invalid wallet '{entry.wallet}'.",
                )

        if wallet.id == wal.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Can't split to itself."
            )

        if entry.percent < 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid percent '{entry.percent}'.",
            )

        targets.append(
            Target(
                wallet=wallet.id,
                source=wal.wallet.id,
                tag=entry.tag,
                percent=entry.percent,
                alias=entry.alias,
            )
        )
        percent_sum = sum([target.percent for target in targets])
        if percent_sum > 100:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Splitting over 100%."
            )
    await set_targets(wal.wallet.id, targets)
    return ""
