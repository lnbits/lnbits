from __future__ import annotations

from typing import TYPE_CHECKING

from lnbits.nodes.base import ChannelStats, Node, PaymentStats

from .base import NodeChannel, NodeChannelsResponse, NodeInfoResponse, NodePayment

if TYPE_CHECKING:
    from lnbits.wallets import CoreLightningWallet


class CoreLightningNode(Node):
    wallet: CoreLightningWallet

    async def _get_id(self) -> str:
        if not self.id:
            info = await self.wallet.ln_rpc("getinfo")
            self.id = info["id"]
        return self.id

    async def get_channels(self) -> NodeChannelsResponse:
        funds = await self.wallet.ln_rpc("listfunds")
        nodes = await self.wallet.ln_rpc("listnodes")
        nodes_by_id = {n["nodeid"]: n for n in nodes["nodes"]}

        return NodeChannelsResponse(
            error_message=None,
            channels=[
                NodeChannel(
                    peer_id=ch["peer_id"],
                    inbound_msat=ch["our_amount_msat"],
                    outbound_msat=ch["amount_msat"] - ch["our_amount_msat"],
                    total_msat=ch["amount_msat"],
                    name=nodes_by_id.get(ch["peer_id"], {}).get("alias"),
                    color=nodes_by_id.get(ch["peer_id"], {}).get("color"),
                )
                for ch in funds["channels"]
            ],
        )

    async def get_info(self) -> NodeInfoResponse:
        info = await self.wallet.ln_rpc("getinfo")
        channel_response = await self.get_channels()
        channels = channel_response.channels
        return NodeInfoResponse(
            id=info["id"],
            alias=info["alias"],
            color=info["color"],
            # A future implementation could leverage the `sql` rpc to calculate these
            # without having to fetch all the channels.
            channel_stats=ChannelStats.from_list(channels),
            num_peers=info["num_peers"],
            blockheight=info["blockheight"],
            balance_msat=sum(channel.inbound_msat for channel in channels),
            channels=channels,
        )

    async def get_payments(self) -> list[NodePayment]:
        pays = await self.wallet.ln_rpc("listpays")
        invoices = await self.wallet.ln_rpc("listinvoices")
        results = []

        results.extend(
            NodePayment(
                bolt11=pay["bolt11"],
                amount=int(pay["amount_msat"]) * -1,
                fee=int(pay["amount_msat"]) - int(pay["amount_sent_msat"]),
                memo=pay.get("description"),
                time=pay["created_at"],
                preimage=pay["preimage"],
                payment_hash=pay["payment_hash"],
                pending=pay["status"] != "complete",
            )
            for pay in pays["pays"]
            if pay["status"] != "failed"
        )
        results.extend(
            NodePayment(
                bolt11=invoice["bolt11"],
                amount=invoice["amount_msat"],
                # fee=pay["amount_sent_msat"] - pay["amount_msat"],
                preimage=invoice.get("payment_preimage") or "0" * 64,
                memo=invoice["description"],
                time=invoice.get("paid_at", invoice["expires_at"]),
                payment_hash=invoice["payment_hash"],
                pending=invoice["status"] != "paid",
            )
            for invoice in invoices["invoices"]
        )
        results.sort(key=lambda x: x.time, reverse=True)
        return results

    async def get_payment_stats(self) -> PaymentStats:
        return PaymentStats()

