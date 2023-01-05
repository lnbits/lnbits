## adapted from https://github.com/Sentymental/chat-fastapi-websocket
"""
Create a class Notifier that will handle messages
and delivery to the specific person
"""

import json
from collections import defaultdict

from fastapi import WebSocket
from loguru import logger

from lnbits.extensions.market.crud import create_chat_message
from lnbits.extensions.market.models import CreateChatMessage


class Notifier:
    """
    Manages chatrooms, sessions and members.

    Methods:
    - get_notification_generator(self): async generator with notification messages
    - get_members(self, room_name: str): get members in room
    - push(message: str, room_name: str): push message
    - connect(websocket: WebSocket, room_name: str): connect to room
    - remove(websocket: WebSocket, room_name: str): remove
    - _notify(message: str, room_name: str): notifier
    """

    def __init__(self):
        # Create sessions as a dict:
        self.sessions: dict = defaultdict(dict)

        # Create notification generator:
        self.generator = self.get_notification_generator()

    async def get_notification_generator(self):
        """Notification Generator"""

        while True:
            message = yield
            msg = message["message"]
            room_name = message["room_name"]
            await self._notify(msg, room_name)

    def get_members(self, room_name: str):
        """Get all members in a room"""

        try:
            logger.info(f"Looking for members in room: {room_name}")
            return self.sessions[room_name]

        except Exception:
            logger.exception(f"There is no member in room: {room_name}")
            return None

    async def push(self, message: str, room_name: str = None):
        """Push a message"""

        message_body = {"message": message, "room_name": room_name}
        await self.generator.asend(message_body)

    async def connect(self, websocket: WebSocket, room_name: str):
        """Connect to room"""

        await websocket.accept()
        if self.sessions[room_name] == {} or len(self.sessions[room_name]) == 0:
            self.sessions[room_name] = []

        self.sessions[room_name].append(websocket)
        print(f"Connections ...: {self.sessions[room_name]}")

    def remove(self, websocket: WebSocket, room_name: str):
        """Remove websocket from room"""

        self.sessions[room_name].remove(websocket)
        print(f"Connection removed...\nOpen connections...: {self.sessions[room_name]}")

    async def _notify(self, message: str, room_name: str):
        """Notifier"""
        d = json.loads(message)
        d["room_name"] = room_name
        db_msg = CreateChatMessage.parse_obj(d)
        await create_chat_message(data=db_msg)

        remaining_sessions = []
        while len(self.sessions[room_name]) > 0:
            websocket = self.sessions[room_name].pop()
            await websocket.send_text(message)
            remaining_sessions.append(websocket)
        self.sessions[room_name] = remaining_sessions
