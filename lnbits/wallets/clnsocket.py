import asyncio
import base64
import json
import os
import ssl
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Optional

from bolt11 import Bolt11Exception
from bolt11.decode import decode
from loguru import logger
from pylnsocket import LNSocket, RpcError

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


async def run_sync(func) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)


class CLNSocketWallet(Wallet):
    def __init__(self):
        if not settings.clnsocket_host:
            raise ValueError("Cannot initialize CLNSocketWallet: missing CLNSOCKET_HOST")

        if not settings.clnsocket_readonly_rune:
            raise ValueError(
                "cannot initialize CLNSocketWallet: " "missing clnsocket_readonly_rune"
            )
        self.readonly_rune = settings.clnsocket_readonly_rune.encode('ASCII')
        del settings.clnsocket_readonly_rune
        self.invoice_rune = None
        self.pay_rune = None
        self.renepay_rune = None
        self.xpay_rune = None

        if not settings.clnsocket_nodeid:
            raise ValueError("missing CLNSOCKET_NODEID")

        if settings.clnsocket_invoice_rune is None:
            logger.warning(
                "Will be unable to create any invoices without "
                "setting 'CLNSOCKET_INVOICE_RUNE[:4]'"
            )
        else:
            self.invoice_rune = settings.clnsocket_invoice_rune.encode('ASCII')
            del settings.clnsocket_invoice_rune

        if settings.clnsocket_pay_rune is None:
            logger.warning(
                "Will be unable to call pay without setting 'CLNSOCKET_PAY_RUNE'"
            )
        else:
            self.pay_rune = settings.clnsocket_pay_rune.encode('ASCII')
            del settings.clnsocket_pay_rune

        if settings.clnsocket_renepay_rune is None:
            logger.warning(
                "Will be unable to call renepay without "
                "setting 'CLNSOCKET_RENEPAY_RUNE'"
            )
        else:
            self.renepay_rune = settings.clnsocket_renepay_rune.encode('ASCII')
            del settings.clnsocket_renepay_rune

        if settings.clnsocket_xpay_rune is None:
            logger.warning(
                "Will be unable to call xpay without "
                "setting 'CLNSOCKET_XPAY_RUNE'"
            )
        else:
            self.xpay_rune = settings.clnsocket_xpay_rune.encode('ASCII')
            del settings.clnsocket_xpay_rune

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

        try:
            self.client = LNSocket(settings.clnsocket_nodeid, settings.clnsocket_host)
        except RuntimeError as exc:
            logger.warning(f"Error initialising LNSocket: {exc}")

        self.last_pay_index = settings.clnrest_last_pay_index or 0
        try:
            invoices: dict = self.client.Call(
                    self.readonly_rune,
                    "listinvoices",
                    params={"start": self.last_pay_index},
            )
            for inv in invoices["invoices"][::-1]:
                if "pay_index" in inv:
                    self.last_pay_index = inv["pay_index"]
                    break
            logger.debug(f"Last pay index is {self.last_pay_index}")

        except Exception as exc:
            logger.warning(exc)
        self.statuses = {
            "paid": True,
            "complete": True,
            "failed": False,
            "pending": None,
        }

    async def cleanup(self):
        try:
            del self.client
        except RuntimeError as exc:
            logger.warning(f"Error closing wallet connection: {exc}")

    async def status(self) -> StatusResponse:
        try:
            logger.debug("REQUEST to listfunds")

            response_data = self.client.Call(
                    self.readonly_rune,
                    "listfunds"
            )

            if not response_data:
                logger.warning("Received empty response data")
                return StatusResponse("no data", 0)

            channels = response_data.get("channels", [])
            total_our_amount_msat = sum(
                channel.get("our_amount_msat", 0) for channel in channels
            )

            return StatusResponse(None, total_our_amount_msat)

        except RpcError as exc:
            logger.warning(exc)
            error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return StatusResponse(error_message, 0)

        except Exception as exc:
            logger.warning(exc)
            return StatusResponse(f"Unable to retrieve the list of funds from {settings.clnsocket_host}.", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:

        if not self.invoice_rune:
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
                "'description_hash' unsupported by CLNSocketWallet, "
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
            response_data = self.client.Call(
                self.invoice_rune,
                "invoice",
                params=data,
            )

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

        except RpcError as exc:
            logger.warning(exc)
            error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return InvoiceResponse(ok=False, error_message=error_message)

        except Exception as exc:
            logger.warning(f"Unable to connect to create an invoice with {settings.clnsocket_host}: {exc}")
            return InvoiceResponse(
                ok=False, error_message=f"Unable to create an invoice with {settings.clnsocket_host}."
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

        if not self.pay_rune and not self.renepay_rune and not self.xpay_rune:
            return PaymentResponse(
                ok=False,
                error_message="Unable to pay invoice without a pay, renepay or xpay rune",
            )

        data = {
            "maxfee": fee_limit_msat
        }

        if self.xpay_rune:
            cmd = "xpay"
            rune = self.xpay_rune
            data["invstring"] = bolt11
        elif self.renepay_rune:
            cmd = "renepay"
            rune = self.renepay_rune
            data["invstring"] = bolt11
            data["description"] = invoice.description
        else:
            cmd = "pay"
            rune = self.pay_rune
            data["bolt11"] = bolt11
            data["description"] = invoice.description

        try:
            data = await run_sync(lambda: self.client.Call(
                rune,
                cmd,
                params=data,
            ))

            if "payment_preimage" not in data:
                error_message = data.get("error", "No payment preimage in response")
                logger.warning(error_message)
                return PaymentResponse(error_message=error_message)

            if self.xpay_rune:
                status = await self.get_payment_status(invoice.payment_hash)

                return PaymentResponse(
                    ok=status.paid,
                    checking_id=invoice.payment_hash,
                    fee_msat=status.fee_msat,
                    preimage=status.preimage,
                )

            return PaymentResponse(
                ok=self.statuses.get(data["status"]),
                checking_id=data["payment_hash"],
                fee_msat=data["amount_sent_msat"] - data["amount_msat"],
                preimage=data["payment_preimage"],
            )
        except RpcError as exc:
            logger.warning(exc)
            try:
                error_code = exc.error.get("code")  # type: ignore
                if error_code in self.pay_failure_error_codes:
                    error_message = exc.error.get("message", error_code)  # type: ignore
                    return PaymentResponse(
                        ok=False, error_message=f"Payment failed: {error_message}"
                    )
                else:
                    error_message = f"Payment failed: {exc.error}"
                    return PaymentResponse(error_message=error_message)
            except Exception:
                error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
                return PaymentResponse(error_message=error_message)
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11}")
            logger.warning(exc)
            error_message = f"Unable to connect to {settings.clnsocket_host}."
            return PaymentResponse(error_message=error_message)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        data: dict = {"payment_hash": checking_id}

        try:
            data = self.client.Call(
                self.readonly_rune,
                "listinvoices",
                params=data,
            )
            if data.get("invoices") is None:
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
        except RpcError as exc:
            logger.warning(exc)
            return PaymentPendingStatus()
        except Exception as exc:
            logger.warning(f"Error getting invoice status: {exc}")
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            data: dict = {"payment_hash": checking_id}
            data = self.client.Call(
                self.readonly_rune,
                "listpays",
                params=data,
            )

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
            await asyncio.sleep(3)
            try:
                waitanyinvoice_timeout = 0
                data: dict = {
                    "lastpay_index": self.last_pay_index,
                    "timeout": waitanyinvoice_timeout,
                }
                paid = await run_sync(
                    lambda: self.client.Call(
                       self.readonly_rune,
                       "waitanyinvoice",
                       params=data,
                ))
                self.last_pay_index = paid["pay_index"]
                yield paid["payment_hash"]
            except RpcError as exc:
                # only raise if not a timeout
                if exc.error["code"] != 904:  # type: ignore
                    raise
            except Exception as exc:
                logger.error(
                    f"lost connection to CLNSocket invoices stream: '{exc}', "
                    "retrying in 5 seconds"
                )
                await asyncio.sleep(5)


def _generate_label() -> str:
    """Generate a unique label for the invoice."""
    random_uuid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode()
    return f"LNbits_{random_uuid}"
