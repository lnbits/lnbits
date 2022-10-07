from http import HTTPStatus
from io import BytesIO

import pyqrcode
from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.param_functions import Query
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, StreamingResponse

from lnbits.core.crud import update_payment_status
from lnbits.core.models import User
from lnbits.core.views.api import api_payment
from lnbits.decorators import check_user_exists

from . import lnurldevice_ext, lnurldevice_renderer
from .crud import get_lnurldevice, get_lnurldevicepayment

templates = Jinja2Templates(directory="templates")


@lnurldevice_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return lnurldevice_renderer().TemplateResponse(
        "lnurldevice/index.html", {"request": request, "user": user.dict()}
    )


@lnurldevice_ext.get(
    "/{paymentid}", name="lnurldevice.displaypin", response_class=HTMLResponse
)
async def displaypin(request: Request, paymentid: str = Query(None)):
    lnurldevicepayment = await get_lnurldevicepayment(paymentid)
    if not lnurldevicepayment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No lmurldevice payment"
        )
    device = await get_lnurldevice(lnurldevicepayment.deviceid)
    if not device:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="lnurldevice not found."
        )
    status = await api_payment(lnurldevicepayment.payhash)
    if status["paid"]:
        await update_payment_status(
            checking_id=lnurldevicepayment.payhash, pending=True
        )
        return lnurldevice_renderer().TemplateResponse(
            "lnurldevice/paid.html", {"request": request, "pin": lnurldevicepayment.pin}
        )
    return lnurldevice_renderer().TemplateResponse(
        "lnurldevice/error.html",
        {"request": request, "pin": "filler", "not_paid": True},
    )


@lnurldevice_ext.get("/img/{lnurldevice_id}", response_class=StreamingResponse)
async def img(request: Request, lnurldevice_id):
    lnurldevice = await get_lnurldevice(lnurldevice_id)
    if not lnurldevice:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURLDevice does not exist."
        )
    return lnurldevice.lnurl(request)


##################WEBSOCKET ROUTES########################


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, lnurldevice_id: str):
        await websocket.accept()
        websocket.id = lnurldevice_id
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, lnurldevice_id: str):
        for connection in self.active_connections:
            if connection.id == lnurldevice_id:
                await connection.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@lnurldevice_ext.websocket("/ws/{lnurldevice_id}", name="lnurldevice.lnurldevice_by_id")
async def websocket_endpoint(websocket: WebSocket, lnurldevice_id: str):
    await manager.connect(websocket, lnurldevice_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def updater(lnurldevice_id):
    lnurldevice = await get_lnurldevice(lnurldevice_id)
    if not lnurldevice:
        return
    await manager.send_personal_message(f"{lnurldevice.amount}", lnurldevice_id)
