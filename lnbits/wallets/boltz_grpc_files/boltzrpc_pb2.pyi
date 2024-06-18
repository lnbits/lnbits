from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

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
PENDING: SwapState
SUCCESSFUL: SwapState
ERROR: SwapState
SERVER_ERROR: SwapState
REFUNDED: SwapState
ABANDONED: SwapState
BTC: Currency
LBTC: Currency

class Pair(_message.Message):
    __slots__ = ("to",)
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    to: Currency
    def __init__(self, to: _Optional[_Union[Currency, str]] = ..., **kwargs) -> None: ...

class SwapInfo(_message.Message):
    __slots__ = ("id", "pair", "state", "error", "status", "private_key", "preimage", "redeem_script", "invoice", "lockup_address", "expected_amount", "timeout_block_height", "lockup_transaction_id", "refund_transaction_id", "refund_address", "chan_ids", "blinding_key", "created_at", "service_fee", "onchain_fee", "wallet")
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
    WALLET_FIELD_NUMBER: _ClassVar[int]
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
    wallet: str
    def __init__(self, id: _Optional[str] = ..., pair: _Optional[_Union[Pair, _Mapping]] = ..., state: _Optional[_Union[SwapState, str]] = ..., error: _Optional[str] = ..., status: _Optional[str] = ..., private_key: _Optional[str] = ..., preimage: _Optional[str] = ..., redeem_script: _Optional[str] = ..., invoice: _Optional[str] = ..., lockup_address: _Optional[str] = ..., expected_amount: _Optional[int] = ..., timeout_block_height: _Optional[int] = ..., lockup_transaction_id: _Optional[str] = ..., refund_transaction_id: _Optional[str] = ..., refund_address: _Optional[str] = ..., chan_ids: _Optional[_Iterable[_Union[ChannelId, _Mapping]]] = ..., blinding_key: _Optional[str] = ..., created_at: _Optional[int] = ..., service_fee: _Optional[int] = ..., onchain_fee: _Optional[int] = ..., wallet: _Optional[str] = ...) -> None: ...

class ChannelCreationInfo(_message.Message):
    __slots__ = ("swap_id", "status", "inbound_liquidity", "private", "funding_transaction_id", "funding_transaction_vout")
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
    def __init__(self, swap_id: _Optional[str] = ..., status: _Optional[str] = ..., inbound_liquidity: _Optional[int] = ..., private: bool = ..., funding_transaction_id: _Optional[str] = ..., funding_transaction_vout: _Optional[int] = ...) -> None: ...

class CombinedChannelSwapInfo(_message.Message):
    __slots__ = ("swap", "channel_creation")
    SWAP_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_CREATION_FIELD_NUMBER: _ClassVar[int]
    swap: SwapInfo
    channel_creation: ChannelCreationInfo
    def __init__(self, swap: _Optional[_Union[SwapInfo, _Mapping]] = ..., channel_creation: _Optional[_Union[ChannelCreationInfo, _Mapping]] = ...) -> None: ...

class ReverseSwapInfo(_message.Message):
    __slots__ = ("id", "state", "error", "status", "private_key", "preimage", "redeem_script", "invoice", "claim_address", "onchain_amount", "timeout_block_height", "lockup_transaction_id", "claim_transaction_id", "pair", "chan_ids", "blinding_key", "created_at", "service_fee", "onchain_fee", "routing_fee_msat", "external_pay")
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
    SERVICE_FEE_FIELD_NUMBER: _ClassVar[int]
    ONCHAIN_FEE_FIELD_NUMBER: _ClassVar[int]
    ROUTING_FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_PAY_FIELD_NUMBER: _ClassVar[int]
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
    service_fee: int
    onchain_fee: int
    routing_fee_msat: int
    external_pay: bool
    def __init__(self, id: _Optional[str] = ..., state: _Optional[_Union[SwapState, str]] = ..., error: _Optional[str] = ..., status: _Optional[str] = ..., private_key: _Optional[str] = ..., preimage: _Optional[str] = ..., redeem_script: _Optional[str] = ..., invoice: _Optional[str] = ..., claim_address: _Optional[str] = ..., onchain_amount: _Optional[int] = ..., timeout_block_height: _Optional[int] = ..., lockup_transaction_id: _Optional[str] = ..., claim_transaction_id: _Optional[str] = ..., pair: _Optional[_Union[Pair, _Mapping]] = ..., chan_ids: _Optional[_Iterable[_Union[ChannelId, _Mapping]]] = ..., blinding_key: _Optional[str] = ..., created_at: _Optional[int] = ..., service_fee: _Optional[int] = ..., onchain_fee: _Optional[int] = ..., routing_fee_msat: _Optional[int] = ..., external_pay: bool = ...) -> None: ...

