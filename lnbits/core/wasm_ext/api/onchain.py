from __future__ import annotations

import hmac
import json
import secrets
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from lnbits.core.crud.onchain import (
    get_address_by_id,
    get_address_snapshot,
)
from lnbits.core.crud.wallets import (
    get_onchain_sync_status,
    get_onchain_wallet,
)
from lnbits.core.db import db
from lnbits.core.models.onchain import Address, Snapshot
from lnbits.core.models.wallets import OnchainWallet
from lnbits.core.services.blockexplorer import TXID
from lnbits.core.services.onchain import (
    SCAN_MAX_AGE,
    get_fresh_address,
    require_onchain_payments,
)
from lnbits.db import Connection
from lnbits.helpers import sha256s
from lnbits.settings import settings
from lnbits.utils.onchain import address_script

from .registry import extension_api_method

if TYPE_CHECKING:
    from .host import ExtensionHostAPI

_UNAVAILABLE = "Onchain wallet or checkout is unavailable."
_STATUS_UNAVAILABLE = "Onchain checkout payment data is unavailable. Retry after sync."
_MAX_SATS = 2_100_000_000_000_000


class ReserveOnchainAddressRequest(BaseModel):
    wallet_id: str = Field(..., min_length=1, max_length=128)
    source_id: str = Field(..., min_length=1, max_length=128)
    checkout_id: str = Field(..., min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")


class ReserveOnchainAddressResponse(BaseModel):
    address: str
    network: str
    status_token: str


class OnchainPaymentStatusRequest(ReserveOnchainAddressRequest):
    address: str = Field(..., min_length=1, max_length=128)
    status_token: str | None = Field(None, min_length=1, max_length=128)


class OnchainPaymentStatusResponse(BaseModel):
    received_sat: int
    confirmed_sat: int
    unconfirmed_sat: int
    checked_at: int


class ExtensionOnchainAPI:
    def __init__(self, api: ExtensionHostAPI) -> None:
        self.api = api

    async def receiving_ready(self, wallet_id: str) -> bool:
        self._authenticated_user()
        try:
            await require_onchain_payments()
            await self._wallet(wallet_id)
            return True
        except (PermissionError, ValueError):
            return False

    @extension_api_method(
        method_id="onchain.reserve_address",
        namespace="onchain",
        name="Reserve checkout address",
        host_interface="onchain",
        host_name="reserve_address",
        sdk_name="reserveAddress",
        description=(
            "Reserve a fresh core onchain address for an authenticated owner's "
            "source and checkout. Returns a checkout-specific public status token."
        ),
        required_permission="onchain.receive",
    )
    async def reserve_address(
        self, request: ReserveOnchainAddressRequest
    ) -> ReserveOnchainAddressResponse:
        self._authenticated_user()
        try:
            await require_onchain_payments()
            async with db.connect() as conn:
                wallet = await self._wallet(request.wallet_id, conn)
                # Core allocation uses a database compare-and-swap, also across workers.
                address = await get_fresh_address(wallet.id, conn=conn)
                if (
                    not address
                    or address.walet_id != wallet.id
                    or address.branch_index != 0
                    or address.has_activity
                ):
                    raise ValueError(_UNAVAILABLE)
                snapshot = await get_address_snapshot(address.id, conn)
                if snapshot and snapshot.transactions:
                    raise ValueError(_UNAVAILABLE)
                token = self._checkout_token(wallet, address, request)
                # Recheck after allocation: deletion/reconfiguration must fail closed.
                current = await self._wallet(wallet.id, conn)
                if token != self._checkout_token(current, address, request):
                    raise PermissionError(_UNAVAILABLE)
            return ReserveOnchainAddressResponse(
                address=address.address,
                network=wallet.onchain_network or "",
                status_token=token,
            )
        except PermissionError:
            raise PermissionError(_UNAVAILABLE) from None
        except Exception:
            raise ValueError(_UNAVAILABLE) from None

    @extension_api_method(
        method_id="onchain.payment_status",
        namespace="onchain",
        name="Read checkout payment totals",
        host_interface="onchain",
        host_name="payment_status",
        sdk_name="paymentStatus",
        description=(
            "Read received, confirmed and unconfirmed satoshis for one checkout. "
            "Requires its checkout token, also for authenticated owners. "
            "Uses recent successful core scans, including spent outputs."
        ),
        required_permission="onchain.payments.read",
        require_auth=False,
    )
    async def payment_status(
        self, request: OnchainPaymentStatusRequest
    ) -> OnchainPaymentStatusResponse:
        try:
            if not request.status_token or "." not in request.status_token:
                raise PermissionError(_UNAVAILABLE)
            address_id = request.status_token.rsplit(".", 1)[0]
            await require_onchain_payments()
            async with db.connect() as conn:
                wallet = await self._wallet(request.wallet_id, conn)
                address = await get_address_by_id(address_id, conn)
                if not address:
                    raise PermissionError(_UNAVAILABLE)
                self._authorize_status(wallet, address, request)
                status = await get_onchain_sync_status(wallet.id, conn)
                snapshot = await get_address_snapshot(address.id, conn)
                now = int(time.time())
                if (
                    not snapshot
                    or snapshot.address_id != address.id
                    or not 0 <= now - snapshot.checked_at <= SCAN_MAX_AGE
                    or wallet.onchain_meta.sync_error
                    or not snapshot.checked_at
                    or wallet.onchain_meta.sync_checked_at < snapshot.checked_at
                    or status.get("onchain_sync_lease_until", 0) > now
                    or status != await get_onchain_sync_status(wallet.id, conn)
                ):
                    raise ValueError(_STATUS_UNAVAILABLE)
                current = await self._wallet(wallet.id, conn)
                self._authorize_status(current, address, request)
                return _payment_totals(address, snapshot)
        except PermissionError:
            raise PermissionError(_UNAVAILABLE) from None
        except Exception:
            raise ValueError(_STATUS_UNAVAILABLE) from None

    def _authenticated_user(self) -> str:
        # owner_id/event context can originate from an unauthenticated public route.
        if not self.api.user_id:
            raise PermissionError("An authenticated owner is required.")
        return self.api.user_id

    async def _wallet(
        self, wallet_id: str, conn: Connection | None = None
    ) -> OnchainWallet:
        wallet = await get_onchain_wallet(wallet_id, conn=conn)
        owner_id = sha256s(self.api.user_id) if self.api.user_id else self.api.owner_id
        if (
            not wallet
            or wallet.id != wallet_id
            or wallet.deleted
            or not wallet.is_onchain_wallet
            or (owner_id is not None and sha256s(wallet.user) != owner_id)
            or not wallet.onchain_network
            or not wallet.onchain_wallet_kind
            or not wallet.onchain_meta.masterpub
            or (
                wallet.onchain_wallet_kind == "hot"
                and not wallet.onchain_meta.backup_confirmed
            )
        ):
            raise PermissionError(_UNAVAILABLE)
        return wallet

    def _authorize_status(
        self,
        wallet: OnchainWallet,
        address: Address,
        request: OnchainPaymentStatusRequest,
    ) -> None:
        if (
            address.walet_id != wallet.id
            or address.address != request.address
            or address.branch_index != 0
            or not request.status_token
            or not secrets.compare_digest(
                request.status_token.encode(),
                self._checkout_token(wallet, address, request).encode(),
            )
        ):
            raise PermissionError(_UNAVAILABLE)

    def _checkout_token(
        self,
        wallet: OnchainWallet,
        address: Address,
        request: ReserveOnchainAddressRequest,
    ) -> str:
        if not settings.auth_secret_key:
            raise PermissionError(_UNAVAILABLE)
        # A purpose-specific MAC binds existing core records without checkout storage.
        # The extension persists this receipt; notes and caller IDs cannot replace it.
        payload = json.dumps(
            [
                "lnbits:wasm:onchain-checkout:v1",
                self.api.extension_id,
                sha256s(wallet.user),
                wallet.id,
                request.source_id,
                request.checkout_id,
                address.id,
                address.address,
                wallet.onchain_network,
                sha256s(wallet.onchain_meta.masterpub),
                sha256s(wallet.adminkey),
            ],
            separators=(",", ":"),
        )
        signature = hmac.digest(
            settings.auth_secret_key.encode(), payload.encode(), "sha256"
        ).hex()
        return f"{address.id}.{signature}"


def _payment_totals(
    address: Address, snapshot: Snapshot
) -> OnchainPaymentStatusResponse:
    receive_script = address_script(address.address)
    confirmed = unconfirmed = 0
    seen: dict[str, dict] = {}
    for transaction in snapshot.transactions:
        txid = transaction.get("txid")
        status = transaction.get("status")
        outputs = transaction.get("vout")
        if (
            not isinstance(txid, str)
            or not TXID.fullmatch(txid)
            or not isinstance(status, dict)
            or type(status.get("confirmed")) is not bool
            or (
                status["confirmed"]
                and (
                    type(status.get("block_height")) is not int
                    or status["block_height"] < 0
                )
            )
            or not isinstance(outputs, list)
            or not outputs
        ):
            raise ValueError(_STATUS_UNAVAILABLE)
        if txid in seen:
            if seen[txid] != transaction:
                raise ValueError(_STATUS_UNAVAILABLE)
            continue
        seen[txid] = transaction
        for output in outputs:
            received = _received_output(output, address.address, receive_script)
            if status["confirmed"]:
                confirmed += received
            else:
                unconfirmed += received
    if confirmed + unconfirmed >= 2**64:
        raise ValueError(_STATUS_UNAVAILABLE)
    return OnchainPaymentStatusResponse(
        received_sat=confirmed + unconfirmed,
        confirmed_sat=confirmed,
        unconfirmed_sat=unconfirmed,
        checked_at=snapshot.checked_at,
    )


def _received_output(output: dict, address: str, receive_script: bytes) -> int:
    if (
        not isinstance(output, dict)
        or type(output.get("value")) is not int
        or not 0 <= output["value"] <= _MAX_SATS
    ):
        raise ValueError(_STATUS_UNAVAILABLE)
    recipient = output.get("scriptpubkey_address")
    script = output.get("scriptpubkey")
    if script is not None:
        if not isinstance(script, str):
            raise ValueError(_STATUS_UNAVAILABLE)
        matches = bytes.fromhex(script) == receive_script
        if recipient is not None and (
            not isinstance(recipient, str) or (recipient == address) != matches
        ):
            raise ValueError(_STATUS_UNAVAILABLE)
    else:
        if not isinstance(recipient, str) or not recipient:
            raise ValueError(_STATUS_UNAVAILABLE)
        matches = recipient == address
    return output["value"] if matches else 0
