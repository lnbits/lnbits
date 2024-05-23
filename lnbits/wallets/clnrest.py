import asyncio
import json
import random
from typing import AsyncGenerator, Dict, Optional

import httpx
import ssl
from bolt11 import Bolt11Exception
from bolt11.decode import decode
from loguru import logger

from lnbits.settings import settings


from .base import (
    InvoiceResponse,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    UnsupportedError,
    Wallet,
)

from pathlib import Path

import base58
import base64
import json
import uuid
import hashlib


def decode_rune(rune):
    # TODO: make this function align with how runes are decoded using lightning-cli decode

    # Ensure proper base64 URL-safe padding
    padding = '=' * (-len(rune) % 4)
    rune_padded = rune + padding

    try:
        # Base64 URL-safe decode
        decoded_bytes = base64.urlsafe_b64decode(rune_padded)
    except Exception as e:
        return f"Error decoding base64: {e}"

    # Find the text part by looking for the first valid UTF-8 segment
    text_part = None
    binary_part = None
    for i in range(len(decoded_bytes)):
        try:
            text_part = decoded_bytes[i:].decode('utf-8')
            binary_part = decoded_bytes[:i]
            break
        except UnicodeDecodeError:
            continue
    else:
        return "No valid UTF-8 text found in the rune"

    # Split the text part into its components
    parts = text_part.split('|')

    if not parts:
        return "Invalid rune format"

    # Create a dictionary to hold the parsed data
    rune_info = {
        # 'binary_part': binary_part,  # Uncomment if binary part is needed
        'restrictions': []
    }

    valid_operators = ['=', '/', '^', '$', '~', '<', '>', '{', '}', '!', '#']

    for restriction in parts:
        found_condition = False

        for operator in valid_operators:
            if operator in restriction:
                fieldname, value = restriction.split(operator, 1)
                condition = operator
                found_condition = True
                break

        if found_condition:
            # Ignore comments and empty conditions
            if condition == '#' or not fieldname or not value:
                continue

            rune_info['restrictions'].append({
                'fieldname': fieldname,
                'condition': condition,
                'value': value
            })

    return rune_info

