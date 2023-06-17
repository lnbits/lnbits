from __future__ import annotations

import asyncio
from functools import partial, wraps
from typing import TYPE_CHECKING, Optional

import starlette.status as status
from fastapi import HTTPException

from lnbits.db import Filters, Page

try:
    from pyln.client import RpcError  # type: ignore
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

from .base import NodeChannel, NodeChannelsResponse, NodeInfoResponse, NodePayment

if TYPE_CHECKING:
    from lnbits.wallets import CoreLightningWallet


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        partial_func = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, partial_func)

    return run


def catch_rpc_errors(f):
    async def wrapper(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except RpcError as e:
            raise HTTPException(status_code=500, detail=e.error["message"])  # type: ignore

    return wrapper


class CoreLightningNode(Node):
    wallet: CoreLightningWallet

    def __init__(self, wallet: CoreLightningWallet):
        super().__init__(wallet)
        try:
            raw: dict = self.wallet.ln.call("listsqlschemas")  # type: ignore
            self.schema_cols = {
                schema["tablename"]: schema["columns"] for schema in raw["schemas"]
            }
        except RpcError:
            self.schema_cols = {}

    @catch_rpc_errors
    async def connect_peer(self, uri: str):
        try:
            await self.wallet.ln_rpc("connect", uri)
        except RpcError as e:
            message = e.error["message"]  # type: ignore

            if "no address known for peer" in message:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Connection establishment: No address known for peer",
                )
            elif "Connection timed out" in message:
                raise HTTPException(
                    status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Connection establishment: Connection timed out.",
                )
            elif "Connection refused" in message:
                raise HTTPException(
                    status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Connection establishment: Connection refused.",
                )
            else:
                raise

    async def disconnect_peer(self, id: str):
        await self.wallet.ln_rpc("disconnect", id)

    @catch_rpc_errors
    async def open_channel(
        self,
        peer_id: str,
        local_amount: int,
        push_amount: Optional[int] = None,
        fee_rate: Optional[int] = None,
    ):
        try:
            result = await self.wallet.ln_rpc(
                "fundchannel",
                peer_id,
                amount=local_amount,
                push_msat=int(push_amount * 1000) if push_amount else None,
                feerate=fee_rate,
            )
            return result["txid"]
        except RpcError as e:
            message = e.error["message"]  # type: ignore

            if "amount: should be a satoshi amount" in message:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="The amount is not a valid satoshi amount.",
                )

            if "Unknown peer" in message:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="We where able to connect to the peer but CLN can't find it when opening a channel.",
                )

            if "Owning subdaemon openingd died" in message:
                # https://github.com/ElementsProject/lightning/issues/2798#issuecomment-511205719
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Likely the peer didn't like our channel opening proposal and disconnected from us.",
                )

            if (
                "Number of pending channels exceed maximum" in message
                or "exceeds maximum chan size of 10 BTC" in message
                or "Could not afford" in message
            ):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)

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
            self.wallet.ln.close()
            await self.wallet.ln_rpc("close", short_id)
        except RpcError as e:
            message = e.error["message"]  # type: ignore
            if (
                "Short channel ID not active:" in message
                or "Short channel ID not found" in message
            ):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)
            else:
                raise

    @catch_rpc_errors
    async def _get_id(self) -> str:
        info = await self.wallet.ln_rpc("getinfo")
        return info["id"]

    @catch_rpc_errors
    async def get_peer_ids(self) -> list[str]:
        peers = await self.wallet.ln_rpc("listpeers")
        return [p["id"] for p in peers["peers"] if p["connected"]]

    @catch_rpc_errors
    async def _get_peer_info(self, pubkey: str) -> NodePeerInfo:
        result = await self.wallet.ln_rpc("listnodes", pubkey)
        nodes = result["nodes"]
        if len(nodes) == 0:
            return NodePeerInfo(id=pubkey)
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
    async def get_channels(self) -> NodeChannelsResponse:
        funds = await self.wallet.ln_rpc("listfunds")
        nodes = await self.wallet.ln_rpc("listnodes")
        nodes_by_id = {n["nodeid"]: n for n in nodes["nodes"]}

        return NodeChannelsResponse.from_list(
            [
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
        )

    @catch_rpc_errors
    async def get_info(self) -> NodeInfoResponse:
        info = await self.wallet.ln_rpc("getinfo")
        funds = await self.wallet.ln_rpc("listfunds")

        channel_response = await self.get_channels()
        active_channels = [
            channel
            for channel in channel_response.channels
            if channel.state == ChannelState.ACTIVE
        ]
        return NodeInfoResponse(
            id=info["id"],
            backend_name="CLN",
            alias=info["alias"],
            color=info["color"],
            onchain_balance_sat=sum(output["value"] for output in funds["outputs"]),
            onchain_confirmed_sat=sum(
                output["value"]
                for output in funds["outputs"]
                if output["status"] == "confirmed"
            ),
            channel_stats=ChannelStats.from_list(channel_response.channels),
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
            result = await self.wallet.ln_rpc("listpays")
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
                for pay in result["pays"]
                if pay["status"] != "failed"
            ]

        results = await self.get_and_revalidate(get_payments, "payments")
        count = len(results)
        if filters.offset:
            results = results[filters.offset :]
        if filters.limit:
            results = results[: filters.limit]
        return Page(data=results, total=count)

    @catch_rpc_errors
    async def sql(self, query: str, schema: Optional[str] = None) -> list:
        loop = asyncio.get_event_loop()
        result: dict = await loop.run_in_executor(  # type: ignore
            None, lambda: self.wallet.ln.call("sql", [query.replace("\n", " ")])
        )

        if schema and schema in self.schema_cols:
            rows = [
                {self.schema_cols[schema][i]["name"]: val for i, val in enumerate(row)}
                for row in result["rows"]
            ]
        else:
            rows = result["rows"]
        return rows

    @catch_rpc_errors
    async def get_invoices(
        self, filters: Filters[NodeInvoiceFilters]
    ) -> Page[NodeInvoice]:
        result = await self.get_and_revalidate(
            lambda: self.wallet.ln_rpc("listinvoices"), key="invoices"
        )
        invoices = result["invoices"]
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
