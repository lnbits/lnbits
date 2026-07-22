from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from lnurl import Lnurl

from tests.e2e.extension_helpers import E2EWallet, invoice_payment_request
from tests.e2e.helpers import api_json


class LNURLPayServer:
    def __init__(self, base_url: str, target_wallet: E2EWallet) -> None:
        self._server = _LNURLHTTPServer(("127.0.0.1", 0), _LNURLPayHandler)
        self._server.base_url = base_url
        self._server.target_wallet = target_wallet
        self._thread = threading.Thread(target=self._server.serve_forever)

    def __enter__(self) -> LNURLPayServer:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._thread.join(timeout=10)
        self._server.server_close()

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/pay"

    @property
    def lnurl(self) -> str:
        return str(Lnurl(self.url).bech32)


class _LNURLHTTPServer(ThreadingHTTPServer):
    base_url: str
    target_wallet: E2EWallet


class _LNURLPayHandler(BaseHTTPRequestHandler):
    server: _LNURLHTTPServer

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/pay":
            self._send_json(
                HTTPStatus.OK,
                {
                    "tag": "payRequest",
                    "callback": self._callback_url(),
                    "minSendable": 1000,
                    "maxSendable": 1_000_000,
                    "metadata": json.dumps([["text/plain", "LNbits e2e LNURL-pay"]]),
                },
            )
            return

        if url.path == "/callback":
            amount_msat = int(parse_qs(url.query)["amount"][0])
            amount_sats = amount_msat // 1000
            invoice = api_json(
                self.server.base_url,
                "POST",
                "/api/v1/payments",
                {
                    "out": False,
                    "amount": amount_sats,
                    "unit": "sat",
                    "memo": "LNbits e2e LNURL-pay target",
                },
                api_key=self.server.target_wallet.inkey,
            )
            self._send_json(
                HTTPStatus.OK,
                {
                    "pr": invoice_payment_request(invoice),
                    "routes": [],
                },
            )
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"status": "ERROR", "reason": "LNURL route not found."},
        )

    def log_message(self, _format: str, *_args: object) -> None:
        pass

    def _callback_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/callback"

    def _send_json(self, status: HTTPStatus, body: dict[str, object]) -> None:
        raw_body = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw_body)))
        self.end_headers()
        self.wfile.write(raw_body)
