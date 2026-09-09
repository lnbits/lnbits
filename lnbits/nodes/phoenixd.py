from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from lnbits.db import Filters, Page

from .base import (
    ChannelBalance,
    ChannelPoint,
    ChannelState,
    ChannelStats,
    Node,
    NodeChannel,
    NodeFees,
    NodeInfoResponse,
    NodeInvoice,
    NodeInvoiceFilters,
    NodePayment,
    NodePaymentsFilters,
    NodePeerInfo,
)

if TYPE_CHECKING:
    from lnbits.wallets.phoenixd import PhoenixdWallet


class PhoenixdStatus(BaseModel):
    version: str | None
    chain: str
    blockheight: int | None
    fee_credit_sat: int
    swap_in: dict[str, int] | None
    capabilities: list[str]


class PhoenixdNode(Node):
    """ACINQ phoenixd HTTP API (verified against v0.7.3 and v0.9.0).

    Use getinfo's safe channel summary, not listchannels' internal channel state.
    The latter can contain sensitive channel recovery/signing data.
    """

    wallet: PhoenixdWallet

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await self.wallet.client.request(
                method, path, timeout=30, **kwargs
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException as exc:
            raise HTTPException(
                504,
                "Phoenixd timed out. Check channels and payments before retrying.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            message = {
                401: "Phoenixd rejected the configured API password.",
                403: "Phoenixd requires its full-access API password.",
                404: "This operation is unavailable on this Phoenixd version.",
                400: "Phoenixd rejected the request. Check parameters and node state.",
            }.get(status, "Phoenixd could not complete the request.")
            raise HTTPException(502, message) from exc
        except httpx.RequestError as exc:
            raise HTTPException(502, "Unable to reach Phoenixd.") from exc

    async def _get(self, path: str, **kwargs) -> Any:
        response = await self._request("GET", path, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise HTTPException(502, "Phoenixd returned an invalid response.") from exc

    async def _get_id(self) -> str:
        return (await self._get("/getinfo"))["nodeId"]

    @staticmethod
    def _unsupported():
        raise HTTPException(501, "Phoenixd manages channels and peers automatically.")

    async def get_peer_ids(self) -> list[str]:
        # Phoenixd does not expose a peer listing or its connection status.
        return []

    async def _get_peer_info(self, peer_id: str) -> NodePeerInfo:
        return NodePeerInfo(id=peer_id)

    async def connect_peer(self, uri: str):
        self._unsupported()

    async def disconnect_peer(self, peer_id: str):
        self._unsupported()

    async def open_channel(
        self,
        peer_id: str,
        local_amount: int,
        push_amount: int | None = None,
        fee_rate: int | None = None,
    ) -> ChannelPoint:
        raise HTTPException(501, "Phoenixd opens and resizes channels automatically.")

    async def close_channel(
        self,
        short_id: str | None = None,
        point: ChannelPoint | None = None,
        force: bool = False,
    ):
        raise HTTPException(
            501, "Use Phoenixd cooperative close with an address and fee rate."
        )

    async def set_channel_fee(self, channel_id: str, base_msat: int, ppm: int):
        self._unsupported()

    @staticmethod
    def _channel(data: dict) -> NodeChannel:
        state = data["state"]
        if state == "Normal":
            parsed_state = ChannelState.ACTIVE
        elif state == "Closed":
            parsed_state = ChannelState.CLOSED
        elif state.startswith("WaitFor"):
            parsed_state = ChannelState.PENDING
        else:
            parsed_state = ChannelState.INACTIVE
        return NodeChannel(
            id=data.get("channelId"),
            peer_id="",
            name="ACINQ (managed)",
            state=parsed_state,
            backend_state=state,
            funding_txid=data.get("fundingTxId"),
            balance=ChannelBalance(
                local_msat=int(data.get("balanceSat") or 0) * 1000,
                remote_msat=int(data.get("inboundLiquiditySat") or 0) * 1000,
                total_msat=int(data.get("capacitySat") or 0) * 1000,
            ),
        )

    async def get_channels(self) -> list[NodeChannel]:
        info = await self._get("/getinfo")
        return [self._channel(channel) for channel in info["channels"]]

    async def get_channel(self, channel_id: str) -> NodeChannel | None:
        return next((c for c in await self.get_channels() if c.id == channel_id), None)

    async def get_info(self) -> NodeInfoResponse:
        info = await self._get("/getinfo")
        balance = await self._get("/getbalance")
        channels = [self._channel(channel) for channel in info["channels"]]
        swap_in = balance.get("swapIn") or {}
        confirmed = int(swap_in.get("weaklyConfirmedBalanceSat", 0)) + int(
            swap_in.get("deeplyConfirmedBalanceSat", 0)
        )
        return NodeInfoResponse(
            id=info["nodeId"],
            backend_name="Phoenixd",
            alias="Phoenixd",
            color="ff9900",
            num_peers=None,
            blockheight=info.get("blockHeight"),
            addresses=[],
            managed_channels=True,
            channel_stats=ChannelStats.from_list(channels),
            balance_msat=int(balance["balanceSat"]) * 1000,
            onchain_balance_sat=confirmed
            + int(swap_in.get("unconfirmedBalanceSat", 0)),
            onchain_confirmed_sat=confirmed,
            fees=NodeFees(total_msat=0),
        )

    async def get_status(self) -> PhoenixdStatus:
        info = await self._get("/getinfo")
        balance = await self._get("/getbalance")
        version = re.match(r"v?(\d+)\.(\d+)\.(\d+)", info.get("version", ""))
        capabilities = []
        if version and tuple(map(int, version.groups())) >= (0, 7, 3):
            capabilities = [
                "estimate",
                "close",
                "send",
                "bump",
                "offer",
                "lnaddress",
                "export",
            ]
        if balance.get("swapIn") is not None:
            capabilities.append("swapin")
        return PhoenixdStatus(
            version=info.get("version"),
            chain=info["chain"],
            blockheight=info.get("blockHeight"),
            fee_credit_sat=int(balance.get("feeCreditSat", 0)),
            swap_in=balance.get("swapIn"),
            capabilities=capabilities,
        )

    async def estimate_liquidity(self, amount_sat: int) -> dict[str, int]:
        data = await self._get(
            "/estimateliquidityfees", params={"amountSat": amount_sat}
        )
        return {key: int(data[key]) for key in ("miningFeeSat", "serviceFeeSat")}

    async def receive_address(self, kind: str) -> str:
        paths = {
            "swapin": "/getswapinaddress",
            "offer": "/getoffer",
            "lnaddress": "/getlnaddress",
        }
        if kind == "swapin":
            return (await self._get(paths[kind]))["address"]
        response = await self._request("GET", paths[kind])
        value = response.text.strip().strip('"')
        if (kind == "offer" and not value.startswith("lno1")) or (
            kind == "lnaddress" and not value.startswith("₿")
        ):
            raise HTTPException(502, "Phoenixd receive address is not available yet.")
        return value

    async def transact(self, operation: str, data: dict) -> str:
        paths = {"close": "/closechannel", "send": "/sendtoaddress", "bump": "/bumpfee"}
        response = await self._request("POST", paths[operation], data=data)
        txid = response.text.strip().strip('"')
        # These endpoints also return failures as text with HTTP 200.
        if not re.fullmatch(r"[0-9a-fA-F]{64}", txid):
            raise HTTPException(
                502,
                "Phoenixd returned no transaction ID. Check the node before retrying.",
            )
        return txid

    async def export_history(self):
        await self._request("POST", "/export")

    async def _history(
        self, direction: str, filters: Filters
    ) -> tuple[list[dict], int]:
        # Phoenixd has no count endpoint. Fetch one extra row for next-page navigation,
        # keeping requests bounded even for nodes with a large payment history.
        limit = min(filters.limit or 10, 100)
        offset = filters.offset or 0
        if limit < 1 or offset < 0:
            raise HTTPException(400, "Invalid pagination parameters.")
        params: dict[str, Any] = {"limit": limit + 1, "offset": offset}
        if direction == "incoming":
            params["all"] = "true"
        rows = await self._get(f"/payments/{direction}", params=params)
        return rows[:limit], offset + len(rows)

    async def get_payments(
        self, filters: Filters[NodePaymentsFilters]
    ) -> Page[NodePayment]:
        rows, total = await self._history("outgoing", filters)
        return Page(
            data=[
                NodePayment(
                    pending=not row["isPaid"],
                    amount=int(row["sent"]) * 1000,
                    fee=int(row["fees"]),
                    memo=row.get("subType", "lightning").replace("_", " "),
                    time=int(row["createdAt"]) // 1000,
                    bolt11=row.get("invoice"),
                    preimage=row.get("preimage"),
                    payment_hash=row.get("paymentHash"),
                    payment_id=row.get("paymentId"),
                    txid=row.get("txId"),
                )
                for row in rows
            ],
            total=total,
        )

    async def get_invoices(
        self, filters: Filters[NodeInvoiceFilters]
    ) -> Page[NodeInvoice]:
        rows, total = await self._history("incoming", filters)
        return Page(
            data=[
                NodeInvoice(
                    pending=not row["isPaid"],
                    amount=int(
                        row["receivedSat"]
                        if row["isPaid"]
                        else row.get("requestedSat") or 0
                    )
                    * 1000,
                    memo=row.get("description") or row.get("payerNote"),
                    bolt11=row.get("invoice") or "",
                    preimage=row.get("preimage"),
                    payment_hash=row["paymentHash"],
                    paid_at=(
                        int(row["completedAt"]) // 1000
                        if row.get("completedAt")
                        else None
                    ),
                    expiry=(
                        int(row["expiresAt"]) // 1000 if row.get("expiresAt") else None
                    ),
                )
                for row in rows
            ],
            total=total,
        )
