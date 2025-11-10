import asyncio
import base64
import hashlib
import json
from collections.abc import AsyncGenerator

import httpx
from loguru import logger

from lnbits.helpers import normalize_endpoint
from lnbits.nodes.lndrest import LndRestNode
from lnbits.settings import settings
from lnbits.utils.crypto import random_secret_and_hash

from .base import (
    Feature,
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)
from .macaroon import load_macaroon


class LndRestWallet(Wallet):
    """https://api.lightning.community/#lnd-rest-api-reference"""

    __node_cls__ = LndRestNode
    features = [Feature.nodemanager, Feature.holdinvoice]

    def __init__(self):
        if not settings.lnd_rest_endpoint:
            raise ValueError(
                "cannot initialize LndRestWallet: missing lnd_rest_endpoint"
            )

        if not settings.lnd_rest_cert:
            logger.warning(
                "No certificate for LndRestWallet provided! "
                "This only works if you have a publicly issued certificate."
            )

        self.endpoint = normalize_endpoint(settings.lnd_rest_endpoint)

        # if no cert provided it should be public so we set verify to True
        # and it will still check for validity of certificate and fail if its not valid
        # even on startup
        cert = settings.lnd_rest_cert or True

        macaroon = (
            settings.lnd_rest_macaroon
            or settings.lnd_admin_macaroon
            or settings.lnd_rest_admin_macaroon
            or settings.lnd_invoice_macaroon
            or settings.lnd_rest_invoice_macaroon
        )
        encrypted_macaroon = settings.lnd_rest_macaroon_encrypted
        try:
            macaroon = load_macaroon(macaroon, encrypted_macaroon)
        except ValueError as exc:
            raise ValueError(
                f"cannot load macaroon for LndRestWallet: {exc!s}"
            ) from exc

        headers = {
            "Grpc-Metadata-macaroon": macaroon,
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(
            base_url=self.endpoint, headers=headers, verify=cert
        )

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            r = await self.client.get("/v1/balance/channels")
            r.raise_for_status()

            data = r.json()
            if len(data) == 0:
                return StatusResponse("no data", 0)
            if r.is_error or "balance" not in data:
                return StatusResponse(f"Server error: '{r.text}'", 0)

        except json.JSONDecodeError:
            return StatusResponse("Server error: 'invalid json response'", 0)
        except Exception as exc:
            logger.warning(exc)
            return StatusResponse(f"Unable to connect to {self.endpoint}.", 0)

        return StatusResponse(None, int(data["balance"]) * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        _data: dict = {
            "value": amount,
            "private": settings.lnd_rest_route_hints,
            "memo": memo or "",
        }
        if kwargs.get("expiry"):
            _data["expiry"] = kwargs["expiry"]
        if description_hash:
            _data["description_hash"] = base64.b64encode(description_hash).decode(
                "ascii"
            )
        elif unhashed_description:
            _data["description_hash"] = base64.b64encode(
                hashlib.sha256(unhashed_description).digest()
            ).decode("ascii")

        preimage, _payment_hash = random_secret_and_hash()
        _data["r_hash"] = base64.b64encode(bytes.fromhex(_payment_hash)).decode()
        _data["r_preimage"] = base64.b64encode(bytes.fromhex(preimage)).decode()

        try:
            r = await self.client.post(url="/v1/invoices", json=_data)
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

            if "payment_request" not in data or "r_hash" not in data:
                return InvoiceResponse(
                    ok=False, error_message="Server error: 'missing required fields'"
                )

            payment_request = data["payment_request"]
            payment_hash = base64.b64decode(data["r_hash"]).hex()
            checking_id = payment_hash
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
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(
                ok=False, error_message=f"Unable to connect to {self.endpoint}."
            )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        req = {
            "payment_request": bolt11,
            "fee_limit_msat": fee_limit_msat,
            "timeout_seconds": 30,
            "no_inflight_updates": True,
        }
        if settings.lnd_rest_allow_self_payment:
            req["allow_self_payment"] = 1

        try:
            r = await self.client.post(
                url="/v2/router/send",
                json=req,
                timeout=None,
            )
            r.raise_for_status()
            data = r.json()
        except json.JSONDecodeError:
            return PaymentResponse(
                error_message="Server error: 'invalid json response'"
            )
        except Exception as exc:
            logger.warning(f"LndRestWallet pay_invoice POST error: {exc}.")
            return PaymentResponse(
                error_message=f"Unable to connect to {self.endpoint}."
            )

        payment_error = data.get("payment_error")
        if payment_error:
            logger.warning(f"LndRestWallet payment_error: {payment_error}.")
            return PaymentResponse(ok=False, error_message=payment_error)

        try:
            payment = data["result"]
            status = payment["status"]
            checking_id = payment["payment_hash"]
            preimage = payment["payment_preimage"]
            fee_msat = abs(int(payment["fee_msat"]))
        except KeyError as exc:
            logger.warning(exc)
            return PaymentResponse(
                error_message="Server error: 'missing required fields'"
            )

        if status == "SUCCEEDED":
            return PaymentResponse(
                ok=True, checking_id=checking_id, fee_msat=fee_msat, preimage=preimage
            )
        elif status == "FAILED":
            reason = payment.get("failure_reason", "unknown reason")
            return PaymentResponse(
                ok=False, checking_id=checking_id, error_message=reason
            )
        elif status == "IN_FLIGHT":
            return PaymentResponse(ok=None, checking_id=checking_id)
        return PaymentResponse(
            ok=False,
            checking_id=checking_id,
            error_message="Server error: 'unknown payment status returned'",
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(url=f"/v1/invoice/{checking_id}")

        try:
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning(f"Error getting invoice status: {e}")
            return PaymentPendingStatus()

        if r.is_error or data.get("settled") is None:
            # this must also work when checking_id is not a hex recognizable by lnd
            # it will return an error and no "settled" attribute on the object
            return PaymentPendingStatus()

        if data.get("settled") is True:
            return PaymentSuccessStatus()

        if data.get("state") == "CANCELED":
            return PaymentFailedStatus()

        return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        """
        This routine checks the payment status using routerpc.TrackPaymentV2.
        """
        try:
            checking_id = base64.urlsafe_b64encode(bytes.fromhex(checking_id)).decode(
                "ascii"
            )
        except ValueError:
            return PaymentPendingStatus()

        url = f"/v2/router/track/{checking_id}"
        async with self.client.stream("GET", url, timeout=None) as r:
            async for json_line in r.aiter_lines():
                try:
                    line = json.loads(json_line)
                    error = line.get("error")
                    if error:
                        logger.warning(
                            error["message"] if "message" in error else error
                        )
                        return PaymentPendingStatus()
                except Exception as exc:
                    logger.warning("Invalid JSON line in payment status stream:", exc)
                    return PaymentPendingStatus()

                payment = line.get("result")
                if not payment:
                    logger.warning(f"No payment info found for: {checking_id}")
                    continue

                status = payment.get("status")
                if status == "SUCCEEDED":
                    return PaymentSuccessStatus(
                        fee_msat=abs(int(payment.get("fee_msat", 0))),
                        preimage=payment.get("payment_preimage"),
                    )
                elif status == "FAILED":
                    reason = payment.get("failure_reason", "unknown reason")
                    logger.info(f"LNDRest Payment failed: {reason}")
                    return PaymentFailedStatus()
                elif status == "IN_FLIGHT":
                    logger.info(f"LNDRest Payment in flight: {checking_id}")
                    return PaymentPendingStatus()

        logger.info(f"LNDRest Payment non-existent: {checking_id}")
        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            try:
                url = "/v1/invoices/subscribe"
                async with self.client.stream("GET", url, timeout=None) as r:
                    async for line in r.aiter_lines():
                        try:
                            inv = json.loads(line)["result"]
                            if not inv["settled"]:
                                continue
                        except Exception as exc:
                            logger.debug(exc)
                            continue

                        payment_hash = base64.b64decode(inv["r_hash"]).hex()
                        yield payment_hash
            except Exception as exc:
                logger.warning(
                    f"lost connection to lnd invoices stream: '{exc}', retrying in 5"
                    " seconds"
                )
                await asyncio.sleep(5)

    async def create_hold_invoice(
        self,
        amount: int,
        payment_hash: str,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        data: dict = {
            "value": amount,
            "private": True,
            "hash": base64.b64encode(bytes.fromhex(payment_hash)).decode("ascii"),
        }
        if description_hash:
            data["description_hash"] = base64.b64encode(description_hash).decode(
                "ascii"
            )
        elif unhashed_description:
            data["description_hash"] = base64.b64encode(
                hashlib.sha256(unhashed_description).digest()
            ).decode("ascii")
        else:
            data["memo"] = memo or ""

        try:
            r = await self.client.post(url="/v2/invoices/hodl", json=data)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=exc.response.text)
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=str(exc))

        payment_request = data["payment_request"]
        payment_hash = base64.b64encode(bytes.fromhex(payment_hash)).decode("ascii")

        return InvoiceResponse(
            ok=True, checking_id=payment_hash, payment_request=payment_request
        )

    async def settle_hold_invoice(self, preimage: str) -> InvoiceResponse:
        data: dict = {
            "preimage": base64.b64encode(bytes.fromhex(preimage)).decode("ascii")
        }
        try:
            r = await self.client.post(url="/v2/invoices/settle", json=data)
            r.raise_for_status()
            return InvoiceResponse(ok=True, preimage=preimage)
        except httpx.HTTPStatusError as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=exc.response.text)
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=str(exc))

    async def cancel_hold_invoice(self, payment_hash: str) -> InvoiceResponse:
        rhash = bytes.fromhex(payment_hash)
        try:
            r = await self.client.post(
                url="/v2/invoices/cancel",
                json={"payment_hash": base64.b64encode(rhash).decode("ascii")},
            )
            r.raise_for_status()
            logger.debug(f"Cancel hold invoice response: {r.text}")
            return InvoiceResponse(ok=True, checking_id=payment_hash)
        except httpx.HTTPStatusError as exc:
            return InvoiceResponse(ok=False, error_message=exc.response.text)
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=str(exc))
