from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, NamedTuple, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from lnbits.wallets.base import Wallet


class NodeStatsResponse(NamedTuple):
    error_message: Optional[str]
    total: int
    onchain_confirmed: int
    channel_balance: int


class NodeChannel(BaseModel):
    peer_id: str
    inbound_msat: int
    outbound_msat: int
    total_msat: int
    name: Optional[str]
    color: Optional[str]


class NodeChannelsResponse(BaseModel):
    error_message: Optional[str]
    channels: list[NodeChannel]


class ChannelStats(BaseModel):
    num_active: int
    avg_size: int
    biggest_size: Optional[int]
    smallest_size: Optional[int]
    total_capacity: int

    @classmethod
    def from_list(cls, channels: list[NodeChannel]):
        return cls(
            num_active=len(channels),
            avg_size=int(
                sum(channel.total_msat for channel in channels) / len(channels)
            ),
            biggest_size=max(channel.total_msat for channel in channels),
            smallest_size=min(channel.total_msat for channel in channels),
            total_capacity=sum(channel.total_msat for channel in channels),
        )


class NodeInfoResponse(BaseModel):
    id: str
    backend_name: str
    alias: str
    color: str
    balance_msat: int
    onchain_balance_sat: int
    onchain_confirmed_sat: int
    num_peers: int
    blockheight: int

    channels: list[NodeChannel]
    channel_stats: ChannelStats
    # addresses: list[str]


class NodePayment(BaseModel):
    pending: bool
    amount: int
    fee: Optional[int] = None
    memo: Optional[str]
    time: Optional[int]
    bolt11: str
    preimage: str
    payment_hash: str
    expiry: Optional[float] = None


class NodePeerInfo(BaseModel):
    id: str
    alias: str
    color: str
    last_timestamp: Optional[int]


class PaymentStats(BaseModel):
    volume: int


class NodePaymentsResponse(BaseModel):
    error_message: Optional[str]
    payments: list[NodePayment]


class Node(ABC):
    wallet: Wallet

    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        self.id: Optional[str] = None

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
    async def connect_peer(self, uri: str) -> bool:
        pass

    @abstractmethod
    async def get_peer_info(self, pubkey: str) -> NodePeerInfo:
        pass

    @abstractmethod
    async def open_channel(self, peer_id: str, funding_amount: int):
        pass

    @abstractmethod
    async def close_channel(self, channel_id: str):
        pass

    @abstractmethod
    async def get_channels(self) -> NodeChannelsResponse:
        pass

    @abstractmethod
    async def get_info(self) -> NodeInfoResponse:
        pass

    @abstractmethod
    async def get_payments(self) -> list[NodePayment]:
        pass

    @abstractmethod
    async def get_payment_stats(self) -> PaymentStats:
        pass
