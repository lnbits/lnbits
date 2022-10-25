from http import HTTPStatus

import crontools as ct
from fastapi import Query
from fastapi.params import Depends
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import scheduledpayments_ext
from .crud import (
    create_schedule,
    delete_schedule,
    get_events,
    get_schedule,
    get_schedules,
    update_schedule,
)
from .models import CreateScheduleData, UpdateScheduleData


@scheduledpayments_ext.get("/api/v1/schedule/{schedule_id}", status_code=HTTPStatus.OK)
async def api_schedule(
    schedule_id: str, wallet: WalletTypeInfo = Depends(get_key_type)
):
    schedule = await get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Schedule does not exist."
        )

    if wallet.wallet.id != schedule.wallet:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your schedule."
        )

    return schedule.dict()


@scheduledpayments_ext.get("/api/v1/schedule", status_code=HTTPStatus.OK)
async def api_schedules(
    all_wallets: bool = Query(None), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [schedule.dict() for schedule in await get_schedules(wallet_ids)]


@scheduledpayments_ext.post("/api/v1/schedule", status_code=HTTPStatus.CREATED)
async def api_schedule_create(
    data: CreateScheduleData, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        valid = ct.Crontab.parse(data.interval)
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Invalid cron expression."
        )

    schedule = await create_schedule(wallet_id=wallet.wallet.id, data=data)
    return schedule.dict()


@scheduledpayments_ext.post("/api/v1/schedule/{schedule_id}", status_code=HTTPStatus.OK)
async def api_schedule_update(
    data: UpdateScheduleData,
    schedule_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    schedule = await update_schedule(wallet_id=wallet.wallet.id, data=data)
    return schedule.dict()


@scheduledpayments_ext.delete(
    "/api/v1/schedule/{schedule_id}", status_code=HTTPStatus.OK
)
async def api_schedule_delete(
    schedule_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    schedule = await get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Schedule does not exist."
        )

    if schedule.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your schedule.", status_code=HTTPStatus.FORBIDDEN
        )

    await delete_schedule(schedule_id)

    return {"success": True}


@scheduledpayments_ext.get("/api/v1/events", status_code=HTTPStatus.OK)
async def api_events(
    all_wallets: bool = Query(None), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [event.dict() for event in await get_events(wallet_ids)]
