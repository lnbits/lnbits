import asyncio
import hashlib
import json
from collections.abc import AsyncGenerator

import httpx
from loguru import logger
from pydantic import BaseModel
from websockets import Subprotocol, connect

from lnbits import bolt11 as bolt11_lib
from lnbits.helpers import normalize_endpoint
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
        if not settings.blink_ws_endpoint:
            raise ValueError("cannot initialize BlinkWallet: missing blink_ws_endpoint")
        if not settings.blink_token:
            raise ValueError("cannot initialize BlinkWallet: missing blink_token")

        self.endpoint = normalize_endpoint(settings.blink_api_endpoint)

        self.auth = {
            "X-API-KEY": settings.blink_token,
            "User-Agent": settings.user_agent,
        }
        self.ws_endpoint = normalize_endpoint(settings.blink_ws_endpoint)
        self.ws_auth = {
            "type": "connection_init",
            "payload": {"X-API-KEY": settings.blink_token},
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.auth)
        self.ws = None
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

        try:
            if self.ws:
                await self.ws.close(reason="Shutting down.")
        except RuntimeError as e:
            logger.warning(f"Error closing websocket connection: {e}")

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
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
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
                return InvoiceResponse(ok=False, error_message=error_message)

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

            # TODO: add preimage to response
            return InvoiceResponse(
                ok=True, checking_id=checking_id, payment_request=payment_request
            )
        except json.JSONDecodeError:
            return InvoiceResponse(
                ok=False, error_message="Server error: 'invalid json response'"
            )
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(
                ok=False, error_message=f"Unable to connect to {self.endpoint}."
            )

    async def _fee_probe(self, bolt11: str) -> tuple[int | None, str | None]:
        """
        Probe the route for the fee of an amount lightning invoice.

        Probing caches the route on the Blink backend so that the subsequent
        payment settles with the exact fee instead of Blink's max fee reserve.
        Only invoices that carry an amount can be probed here, since the
        pay_invoice interface does not provide a separate amount for
        zero-amount invoices.

        Returns a tuple of (fee_sat, error_message). On success the fee in
        satoshis is returned; on failure an error message is returned.
        """
        probe_input = {
            "paymentRequest": bolt11,
            "walletId": self.wallet_id,
        }
        data = {"query": q.fee_probe_query, "variables": {"input": probe_input}}
        response = await self._graphql_query(data)
        result = response.get("data", {}).get("lnInvoiceFeeProbe", {})

        errors = result.get("errors") or []
        if len(errors) > 0:
            return None, errors[0].get("message")

        return result.get("amount"), None

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        # https://dev.blink.sv/api/btc-ln-send

        invoice = bolt11_lib.decode(bolt11)

        # Only amount invoices can be probed: lnInvoiceFeeProbe takes no amount,
        # and zero-amount invoices have no amount to probe with (pay_invoice
        # does not receive a separate amount). Zero-amount invoices skip the
        # probe and fall back to the send-without-probe behaviour.
        try:
            if invoice.amount_msat:
                fee_sat, probe_error = await self._fee_probe(bolt11)
                if probe_error is not None:
                    if not settings.blink_send_without_probe:
                        logger.info(f"Fee probe failed for invoice {bolt11}")
                        return PaymentResponse(ok=False, error_message=probe_error)
                    logger.warning(
                        f"Fee probe failed ('{probe_error}'), "
                        "sending payment without probe."
                    )
                elif fee_sat is not None and fee_sat * 1000 > fee_limit_msat:
                    error_message = (
                        f"fee of {fee_sat * 1000} msat exceeds "
                        f"limit of {fee_limit_msat} msat"
                    )
                    return PaymentResponse(ok=False, error_message=error_message)
            elif not settings.blink_send_without_probe:
                logger.info(f"Cannot probe zero-amount invoice {bolt11}")
                return PaymentResponse(
                    ok=False,
                    error_message="Cannot probe fee for zero-amount invoice.",
                )
        except Exception as exc:
            if not settings.blink_send_without_probe:
                logger.info(f"Failed to probe fee for invoice {bolt11}")
                logger.warning(exc)
                return PaymentResponse(
                    ok=False, error_message=f"Unable to connect to {self.endpoint}."
                )
            logger.warning(f"Fee probe errored ('{exc}'), sending without probe.")

        payment_variables = {
            "input": {
                "paymentRequest": bolt11,
                "walletId": self.wallet_id,
                "memo": "Payment memo",
            }
        }
        data = {"query": q.payment_query, "variables": payment_variables}
        try:
            response = await self._graphql_query(data)

            payment_result = response.get("data", {}).get("lnInvoicePaymentSend", {})
            errors = payment_result.get("errors", {})
            if len(errors) > 0:
                error_message = errors[0].get("message")
                status = payment_result.get("status")
                return PaymentResponse(
                    ok=False if status in {"FAILURE", "FAILED"} else None,
                    error_message=error_message,
                )

            checking_id = invoice.payment_hash

            payment_status = await self.get_payment_status(checking_id)
            fee_msat = payment_status.fee_msat
            preimage = payment_status.preimage
            return PaymentResponse(
                ok=payment_status.paid,
                checking_id=checking_id,
                fee_msat=fee_msat,
                preimage=preimage,
            )
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11}")
            logger.warning(exc)
            return PaymentResponse(
                error_message=f"Unable to connect to {self.endpoint}."
            )

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:

        statuses = {
            "EXPIRED": False,
            "PENDING": None,
            "PAID": True,
        }

        variables = {"paymentHash": checking_id, "walletId": self.wallet_id}
        data = {"query": q.status_query, "variables": variables}

        try:
            response = await self._graphql_query(data)
            if response.get("errors") is not None:
                logger.trace(response.get("errors"))
                return PaymentStatus(None)

            status = response["data"]["me"]["defaultAccount"]["walletById"][
                "invoiceByPaymentHash"
            ]["paymentStatus"]
            return PaymentStatus(statuses[status])
        except Exception as e:
            logger.warning(f"Error getting invoice status: {e}")
            return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:

        variables = {
            "walletId": self.wallet_id,
            "transactionsByPaymentHash": checking_id,
        }
        data = {"query": q.tx_query, "variables": variables}

        statuses = {
            "FAILURE": False,
            "EXPIRED": False,
            "PENDING": None,
            "PAID": True,
            "SUCCESS": True,
        }

        try:
            response = await self._graphql_query(data)

            response_data = response.get("data")
            if response_data is None:
                raise ValueError("No data found in response.")
            txs_data = (
                response_data.get("me", {})
                .get("defaultAccount", {})
                .get("walletById", {})
                .get("transactionsByPaymentHash", [])
            )
            tx_data = next((t for t in txs_data if t.get("direction") == "SEND"), None)
            if not tx_data:
                raise ValueError("No SEND data found.")
            fee = tx_data.get("settlementFee")
            preimage = tx_data.get("settlementVia", {}).get("preImage")
            status = tx_data.get("status")

            return PaymentStatus(
                paid=statuses[status], fee_msat=fee * 1000, preimage=preimage
            )
        except Exception as e:
            logger.error(f"Error getting payment status: {e}")
            return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        subscription_id = "blink_payment_stream"
        while settings.lnbits_running:
            try:
                async with connect(
                    self.ws_endpoint, subprotocols=[Subprotocol("graphql-transport-ws")]
                ) as ws:
                    logger.info("Connected to blink invoices stream.")
                    self.ws = ws
                    await ws.send(json.dumps(self.ws_auth))
                    confirmation = await ws.recv()
                    ack = json.loads(confirmation)
                    if ack.get("type") != "connection_ack":
                        raise ValueError("Websocket connection not acknowledged.")

                    logger.info("Websocket connection acknowledged.")
                    subscription_req = {
                        "id": subscription_id,
                        "type": "subscribe",
                        "payload": {"query": q.my_updates_query, "variables": {}},
                    }
                    await ws.send(json.dumps(subscription_req))

                    while settings.lnbits_running:
                        message = await ws.recv()
                        resp = json.loads(message)
                        if resp.get("id") != subscription_id:
                            continue
                        tx = (
                            resp.get("payload", {})
                            .get("data", {})
                            .get("myUpdates", {})
                            .get("update", {})
                            .get("transaction", {})
                        )
                        if tx.get("direction") != "RECEIVE":
                            continue

                        if not tx.get("initiationVia"):
                            continue

                        payment_hash = tx.get("initiationVia").get("paymentHash")
                        if payment_hash:
                            yield payment_hash

            except Exception as exc:
                logger.error(
                    f"lost connection to blink invoices stream: '{exc}'"
                    "retrying in 5 seconds"
                )
                await asyncio.sleep(5)

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
    fee_probe_query: str
    status_query: str
    wallet_query: str
    tx_query: str
    my_updates_query: str


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
    invoice_query="""
        mutation LnInvoiceCreateOnBehalfOfRecipient(
          $input: LnInvoiceCreateOnBehalfOfRecipientInput!
        ) {
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
        """,
    payment_query="""
        mutation LnInvoicePaymentSend($input: LnInvoicePaymentInput!) {
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
    fee_probe_query="""
        mutation LnInvoiceFeeProbe($input: LnInvoiceFeeProbeInput!) {
          lnInvoiceFeeProbe(input: $input) {
            amount
            errors {
              message
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
        """,
    wallet_query="""
        query me {
          me {
            defaultAccount {
              wallets {
                id
                walletCurrency
              }
            }
          }
        }
        """,
    tx_query="""
        query TransactionsByPaymentHash(
          $walletId: WalletId!
          $transactionsByPaymentHash: PaymentHash!
        ) {
          me {
            defaultAccount {
              walletById(walletId: $walletId) {
                walletCurrency
                ... on BTCWallet {
                  transactionsByPaymentHash(paymentHash: $transactionsByPaymentHash) {
                    settlementFee
                    status
                    direction
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
        """,
    my_updates_query="""
        subscription {
          myUpdates {
            update {
              ... on LnUpdate {
                transaction {
                  initiationVia {
                    ... on InitiationViaLn {
                      paymentHash
                    }
                  }
                  direction
                }
              }
            }
          }
        }
        """,
)
