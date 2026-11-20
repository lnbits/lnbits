from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from lnbits.core.crud.onchain import (
    create_wasm_onchain_checkout,
    get_address_by_id,
    get_address_snapshot,
    get_wasm_onchain_checkout,
)
from lnbits.core.crud.wallets import (
    get_onchain_sync_status,
    get_onchain_wallet,
    get_wallets,
)
from lnbits.core.db import db
from lnbits.core.models.onchain import Address, Snapshot, WasmOnchainCheckout
from lnbits.core.models.wallets import OnchainWallet
from lnbits.core.services.blockexplorer import TXID
from lnbits.core.services.onchain import (
    SCAN_MAX_AGE,
    get_fresh_address,
    require_onchain_payments,
)
from lnbits.db import Connection
from lnbits.helpers import sha256s
from lnbits.utils.onchain import address_script

from .models import EmptyRequest, ListUserWalletsResponse, UserWalletSummary
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

    async def list_user_wallets(self, request: EmptyRequest) -> ListUserWalletsResponse:
        self.api.require_permission("wallet.list")
        user_id = self._authenticated_user()
        wallets = await get_wallets(user_id)
        summaries = []
        for wallet in wallets:
            if wallet.user != user_id or wallet.deleted:
                raise PermissionError(_UNAVAILABLE)
            ready = wallet.can_receive_payments
            if wallet.is_onchain_wallet:
                try:
                    await require_onchain_payments()
                    await self._wallet(wallet.id, sha256s(user_id))
                    ready = True
                except (PermissionError, ValueError):
                    ready = False
            summaries.append(
                UserWalletSummary(
                    id=wallet.id,
                    name=wallet.name,
                    currency=wallet.currency,
                    wallet_type=wallet.wallet_type,
                    onchain_network=wallet.onchain_network,
                    receiving_ready=ready,
                )
            )
        return ListUserWalletsResponse(wallets=summaries)

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
        owner_id = sha256s(self._authenticated_user())
        try:
            await require_onchain_payments()
            async with db.connect() as conn:
                wallet = await self._wallet(request.wallet_id, owner_id, conn)
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
                token = secrets.token_urlsafe(32)
                checkout = WasmOnchainCheckout(
                    extension_id=self.api.extension_id,
                    owner_id=owner_id,
                    wallet_id=wallet.id,
                    source_id=request.source_id,
                    checkout_id=request.checkout_id,
                    address_id=address.id,
                    address=address.address,
                    network=wallet.onchain_network or "",
                    wallet_fingerprint=sha256s(wallet.onchain_meta.masterpub),
                    status_token_hash=sha256s(token),
                )
                if not await create_wasm_onchain_checkout(checkout, conn):
                    raise ValueError(_UNAVAILABLE)
                # Recheck after allocation: deletion/reconfiguration must fail closed.
                current = await self._wallet(wallet.id, owner_id, conn)
                self._validate_wallet_binding(current, checkout)
            return ReserveOnchainAddressResponse(
                address=checkout.address, network=checkout.network, status_token=token
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
            "Requires its authenticated owner or its public status token. "
            "Uses recent successful core scans, including spent outputs."
        ),
        required_permission="onchain.payments.read",
        require_auth=False,
    )
    async def payment_status(
        self, request: OnchainPaymentStatusRequest
    ) -> OnchainPaymentStatusResponse:
        try:
            await require_onchain_payments()
            async with db.connect() as conn:
                checkout = await get_wasm_onchain_checkout(
                    self.api.extension_id,
                    request.wallet_id,
                    request.source_id,
                    request.checkout_id,
                    conn,
                )
                self._authorize_status(checkout, request)
                if checkout is None:
                    raise PermissionError(_UNAVAILABLE)
                wallet = await self._wallet(checkout.wallet_id, checkout.owner_id, conn)
                self._validate_wallet_binding(wallet, checkout)
                address = await get_address_by_id(checkout.address_id, conn)
                if (
                    not address
                    or address.walet_id != wallet.id
                    or address.address != checkout.address
                    or address.branch_index != 0
                ):
                    raise PermissionError(_UNAVAILABLE)
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
                current = await self._wallet(wallet.id, checkout.owner_id, conn)
                self._validate_wallet_binding(current, checkout)
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
        self, wallet_id: str, owner_id: str, conn: Connection | None = None
    ) -> OnchainWallet:
        wallet = await get_onchain_wallet(wallet_id, conn=conn)
        if (
            not wallet
            or wallet.id != wallet_id
            or wallet.deleted
            or not wallet.is_onchain_wallet
            or sha256s(wallet.user) != owner_id
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
        checkout: WasmOnchainCheckout | None,
        request: OnchainPaymentStatusRequest,
    ) -> None:
        if (
            not checkout
            or checkout.extension_id != self.api.extension_id
            or checkout.wallet_id != request.wallet_id
            or checkout.source_id != request.source_id
            or checkout.checkout_id != request.checkout_id
            or checkout.address != request.address
        ):
            raise PermissionError(_UNAVAILABLE)
        if self.api.user_id:
            if checkout.owner_id != sha256s(self._authenticated_user()):
                raise PermissionError(_UNAVAILABLE)
        elif not request.status_token:
            raise PermissionError(_UNAVAILABLE)
        elif self.api.owner_id and self.api.owner_id != checkout.owner_id:
            raise PermissionError(_UNAVAILABLE)
        if request.status_token and not secrets.compare_digest(
            checkout.status_token_hash, sha256s(request.status_token)
        ):
            raise PermissionError(_UNAVAILABLE)

    def _validate_wallet_binding(
        self, wallet: OnchainWallet, checkout: WasmOnchainCheckout
    ) -> None:
        if (
            wallet.onchain_network != checkout.network
            or sha256s(wallet.onchain_meta.masterpub) != checkout.wallet_fingerprint
        ):
            raise PermissionError(_UNAVAILABLE)


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
