import asyncio
import logging
from typing import Any, Dict

import websockets


# Many thanks to Fusion44 for https://gist.github.com/fusion44/9af0b054b4609012752b0c8c1dafbd4a

class Relay:
    url: str
    read: bool
    write: bool
    active: bool
    _connection: Any

    def __init__(self, url: str, read: bool, write: bool, active: bool) -> None:
        self.url = url
        self.read = read
        self.write = write
        self.active = active

    async def connect(self):
        self._connection = await websockets.connect(self.url)

    async def send(self, message):
        if not self.write or not self.active:
            raise RuntimeError("Can't send to a relay that is inactive or not writable")
        await self._connection.send(message)

    async def listen(self):
        if not self.read or not self.active:
            raise RuntimeError(
                "Can't listen to a relay that is inactive or not readable"
            )

        while True:
            try:
                msg = await self._connection.recv()
                yield msg
            except websockets.ConnectionClosedOK:
                break


class RelayManager:
    _relays: Dict[str, Relay] = {}
    _tasks: Dict[str, asyncio.Task] = {}
    msg_channel = asyncio.Queue()

    def __init__(self, enable_ws_debugger=False) -> None:
        if enable_ws_debugger:
            logger = logging.getLogger("websockets")
            logger.setLevel(logging.DEBUG)
            logger.addHandler(logging.StreamHandler())
        pass

    async def add_relay(self, relay: Relay):
        if relay.url in self._relays.keys():
            raise RuntimeError(f"Relay {relay.url} exists")

        if relay.active and relay.read:
            await relay.connect()
            loop = asyncio.get_event_loop()
            t = loop.create_task(self._relay_listener(relay, self.msg_channel))
            self._tasks[relay.url] = t

        self._relays[relay.url] = relay

    async def remove_relay(self, url: str):
        if url in self._relays.keys():
            relay = self._relays[url]
            if relay.active:
                t = self._tasks[url]
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    print(f"Canceled task {relay.url}")

    def get_relay(self, url: str) -> Relay:
        if not url in self._relays.keys():
            raise RuntimeError("Relay not found")
        return self._relays.get(url)

    async def update_relay(self, relay: Relay):
        if relay.url in self._relays.keys():
            # remove the old relay
            await self.remove_relay(relay.url)

            # add the new relay
            await self.add_relay(relay)
        else:
            raise RuntimeError("Unknown Relay")

    async def send_to_all(self, message):
        for r in self._relays.values():
            if r.write:
                await r.send(message=message)

    async def _relay_listener(self, relay: Relay, msg_chan: asyncio.Queue):
        print(f"listening for {relay.url}")
        async for msg in relay.listen():
            print(msg)
            msg_chan.put_nowait(msg)
        print(f"STOP listening for {relay.url}")