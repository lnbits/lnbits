from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import (
    ClassVar as _ClassVar,
    Iterable as _Iterable,
    Mapping as _Mapping,
    Optional as _Optional,
    Union as _Union,
)

DESCRIPTOR: _descriptor.FileDescriptor

class MacaroonAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    READ: _ClassVar[MacaroonAction]
    WRITE: _ClassVar[MacaroonAction]

class SwapState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PENDING: _ClassVar[SwapState]
    SUCCESSFUL: _ClassVar[SwapState]
    ERROR: _ClassVar[SwapState]
    SERVER_ERROR: _ClassVar[SwapState]
    REFUNDED: _ClassVar[SwapState]
    ABANDONED: _ClassVar[SwapState]

class Currency(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BTC: _ClassVar[Currency]
    LBTC: _ClassVar[Currency]

class SwapType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SUBMARINE: _ClassVar[SwapType]
    REVERSE: _ClassVar[SwapType]
    CHAIN: _ClassVar[SwapType]

class IncludeSwaps(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ALL: _ClassVar[IncludeSwaps]
    MANUAL: _ClassVar[IncludeSwaps]
    AUTO: _ClassVar[IncludeSwaps]

READ: MacaroonAction
WRITE: MacaroonAction
PENDING: SwapState
SUCCESSFUL: SwapState
ERROR: SwapState
SERVER_ERROR: SwapState
REFUNDED: SwapState
ABANDONED: SwapState
BTC: Currency
LBTC: Currency
SUBMARINE: SwapType
REVERSE: SwapType
CHAIN: SwapType
ALL: IncludeSwaps
MANUAL: IncludeSwaps
AUTO: IncludeSwaps

class CreateTenantRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class ListTenantsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListTenantsResponse(_message.Message):
    __slots__ = ("tenants",)
    TENANTS_FIELD_NUMBER: _ClassVar[int]
    tenants: _containers.RepeatedCompositeFieldContainer[Tenant]
    def __init__(
        self, tenants: _Optional[_Iterable[_Union[Tenant, _Mapping]]] = ...
    ) -> None: ...

class GetTenantRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class Tenant(_message.Message):
    __slots__ = ("id", "name")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    def __init__(
        self, id: _Optional[int] = ..., name: _Optional[str] = ...
    ) -> None: ...

class MacaroonPermissions(_message.Message):
    __slots__ = ("action",)
    ACTION_FIELD_NUMBER: _ClassVar[int]
    action: MacaroonAction
    def __init__(
        self, action: _Optional[_Union[MacaroonAction, str]] = ...
    ) -> None: ...

class BakeMacaroonRequest(_message.Message):
    __slots__ = ("tenant_id", "permissions")
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    tenant_id: int
    permissions: _containers.RepeatedCompositeFieldContainer[MacaroonPermissions]
    def __init__(
        self,
        tenant_id: _Optional[int] = ...,
        permissions: _Optional[_Iterable[_Union[MacaroonPermissions, _Mapping]]] = ...,
    ) -> None: ...

class BakeMacaroonResponse(_message.Message):
    __slots__ = ("macaroon",)
    MACAROON_FIELD_NUMBER: _ClassVar[int]
    macaroon: str
    def __init__(self, macaroon: _Optional[str] = ...) -> None: ...

class Pair(_message.Message):
    __slots__ = ("to",)
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    to: Currency
    def __init__(
        self, to: _Optional[_Union[Currency, str]] = ..., **kwargs
    ) -> None: ...

class SwapInfo(_message.Message):
    __slots__ = (
        "id",
        "pair",
        "state",
        "error",
        "status",
        "private_key",
        "preimage",
        "redeem_script",
        "invoice",
        "lockup_address",
        "expected_amount",
        "timeout_block_height",
        "lockup_transaction_id",
        "refund_transaction_id",
        "refund_address",
        "chan_ids",
        "blinding_key",
        "created_at",
        "service_fee",
        "onchain_fee",
        "wallet_id",
        "tenant_id",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_KEY_FIELD_NUMBER: _ClassVar[int]
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    REDEEM_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    INVOICE_FIELD_NUMBER: _ClassVar[int]
    LOCKUP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    LOCKUP_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    REFUND_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    REFUND_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    CHAN_IDS_FIELD_NUMBER: _ClassVar[int]
    BLINDING_KEY_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FEE_FIELD_NUMBER: _ClassVar[int]
    ONCHAIN_FEE_FIELD_NUMBER: _ClassVar[int]
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    pair: Pair
    state: SwapState
    error: str
    status: str
    private_key: str
    preimage: str
    redeem_script: str
    invoice: str
    lockup_address: str
    expected_amount: int
    timeout_block_height: int
    lockup_transaction_id: str
    refund_transaction_id: str
    refund_address: str
    chan_ids: _containers.RepeatedCompositeFieldContainer[ChannelId]
    blinding_key: str
    created_at: int
    service_fee: int
    onchain_fee: int
    wallet_id: int
    tenant_id: int
    def __init__(
        self,
        id: _Optional[str] = ...,
        pair: _Optional[_Union[Pair, _Mapping]] = ...,
        state: _Optional[_Union[SwapState, str]] = ...,
        error: _Optional[str] = ...,
        status: _Optional[str] = ...,
        private_key: _Optional[str] = ...,
        preimage: _Optional[str] = ...,
        redeem_script: _Optional[str] = ...,
        invoice: _Optional[str] = ...,
        lockup_address: _Optional[str] = ...,
        expected_amount: _Optional[int] = ...,
        timeout_block_height: _Optional[int] = ...,
        lockup_transaction_id: _Optional[str] = ...,
        refund_transaction_id: _Optional[str] = ...,
        refund_address: _Optional[str] = ...,
        chan_ids: _Optional[_Iterable[_Union[ChannelId, _Mapping]]] = ...,
        blinding_key: _Optional[str] = ...,
        created_at: _Optional[int] = ...,
        service_fee: _Optional[int] = ...,
        onchain_fee: _Optional[int] = ...,
        wallet_id: _Optional[int] = ...,
        tenant_id: _Optional[int] = ...,
    ) -> None: ...

class GetPairInfoRequest(_message.Message):
    __slots__ = ("type", "pair")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    type: SwapType
    pair: Pair
    def __init__(
        self,
        type: _Optional[_Union[SwapType, str]] = ...,
        pair: _Optional[_Union[Pair, _Mapping]] = ...,
    ) -> None: ...

class PairInfo(_message.Message):
    __slots__ = ("pair", "fees", "limits", "hash")
    PAIR_FIELD_NUMBER: _ClassVar[int]
    FEES_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    pair: Pair
    fees: SwapFees
    limits: Limits
    hash: str
    def __init__(
        self,
        pair: _Optional[_Union[Pair, _Mapping]] = ...,
        fees: _Optional[_Union[SwapFees, _Mapping]] = ...,
        limits: _Optional[_Union[Limits, _Mapping]] = ...,
        hash: _Optional[str] = ...,
    ) -> None: ...

class ChannelCreationInfo(_message.Message):
    __slots__ = (
        "swap_id",
        "status",
        "inbound_liquidity",
        "private",
        "funding_transaction_id",
        "funding_transaction_vout",
    )
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    INBOUND_LIQUIDITY_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    FUNDING_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    FUNDING_TRANSACTION_VOUT_FIELD_NUMBER: _ClassVar[int]
    swap_id: str
    status: str
    inbound_liquidity: int
    private: bool
    funding_transaction_id: str
    funding_transaction_vout: int
    def __init__(
        self,
        swap_id: _Optional[str] = ...,
        status: _Optional[str] = ...,
        inbound_liquidity: _Optional[int] = ...,
        private: bool = ...,
        funding_transaction_id: _Optional[str] = ...,
        funding_transaction_vout: _Optional[int] = ...,
    ) -> None: ...

class CombinedChannelSwapInfo(_message.Message):
    __slots__ = ("swap", "channel_creation")
    SWAP_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_CREATION_FIELD_NUMBER: _ClassVar[int]
    swap: SwapInfo
    channel_creation: ChannelCreationInfo
    def __init__(
        self,
        swap: _Optional[_Union[SwapInfo, _Mapping]] = ...,
        channel_creation: _Optional[_Union[ChannelCreationInfo, _Mapping]] = ...,
    ) -> None: ...

class ReverseSwapInfo(_message.Message):
    __slots__ = (
        "id",
        "state",
        "error",
        "status",
        "private_key",
        "preimage",
        "redeem_script",
        "invoice",
        "claim_address",
        "onchain_amount",
        "timeout_block_height",
        "lockup_transaction_id",
        "claim_transaction_id",
        "pair",
        "chan_ids",
        "blinding_key",
        "created_at",
        "paid_at",
        "service_fee",
        "onchain_fee",
        "routing_fee_msat",
        "external_pay",
        "tenant_id",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_KEY_FIELD_NUMBER: _ClassVar[int]
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    REDEEM_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    INVOICE_FIELD_NUMBER: _ClassVar[int]
    CLAIM_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    ONCHAIN_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    LOCKUP_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    CLAIM_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    CHAN_IDS_FIELD_NUMBER: _ClassVar[int]
    BLINDING_KEY_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    PAID_AT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FEE_FIELD_NUMBER: _ClassVar[int]
    ONCHAIN_FEE_FIELD_NUMBER: _ClassVar[int]
    ROUTING_FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_PAY_FIELD_NUMBER: _ClassVar[int]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    state: SwapState
    error: str
    status: str
    private_key: str
    preimage: str
    redeem_script: str
    invoice: str
    claim_address: str
    onchain_amount: int
    timeout_block_height: int
    lockup_transaction_id: str
    claim_transaction_id: str
    pair: Pair
    chan_ids: _containers.RepeatedCompositeFieldContainer[ChannelId]
    blinding_key: str
    created_at: int
    paid_at: int
    service_fee: int
    onchain_fee: int
    routing_fee_msat: int
    external_pay: bool
    tenant_id: int
    def __init__(
        self,
        id: _Optional[str] = ...,
        state: _Optional[_Union[SwapState, str]] = ...,
        error: _Optional[str] = ...,
        status: _Optional[str] = ...,
        private_key: _Optional[str] = ...,
        preimage: _Optional[str] = ...,
        redeem_script: _Optional[str] = ...,
        invoice: _Optional[str] = ...,
        claim_address: _Optional[str] = ...,
        onchain_amount: _Optional[int] = ...,
        timeout_block_height: _Optional[int] = ...,
        lockup_transaction_id: _Optional[str] = ...,
        claim_transaction_id: _Optional[str] = ...,
        pair: _Optional[_Union[Pair, _Mapping]] = ...,
        chan_ids: _Optional[_Iterable[_Union[ChannelId, _Mapping]]] = ...,
        blinding_key: _Optional[str] = ...,
        created_at: _Optional[int] = ...,
        paid_at: _Optional[int] = ...,
        service_fee: _Optional[int] = ...,
        onchain_fee: _Optional[int] = ...,
        routing_fee_msat: _Optional[int] = ...,
        external_pay: bool = ...,
        tenant_id: _Optional[int] = ...,
    ) -> None: ...

class BlockHeights(_message.Message):
    __slots__ = ("btc", "liquid")
    BTC_FIELD_NUMBER: _ClassVar[int]
    LIQUID_FIELD_NUMBER: _ClassVar[int]
    btc: int
    liquid: int
    def __init__(
        self, btc: _Optional[int] = ..., liquid: _Optional[int] = ...
    ) -> None: ...

class GetInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetInfoResponse(_message.Message):
    __slots__ = (
        "version",
        "node",
        "network",
        "node_pubkey",
        "auto_swap_status",
        "block_heights",
        "refundable_swaps",
        "tenant",
        "claimable_swaps",
        "symbol",
        "lnd_pubkey",
        "block_height",
        "pending_swaps",
        "pending_reverse_swaps",
    )
    VERSION_FIELD_NUMBER: _ClassVar[int]
    NODE_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    NODE_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    AUTO_SWAP_STATUS_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HEIGHTS_FIELD_NUMBER: _ClassVar[int]
    REFUNDABLE_SWAPS_FIELD_NUMBER: _ClassVar[int]
    TENANT_FIELD_NUMBER: _ClassVar[int]
    CLAIMABLE_SWAPS_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    LND_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    PENDING_SWAPS_FIELD_NUMBER: _ClassVar[int]
    PENDING_REVERSE_SWAPS_FIELD_NUMBER: _ClassVar[int]
    version: str
    node: str
    network: str
    node_pubkey: str
    auto_swap_status: str
    block_heights: BlockHeights
    refundable_swaps: _containers.RepeatedScalarFieldContainer[str]
    tenant: Tenant
    claimable_swaps: _containers.RepeatedScalarFieldContainer[str]
    symbol: str
    lnd_pubkey: str
    block_height: int
    pending_swaps: _containers.RepeatedScalarFieldContainer[str]
    pending_reverse_swaps: _containers.RepeatedScalarFieldContainer[str]
    def __init__(
        self,
        version: _Optional[str] = ...,
        node: _Optional[str] = ...,
        network: _Optional[str] = ...,
        node_pubkey: _Optional[str] = ...,
        auto_swap_status: _Optional[str] = ...,
        block_heights: _Optional[_Union[BlockHeights, _Mapping]] = ...,
        refundable_swaps: _Optional[_Iterable[str]] = ...,
        tenant: _Optional[_Union[Tenant, _Mapping]] = ...,
        claimable_swaps: _Optional[_Iterable[str]] = ...,
        symbol: _Optional[str] = ...,
        lnd_pubkey: _Optional[str] = ...,
        block_height: _Optional[int] = ...,
        pending_swaps: _Optional[_Iterable[str]] = ...,
        pending_reverse_swaps: _Optional[_Iterable[str]] = ...,
    ) -> None: ...

class Limits(_message.Message):
    __slots__ = ("minimal", "maximal", "maximal_zero_conf_amount")
    MINIMAL_FIELD_NUMBER: _ClassVar[int]
    MAXIMAL_FIELD_NUMBER: _ClassVar[int]
    MAXIMAL_ZERO_CONF_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    minimal: int
    maximal: int
    maximal_zero_conf_amount: int
    def __init__(
        self,
        minimal: _Optional[int] = ...,
        maximal: _Optional[int] = ...,
        maximal_zero_conf_amount: _Optional[int] = ...,
    ) -> None: ...

class SwapFees(_message.Message):
    __slots__ = ("percentage", "miner_fees")
    PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    MINER_FEES_FIELD_NUMBER: _ClassVar[int]
    percentage: float
    miner_fees: int
    def __init__(
        self, percentage: _Optional[float] = ..., miner_fees: _Optional[int] = ...
    ) -> None: ...

class GetPairsResponse(_message.Message):
    __slots__ = ("submarine", "reverse", "chain")
    SUBMARINE_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    CHAIN_FIELD_NUMBER: _ClassVar[int]
    submarine: _containers.RepeatedCompositeFieldContainer[PairInfo]
    reverse: _containers.RepeatedCompositeFieldContainer[PairInfo]
    chain: _containers.RepeatedCompositeFieldContainer[PairInfo]
    def __init__(
        self,
        submarine: _Optional[_Iterable[_Union[PairInfo, _Mapping]]] = ...,
        reverse: _Optional[_Iterable[_Union[PairInfo, _Mapping]]] = ...,
        chain: _Optional[_Iterable[_Union[PairInfo, _Mapping]]] = ...,
    ) -> None: ...

class MinerFees(_message.Message):
    __slots__ = ("normal", "reverse")
    NORMAL_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    normal: int
    reverse: int
    def __init__(
        self, normal: _Optional[int] = ..., reverse: _Optional[int] = ...
    ) -> None: ...

class Fees(_message.Message):
    __slots__ = ("percentage", "miner")
    PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    MINER_FIELD_NUMBER: _ClassVar[int]
    percentage: float
    miner: MinerFees
    def __init__(
        self,
        percentage: _Optional[float] = ...,
        miner: _Optional[_Union[MinerFees, _Mapping]] = ...,
    ) -> None: ...

class GetServiceInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetServiceInfoResponse(_message.Message):
    __slots__ = ("fees", "limits")
    FEES_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    fees: Fees
    limits: Limits
    def __init__(
        self,
        fees: _Optional[_Union[Fees, _Mapping]] = ...,
        limits: _Optional[_Union[Limits, _Mapping]] = ...,
    ) -> None: ...

class ListSwapsRequest(_message.Message):
    __slots__ = ("to", "state", "include")
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_FIELD_NUMBER: _ClassVar[int]
    to: Currency
    state: SwapState
    include: IncludeSwaps
    def __init__(
        self,
        to: _Optional[_Union[Currency, str]] = ...,
        state: _Optional[_Union[SwapState, str]] = ...,
        include: _Optional[_Union[IncludeSwaps, str]] = ...,
        **kwargs
    ) -> None: ...

class ListSwapsResponse(_message.Message):
    __slots__ = ("swaps", "channel_creations", "reverse_swaps", "chain_swaps")
    SWAPS_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_CREATIONS_FIELD_NUMBER: _ClassVar[int]
    REVERSE_SWAPS_FIELD_NUMBER: _ClassVar[int]
    CHAIN_SWAPS_FIELD_NUMBER: _ClassVar[int]
    swaps: _containers.RepeatedCompositeFieldContainer[SwapInfo]
    channel_creations: _containers.RepeatedCompositeFieldContainer[
        CombinedChannelSwapInfo
    ]
    reverse_swaps: _containers.RepeatedCompositeFieldContainer[ReverseSwapInfo]
    chain_swaps: _containers.RepeatedCompositeFieldContainer[ChainSwapInfo]
    def __init__(
        self,
        swaps: _Optional[_Iterable[_Union[SwapInfo, _Mapping]]] = ...,
        channel_creations: _Optional[
            _Iterable[_Union[CombinedChannelSwapInfo, _Mapping]]
        ] = ...,
        reverse_swaps: _Optional[_Iterable[_Union[ReverseSwapInfo, _Mapping]]] = ...,
        chain_swaps: _Optional[_Iterable[_Union[ChainSwapInfo, _Mapping]]] = ...,
    ) -> None: ...

class GetStatsRequest(_message.Message):
    __slots__ = ("include",)
    INCLUDE_FIELD_NUMBER: _ClassVar[int]
    include: IncludeSwaps
    def __init__(self, include: _Optional[_Union[IncludeSwaps, str]] = ...) -> None: ...

class GetStatsResponse(_message.Message):
    __slots__ = ("stats",)
    STATS_FIELD_NUMBER: _ClassVar[int]
    stats: SwapStats
    def __init__(self, stats: _Optional[_Union[SwapStats, _Mapping]] = ...) -> None: ...

class RefundSwapRequest(_message.Message):
    __slots__ = ("id", "address", "wallet_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    address: str
    wallet_id: int
    def __init__(
        self,
        id: _Optional[str] = ...,
        address: _Optional[str] = ...,
        wallet_id: _Optional[int] = ...,
    ) -> None: ...

class ClaimSwapsRequest(_message.Message):
    __slots__ = ("swap_ids", "address", "wallet_id")
    SWAP_IDS_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    swap_ids: _containers.RepeatedScalarFieldContainer[str]
    address: str
    wallet_id: int
    def __init__(
        self,
        swap_ids: _Optional[_Iterable[str]] = ...,
        address: _Optional[str] = ...,
        wallet_id: _Optional[int] = ...,
    ) -> None: ...

class ClaimSwapsResponse(_message.Message):
    __slots__ = ("transaction_id",)
    TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    transaction_id: str
    def __init__(self, transaction_id: _Optional[str] = ...) -> None: ...

class GetSwapInfoRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetSwapInfoResponse(_message.Message):
    __slots__ = ("swap", "channel_creation", "reverse_swap", "chain_swap")
    SWAP_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_CREATION_FIELD_NUMBER: _ClassVar[int]
    REVERSE_SWAP_FIELD_NUMBER: _ClassVar[int]
    CHAIN_SWAP_FIELD_NUMBER: _ClassVar[int]
    swap: SwapInfo
    channel_creation: ChannelCreationInfo
    reverse_swap: ReverseSwapInfo
    chain_swap: ChainSwapInfo
    def __init__(
        self,
        swap: _Optional[_Union[SwapInfo, _Mapping]] = ...,
        channel_creation: _Optional[_Union[ChannelCreationInfo, _Mapping]] = ...,
        reverse_swap: _Optional[_Union[ReverseSwapInfo, _Mapping]] = ...,
        chain_swap: _Optional[_Union[ChainSwapInfo, _Mapping]] = ...,
    ) -> None: ...

class DepositRequest(_message.Message):
    __slots__ = ("inbound_liquidity",)
    INBOUND_LIQUIDITY_FIELD_NUMBER: _ClassVar[int]
    inbound_liquidity: int
    def __init__(self, inbound_liquidity: _Optional[int] = ...) -> None: ...

class DepositResponse(_message.Message):
    __slots__ = ("id", "address", "timeout_block_height")
    ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    id: str
    address: str
    timeout_block_height: int
    def __init__(
        self,
        id: _Optional[str] = ...,
        address: _Optional[str] = ...,
        timeout_block_height: _Optional[int] = ...,
    ) -> None: ...

class CreateSwapRequest(_message.Message):
    __slots__ = (
        "amount",
        "pair",
        "send_from_internal",
        "refund_address",
        "wallet_id",
        "invoice",
        "zero_conf",
    )
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    SEND_FROM_INTERNAL_FIELD_NUMBER: _ClassVar[int]
    REFUND_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    INVOICE_FIELD_NUMBER: _ClassVar[int]
    ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    amount: int
    pair: Pair
    send_from_internal: bool
    refund_address: str
    wallet_id: int
    invoice: str
    zero_conf: bool
    def __init__(
        self,
        amount: _Optional[int] = ...,
        pair: _Optional[_Union[Pair, _Mapping]] = ...,
        send_from_internal: bool = ...,
        refund_address: _Optional[str] = ...,
        wallet_id: _Optional[int] = ...,
        invoice: _Optional[str] = ...,
        zero_conf: bool = ...,
    ) -> None: ...

class CreateSwapResponse(_message.Message):
    __slots__ = (
        "id",
        "address",
        "expected_amount",
        "bip21",
        "tx_id",
        "timeout_block_height",
        "timeout_hours",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    BIP21_FIELD_NUMBER: _ClassVar[int]
    TX_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_HOURS_FIELD_NUMBER: _ClassVar[int]
    id: str
    address: str
    expected_amount: int
    bip21: str
    tx_id: str
    timeout_block_height: int
    timeout_hours: float
    def __init__(
        self,
        id: _Optional[str] = ...,
        address: _Optional[str] = ...,
        expected_amount: _Optional[int] = ...,
        bip21: _Optional[str] = ...,
        tx_id: _Optional[str] = ...,
        timeout_block_height: _Optional[int] = ...,
        timeout_hours: _Optional[float] = ...,
    ) -> None: ...

class CreateChannelRequest(_message.Message):
    __slots__ = ("amount", "inbound_liquidity", "private")
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    INBOUND_LIQUIDITY_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    amount: int
    inbound_liquidity: int
    private: bool
    def __init__(
        self,
        amount: _Optional[int] = ...,
        inbound_liquidity: _Optional[int] = ...,
        private: bool = ...,
    ) -> None: ...

class CreateReverseSwapRequest(_message.Message):
    __slots__ = (
        "amount",
        "address",
        "accept_zero_conf",
        "pair",
        "chan_ids",
        "wallet_id",
        "return_immediately",
        "external_pay",
        "description",
    )
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    ACCEPT_ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    CHAN_IDS_FIELD_NUMBER: _ClassVar[int]
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    RETURN_IMMEDIATELY_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_PAY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    amount: int
    address: str
    accept_zero_conf: bool
    pair: Pair
    chan_ids: _containers.RepeatedScalarFieldContainer[str]
    wallet_id: int
    return_immediately: bool
    external_pay: bool
    description: str
    def __init__(
        self,
        amount: _Optional[int] = ...,
        address: _Optional[str] = ...,
        accept_zero_conf: bool = ...,
        pair: _Optional[_Union[Pair, _Mapping]] = ...,
        chan_ids: _Optional[_Iterable[str]] = ...,
        wallet_id: _Optional[int] = ...,
        return_immediately: bool = ...,
        external_pay: bool = ...,
        description: _Optional[str] = ...,
    ) -> None: ...

class CreateReverseSwapResponse(_message.Message):
    __slots__ = (
        "id",
        "lockup_address",
        "routing_fee_milli_sat",
        "claim_transaction_id",
        "invoice",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    LOCKUP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    ROUTING_FEE_MILLI_SAT_FIELD_NUMBER: _ClassVar[int]
    CLAIM_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    INVOICE_FIELD_NUMBER: _ClassVar[int]
    id: str
    lockup_address: str
    routing_fee_milli_sat: int
    claim_transaction_id: str
    invoice: str
    def __init__(
        self,
        id: _Optional[str] = ...,
        lockup_address: _Optional[str] = ...,
        routing_fee_milli_sat: _Optional[int] = ...,
        claim_transaction_id: _Optional[str] = ...,
        invoice: _Optional[str] = ...,
    ) -> None: ...

class CreateChainSwapRequest(_message.Message):
    __slots__ = (
        "amount",
        "pair",
        "to_address",
        "refund_address",
        "from_wallet_id",
        "to_wallet_id",
        "accept_zero_conf",
        "external_pay",
        "lockup_zero_conf",
    )
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    TO_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    REFUND_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    FROM_WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    TO_WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    ACCEPT_ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_PAY_FIELD_NUMBER: _ClassVar[int]
    LOCKUP_ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    amount: int
    pair: Pair
    to_address: str
    refund_address: str
    from_wallet_id: int
    to_wallet_id: int
    accept_zero_conf: bool
    external_pay: bool
    lockup_zero_conf: bool
    def __init__(
        self,
        amount: _Optional[int] = ...,
        pair: _Optional[_Union[Pair, _Mapping]] = ...,
        to_address: _Optional[str] = ...,
        refund_address: _Optional[str] = ...,
        from_wallet_id: _Optional[int] = ...,
        to_wallet_id: _Optional[int] = ...,
        accept_zero_conf: bool = ...,
        external_pay: bool = ...,
        lockup_zero_conf: bool = ...,
    ) -> None: ...

class ChainSwapInfo(_message.Message):
    __slots__ = (
        "id",
        "pair",
        "state",
        "error",
        "status",
        "preimage",
        "is_auto",
        "service_fee",
        "service_fee_percent",
        "onchain_fee",
        "created_at",
        "tenant_id",
        "from_data",
        "to_data",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    IS_AUTO_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FEE_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FEE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    ONCHAIN_FEE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    FROM_DATA_FIELD_NUMBER: _ClassVar[int]
    TO_DATA_FIELD_NUMBER: _ClassVar[int]
    id: str
    pair: Pair
    state: SwapState
    error: str
    status: str
    preimage: str
    is_auto: bool
    service_fee: int
    service_fee_percent: float
    onchain_fee: int
    created_at: int
    tenant_id: int
    from_data: ChainSwapData
    to_data: ChainSwapData
    def __init__(
        self,
        id: _Optional[str] = ...,
        pair: _Optional[_Union[Pair, _Mapping]] = ...,
        state: _Optional[_Union[SwapState, str]] = ...,
        error: _Optional[str] = ...,
        status: _Optional[str] = ...,
        preimage: _Optional[str] = ...,
        is_auto: bool = ...,
        service_fee: _Optional[int] = ...,
        service_fee_percent: _Optional[float] = ...,
        onchain_fee: _Optional[int] = ...,
        created_at: _Optional[int] = ...,
        tenant_id: _Optional[int] = ...,
        from_data: _Optional[_Union[ChainSwapData, _Mapping]] = ...,
        to_data: _Optional[_Union[ChainSwapData, _Mapping]] = ...,
    ) -> None: ...

class ChainSwapData(_message.Message):
    __slots__ = (
        "id",
        "currency",
        "private_key",
        "their_public_key",
        "amount",
        "timeout_block_height",
        "lockup_transaction_id",
        "transaction_id",
        "wallet_id",
        "address",
        "blinding_key",
        "lockup_address",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_KEY_FIELD_NUMBER: _ClassVar[int]
    THEIR_PUBLIC_KEY_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    LOCKUP_TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSACTION_ID_FIELD_NUMBER: _ClassVar[int]
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    BLINDING_KEY_FIELD_NUMBER: _ClassVar[int]
    LOCKUP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    id: str
    currency: Currency
    private_key: str
    their_public_key: str
    amount: int
    timeout_block_height: int
    lockup_transaction_id: str
    transaction_id: str
    wallet_id: int
    address: str
    blinding_key: str
    lockup_address: str
    def __init__(
        self,
        id: _Optional[str] = ...,
        currency: _Optional[_Union[Currency, str]] = ...,
        private_key: _Optional[str] = ...,
        their_public_key: _Optional[str] = ...,
        amount: _Optional[int] = ...,
        timeout_block_height: _Optional[int] = ...,
        lockup_transaction_id: _Optional[str] = ...,
        transaction_id: _Optional[str] = ...,
        wallet_id: _Optional[int] = ...,
        address: _Optional[str] = ...,
        blinding_key: _Optional[str] = ...,
        lockup_address: _Optional[str] = ...,
    ) -> None: ...

class ChannelId(_message.Message):
    __slots__ = ("cln", "lnd")
    CLN_FIELD_NUMBER: _ClassVar[int]
    LND_FIELD_NUMBER: _ClassVar[int]
    cln: str
    lnd: int
    def __init__(
        self, cln: _Optional[str] = ..., lnd: _Optional[int] = ...
    ) -> None: ...

class LightningChannel(_message.Message):
    __slots__ = ("id", "capacity", "outbound_sat", "inbound_sat", "peer_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    OUTBOUND_SAT_FIELD_NUMBER: _ClassVar[int]
    INBOUND_SAT_FIELD_NUMBER: _ClassVar[int]
    PEER_ID_FIELD_NUMBER: _ClassVar[int]
    id: ChannelId
    capacity: int
    outbound_sat: int
    inbound_sat: int
    peer_id: str
    def __init__(
        self,
        id: _Optional[_Union[ChannelId, _Mapping]] = ...,
        capacity: _Optional[int] = ...,
        outbound_sat: _Optional[int] = ...,
        inbound_sat: _Optional[int] = ...,
        peer_id: _Optional[str] = ...,
    ) -> None: ...

class SwapStats(_message.Message):
    __slots__ = (
        "total_fees",
        "total_amount",
        "avg_fees",
        "avg_amount",
        "count",
        "success_count",
    )
    TOTAL_FEES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    AVG_FEES_FIELD_NUMBER: _ClassVar[int]
    AVG_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_COUNT_FIELD_NUMBER: _ClassVar[int]
    total_fees: int
    total_amount: int
    avg_fees: int
    avg_amount: int
    count: int
    success_count: int
    def __init__(
        self,
        total_fees: _Optional[int] = ...,
        total_amount: _Optional[int] = ...,
        avg_fees: _Optional[int] = ...,
        avg_amount: _Optional[int] = ...,
        count: _Optional[int] = ...,
        success_count: _Optional[int] = ...,
    ) -> None: ...

class Budget(_message.Message):
    __slots__ = ("total", "remaining", "start_date", "end_date")
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    REMAINING_FIELD_NUMBER: _ClassVar[int]
    START_DATE_FIELD_NUMBER: _ClassVar[int]
    END_DATE_FIELD_NUMBER: _ClassVar[int]
    total: int
    remaining: int
    start_date: int
    end_date: int
    def __init__(
        self,
        total: _Optional[int] = ...,
        remaining: _Optional[int] = ...,
        start_date: _Optional[int] = ...,
        end_date: _Optional[int] = ...,
    ) -> None: ...

class WalletCredentials(_message.Message):
    __slots__ = ("mnemonic", "xpub", "core_descriptor", "subaccount")
    MNEMONIC_FIELD_NUMBER: _ClassVar[int]
    XPUB_FIELD_NUMBER: _ClassVar[int]
    CORE_DESCRIPTOR_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_FIELD_NUMBER: _ClassVar[int]
    mnemonic: str
    xpub: str
    core_descriptor: str
    subaccount: int
    def __init__(
        self,
        mnemonic: _Optional[str] = ...,
        xpub: _Optional[str] = ...,
        core_descriptor: _Optional[str] = ...,
        subaccount: _Optional[int] = ...,
    ) -> None: ...

class WalletParams(_message.Message):
    __slots__ = ("name", "currency", "password")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    name: str
    currency: Currency
    password: str
    def __init__(
        self,
        name: _Optional[str] = ...,
        currency: _Optional[_Union[Currency, str]] = ...,
        password: _Optional[str] = ...,
    ) -> None: ...

class ImportWalletRequest(_message.Message):
    __slots__ = ("credentials", "params")
    CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    credentials: WalletCredentials
    params: WalletParams
    def __init__(
        self,
        credentials: _Optional[_Union[WalletCredentials, _Mapping]] = ...,
        params: _Optional[_Union[WalletParams, _Mapping]] = ...,
    ) -> None: ...

class CreateWalletRequest(_message.Message):
    __slots__ = ("params",)
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    params: WalletParams
    def __init__(
        self, params: _Optional[_Union[WalletParams, _Mapping]] = ...
    ) -> None: ...

class CreateWalletResponse(_message.Message):
    __slots__ = ("mnemonic", "wallet")
    MNEMONIC_FIELD_NUMBER: _ClassVar[int]
    WALLET_FIELD_NUMBER: _ClassVar[int]
    mnemonic: str
    wallet: Wallet
    def __init__(
        self,
        mnemonic: _Optional[str] = ...,
        wallet: _Optional[_Union[Wallet, _Mapping]] = ...,
    ) -> None: ...

class SetSubaccountRequest(_message.Message):
    __slots__ = ("wallet_id", "subaccount")
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_FIELD_NUMBER: _ClassVar[int]
    wallet_id: int
    subaccount: int
    def __init__(
        self, wallet_id: _Optional[int] = ..., subaccount: _Optional[int] = ...
    ) -> None: ...

class GetSubaccountsRequest(_message.Message):
    __slots__ = ("wallet_id",)
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    wallet_id: int
    def __init__(self, wallet_id: _Optional[int] = ...) -> None: ...

class GetSubaccountsResponse(_message.Message):
    __slots__ = ("current", "subaccounts")
    CURRENT_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    current: int
    subaccounts: _containers.RepeatedCompositeFieldContainer[Subaccount]
    def __init__(
        self,
        current: _Optional[int] = ...,
        subaccounts: _Optional[_Iterable[_Union[Subaccount, _Mapping]]] = ...,
    ) -> None: ...

class ImportWalletResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetWalletsRequest(_message.Message):
    __slots__ = ("currency", "include_readonly")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_READONLY_FIELD_NUMBER: _ClassVar[int]
    currency: Currency
    include_readonly: bool
    def __init__(
        self,
        currency: _Optional[_Union[Currency, str]] = ...,
        include_readonly: bool = ...,
    ) -> None: ...

class GetWalletRequest(_message.Message):
    __slots__ = ("name", "id")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    name: str
    id: int
    def __init__(
        self, name: _Optional[str] = ..., id: _Optional[int] = ...
    ) -> None: ...

class GetWalletCredentialsRequest(_message.Message):
    __slots__ = ("id", "password")
    ID_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    id: int
    password: str
    def __init__(
        self, id: _Optional[int] = ..., password: _Optional[str] = ...
    ) -> None: ...

class RemoveWalletRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    def __init__(self, id: _Optional[int] = ...) -> None: ...

class Wallet(_message.Message):
    __slots__ = ("id", "name", "currency", "readonly", "balance", "tenant_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    READONLY_FIELD_NUMBER: _ClassVar[int]
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    TENANT_ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    currency: Currency
    readonly: bool
    balance: Balance
    tenant_id: int
    def __init__(
        self,
        id: _Optional[int] = ...,
        name: _Optional[str] = ...,
        currency: _Optional[_Union[Currency, str]] = ...,
        readonly: bool = ...,
        balance: _Optional[_Union[Balance, _Mapping]] = ...,
        tenant_id: _Optional[int] = ...,
    ) -> None: ...

class Wallets(_message.Message):
    __slots__ = ("wallets",)
    WALLETS_FIELD_NUMBER: _ClassVar[int]
    wallets: _containers.RepeatedCompositeFieldContainer[Wallet]
    def __init__(
        self, wallets: _Optional[_Iterable[_Union[Wallet, _Mapping]]] = ...
    ) -> None: ...

class Balance(_message.Message):
    __slots__ = ("total", "confirmed", "unconfirmed")
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    CONFIRMED_FIELD_NUMBER: _ClassVar[int]
    UNCONFIRMED_FIELD_NUMBER: _ClassVar[int]
    total: int
    confirmed: int
    unconfirmed: int
    def __init__(
        self,
        total: _Optional[int] = ...,
        confirmed: _Optional[int] = ...,
        unconfirmed: _Optional[int] = ...,
    ) -> None: ...

class Subaccount(_message.Message):
    __slots__ = ("balance", "pointer", "type")
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    POINTER_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    balance: Balance
    pointer: int
    type: str
    def __init__(
        self,
        balance: _Optional[_Union[Balance, _Mapping]] = ...,
        pointer: _Optional[int] = ...,
        type: _Optional[str] = ...,
    ) -> None: ...

class RemoveWalletResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UnlockRequest(_message.Message):
    __slots__ = ("password",)
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    password: str
    def __init__(self, password: _Optional[str] = ...) -> None: ...

class VerifyWalletPasswordRequest(_message.Message):
    __slots__ = ("password",)
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    password: str
    def __init__(self, password: _Optional[str] = ...) -> None: ...

class VerifyWalletPasswordResponse(_message.Message):
    __slots__ = ("correct",)
    CORRECT_FIELD_NUMBER: _ClassVar[int]
    correct: bool
    def __init__(self, correct: bool = ...) -> None: ...

class ChangeWalletPasswordRequest(_message.Message):
    __slots__ = ("old", "new")
    OLD_FIELD_NUMBER: _ClassVar[int]
    NEW_FIELD_NUMBER: _ClassVar[int]
    old: str
    new: str
    def __init__(
        self, old: _Optional[str] = ..., new: _Optional[str] = ...
    ) -> None: ...
