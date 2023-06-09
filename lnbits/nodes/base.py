from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from time import time
from typing import TYPE_CHECKING, Any, NamedTuple, Optional

from loguru import logger
from pydantic import BaseModel

from lnbits.db import FilterModel, Filters, Page

if TYPE_CHECKING:
    from lnbits.wallets.base import Wallet


class NodeStatsResponse(NamedTuple):
    error_message: Optional[str]
    total: int
    onchain_confirmed: int
    channel_balance: int


class NodePeerInfo(BaseModel):
    id: str
    alias: Optional[str] = None
    color: Optional[str] = None
    last_timestamp: Optional[int] = None
    addresses: Optional[list[str]] = None


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


class NodeChannel(BaseModel):
    short_id: Optional[str] = None
    point: Optional[ChannelPoint] = None
    peer_id: str
    balance: ChannelBalance
    state: ChannelState
    name: Optional[str]
    color: Optional[str]


class NodeChannelsResponse(BaseModel):
    channels: list[NodeChannel]
    active_balance: ChannelBalance

    @classmethod
    def from_list(cls, channels: list[NodeChannel]):
        active = [
            channel for channel in channels if channel.state == ChannelState.ACTIVE
        ]
        return NodeChannelsResponse(
            channels=channels,
            active_balance=ChannelBalance(
                local_msat=sum(channel.balance.local_msat for channel in active),
                remote_msat=sum(channel.balance.remote_msat for channel in active),
                total_msat=sum(channel.balance.total_msat for channel in active),
            ),
        )


class ChannelStats(BaseModel):
    counts: dict[ChannelState, int]
    avg_size: int
    biggest_size: Optional[int]
    smallest_size: Optional[int]
    total_capacity: int

    @classmethod
    def from_list(cls, channels: list[NodeChannel]):
        counts: dict[ChannelState, int] = {}
        for channel in channels:
            counts[channel.state] = counts.get(channel.state, 0) + 1

        return cls(
            counts=counts,
            avg_size=int(
                sum(channel.balance.total_msat for channel in channels) / len(channels)
            ),
            biggest_size=max(channel.balance.total_msat for channel in channels),
            smallest_size=min(channel.balance.total_msat for channel in channels),
            total_capacity=sum(channel.balance.total_msat for channel in channels),
        )


class NodeFees(BaseModel):
    total_msat: int
    daily_msat: Optional[int] = None
    weekly_msat: Optional[int] = None
    monthly_msat: Optional[int] = None


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
    fee: Optional[int] = None
    memo: Optional[str] = None
    time: int
    bolt11: str
    preimage: Optional[str]
    payment_hash: str
    expiry: Optional[float] = None
    destination: Optional[NodePeerInfo] = None


class NodeInvoice(BaseModel):
    pending: bool
    amount: int
    memo: Optional[str]
    bolt11: str
    preimage: Optional[str]
    payment_hash: str
    paid_at: Optional[int] = None
    expiry: Optional[int] = None


class PaymentStats(BaseModel):
    volume: int


class NodePaymentsResponse(BaseModel):
    error_message: Optional[str]
    payments: list[NodePayment]


class NodeInvoiceFilters(FilterModel):
    pass


class NodePaymentsFilters(FilterModel):
    pass


class Cached(NamedTuple):
    value: Any
    stale: float
    expiry: float


class Node(ABC):
    wallet: Wallet

    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        self.id: Optional[str] = None
        self.cache: dict[Any, Cached] = {}

    async def startup(self):
        asyncio.create_task(self.invalide_cache())

    async def get_id(self):
        if not self.id:
            self.id = await self._get_id()
        return self.id

    @abstractmethod
    async def _get_id(self) -> str:
        pass

    async def get_peers(self) -> list[NodePeerInfo]:
        ids = await self.get_peer_ids()
        return [await self.get_peer_info(pubkey) for pubkey in ids]

    @abstractmethod
    async def get_peer_ids(self) -> list[str]:
        pass

    @abstractmethod
    async def connect_peer(self, uri: str):
        pass

    @abstractmethod
    async def disconnect_peer(self, id: str):
        pass

    @abstractmethod
    async def _get_peer_info(self, pubkey: str) -> NodePeerInfo:
        pass

    async def get_peer_info(self, pubkey: str) -> NodePeerInfo:
        info = self.get_cache(f"peers:{pubkey}")
        if not info:
            info = await self._get_peer_info(pubkey)
            if info.last_timestamp:
                self.set_cache(f"peers:{pubkey}", info)
        return info

    @abstractmethod
    async def open_channel(
        self,
        peer_id: str,
        local_amount: int,
        push_amount: Optional[int] = None,
        fee_rate: Optional[int] = None,
    ):
        pass

    @abstractmethod
    async def close_channel(
        self,
        short_id: Optional[str] = None,
        point: Optional[ChannelPoint] = None,
        force: bool = False,
    ):
        pass

    @abstractmethod
    async def get_channels(self) -> NodeChannelsResponse:
        pass

    @abstractmethod
    async def get_info(self) -> NodeInfoResponse:
        pass

    async def get_public_info(self) -> PublicNodeInfo:
        info = await self.get_info()
        return PublicNodeInfo(**info.__dict__)

    @abstractmethod
    async def get_payments(
        self, filters: Filters[NodePaymentsFilters]
    ) -> Page[NodePayment]:
        pass

    @abstractmethod
    async def get_invoices(
        self, filters: Filters[NodeInvoiceFilters]
    ) -> Page[NodeInvoice]:
        pass

    @abstractmethod
    async def get_payment_stats(self) -> PaymentStats:
        pass

    async def get_and_revalidate(self, coro, key: str, expiry: float = 20):
        """
        Stale while revalidate cache
        Gets a result from the cache if it exists, otherwise run the coroutine and cache the result
        """
        cached = self.cache.get(key)
        if cached:
            ts = time()
            if ts < cached.expiry:
                if ts > cached.stale:
                    asyncio.create_task(coro()).add_done_callback(
                        lambda fut: self.set_cache(key, fut.result(), expiry)
                    )
                return cached.value
        value = await coro()
        self.set_cache(key, value, expiry)
        return value

    async def invalide_cache(self):
        while True:
            try:
                await asyncio.sleep(60)
                ts = time()
                self.cache = {k: v for k, v in self.cache.items() if v.expiry > ts}
            except Exception:
                logger.error("Error invalidating cache")

    def get_cache(self, key: str) -> Optional[Any]:
        cached = self.cache.get(key)
        if cached is not None:
            if cached.expiry > time():
                return cached.value
            else:
                self.cache.pop(key)
        return None

    def set_cache(self, key: str, value: Any, expiry: float = 10):
        self.cache[key] = Cached(value, time() + expiry / 2, time() + expiry)
