from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Optional

from fastapi import HTTPException
from httpx import HTTPStatusError
from loguru import logger

from lnbits.db import Filters, Page
from lnbits.nodes import Node
from lnbits.nodes.base import (
    ChannelBalance,
    ChannelPoint,
    ChannelState,
    ChannelStats,
    NodeChannel,
    NodeChannelsResponse,
    NodeFees,
    NodeInfoResponse,
    NodeInvoice,
    NodeInvoiceFilters,
    NodePayment,
    NodePaymentsFilters,
    NodePeerInfo,
    PaymentStats,
    PublicNodeInfo,
)

if TYPE_CHECKING:
    from lnbits.wallets import LndRestWallet


def msat(raw: str) -> int:
    return int(raw) * 1000


class LndRestNode(Node):
    wallet: LndRestWallet

    async def request(
        self, method: str, path: str, json: Optional[dict] = None, **kwargs
    ):
        response = await self.wallet.client.request(
            method, f"{self.wallet.endpoint}{path}", json=json, **kwargs
        )
        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            json = e.response.json()
            if json:
                error = json.get("error") or json
                raise HTTPException(e.response.status_code, detail=error.get("message"))
        return response.json()

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    async def _get_id(self) -> str:
        info = await self.get("/v1/getinfo")
        return info["identity_pubkey"]

    async def get_peer_ids(self) -> list[str]:
        response = await self.get("/v1/peers")
        return [p["pub_key"] for p in response["peers"]]

    async def connect_peer(self, uri: str):
        pubkey, host = uri.split("@")
        await self.request(
            "POST",
            "/v1/peers",
            json={
                "addr": {"pubkey": pubkey, "host": host},
                "perm": True,
                "timeout": 30,
            },
        )

    async def disconnect_peer(self, id: str):
        await self.request("DELETE", "/v1/peers/" + id)

    async def _get_peer_info(self, pubkey: str) -> NodePeerInfo:
        response = await self.get("/v1/graph/node/" + pubkey)
        node = response["node"]
        return NodePeerInfo(
            id=pubkey,
            alias=node["alias"],
            color=node["color"].strip("#"),
            last_timestamp=node["last_update"],
            addresses=[a["addr"] for a in node["addresses"]],
        )

    async def open_channel(
        self,
        peer_id: str,
        local_amount: int,
        push_amount: Optional[int] = None,
        fee_rate: Optional[int] = None,
    ):
        await self.request(
            "POST",
            "/v1/channels",
            data=json.dumps(
                {
                    # 'node_pubkey': base64.b64encode(peer_id.encode()).decode(),
                    "node_pubkey_string": peer_id,
                    "sat_per_vbyte": fee_rate,
                    "local_funding_amount": local_amount,
                    "push_sat": push_amount,
                }
            ),
        )
        pass

    async def _close_channel(
        self,
        point: ChannelPoint,
        force: bool = False,
    ):
        async with self.wallet.client.stream(
            "DELETE",
            f"{self.wallet.endpoint}/v1/channels/{point.funding_txid}/{point.output_index}",
            params={"force": force},
            timeout=None,
        ) as stream:
            async for chunk in stream.aiter_text():
                if chunk:
                    chunk = json.loads(chunk)
                    logger.info(f"LND Channel close update: {chunk['result']}")

    async def close_channel(
        self,
        short_id: Optional[str] = None,
        point: Optional[ChannelPoint] = None,
        force: bool = False,
    ):
        if not point:
            raise HTTPException(status_code=400, detail="Channel point required")

        asyncio.create_task(self._close_channel(point, force))

    async def get_channels(self) -> NodeChannelsResponse:
        normal, pending, closed = await asyncio.gather(
            self.get("/v1/channels"),
            self.get("/v1/channels/pending"),
            self.get("/v1/channels/closed"),
        )

        channels = []

        for channel in pending["pending_open_channels"]:
            channel = channel["channel"]
            info = await self.get_peer_info(channel["remote_node_pub"])
            channels.append(
                NodeChannel(
                    peer_id=info.id,
                    state=ChannelState.PENDING,
                    name=info.alias,
                    color=info.color,
                    balance=ChannelBalance(
                        local_msat=msat(channel["local_balance"]),
                        remote_msat=msat(channel["remote_balance"]),
                        total_msat=msat(channel["capacity"]),
                    ),
                )
            )

        for channel in closed["channels"]:
            info = await self.get_peer_info(channel["remote_pubkey"])
            channels.append(
                NodeChannel(
                    peer_id=info.id,
                    state=ChannelState.CLOSED,
                    name=info.alias,
                    color=info.color,
                    balance=ChannelBalance(
                        local_msat=0,
                        remote_msat=0,
                        total_msat=msat(channel["capacity"]),
                    ),
                )
            )

        for channel in normal["channels"]:
            info = await self.get_peer_info(channel["remote_pubkey"])
            funding_tx, output_index = channel["channel_point"].split(":")
            channels.append(
                NodeChannel(
                    short_id=channel["chan_id"],
                    point=ChannelPoint(
                        funding_txid=funding_tx,
                        output_index=output_index,
                    ),
                    peer_id=channel["remote_pubkey"],
                    balance=ChannelBalance(
                        local_msat=msat(channel["local_balance"]),
                        remote_msat=msat(channel["remote_balance"]),
                        total_msat=msat(channel["capacity"]),
                    ),
                    state=ChannelState.ACTIVE
                    if channel["active"]
                    else ChannelState.INACTIVE,
                    # name=channel['peer_alias'],
                    name=info.alias,
                    color=info.color,
                )
            )

        return NodeChannelsResponse.from_list(channels)

    async def get_public_info(self) -> PublicNodeInfo:
        info = await self.get("/v1/getinfo")
        channels = await self.get_channels()
        return PublicNodeInfo(
            backend_name="LND",
            id=info["identity_pubkey"],
            color=info["color"].lstrip("#"),
            alias=info["alias"],
            num_peers=info["num_peers"],
            blockheight=info["block_height"],
            addresses=info["uris"],
            channel_stats=ChannelStats.from_list(channels.channels),
        )

    async def get_info(self) -> NodeInfoResponse:
        public = await self.get_public_info()
        onchain = await self.get("/v1/balance/blockchain")
        fee_report = await self.get("/v1/fees")
        balance = await self.get("/v1/balance/channels")
        return NodeInfoResponse(
            **public.dict(),
            onchain_balance_sat=onchain["total_balance"],
            onchain_confirmed_sat=onchain["confirmed_balance"],
            balance_msat=balance["local_balance"]["msat"],
            fees=NodeFees(
                total_msat=0,
                daily_msat=fee_report["day_fee_sum"],
                weekly_msat=fee_report["week_fee_sum"],
                monthly_msat=fee_report["month_fee_sum"],
            ),
        )

        pass

    async def get_payments(
        self, filters: Filters[NodePaymentsFilters]
    ) -> Page[NodePayment]:
        offset = self.get_cache("payments_offset") or -1

        response = await self.get(
            "/v1/payments",
            params={
                "index_offset": offset + 1 - (filters.offset or 0),
                "max_payments": filters.limit,
                "include_incomplete": True,
                "count_total_payments": True,
                "reversed": True,
            },
        )

        self.set_cache("payments_offset", int(response["total_num_payments"]))

        payments = [
            NodePayment(
                payment_hash=payment["payment_hash"],
                pending=payment["status"] == "IN_FLIGHT",
                amount=payment["value_msat"],
                fee=payment["fee_msat"],
                time=payment["creation_date"],
                destination=await self.get_peer_info(
                    payment["htlcs"][0]["route"]["hops"][-1]["pub_key"]
                )
                if payment["htlcs"]
                else None,
                bolt11=payment["payment_request"],
                preimage=payment["payment_preimage"],
            )
            for payment in response["payments"]
        ]

        payments.sort(key=lambda p: p.time, reverse=True)

        return Page(data=payments, total=response["total_num_payments"])

    async def get_invoices(
        self, filters: Filters[NodeInvoiceFilters]
    ) -> Page[NodeInvoice]:
        offset = filters.offset or 0

        response = await self.get(
            "/v1/invoices",
            params={
                "index_offset": offset,
                "num_max_invoices": filters.limit,
            },
        )
        invoices = [
            NodeInvoice(
                payment_hash=invoice["r_hash"],
                amount=invoice["value_msat"],
                memo=invoice["memo"],
                pending=invoice["state"] == "OPEN",
                paid_at=invoice["settle_date"],
                expiry=invoice["creation_date"] + invoice["expiry"],
                preimage=invoice["r_preimage"],
                bolt11=invoice["payment_request"],
            )
            for invoice in response["invoices"]
        ]
        # we simply guess that there is at least one more page because
        # lnd doesnt provide the total amount of invoices
        total = len(invoices) + offset
        if len(invoices) == filters.limit and filters.limit:
            total += filters.limit
        return Page(
            data=invoices,
            total=total,
        )

    async def get_payment_stats(self) -> PaymentStats:
        return PaymentStats(volume=0)
