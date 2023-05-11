from __future__ import annotations

from time import time
from typing import TYPE_CHECKING

from lnbits.nodes.base import ChannelStats, Node, PaymentStats

from .base import NodeChannel, NodeChannelsResponse, NodeInfoResponse, NodePayment

if TYPE_CHECKING:
    from lnbits.wallets import FakeWallet


class FakeNode(Node):
    wallet: FakeWallet

    async def _get_id(self) -> str:
        return "026165850492521f4ac8abd9bd8088123446d126f648ca35e60f88177dc149ceb2"

    async def get_channels(self) -> NodeChannelsResponse:
        return NodeChannelsResponse(
            error_message=None,
            channels=[
                NodeChannel(
                    peer_id="fake",
                    inbound_msat=10000,
                    outbound_msat=10000,
                    total_msat=20000,
                    name="cool fake node",
                    color="821212",
                )
            ],
        )

    async def get_info(self) -> NodeInfoResponse:
        channel_response = await self.get_channels()
        channels = channel_response.channels
        return NodeInfoResponse(
            id=await self.get_id(),
            backend_name="Fake",
            alias="FakeNode",
            color="347293",
            onchain_balance_sat=100000000,
            onchain_confirmed_sat=100000000,
            # A future implementation could leverage the `sql` rpc to calculate these
            # without having to fetch all the channels.
            channel_stats=ChannelStats.from_list(channels),
            num_peers=42,
            blockheight=130,
            balance_msat=sum(channel.inbound_msat for channel in channels),
            channels=channels,
        )

    async def get_payments(self) -> list[NodePayment]:
        return [
            NodePayment(
                pending=False,
                amount=100000,
                memo="some payment",
                time=int(time()),
                bolt11="askdfjhaskldfhasdklfjhasdh",
                preimage="0" * 64,
                payment_hash="asllasdjflsdhfaksdjfhaskdjfhaskldfh",
            )
        ]

    async def get_payment_stats(self) -> PaymentStats:
        return PaymentStats()
