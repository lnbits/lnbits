import asyncio
import random
from typing import Any, AsyncGenerator, Optional

from bolt11.decode import decode as bolt11_decode
from bolt11.exceptions import Bolt11Exception
from loguru import logger
from pyln.client import LightningRpc, RpcError

from lnbits.nodes.cln import CoreLightningNode
from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    UnsupportedError,
    Wallet,
)


async def run_sync(func) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)


class CoreLightningWallet(Wallet):
    __node_cls__ = CoreLightningNode

    def __init__(self):
        rpc = settings.corelightning_rpc or settings.clightning_rpc
        if not rpc:
            raise ValueError(
                "cannot initialize CoreLightningWallet: missing corelightning_rpc"
            )

        self.ln = LightningRpc(rpc)
        # check if description_hash is supported (from corelightning>=v0.11.0)
        command = self.ln.help("invoice")["help"][0]["command"]  # type: ignore
        self.supports_description_hash = "deschashonly" in command

        # check last payindex so we can listen from that point on
        self.last_pay_index = 0
        invoices: dict = self.ln.listinvoices()  # type: ignore
        for inv in invoices["invoices"][::-1]:
            if "pay_index" in inv:
                self.last_pay_index = inv["pay_index"]
                break

    async def status(self) -> StatusResponse:
        try:
            funds: dict = self.ln.listfunds()  # type: ignore
            if len(funds) == 0:
                return StatusResponse("no data", 0)

            return StatusResponse(
                None, sum([int(ch["our_amount_msat"]) for ch in funds["channels"]])
            )
        except RpcError as exc:
            logger.warning(exc)
            error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return StatusResponse(error_message, 0)
        except Exception as exc:
            logger.warning(f"Failed to connect, got: '{exc}'")
            return StatusResponse(f"Unable to connect, got: '{exc}'", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        label = kwargs.get("label", f"lbl{random.random()}")
        msat: int = int(amount * 1000)
        try:
            if description_hash and not unhashed_description:
                raise UnsupportedError(
                    "'description_hash' unsupported by CoreLightning, provide"
                    " 'unhashed_description'"
                )
            if unhashed_description and not self.supports_description_hash:
                raise UnsupportedError("unhashed_description")
            r: dict = self.ln.invoice(  # type: ignore
                msatoshi=msat,
                label=label,
                description=(
                    unhashed_description.decode() if unhashed_description else memo
                ),
                exposeprivatechannels=True,
                deschashonly=(
                    True if unhashed_description else False
                ),  # we can't pass None here
                expiry=kwargs.get("expiry"),
            )

            if r.get("code") and r.get("code") < 0:  # type: ignore
                raise Exception(r.get("message"))

            return InvoiceResponse(True, r["payment_hash"], r["bolt11"], None)
        except RpcError as exc:
            logger.warning(exc)
            error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return InvoiceResponse(False, None, None, error_message)
        except KeyError as exc:
            logger.warning(exc)
            return InvoiceResponse(
                False, None, None, "Server error: 'missing required fields'"
            )
        except Exception as e:
            logger.warning(e)
            return InvoiceResponse(False, None, None, str(e))

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            invoice = bolt11_decode(bolt11)
        except Bolt11Exception as exc:
            return PaymentResponse(False, None, None, None, str(exc))

        try:
            previous_payment = await self.get_payment_status(invoice.payment_hash)
            if previous_payment.paid:
                return PaymentResponse(False, None, None, None, "invoice already paid")

            if not invoice.amount_msat or invoice.amount_msat <= 0:
                return PaymentResponse(
                    False, None, None, None, "CLN 0 amount invoice not supported"
                )

            fee_limit_percent = fee_limit_msat / invoice.amount_msat * 100
            # so fee_limit_percent is applied even
            # on payments with fee < 5000 millisatoshi
            # (which is default value of exemptfee)
            payload = {
                "bolt11": bolt11,
                "maxfeepercent": f"{fee_limit_percent:.11}",
                "exemptfee": 0,
                # so fee_limit_percent is applied even on payments with fee < 5000
                # millisatoshi (which is default value of exemptfee)
                "description": invoice.description,
            }

            r = await run_sync(lambda: self.ln.call("pay", payload))

            fee_msat = -int(r["amount_sent_msat"] - r["amount_msat"])
            return PaymentResponse(
                True, r["payment_hash"], fee_msat, r["payment_preimage"], None
            )
        except RpcError as exc:
            logger.warning(exc)
            try:
                error_message = exc.error["attempts"][-1]["fail_reason"]  # type: ignore
            except Exception:
                error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return PaymentResponse(False, None, None, None, error_message)
        except KeyError as exc:
            logger.warning(exc)
            return PaymentResponse(
                False, None, None, None, "Server error: 'missing required fields'"
            )
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11}")
            logger.warning(exc)
            return PaymentResponse(False, None, None, None, f"Payment failed: '{exc}'.")

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r: dict = self.ln.listinvoices(payment_hash=checking_id)  # type: ignore

            if not r["invoices"]:
                return PaymentPendingStatus()

            invoice_resp = r["invoices"][-1]

            if invoice_resp["payment_hash"] == checking_id:
                if invoice_resp["status"] == "paid":
                    return PaymentSuccessStatus()
                elif invoice_resp["status"] == "unpaid":
                    return PaymentPendingStatus()
                elif invoice_resp["status"] == "expired":
                    return PaymentFailedStatus()
            else:
                logger.warning(f"supplied an invalid checking_id: {checking_id}")
            return PaymentPendingStatus()
        except RpcError as exc:
            logger.warning(exc)
            return PaymentPendingStatus()
        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            r: dict = self.ln.listpays(payment_hash=checking_id)  # type: ignore

            if "pays" not in r:
                return PaymentPendingStatus()
            if not r["pays"]:
                # no payment with this payment_hash is found
                return PaymentFailedStatus()

            payment_resp = r["pays"][-1]

            if payment_resp["payment_hash"] == checking_id:
                status = payment_resp["status"]
                if status == "complete":
                    fee_msat = -int(
                        payment_resp["amount_sent_msat"] - payment_resp["amount_msat"]
                    )

                    return PaymentSuccessStatus(
                        fee_msat=fee_msat, preimage=payment_resp["preimage"]
                    )
                elif status == "failed":
                    return PaymentFailedStatus()
                else:
                    return PaymentPendingStatus()
            else:
                logger.warning(f"supplied an invalid checking_id: {checking_id}")
            return PaymentPendingStatus()

        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                paid = await run_sync(
                    lambda: self.ln.waitanyinvoice(self.last_pay_index, timeout=2)
                )
                self.last_pay_index = paid["pay_index"]
                yield paid["payment_hash"]
            except RpcError as exc:
                # only raise if not a timeout
                if exc.error["code"] != 904:  # type: ignore
                    raise
            except Exception as exc:
                logger.error(
                    f"lost connection to corelightning invoices stream: '{exc}', "
                    "retrying in 5 seconds"
                )
                await asyncio.sleep(5)