class BlockHeights(_message.Message):
    __slots__ = ("btc", "liquid")
    BTC_FIELD_NUMBER: _ClassVar[int]
    LIQUID_FIELD_NUMBER: _ClassVar[int]
    btc: int
    liquid: int
    def __init__(self, btc: _Optional[int] = ..., liquid: _Optional[int] = ...) -> None: ...

class GetInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetInfoResponse(_message.Message):
    __slots__ = ("version", "node", "network", "node_pubkey", "auto_swap_status", "block_heights", "symbol", "lnd_pubkey", "block_height", "pending_swaps", "pending_reverse_swaps")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    NODE_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    NODE_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    AUTO_SWAP_STATUS_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HEIGHTS_FIELD_NUMBER: _ClassVar[int]
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
    symbol: str
    lnd_pubkey: str
    block_height: int
    pending_swaps: _containers.RepeatedScalarFieldContainer[str]
    pending_reverse_swaps: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, version: _Optional[str] = ..., node: _Optional[str] = ..., network: _Optional[str] = ..., node_pubkey: _Optional[str] = ..., auto_swap_status: _Optional[str] = ..., block_heights: _Optional[_Union[BlockHeights, _Mapping]] = ..., symbol: _Optional[str] = ..., lnd_pubkey: _Optional[str] = ..., block_height: _Optional[int] = ..., pending_swaps: _Optional[_Iterable[str]] = ..., pending_reverse_swaps: _Optional[_Iterable[str]] = ...) -> None: ...

class Limits(_message.Message):
    __slots__ = ("minimal", "maximal", "maximal_zero_conf_amount")
    MINIMAL_FIELD_NUMBER: _ClassVar[int]
    MAXIMAL_FIELD_NUMBER: _ClassVar[int]
    MAXIMAL_ZERO_CONF_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    minimal: int
    maximal: int
    maximal_zero_conf_amount: int
    def __init__(self, minimal: _Optional[int] = ..., maximal: _Optional[int] = ..., maximal_zero_conf_amount: _Optional[int] = ...) -> None: ...

class SubmarinePair(_message.Message):
    __slots__ = ("pair", "hash", "rate", "limits", "fees")
    class Fees(_message.Message):
        __slots__ = ("percentage", "miner_fees")
        PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
        MINER_FEES_FIELD_NUMBER: _ClassVar[int]
        percentage: float
        miner_fees: int
        def __init__(self, percentage: _Optional[float] = ..., miner_fees: _Optional[int] = ...) -> None: ...
    PAIR_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    RATE_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    FEES_FIELD_NUMBER: _ClassVar[int]
    pair: Pair
    hash: str
    rate: float
    limits: Limits
    fees: SubmarinePair.Fees
    def __init__(self, pair: _Optional[_Union[Pair, _Mapping]] = ..., hash: _Optional[str] = ..., rate: _Optional[float] = ..., limits: _Optional[_Union[Limits, _Mapping]] = ..., fees: _Optional[_Union[SubmarinePair.Fees, _Mapping]] = ...) -> None: ...

class ReversePair(_message.Message):
    __slots__ = ("pair", "hash", "rate", "limits", "fees")
    class Fees(_message.Message):
        __slots__ = ("percentage", "miner_fees")
        class MinerFees(_message.Message):
            __slots__ = ("lockup", "claim")
            LOCKUP_FIELD_NUMBER: _ClassVar[int]
            CLAIM_FIELD_NUMBER: _ClassVar[int]
            lockup: int
            claim: int
            def __init__(self, lockup: _Optional[int] = ..., claim: _Optional[int] = ...) -> None: ...
        PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
        MINER_FEES_FIELD_NUMBER: _ClassVar[int]
        percentage: float
        miner_fees: ReversePair.Fees.MinerFees
        def __init__(self, percentage: _Optional[float] = ..., miner_fees: _Optional[_Union[ReversePair.Fees.MinerFees, _Mapping]] = ...) -> None: ...
    PAIR_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    RATE_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    FEES_FIELD_NUMBER: _ClassVar[int]
    pair: Pair
    hash: str
    rate: float
    limits: Limits
    fees: ReversePair.Fees
    def __init__(self, pair: _Optional[_Union[Pair, _Mapping]] = ..., hash: _Optional[str] = ..., rate: _Optional[float] = ..., limits: _Optional[_Union[Limits, _Mapping]] = ..., fees: _Optional[_Union[ReversePair.Fees, _Mapping]] = ...) -> None: ...

