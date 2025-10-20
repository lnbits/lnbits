import asyncio
import base64
import json
import os
import ssl
import uuid
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

import httpx
from bolt11 import Bolt11Exception
from bolt11.decode import decode
from loguru import logger

from lnbits.exceptions import UnsupportedError
from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings
from lnbits.utils.crypto import random_secret_and_hash

from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)


class CLNRestWallet(Wallet):
    def __init__(self):
        if not settings.clnrest_url:
            raise ValueError("Cannot initialize CLNRestWallet: missing CLNREST_URL")

        if not settings.clnrest_readonly_rune:
            raise ValueError(
                "cannot initialize CLNRestWallet: " "missing clnrest_readonly_rune"
            )

        self.url = normalize_endpoint(settings.clnrest_url)

        if not settings.clnrest_nodeid:
            logger.info("missing CLNREST_NODEID, but this is only needed for v23.08")

        self.base_headers = {
            "accept": "application/json",
            "User-Agent": settings.user_agent,
            "Content-Type": "application/json",
        }

        if settings.clnrest_nodeid is not None:
            self.base_headers["nodeid"] = settings.clnrest_nodeid

        # Ensure the readonly rune is set
        if settings.clnrest_readonly_rune is not None:
            self.readonly_headers = {
                **self.base_headers,
                "rune": settings.clnrest_readonly_rune,
            }
        else:
            logger.warning(
                "Readonly rune 'CLNREST_READONLY_RUNE' is required but not set."
            )

        if settings.clnrest_invoice_rune is not None:
            self.invoice_headers = {
                **self.base_headers,
                "rune": settings.clnrest_invoice_rune,
            }
        else:
            logger.warning(
                "Will be unable to create any invoices without "
                "setting 'CLNREST_INVOICE_RUNE[:4]'"
            )

        if settings.clnrest_pay_rune is not None:
            self.pay_headers = {**self.base_headers, "rune": settings.clnrest_pay_rune}
        else:
            logger.warning(
                "Will be unable to call pay endpoint without setting 'CLNREST_PAY_RUNE'"
            )

        if settings.clnrest_renepay_rune is not None:
            self.renepay_headers = {
                **self.base_headers,
                "rune": settings.clnrest_renepay_rune,
            }
        else:
            logger.warning(
                "Will be unable to call renepay endpoint without "
                "setting 'CLNREST_RENEPAY_RUNE'"
            )

        # https://docs.corelightning.org/reference/lightning-pay
        # -32602: Invalid bolt11: Prefix bc is not for regtest
        # -1: Catchall nonspecific error.
        ## 201: Already paid
        # 203: Permanent failure at destination.
        # 205: Unable to find a route.
        # 206: Route too expensive.
        # 207: Invoice expired.
        # 210: Payment timed out without a payment in progress.
        # 401: Unauthorized. Probably a rune issue

        self.pay_failure_error_codes = [-32602, 203, 205, 206, 207, 210, 401]
        self.client = self._create_client()
        self.last_pay_index = settings.clnrest_last_pay_index
        self.statuses = {
            "paid": True,
            "complete": True,
            "failed": False,
            "pending": None,
        }

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as exc:
            logger.warning(f"Error closing wallet connection: {exc}")

    async def status(self) -> StatusResponse:
        try:
            logger.debug("REQUEST to /v1/listfunds")

            r = await self.client.post(
                "/v1/listfunds", timeout=15, headers=self.readonly_headers
            )
            r.raise_for_status()

            response_data = r.json()

            if not response_data:
                logger.warning("Received empty response data")
                return StatusResponse("no data", 0)

            channels = response_data.get("channels", [])
            total_our_amount_msat = sum(
                channel.get("our_amount_msat", 0) for channel in channels
            )

            return StatusResponse(None, total_our_amount_msat)

        except json.JSONDecodeError as exc:
            logger.warning(f"JSON decode error: {exc!s}")
            return StatusResponse(f"Failed to decode JSON response from {self.url}", 0)

        except httpx.ReadTimeout:
            logger.warning(
                "Timeout error: The server did not respond in time. This can happen if "
                "the server is running HTTPS but the client is using HTTP."
            )
            return StatusResponse(
                "Unable to connect to 'v1/listfunds' due to timeout", 0
            )

        except (httpx.ConnectError, httpx.RequestError) as exc:
            logger.warning(f"Connection error: {exc}")
            return StatusResponse("Unable to connect to 'v1/listfunds'", 0)

        except httpx.HTTPStatusError as exc:
            logger.warning(
                f"HTTP error: {exc.response.status_code} {exc.response.reason_phrase} "
                f"while accessing {exc.request.url}"
            )
            return StatusResponse(
                f"Failed with HTTP {exc.response.status_code} on 'v1/listfunds'", 0
            )
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

        if not settings.clnrest_invoice_rune:
            return InvoiceResponse(
                ok=False, error_message="Unable to invoice without an invoice rune"
            )

        data: dict = {
            "amount_msat": int(amount * 1000),
            "description": memo,
            "label": _generate_label(),
        }

        if description_hash and not unhashed_description:
            raise UnsupportedError(
                "'description_hash' unsupported by CoreLightningRest, "
                "provide 'unhashed_description'"
            )

        if unhashed_description:
            data["description"] = unhashed_description.decode()

        if kwargs.get("expiry"):
            data["expiry"] = kwargs["expiry"]

        if kwargs.get("preimage"):
            data["preimage"] = kwargs["preimage"]
        else:
            preimage, _ = random_secret_and_hash()
            data["preimage"] = preimage

        try:
            r = await self.client.post(
                "/v1/invoice",
                json=data,
                headers=self.invoice_headers,
            )
            r.raise_for_status()
            response_data = r.json()

            if "error" in response_data:
                error_message = response_data["error"]
                logger.debug(f"Error creating invoice: {error_message}")
                return InvoiceResponse(ok=False, error_message=error_message)

            if "payment_hash" not in response_data or "bolt11" not in response_data:
                return InvoiceResponse(
                    ok=False, error_message="Server error: 'missing required fields'"
                )
            return InvoiceResponse(
                ok=True,
                checking_id=response_data["payment_hash"],
                payment_request=response_data["bolt11"],
                preimage=data["preimage"],
            )

        except json.JSONDecodeError as exc:
            logger.warning(exc)
            return InvoiceResponse(
                ok=False, error_message="Server error: 'invalid json response'"
            )
        except Exception as exc:
            logger.warning(f"Unable to connect to {self.url}: {exc}")
            return InvoiceResponse(
                ok=False, error_message=f"Unable to connect to {self.url}."
            )

    async def pay_invoice(
        self,
        bolt11: str,
        fee_limit_msat: int,
        **_,
    ) -> PaymentResponse:

        try:
            invoice = decode(bolt11)
        except Bolt11Exception as exc:
            return PaymentResponse(ok=False, error_message=str(exc))

        if not invoice.amount_msat or invoice.amount_msat <= 0:
            return PaymentResponse(
                ok=False, error_message="0 amount invoices are not allowed"
            )

        if not settings.clnrest_pay_rune and not settings.clnrest_renepay_rune:
            return PaymentResponse(
                ok=False,
                error_message="Unable to pay invoice without a pay or renepay rune",
            )

        data = {
            "label": _generate_label(),
            "description": invoice.description,
            "maxfee": fee_limit_msat,
        }

        if settings.clnrest_renepay_rune:
            endpoint = "/v1/renepay"
            headers = self.renepay_headers
            data["invstring"] = bolt11
        else:
            endpoint = "/v1/pay"
            headers = self.pay_headers
            data["bolt11"] = bolt11

        try:
            r = await self.client.post(
                endpoint,
                json=data,
                headers=headers,
                timeout=None,
            )

            r.raise_for_status()
            data = r.json()

            if "payment_preimage" not in data:
                error_message = data.get("error", "No payment preimage in response")
                logger.warning(error_message)
                return PaymentResponse(error_message=error_message)

            return PaymentResponse(
                ok=self.statuses.get(data["status"]),
                checking_id=data["payment_hash"],
                fee_msat=data["amount_sent_msat"] - data["amount_msat"],
                preimage=data["payment_preimage"],
            )
        except httpx.HTTPStatusError as exc:
            try:
                data = exc.response.json()
                error = data.get("error", {})
                error_code = int(error.get("code", 0))
                error_message = error.get("message", "Unknown error")
                if error_code in self.pay_failure_error_codes:
                    return PaymentResponse(ok=False, error_message=error_message)
                else:
                    return PaymentResponse(error_message=error_message)
            except Exception:
                error_message = f"Error parsing response from {self.url}: {exc!s}"
                logger.warning(error_message)
                return PaymentResponse(error_message=error_message)
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11}")
            logger.warning(exc)
            error_message = f"Unable to connect to {self.url}."
            return PaymentResponse(error_message=error_message)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        data: dict = {"payment_hash": checking_id}

        try:
            r = await self.client.post(
                "/v1/listinvoices",
                json=data,
                headers=self.readonly_headers,
            )
            r.raise_for_status()
            data = r.json()
            if r.is_error or "error" in data or data.get("invoices") is None:
                logger.warning(f"error in cln response '{checking_id}'")
                return PaymentPendingStatus()
            status = self.statuses.get(data["invoices"][0]["status"])
            fee_msat = data["invoices"][0].get("amount_received_msat", 0) - data[
                "invoices"
            ][0].get("amount_msat", 0)
            return PaymentStatus(
                paid=status,
                preimage=data["invoices"][0].get("preimage"),
                fee_msat=fee_msat,
            )
        except Exception as exc:
            logger.warning(f"Error getting invoice status: {exc}")
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            data: dict = {"payment_hash": checking_id}
            r = await self.client.post(
                "/v1/listpays",
                json=data,
                headers=self.readonly_headers,
            )
            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data:
                logger.warning(f"API response error: {data}")
                return PaymentPendingStatus()

            pays_list = data.get("pays", [])
            if not pays_list:
                logger.warning(f"No payments found for payment hash {checking_id}.")
                return PaymentPendingStatus()

            if len(pays_list) != 1:
                logger.warning(
                    f"Expected one payment status, but found {len(pays_list)}"
                )
                return PaymentPendingStatus()

            pay = pays_list[-1]

            if pay["status"] == "complete":
                fee_msat = pay["amount_sent_msat"] - pay["amount_msat"]
                return PaymentSuccessStatus(fee_msat=fee_msat, preimage=pay["preimage"])

        except Exception as exc:
            logger.warning(f"Error getting payment status: {exc}")

        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            try:
                waitanyinvoice_timeout = None
                request_timeout = httpx.Timeout(
                    connect=5.0, read=waitanyinvoice_timeout, write=60.0, pool=60.0
                )
                data: dict = {
                    "lastpay_index": self.last_pay_index,
                    "timeout": waitanyinvoice_timeout,
                }
                url = "/v1/waitanyinvoice"
                async with self.client.stream(
                    "POST",
                    url,
                    json=data,
                    headers=self.readonly_headers,
                    timeout=request_timeout,
                ) as r:
                    async for line in r.aiter_lines():
                        inv = json.loads(line)
                        if "error" in inv and "message" in inv["error"]:
                            logger.warning("Error in paid_invoices_stream:", inv)
                            raise Exception(inv["error"]["message"])
                        try:
                            paid = inv["status"] == "paid"
                            self.last_pay_index = inv["pay_index"]
                            if not paid:
                                continue
                        except Exception as exc:
                            logger.warning(exc)
                            continue
                        logger.debug(f"paid invoice: {inv}")

                        if "payment_hash" in inv:
                            payment_hash_from_waitanyinvoice = inv["payment_hash"]
                            yield payment_hash_from_waitanyinvoice

            except Exception as exc:
                logger.debug(
                    f"lost connection to corelightning-rest invoices stream: '{exc}', "
                    "reconnecting..."
                )
                await asyncio.sleep(0.02)

    def _create_client(self) -> httpx.AsyncClient:
        """Create an HTTP client with specified headers and SSL configuration."""

        parsed_url = urlparse(self.url)

        # Validate the URL scheme
        if parsed_url.scheme == "http":
            if parsed_url.hostname in ("localhost", "127.0.0.1", "::1"):
                logger.warning("Not using SSL for connection to CLNRestWallet")
            else:
                raise ValueError(
                    "Insecure HTTP connections are only allowed for localhost or "
                    "equivalent IP addresses. Set CLNREST_URL to https:// for external "
                    "connections or use localhost."
                )
            return httpx.AsyncClient(base_url=self.url)

        if parsed_url.scheme == "https":
            logger.info(f"Using SSL to connect to {self.url}")

            # Check for CA certificate
            if not settings.clnrest_ca:
                logger.warning(
                    "No CA certificate provided for CLNRestWallet. "
                    "This setup requires a CA certificate for server authentication "
                    "and trust. Set CLNREST_CA to the CA certificate file path or the "
                    "contents of the certificate."
                )
                raise ValueError("CA certificate is required for secure communication.")

            logger.info(f"CA Certificate provided: {settings.clnrest_ca}")

            # Create an SSL context and load the CA certificate
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

            # Load CA certificate
            if os.path.isfile(settings.clnrest_ca):
                logger.info(f"Using CA certificate file: {settings.clnrest_ca}")
                ssl_context.load_verify_locations(cafile=settings.clnrest_ca)
            else:
                logger.info("Using CA certificate from PEM string: ")
                ca_content = settings.clnrest_ca.replace("\\n", "\n")
                logger.info(ca_content)
                ssl_context.load_verify_locations(cadata=ca_content)

            # Optional: Disable hostname checking if necessary
            # especially for ip addresses
            ssl_context.check_hostname = False

            # Create the HTTP client without a client certificate
            client = httpx.AsyncClient(base_url=self.url, verify=ssl_context)

            return client

        else:
            raise ValueError("CLNREST_URL must start with http:// or https://")


def _generate_label() -> str:
    """Generate a unique label for the invoice."""
    random_uuid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode()
    return f"LNbits_{random_uuid}"
