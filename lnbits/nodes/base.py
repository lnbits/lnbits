from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, NamedTuple, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from lnbits.wallets.base import Wallet


class NodeStatsResponse(NamedTuple):
    error_message: Optional[str]
    total: int
    onchain_confirmed: int
    channel_balance: int


class NodePeerInfo(BaseModel):
    id: str
    alias: str
    color: str
    last_timestamp: Optional[int]


class ChannelState(Enum):
    ACTIVE = "active"
    PENDING = "pending"
    CLOSED = "closed"
    INACTIVE = "inactive"


class ChannelBalance(BaseModel):
    inbound_msat: int
    outbound_msat: int
    total_msat: int


class NodeChannel(BaseModel):
    short_id: Optional[str]
    funding_txid: Optional[str]
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
        active = [channel for channel in channels if channel.state == ChannelState.ACTIVE]
        return NodeChannelsResponse(
            channels=channels,
            active_balance=ChannelBalance(
                inbound_msat=sum(channel.balance.inbound_msat for channel in active),
                outbound_msat=sum(channel.balance.outbound_msat for channel in active),
                total_msat=sum(channel.balance.total_msat for channel in active),
            )
        )


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
                sum(channel.balance.total_msat for channel in channels) / len(channels)
            ),
            biggest_size=max(channel.balance.total_msat for channel in channels),
            smallest_size=min(channel.balance.total_msat for channel in channels),
            total_capacity=sum(channel.balance.total_msat for channel in channels),
        )


class NodeFees(BaseModel):
    total_msat: int
    daily_msat: Optional[int]
    weekly_msat: Optional[int]
    monthly_msat: Optional[int]


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
    fees: NodeFees
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
    destination: Optional[NodePeerInfo] = None


class NodeInvoice(BaseModel):
    pending: bool
    amount: int
    memo: Optional[str]
    time: Optional[int]
    bolt11: str
    preimage: str
    payment_hash: str
    paid_at: Optional[int] = None
    expiry: Optional[int] = None


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
        funding_txid: Optional[str] = None,
        force: bool = False,
    ):
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
    async def get_invoices(self) -> list[NodeInvoice]:
        pass

    @abstractmethod
    async def get_payment_stats(self) -> PaymentStats:
        pass
