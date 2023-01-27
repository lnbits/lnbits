import json
from http import HTTPStatus
from typing import Any, List

from fastapi import Depends, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import nostrrelay_ext
from .crud import create_event
from .models import NostrEvent, NostrEventType, NostrFilter


@nostrrelay_ext.websocket("/client")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        json_data = await websocket.receive_text()
        # print('### data', json_data)
        data = json.loads(json_data)
        await handle_message(data)


async def handle_message(data: List):
    if len(data) < 2:
        return

    try:
        message_type = data[0]
        if message_type == NostrEventType.EVENT:
            return await handle_event(NostrEvent.parse_obj(data[1]))
        if message_type == NostrEventType.REQ:
            if len(data) != 3:
                return
            return handle_request(data[1], NostrFilter.parse_obj(data[2]))
        if message_type == NostrEventType.CLOSE:
            return handle_close(data[1])
    except Exception as e:
        logger.warning(e)


async def handle_event(e: NostrEvent):
    print("### handle_event", e)
    e.check_signature()
    await create_event("111", e)


def handle_request(subscription_id: str, filters: NostrFilter):
    print("### handle_request 1", subscription_id)
    print("### handle_request 2", filters)


def handle_close(subscription_id: str):
    print("### handle_close", subscription_id)


@nostrrelay_ext.get("/api/v1/enable", status_code=HTTPStatus.OK)
async def api_nostrrelay(enable: bool = Query(True)):
    return await enable_relay(enable)


async def enable_relay(enable: bool):
    return enable
