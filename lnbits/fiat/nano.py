"""Nano (XNO) fiat provider for LNbits - the ``nano:mainnet`` exact scheme.

This is a non-Lightning settlement provider: a payer sends feeless, issuer-free
Nano directly to an address the operator configures, and the provider verifies
the payment by reading one confirmed block from a public node URL the operator
names. There is no key, no seed and no signing anywhere in LNbits; the provider
only *reads* the ledger.

It is opt-in and off until configured (``nano_enabled`` defaults to ``False``),
so an LNbits instance that does not set it behaves exactly as before.

Binding and replay (see ``nano_binding`` and the public binding standard):
each invoice binds the payment to the order with a commitment the payer carries
in the send block's ``representative`` field, and every credited block hash is
recorded once in a restart-proof SQLite ledger so the same block can never be
replayed - the refusal holds across a process restart.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from lnbits.settings import settings

from .base import (
    FiatInvoiceResponse,
    FiatPaymentPendingStatus,
    FiatPaymentResponse,
    FiatPaymentStatus,
    FiatPaymentSuccessStatus,
    FiatProvider,
    FiatStatusResponse,
    FiatSubscriptionPaymentOptions,
    FiatSubscriptionResponse,
)
from .nano_binding import (
    NanoClaimLedger,
    commitment_rep_account,
    is_valid_address,
    payment_uri,
    xno_to_raw,
)

_CHECKING_PREFIX = "fiat_nano_"
_XNO_CURRENCIES = {"XNO", "NANO"}


class NanoWallet(FiatProvider):
    """A read-only Nano settlement provider for the ``nano:mainnet`` exact scheme."""

    def __init__(self):
        logger.debug("Initializing NanoWallet")
        if not settings.nano_node_url:
            raise ValueError("Cannot initialize NanoWallet: missing node URL.")
        pay_to = settings.nano_payto_address
        if not pay_to:
            raise ValueError("Cannot initialize NanoWallet: missing payTo address.")
        if not is_valid_address(pay_to):
            raise ValueError(
                "Cannot initialize NanoWallet: payTo address fails its checksum."
            )

        self.pay_to = pay_to
        self.endpoint = settings.nano_node_url.rstrip("/")
        self.confirmations_required = settings.nano_confirmations_required
        self._settings_fields = self._settings_connection_fields()

        ledger_path = settings.nano_ledger_path or os.path.join(
            settings.lnbits_data_folder, "fiat_nano_claims.sqlite3"
        )
        self.ledger = NanoClaimLedger(ledger_path)

        self.client = httpx.AsyncClient(
            base_url=self.endpoint,
            headers={"User-Agent": settings.user_agent},
        )
        logger.info("NanoWallet initialized.")

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as exc:
            logger.warning(f"Error closing nano wallet connection: {exc}")
        try:
            self.ledger.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Error closing nano ledger: {exc}")

    async def status(
        self, only_check_settings: bool | None = False
    ) -> FiatStatusResponse:
        if only_check_settings:
            if self._settings_fields != self._settings_connection_fields():
                return FiatStatusResponse("Connection settings have changed.", 0)
            return FiatStatusResponse(balance=0)

        try:
            data = await self._rpc("account_info", account=self.pay_to)
            if data.get("error") and data["error"] != "Account not found":
                return FiatStatusResponse(f"Node error: {data['error']}", 0)
            balance_raw = int(data.get("balance", 0) or 0)
            return FiatStatusResponse(balance=balance_raw)
        except Exception as exc:
            logger.warning(exc)
            return FiatStatusResponse(f"Unable to connect to {self.endpoint}.", 0)

    async def create_invoice(
        self,
        amount: float,
        payment_hash: str,
        currency: str,
        memo: str | None = None,
        extra: dict[str, Any] | None = None,
        **kwargs,
    ) -> FiatInvoiceResponse:
        if currency.upper() not in _XNO_CURRENCIES:
            return FiatInvoiceResponse(
                ok=False,
                error_message=(
                    "NanoWallet settles in XNO; price the invoice in 'XNO'."
                ),
            )
        try:
            price_raw = xno_to_raw(amount)
        except ValueError as exc:
            return FiatInvoiceResponse(ok=False, error_message=str(exc))

        order_id = payment_hash
        representative = commitment_rep_account(order_id, self.pay_to, price_raw)
        checking_id = f"{_CHECKING_PREFIX}{payment_hash}_{price_raw}"
        request = payment_uri(self.pay_to, price_raw, representative)
        return FiatInvoiceResponse(
            ok=True, checking_id=checking_id, payment_request=request
        )

    async def create_subscription(
        self,
        subscription_id: str,
        quantity: int,
        payment_options: FiatSubscriptionPaymentOptions,
        **kwargs,
    ) -> FiatSubscriptionResponse:
        return FiatSubscriptionResponse(
            ok=False, error_message="NanoWallet does not support subscriptions."
        )

    async def cancel_subscription(
        self,
        subscription_id: str,
        correlation_id: str,
        **kwargs,
    ) -> FiatSubscriptionResponse:
        return FiatSubscriptionResponse(
            ok=False, error_message="NanoWallet does not support subscriptions."
        )

    async def pay_invoice(self, payment_request: str) -> FiatPaymentResponse:
        raise NotImplementedError("NanoWallet does not support paying invoices.")

    async def get_invoice_status(self, checking_id: str) -> FiatPaymentStatus:
        parsed = self._parse_checking_id(checking_id)
        if not parsed:
            return FiatPaymentPendingStatus()
        order_id, price_raw = parsed

        # Idempotent: an order already credited stays paid, with no node call.
        if self.ledger.order_credited(order_id):
            return FiatPaymentSuccessStatus()

        try:
            for block_hash in await self._candidate_send_hashes(price_raw):
                info = await self._block_info(block_hash)
                if info is None:
                    continue
                result = self.ledger.credit(
                    block_hash=block_hash,
                    order_id=order_id,
                    pay_to=self.pay_to,
                    price_raw=price_raw,
                    paid_raw=info["amount"],
                    link_as_account=info["link_as_account"],
                    representative=info["representative"],
                    subtype=info["subtype"],
                    block_time=info["local_timestamp"],
                )
                if result.matched:
                    return FiatPaymentSuccessStatus()
        except Exception as exc:
            logger.debug(f"Error reading nano payment status: {exc}")
            return FiatPaymentPendingStatus()

        return FiatPaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> FiatPaymentStatus:
        raise NotImplementedError("NanoWallet does not support outgoing payments.")

    # ----- node helpers (read-only) --------------------------------------

    async def _rpc(self, action: str, **params) -> dict:
        payload = {"action": action, **params}
        r = await self.client.post("", json=payload, timeout=15)
        r.raise_for_status()
        return r.json()

    async def _candidate_send_hashes(self, price_raw: int) -> list[str]:
        """Send-block hashes paying ``payTo`` exactly ``price_raw`` (unpocketed)."""
        data = await self._rpc(
            "receivable",
            account=self.pay_to,
            threshold=str(price_raw),
            count="50",
            source="true",
        )
        blocks = data.get("blocks")
        if not isinstance(blocks, dict):
            return []
        out: list[str] = []
        for block_hash, value in blocks.items():
            amount = value.get("amount") if isinstance(value, dict) else value
            try:
                if int(amount) == int(price_raw):
                    out.append(block_hash)
            except (TypeError, ValueError):
                continue
        return out

    async def _block_info(self, block_hash: str) -> dict | None:
        data = await self._rpc("block_info", json_block="true", hash=block_hash)
        if "contents" not in data:
            return None
        if self.confirmations_required and data.get("confirmed") != "true":
            return None
        contents = data.get("contents") or {}
        try:
            local_timestamp = int(data.get("local_timestamp") or 0)
        except (TypeError, ValueError):
            local_timestamp = 0
        return {
            "amount": int(data.get("amount", 0) or 0),
            "subtype": data.get("subtype", ""),
            "link_as_account": contents.get("link_as_account", ""),
            "representative": contents.get("representative", ""),
            "local_timestamp": local_timestamp,
        }

    # ----- plumbing ------------------------------------------------------

    @staticmethod
    def _parse_checking_id(checking_id: str) -> tuple[str, int] | None:
        if not checking_id.startswith(_CHECKING_PREFIX):
            return None
        rest = checking_id[len(_CHECKING_PREFIX) :]
        if "_" not in rest:
            return None
        order_id, _, price = rest.rpartition("_")
        try:
            return order_id, int(price)
        except ValueError:
            return None

    def _settings_connection_fields(self) -> str:
        return "-".join(
            [
                str(settings.nano_node_url),
                str(settings.nano_payto_address),
            ]
        )
