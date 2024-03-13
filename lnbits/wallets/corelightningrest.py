import asyncio
import json
import random
from typing import AsyncGenerator, Dict, Optional

import httpx
from bolt11 import Bolt11Exception
from bolt11.decode import decode
from loguru import logger

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentStatusMap,
    PaymentSuccessStatus,
    StatusResponse,
    Unsupported,
    Wallet,
)
from .macaroon import load_macaroon


class CoreLightningRestWallet(Wallet):
    def __init__(self):
        if not settings.corelightning_rest_url:
            raise ValueError(
                "cannot initialize CoreLightningRestWallet: "
                "missing corelightning_rest_url"
            )
        if not settings.corelightning_rest_macaroon:
            raise ValueError(
                "cannot initialize CoreLightningRestWallet: "
                "missing corelightning_rest_macaroon"
            )
        macaroon = load_macaroon(settings.corelightning_rest_macaroon)
        if not macaroon:
            raise ValueError(
                "cannot initialize CoreLightningRestWallet: "
                "invalid corelightning_rest_macaroon provided"
            )

        self.url = self.normalize_endpoint(settings.corelightning_rest_url)
        headers = {
            "macaroon": macaroon,
            "encodingtype": "hex",
            "accept": "application/json",
            "User-Agent": settings.user_agent,
        }

        self.cert = settings.corelightning_rest_cert or False
        self.client = httpx.AsyncClient(verify=self.cert, headers=headers)
        self.last_pay_index = 0

        # todo: remove statuses
        self.statuses = {
            "paid": True,
            "complete": True,
            "failed": False,
            "pending": None,
        }

    @property
    def payment_status_map(self) -> PaymentStatusMap:
        return PaymentStatusMap(
            success=["paid", "complete"],
            failed=["failed"],
            pending=["pending"],
        )

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        r = await self.client.get(f"{self.url}/v1/channel/localremotebal", timeout=5)
        r.raise_for_status()
        if r.is_error or "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except Exception:
                error_message = r.text
            return StatusResponse(
                f"Failed to connect to {self.url}, got: '{error_message}...'", 0
            )

        data = r.json()
        if len(data) == 0:
            return StatusResponse("no data", 0)

        return StatusResponse(None, int(data.get("localBalance") * 1000))

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        label = f"lbl{random.random()}"
        data: Dict = {
            "amount": amount * 1000,
            "description": memo,
            "label": label,
        }
        if description_hash and not unhashed_description:
            raise Unsupported(
                "'description_hash' unsupported by CoreLightningRest, "
                "provide 'unhashed_description'"
            )

        if unhashed_description:
            data["description"] = unhashed_description.decode("utf-8")

        if kwargs.get("expiry"):
            data["expiry"] = kwargs["expiry"]

        if kwargs.get("preimage"):
            data["preimage"] = kwargs["preimage"]

        r = await self.client.post(
            f"{self.url}/v1/invoice/genInvoice",
            data=data,
        )

        if r.is_error or "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except Exception:
                error_message = r.text

            return InvoiceResponse(False, None, None, error_message)

        data = r.json()
        assert "payment_hash" in data
        assert "bolt11" in data
        return InvoiceResponse(True, data["payment_hash"], data["bolt11"], None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            invoice = decode(bolt11)
        except Bolt11Exception as exc:
            return PaymentResponse(False, None, None, None, str(exc))

        if not invoice.amount_msat or invoice.amount_msat <= 0:
            error_message = "0 amount invoices are not allowed"
            return PaymentResponse(False, None, None, None, error_message)
        fee_limit_percent = fee_limit_msat / invoice.amount_msat * 100
        r = await self.client.post(
            f"{self.url}/v1/pay",
            data={
                "invoice": bolt11,
                "maxfeepercent": f"{fee_limit_percent:.11}",
                "exemptfee": 0,  # so fee_limit_percent is applied even on payments
                # with fee < 5000 millisatoshi (which is default value of exemptfee)
            },
            timeout=None,
        )

        if r.is_error or "error" in r.json():
            try:
                data = r.json()
                error_message = data["error"]
            except Exception:
                error_message = r.text
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()

        checking_id = data["payment_hash"]
        preimage = data["payment_preimage"]
        fee_msat = data["msatoshi_sent"] - data["msatoshi"]

        return PaymentResponse(
            self.statuses.get(data["status"]), checking_id, fee_msat, preimage, None
        )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(
            f"{self.url}/v1/invoice/listInvoices",
            params={"payment_hash": checking_id},
        )
        try:
            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or data.get("invoices") is None:
                raise Exception("error in cln response")

            return self.payment_status(data["invoices"][0]["status"])
        except Exception as e:
            logger.error(f"Error getting invoice status: {e}")
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        r = await self.client.get(
            f"{self.url}/v1/pay/listPays",
            params={"payment_hash": checking_id},
        )
        try:
            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or not data.get("pays"):
                raise Exception("error in corelightning-rest response")

            pay = data["pays"][0]

            status = self.payment_status(pay["status"])
            if status.pending or status.failed:
                return status

            # cut off "msat" and convert to int
            fee_msat = -int(pay["amount_sent_msat"][:-4]) - int(pay["amount_msat"][:-4])
            return PaymentSuccessStatus(fee_msat=fee_msat, preimage=pay["preimage"])

        except Exception as e:
            logger.error(f"Error getting payment status: {e}")
            return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                url = f"{self.url}/v1/invoice/waitAnyInvoice/{self.last_pay_index}"
                async with self.client.stream("GET", url, timeout=None) as r:
                    async for line in r.aiter_lines():
                        inv = json.loads(line)
                        if "error" in inv and "message" in inv["error"]:
                            logger.error("Error in paid_invoices_stream:", inv)
                            raise Exception(inv["error"]["message"])
                        try:
                            paid = inv["status"] == "paid"
                            self.last_pay_index = inv["pay_index"]
                            if not paid:
                                continue
                        except Exception:
                            continue
                        logger.trace(f"paid invoice: {inv}")

                        # NOTE: use payment_hash when corelightning-rest returns it
                        # when using waitAnyInvoice
                        # payment_hash = inv["payment_hash"]
                        # yield payment_hash
                        # hack to return payment_hash if the above shouldn't work
                        r = await self.client.get(
                            f"{self.url}/v1/invoice/listInvoices",
                            params={"label": inv["label"]},
                        )
                        paid_invoice = r.json()
                        logger.trace(f"paid invoice: {paid_invoice}")
                        status = self.payment_status(
                            paid_invoice["invoices"][0]["status"]
                        )
                        assert status.success, "streamed invoice not paid"
                        assert "invoices" in paid_invoice, "no invoices in response"
                        assert len(paid_invoice["invoices"]), "no invoices in response"
                        yield paid_invoice["invoices"][0]["payment_hash"]

            except Exception as exc:
                logger.debug(
                    f"lost connection to corelightning-rest invoices stream: '{exc}', "
                    "reconnecting..."
                )
                await asyncio.sleep(0.02)
