from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, List, Optional

from fastapi import HTTPException

from lnbits.db import Filters, Page

from ..utils.cache import cache

try:
    from pyln.client import RpcError  # type: ignore

    if TYPE_CHECKING:
        # override the false type
        class RpcError(RpcError):  # type: ignore
            error: dict

except ImportError:  # pragma: nocover
    LightningRpc = None

from lnbits.nodes.base import (
    ChannelBalance,
    ChannelPoint,
    ChannelState,
    ChannelStats,
    Node,
    NodeFees,
    NodeInvoice,
    NodeInvoiceFilters,
    NodePaymentsFilters,
    NodePeerInfo,
)

from .base import NodeChannel, NodeInfoResponse, NodePayment

if TYPE_CHECKING:
    from lnbits.wallets import CoreLightningWallet


def catch_rpc_errors(f):
    async def wrapper(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except RpcError as e:
            if e.error["code"] == -32602:
                raise HTTPException(status_code=400, detail=e.error["message"])
            else:
                raise HTTPException(status_code=500, detail=e.error["message"])

    return wrapper


class CoreLightningNode(Node):
    wallet: CoreLightningWallet

    async def ln_rpc(self, method, *args, **kwargs) -> dict:
        loop = asyncio.get_event_loop()
        fn = getattr(self.wallet.ln, method)
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    @catch_rpc_errors
    async def connect_peer(self, uri: str):
        # https://docs.corelightning.org/reference/lightning-connect
        try:
            await self.ln_rpc("connect", uri)
        except RpcError as e:
            if e.error["code"] == 400:
                raise HTTPException(HTTPStatus.BAD_REQUEST, detail=e.error["message"])
            else:
                raise

    @catch_rpc_errors
    async def disconnect_peer(self, peer_id: str):
        try:
            await self.ln_rpc("disconnect", peer_id)
        except RpcError as e:
            if e.error["code"] == -1:
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST,
                    detail=e.error["message"],
                )
            else:
                raise

    @catch_rpc_errors
    async def open_channel(
        self,
        peer_id: str,
        local_amount: int,
        push_amount: Optional[int] = None,
        fee_rate: Optional[int] = None,
    ) -> ChannelPoint:
        try:
            result = await self.ln_rpc(
                "fundchannel",
                peer_id,
                amount=local_amount,
                push_msat=int(push_amount * 1000) if push_amount else None,
                feerate=fee_rate,
            )
            return ChannelPoint(
                funding_txid=result["txid"],
                output_index=result["outnum"],
            )
        except RpcError as e:
            message = e.error["message"]

            if "amount: should be a satoshi amount" in message:
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST,
                    detail="The amount is not a valid satoshi amount.",
                )

            if "Unknown peer" in message:
                raise HTTPException(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    detail=(
                        "We where able to connect to the peer but CLN "
                        "can't find it when opening a channel."
                    ),
                )

            if "Owning subdaemon openingd died" in message:
                # https://github.com/ElementsProject/lightning/issues/2798#issuecomment-511205719
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST,
                    detail=(
                        "Likely the peer didn't like our channel opening "
                        "proposal and disconnected from us."
                    ),
                )

            if (
                "Number of pending channels exceed maximum" in message
                or "exceeds maximum chan size of 10 BTC" in message
                or "Could not afford" in message
            ):
                raise HTTPException(HTTPStatus.BAD_REQUEST, detail=message)
            raise

    @catch_rpc_errors
    async def close_channel(
        self,
        short_id: Optional[str] = None,
        point: Optional[ChannelPoint] = None,
        force: bool = False,
    ):
        if not short_id:
            raise HTTPException(status_code=400, detail="Short id required")
        try:
            await self.ln_rpc("close", short_id)
        except RpcError as e:
            message = e.error["message"]
            if (
                "Short channel ID not active:" in message
                or "Short channel ID not found" in message
            ):
                raise HTTPException(HTTPStatus.BAD_REQUEST, detail=message)
            else:
                raise

    @catch_rpc_errors
    async def _get_id(self) -> str:
        info = await self.ln_rpc("getinfo")
        return info["id"]

    @catch_rpc_errors
    async def get_peer_ids(self) -> List[str]:
        peers = await self.ln_rpc("listpeers")
        return [p["id"] for p in peers["peers"] if p["connected"]]

    @catch_rpc_errors
    async def _get_peer_info(self, peer_id: str) -> NodePeerInfo:
        result = await self.ln_rpc("listnodes", peer_id)
        nodes = result["nodes"]
        if len(nodes) == 0:
            return NodePeerInfo(id=peer_id)
        node = nodes[0]
        if "last_timestamp" in node:
            return NodePeerInfo(
                id=node["nodeid"],
                alias=node["alias"],
                color=node["color"],
                last_timestamp=node["last_timestamp"],
                addresses=[
                    address["address"] + ":" + str(address["port"])
                    for address in node["addresses"]
                ],
            )
        else:
            return NodePeerInfo(id=node["nodeid"])

    @catch_rpc_errors
    async def get_channels(self) -> List[NodeChannel]:
        funds = await self.ln_rpc("listfunds")
        nodes = await self.ln_rpc("listnodes")
        nodes_by_id = {n["nodeid"]: n for n in nodes["nodes"]}

        return [
            NodeChannel(
                short_id=ch.get("short_channel_id"),
                point=ChannelPoint(
                    funding_txid=ch["funding_txid"],
                    output_index=ch["funding_output"],
                ),
                peer_id=ch["peer_id"],
                balance=ChannelBalance(
                    local_msat=ch["our_amount_msat"],
                    remote_msat=ch["amount_msat"] - ch["our_amount_msat"],
                    total_msat=ch["amount_msat"],
                ),
                name=nodes_by_id.get(ch["peer_id"], {}).get("alias"),
                color=nodes_by_id.get(ch["peer_id"], {}).get("color"),
                state=(
                    ChannelState.ACTIVE
                    if ch["state"] == "CHANNELD_NORMAL"
                    else ChannelState.PENDING
                    if ch["state"] in ("CHANNELD_AWAITING_LOCKIN", "OPENINGD")
                    else ChannelState.CLOSED
                    if ch["state"]
                    in (
                        "CHANNELD_CLOSING",
                        "CLOSINGD_COMPLETE",
                        "CLOSINGD_SIGEXCHANGE",
                        "ONCHAIN",
                    )
                    else ChannelState.INACTIVE
                ),
            )
            for ch in funds["channels"]
        ]

    @catch_rpc_errors
    async def get_info(self) -> NodeInfoResponse:
        info = await self.ln_rpc("getinfo")
        funds = await self.ln_rpc("listfunds")

        channels = await self.get_channels()
        active_channels = [
            channel for channel in channels if channel.state == ChannelState.ACTIVE
        ]
        return NodeInfoResponse(
            id=info["id"],
            backend_name="CLN",
            alias=info["alias"],
            color=info["color"],
            onchain_balance_sat=sum(
                output["amount_msat"] / 1000 for output in funds["outputs"]
            ),
            onchain_confirmed_sat=sum(
                output["amount_msat"] / 1000
                for output in funds["outputs"]
                if output["status"] == "confirmed"
            ),
            channel_stats=ChannelStats.from_list(channels),
            num_peers=info["num_peers"],
            blockheight=info["blockheight"],
            balance_msat=sum(channel.balance.local_msat for channel in active_channels),
            fees=NodeFees(total_msat=info["fees_collected_msat"]),
            addresses=[address["address"] for address in info["address"]],
        )

    @catch_rpc_errors
    async def get_payments(
        self, filters: Filters[NodePaymentsFilters]
    ) -> Page[NodePayment]:
        async def get_payments():
            result = await self.ln_rpc("listpays")
            return [
                NodePayment(
                    bolt11=pay["bolt11"],
                    amount=pay["amount_msat"],
                    fee=int(pay["amount_msat"]) - int(pay["amount_sent_msat"]),
                    memo=pay.get("description"),
                    time=pay["created_at"],
                    preimage=pay.get("preimage"),
                    payment_hash=pay["payment_hash"],
                    pending=pay["status"] != "complete",
                    destination=await self.get_peer_info(pay["destination"]),
                )
                for pay in reversed(result["pays"])
                if pay["status"] != "failed"
            ]

        results = await cache.save_result(get_payments, key="node:payments")
        count = len(results)
        if filters.offset:
            results = results[filters.offset :]
        if filters.limit:
            results = results[: filters.limit]
        return Page(data=results, total=count)

    @catch_rpc_errors
    async def get_invoices(
        self, filters: Filters[NodeInvoiceFilters]
    ) -> Page[NodeInvoice]:
        result = await cache.save_result(
            lambda: self.ln_rpc("listinvoices"), key="node:invoices"
        )
        invoices = result["invoices"]
        invoices.reverse()
        count = len(invoices)
        if filters.offset:
            invoices = invoices[filters.offset :]
        if filters.limit:
            invoices = invoices[: filters.limit]
        return Page(
            data=[
                NodeInvoice(
                    bolt11=invoice["bolt11"],
                    amount=invoice["amount_msat"],
                    preimage=invoice.get("payment_preimage"),
                    memo=invoice["description"],
                    paid_at=invoice.get("paid_at"),
                    expiry=invoice["expires_at"],
                    payment_hash=invoice["payment_hash"],
                    pending=invoice["status"] != "paid",
                )
                for invoice in invoices
            ],
            total=count,
        )
