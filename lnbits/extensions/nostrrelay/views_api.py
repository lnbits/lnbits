from http import HTTPStatus

from fastapi import Depends, Query
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import nostrrelay_ext


@nostrrelay_ext.get("/api/v1/enable", status_code=HTTPStatus.OK)
async def api_nostrrelay(enable: bool = Query(True)):
    return await enable_relay(enable)


async def enable_relay():
    return
