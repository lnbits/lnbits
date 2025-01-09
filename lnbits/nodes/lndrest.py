from __future__ import annotations

import asyncio
import base64
import json
from http import HTTPStatus
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
    NodeFees,
    NodeInfoResponse,
    NodeInvoice,
    NodeInvoiceFilters,
    NodePayment,
    NodePaymentsFilters,
    NodePeerInfo,
    PublicNodeInfo,
)
from lnbits.utils.cache import cache

if TYPE_CHECKING:
    from lnbits.wallets import LndRestWallet


def msat(raw: str) -> int:
    return int(raw) * 1000


def _decode_bytes(data: str) -> str:
    return base64.b64decode(data).hex()


def _encode_bytes(data: str) -> str:
    return base64.b64encode(bytes.fromhex(data)).decode()


def _encode_urlsafe_bytes(data: str) -> str:
    return base64.urlsafe_b64encode(bytes.fromhex(data)).decode()


def _parse_channel_point(raw: str) -> ChannelPoint:
    funding_tx, output_index = raw.split(":")
    return ChannelPoint(
        funding_txid=funding_tx,
        output_index=int(output_index),
    )


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
        except HTTPStatusError as exc:
            json = exc.response.json()
            if json:
                error = json.get("error") or json
                raise HTTPException(
                    exc.response.status_code, detail=error.get("message")
                ) from exc
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
        try:
            pubkey, host = uri.split("@")
        except ValueError as exc:
            raise HTTPException(400, detail="Invalid peer URI") from exc
        await self.request(
            "POST",
            "/v1/peers",
            json={
                "addr": {"pubkey": pubkey, "host": host},
                "perm": True,
                "timeout": 30,
            },
        )

    async def disconnect_peer(self, peer_id: str):
        try:
            await self.request("DELETE", "/v1/peers/" + peer_id)
        except HTTPException as exc:
            if "unable to disconnect" in exc.detail:
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST, detail="Peer is not connected"
                ) from exc
            raise

    async def _get_peer_info(self, peer_id: str) -> NodePeerInfo:
        try:
            response = await self.get("/v1/graph/node/" + peer_id)
        except HTTPException:
            return NodePeerInfo(id=peer_id)
        node = response["node"]
        return NodePeerInfo(
            id=peer_id,
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
    ) -> ChannelPoint:
        response = await self.request(
            "POST",
            "/v1/channels",
            json={
                "node_pubkey": _encode_bytes(peer_id),
                "sat_per_vbyte": fee_rate,
                "local_funding_amount": local_amount,
                "push_sat": push_amount,
            },
        )
        return ChannelPoint(
            # WHY IS THIS REVERSED?!
            funding_txid=bytes(
                reversed(base64.b64decode(response["funding_txid_bytes"]))
            ).hex(),
            output_index=response["output_index"],
        )

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
                if not chunk:
                    continue
                chunk = json.loads(chunk)
                if "error" in chunk:
                    raise HTTPException(
                        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                        detail=chunk["error"].get("message"),
                    )
                logger.info(f"LND Channel close update: {chunk.get('result')}")

    async def close_channel(
        self,
        short_id: Optional[str] = None,
        point: Optional[ChannelPoint] = None,
        force: bool = False,
    ):
        if short_id:
            logger.debug(f"Closing channel with short_id: {short_id}")
        if not point:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Channel point required"
            )

        asyncio.create_task(self._close_channel(point, force))  # noqa: RUF006

    async def set_channel_fee(self, channel_id: str, base_msat: int, ppm: int):
        # https://lightning.engineering/api-docs/api/lnd/lightning/update-channel-policy/
        channel = await self.get_channel(channel_id)
        if not channel:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Channel not found"
            )
        if not channel.point:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Channel point required"
            )
        await self.request(
            "POST",
            "/v1/chanpolicy",
            json={
                "base_fee_msat": base_msat,
                "fee_rate_ppm": ppm,
                "chan_point": {
                    "funding_txid_str": channel.point.funding_txid,
                    "output_index": channel.point.output_index,
                },
                # https://docs.lightning.engineering/lightning-network-tools/lnd/optimal-configuration-of-a-routing-node#channel-defaults
                "time_lock_delta": 80,
                # 'max_htlc_msat': <uint64>,
                # 'min_htlc_msat': <uint64>,
                # 'inbound_fee': <InboundFee>,
            },
        )

    async def get_channel(self, channel_id: str) -> Optional[NodeChannel]:
        channel_info = await self.get(f"/v1/graph/edge/{channel_id}")
        info = await self.get("/v1/getinfo")
        if info["identity_pubkey"] == channel_info["node1_pub"]:
            my_node_key = "node1"
            peer_node_key = "node2"
        else:
            my_node_key = "node2"
            peer_node_key = "node1"
        peer_id = channel_info[f"{peer_node_key}_pub"]
        peer_b64 = _encode_urlsafe_bytes(peer_id)
        channels = await self.get(f"/v1/channels?peer={peer_b64}")
        if "error" in channel_info and "error" in channels:
            logger.debug("LND get_channel", channels)
            return None
        if len(channels["channels"]) == 0:
            logger.debug(f"LND get_channel no channels founds with id {peer_b64}")
            return None
        for channel in channels["channels"]:
            if channel["chan_id"] == channel_id:
                peer_info = await self.get_peer_info(peer_id)
                return NodeChannel(
                    id=channel.get("chan_id"),
                    peer_id=peer_info.id,
                    name=peer_info.alias,
                    color=peer_info.color,
                    state=(
                        ChannelState.ACTIVE
                        if channel["active"]
                        else ChannelState.INACTIVE
                    ),
                    fee_ppm=channel_info[f"{my_node_key}_policy"][
                        "fee_rate_milli_msat"
                    ],
                    fee_base_msat=channel_info[f"{my_node_key}_policy"][
                        "fee_base_msat"
                    ],
                    point=_parse_channel_point(channel["channel_point"]),
                    balance=ChannelBalance(
                        local_msat=msat(channel["local_balance"]),
                        remote_msat=msat(channel["remote_balance"]),
                        total_msat=msat(channel["capacity"]),
                    ),
                )
        return None

    async def get_channels(self) -> list[NodeChannel]:
        normal, pending, closed = await asyncio.gather(
            self.get("/v1/channels"),
            self.get("/v1/channels/pending"),
            self.get("/v1/channels/closed"),
        )

        channels = []

        async def parse_pending(raw_channels, state):
            for channel in raw_channels:
                channel = channel["channel"]
                info = await self.get_peer_info(channel["remote_node_pub"])
                channels.append(
                    NodeChannel(
                        peer_id=info.id,
                        state=state,
                        name=info.alias,
                        color=info.color,
                        id=channel.get("chan_id", "node is for pending channels"),
                        point=_parse_channel_point(channel["channel_point"]),
                        balance=ChannelBalance(
                            local_msat=msat(channel["local_balance"]),
                            remote_msat=msat(channel["remote_balance"]),
                            total_msat=msat(channel["capacity"]),
                        ),
                    )
                )

        await parse_pending(pending["pending_open_channels"], ChannelState.PENDING)
        await parse_pending(
            pending["pending_force_closing_channels"], ChannelState.CLOSED
        )
        await parse_pending(pending["waiting_close_channels"], ChannelState.CLOSED)

        for channel in closed["channels"]:
            info = await self.get_peer_info(channel["remote_pubkey"])
            channels.append(
                NodeChannel(
                    id=channel.get("chan_id", "node is for closing channels"),
                    peer_id=info.id,
                    state=ChannelState.CLOSED,
                    name=info.alias,
                    color=info.color,
                    point=_parse_channel_point(channel["channel_point"]),
                    balance=ChannelBalance(
                        local_msat=0,
                        remote_msat=0,
                        total_msat=msat(channel["capacity"]),
                    ),
                )
            )

        for channel in normal["channels"]:
            info = await self.get_peer_info(channel["remote_pubkey"])
            channels.append(
                NodeChannel(
                    id=channel["chan_id"],
                    short_id=channel["chan_id"],
                    point=_parse_channel_point(channel["channel_point"]),
                    peer_id=channel["remote_pubkey"],
                    balance=ChannelBalance(
                        local_msat=msat(channel["local_balance"]),
                        remote_msat=msat(channel["remote_balance"]),
                        total_msat=msat(channel["capacity"]),
                    ),
                    state=(
                        ChannelState.ACTIVE
                        if channel["active"]
                        else ChannelState.INACTIVE
                    ),
                    # name=channel['peer_alias'],
                    name=info.alias,
                    color=info.color,
                )
            )

        return channels

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
            channel_stats=ChannelStats.from_list(channels),
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

    async def get_payments(
        self, filters: Filters[NodePaymentsFilters]
    ) -> Page[NodePayment]:
        count_key = "node:payments_count"
        payments_count = cache.get(count_key)
        if not payments_count and filters.offset:
            # this forces fetching the payments count
            await self.get_payments(Filters(limit=1))
            payments_count = cache.get(count_key)

        if filters.offset and payments_count:
            index_offset = max(payments_count + 1 - filters.offset, 0)
        else:
            index_offset = 0

        response = await self.get(
            "/v1/payments",
            params={
                "index_offset": index_offset,
                "max_payments": filters.limit,
                "include_incomplete": True,
                "reversed": True,
                "count_total_payments": not index_offset,
            },
        )

        if not filters.offset:
            payments_count = int(response["total_num_payments"])

        cache.set(count_key, payments_count)

        payments = [
            NodePayment(
                payment_hash=payment["payment_hash"],
                pending=payment["status"] == "IN_FLIGHT",
                amount=payment["value_msat"],
                fee=payment["fee_msat"],
                time=payment["creation_date"],
                destination=(
                    await self.get_peer_info(
                        payment["htlcs"][0]["route"]["hops"][-1]["pub_key"]
                    )
                    if payment["htlcs"]
                    else None
                ),
                bolt11=payment["payment_request"],
                preimage=payment["payment_preimage"],
            )
            for payment in response["payments"]
        ]

        payments.sort(key=lambda p: p.time, reverse=True)

        return Page(data=payments, total=payments_count or 0)

    async def get_invoices(
        self, filters: Filters[NodeInvoiceFilters]
    ) -> Page[NodeInvoice]:
        last_invoice_key = "node:last_invoice_index"
        last_invoice_index = cache.get(last_invoice_key)
        if not last_invoice_index and filters.offset:
            # this forces fetching the last invoice index so
            await self.get_invoices(Filters(limit=1))
            last_invoice_index = cache.get(last_invoice_key)

        if filters.offset and last_invoice_index:
            index_offset = max(last_invoice_index + 1 - filters.offset, 0)
        else:
            index_offset = 0

        response = await self.get(
            "/v1/invoices",
            params={
                "index_offset": index_offset,
                "num_max_invoices": filters.limit,
                "reversed": True,
            },
        )

        if not filters.offset:
            last_invoice_index = int(response["last_index_offset"])

        cache.set(last_invoice_key, last_invoice_index)

        invoices = [
            NodeInvoice(
                payment_hash=_decode_bytes(invoice["r_hash"]),
                amount=invoice["value_msat"],
                memo=invoice["memo"],
                pending=invoice["state"] == "OPEN",
                paid_at=invoice["settle_date"],
                expiry=int(invoice["creation_date"]) + int(invoice["expiry"]),
                preimage=_decode_bytes(invoice["r_preimage"]),
                bolt11=invoice["payment_request"],
            )
            for invoice in reversed(response["invoices"])
        ]

        return Page(
            data=invoices,
            total=last_invoice_index or 0,
        )
