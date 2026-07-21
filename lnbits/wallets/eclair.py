import asyncio
import base64
import hashlib
import json
import urllib.parse
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import httpx
from loguru import logger
from websockets import connect

from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings
from lnbits.utils.crypto import random_secret_and_hash

from .base import (
    Feature,
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class EclairError(Exception):
    pass


class UnknownError(Exception):
    pass


class EclairWallet(Wallet):
    features = [Feature.bolt12]

    def __init__(self):
        if not settings.eclair_url:
            raise ValueError("cannot initialize EclairWallet: missing eclair_url")
        if not settings.eclair_pass:
            raise ValueError("cannot initialize EclairWallet: missing eclair_pass")

        self.url = normalize_endpoint(settings.eclair_url)
        self.ws_url = f"ws://{urllib.parse.urlsplit(self.url).netloc}/ws"

        password = settings.eclair_pass
        encoded_auth = base64.b64encode(f":{password}".encode())
        auth = str(encoded_auth, "utf-8")
        self.headers = {
            "Authorization": f"Basic {auth}",
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.url, headers=self.headers)

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.post("/globalbalance", timeout=5)
            r.raise_for_status()

            data = r.json()

            if len(data) == 0:
                return StatusResponse("no data", 0)

            if "error" in data:
                return StatusResponse(f"""Server error: '{data["error"]}'""", 0)

            if r.is_error or "total" not in data:
                return StatusResponse(f"Server error: '{r.text}'", 0)
            total = round(Decimal(data.get("total")), 8) * 100_000_000_000
            return StatusResponse(balance_msat=int(total), error_message=None)
        except json.JSONDecodeError:
            return StatusResponse("Server error: 'invalid json response'", 0)
        except Exception as exc:
            logger.warning(exc)
            return StatusResponse(f"Unable to connect to {self.url}.", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        data: dict[str, Any] = {
            "amountMsat": amount * 1000,
        }
        if kwargs.get("expiry"):
            data["expireIn"] = kwargs["expiry"]

        # Either 'description' (string) or 'descriptionHash' must be supplied
        if description_hash:
            data["descriptionHash"] = description_hash.hex()
        elif unhashed_description:
            data["descriptionHash"] = hashlib.sha256(unhashed_description).hexdigest()
        else:
            data["description"] = memo

        preimage, _ = random_secret_and_hash()
        data["paymentPreimage"] = preimage

        try:
            r = await self.client.post("/createinvoice", data=data, timeout=40)
            r.raise_for_status()
            data = r.json()

            if len(data) == 0:
                return InvoiceResponse(ok=False, error_message="no data")

            if "error" in data:
                return InvoiceResponse(
                    ok=False, error_message=f"""Server error: '{data["error"]}'"""
                )

            if r.is_error:
                return InvoiceResponse(
                    ok=False, error_message=f"Server error: '{r.text}'"
                )
            return InvoiceResponse(
                ok=True,
                checking_id=data["paymentHash"],
                payment_request=data["serialized"],
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
                ok=False, error_message=f"Unable to connect to {self.url}."
            )

    async def pay_offer(
        self,
        offer: str,
        fee_limit_msat: int,
        amount_msat: int | None = None,
    ) -> PaymentResponse:
        """Pay a BOLT12 offer via Eclair payoffer."""
        try:
            body: dict = {"offer": offer, "blocking": True}
            if amount_msat is not None and amount_msat > 0:
                body["amountMsat"] = str(amount_msat)
            if fee_limit_msat > 0:
                body["maxFeeMsat"] = str(fee_limit_msat)
            r = await self.client.post(
                "/payoffer",
                data=body,
                timeout=None,
            )
            r.raise_for_status()
            data = r.json()

            if "error" in data:
                return PaymentResponse(error_message=str(data["error"]))
            if r.is_error:
                return PaymentResponse(error_message=r.text)

            if data.get("type") == "payment-failed":
                return PaymentResponse(ok=False, error_message="payment failed")

            checking_id = data.get("paymentHash") or data.get("payment_hash")
            preimage = data.get("paymentPreimage") or data.get("payment_preimage")
            if not checking_id:
                return PaymentResponse(
                    error_message="Server error: 'missing paymentHash'"
                )

            payment_status: PaymentStatus = await self.get_payment_status(checking_id)
            success = True if payment_status.success else None
            # Prefer amount from getsentinfo (recipientAmount/amount in msat).
            resolved_msat = await self._sent_amount_msat(checking_id)
            if resolved_msat is None:
                for key in ("recipientAmount", "amount", "amountMsat", "amount_msat"):
                    if key in data and data[key] is not None:
                        resolved_msat = self._parse_msat(data[key])
                        if resolved_msat is not None:
                            break
            return PaymentResponse(
                ok=success,
                checking_id=checking_id,
                fee_msat=payment_status.fee_msat,
                preimage=preimage,
                amount_msat=resolved_msat,
            )
        except json.JSONDecodeError:
            return PaymentResponse(
                error_message="Server error: 'invalid json response'"
            )
        except Exception as exc:
            logger.info(f"Failed to pay offer {offer[:24]}...")
            logger.warning(exc)
            return PaymentResponse(error_message=f"Unable to connect to {self.url}.")

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            r = await self.client.post(
                "/payinvoice",
                data={"invoice": bolt11, "blocking": True},
                timeout=None,
            )
            r.raise_for_status()
            data = r.json()

            if "error" in data:
                return PaymentResponse(error_message=data["error"])
            if r.is_error:
                return PaymentResponse(error_message=r.text)

            if data["type"] == "payment-failed":
                return PaymentResponse(ok=False, error_message="payment failed")

            checking_id = data["paymentHash"]
            preimage = data["paymentPreimage"]

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
            return PaymentResponse(error_message=f"Unable to connect to {self.url}.")

        payment_status: PaymentStatus = await self.get_payment_status(checking_id)
        success = True if payment_status.success else None
        return PaymentResponse(
            ok=success,
            checking_id=checking_id,
            fee_msat=payment_status.fee_msat,
            preimage=preimage,
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self.client.post(
                "/getreceivedinfo",
                data={"paymentHash": checking_id},
            )

            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or data.get("status") is None:
                raise Exception("error in eclair response")

            statuses = {
                "received": True,
                "expired": False,
                "pending": None,
            }
            return PaymentStatus(statuses.get(data["status"]["type"]))
        except Exception:
            return PaymentPendingStatus()

    @staticmethod
    def _parse_msat(value) -> int | None:
        """Parse Eclair amount fields (int, or strings like '1000 msat' / '1 sat')."""
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip().lower().replace("_", "")
        try:
            if text.endswith("msat"):
                return int(float(text[: -len("msat")].strip()))
            if text.endswith("sat"):
                return int(float(text[: -len("sat")].strip()) * 1000)
            return int(float(text))
        except (TypeError, ValueError):
            return None

    async def _sent_amount_msat(self, checking_id: str) -> int | None:
        """Read paid amount (msat) from Eclair getsentinfo, if present."""
        try:
            r = await self.client.post(
                "/getsentinfo",
                data={"paymentHash": checking_id},
                timeout=40,
            )
            r.raise_for_status()
            data = r.json()[-1]
            for key in ("recipientAmount", "amount", "amountMsat", "amount_msat"):
                if key in data and data[key] is not None:
                    parsed = self._parse_msat(data[key])
                    if parsed is not None:
                        return parsed
        except Exception:
            return None
        return None

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self.client.post(
                "/getsentinfo",
                data={"paymentHash": checking_id},
                timeout=40,
            )

            r.raise_for_status()

            data = r.json()[-1]

            if r.is_error or "error" in data or data.get("status") is None:
                raise Exception("error in eclair response")

            fee_msat, preimage = None, None
            if data["status"]["type"] == "sent":
                fee_msat = -data["status"]["feesPaid"]
                preimage = data["status"]["paymentPreimage"]

            statuses = {
                "sent": True,
                "failed": False,
                "pending": None,
            }
            return PaymentStatus(
                statuses.get(data["status"]["type"]), fee_msat, preimage
            )
        except Exception:
            return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            try:
                async with connect(
                    self.ws_url,
                    additional_headers=[
                        ("Authorization", self.headers["Authorization"])
                    ],
                ) as ws:
                    while settings.lnbits_running:
                        message = await ws.recv()
                        message_json = json.loads(message)

                        if message_json and message_json["type"] == "payment-received":
                            yield message_json["paymentHash"]

            except Exception as exc:
                logger.error(
                    f"lost connection to eclair invoices stream: '{exc}'"
                    "retrying in 5 seconds"
                )
                await asyncio.sleep(5)
