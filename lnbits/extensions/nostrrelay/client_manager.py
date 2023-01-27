import json
from typing import List

from fastapi import WebSocket
from loguru import logger
from pydantic import BaseModel

from .crud import create_event, get_events
from .models import NostrEvent, NostrEventType, NostrFilter


class NostrClientManager:
    
    def __init__(self):
        self.clients: List["NostrClientConnection"] = []

    def add_client(self, client: "NostrClientConnection"):
        self.clients.append(client)

    def remove_client(self, client: "NostrClientConnection"):
        self.clients.remove(client)

class NostrClientConnection:
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.filters: List[NostrFilter] = []

    async def start(self):
        await self.websocket.accept()
        while True:
            json_data = await self.websocket.receive_text()
            try:
                data = json.loads(json_data)
                resp = await self.handle_message(data)
                if resp:
                    for r in resp:
                        await self.websocket.send_text(json.dumps(r))
            except Exception as e:
                logger.warning(e)

    async def handle_message(self, data: List):
        if len(data) < 2:
            return

        message_type = data[0]
        if message_type == NostrEventType.EVENT:
            return await self.handle_event(NostrEvent.parse_obj(data[1]))
        if message_type == NostrEventType.REQ:
            if len(data) != 3:
                return
            return await self.handle_request(data[1], NostrFilter.parse_obj(data[2]))
        if message_type == NostrEventType.CLOSE:
            return self.handle_close(data[1])

    async def handle_event(self, e: "NostrEvent") -> None:
        e.check_signature()
        await create_event("111", e)

    async def handle_request(self, subscription_id: str, filter: "NostrFilter") -> List:
        events = await get_events("111", filter)
        x = [[NostrEventType.EVENT, subscription_id, dict(event)] for event in events]
        return x

    def handle_close(self, subscription_id: str) -> None:
        print("### handle_close", subscription_id)