class CLNRestWallet(Wallet):

    def __init__(self):

        if not settings.clnrest_url:
            raise ValueError("Cannot initialize CLNRestWallet: missing CLNREST_URL")

        if not settings.clnrest_nodeid:
            raise ValueError("Cannot initialize CLNRestWallet: missing CLNREST_NODEID")

        if settings.clnrest_url.startswith("https://"):
            logger.info("Using SSL")
            if not settings.clnrest_cert:
                logger.warning(
                    "No certificate for the CLNRestWallet provided! "
                    "This only works if you have a publicly issued certificate."
                    "Set CLNREST_CERT to the certificate file (~/.lightning/bitcoin/server.pem)"
                )
            else:
                #The cert that is generated by core lightning by default is only valid for DNS=localhost, DNS=cln with core lightning by default
                #This will allow you to check the certificate but ignore the hostname issue
                self.bypass_ssl_hostname_check = True
            
        elif settings.clnrest_url.startswith("http://"):
            logger.warning("NOT Using SSL")
            raise ValueError ('#TODO: consider not allowing this unless the hostname is localhost')

        if settings.clnrest_readonly_rune:
            logger.debug((decode_rune(settings.clnrest_readonly_rune)))
            logger.debug(f"TODO: decode this readonly_rune and make sure that it has the correct permissions: {settings.clnrest_readonly_rune}:")
        else:
            raise ValueError(
                "Cannot initialize CLNRestWallet: missing CLNREST_READONLY_RUNE. Create one with:\n"
                """ lightning-cli createrune restrictions='[["method=listfunds", "method=listpays", "method=listinvoices", "method=getinfo", "method=summary", "method=waitanyinvoice"]]' """
            )

        if settings.clnrest_invoice_rune:
            logger.debug(f"TODO: decode this invoice_rune and make sure that it has the correct permissions: {settings.clnrest_invoice_rune}:")
            logger.debug((decode_rune(settings.clnrest_invoice_rune)))
        else:
            raise ValueError(
                "Cannot initialize CLNRestWallet: missing CLNREST_INVOICE_RUNE. Create one with:\n"
                """ lightning-cli createrune restrictions='[["method=invoice"], ["pnameamount_msat<1000001"], ["pname_label^LNbits"], ["rate=60"]]' """
                )

        if settings.clnrest_pay_rune and settings.clnrest_renepay_rune:
            raise ValueError( "Cannot initialize CLNRestWallet: both CLNREST_PAY_RUNE and CLNREST_RENEPAY_RUNE are set. Only one should be set.")
        elif not settings.clnrest_pay_rune and not settings.clnrest_renepay_rune:
            raise ValueError(
                    "Cannot initialize CLNRestWallet: missing either 'CLNREST_PAY_RUNE' or 'CLNREST_RENEPAY_RUNE'. Please create one with one of the following commands:\n"
                    """   lightning-cli createrune restrictions='[["method=pay"],     ["pinvbolt11_amount<1001"], ["pname_label^LNbits"], ["rate=1"]]' \n"""
                    """   lightning-cli createrune restrictions='[["method=renepay"], ["pinvbolt11_amount<1001"], ["pname_label^LNbits"], ["rate=1"]]' """
                    )
        elif settings.clnrest_pay_rune:
            self.use_renepay = False
            logger.debug(f"TODO: decode this pay_rune and make sure that it has the correct permissions: {settings.clnrest_pay_rune}:")
            logger.debug((decode_rune(settings.clnrest_pay_rune)))
        elif settings.clnrest_renepay_rune:
            self.use_renepay = True
            logger.debug(f"TODO: decode this pay_rune and make sure that it has the correct permissions: {settings.clnrest_renepay_rune}:")
            logger.debug((decode_rune(settings.clnrest_renepay_rune)))

        self.url = self.normalize_endpoint(settings.clnrest_url)

        base_headers = {
            "accept": "application/json",
            "User-Agent": settings.user_agent,
            "Content-Type": "application/json",
            "nodeid": settings.clnrest_nodeid,
        }
        
        self.readonly_headers = {**base_headers, "rune": settings.clnrest_readonly_rune}
        self.invoice_headers = {**base_headers, "rune": settings.clnrest_invoice_rune}
        if self.use_renepay:
            self.renepay_headers = {**base_headers, "rune": settings.clnrest_renepay_rune}
        else:
            self.pay_headers = {**base_headers, "rune": settings.clnrest_pay_rune}

        # https://docs.corelightning.org/reference/lightning-pay
        # 201: Already paid
        # 203: Permanent failure at destination.
        # 205: Unable to find a route.
        # 206: Route too expensive.
        # 207: Invoice expired.
        # 210: Payment timed out without a payment in progress.
        self.pay_failure_error_codes = [201, 203, 205, 206, 207, 210]

        self.cert  = settings.clnrest_cert or False
        self.client = self.create_client()
        self.last_pay_index = 0
        self.statuses = {
            "paid": True,
            "complete": True,
            "failed": False,
            "pending": None,
        }


    def create_client(self) -> httpx.AsyncClient:
        """Create an HTTP client with specified headers and SSL configuration."""

        if self.cert:
            ssl_context = ssl.create_default_context()
            cert_path = Path(self.cert)
            if cert_path.is_file():
                ssl_context.load_verify_locations(cert_path)
            else:
                ssl_context.load_verify_locations(cadata=self.cert)
            if self.bypass_ssl_hostname_check:
                ssl_context.check_hostname = False
            return httpx.AsyncClient(base_url=self.url, verify=ssl_context)
        else:
            assert self.url.startswith("http://localhost"), "URL must start with 'http://localhost' if you don't want to use SSL"
            return httpx.AsyncClient(base_url=self.url, verify=False)

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            logger.debug("REQUEST to /v1/getinfo")
            r = await self.client.post( "/v1/listfunds", timeout=15, headers=self.readonly_headers)
        except (httpx.ConnectError, httpx.RequestError) as e:
            logger.error(f"Connection error: {str(e)}")
            return StatusResponse(f"Unable to connect to '{self.endpoint}'", 0)

        try:
            response_data = r.json()
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return StatusResponse(f"Failed to decode JSON response from {self.url}", 0)

        if r.is_error or "error" in response_data:
            error_message = response_data.get("error", r.text)
            return StatusResponse(f"Failed to connect to {self.url}, got: '{error_message}'...", 0)

        if not response_data:
            return StatusResponse("no data", 0)

        channels = response_data.get("channels")
        if not channels:
            return StatusResponse("no data or no channels available", 0)

        total_our_amount_msat = sum(channel["our_amount_msat"] for channel in channels)

        return StatusResponse(None, total_our_amount_msat)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:

        #TODO: the identifier could be used to encode the LNBits user or the LNBits wallet that is creating the invoice

        identifier = base58.b58encode(hashlib.sha256(settings.clnrest_invoice_rune.encode('utf-8')).digest()[:16]).decode('utf-8').rstrip('=')
        label = "LNbits " + identifier + ' ' + base58.b58encode(uuid.uuid4().bytes).rstrip(b'=').decode('utf-8')

        data: Dict = {
            "amount_msat": amount * 1000,
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

        logger.debug(f"REQUEST to /v1/invoice: : {json.dumps(data)}")

        try:
            r = await self.client.post(
                "/v1/invoice",
                json=data,
                headers=self.invoice_headers,
            )
            r.raise_for_status()
            data = r.json()

            if len(data) == 0:
                return InvoiceResponse(False, None, None, "no data")

            if "error" in data:
                return InvoiceResponse(
                            False, None, None, f"""Server error: '{data["error"]}'"""
                )

            if r.is_error:
                return InvoiceResponse(False, None, None, f"Server error: '{r.text}'")

            if "payment_hash" not in data or "bolt11" not in data:
                return InvoiceResponse(
                        False, None, None, "Server error: 'missing required fields'"
                )

            return InvoiceResponse(True, data["payment_hash"], data["bolt11"], None)
        except json.JSONDecodeError:
            return InvoiceResponse(
                False, None, None, "Server error: 'invalid json response'"
            )
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(
                False, None, None, f"Unable to connect to {self.url}."
            )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        #todo: rune restrictions will not be enforced for internal payments within the lnbits instance as they are not routed through to core lightning
        try:
            invoice = decode(bolt11)
            logger.debug(invoice)
            logger.debug(invoice.description)

        except Bolt11Exception as exc:
            return PaymentResponse(False, None, None, None, str(exc))


        if not invoice.amount_msat or invoice.amount_msat <= 0:
            error_message = "0 amount invoices are not allowed"
            return PaymentResponse(False, None, None, None, error_message)

        #TODO: the identifier could be used to encode the LNBits user or the LNBits wallet that is pay the invoice
        identifier = base58.b58encode(hashlib.sha256(settings.clnrest_pay_rune.encode('utf-8')).digest()[:16]).decode('utf-8').rstrip('=')
        label = "LNbits " + identifier + ' ' + base58.b58encode(uuid.uuid4().bytes).rstrip(b'=').decode('utf-8')

        if self.use_renepay:
            pay_or_renepay_headers = self.renepay_headers
            api_endpoint = "/v1/renepay"
            maxfee = fee_limit_msat
            maxdelay = 300
            data = {
                "invstring": bolt11,
                "label": label,
                "description": invoice.description,
                "maxfee": maxfee,
                "retry_for": 60,
            }
                #"amount_msat": invoice.amount_msat,
                #"maxdelay": maxdelay,
                # Add other necessary parameters like retry_for, description, label as required
        else:
            pay_or_renepay_headers = self.pay_headers
            api_endpoint = "/v1/pay"
            fee_limit_percent = fee_limit_msat / invoice.amount_msat * 100
            data = {
                "bolt11": bolt11,
                "label": label,
                "description": invoice.description,
                "maxfeepercent": f"{fee_limit_percent:.11}",
                "exemptfee": 0,  # so fee_limit_percent is applied even on payments
                # with fee < 5000 millisatoshi (which is default value of exemptfee)
            }

        logger.debug(f"REQUEST to {api_endpoint}: {json.dumps(data)}")

        r = await self.client.post(
            api_endpoint,
            json=data,
            headers=pay_or_renepay_headers,
            timeout=None,
        )

        if r.is_error or "error" in r.json():
            try:
                data = r.json()
                logger.debug(f"RESPONSE with error: {data}")
                error_message = data["error"]
            except Exception:
                error_message = r.text
            return PaymentResponse(False, None, None, None, error_message)

        data = r.json()
        logger.debug(f"RESPONSE: {data}")

        if data["status"] != "complete":
            return PaymentResponse(False, None, None, None, "payment failed")

        #destination = data['destination']
        #created_at = data['created_at']
        #parts = data['parts']
        status = data['status']

        checking_id = data["payment_hash"]
        preimage = data["payment_preimage"]

        amount_sent_msat_int = data.get('amount_sent_msat')
        amount_msat_int = data.get('amount_msat')
        fee_msat = amount_sent_msat_int - amount_msat_int

        return PaymentResponse(
            self.statuses.get(data["status"]), checking_id, fee_msat, preimage, None
        )

        return PaymentResponse(status, checking_id, fee_msat, preimage, None)

    async def invoice_status(self, checking_id: str) -> PaymentStatus:
        logger.error("why is something calling invoice_status from clnrest.py")
        # Call get_invoice_status instead
        return await self.get_invoice_status(checking_id)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        data: Dict = { "payment_hash": checking_id }
        logger.debug(f"REQUEST to /v1/listinvoices: {json.dumps(data)}")
        r = await self.client.post(
            "/v1/listinvoices",
            json=data,
            headers=self.readonly_headers,
        )
        try:
            r.raise_for_status()
            data = r.json()

            if r.is_error or "error" in data or data.get("invoices") is None:
                raise Exception("error in cln response")
            logger.debug(f"RESPONSE: invoice with payment_hash {data['invoices'][0]['payment_hash']} has status {data['invoices'][0]['status']}")
            return PaymentStatus(self.statuses.get(data["invoices"][0]["status"]))
        except Exception as e:
            logger.error(f"Error getting invoice status: {e}")
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        data: Dict = { "payment_hash": checking_id }

        logger.debug(f"REQUEST to /v1/listpays: {json.dumps(data)}")
        r = await self.client.post(
            "/v1/listpays",
            json=data,
            headers=self.readonly_headers,
        )
        try:
            r.raise_for_status()
            data = r.json()
            logger.debug(data)

            if r.is_error or "error" in data or not data.get("pays"):
                logger.error(f"RESPONSE with error: {data}")
                raise Exception("error in corelightning-rest response")


            pays_list = data.get("pays", [])
            if len(pays_list) != 1:
                error_message = f"Expected one payment status, but found {len(pays_list)}"
                logger.error(error_message)
                raise Exception(error_message)

            pay = pays_list[0]

            logger.debug(f"Payment status from API: {pay['status']}")

            fee_msat, preimage = None, None
            if pay['status'] == 'complete':
                fee_msat = -pay["amount_sent_msat"] - pay["amount_msat"]
                preimage = pay["preimage"]

            return PaymentStatus(self.statuses.get(pay["status"]), fee_msat, preimage)
        except Exception as e:
            logger.error(f"Error getting payment status: {e}")
            return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while True:
            try:
                read_timeout=None
                data: Dict = { "lastpay_index": self.last_pay_index, "timeout": read_timeout}
                request_timeout = httpx.Timeout(connect=5.0, read=read_timeout, write=60.0, pool=60.0)
                url = "/v1/waitanyinvoice"
                logger.debug(f"REQUEST(stream) to  /v1/waitanyinvoice with data: {data}.")
                async with self.client.stream("POST", url, json=data, headers=self.readonly_headers,  timeout=request_timeout) as r:
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
                        payment_hash = inv["payment_hash"]
                        yield payment_hash

                        #TODO: ask about why this might ever be needed

                        # hack to return payment_hash if the above shouldn't work
                        #r = await self.client.get(
                        #    "/v1/invoice/listInvoices",
                        #    params={"label": inv["label"]},
                        #)
                        #paid_invoice = r.json()
                        #logger.trace(f"paid invoice: {paid_invoice}")
                        #assert self.statuses[
                        #    paid_invoice["invoices"][0]["status"]
                        #], "streamed invoice not paid"
                        #assert "invoices" in paid_invoice, "no invoices in response"
                        #assert len(paid_invoice["invoices"]), "no invoices in response"
                        #logger.debug(inv)
                        #yield paid_invoice["invoices"][0]["payment_hash"]

            except Exception as exc:
                logger.debug(
                    f"lost connection to corelightning-rest invoices stream: '{exc}', "
                    "reconnecting..."
                )
                await asyncio.sleep(0.5)
