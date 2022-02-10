from http import HTTPStatus
import asyncio
from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from . import nostradmin_ext, nostr_renderer
# FastAPI good for incoming
from fastapi import Request, WebSocket, WebSocketDisconnect
# Websockets needed for outgoing 
import websockets

from lnbits.core.crud import update_payment_status
from lnbits.core.models import User
from lnbits.core.views.api import api_payment
from lnbits.decorators import check_user_exists

from .crud import get_nostrkeys, get_nostrrelay

templates = Jinja2Templates(directory="templates")


@nostradmin_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return nostr_renderer().TemplateResponse(
        "nostradmin/index.html", {"request": request, "user": user.dict()}
    )

#####################################################################
#################### NOSTR WEBSOCKET THREAD #########################
##### THE QUEUE LOOP THREAD THING THAT LISTENS TO BUNCH OF ##########
### WEBSOCKET CONNECTIONS, STORING DATA IN DB/PUSHING TO FRONTEND ###
################### VIA updater() FUNCTION ##########################
#####################################################################

websocket_queue = asyncio.Queue(1000)

# while True:
async def nostr_subscribe():
    return
    # for the relays:
    # async with websockets.connect("ws://localhost:8765") as websocket:
    # for the public keys:
    # await websocket.send("subscribe to events")
    # await websocket.recv()

#####################################################################
################### LNBITS WEBSOCKET ROUTES #########################
#### HERE IS WHERE LNBITS FRONTEND CAN RECEIVE AND SEND MESSAGES ####
#####################################################################

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, nostr_id: str):
        await websocket.accept()
        websocket.id = nostr_id
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, nostr_id: str):
        for connection in self.active_connections:
            if connection.id == nostr_id:
                await connection.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@nostradmin_ext.websocket("/nostradmin/ws/relayevents/{nostr_id}", name="nostr_id.websocket_by_id")
async def websocket_endpoint(websocket: WebSocket, nostr_id: str):
    await manager.connect(websocket, nostr_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def updater(nostr_id, message):
    copilot = await get_copilot(nostr_id)
    if not copilot:
        return
    await manager.send_personal_message(f"{message}", nostr_id)


async def relay_check(relay: str):
    async with websockets.connect(relay) as websocket:
            if str(websocket.state) == "State.OPEN":
                print(str(websocket.state))
                return True
            else:
                return False