import asyncio
import hashlib
from typing import AsyncGenerator, Optional, Union

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

    async def get_wallet_id(self) -> Union[str, StatusResponse]:
        """
        Get the defaultAccount wallet id, required for payments.
        """
        try:
            payload = {
                "query": "query me { me { defaultAccount { wallets { id walletCurrency }}}}",  # noqa: E501
                "variables": {},
            }
            response = await self._graphql_query(payload)
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
            ret = await self.get_wallet_id()
            if isinstance(ret, StatusResponse):
                return ret
            self.wallet_id = ret

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
        response = await self._graphql_query(payload)
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
        assert btc_balance is not None
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
        """  # noqa: E501
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
        # logger.info(f"create_invoice complete data: {data}")

        response = await self._graphql_query(data)
        # logger.info(f"create_invoice complete response: {response}")

        errors = (
            response.get("data", {})
            .get("lnInvoiceCreateOnBehalfOfRecipient", {})
            .get("errors", {})
        )
        if len(errors) > 0:
            error_message = errors[0].get("message")
            # logger.error(f"Error creating invoice: {error_message}")
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

        # logger.info(f"Created invoice: {payment_request}, checking_id: {checking_id}")
        return InvoiceResponse(True, checking_id, payment_request, None)

    async def pay_invoice(
        self, bolt11_invoice: str, fee_limit_msat: int
    ) -> PaymentResponse:
        # https://dev.blink.sv/api/btc-ln-send
        # Future: add check fee estimate is < fee_limit_msat before paying invoice
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
        """  # noqa: E501
        payment_variables = {
            "input": {
                "paymentRequest": bolt11_invoice,
                "walletId": self.wallet_id,
                "memo": "Payment memo",
            }
        }
        data = {"query": payment_query, "variables": payment_variables}
        response = await self._graphql_query(data)
        # logger.info(f'pay_invoice complete response: {response}')
        errors = (
            response.get("data", {}).get("lnInvoicePaymentSend", {}).get("errors", {})
        )
        if len(errors) > 0:
            error_message = errors[0].get("message")
            return PaymentResponse(False, None, None, None, error_message)

        checking_id = bolt11.decode(bolt11_invoice).payment_hash
        # logger.info(f'pay_invoice complete checking_id: {checking_id}')
        payment_status = await self.get_payment_status(checking_id)
        fee_msat = payment_status.fee_msat
        preimage = payment_status.preimage
        return PaymentResponse(True, checking_id, fee_msat, preimage, None)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        status_query = """
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

                """  # noqa: E501
        statuses = {
            "EXPIRED": False,
            "PENDING": None,
            "PAID": True,
        }

        variables = {"paymentHash": checking_id, "walletId": self.wallet_id}
        data = {"query": status_query, "variables": variables}
        response = await self._graphql_query(data)
        # logger.info(f"get_invoice_status response: {response}")
        if response.get("errors") is not None:
            # msg = response["errors"][0]["message"]
            # logger.info(msg)
            return PaymentStatus(None)
        else:
            status = response["data"]["me"]["defaultAccount"]["walletById"][
                "invoiceByPaymentHash"
            ]["paymentStatus"]
            # logger.info(status)
            return PaymentStatus(statuses[status])

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        tx_query = """
            query TransactionsByPaymentHash($walletId: WalletId!, $transactionsByPaymentHash: PaymentHash!) {
                    me {
                        defaultAccount {
                        walletById(walletId: $walletId) {
                            walletCurrency
                            ... on BTCWallet {
                            transactionsByPaymentHash(paymentHash: $transactionsByPaymentHash) {
                                settlementFee
                                status
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
            """  # noqa: E501
        variables = {
            "walletId": self.wallet_id,
            "transactionsByPaymentHash": checking_id,
        }
        data = {"query": tx_query, "variables": variables}

        # logger.info(f"get_payment_status data: {data}\n\n")
        response = await self._graphql_query(data)
        # logger.info(f"get_payment_status response: {response}")

        response_data = response.get("data")
        assert response_data is not None
        data = (
            response_data.get("me")
            .get("defaultAccount")
            .get("walletById")
            .get("transactionsByPaymentHash")
        )
        fee = data[0].get("settlementFee")
        preimage = data[0].get("settlementVia").get("preImage")
        status = data[0].get("status")
        # logger.info(f"payment status fee: {fee}, preimage: {preimage}, status: {status}")  # noqa: E501

        statuses = {
            "FAILURE": False,
            "EXPIRED": False,
            "PENDING": None,
            "PAID": True,
            "SUCCESS": True,
        }
        return PaymentStatus(statuses[status], fee_msat=fee * 1000, preimage=preimage)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        # https://dev.blink.sv/api/websocket
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value

    async def _graphql_query(self, payload) -> dict:
        response = await self.client.post(self.endpoint, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
