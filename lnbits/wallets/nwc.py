import asyncio
import base64
import hashlib
import hmac
import json
import random
import secrets
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, cast
from urllib.parse import parse_qs, unquote, urlparse

from bolt11 import decode as bolt11_decode
from coincurve import PrivateKey, PublicKey
from Cryptodome.Cipher import ChaCha20
from Cryptodome.Hash import HMAC, SHA256
from loguru import logger
from websockets import connect as ws_connect

from lnbits.settings import settings
from lnbits.utils.nostr import (
    decrypt_content,
    encrypt_content,
    json_dumps,
    sign_event,
    verify_event,
)

from .base import (
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    StatusResponse,
    Wallet,
)


class NWCError(Exception):
    """
    An exception from NWC
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(self.__str__())

    def __str__(self):
        return f"{self.code} {self.message}"


NWC_ENCRYPTION_NIP04 = "nip04"
NWC_ENCRYPTION_NIP44_V2 = "nip44_v2"
NWC_SUPPORTED_ENCRYPTIONS = [NWC_ENCRYPTION_NIP44_V2, NWC_ENCRYPTION_NIP04]
NWC_NOTIFICATION_KIND_NIP04 = 23196
NWC_NOTIFICATION_KIND_NIP44 = 23197


def _normalize_supported_encryptions(encryptions: list[str]) -> list[str]:
    normalized = [enc for enc in encryptions if enc in NWC_SUPPORTED_ENCRYPTIONS]
    return normalized or [NWC_ENCRYPTION_NIP04]


def _choose_preferred_encryption(encryptions: list[str]) -> str:
    supported = set(_normalize_supported_encryptions(encryptions))
    for encryption in NWC_SUPPORTED_ENCRYPTIONS:
        if encryption in supported:
            return encryption
    return NWC_ENCRYPTION_NIP04


class NWCWallet(Wallet):
    """
    A funding source that connects to a Nostr Wallet Connect (NWC) service provider.
    https://nwc.dev/
    """

    def __init__(self):
        super().__init__()
        self.shutdown = False
        nwc_data = parse_nwc(settings.nwc_pairing_url)
        self.conn = NWCConnection(
            nwc_data["pubkey"],
            nwc_data["secret"],
            nwc_data["relay"],
            notification_handler=self._handle_notification,
        )
        self.pending_invoice_details: dict[str, dict[str, Any]] = {}
        self.payment_status_cache: dict[str, dict[str, Any]] = {}
        self.payment_status_cache_pending_ttl = 30
        self.payment_status_cache_terminal_ttl = 60 * 60 * 24
        self.transactions_refresh_interval = 30
        self.transactions_refresh_max_age = 60 * 60 * 24 * 15
        self.transactions_refresh_max_pages = 20
        self.transactions_refresh_lock = asyncio.Lock()
        self.last_transactions_refresh_at: dict[bool, float] = {}
        self.pending_invoices_maintenance_interval = 5
        self.notification_lookup_schedule = [60, 120, 300, 600, 1200, 1800]
        self.lookup_only_schedule = [15, 30, 60, 120, 300, 600, 1200, 1800]
        self.pending_invoices_lookup_cooldown = 1.0
        self.pending_invoices_reconcile_interval = 180
        self.next_reconcile_at = 0.0
        self.last_connection_generation = -1
        self.paid_invoices_queue = asyncio.Queue(0)

    def _is_shutting_down(self) -> bool:
        """
        Returns True if the wallet is shutting down.
        """
        return self.shutdown or not settings.lnbits_running

    async def _handle_notification(self, notification: dict[str, Any]):
        notification_type = notification.get("notification_type")
        notification_payload = notification.get("notification") or {}
        if not isinstance(notification_payload, dict):
            logger.warning(
                "Ignoring malformed NWC notification payload: "
                + str(notification_payload)
            )
            return

        if notification_type == "payment_received":
            checking_id = str(notification_payload.get("payment_hash") or "")
            if checking_id:
                logger.debug(
                    "Received NWC payment_received notification for " + checking_id
                )
                self._cache_payment_data(checking_id, notification_payload)
                self._mark_invoice_settled(checking_id, source="notification")
        elif notification_type == "payment_sent":
            checking_id = str(notification_payload.get("payment_hash") or "")
            if checking_id:
                logger.debug(
                    "Received NWC payment_sent notification for " + checking_id
                )
                payment_data = dict(notification_payload)
                payment_data.setdefault("state", "settled")
                payment_data.setdefault("settled_at", int(time.time()))
                self._cache_payment_data(checking_id, payment_data)
        elif notification_type == "hold_invoice_accepted":
            logger.debug(
                "Received NWC hold_invoice_accepted notification for "
                + str(notification_payload.get("payment_hash") or "")
            )
        elif notification_type:
            logger.debug(
                "Ignoring unsupported NWC notification type " + notification_type
            )

    def _get_lookup_schedule(self) -> list[int]:
        if self.conn.supports_notification_type("payment_received"):
            return self.notification_lookup_schedule
        return self.lookup_only_schedule

    def _schedule_next_lookup(self, invoice: dict[str, Any], now: float | None = None):
        now = now or time.time()
        schedule = self._get_lookup_schedule()
        attempt = int(invoice.get("lookup_attempts", 0))
        delay = schedule[min(attempt, len(schedule) - 1)]
        jitter = random.uniform(0, min(15, max(1, delay * 0.1)))  # noqa: S311
        invoice["next_lookup_at"] = now + delay + jitter

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
        self.next_reconcile_at = 0.0

    def _remove_pending_invoice(self, checking_id: str) -> bool:
        self.pending_invoice_details.pop(checking_id, None)
        if checking_id in self.pending_invoices:
            self.pending_invoices.remove(checking_id)
            return True
        return False

    def _mark_invoice_settled(self, checking_id: str, source: str):
        was_pending = self._remove_pending_invoice(checking_id)
        if was_pending:
            logger.debug("Pending invoice " + checking_id + " settled via " + source)
            self.paid_invoices_queue.put_nowait(checking_id)

    def _expire_pending_invoices(self, now: float):
        expired_ids: list[str] = []
        for checking_id in list(self.pending_invoices):
            invoice = self.pending_invoice_details.get(checking_id, {})
            expires_at = int(invoice.get("expires_at", 0) or 0)
            if expires_at and now > expires_at:
                logger.warning("Pending invoice " + checking_id + " timed out")
                expired_ids.append(checking_id)
        for checking_id in expired_ids:
            self._remove_pending_invoice(checking_id)

    async def _should_run_reconciliation(self, now: float) -> bool:
        if now < self.next_reconcile_at:
            return False
        await self.conn.get_info()
        if not self.conn.supports_method("list_transactions"):
            self.next_reconcile_at = now + self.pending_invoices_reconcile_interval
            return False
        return True

    def _cache_ids(self, *extra_ids: str) -> set[str]:
        ids = {checking_id for checking_id in self.pending_invoices if checking_id}
        ids.update(checking_id for checking_id in extra_ids if checking_id)
        return ids

    async def _fetch_incoming_transactions(
        self,
        *,
        from_ts: int,
        now: float | None = None,
        cache_ids: set[str] | None = None,
        stop_when_found_ids: set[str] | None = None,
        unpaid: bool = False,
    ) -> list[dict[str, Any]]:
        now = now or time.time()
        await self.conn.get_info()
        if not self.conn.supports_method("list_transactions"):
            return []

        offset = 0
        limit = 20
        transactions: list[dict[str, Any]] = []
        remaining_ids = {
            checking_id for checking_id in (stop_when_found_ids or set()) if checking_id
        }

        while offset < limit * self.transactions_refresh_max_pages:
            result = await self.conn.call(
                "list_transactions",
                {
                    "from": from_ts,
                    "until": int(now),
                    "limit": limit,
                    "offset": offset,
                    "type": "incoming",
                    "unpaid": unpaid,
                },
            )
            page = result.get("transactions", [])
            tx_summary = [
                {
                    "payment_hash": tx.get("payment_hash"),
                    "state": tx.get("state"),
                    "settled_at": tx.get("settled_at"),
                    "expires_at": tx.get("expires_at"),
                }
                for tx in page
                if isinstance(tx, dict)
            ]
            logger.debug(
                "NWC list_transactions response. "
                f"from={from_ts} until={int(now)} offset={offset} "
                f"limit={limit} unpaid={unpaid} "
                f"count={len(page) if isinstance(page, list) else 'malformed'} "
                f"transactions={tx_summary} raw={result}"
            )
            if not isinstance(page, list) or not page:
                break

            for tx in page:
                if not isinstance(tx, dict):
                    continue
                checking_id = str(tx.get("payment_hash") or "")
                if checking_id and (cache_ids is None or checking_id in cache_ids):
                    self._cache_payment_data(checking_id, tx, cached_at=now)
                if checking_id:
                    remaining_ids.discard(checking_id)
                transactions.append(tx)

            if len(page) < limit:
                break
            if not remaining_ids and stop_when_found_ids:
                break
            offset += limit

        return transactions

    async def _reconcile_pending_invoices(self, now: float):
        try:
            await self.conn.get_info()
            if not self.conn.supports_method("list_transactions"):
                self.next_reconcile_at = now + self.pending_invoices_reconcile_interval
                return

            created_from = min(
                int(
                    self.pending_invoice_details.get(checking_id, {}).get(
                        "created_at", now
                    )
                )
                for checking_id in self.pending_invoices
            )
            from_ts = max(0, created_from - 60)
            matched = 0
            pending_ids = self._cache_ids()

            logger.debug(
                "Reconciling pending NWC invoices with list_transactions. "
                f"pending_count={len(self.pending_invoices)} from={from_ts}"
            )

            transactions = await self._fetch_incoming_transactions(
                from_ts=from_ts,
                now=now,
                cache_ids=pending_ids,
                stop_when_found_ids=pending_ids,
            )
            for tx in transactions:
                checking_id = str(tx.get("payment_hash") or "")
                if checking_id not in self.pending_invoices:
                    continue
                if self._payment_data_is_settled(tx):
                    self._mark_invoice_settled(checking_id, source="reconciliation")
                    matched += 1

            logger.debug(
                "NWC reconciliation complete. "
                f"matched={matched} remaining_pending={len(self.pending_invoices)}"
            )
        except Exception as e:
            logger.error("Error reconciling pending NWC invoices: " + str(e))
        finally:
            self.next_reconcile_at = now + self.pending_invoices_reconcile_interval

    async def _run_fallback_lookups(self, now: float):
        await self.conn.get_info()
        if not self.conn.supports_method("lookup_invoice"):
            return

        due_invoices = [
            self.pending_invoice_details[checking_id]
            for checking_id in self.pending_invoices
            if checking_id in self.pending_invoice_details
            and float(
                self.pending_invoice_details[checking_id].get("next_lookup_at", 0.0)
                or 0.0
            )
            <= now
        ]
        due_invoices.sort(key=lambda invoice: float(invoice.get("next_lookup_at", 0.0)))

        for index, invoice in enumerate(due_invoices):
            checking_id = str(invoice["checking_id"])
            if checking_id not in self.pending_invoices:
                continue
            try:
                payment_data = await self.conn.call(
                    "lookup_invoice", {"payment_hash": checking_id}
                )
                self._cache_payment_data(checking_id, payment_data, cached_at=now)
                invoice["last_lookup_at"] = now
                invoice["lookup_attempts"] = int(invoice.get("lookup_attempts", 0)) + 1
                if self._payment_data_is_settled(payment_data):
                    self._mark_invoice_settled(checking_id, source="lookup")
                    continue
                self._schedule_next_lookup(invoice, now)
            except NWCError as e:
                logger.warning(
                    "Error handling pending invoice via lookup. "
                    f"checking_id={checking_id} code={e.code} message={e.message}"
                )
                invoice["lookup_attempts"] = int(invoice.get("lookup_attempts", 0)) + 1
                if e.code == "RATE_LIMITED":
                    self.next_reconcile_at = max(
                        self.next_reconcile_at,
                        now + self.pending_invoices_reconcile_interval,
                    )
                self._schedule_next_lookup(invoice, now)
            except Exception as e:
                logger.error("Error handling pending invoice: " + str(e))
                invoice["lookup_attempts"] = int(invoice.get("lookup_attempts", 0)) + 1
                self._schedule_next_lookup(invoice, now)
            if (
                index < len(due_invoices) - 1
                and self.pending_invoices_lookup_cooldown > 0
                and not self._is_shutting_down()
            ):
                await asyncio.sleep(self.pending_invoices_lookup_cooldown)

    async def _maintain_pending_invoices(self):
        if not self.pending_invoices:
            return

        now = time.time()
        if self.conn.connection_generation != self.last_connection_generation:
            self.last_connection_generation = self.conn.connection_generation
            self.next_reconcile_at = 0.0

        self._expire_pending_invoices(now)
        if not self.pending_invoices:
            return

        if await self._should_run_reconciliation(now):
            await self._reconcile_pending_invoices(now)

        await self._run_fallback_lookups(now)
        self._prune_payment_status_cache(self._cache_ids())

    def _payment_data_is_settled(self, payment_data: dict[str, Any]) -> bool:
        state = payment_data.get("state")
        settled_at = payment_data.get("settled_at")
        preimage = payment_data.get("preimage")
        if state == "settled":
            return True
        return bool(settled_at and int(settled_at) > 0 and preimage)

    def _payment_data_is_failed(self, payment_data: dict[str, Any]) -> bool:
        state = payment_data.get("state")
        if state in {"expired", "failed"}:
            return True
        created_at = int(payment_data.get("created_at", time.time()))
        expires_at = int(payment_data.get("expires_at", created_at + 3600))
        return bool(
            expires_at
            and time.time() > expires_at
            and not self._payment_data_is_settled(payment_data)
        )

    def _payment_data_to_status(self, payment_data: dict[str, Any]) -> PaymentStatus:
        fee_msat = payment_data.get("fees_paid", None)
        preimage = payment_data.get("preimage", None)
        if self._payment_data_is_settled(payment_data):
            return PaymentStatus(True, fee_msat=fee_msat, preimage=preimage)
        if self._payment_data_is_failed(payment_data):
            return PaymentStatus(False, fee_msat=fee_msat, preimage=preimage)
        return PaymentStatus(None, fee_msat=fee_msat, preimage=preimage)

    def _cache_payment_data(
        self,
        checking_id: str,
        payment_data: dict[str, Any],
        cached_at: float | None = None,
    ) -> None:
        cached_at = cached_at or time.time()
        ttl = (
            self.payment_status_cache_terminal_ttl
            if self._payment_data_is_settled(payment_data)
            or self._payment_data_is_failed(payment_data)
            else self.payment_status_cache_pending_ttl
        )
        self.payment_status_cache[checking_id] = {
            "payment_data": dict(payment_data),
            "expires_at": cached_at + ttl,
        }

    def _prune_payment_status_cache(self, keep_ids: set[str] | None = None) -> None:
        now = time.time()
        for checking_id in list(self.payment_status_cache.keys()):
            cached = self.payment_status_cache.get(checking_id) or {}
            expires_at = float(cached.get("expires_at", 0.0) or 0.0)
            if expires_at <= now or (
                keep_ids is not None and checking_id not in keep_ids
            ):
                self.payment_status_cache.pop(checking_id, None)

    def _get_cached_payment_data(self, checking_id: str) -> dict[str, Any] | None:
        cached = self.payment_status_cache.get(checking_id)
        if not cached:
            return None
        if float(cached.get("expires_at", 0.0) or 0.0) <= time.time():
            self.payment_status_cache.pop(checking_id, None)
            return None
        payment_data = cached.get("payment_data")
        if isinstance(payment_data, dict):
            return payment_data
        return None

    async def _refresh_recent_incoming_transactions(
        self,
        *,
        now: float | None = None,
        from_ts: int | None = None,
        cache_ids: set[str] | None = None,
        stop_when_found_ids: set[str] | None = None,
        unpaid: bool = True,
        force: bool = False,
    ) -> None:
        now = now or time.time()
        last_refresh_at = self.last_transactions_refresh_at.get(unpaid, 0.0)
        if not force and now - last_refresh_at < self.transactions_refresh_interval:
            return

        async with self.transactions_refresh_lock:
            now = time.time()
            last_refresh_at = self.last_transactions_refresh_at.get(unpaid, 0.0)
            if not force and now - last_refresh_at < self.transactions_refresh_interval:
                return

            from_ts = from_ts or max(0, int(now - self.transactions_refresh_max_age))

            logger.debug(
                "Refreshing recent NWC incoming transactions cache. "
                f"from={from_ts} max_pages={self.transactions_refresh_max_pages}"
            )

            await self._fetch_incoming_transactions(
                from_ts=from_ts,
                now=now,
                cache_ids=cache_ids,
                stop_when_found_ids=stop_when_found_ids,
                unpaid=unpaid,
            )
            self.last_transactions_refresh_at[unpaid] = now

    async def cleanup(self):
        self.shutdown = True
        await self.conn.close()

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **_,
    ) -> InvoiceResponse:
        desc = ""
        desc_hash = None
        if description_hash:
            desc_hash = description_hash.hex()
            desc = (unhashed_description or b"").decode()
        elif unhashed_description:
            desc = unhashed_description.decode()
            desc_hash = hashlib.sha256(desc.encode()).hexdigest()
        else:
            desc = memo or ""
        try:
            await self.conn.get_info()
            if not self.conn.supports_method("make_invoice"):
                return InvoiceResponse(
                    ok=False,
                    error_message="make_invoice is not supported by this NWC service.",
                )
            resp = await self.conn.call(
                "make_invoice",
                {
                    "amount": int(amount * 1000),  # nwc uses msats denominations
                    "description_hash": desc_hash,
                    "description": desc,
                },
            )
            checking_id = str(resp["payment_hash"])
            payment_request = resp.get("invoice", None)
            created_at = int(resp.get("created_at", time.time()))
            expires_at = int(resp.get("expires_at", created_at + 3600))
            if (
                self.conn.supports_method("lookup_invoice")
                or self.conn.supports_method("list_transactions")
                or self.conn.supports_notification_type("payment_received")
            ):
                self._track_pending_invoice(checking_id, created_at, expires_at)
            return InvoiceResponse(
                ok=True, checking_id=checking_id, payment_request=payment_request
            )
        except Exception as e:
            return InvoiceResponse(ok=False, error_message=str(e))

    async def status(self) -> StatusResponse:
        try:
            await self.conn.get_info()
            if not self.conn.supports_method("get_balance"):
                logger.debug("get_balance is not supported by this NWC service.")
                return StatusResponse(None, 0)
            resp = await self.conn.call("get_balance", {})
            balance = int(resp["balance"])
            return StatusResponse(None, balance)
        except Exception as e:
            return StatusResponse(str(e), 0)

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            resp = await self.conn.call("pay_invoice", {"invoice": bolt11})
            preimage = resp.get("preimage", None)
            invoice_data = bolt11_decode(bolt11)
            payment_hash = invoice_data.payment_hash
            # pay_invoice doesn't return payment data, so we need
            # to call lookup_invoice too (if supported)
            await self.conn.get_info()

            if not self.conn.supports_method("lookup_invoice"):
                # if not supported, we assume it succeeded
                return PaymentResponse(
                    ok=True, checking_id=payment_hash, preimage=preimage, fee_msat=0
                )

            try:
                payment_data = await self.conn.call(
                    "lookup_invoice", {"invoice": bolt11}
                )
                settled = payment_data.get("settled_at", None) and payment_data.get(
                    "preimage", None
                )
                if not settled:
                    return PaymentResponse(checking_id=payment_hash)
                else:
                    fee_msat = payment_data.get("fees_paid", None)
                    return PaymentResponse(
                        ok=True,
                        checking_id=payment_hash,
                        fee_msat=fee_msat,
                        preimage=preimage,
                    )
            except Exception:
                # Workaround: some nwc service providers might not store the invoice
                # right away, so this call may raise an exception.
                # We will assume the payment is pending anyway
                return PaymentResponse(checking_id=payment_hash)
        except NWCError as e:
            logger.error("Error paying invoice: " + str(e))
            failure_codes = [
                "RATE_LIMITED",
                "NOT_IMPLEMENTED",
                "INSUFFICIENT_BALANCE",
                "QUOTA_EXCEEDED",
                "RESTRICTED",
                "UNAUTHORIZED",
                "INTERNAL",
                "OTHER",
                "PAYMENT_FAILED",
            ]
            failed = e.code in failure_codes
            return PaymentResponse(
                ok=None if not failed else False,
                error_message=e.message if failed else None,
            )
        except Exception as e:
            msg = "Error paying invoice: " + str(e)
            logger.error(msg)
            # assume pending
            return PaymentResponse(error_message=msg)

    async def _get_status_via_transactions(
        self, checking_id: str, unpaid_filters: list[bool]
    ) -> PaymentStatus | None:
        keep_ids = self._cache_ids(checking_id)
        self._prune_payment_status_cache()
        payment_data = self._get_cached_payment_data(checking_id)
        if payment_data:
            return self._payment_data_to_status(payment_data)

        if self.conn.supports_method("list_transactions"):
            invoice_details = self.pending_invoice_details.get(checking_id, {})
            created_at_hint = int(
                invoice_details.get(
                    "created_at", time.time() - self.transactions_refresh_max_age
                )
            )
            from_ts = max(0, created_at_hint - 60)

            for unpaid in unpaid_filters:
                await self._refresh_recent_incoming_transactions(
                    from_ts=from_ts,
                    cache_ids=None,
                    stop_when_found_ids=keep_ids,
                    unpaid=unpaid,
                )
                payment_data = self._get_cached_payment_data(checking_id)
                if payment_data:
                    return self._payment_data_to_status(payment_data)

        if self.conn.supports_method("lookup_invoice"):
            payment_data = await self.conn.call(
                "lookup_invoice", {"payment_hash": checking_id}
            )
            self._cache_payment_data(checking_id, payment_data)
            return self._payment_data_to_status(payment_data)

        return None

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            await self.conn.get_info()
            status = await self._get_status_via_transactions(checking_id, [True, False])
            return status or PaymentStatus(None, fee_msat=None, preimage=None)
        except NWCError as e:
            logger.error("Error getting invoice status: " + str(e))
            failed = e.code == "NOT_FOUND"
            return PaymentStatus(
                None if not failed else False, fee_msat=None, preimage=None
            )
        except Exception as e:
            logger.error("Error getting invoice status: " + str(e))
            return PaymentStatus(None, fee_msat=None, preimage=None)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            await self.conn.get_info()
            status = await self._get_status_via_transactions(checking_id, [False])
            return status or PaymentStatus(None, fee_msat=None, preimage=None)
        except NWCError as e:
            logger.error("Error getting payment status: " + str(e))
            failed = e.code == "NOT_FOUND"
            return PaymentStatus(
                None if not failed else False, fee_msat=None, preimage=None
            )
        except Exception as e:
            logger.error("Error getting payment status: " + str(e))
            # assume pending (eg. exception due to network error)
            return PaymentStatus(None, fee_msat=None, preimage=None)

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        while not self._is_shutting_down():
            try:
                value = await asyncio.wait_for(
                    self.paid_invoices_queue.get(),
                    timeout=self.pending_invoices_maintenance_interval,
                )
                yield value
            except asyncio.TimeoutError:
                await self._maintain_pending_invoices()


class NWCConnection:
    """
    A connection to a Nostr Wallet Connect (NWC) service provider.
    """

    def __init__(
        self,
        pubkey,
        secret,
        relay,
        notification_handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ):
        # Parse pairing url (if invalid an exception is raised)

        # Extract keys (used to sign nwc events+identify NWC user)
        self.account_private_key = PrivateKey(bytes.fromhex(secret))
        self.account_private_key_hex = secret
        self.account_public_key = self.account_private_key.public_key
        if not self.account_public_key:
            raise ValueError("Missing account public key")
        self.account_public_key_hex = self.account_public_key.format().hex()[2:]

        # Extract service key (used for encryption to identify the nwc service provider)
        self.service_pubkey = PublicKey(bytes.fromhex("02" + pubkey))
        self.service_pubkey_hex = pubkey

        # Extract relay url
        self.relay = relay

        # Create temporary subscriptions, stored until the response is received/expires
        self.subscriptions: dict[str, dict[str, Any]] = {}
        # Timeout in seconds after which a subscription is closed
        # if no response is received
        self.subscription_timeout = 10
        # Incremental counter to generate unique subscription ids for the connection
        self.subscriptions_count = 0

        # websocket connection
        self.ws = None
        # if True the websocket is connected
        self.connected = False
        # if True the connection is shutting down
        self.shutdown = False

        # cached info about the service provider
        self.info: dict[str, Any] | None = None
        self.supported_methods: set[str] = set()
        self.notification_types: set[str] = set()
        self.supported_encryptions = [NWC_ENCRYPTION_NIP04]
        self.selected_encryption = NWC_ENCRYPTION_NIP04
        self.advertises_encryption_tag = False
        self.notification_handler = notification_handler
        self.notification_subscription_ids: set[str] = set()
        self.connection_generation = 0

        # This task handles connection and reconnection to the relay
        self.connection_task = asyncio.create_task(self._connect_to_relay())

        # This task periodically checks and removes subscriptions
        # and pending payments that have timed out
        self.timeout_task = asyncio.create_task(self._handle_timeouts())

        logger.info(
            "NWCConnection is ready. relay: "
            + self.relay
            + " account: "
            + self.account_public_key_hex
            + " service: "
            + self.service_pubkey_hex
        )

    def _is_shutting_down(self) -> bool:
        """
        Returns True if the connection is shutting down.
        """
        return self.shutdown or not settings.lnbits_running

    async def _send(self, data: list[str | dict]):
        """
        Sends data to the NWC relay.

        Args:
            data (Dict): The data to be sent.
        """
        if self._is_shutting_down():
            logger.warning("Trying to send data while shutting down")
            return
        if not self.ws:
            logger.warning("Trying to send data without a connection")
            return
        await self._wait_for_connection()  # ensure the connection is established
        tx = json_dumps(data)
        logger.debug("Sending raw NWC relay message: " + tx)
        await self.ws.send(tx)

    def _get_new_subid(self) -> str:
        """
        Generates a unique subscription id.

        Returns:
            str: The generated 64 characters long subscription id (eg. lnbits0abc...)
        """
        subid = "lnbits" + str(self.subscriptions_count)
        self.subscriptions_count += 1
        max_length = 64
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        n = max_length - len(subid)
        if n > 0:
            for _ in range(n):
                subid += chars[random.randint(0, len(chars) - 1)]  # noqa: S311
        return subid

    async def _close_subscription_by_subid(
        self, sub_id: str, send_event: bool = True
    ) -> dict | None:
        """
        Closes a subscription by its sub_id.

        Args:
            sub_id (str): The subscription id.
            sendEvent (bool): If True, sends a CLOSE event to the relay.

        Returns:
            Dict: The subscription that was closed.
        """
        logger.debug("Closing subscription " + sub_id)
        sub_to_close = None
        for subscription in self.subscriptions.values():
            if subscription["sub_id"] == sub_id:
                sub_to_close = subscription
                break
        # remove the subscription from the list
        if sub_to_close:
            self.subscriptions.pop(sub_to_close["event_id"], None)
            self.notification_subscription_ids.discard(sub_id)
            if not sub_to_close["closed"]:
                sub_to_close["closed"] = True
                if send_event:
                    try:
                        await self._send(["CLOSE", sub_id])
                    except Exception as e:
                        logger.error("Error closing subscription: " + str(e))
        return sub_to_close

    async def _close_subscription_by_eventid(
        self, event_id, send_event=True
    ) -> dict | None:
        """
        Closes a subscription associated to an event_id.

        Args:
            event_id (str): The event id associated to the subscription.
            sendEvent (bool): If True, sends a CLOSE event to the relay.

        Returns:
            Dict: The subscription that was closed.
        """
        logger.debug("Closing subscription for event " + event_id)
        # find and remove the subscription
        subscription = self.subscriptions.pop(event_id, None)
        if subscription:
            if not subscription["closed"]:
                subscription["closed"] = True
                self.notification_subscription_ids.discard(subscription["sub_id"])
                if send_event:
                    try:
                        await self._send(["CLOSE", subscription["sub_id"]])
                    except Exception as e:
                        logger.error("Error closing subscription: " + str(e))
        return subscription

    async def _wait_for_connection(self, timeout: int = 60 * 2):
        """
        Waits until the connection is ready
        """
        t = time.time()
        while not self.connected:
            if time.time() - t > timeout:
                raise Exception("Connection timeout, cannot connect to NWC service")
            if self._is_shutting_down():
                raise Exception("Connection is closing")
            logger.debug("Waiting for connection...")
            await asyncio.sleep(1)

    async def _handle_timeouts(self):
        """
        Periodically checks if any subscriptions and pending
        payments have timed out, and removes them.
        """
        try:
            while not self._is_shutting_down():
                try:
                    await asyncio.sleep(int(self.subscription_timeout * 0.5))
                    # skip if connection is not established
                    if not self.connected:
                        continue
                    # Find all subscriptions that have timed out
                    now = time.time()
                    subscriptions_to_close = []
                    for subscription in self.subscriptions.values():
                        if subscription["method"] == "notification_sub":
                            continue
                        t = now - subscription["timestamp"]
                        if t > self.subscription_timeout:
                            logger.warning(
                                "Subscription " + subscription["sub_id"] + " timed out"
                            )
                            subscriptions_to_close.append(subscription["sub_id"])
                            # if not already closed, pass the "time out"
                            # exception to the future
                            if not subscription["closed"]:
                                subscription["future"].set_exception(
                                    Exception("timed out")
                                )
                    # Close all timed out subscriptions
                    for sub_id in subscriptions_to_close:
                        await self._close_subscription_by_subid(sub_id)
                except Exception as e:
                    logger.error("Error handling subscription timeout: " + str(e))
        except Exception as e:
            logger.error("Error handling subscription timeout: " + str(e))

    async def _on_ok_message(self, msg: list[str]):
        """
        Handles OK messages from the relay.
        """
        event_id = msg[1]
        status = msg[2]
        info = (msg[3] or "") if len(msg) > 3 else ""
        if not status:
            # close subscription and pass an exception
            # if the event was rejected by the relay
            subscription = await self._close_subscription_by_eventid(event_id)
            if subscription:  # Check if the subscription exists first
                subscription["future"].set_exception(Exception(info))

    async def _on_event_message(self, msg: list[str | dict]):  # noqa: C901
        """
        Handles EVENT messages from the relay.
        """
        sub_id = cast(str, msg[1])
        event = cast(dict, msg[2])
        # Ensure the event is valid and comes from the configured service
        # provider (do not trust relays).
        if not verify_event(event) or event.get("pubkey") != self.service_pubkey_hex:
            raise Exception("Invalid event signature")
        tags = event["tags"]
        if event["kind"] == 13194:  # An info event
            # info events are handled specially,
            # they are stored in the subscriptions list
            # using the subscription id for both sub_id and event_id
            subscription = await self._close_subscription_by_eventid(
                sub_id
            )  # sub_id is the event_id for info events
            if subscription:  # Check if the subscription exists first
                if (
                    subscription["method"] != "info_sub"
                ):  # Ensure the subscription is for an info event
                    raise Exception("Unexpected info event")
                # create an info dictionary with the supported
                # methods that is passed to the future
                content = event["content"]
                subscription["future"].set_result(
                    self._normalize_info(
                        {
                            "supported_methods": content.split(" "),
                            "notification_types": self._get_tag_values(
                                tags, "notifications"
                            ),
                            "supported_encryptions": self._get_tag_values(
                                tags, "encryption"
                            ),
                        }
                    )
                )
        elif event["kind"] in (23196, 23197):
            await self._on_notification_event(event)
        else:  # A response event
            subscription = None
            # find the first "e" tag that is handled by
            # a registered subscription
            # Note: usually we expect only one "e" tag, but we are
            # handling multiple "e" tags just in case
            for tag in tags:
                if tag[0] == "e":
                    subscription = await self._close_subscription_by_eventid(tag[1])
                    if subscription:
                        break
            # if a subscription was found, pass the result to the future
            if subscription:
                try:
                    content = self._decrypt_event_content(event)
                    content = json.loads(content)
                except Exception as e:
                    logger.error(
                        "Failed to decode NWC response event. "
                        f"kind={event.get('kind')} id={event.get('id')} "
                        f"tags={event.get('tags', [])} "
                        f"ciphertext={event.get('content')} error={e}"
                    )
                    raise
                result_type = content.get("result_type", "")
                error = content.get("error", None)
                result = content.get("result", None)
                if error:  # if an error occurred, pass the error to the future
                    nwc_exception = NWCError(error["code"], error["message"])
                    subscription["future"].set_exception(nwc_exception)
                else:
                    # ensure the result is for the expected method
                    if result_type != subscription["method"]:
                        raise Exception("Unexpected result type")
                    if not result:
                        raise Exception("Malformed response")
                    else:
                        subscription["future"].set_result(result)

    async def _on_notification_event(self, event: dict[str, Any]):
        if event.get("pubkey") != self.service_pubkey_hex:
            logger.warning(
                "Ignoring NWC notification from unexpected pubkey "
                + str(event.get("pubkey"))
            )
            return

        if not self.notification_handler:
            return

        try:
            content = self._decrypt_event_content(event)
            notification = json.loads(content)
        except Exception as e:
            logger.error(
                "Failed to decode NWC notification event. "
                f"kind={event.get('kind')} id={event.get('id')} "
                f"tags={event.get('tags', [])} "
                f"ciphertext={event.get('content')} error={e}"
            )
            raise
        await self.notification_handler(notification)

    async def _on_closed_message(self, msg: list[str]):
        """
        Handles CLOSED messages from the relay.
        """
        # The change is reflected in the subscriptions list.
        sub_id = msg[1]
        info = msg[2] or ""
        if info:
            logger.warning("Subscription " + sub_id + " closed remotely: " + info)
        # Note: sendEvent=false because the action was initiated by the relay
        await self._close_subscription_by_subid(sub_id, send_event=False)

    async def _on_message(self, ws, message: str):
        """
        Handle incoming messages from the relay.
        """
        try:
            logger.debug("Received raw NWC relay message: " + message)
            msg = json.loads(message)
            if msg[0] == "OK":  # Event status message
                await self._on_ok_message(msg)
            elif msg[0] == "EVENT":  # Event message
                await self._on_event_message(msg)
            elif msg[0] == "EOSE":
                # Do nothing. No need to handle this message type for NWC
                pass
            elif msg[0] == "CLOSED":
                # Subscription was closed remotely.
                await self._on_closed_message(msg)
            elif msg[0] == "NOTICE":
                # A message from the relay, mostly useless, but we log it anyway
                logger.info("Notice from relay " + self.relay + ": " + str(msg[1]))
            else:
                raise Exception("Unknown message type")
        except Exception as e:
            logger.error("Error parsing event: " + str(e))

    async def _connect_to_relay(self):
        """
        Initiate websocket connection to the relay.
        """
        logger.debug("Connecting to NWC relay " + self.relay)
        while (
            not self._is_shutting_down()
        ):  # Reconnect until the connection is shutting down
            logger.debug("Creating new connection...")
            try:
                async with ws_connect(self.relay) as ws:
                    self.ws = ws
                    self.connected = True
                    self.connection_generation += 1
                    self.notification_subscription_ids = set()
                    await self._subscribe_to_notifications()
                    while (
                        not self._is_shutting_down()
                    ):  # receive messages until the connection is shutting down
                        try:
                            reply = await ws.recv()
                            reply_str = ""
                            if isinstance(reply, bytes):
                                reply_str = reply.decode("utf-8")
                            else:
                                reply_str = reply
                            await self._on_message(ws, reply_str)
                        except Exception as e:
                            logger.debug("Error receiving message: " + str(e))
                            break
                logger.debug("Connection to NWC relay closed")
            except Exception as e:
                logger.error("Error connecting to NWC relay: " + str(e))
            # the connection was closed, so we set the connected flag to False
            # this will make the methods calling _wait_for_connection()
            # to wait until the connection is re-established
            self.connected = False
            if not self._is_shutting_down():
                # Wait some time before reconnecting
                logger.debug("Reconnecting to NWC relay in 5 seconds...")
                await asyncio.sleep(5)

    async def _subscribe_to_notifications(self):
        for kind in (23197, 23196):
            sub_id = self._get_new_subid()
            sub_filter = {
                "kinds": [kind],
                "authors": [self.service_pubkey_hex],
                "#p": [self.account_public_key_hex],
                "since": int(time.time()),
            }
            future = asyncio.get_event_loop().create_future()
            self.subscriptions[sub_id] = {
                "method": "notification_sub",
                "future": future,
                "sub_id": sub_id,
                "event_id": sub_id,
                "timestamp": time.time(),
                "closed": False,
            }
            self.notification_subscription_ids.add(sub_id)
            await self._send(["REQ", sub_id, sub_filter])

    def _get_tag_values(self, tags: list[list[str]], tag_name: str) -> list[str]:
        for tag in tags:
            if tag and tag[0] == tag_name and len(tag) > 1:
                return [value for value in tag[1].split(" ") if value]
        return []

    def supports_notification_type(self, notification_type: str) -> bool:
        return notification_type in self.notification_types

    def supports_method(self, method: str) -> bool:
        return method in self.supported_methods

    def _normalize_info(self, info: dict[str, Any]) -> dict[str, Any]:
        methods = info.get("supported_methods", []) or []
        notifications = info.get("notification_types", []) or []
        encryptions = _normalize_supported_encryptions(
            info.get("supported_encryptions", []) or []
        )
        normalized = {
            "supported_methods": [method for method in methods if method],
            "notification_types": [
                notification for notification in notifications if notification
            ],
            "supported_encryptions": encryptions,
        }
        return normalized

    def _apply_capabilities(self, info: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_info(info)
        self.supported_methods = set(normalized["supported_methods"])
        self.notification_types = set(normalized["notification_types"])
        self.supported_encryptions = normalized["supported_encryptions"]
        self.advertises_encryption_tag = bool(info.get("supported_encryptions"))
        self.selected_encryption = _choose_preferred_encryption(
            normalized["supported_encryptions"]
        )
        logger.debug(
            "Negotiated NWC provider capabilities. "
            f"supported_encryptions={self.supported_encryptions} "
            f"selected_encryption={self.selected_encryption} "
            f"advertises_encryption_tag={self.advertises_encryption_tag} "
            f"supported_methods={sorted(self.supported_methods)} "
            f"notification_types={sorted(self.notification_types)}"
        )
        return normalized

    def _get_event_encryption(self, event: dict[str, Any]) -> str:
        encryption_tag = self._get_tag_values(event.get("tags", []), "encryption")
        if encryption_tag:
            return _choose_preferred_encryption(encryption_tag)
        if event.get("kind") == NWC_NOTIFICATION_KIND_NIP44:
            return NWC_ENCRYPTION_NIP44_V2
        if event.get("kind") == NWC_NOTIFICATION_KIND_NIP04:
            return NWC_ENCRYPTION_NIP04
        return (
            self.selected_encryption
            if self.selected_encryption
            else NWC_ENCRYPTION_NIP04
        )

    def _encrypt_payload(self, content: str) -> tuple[str, str]:
        encryption = self.selected_encryption or NWC_ENCRYPTION_NIP04
        logger.debug(
            "Encrypting NWC payload. "
            f"encryption={encryption} plaintext={content}"
        )
        if encryption == NWC_ENCRYPTION_NIP44_V2:
            encrypted = NIP44Encryption.encrypt(
                content, self.service_pubkey, self.account_private_key_hex
            )
        else:
            encrypted = encrypt_content(
                content,
                self.service_pubkey,
                self.account_private_key_hex,
            )
            encryption = NWC_ENCRYPTION_NIP04
        logger.debug(
            "Encrypted NWC payload. "
            f"encryption={encryption} ciphertext={encrypted}"
        )
        return encrypted, encryption

    def _decrypt_event_content(self, event: dict[str, Any]) -> str:
        encryption = self._get_event_encryption(event)
        logger.debug(
            "Decrypting NWC event. "
            f"kind={event.get('kind')} id={event.get('id')} "
            f"encryption={encryption} tags={event.get('tags', [])} "
            f"ciphertext={event.get('content')}"
        )
        if encryption == NWC_ENCRYPTION_NIP44_V2:
            plaintext = NIP44Encryption.decrypt(
                event["content"], self.service_pubkey, self.account_private_key_hex
            )
        else:
            plaintext = decrypt_content(
                event["content"],
                self.service_pubkey,
                self.account_private_key_hex,
            )
        logger.debug(
            "Decrypted NWC event. "
            f"kind={event.get('kind')} id={event.get('id')} "
            f"encryption={encryption} plaintext={plaintext}"
        )
        return plaintext

    async def call(self, method: str, params: dict) -> dict:
        """
        Call a NWC method.

        Args:
            method (str): The method name.
            params (Dict): The method parameters.

        Returns:
            Dict: The result of the method call.
        """
        await self._wait_for_connection()
        logger.debug("Calling " + method + " with params: " + str(params))
        # Prepare the content
        content = json_dumps(
            {
                "method": method,
                "params": params,
            }
        )
        content, encryption = self._encrypt_payload(content)
        # Prepare the NWC event
        tags = [["p", self.service_pubkey_hex]]
        if encryption != NWC_ENCRYPTION_NIP04 or self.advertises_encryption_tag:
            tags.append(["encryption", encryption])
        logger.debug(
            "Using NWC provider encryption for request. "
            f"method={method} encryption={encryption} tags={tags}"
        )
        event = {
            "kind": 23194,
            "content": content,
            "created_at": int(time.time()),
            "tags": tags,
        }
        # Sign
        sign_event(event, self.account_public_key_hex, self.account_private_key)
        # Subscribe for a response to this event
        sub_filter = {
            "kinds": [23195],
            "authors": [self.service_pubkey_hex],
            "#p": [self.account_public_key_hex],
            "#e": [event["id"]],
            "since": event["created_at"],
        }
        sub_id = self._get_new_subid()
        # register a future to receive the response asynchronously
        future = asyncio.get_event_loop().create_future()
        event_id = cast(str, event["id"])
        # Check if the subscription already exists
        # (this means there is a bug somewhere, should not happen)
        if event_id in self.subscriptions:
            raise Exception("Subscription for this event id already exists?")
        # Store the subscription in the list
        self.subscriptions[event_id] = {
            "method": method,
            "future": future,
            "sub_id": sub_id,
            "event_id": event_id,
            "timestamp": time.time(),
            "closed": False,
        }
        # Send the events
        await self._send(["REQ", sub_id, sub_filter])
        await self._send(["EVENT", event])
        # Wait for the response
        return await future

    async def get_info(self) -> dict:
        """
        Get the info about the service provider and cache it.

        Returns:
            Dict: The info about the service provider.
        """
        if not self.info:  # if not cached
            try:
                await self._wait_for_connection()
                # Prepare filter to request the info note
                sub_filter = {"kinds": [13194], "authors": [self.service_pubkey_hex]}
                # We register a special subscription using the sub_id as the event_id
                sub_id = self._get_new_subid()
                future = asyncio.get_event_loop().create_future()
                self.subscriptions[sub_id] = {
                    "method": "info_sub",
                    "future": future,
                    "sub_id": sub_id,
                    "event_id": sub_id,
                    "timestamp": time.time(),
                    "closed": False,
                }
                # Send the request
                await self._send(["REQ", sub_id, sub_filter])
                # Wait for the response
                service_info = await future
                service_info = self._apply_capabilities(service_info)
                # Get account info when possible
                if self.supports_method("get_info"):
                    try:
                        account_info = await self.call("get_info", {})
                        # cache
                        info: dict[str, Any] = dict(service_info)
                        info["alias"] = account_info.get("alias", "")
                        info["color"] = account_info.get("color", "")
                        info["pubkey"] = account_info.get("pubkey", "")
                        info["network"] = account_info.get("network", "")
                        info["block_height"] = account_info.get("block_height", 0)
                        info["block_hash"] = account_info.get("block_hash", "")
                        info["supported_methods"] = account_info.get(
                            "methods",
                            service_info.get("supported_methods", ["pay_invoice"]),
                        )
                        info["notification_types"] = account_info.get(
                            "notifications",
                            service_info.get("notification_types", []),
                        )
                        info["supported_encryptions"] = service_info.get(
                            "supported_encryptions",
                            [NWC_ENCRYPTION_NIP04],
                        )
                        self.info = self._apply_capabilities(info)
                    except Exception as e:
                        # If there is an error, fallback to using service info
                        logger.error(
                            "Error getting account info: "
                            + str(e)
                            + " Using service info only"
                        )
                        self.info = service_info
                else:
                    # get_info is not supported,
                    # so we will make do with the service info
                    self.info = service_info  # cache
            except Exception as e:
                logger.error("Error getting info: " + str(e))
                # The error could mean that the service provider does
                # not provide an info note
                # So we just assume it supports the bare minimum to be Nip47 compliant
                self.info = self._apply_capabilities(
                    {
                        "supported_methods": ["pay_invoice"],
                        "notification_types": [],
                        "supported_encryptions": [NWC_ENCRYPTION_NIP04],
                    }
                )
        return self.info or {}

    async def close(self):
        logger.debug("Closing NWCConnection")
        self.shutdown = True  # Mark for shutdown
        # cancel all tasks
        try:
            self.timeout_task.cancel()
        except Exception as e:
            logger.warning("Error cancelling subscription timeout task: " + str(e))
        try:
            self.connection_task.cancel()
        except Exception as e:
            logger.warning("Error cancelling connection task: " + str(e))
        for sub_id in list(self.notification_subscription_ids):
            try:
                await self._send(["CLOSE", sub_id])
            except Exception as e:
                logger.warning("Error closing notification subscription: " + str(e))
        # close the websocket
        try:
            if self.ws:
                await self.ws.close()
        except Exception as e:
            logger.warning("Error closing connection: " + str(e))


def parse_nwc(nwc) -> dict:
    """
    Parses a NWC URL (nostr+walletconnect://...) and extracts relevant information.

    Args:
        nwc (str): The Nostr Wallet Connect URL to be parsed.

    Returns:
        Dict[str, str]: A dict containing:'pubkey', 'relay', and 'secret'.
        If the URL is invalid, an exception is raised.

    Example:
        >>> parse_nwc("nostr+walletconnect://000000...000000?relay=example.com&secret=123")
        {'pubkey': '000000...000000', 'relay': 'example.com', 'secret': '123'}
    """
    data = {}
    prefix = "nostr+walletconnect://"
    if nwc and nwc.startswith(prefix):
        nwc = nwc[len(prefix) :]
        parsed_url = urlparse(nwc)
        data["pubkey"] = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        for key, value in query_params.items():
            if key in ["relay", "secret"] and value:
                data[key] = unquote(value[0])
        if "pubkey" not in data or "relay" not in data or "secret" not in data:
            raise ValueError("Invalid NWC pairing url")
    else:
        raise ValueError("Invalid NWC pairing url")
    return data


class NIP44Encryption:
    @staticmethod
    def encrypt(
        content: str,
        service_pubkey: PublicKey,
        account_private_key_hex: str,
    ) -> str:
        conversation_key = NIP44Encryption._get_conversation_key(
            service_pubkey,
            account_private_key_hex,
        )
        nonce = secrets.token_bytes(32)
        chacha_key, chacha_nonce, hmac_key = NIP44Encryption._get_message_keys(
            conversation_key,
            nonce,
        )
        padded = NIP44Encryption._pad(content)
        ciphertext = ChaCha20.new(key=chacha_key, nonce=chacha_nonce).encrypt(padded)
        mac = HMAC.new(hmac_key, digestmod=SHA256)
        mac.update(nonce + ciphertext)
        payload = bytes([2]) + nonce + ciphertext + mac.digest()
        return base64.b64encode(payload).decode("ascii")

    @staticmethod
    def decrypt(
        content: str,
        service_pubkey: PublicKey,
        account_private_key_hex: str,
    ) -> str:
        if not content or content[0] == "#":
            raise ValueError("unknown encryption version")
        raw = base64.b64decode(content.encode("ascii"))
        if len(raw) < 99 or len(raw) > 65603:
            raise ValueError("invalid data size")
        version = raw[0]
        if version != 2:
            raise ValueError(f"unknown version {version}")
        nonce = raw[1:33]
        ciphertext = raw[33:-32]
        mac = raw[-32:]
        conversation_key = NIP44Encryption._get_conversation_key(
            service_pubkey,
            account_private_key_hex,
        )
        chacha_key, chacha_nonce, hmac_key = NIP44Encryption._get_message_keys(
            conversation_key,
            nonce,
        )
        expected_mac = HMAC.new(hmac_key, digestmod=SHA256)
        expected_mac.update(nonce + ciphertext)
        if not hmac.compare_digest(expected_mac.digest(), mac):
            raise ValueError("invalid MAC")
        padded = ChaCha20.new(key=chacha_key, nonce=chacha_nonce).decrypt(ciphertext)
        return NIP44Encryption._unpad(padded)

    @staticmethod
    def _get_shared_x(
        service_pubkey: PublicKey,
        account_private_key_hex: str,
    ) -> bytes:
        return service_pubkey.multiply(bytes.fromhex(account_private_key_hex)).format()[
            1:
        ]

    @staticmethod
    def _hkdf_extract(*, ikm: bytes, salt: bytes) -> bytes:
        return hmac.new(salt, ikm, hashlib.sha256).digest()

    @staticmethod
    def _hkdf_expand(*, prk: bytes, info: bytes, length: int) -> bytes:
        output = bytearray()
        previous = b""
        counter = 1
        while len(output) < length:
            previous = hmac.new(
                prk,
                previous + info + bytes([counter]),
                hashlib.sha256,
            ).digest()
            output.extend(previous)
            counter += 1
        return bytes(output[:length])

    @staticmethod
    def _get_conversation_key(
        service_pubkey: PublicKey,
        account_private_key_hex: str,
    ) -> bytes:
        return NIP44Encryption._hkdf_extract(
            ikm=NIP44Encryption._get_shared_x(service_pubkey, account_private_key_hex),
            salt=b"nip44-v2",
        )

    @staticmethod
    def _calc_padded_len(unpadded_len: int) -> int:
        if unpadded_len <= 32:
            return 32
        next_power = 1 << ((unpadded_len - 1).bit_length())
        chunk = 32 if next_power <= 256 else next_power // 8
        return chunk * (((unpadded_len - 1) // chunk) + 1)

    @staticmethod
    def _pad(content: str) -> bytes:
        plaintext = content.encode("utf-8")
        plaintext_len = len(plaintext)
        if plaintext_len < 1 or plaintext_len > 65535:
            raise ValueError("invalid plaintext length")
        padded_len = NIP44Encryption._calc_padded_len(plaintext_len)
        return (
            plaintext_len.to_bytes(2, "big")
            + plaintext
            + bytes(padded_len - plaintext_len)
        )

    @staticmethod
    def _unpad(padded: bytes) -> str:
        if len(padded) < 34:
            raise ValueError("invalid padded payload size")
        plaintext_len = int.from_bytes(padded[:2], "big")
        plaintext = padded[2 : 2 + plaintext_len]
        expected_len = 2 + NIP44Encryption._calc_padded_len(plaintext_len)
        if (
            plaintext_len < 1
            or len(plaintext) != plaintext_len
            or len(padded) != expected_len
        ):
            raise ValueError("invalid padding")
        return plaintext.decode("utf-8")

    @staticmethod
    def _get_message_keys(
        conversation_key: bytes, nonce: bytes
    ) -> tuple[bytes, bytes, bytes]:
        if len(conversation_key) != 32:
            raise ValueError("invalid conversation_key length")
        if len(nonce) != 32:
            raise ValueError("invalid nonce length")
        keys = NIP44Encryption._hkdf_expand(
            prk=conversation_key,
            info=nonce,
            length=76,
        )
        return keys[:32], keys[32:44], keys[44:76]
