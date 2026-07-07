import asyncio
import hashlib
import json
import random
import time
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


class TokenBucket:
    """Token bucket rate limiter for Blink GraphQL API."""

    def __init__(self, rate: int, period_seconds: int) -> None:
        self.rate = rate
        self.period = period_seconds
        self.tokens = rate
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()

    async def consume(self) -> None:
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            if elapsed > 0:
                new_tokens = int((elapsed / self.period) * self.rate)
                self.tokens = min(self.rate, self.tokens + new_tokens)
                self.last_refill = now
            if self.tokens < 1:
                wait_time = (self.period / self.rate) * (1 - self.tokens)
                await asyncio.sleep(wait_time)
                self.last_refill = time.monotonic()
                self.tokens = 1
            self.tokens -= 1


_INVOICE_STATUS_MAP = {
    "EXPIRED": False,
    "PENDING": None,
    "PAID": True,
}

_PAYMENT_STATUS_MAP = {
    "FAILURE": False,
    "EXPIRED": False,
    "PENDING": None,
    "PAID": True,
    "SUCCESS": True,
}


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

        super().__init__()

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
        self._shutdown = False

        # Rate limiter: 120 requests per 60 seconds for GraphQL
        self._graphql_limiter = TokenBucket(120, 60)

        # Payment status cache
        self.payment_status_cache: dict[str, dict] = {}
        self.payment_status_cache_pending_ttl = 30
        self.payment_status_cache_terminal_ttl = 60 * 60 * 24

        # Pending invoice tracking
        self.pending_invoice_details: dict[str, dict] = {}
        self.pending_invoices_lookup_cooldown = 1.0
        self.pending_invoices_maintenance_interval = 5
        self.lookup_backoff_schedule = [30, 60, 120, 300, 600, 1200, 1800]

        # Paid invoice queue for paid_invoices_stream
        self.paid_invoices_queue: asyncio.Queue[str] = asyncio.Queue()

        # Locks for coalescing concurrent status checks
        self._status_locks: dict[str, asyncio.Lock] = {}

    @property
    def wallet_id(self):
        if self._wallet_id:
            return self._wallet_id
        raise ValueError("Wallet id not initialized.")

    async def cleanup(self):
        self._shutdown = True
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

            if checking_id:
                created_at = int(time.time())
                expiry = kwargs.get("expiry", 3600)
                expires_at = created_at + expiry
                self._track_pending_invoice(checking_id, created_at, expires_at)

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

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            invoice_data = bolt11_lib.decode(bolt11)
            payment_hash = invoice_data.payment_hash
        except Exception as e:
            logger.warning(f"Failed to decode bolt11: {e}")
            return PaymentResponse(ok=False, error_message=f"Invalid bolt11: {e}")

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

            errors = (
                response.get("data", {})
                .get("lnInvoicePaymentSend", {})
                .get("errors", {})
            )
            if len(errors) > 0:
                error_message = errors[0].get("message")
                return PaymentResponse(ok=False, error_message=error_message)

            payment_status = await self.get_payment_status(payment_hash)
            fee_msat = payment_status.fee_msat
            preimage = payment_status.preimage
            return PaymentResponse(
                ok=True,
                checking_id=payment_hash,
                fee_msat=fee_msat,
                preimage=preimage,
            )
        except Exception as exc:
            logger.info(f"Failed to pay invoice {bolt11}")
            logger.warning(exc)
            return PaymentResponse(checking_id=payment_hash)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        cached = self._get_cached_payment_status(checking_id)
        if cached is not None:
            return cached

        status = await self._fetch_invoice_status(checking_id)
        self._cache_payment_status(checking_id, status)
        return status

    async def _fetch_invoice_status(self, checking_id: str) -> PaymentStatus:
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
            return PaymentStatus(_INVOICE_STATUS_MAP[status])
        except Exception as e:
            logger.warning(f"Error getting invoice status: {e}")
            return PaymentStatus(None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        cached = self._get_cached_payment_status(checking_id)
        if cached is not None:
            return cached

        lock = self._status_locks.get(checking_id)
        if lock is None:
            lock = asyncio.Lock()
            self._status_locks[checking_id] = lock

        async with lock:
            cached = self._get_cached_payment_status(checking_id)
            if cached is not None:
                return cached

            status = await self._fetch_payment_status(checking_id)
            self._cache_payment_status(checking_id, status)

            if status.paid is not None:
                self._status_locks.pop(checking_id, None)

            return status

    async def _fetch_payment_status(self, checking_id: str) -> PaymentStatus:
        variables = {
            "walletId": self.wallet_id,
            "transactionsByPaymentHash": checking_id,
        }
        data = {"query": q.tx_query, "variables": variables}

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
                paid=_PAYMENT_STATUS_MAP[status],
                fee_msat=fee * 1000,
                preimage=preimage,
            )
        except Exception as e:
            logger.error(f"Error getting payment status: {e}")
            return PaymentStatus(None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        ws_task = asyncio.create_task(self._ws_payment_listener())
        try:
            while settings.lnbits_running:
                try:
                    value = await asyncio.wait_for(
                        self.paid_invoices_queue.get(),
                        timeout=self.pending_invoices_maintenance_interval,
                    )
                    yield value
                except asyncio.TimeoutError:
                    await self._maintain_pending_invoices()
        finally:
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass

    async def _ws_payment_listener(self):
        subscription_id = "blink_payment_stream"
        while settings.lnbits_running and not self._shutdown:
            try:
                async with connect(
                    self.ws_endpoint,
                    subprotocols=[Subprotocol("graphql-transport-ws")],
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
                        "payload": {
                            "query": q.my_updates_query,
                            "variables": {},
                        },
                    }
                    await ws.send(json.dumps(subscription_req))

                    while settings.lnbits_running and not self._shutdown:
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
                            self._remove_pending_invoice(payment_hash)
                            self.paid_invoices_queue.put_nowait(payment_hash)

            except Exception as exc:
                logger.error(
                    f"lost connection to blink invoices stream: '{exc}'"
                    " retrying in 5 seconds"
                )
                await asyncio.sleep(5)

    async def _maintain_pending_invoices(self):
        if not self.pending_invoices:
            return

        now = time.time()
        self._expire_pending_invoices(now)
        if not self.pending_invoices:
            return

        due = self._get_due_pending_invoices(now)
        if not due:
            return

        await self._process_due_invoices(due, now)

    def _get_due_pending_invoices(self, now: float) -> list[dict]:
        due = []
        for cid in list(self.pending_invoices):
            invoice = self.pending_invoice_details.get(cid)
            if invoice and invoice.get("next_lookup_at", 0) <= now:
                due.append(invoice)
        due.sort(key=lambda inv: inv.get("next_lookup_at", 0))
        return due

    async def _process_due_invoices(self, due: list[dict], now: float) -> None:
        for index, invoice in enumerate(due):
            cid = invoice["checking_id"]
            if cid not in self.pending_invoices:
                continue
            settled = await self._lookup_single_pending_invoice(cid, now)
            if (
                not settled
                and index < len(due) - 1
                and self.pending_invoices_lookup_cooldown > 0
            ):
                await asyncio.sleep(self.pending_invoices_lookup_cooldown)

    async def _lookup_single_pending_invoice(self, cid: str, now: float) -> bool:
        try:
            status = await self.get_invoice_status(cid)
            if status.paid:
                self._remove_pending_invoice(cid)
                self.paid_invoices_queue.put_nowait(cid)
                return True
            if status.failed:
                self._remove_pending_invoice(cid)
                return True
            invoice = self.pending_invoice_details.get(cid)
            if invoice:
                invoice["lookup_attempts"] = int(invoice.get("lookup_attempts", 0)) + 1
                self._schedule_next_lookup(invoice, now)
        except Exception:
            invoice = self.pending_invoice_details.get(cid)
            if invoice:
                invoice["lookup_attempts"] = int(invoice.get("lookup_attempts", 0)) + 1
                self._schedule_next_lookup(invoice, now)
        return False

    async def _graphql_query(self, payload) -> dict:
        await self._graphql_limiter.consume()
        response = await self.client.post(self.endpoint, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    async def _init_wallet_id(self) -> str:
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

    # ── Cache helpers ──────────────────────────────────────────────

    def _cache_payment_status(self, checking_id: str, status: PaymentStatus) -> None:
        ttl = (
            self.payment_status_cache_terminal_ttl
            if status.paid is not None
            else self.payment_status_cache_pending_ttl
        )
        self.payment_status_cache[checking_id] = {
            "status": status,
            "expires_at": time.time() + ttl,
        }

    def _get_cached_payment_status(self, checking_id: str) -> PaymentStatus | None:
        cached = self.payment_status_cache.get(checking_id)
        if not cached:
            return None
        if cached["expires_at"] <= time.time():
            self.payment_status_cache.pop(checking_id, None)
            return None
        return cached["status"]

    # ── Pending invoice helpers ────────────────────────────────────

    def _track_pending_invoice(
        self, checking_id: str, created_at: int, expires_at: int
    ) -> None:
        invoice = self.pending_invoice_details.get(checking_id, {})
        invoice["checking_id"] = checking_id
        invoice["created_at"] = created_at
        invoice["expires_at"] = expires_at
        invoice.setdefault("lookup_attempts", 0)
        invoice.setdefault("last_lookup_at", 0.0)
        self.pending_invoice_details[checking_id] = invoice
        if checking_id not in self.pending_invoices:
            self.pending_invoices.append(checking_id)
        if "next_lookup_at" not in invoice:
            self._schedule_next_lookup(invoice, created_at)

    def _remove_pending_invoice(self, checking_id: str) -> bool:
        self.pending_invoice_details.pop(checking_id, None)
        if checking_id in self.pending_invoices:
            self.pending_invoices.remove(checking_id)
            return True
        return False

    def _schedule_next_lookup(self, invoice: dict, now: float | None = None) -> None:
        now = now or time.time()
        attempt = int(invoice.get("lookup_attempts", 0))
        delay = self.lookup_backoff_schedule[
            min(attempt, len(self.lookup_backoff_schedule) - 1)
        ]
        jitter = random.uniform(0, min(15, max(1, delay * 0.1)))  # noqa: S311
        invoice["next_lookup_at"] = now + delay + jitter

    def _expire_pending_invoices(self, now: float) -> None:
        expired = []
        for cid in list(self.pending_invoices):
            invoice = self.pending_invoice_details.get(cid, {})
            expires_at = int(invoice.get("expires_at", 0) or 0)
            if expires_at and now > expires_at:
                expired.append(cid)
        for cid in expired:
            self._remove_pending_invoice(cid)


class BlinkGrafqlQueries(BaseModel):
    balance_query: str
    invoice_query: str
    payment_query: str
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
