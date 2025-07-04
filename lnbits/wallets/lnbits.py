import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Optional

import httpx
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


class LNbitsWallet(Wallet):
    """https://github.com/lnbits/lnbits"""

    def __init__(self):
        if not settings.lnbits_endpoint:
            raise ValueError("cannot initialize LNbitsWallet: missing lnbits_endpoint")
        key = (
            settings.lnbits_key
            or settings.lnbits_admin_key
            or settings.lnbits_invoice_key
        )
        if not key:
            raise ValueError(
                "cannot initialize LNbitsWallet: "
                "missing lnbits_key or lnbits_admin_key or lnbits_invoice_key"
            )
        self.endpoint = normalize_endpoint(settings.lnbits_endpoint)
        self.ws_url = f"{self.endpoint.replace('http', 'ws', 1)}/api/v1/ws/{key}"
        self.headers = {"X-Api-Key": key, "User-Agent": settings.user_agent}
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.headers)

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.get(url="/api/v1/wallet", timeout=15)
            r.raise_for_status()
            data = r.json()

            if len(data) == 0:
                return StatusResponse("no data", 0)

            if r.is_error or "balance" not in data:
                return StatusResponse(f"Server error: '{r.text}'", 0)

            return StatusResponse(None, data["balance"])
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
        data: dict = {"out": False, "amount": amount, "memo": memo or ""}
        if kwargs.get("expiry"):
            data["expiry"] = kwargs["expiry"]
        if description_hash:
            data["description_hash"] = description_hash.hex()
        if unhashed_description:
            data["unhashed_description"] = unhashed_description.hex()

        try:
            r = await self.client.post(url="/api/v1/payments", json=data)
            r.raise_for_status()
            data = r.json()

            # Backwards compatibility for pre-v1 which used the key "payment_request"
            payment_str = data.get("bolt11") or data.get("payment_request")
            if r.is_error or not payment_str:
                error_message = data["detail"] if "detail" in data else r.text
                return InvoiceResponse(
                    ok=False, error_message=f"Server error: '{error_message}'"
                )

            return InvoiceResponse(
                ok=True,
                checking_id=data["checking_id"],
                payment_request=payment_str,
                preimage=data.get("preimage"),
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
                url="/api/v1/payments",
                json={"out": True, "bolt11": bolt11},
                timeout=None,
            )

            r.raise_for_status()
            data = r.json()

            checking_id = data["payment_hash"]

            # we do this to get the fee and preimage
            payment: PaymentStatus = await self.get_payment_status(checking_id)

            success = True if payment.success else None
            return PaymentResponse(
                ok=success,
                checking_id=checking_id,
                fee_msat=payment.fee_msat,
                preimage=payment.preimage,
            )

        except httpx.HTTPStatusError as exc:
            try:
                logger.debug(exc)
                data = exc.response.json()
                error_message = f"Payment {data['status']}: {data['detail']}."
                if data["status"] == "failed":
                    return PaymentResponse(ok=False, error_message=error_message)
                return PaymentResponse(error_message=error_message)
            except Exception as exc:
                error_message = f"Unable to connect to {self.endpoint}."
                return PaymentResponse(error_message=error_message)

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
        try:
            r = await self.client.get(
                url=f"/api/v1/payments/{checking_id}",
            )
            r.raise_for_status()

            data = r.json()

            if data.get("paid", False) is True:
                return PaymentSuccessStatus()
            return PaymentPendingStatus()
        except Exception:
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self.client.get(url=f"/api/v1/payments/{checking_id}")

            if r.is_error:
                return PaymentPendingStatus()
            data = r.json()

            if data.get("status") == "failed":
                return PaymentFailedStatus()

            if "paid" not in data or not data["paid"]:
                return PaymentPendingStatus()

            if "details" not in data:
                return PaymentPendingStatus()

            return PaymentSuccessStatus(
                fee_msat=data["details"]["fee"], preimage=data["preimage"]
            )
        except Exception:
            return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            try:
                async with connect(self.ws_url) as ws:
                    logger.info("connected to LNbits fundingsource websocket.")
                    while settings.lnbits_running:
                        message = await ws.recv()
                        message_dict = json.loads(message)
                        if (
                            message_dict
                            and message_dict.get("payment")
                            and message_dict["payment"].get("payment_hash")
                        ):
                            payment_hash = message_dict["payment"]["payment_hash"]
                            logger.info(f"payment-received: {payment_hash}")
                            yield payment_hash
            except Exception as exc:
                logger.error(
                    f"lost connection to LNbits fundingsource websocket: '{exc}'"
                    "retrying in 5 seconds"
                )
                await asyncio.sleep(5)
