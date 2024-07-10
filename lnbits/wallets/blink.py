import asyncio
import hashlib
import json
from typing import AsyncGenerator, Optional

import httpx
from loguru import logger
from pydantic import BaseModel

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
        self._wallet_id = None

    @property
    def wallet_id(self):
        if self._wallet_id:
            return self._wallet_id
        raise ValueError("Wallet id not initialized.")

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            await self._init_wallet_id()

            payload = {"query": q.balance_query, "variables": {}}
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
            if btc_balance is None:
                return StatusResponse("No BTC balance", 0)

            # multiply balance by 1000 to get msats balance
            return StatusResponse(None, btc_balance * 1000)
        except ValueError as exc:
            return StatusResponse(str(exc), 0)
        except Exception as exc:
            logger.warning(exc)
            return StatusResponse(f"Unable to connect, got: '{exc}'", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        # https://dev.blink.sv/api/btc-ln-receive

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

        data = {"query": q.invoice_query, "variables": invoice_variables}

        try:
            response = await self._graphql_query(data)

            errors = (
                response.get("data", {})
                .get("lnInvoiceCreateOnBehalfOfRecipient", {})
                .get("errors", {})
            )
            if len(errors) > 0:
                error_message = errors[0].get("message")
                return InvoiceResponse(False, None, None, error_message)

            payment_request = (
                response.get("data", {})
                .get("lnInvoiceCreateOnBehalfOfRecipient", {})
                .get("invoice", {})
                .get("paymentRequest", None)
            )
            checking_id = (
                response.get("data", {})
                .get("lnInvoiceCreateOnBehalfOfRecipient", {})
                .get("invoice", {})
                .get("paymentHash", None)
            )

            return InvoiceResponse(True, checking_id, payment_request, None)
        except json.JSONDecodeError:
            return InvoiceResponse(
                False, None, None, "Server error: 'invalid json response'"
            )
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(
                False, None, None, f"Unable to connect to {self.endpoint}."
            )

    async def pay_invoice(
        self, bolt11_invoice: str, fee_limit_msat: int
    ) -> PaymentResponse:
        # https://dev.blink.sv/api/btc-ln-send
        # Future: add check fee estimate is < fee_limit_msat before paying invoice

        payment_variables = {
            "input": {
                "paymentRequest": bolt11_invoice,
                "walletId": self.wallet_id,
                "memo": "Payment memo",
            }
        }
        data = {"query": q.payment_query, "variables": payment_variables}
        try:
            response = await self._graphql_query(data)

            errors = (
                response.get("data", {})
                .get("lnInvoicePaymentSend", {})
                .get("errors", {})
            )
            if len(errors) > 0:
                error_message = errors[0].get("message")
                return PaymentResponse(False, None, None, None, error_message)

            checking_id = bolt11.decode(bolt11_invoice).payment_hash

            payment_status = await self.get_payment_status(checking_id)
            fee_msat = payment_status.fee_msat
            preimage = payment_status.preimage
            return PaymentResponse(True, checking_id, fee_msat, preimage, None)
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11_invoice}")
            logger.warning(exc)
            return PaymentResponse(
                None, None, None, None, f"Unable to connect to {self.endpoint}."
            )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:

        statuses = {
            "EXPIRED": False,
            "PENDING": None,
            "PAID": True,
        }

        variables = {"paymentHash": checking_id, "walletId": self.wallet_id}
        data = {"query": q.status_query, "variables": variables}
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
        txs_data = (
            response_data.get("me", {})
            .get("defaultAccount", {})
            .get("walletById", {})
            .get("transactionsByPaymentHash", [])
        )
        fee = txs_data[0].get("settlementFee")
        preimage = txs_data[0].get("settlementVia").get("preImage")
        status = txs_data[0].get("status")
        # logger.info(f"payment status fee: {fee}, preimage: {preimage}, status: {status}")  # noqa: E501

        statuses = {
            "FAILURE": False,
            "EXPIRED": False,
            "PENDING": None,
            "PAID": True,
            "SUCCESS": True,
        }
        return PaymentStatus(
            paid=statuses[status], fee_msat=fee * 1000, preimage=preimage
        )

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        # https://dev.blink.sv/api/websocket
        self.queue: asyncio.Queue = asyncio.Queue(0)
        while True:
            value = await self.queue.get()
            yield value

    async def _graphql_query(self, payload) -> dict:
        response = await self.client.post(self.endpoint, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    async def _init_wallet_id(self) -> str:
        """
        Get the defaultAccount wallet id, required for payments.
        """

        if self._wallet_id:
            return self._wallet_id

        try:
            payload = {
                "query": q.wallet_query,
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

            if not btc_wallet_ids:
                raise ValueError("BTC Wallet not found")

            self._wallet_id = btc_wallet_ids[0]
            return self._wallet_id
        except Exception as exc:
            logger.warning(exc)
            raise ValueError(f"Unable to connect to '{self.endpoint}'") from exc


class BlinkGrafqlQueries(BaseModel):
    balance_query: str
    invoice_query: str
    payment_query: str
    status_query: str
    wallet_query: str


q = BlinkGrafqlQueries(
    balance_query="""
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
            """,
    invoice_query="""mutation LnInvoiceCreateOnBehalfOfRecipient($input: LnInvoiceCreateOnBehalfOfRecipientInput!) {
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
        """,  # noqa: E501
    payment_query="""mutation LnInvoicePaymentSend($input: LnInvoicePaymentInput!) {
            lnInvoicePaymentSend(input: $input) {
            status
                errors {
                    message
                    path
                    code
                    }
                }
            }
        """,
    status_query="""
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

                """,  # noqa: E501,
    wallet_query="query me { me { defaultAccount { wallets { id walletCurrency }}}}",
)