class GetPairsResponse(_message.Message):
    __slots__ = ("submarine", "reverse")
    SUBMARINE_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    submarine: _containers.RepeatedCompositeFieldContainer[SubmarinePair]
    reverse: _containers.RepeatedCompositeFieldContainer[ReversePair]
    def __init__(self, submarine: _Optional[_Iterable[_Union[SubmarinePair, _Mapping]]] = ..., reverse: _Optional[_Iterable[_Union[ReversePair, _Mapping]]] = ...) -> None: ...

class MinerFees(_message.Message):
    __slots__ = ("normal", "reverse")
    NORMAL_FIELD_NUMBER: _ClassVar[int]
    REVERSE_FIELD_NUMBER: _ClassVar[int]
    normal: int
    reverse: int
    def __init__(self, normal: _Optional[int] = ..., reverse: _Optional[int] = ...) -> None: ...

class Fees(_message.Message):
    __slots__ = ("percentage", "miner")
    PERCENTAGE_FIELD_NUMBER: _ClassVar[int]
    MINER_FIELD_NUMBER: _ClassVar[int]
    percentage: float
    miner: MinerFees
    def __init__(self, percentage: _Optional[float] = ..., miner: _Optional[_Union[MinerFees, _Mapping]] = ...) -> None: ...

class GetServiceInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetServiceInfoResponse(_message.Message):
    __slots__ = ("fees", "limits")
    FEES_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    fees: Fees
    limits: Limits
    def __init__(self, fees: _Optional[_Union[Fees, _Mapping]] = ..., limits: _Optional[_Union[Limits, _Mapping]] = ...) -> None: ...

class ListSwapsRequest(_message.Message):
    __slots__ = ("to", "is_auto", "state")
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    IS_AUTO_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    to: Currency
    is_auto: bool
    state: SwapState
    def __init__(self, to: _Optional[_Union[Currency, str]] = ..., is_auto: bool = ..., state: _Optional[_Union[SwapState, str]] = ..., **kwargs) -> None: ...

class ListSwapsResponse(_message.Message):
    __slots__ = ("swaps", "channel_creations", "reverse_swaps")
    SWAPS_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_CREATIONS_FIELD_NUMBER: _ClassVar[int]
    REVERSE_SWAPS_FIELD_NUMBER: _ClassVar[int]
    swaps: _containers.RepeatedCompositeFieldContainer[SwapInfo]
    channel_creations: _containers.RepeatedCompositeFieldContainer[CombinedChannelSwapInfo]
    reverse_swaps: _containers.RepeatedCompositeFieldContainer[ReverseSwapInfo]
    def __init__(self, swaps: _Optional[_Iterable[_Union[SwapInfo, _Mapping]]] = ..., channel_creations: _Optional[_Iterable[_Union[CombinedChannelSwapInfo, _Mapping]]] = ..., reverse_swaps: _Optional[_Iterable[_Union[ReverseSwapInfo, _Mapping]]] = ...) -> None: ...

class RefundSwapRequest(_message.Message):
    __slots__ = ("id", "address")
    ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    id: str
    address: str
    def __init__(self, id: _Optional[str] = ..., address: _Optional[str] = ...) -> None: ...

class GetSwapInfoRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetSwapInfoResponse(_message.Message):
    __slots__ = ("swap", "channel_creation", "reverse_swap")
    SWAP_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_CREATION_FIELD_NUMBER: _ClassVar[int]
    REVERSE_SWAP_FIELD_NUMBER: _ClassVar[int]
    swap: SwapInfo
    channel_creation: ChannelCreationInfo
    reverse_swap: ReverseSwapInfo
    def __init__(self, swap: _Optional[_Union[SwapInfo, _Mapping]] = ..., channel_creation: _Optional[_Union[ChannelCreationInfo, _Mapping]] = ..., reverse_swap: _Optional[_Union[ReverseSwapInfo, _Mapping]] = ...) -> None: ...

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
    def __init__(self, id: _Optional[str] = ..., address: _Optional[str] = ..., timeout_block_height: _Optional[int] = ...) -> None: ...

