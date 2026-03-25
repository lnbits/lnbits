from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from lnbits.db import FilterModel, Filters, Page
from lnbits.utils.cache import cache

if TYPE_CHECKING:
    from lnbits.wallets.base import Wallet


class NodePeerInfo(BaseModel):
    id: str
    alias: str | None = None
    color: str | None = None
    last_timestamp: int | None = None
    addresses: list[str] | None = None


class ChannelState(Enum):
    ACTIVE = "active"
    PENDING = "pending"
    CLOSED = "closed"
    INACTIVE = "inactive"


class ChannelBalance(BaseModel):
    local_msat: int
    remote_msat: int
    total_msat: int


class ChannelPoint(BaseModel):
    funding_txid: str
    output_index: int

    def __str__(self):
        return f"{self.funding_txid}:{self.output_index}"


class NodeChannel(BaseModel):
    peer_id: str
    balance: ChannelBalance
    state: ChannelState
    # could be optional for closing/pending channels on lndrest
    id: str | None = None
    short_id: str | None = None
    point: ChannelPoint | None = None
    name: str | None = None
    color: str | None = None
    fee_ppm: int | None = None
    fee_base_msat: int | None = None


class ChannelStats(BaseModel):
    counts: dict[ChannelState, int]
    avg_size: int
    biggest_size: int | None
    smallest_size: int | None
    total_capacity: int

    @classmethod
    def from_list(cls, channels: list[NodeChannel]):
        counts: dict[ChannelState, int] = {}
        for channel in channels:
            counts[channel.state] = counts.get(channel.state, 0) + 1

        active_channel_sizes = [
            channel.balance.total_msat
            for channel in channels
            if channel.state == ChannelState.ACTIVE
        ]

        if len(active_channel_sizes) > 0:
            return cls(
                counts=counts,
                avg_size=int(sum(active_channel_sizes) / len(active_channel_sizes)),
                biggest_size=max(active_channel_sizes),
                smallest_size=min(active_channel_sizes),
                total_capacity=sum(active_channel_sizes),
            )
        else:
            return cls(
                counts=counts,
                avg_size=0,
                biggest_size=0,
                smallest_size=0,
                total_capacity=0,
            )


class NodeFees(BaseModel):
    total_msat: int
    daily_msat: int | None = None
    weekly_msat: int | None = None
    monthly_msat: int | None = None


class PublicNodeInfo(BaseModel):
    id: str
    backend_name: str
    alias: str
    color: str
    num_peers: int
    blockheight: int
    channel_stats: ChannelStats
    addresses: list[str]


class NodeInfoResponse(PublicNodeInfo):
    onchain_balance_sat: int
    onchain_confirmed_sat: int
    fees: NodeFees
    balance_msat: int


class NodePayment(BaseModel):
    pending: bool
    amount: int
    fee: int | None = None
    memo: str | None = None
    time: int
    bolt11: str | None = None
    preimage: str | None
    payment_hash: str
    expiry: float | None = None
    destination: NodePeerInfo | None = None


class NodeInvoice(BaseModel):
    pending: bool
    amount: int
    memo: str | None
    bolt11: str
    preimage: str | None
    payment_hash: str
    paid_at: int | None = None
    expiry: int | None = None


class NodeInvoiceFilters(FilterModel):
    pass


class NodePaymentsFilters(FilterModel):
    pass


class Node(ABC):

    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        self.id: str | None = None

    @property
    def name(self):
        return self.__class__.__name__

    async def get_id(self):
        if not self.id:
            self.id = await self._get_id()
        return self.id

    @abstractmethod
    async def _get_id(self) -> str:
        raise NotImplementedError

    async def get_peers(self) -> list[NodePeerInfo]:
        peer_ids = await self.get_peer_ids()
        return [await self.get_peer_info(peer_id) for peer_id in peer_ids]

    @abstractmethod
    async def get_peer_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def connect_peer(self, uri: str):
        raise NotImplementedError

    @abstractmethod
    async def disconnect_peer(self, peer_id: str):
        raise NotImplementedError

    @abstractmethod
    async def _get_peer_info(self, peer_id: str) -> NodePeerInfo:
        pass

    async def get_peer_info(self, peer_id: str) -> NodePeerInfo:
        key = f"node:peers:{peer_id}"
        info = cache.get(key)
        if not info:
            info = await self._get_peer_info(peer_id)
            if info.last_timestamp:
                cache.set(key, info)
        return info

    @abstractmethod
    async def open_channel(
        self,
        peer_id: str,
        local_amount: int,
        push_amount: int | None = None,
        fee_rate: int | None = None,
    ) -> ChannelPoint:
        raise NotImplementedError

    @abstractmethod
    async def close_channel(
        self,
        short_id: str | None = None,
        point: ChannelPoint | None = None,
        force: bool = False,
    ):
        raise NotImplementedError

    @abstractmethod
    async def get_channel(self, channel_id: str) -> NodeChannel | None:
        raise NotImplementedError

    @abstractmethod
    async def get_channels(self) -> list[NodeChannel]:
        raise NotImplementedError

    @abstractmethod
    async def set_channel_fee(self, channel_id: str, base_msat: int, ppm: int):
        raise NotImplementedError

    @abstractmethod
    async def get_info(self) -> NodeInfoResponse:
        raise NotImplementedError

    async def get_public_info(self) -> PublicNodeInfo:
        info = await self.get_info()
        return PublicNodeInfo(**info.__dict__)

    @abstractmethod
    async def get_payments(
        self, filters: Filters[NodePaymentsFilters]
    ) -> Page[NodePayment]:
        raise NotImplementedError

    @abstractmethod
    async def get_invoices(
        self, filters: Filters[NodeInvoiceFilters]
    ) -> Page[NodeInvoice]:
        raise NotImplementedError
