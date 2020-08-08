from flask_socketio import send, emit
from flask_socketio import SocketIO  # type: ignore

from lnbits.settings import WALLET


def attach_socket_methods(socketio) -> None:
    @socketio.on("wait_invoice")
    def handle_wait_invoice(json):
        try:
            paid = not WALLET.wait_invoice(checking_id=json["id"]).pending
        except Exception as e:
            paid = False
        emit(json["id"], {"paid": paid})

    @socketio.on("connect")
    def on_connect():
        send("websocket connection established (socket.py)")


# from lnbits.decorators import api_check_wallet_key
# @api_check_wallet_key("invoice")
