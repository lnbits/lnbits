import asyncio
import hashlib
import json
from typing import AsyncGenerator, Dict, Optional

import httpx
from loguru import logger

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)

class BlinkWallet(Wallet):
    """https://dev.blink.sv/"""

    def __init__(self):
        if not settings.blink_api_endpoint:
            raise ValueError(
                "cannot initialize BlinkWallet: missing blink_api_endpoint"
            )
        if not settings.blink_token:
            raise ValueError("cannot initialize BlinkWallet: missing blink_token")

        self.endpoint = self.normalize_endpoint(settings.blink_api_endpoint)
        self.auth = {
            "X-API-KEY" : settings.blink_token,
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.auth)
        self.wallet_id = None


    async def graphql_query(self, payload) -> json:
        response = await self.client.post(self.endpoint, json=payload, timeout=10)
        data = response.json()
        return data

    async def get_wallet_id(self) -> str:
        """
        Get the defaultAccount wallet id, required for payments.
        """
        try:
            payload = {
                "query": "query me { me { defaultAccount { wallets { id walletCurrency }}}}",
                "variables": {}
            }
            response = await self.graphql_query(payload)
            wallets = response.get("data", {}).get("me", {}).get("defaultAccount", {}).get("wallets", [])
            btc_wallet_ids = [wallet["id"] for wallet in wallets if wallet["walletCurrency"] == "BTC"]
            wallet_id = btc_wallet_ids[0]
            if not btc_wallet_ids:
                return StatusResponse("BTC Wallet not found", 0)
            else: 
                wallet_id = btc_wallet_ids[0]
                return wallet_id
        except (httpx.ConnectError, httpx.RequestError):
            return StatusResponse(f"Unable to connect to '{self.endpoint}'", 0)


    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        # is it possible to put this in the __init__ somehow?
        if self.wallet_id is None:
            self.wallet_id = await self.get_wallet_id()
        
        balance_query = """
            query Me {
            me {
                defaultAccount {
                wallets {
                    walletCurrency
                    balance
                }
                }
            }
        }
        """
        payload = {
            "query": balance_query,
            "variables": {}
        }
        response = await self.graphql_query(payload)        
        wallets = response.get("data", {}).get("me", {}).get("defaultAccount", {}).get("wallets", [])
        btc_balance = next((wallet['balance'] for wallet in wallets if wallet['walletCurrency'] == 'BTC'), None)
        # multiply balance by 1000 to get msats balance
        return StatusResponse(None, btc_balance * 1000)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        # https://dev.blink.sv/api/btc-ln-receive

        invoice_query = """mutation LnInvoiceCreateOnBehalfOfRecipient($input: LnInvoiceCreateOnBehalfOfRecipientInput!) {
        lnInvoiceCreateOnBehalfOfRecipient(input: $input) {
            invoice {
            paymentRequest
            paymentHash
            paymentSecret
            satoshis
            }
            errors {
            message
            }
        }
        }
        """
        invoice_variables = {
            "input": {
                "amount": amount,
                "recipientWalletId": self.wallet_id,
                "descriptionHash": '',
                "memo": ''
            }
        }
        if description_hash:
            invoice_variables['input']['descriptionHash'] = description_hash.hex()
        elif unhashed_description:
            invoice_variables['input']['descriptionHash']= hashlib.sha256(unhashed_description).hexdigest()
        else:
            invoice_variables['input']['memo'] = memo or ""

        data = {
            "query": invoice_query,
            "variables": invoice_variables
        }
        response = await self.graphql_query(data)

        errors = response.get('data', {}).get('lnInvoiceCreateOnBehalfOfRecipient', {}).get('errors', {})
        if len(errors) > 0:
            error_message = errors[0].get('message')
            return InvoiceResponse(False, None, None, error_message)
        
        payment_request = response.get('data', {}).get('lnInvoiceCreateOnBehalfOfRecipient', {}).get('invoice', {}).get('paymentRequest', {})
        checking_id = response.get('data', {}).get('lnInvoiceCreateOnBehalfOfRecipient', {}).get('invoice', {}).get('paymentHash', {})

        return InvoiceResponse(True, checking_id, payment_request, None)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        #  https://dev.blink.sv/api/btc-ln-send
        payment_query = """mutation LnInvoicePaymentSend($input: LnInvoicePaymentInput!) {
            lnInvoicePaymentSend(input: $input) {
            status
                errors {
                    message
                    path
                    code
                    }
                }
            }
        """
        payment_variables =  {
            "input": {
                "paymentRequest": bolt11,
                "walletId": self.wallet_id,
                "memo": "Payment memo"
            }
        }
        data = {
            "query": payment_query,
            "variables": payment_variables
        }
        response = await self.graphql_query(data)

        errors = response.get('data', {}).get('lnInvoicePaymentSend', {}).get('errors', {})
        if len(errors) > 0:
            error_message = errors[0].get('message')
            return InvoiceResponse(False, None, None, error_message)

        status = response['data']['lnInvoicePaymentSend']['status']
        # if status == 'PAID' or 'ALREADY_PAID':

        # TODO: get the paymentHash, fee and preimage
        # checking_id = data['paymentHash']
        # fee_msat = -data["fee"]
        # preimage = data["payment_preimage"]
        
        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        return await self.get_payment_status(checking_id)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        # TODO: needs to update to Blink graphQL version, in progress
        r = await self.client.get(f"/invoices/{checking_id}")

        if r.is_error:
            return PaymentStatus(None)

        data = r.json()

        statuses = {
            "PENDING": None,
            "PAID": True,
        }
        return PaymentStatus(statuses[data.get("state")], fee_msat=None, preimage=None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        # https://dev.blink.sv/api/websocket
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value

    async def webhook_listener(self):
        # https://dev.blink.sv/api/webhooks#currently-available-webhook-events
        logger.error("Blink webhook listener disabled")
        return
