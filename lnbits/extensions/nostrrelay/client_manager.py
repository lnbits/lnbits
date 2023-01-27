import json
from typing import Callable, List

from fastapi import WebSocket
from loguru import logger

from .crud import create_event, get_events
from .models import NostrEvent, NostrEventType, NostrFilter


class NostrClientManager:
    def __init__(self):
        self.clients: List["NostrClientConnection"] = []

    def add_client(self, client: "NostrClientConnection"):
        setattr(client, "broadcast_event", self.broadcast_event)
        self.clients.append(client)
        print("### client count:", len(self.clients))

    def remove_client(self, client: "NostrClientConnection"):
        self.clients.remove(client)

    async def broadcast_event(self, source: "NostrClientConnection", event: NostrEvent):
        print("### broadcast_event", len(self.clients))
        for client in self.clients:
            if client != source:
                await client.notify_event(event)


class NostrClientConnection:
    broadcast_event: Callable

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.filters: List[NostrFilter] = []

    async def start(self):
        await self.websocket.accept()
        while True:
            json_data = await self.websocket.receive_text()
            try:
                data = json.loads(json_data)
                
                resp = await self.__handle_message(data)
                if resp:
                    for r in resp:
                        print("### start send content: ", json.dumps(r))
                        await self.websocket.send_text(json.dumps(r))
            except Exception as e:
                logger.warning(e)

    async def notify_event(self, event: NostrEvent) -> bool:
        for filter in self.filters:
            if filter.matches(event):
                r = [NostrEventType.EVENT, filter.subscription_id, dict(event)]
                print("### notify send content: ", json.dumps(r))
                await self.websocket.send_text(json.dumps(r))
                return True
        return False

    async def __handle_message(self, data: List):
        if len(data) < 2:
            return

        message_type = data[0]
        if message_type == NostrEventType.EVENT:
            return await self.__handle_event(NostrEvent.parse_obj(data[1]))
        if message_type == NostrEventType.REQ:
            if len(data) != 3:
                return
            return await self.__handle_request(data[1], NostrFilter.parse_obj(data[2]))
        if message_type == NostrEventType.CLOSE:
            return self.__handle_close(data[1])

    async def __handle_event(self, e: "NostrEvent") -> None:
        # print('### __handle_event', e)
        e.check_signature()
        await create_event("111", e)
        await self.broadcast_event(self, e)

    async def __handle_request(self, subscription_id: str, filter: NostrFilter) -> List:
        filter.subscription_id = subscription_id
        # print("### __handle_request", filter)
        self.filters.append(filter)
        events = await get_events("111", filter)
        return [
            [NostrEventType.EVENT, subscription_id, dict(event)] for event in events
        ]

    def __handle_close(self, subscription_id: str) -> None:
        print("### __handle_close", len(self.filters), subscription_id)
        self.filters = [f for f in self.filters if f.subscription_id != subscription_id]
        print("### __handle_close", len(self.filters))
