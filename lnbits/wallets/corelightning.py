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
    FetchInvoiceResponse,
    InvoiceMainData,
    InvoiceResponse,
    OfferResponse,
    OfferErrorStatus,
    OfferStatus,
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

    async def cleanup(self):
        pass

    def __init__(self):
        rpc = settings.corelightning_rpc or settings.clightning_rpc
        if not rpc:
            raise ValueError(
                "cannot initialize CoreLightningWallet: missing corelightning_rpc"
            )
        self.pay = settings.corelightning_pay_command
        self.ln = LightningRpc(rpc)
        # check if description_hash is supported (from corelightning>=v0.11.0)
        command = self.ln.help("invoice")["help"][0]["command"]  # type: ignore
        self.supports_description_hash = "deschashonly" in command

        # https://docs.corelightning.org/reference/lightning-pay
        # -32602: Invalid bolt11: Prefix bc is not for regtest
        # -1: Catchall nonspecific error.
        # 201: Already paid
        # 203: Permanent failure at destination.
        # 205: Unable to find a route.
        # 206: Route too expensive.
        # 207: Invoice expired.
        # 210: Payment timed out without a payment in progress.
        self.pay_failure_error_codes = [-32602, 201, 203, 205, 206, 207, 210]

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

    async def create_offer(
        self,
        amount: int,
        memo: Optional[str] = None,
        issuer: Optional[str] = None,
        absolute_expiry: Optional[int] = None,
        single_use: Optional[bool] = None,
        **kwargs,
    ) -> OfferResponse:
        label = kwargs.get("label", f"lbl{random.random()}")
        try:
            payload = {
                "amount": int(amount * 1000) if amount>0 else "any",
                "description": memo,
                "issuer": issuer,
                "label": label,
                "absolute_expiry": absolute_expiry,
                "single_use": single_use,
            }
            r: dict = self.ln.call("offer", payload)

            if r.get("code") and r.get("code") < 0:  # type: ignore
                raise Exception(r.get("message"))

            return OfferResponse(True, r["offer_id"], r["active"], r["single_use"], r["bolt12"], r["used"], r["created"], r["label"], None)
        except RpcError as exc:
            logger.warning(exc)
            error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return OfferResponse(False, None, None, None, None, None, None, None, error_message)
        except KeyError as exc:
            logger.warning(exc)
            return OfferResponse(
                False, None, None, None, None, None, None, None, "Server error: 'missing required fields'"
            )
        except Exception as e:
            logger.warning(e)
            return OfferResponse(False, None, None, None, None, None, None, None, str(e))

    async def enable_offer(
        self,
        offer_id: str,
    ) -> OfferResponse:
        try:
            payload = {
                "offer_id": offer_id,
            }
            r: dict = self.ln.call("enableoffer", payload)

            if r.get("code"):

                if r.get("code")==1006:
                    return OfferResponse(True, None, None, None, None, None, False, None, None)

                else:  # type: ignore
                    raise Exception(r.get("message"))

            return OfferResponse(True, r["offer_id"], r["active"], r["single_use"], r["bolt12"], r["used"], True, r["label"], None)
        except RpcError as exc:
            logger.warning(exc)
            error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return OfferResponse(False, None, None, None, None, None, None, None, error_message)
        except KeyError as exc:
            logger.warning(exc)
            return OfferResponse(
                False, None, None, None, "Server error: 'missing required fields'"
            )
        except Exception as e:
            logger.warning(e)
            return OfferResponse(False, None, None, None, None, None, None, None, str(e))

    async def disable_offer(
        self,
        offer_id: str,
    ) -> OfferResponse:
        try:
            payload = {
                "offer_id": offer_id,
            }
            r: dict = self.ln.call("disableoffer", payload)

            if r.get("code"):

                if r.get("code")==1001:
                    return OfferResponse(True, None, None, None, None, None, False, None, None)

                else:  # type: ignore
                    raise Exception(r.get("message"))

            return OfferResponse(True, r["offer_id"], r["active"], r["single_use"], r["bolt12"], r["used"], True, r["label"], None)
        except RpcError as exc:
            logger.warning(exc)
            error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return OfferResponse(False, None, None, None, None, None, None, None, error_message)
        except KeyError as exc:
            logger.warning(exc)
            return OfferResponse(
                False, None, None, None, "Server error: 'missing required fields'"
            )
        except Exception as e:
            logger.warning(e)
            return OfferResponse(False, None, None, None, None, None, None, None, str(e))

    async def get_offer_status(self, offer_id: str, active_only: bool = False) -> OfferStatus:
        try:
            payload = {
                "offer_id": offer_id,
                "active_only": active_only,
            }
            r: dict = self.ln.call("listoffers", payload)

            if not r["offers"]:
                return OfferErrorStatus()

            offer_resp = r["offers"][-1]

            if offer_resp["offer_id"] == offer_id:
                    return OfferStatus(offer_resp["active"], offer_resp["used"])
            else:
                logger.warning(f"supplied an invalid offer_id: {offer_id}")
            return OfferErrorStatus()
        except RpcError as exc:
            logger.warning(exc)
            return OfferErrorStatus()
        except Exception as exc:
            logger.warning(exc)
            return OfferErrorStatus()

    async def fetch_invoice(
        self,
        offer_id: str,
        amount: Optional[int] = None,
    ) -> FetchInvoiceResponse:
        try:
            payload = {
                "offer": offer,
                "amount_msat": int(amount * 1000) if amount else None,
            }
            r: dict = self.ln.call("fetchinvoice", payload)

            if r.get("code") and r.get("code") < 0:  # type: ignore
                raise Exception(r.get("message"))

            return FetchInvoiceResponse(True, r["invoice"], None)
        except RpcError as exc:
            logger.warning(exc)
            error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
            return FetchInvoiceResponse(False, None, error_message)
        except KeyError as exc:
            logger.warning(exc)
            return FetchInvoiceResponse(
                False, None, "Server error: 'missing required fields'"
            )
        except Exception as e:
            logger.warning(e)
            return FetchInvoiceResponse(False, None, str(e))

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
                amount_msat=msat,
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

            # maxfee overrides both maxfeepercent and exemptfee defaults (and
            # if you specify maxfee you cannot specify either of those), and
            # creates an absolute limit on what fee we will pay. This allows you to
            # implement your own heuristics rather than the primitive ones used
            # here.
            payload = {
                "bolt11": bolt11,
                "maxfee": fee_limit_msat,
                "description": invoice.description,
            }

            r = await run_sync(lambda: self.ln.call(self.pay, payload))

            fee_msat = -int(r["amount_sent_msat"] - r["amount_msat"])
            return PaymentResponse(
                True, r["payment_hash"], fee_msat, r["payment_preimage"], None
            )
        except RpcError as exc:
            logger.warning(exc)
            try:
                error_code = exc.error.get("code")  # type: ignore
                if error_code in self.pay_failure_error_codes:
                    error_message = exc.error.get("message", error_code)  # type: ignore
                    return PaymentResponse(
                        False, None, None, None, f"Payment failed: {error_message}"
                    )
                else:
                    error_message = f"Payment failed: {exc.error}"
                    return PaymentResponse(None, None, None, None, error_message)
            except Exception:
                error_message = f"RPC '{exc.method}' failed with '{exc.error}'."
                return PaymentResponse(None, None, None, None, error_message)
        except KeyError as exc:
            logger.warning(exc)
            return PaymentResponse(
                None, None, None, None, "Server error: 'missing required fields'"
            )
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11}")
            logger.warning(exc)
            return PaymentResponse(None, None, None, None, f"Payment failed: '{exc}'.")


    async def get_bolt12_invoice_main_data(self, checking_id: str) -> Optional[InvoiceMainData]:
        try:
            r: dict = self.ln.listinvoices(payment_hash=checking_id)

            if not r["invoices"]:
                raise Exception(f"Invoice with checking_id {checking_id}")

            invoice_resp = r["invoices"][-1]
            logger.debug(f"Returned invoice response is {invoice_resp}")

            if invoice_resp["payment_hash"] != checking_id:
                raise Exception(f"Supplied an invalid checking_id: {checking_id}")

            if not invoice_resp["bolt12"]:
                raise Exception("Invoice does not contain bolt12 data")

            payload = {
                    "string": invoice_resp["bolt12"]
                    }
            r: dict = self.ln.call("decode", payload)

            logger.debug(f"Returned decoded bolt12 invoice is {r}")

            if not r["type"] == "bolt12 invoice":
                raise Exception("Provided string is not a bolt12 invoice")

            if not r["valid"] == True:
                raise Exception("Provided bolt12 invoice is invalid")

            if invoice_resp["status"] == "paid":
                return InvoiceMainData(paid = True, 
                                       payment_hash = invoice_resp["payment_hash"],
                                       description = invoice_resp.get("description"),
                                       payer_note = r.get("invreq_payer_note"),
                                       amount_msat = invoice_resp["amount_msat"],
                                       offer_id = invoice_resp["local_offer_id"],
                                       expires_at = invoice_resp["expires_at"],
                                       created_at = r["invoice_created_at"],
                                       paid_at = invoice_resp["paid_at"],
                                       payment_preimage = invoice_resp["payment_preimage"])

            else:
                return InvoiceMainData(paid = None if invoice_resp["status"] == "unpaid" else False, 
                                       payment_hash = invoice_resp["payment_hash"],
                                       description = invoice_resp.get("description"),
                                       payer_note = r.get("invreq_payer_note"),
                                       amount_msat = invoice_resp["amount_msat"],
                                       offer_id = invoice_resp["local_offer_id"],
                                       expires_at = invoice_resp["expires_at"],
                                       created_at = r["invoice_created_at"],
                                       paid_at = None,
                                       payment_preimage = None)

        except RpcError as exc:
            logger.warning(exc)
            return None
        except Exception as exc:
            logger.warning(exc)
            return None

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
        while settings.lnbits_running:
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
