import asyncio
import base64
import hashlib
import json
import urllib.parse
from collections.abc import AsyncGenerator
from typing import Any, Optional

import httpx
from httpx import RequestError, TimeoutException
from loguru import logger
from websockets.legacy.client import connect

from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)


class PhoenixdWallet(Wallet):
    """https://phoenix.acinq.co/server/api"""

    def __init__(self):
        if not settings.phoenixd_api_endpoint:
            raise ValueError(
                "cannot initialize PhoenixdWallet: missing phoenixd_api_endpoint"
            )
        if not settings.phoenixd_api_password:
            raise ValueError(
                "cannot initialize PhoenixdWallet: missing phoenixd_api_password"
            )

        self.endpoint = normalize_endpoint(settings.phoenixd_api_endpoint)
        parsed_url = urllib.parse.urlparse(settings.phoenixd_api_endpoint)

        if parsed_url.scheme == "http":
            ws_protocol = "ws"
        elif parsed_url.scheme == "https":
            ws_protocol = "wss"
        else:
            raise ValueError(f"Unsupported scheme: {parsed_url.scheme}")

        self.ws_url = (
            f"{ws_protocol}://{urllib.parse.urlsplit(self.endpoint).netloc}/websocket"
        )
        password = settings.phoenixd_api_password
        encoded_auth = base64.b64encode(f":{password}".encode())
        auth = str(encoded_auth, "utf-8")
        self.headers = {
            "Authorization": f"Basic {auth}",
            "User-Agent": settings.user_agent,
        }

        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.headers)

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.get("/getinfo", timeout=10)
            r.raise_for_status()
            data = r.json()

            if len(data) == 0:
                return StatusResponse("no data", 0)

            if r.is_error or "channels" not in data:
                error_message = data["message"] if "message" in data else r.text
                return StatusResponse(f"Server error: '{error_message}'", 0)

            if len(data["channels"]) == 0:
                # todo: add custom unit-test for this
                return StatusResponse(None, 0)

            balance_msat = int(data["channels"][0]["balanceSat"]) * 1000
            return StatusResponse(None, balance_msat)
        except json.JSONDecodeError:
            return StatusResponse("Server error: 'invalid json response'", 0)
        except Exception as exc:
            logger.warning(exc)
            return StatusResponse(f"Unable to connect to {self.endpoint}.", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:

        try:
            msats_amount = amount
            data: dict[str, Any] = {
                "amountSat": f"{msats_amount}",
                "externalId": "",
            }

            # Either 'description' (string) or 'descriptionHash' must be supplied
            # PhoenixD description limited to 128 characters
            if description_hash:
                data["descriptionHash"] = description_hash.hex()
            else:
                desc = memo
                if desc is None and unhashed_description:
                    desc = unhashed_description.decode()
                desc = desc or ""
                if len(desc) > 128:
                    data["descriptionHash"] = hashlib.sha256(desc.encode()).hexdigest()
                else:
                    data["description"] = desc

            # if expiry is not set, it defaults to 3600 seconds (1 hour)
            data["expirySeconds"] = int(kwargs.get("expiry", 3600))

            r = await self.client.post(
                "/createinvoice",
                data=data,
                timeout=40,
            )
            r.raise_for_status()
            data = r.json()

            if r.is_error or "paymentHash" not in data:
                error_message = data["message"]
                return InvoiceResponse(
                    ok=False, error_message=f"Server error: '{error_message}'"
                )

            checking_id = data["paymentHash"]
            payment_request = data["serialized"]
            preimage = data.get("paymentPreimage", None)  # if available
            return InvoiceResponse(
                ok=True,
                checking_id=checking_id,
                payment_request=payment_request,
                preimage=preimage,
            )
        except json.JSONDecodeError:
            return InvoiceResponse(
                ok=False, error_message="Server error: 'invalid json response'"
            )
        except KeyError as exc:
            logger.warning(exc)
            return InvoiceResponse(
                ok=False, error_message="Server error: 'missing required fields'"
            )
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(
                ok=False, error_message=f"Unable to connect to {self.endpoint}."
            )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            r = await self.client.post(
                "/payinvoice",
                data={
                    "invoice": bolt11,
                },
                timeout=40,
            )

            r.raise_for_status()

        except TimeoutException:
            # be safe and return pending on timeouts
            msg = f"Timeout connecting to {self.endpoint}. keep pending..."
            logger.warning(msg)
            return PaymentResponse(ok=None, error_message=msg)
        except RequestError as exc:
            # RequestError is raised when the request never hit the destination server
            msg = f"Unable to connect to {self.endpoint}."
            logger.warning(msg)
            logger.warning(exc)
            return PaymentResponse(ok=False, error_message=msg)
        except Exception as exc:
            logger.warning(exc)
            return PaymentResponse(
                ok=None, error_message=f"Unable to connect to {self.endpoint}."
            )

        try:
            data = r.json()

            if "routingFeeSat" not in data and ("reason" in data or "message" in data):
                error_message = data.get("reason", data.get("message", "Unknown error"))
                return PaymentResponse(error_message=error_message)

            checking_id = data["paymentHash"]
            fee_msat = -int(data["routingFeeSat"]) * 1000
            preimage = data["paymentPreimage"]
            return PaymentResponse(
                ok=True,
                checking_id=checking_id,
                fee_msat=fee_msat,
                preimage=preimage,
            )

        except json.JSONDecodeError:
            return PaymentResponse(
                error_message="Server error: 'invalid json response'"
            )
        except KeyError:
            return PaymentResponse(
                error_message="Server error: 'missing required fields'"
            )
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11}")
            logger.warning(exc)
            return PaymentResponse(
                error_message=f"Unable to connect to {self.endpoint}."
            )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(
            f"/payments/incoming/{checking_id}?all=true&limit=1000"
        )
        if r.is_error:
            if r.status_code == 404:
                # invoice does not exist in phoenixd, so it was never paid
                return PaymentFailedStatus()
            else:
                # otherwise something unexpected happened, and we keep it pending
                logger.warning(
                    f"Error getting invoice status: {r.text}, keeping pending"
                )
                return PaymentPendingStatus()
        try:
            data = r.json()
        except json.JSONDecodeError:
            # should never return invalid json, but just in case we keep it pending
            logger.warning(
                f"Phoenixd: invalid json response: {r.text}, keeping pending"
            )
            return PaymentPendingStatus()

        if "isPaid" not in data or "fees" not in data or "preimage" not in data:
            # should never return missing fields, but just in case we keep it pending
            return PaymentPendingStatus()

        if data["isPaid"] is True:
            fee_msat = data["fees"]
            preimage = data["preimage"]
            return PaymentSuccessStatus(fee_msat=fee_msat, preimage=preimage)

        return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(
            f"/payments/outgoing/{checking_id}?all=true&limit=1000"
        )
        if r.is_error:
            if r.status_code == 404:
                # payment does not exist in phoenixd, so it was never paid
                return PaymentFailedStatus()
            else:
                # otherwise something unexpected happened, and we keep it pending
                logger.warning(
                    f"Error getting payment status: {r.text}, keeping pending"
                )
                return PaymentPendingStatus()
        try:
            data = r.json()
        except json.JSONDecodeError:
            # should never return invalid json, but just in case we keep it pending
            logger.warning(
                f"Phoenixd: invalid json response: {r.text}, keeping pending"
            )
            return PaymentPendingStatus()

        if "isPaid" not in data or "fees" not in data or "preimage" not in data:
            # should never happen, but just in case we keep it pending
            logger.warning(
                f"Phoenixd: missing required fields: {data}, keeping pending"
            )
            return PaymentPendingStatus()

        if data["isPaid"] is True:
            fee_msat = data["fees"]
            preimage = data["preimage"]
            return PaymentSuccessStatus(fee_msat=fee_msat, preimage=preimage)
        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            try:
                async with connect(
                    self.ws_url,
                    extra_headers=[("Authorization", self.headers["Authorization"])],
                ) as ws:
                    logger.info("connected to phoenixd invoices stream")
                    while settings.lnbits_running:
                        message = await ws.recv()
                        message_json = json.loads(message)
                        if (
                            message_json
                            and message_json.get("type") == "payment_received"
                        ):
                            logger.info(
                                f'payment-received: {message_json["paymentHash"]}'
                            )
                            yield message_json["paymentHash"]

            except Exception as exc:
                logger.warning(
                    f"lost connection to phoenixd invoices stream: '{exc}'"
                    "retrying in 5 seconds"
                )
                await asyncio.sleep(5)