class CreateSwapRequest(_message.Message):
    __slots__ = ("amount", "pair", "send_from_internal", "refund_address", "wallet", "invoice")
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    SEND_FROM_INTERNAL_FIELD_NUMBER: _ClassVar[int]
    REFUND_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WALLET_FIELD_NUMBER: _ClassVar[int]
    INVOICE_FIELD_NUMBER: _ClassVar[int]
    amount: int
    pair: Pair
    send_from_internal: bool
    refund_address: str
    wallet: str
    invoice: str
    def __init__(self, amount: _Optional[int] = ..., pair: _Optional[_Union[Pair, _Mapping]] = ..., send_from_internal: bool = ..., refund_address: _Optional[str] = ..., wallet: _Optional[str] = ..., invoice: _Optional[str] = ...) -> None: ...

class CreateSwapResponse(_message.Message):
    __slots__ = ("id", "address", "expected_amount", "bip21", "tx_id", "timeout_block_height", "timeout_hours")
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
    def __init__(self, id: _Optional[str] = ..., address: _Optional[str] = ..., expected_amount: _Optional[int] = ..., bip21: _Optional[str] = ..., tx_id: _Optional[str] = ..., timeout_block_height: _Optional[int] = ..., timeout_hours: _Optional[float] = ...) -> None: ...

class CreateChannelRequest(_message.Message):
    __slots__ = ("amount", "inbound_liquidity", "private")
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    INBOUND_LIQUIDITY_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    amount: int
    inbound_liquidity: int
    private: bool
    def __init__(self, amount: _Optional[int] = ..., inbound_liquidity: _Optional[int] = ..., private: bool = ...) -> None: ...

class CreateReverseSwapRequest(_message.Message):
    __slots__ = ("amount", "address", "accept_zero_conf", "pair", "chan_ids", "wallet", "return_immediately", "external_pay")
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    ACCEPT_ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    PAIR_FIELD_NUMBER: _ClassVar[int]
    CHAN_IDS_FIELD_NUMBER: _ClassVar[int]
    WALLET_FIELD_NUMBER: _ClassVar[int]
    RETURN_IMMEDIATELY_FIELD_NUMBER: _ClassVar[int]
    EXTERNAL_PAY_FIELD_NUMBER: _ClassVar[int]
    amount: int
    address: str
    accept_zero_conf: bool
    pair: Pair
    chan_ids: _containers.RepeatedScalarFieldContainer[str]
    wallet: str
    return_immediately: bool
    external_pay: bool
    def __init__(self, amount: _Optional[int] = ..., address: _Optional[str] = ..., accept_zero_conf: bool = ..., pair: _Optional[_Union[Pair, _Mapping]] = ..., chan_ids: _Optional[_Iterable[str]] = ..., wallet: _Optional[str] = ..., return_immediately: bool = ..., external_pay: bool = ...) -> None: ...

class CreateReverseSwapResponse(_message.Message):
    __slots__ = ("id", "lockup_address", "routing_fee_milli_sat", "claim_transaction_id", "invoice")
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
    def __init__(self, id: _Optional[str] = ..., lockup_address: _Optional[str] = ..., routing_fee_milli_sat: _Optional[int] = ..., claim_transaction_id: _Optional[str] = ..., invoice: _Optional[str] = ...) -> None: ...

class ChannelId(_message.Message):
    __slots__ = ("cln", "lnd")
    CLN_FIELD_NUMBER: _ClassVar[int]
    LND_FIELD_NUMBER: _ClassVar[int]
    cln: str
    lnd: int
    def __init__(self, cln: _Optional[str] = ..., lnd: _Optional[int] = ...) -> None: ...

