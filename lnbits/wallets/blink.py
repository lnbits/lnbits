import asyncio
import hashlib
import base64
import re
import json
from typing import AsyncGenerator, Optional

import httpx
from loguru import logger

from lnbits import bolt11
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
            "X-API-KEY": settings.blink_token,
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
                "variables": {},
            }
            response = await self.graphql_query(payload)
            wallets = (
                response.get("data", {})
                .get("me", {})
                .get("defaultAccount", {})
                .get("wallets", [])
            )
            btc_wallet_ids = [
                wallet["id"] for wallet in wallets if wallet["walletCurrency"] == "BTC"
            ]
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
        payload = {"query": balance_query, "variables": {}}
        response = await self.graphql_query(payload)
        wallets = (
            response.get("data", {})
            .get("me", {})
            .get("defaultAccount", {})
            .get("wallets", [])
        )
        btc_balance = next(
            (
                wallet["balance"]
                for wallet in wallets
                if wallet["walletCurrency"] == "BTC"
            ),
            None,
        )
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
            }
        }
        if description_hash:
            invoice_variables["input"]["descriptionHash"] = description_hash.hex()
        elif unhashed_description:
            invoice_variables["input"]["descriptionHash"] = hashlib.sha256(
                unhashed_description
            ).hexdigest()
        else:
            invoice_variables["input"]["memo"] = memo or ""

        data = {"query": invoice_query, "variables": invoice_variables}
        logger.info(f'create_invoice complete data: {data}')

        response = await self.graphql_query(data)
        logger.info(f'create_invoice complete response: {response}')

        errors = (
            response.get("data", {})
            .get("lnInvoiceCreateOnBehalfOfRecipient", {})
            .get("errors", {})
        )
        if len(errors) > 0:
            error_message = errors[0].get("message")
            logger.error(f"Error creating invoice: {error_message}")
            return InvoiceResponse(False, None, None, error_message)

        payment_request = (
            response.get("data", {})
            .get("lnInvoiceCreateOnBehalfOfRecipient", {})
            .get("invoice", {})
            .get("paymentRequest", {})
        )
        checking_id = (
            response.get("data", {})
            .get("lnInvoiceCreateOnBehalfOfRecipient", {})
            .get("invoice", {})
            .get("paymentHash", {})
        )

        logger.info(f"Created invoice: {payment_request}, checking_id: {checking_id}")
        return InvoiceResponse(True, checking_id, payment_request, None)

    
    async def pay_invoice(self, bolt11_invoice: str, fee_limit_msat: int) -> PaymentResponse:
        #  https://dev.blink.sv/api/btc-ln-send
        # TODO: add check fee estimate before paying invoice
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
        payment_variables = {
            "input": {
                "paymentRequest": bolt11_invoice,
                "walletId": self.wallet_id,
                "memo": "Payment memo",
            }
        }
        data = {"query": payment_query, "variables": payment_variables}
        response = await self.graphql_query(data)

        errors = (
            response.get("data", {}).get("lnInvoicePaymentSend", {}).get("errors", {})
        )
        if len(errors) > 0:
            error_message = errors[0].get("message")
            return PaymentResponse(False, None, None, None, error_message)

        checking_id = bolt11.decode(bolt11_invoice).payment_hash
        payment_status = await self.get_payment_status(checking_id)
        fee_msat = payment_status.fee_msat
        preimage = payment_status.preimage
        return PaymentResponse(True, checking_id, fee_msat, preimage , None)


    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        logger.info(f'inside get_invoice_status with checking_id: {checking_id}')
        status_query  ="""
                query InvoiceByPaymentHash($walletId: WalletId!, $paymentHash: PaymentHash!) {
                me {
                    defaultAccount {
                    walletById(walletId: $walletId) {
                        invoiceByPaymentHash(paymentHash: $paymentHash) {
                        ... on LnInvoice {
                            paymentStatus
                        }
                        }
                    }
                    }
                }
                }

                """
        statuses = {
            "EXPIRED": False, 
            "PENDING": None, 
            "PAID": True, 
        }

        variables = {
            "paymentHash": checking_id,
            "walletId": self.wallet_id
        }
        data = {"query": status_query, "variables": variables}
        logger.info(f'get invoice_status data: {data}')
        response = await self.graphql_query(data)
        print(f"get_invoice_status response: {response}")
        if response.get('errors') is not None:
            msg = response['errors'][0]['message']
            print(msg)
            return PaymentStatus(None)
        else: 
            status = response['data']['me']['defaultAccount']['walletById']['invoiceByPaymentHash']['paymentStatus']
            print(status)        
            return PaymentStatus(statuses[status])
        

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        tx_query = """
        query TransactionsByPaymentHash($paymentHash: PaymentHash!) {
        me {
            defaultAccount {
            wallets {
                ... on BTCWallet {
                transactionsByPaymentHash(paymentHash: $paymentHash) {
                    createdAt
                    direction
                    id
                    memo
                    status
                    settlementFee
                    settlementVia {
                    ... on SettlementViaLn {
                        preImage
                    }
                    }
                }
                }
            }
            }
        }
        }
        """
        variables = {"paymentHash": checking_id}
        data = {"query": tx_query, "variables": variables}
        print(f"get_payment_status data: {data}\n\n")
        response = await self.graphql_query(data)
        print(f"get_payment_status response: {response}")

        statuses = {"FAILURE": False, "EXPIRED": False, "PENDING": None, "PAID": True, "SUCCESS": True}

        status = "PENDING"
        fee = 1
        preimage ="preimage"
        return PaymentStatus(statuses[status], fee_msat=fee * 1000, preimage=preimage)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        # https://dev.blink.sv/api/websocket
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value