class LightningChannel(_message.Message):
    __slots__ = ("id", "capacity", "local_sat", "remote_sat", "peer_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    LOCAL_SAT_FIELD_NUMBER: _ClassVar[int]
    REMOTE_SAT_FIELD_NUMBER: _ClassVar[int]
    PEER_ID_FIELD_NUMBER: _ClassVar[int]
    id: ChannelId
    capacity: int
    local_sat: int
    remote_sat: int
    peer_id: str
    def __init__(self, id: _Optional[_Union[ChannelId, _Mapping]] = ..., capacity: _Optional[int] = ..., local_sat: _Optional[int] = ..., remote_sat: _Optional[int] = ..., peer_id: _Optional[str] = ...) -> None: ...

class SwapStats(_message.Message):
    __slots__ = ("total_fees", "total_amount", "avg_fees", "avg_amount", "count")
    TOTAL_FEES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    AVG_FEES_FIELD_NUMBER: _ClassVar[int]
    AVG_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    total_fees: int
    total_amount: int
    avg_fees: int
    avg_amount: int
    count: int
    def __init__(self, total_fees: _Optional[int] = ..., total_amount: _Optional[int] = ..., avg_fees: _Optional[int] = ..., avg_amount: _Optional[int] = ..., count: _Optional[int] = ...) -> None: ...

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
    def __init__(self, total: _Optional[int] = ..., remaining: _Optional[int] = ..., start_date: _Optional[int] = ..., end_date: _Optional[int] = ...) -> None: ...

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
    def __init__(self, mnemonic: _Optional[str] = ..., xpub: _Optional[str] = ..., core_descriptor: _Optional[str] = ..., subaccount: _Optional[int] = ...) -> None: ...

class WalletInfo(_message.Message):
    __slots__ = ("name", "currency")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    name: str
    currency: Currency
    def __init__(self, name: _Optional[str] = ..., currency: _Optional[_Union[Currency, str]] = ...) -> None: ...

class ImportWalletRequest(_message.Message):
    __slots__ = ("credentials", "info", "password")
    CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    credentials: WalletCredentials
    info: WalletInfo
    password: str
    def __init__(self, credentials: _Optional[_Union[WalletCredentials, _Mapping]] = ..., info: _Optional[_Union[WalletInfo, _Mapping]] = ..., password: _Optional[str] = ...) -> None: ...

class CreateWalletRequest(_message.Message):
    __slots__ = ("info", "password")
    INFO_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    info: WalletInfo
    password: str
    def __init__(self, info: _Optional[_Union[WalletInfo, _Mapping]] = ..., password: _Optional[str] = ...) -> None: ...

class SetSubaccountRequest(_message.Message):
    __slots__ = ("name", "subaccount")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_FIELD_NUMBER: _ClassVar[int]
    name: str
    subaccount: int
    def __init__(self, name: _Optional[str] = ..., subaccount: _Optional[int] = ...) -> None: ...

class GetSubaccountsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetSubaccountsResponse(_message.Message):
    __slots__ = ("current", "subaccounts")
    CURRENT_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    current: int
    subaccounts: _containers.RepeatedCompositeFieldContainer[Subaccount]
    def __init__(self, current: _Optional[int] = ..., subaccounts: _Optional[_Iterable[_Union[Subaccount, _Mapping]]] = ...) -> None: ...

class ImportWalletResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetWalletsRequest(_message.Message):
    __slots__ = ("currency", "include_readonly")
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_READONLY_FIELD_NUMBER: _ClassVar[int]
    currency: Currency
    include_readonly: bool
    def __init__(self, currency: _Optional[_Union[Currency, str]] = ..., include_readonly: bool = ...) -> None: ...

class GetWalletRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class GetWalletCredentialsRequest(_message.Message):
    __slots__ = ("name", "password")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    name: str
    password: str
    def __init__(self, name: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class RemoveWalletRequest(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class Wallet(_message.Message):
    __slots__ = ("name", "currency", "readonly", "balance")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    READONLY_FIELD_NUMBER: _ClassVar[int]
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    name: str
    currency: Currency
    readonly: bool
    balance: Balance
    def __init__(self, name: _Optional[str] = ..., currency: _Optional[_Union[Currency, str]] = ..., readonly: bool = ..., balance: _Optional[_Union[Balance, _Mapping]] = ...) -> None: ...

class Wallets(_message.Message):
    __slots__ = ("wallets",)
    WALLETS_FIELD_NUMBER: _ClassVar[int]
    wallets: _containers.RepeatedCompositeFieldContainer[Wallet]
    def __init__(self, wallets: _Optional[_Iterable[_Union[Wallet, _Mapping]]] = ...) -> None: ...

class Balance(_message.Message):
    __slots__ = ("total", "confirmed", "unconfirmed")
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    CONFIRMED_FIELD_NUMBER: _ClassVar[int]
    UNCONFIRMED_FIELD_NUMBER: _ClassVar[int]
    total: int
    confirmed: int
    unconfirmed: int
    def __init__(self, total: _Optional[int] = ..., confirmed: _Optional[int] = ..., unconfirmed: _Optional[int] = ...) -> None: ...

class Subaccount(_message.Message):
    __slots__ = ("balance", "pointer", "type")
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    POINTER_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    balance: Balance
    pointer: int
    type: str
    def __init__(self, balance: _Optional[_Union[Balance, _Mapping]] = ..., pointer: _Optional[int] = ..., type: _Optional[str] = ...) -> None: ...

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
    def __init__(self, old: _Optional[str] = ..., new: _Optional[str] = ...) -> None: ...
