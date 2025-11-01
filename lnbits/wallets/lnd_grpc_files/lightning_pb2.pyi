from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OutputScriptType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SCRIPT_TYPE_PUBKEY_HASH: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_SCRIPT_HASH: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_WITNESS_V0_PUBKEY_HASH: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_WITNESS_V0_SCRIPT_HASH: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_PUBKEY: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_MULTISIG: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_NULLDATA: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_NON_STANDARD: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_WITNESS_UNKNOWN: _ClassVar[OutputScriptType]
    SCRIPT_TYPE_WITNESS_V1_TAPROOT: _ClassVar[OutputScriptType]

class CoinSelectionStrategy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STRATEGY_USE_GLOBAL_CONFIG: _ClassVar[CoinSelectionStrategy]
    STRATEGY_LARGEST: _ClassVar[CoinSelectionStrategy]
    STRATEGY_RANDOM: _ClassVar[CoinSelectionStrategy]

class AddressType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WITNESS_PUBKEY_HASH: _ClassVar[AddressType]
    NESTED_PUBKEY_HASH: _ClassVar[AddressType]
    UNUSED_WITNESS_PUBKEY_HASH: _ClassVar[AddressType]
    UNUSED_NESTED_PUBKEY_HASH: _ClassVar[AddressType]
    TAPROOT_PUBKEY: _ClassVar[AddressType]
    UNUSED_TAPROOT_PUBKEY: _ClassVar[AddressType]

class CommitmentType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN_COMMITMENT_TYPE: _ClassVar[CommitmentType]
    LEGACY: _ClassVar[CommitmentType]
    STATIC_REMOTE_KEY: _ClassVar[CommitmentType]
    ANCHORS: _ClassVar[CommitmentType]
    SCRIPT_ENFORCED_LEASE: _ClassVar[CommitmentType]
    SIMPLE_TAPROOT: _ClassVar[CommitmentType]
    SIMPLE_TAPROOT_OVERLAY: _ClassVar[CommitmentType]

class Initiator(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INITIATOR_UNKNOWN: _ClassVar[Initiator]
    INITIATOR_LOCAL: _ClassVar[Initiator]
    INITIATOR_REMOTE: _ClassVar[Initiator]
    INITIATOR_BOTH: _ClassVar[Initiator]

class ResolutionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TYPE_UNKNOWN: _ClassVar[ResolutionType]
    ANCHOR: _ClassVar[ResolutionType]
    INCOMING_HTLC: _ClassVar[ResolutionType]
    OUTGOING_HTLC: _ClassVar[ResolutionType]
    COMMIT: _ClassVar[ResolutionType]

class ResolutionOutcome(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OUTCOME_UNKNOWN: _ClassVar[ResolutionOutcome]
    CLAIMED: _ClassVar[ResolutionOutcome]
    UNCLAIMED: _ClassVar[ResolutionOutcome]
    ABANDONED: _ClassVar[ResolutionOutcome]
    FIRST_STAGE: _ClassVar[ResolutionOutcome]
    TIMEOUT: _ClassVar[ResolutionOutcome]

class NodeMetricType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[NodeMetricType]
    BETWEENNESS_CENTRALITY: _ClassVar[NodeMetricType]

class InvoiceHTLCState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACCEPTED: _ClassVar[InvoiceHTLCState]
    SETTLED: _ClassVar[InvoiceHTLCState]
    CANCELED: _ClassVar[InvoiceHTLCState]

class PaymentFailureReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FAILURE_REASON_NONE: _ClassVar[PaymentFailureReason]
    FAILURE_REASON_TIMEOUT: _ClassVar[PaymentFailureReason]
    FAILURE_REASON_NO_ROUTE: _ClassVar[PaymentFailureReason]
    FAILURE_REASON_ERROR: _ClassVar[PaymentFailureReason]
    FAILURE_REASON_INCORRECT_PAYMENT_DETAILS: _ClassVar[PaymentFailureReason]
    FAILURE_REASON_INSUFFICIENT_BALANCE: _ClassVar[PaymentFailureReason]
    FAILURE_REASON_CANCELED: _ClassVar[PaymentFailureReason]

class FeatureBit(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DATALOSS_PROTECT_REQ: _ClassVar[FeatureBit]
    DATALOSS_PROTECT_OPT: _ClassVar[FeatureBit]
    INITIAL_ROUING_SYNC: _ClassVar[FeatureBit]
    UPFRONT_SHUTDOWN_SCRIPT_REQ: _ClassVar[FeatureBit]
    UPFRONT_SHUTDOWN_SCRIPT_OPT: _ClassVar[FeatureBit]
    GOSSIP_QUERIES_REQ: _ClassVar[FeatureBit]
    GOSSIP_QUERIES_OPT: _ClassVar[FeatureBit]
    TLV_ONION_REQ: _ClassVar[FeatureBit]
    TLV_ONION_OPT: _ClassVar[FeatureBit]
    EXT_GOSSIP_QUERIES_REQ: _ClassVar[FeatureBit]
    EXT_GOSSIP_QUERIES_OPT: _ClassVar[FeatureBit]
    STATIC_REMOTE_KEY_REQ: _ClassVar[FeatureBit]
    STATIC_REMOTE_KEY_OPT: _ClassVar[FeatureBit]
    PAYMENT_ADDR_REQ: _ClassVar[FeatureBit]
    PAYMENT_ADDR_OPT: _ClassVar[FeatureBit]
    MPP_REQ: _ClassVar[FeatureBit]
    MPP_OPT: _ClassVar[FeatureBit]
    WUMBO_CHANNELS_REQ: _ClassVar[FeatureBit]
    WUMBO_CHANNELS_OPT: _ClassVar[FeatureBit]
    ANCHORS_REQ: _ClassVar[FeatureBit]
    ANCHORS_OPT: _ClassVar[FeatureBit]
    ANCHORS_ZERO_FEE_HTLC_REQ: _ClassVar[FeatureBit]
    ANCHORS_ZERO_FEE_HTLC_OPT: _ClassVar[FeatureBit]
    ROUTE_BLINDING_REQUIRED: _ClassVar[FeatureBit]
    ROUTE_BLINDING_OPTIONAL: _ClassVar[FeatureBit]
    AMP_REQ: _ClassVar[FeatureBit]
    AMP_OPT: _ClassVar[FeatureBit]

class UpdateFailure(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UPDATE_FAILURE_UNKNOWN: _ClassVar[UpdateFailure]
    UPDATE_FAILURE_PENDING: _ClassVar[UpdateFailure]
    UPDATE_FAILURE_NOT_FOUND: _ClassVar[UpdateFailure]
    UPDATE_FAILURE_INTERNAL_ERR: _ClassVar[UpdateFailure]
    UPDATE_FAILURE_INVALID_PARAMETER: _ClassVar[UpdateFailure]
SCRIPT_TYPE_PUBKEY_HASH: OutputScriptType
SCRIPT_TYPE_SCRIPT_HASH: OutputScriptType
SCRIPT_TYPE_WITNESS_V0_PUBKEY_HASH: OutputScriptType
SCRIPT_TYPE_WITNESS_V0_SCRIPT_HASH: OutputScriptType
SCRIPT_TYPE_PUBKEY: OutputScriptType
SCRIPT_TYPE_MULTISIG: OutputScriptType
SCRIPT_TYPE_NULLDATA: OutputScriptType
SCRIPT_TYPE_NON_STANDARD: OutputScriptType
SCRIPT_TYPE_WITNESS_UNKNOWN: OutputScriptType
SCRIPT_TYPE_WITNESS_V1_TAPROOT: OutputScriptType
STRATEGY_USE_GLOBAL_CONFIG: CoinSelectionStrategy
STRATEGY_LARGEST: CoinSelectionStrategy
STRATEGY_RANDOM: CoinSelectionStrategy
WITNESS_PUBKEY_HASH: AddressType
NESTED_PUBKEY_HASH: AddressType
UNUSED_WITNESS_PUBKEY_HASH: AddressType
UNUSED_NESTED_PUBKEY_HASH: AddressType
TAPROOT_PUBKEY: AddressType
UNUSED_TAPROOT_PUBKEY: AddressType
UNKNOWN_COMMITMENT_TYPE: CommitmentType
LEGACY: CommitmentType
STATIC_REMOTE_KEY: CommitmentType
ANCHORS: CommitmentType
SCRIPT_ENFORCED_LEASE: CommitmentType
SIMPLE_TAPROOT: CommitmentType
SIMPLE_TAPROOT_OVERLAY: CommitmentType
INITIATOR_UNKNOWN: Initiator
INITIATOR_LOCAL: Initiator
INITIATOR_REMOTE: Initiator
INITIATOR_BOTH: Initiator
TYPE_UNKNOWN: ResolutionType
ANCHOR: ResolutionType
INCOMING_HTLC: ResolutionType
OUTGOING_HTLC: ResolutionType
COMMIT: ResolutionType
OUTCOME_UNKNOWN: ResolutionOutcome
CLAIMED: ResolutionOutcome
UNCLAIMED: ResolutionOutcome
ABANDONED: ResolutionOutcome
FIRST_STAGE: ResolutionOutcome
TIMEOUT: ResolutionOutcome
UNKNOWN: NodeMetricType
BETWEENNESS_CENTRALITY: NodeMetricType
ACCEPTED: InvoiceHTLCState
SETTLED: InvoiceHTLCState
CANCELED: InvoiceHTLCState
FAILURE_REASON_NONE: PaymentFailureReason
FAILURE_REASON_TIMEOUT: PaymentFailureReason
FAILURE_REASON_NO_ROUTE: PaymentFailureReason
FAILURE_REASON_ERROR: PaymentFailureReason
FAILURE_REASON_INCORRECT_PAYMENT_DETAILS: PaymentFailureReason
FAILURE_REASON_INSUFFICIENT_BALANCE: PaymentFailureReason
FAILURE_REASON_CANCELED: PaymentFailureReason
DATALOSS_PROTECT_REQ: FeatureBit
DATALOSS_PROTECT_OPT: FeatureBit
INITIAL_ROUING_SYNC: FeatureBit
UPFRONT_SHUTDOWN_SCRIPT_REQ: FeatureBit
UPFRONT_SHUTDOWN_SCRIPT_OPT: FeatureBit
GOSSIP_QUERIES_REQ: FeatureBit
GOSSIP_QUERIES_OPT: FeatureBit
TLV_ONION_REQ: FeatureBit
TLV_ONION_OPT: FeatureBit
EXT_GOSSIP_QUERIES_REQ: FeatureBit
EXT_GOSSIP_QUERIES_OPT: FeatureBit
STATIC_REMOTE_KEY_REQ: FeatureBit
STATIC_REMOTE_KEY_OPT: FeatureBit
PAYMENT_ADDR_REQ: FeatureBit
PAYMENT_ADDR_OPT: FeatureBit
MPP_REQ: FeatureBit
MPP_OPT: FeatureBit
WUMBO_CHANNELS_REQ: FeatureBit
WUMBO_CHANNELS_OPT: FeatureBit
ANCHORS_REQ: FeatureBit
ANCHORS_OPT: FeatureBit
ANCHORS_ZERO_FEE_HTLC_REQ: FeatureBit
ANCHORS_ZERO_FEE_HTLC_OPT: FeatureBit
ROUTE_BLINDING_REQUIRED: FeatureBit
ROUTE_BLINDING_OPTIONAL: FeatureBit
AMP_REQ: FeatureBit
AMP_OPT: FeatureBit
UPDATE_FAILURE_UNKNOWN: UpdateFailure
UPDATE_FAILURE_PENDING: UpdateFailure
UPDATE_FAILURE_NOT_FOUND: UpdateFailure
UPDATE_FAILURE_INTERNAL_ERR: UpdateFailure
UPDATE_FAILURE_INVALID_PARAMETER: UpdateFailure

class LookupHtlcResolutionRequest(_message.Message):
    __slots__ = ("chan_id", "htlc_index")
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    HTLC_INDEX_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    htlc_index: int
    def __init__(self, chan_id: _Optional[int] = ..., htlc_index: _Optional[int] = ...) -> None: ...

class LookupHtlcResolutionResponse(_message.Message):
    __slots__ = ("settled", "offchain")
    SETTLED_FIELD_NUMBER: _ClassVar[int]
    OFFCHAIN_FIELD_NUMBER: _ClassVar[int]
    settled: bool
    offchain: bool
    def __init__(self, settled: bool = ..., offchain: bool = ...) -> None: ...

class SubscribeCustomMessagesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CustomMessage(_message.Message):
    __slots__ = ("peer", "type", "data")
    PEER_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    peer: bytes
    type: int
    data: bytes
    def __init__(self, peer: _Optional[bytes] = ..., type: _Optional[int] = ..., data: _Optional[bytes] = ...) -> None: ...

class SendCustomMessageRequest(_message.Message):
    __slots__ = ("peer", "type", "data")
    PEER_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    peer: bytes
    type: int
    data: bytes
    def __init__(self, peer: _Optional[bytes] = ..., type: _Optional[int] = ..., data: _Optional[bytes] = ...) -> None: ...

class SendCustomMessageResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class Utxo(_message.Message):
    __slots__ = ("address_type", "address", "amount_sat", "pk_script", "outpoint", "confirmations")
    ADDRESS_TYPE_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_SAT_FIELD_NUMBER: _ClassVar[int]
    PK_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    OUTPOINT_FIELD_NUMBER: _ClassVar[int]
    CONFIRMATIONS_FIELD_NUMBER: _ClassVar[int]
    address_type: AddressType
    address: str
    amount_sat: int
    pk_script: str
    outpoint: OutPoint
    confirmations: int
    def __init__(self, address_type: _Optional[_Union[AddressType, str]] = ..., address: _Optional[str] = ..., amount_sat: _Optional[int] = ..., pk_script: _Optional[str] = ..., outpoint: _Optional[_Union[OutPoint, _Mapping]] = ..., confirmations: _Optional[int] = ...) -> None: ...

class OutputDetail(_message.Message):
    __slots__ = ("output_type", "address", "pk_script", "output_index", "amount", "is_our_address")
    OUTPUT_TYPE_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PK_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_INDEX_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    IS_OUR_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    output_type: OutputScriptType
    address: str
    pk_script: str
    output_index: int
    amount: int
    is_our_address: bool
    def __init__(self, output_type: _Optional[_Union[OutputScriptType, str]] = ..., address: _Optional[str] = ..., pk_script: _Optional[str] = ..., output_index: _Optional[int] = ..., amount: _Optional[int] = ..., is_our_address: bool = ...) -> None: ...

class Transaction(_message.Message):
    __slots__ = ("tx_hash", "amount", "num_confirmations", "block_hash", "block_height", "time_stamp", "total_fees", "dest_addresses", "output_details", "raw_tx_hex", "label", "previous_outpoints")
    TX_HASH_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    NUM_CONFIRMATIONS_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HASH_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    TIME_STAMP_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FEES_FIELD_NUMBER: _ClassVar[int]
    DEST_ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_DETAILS_FIELD_NUMBER: _ClassVar[int]
    RAW_TX_HEX_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    PREVIOUS_OUTPOINTS_FIELD_NUMBER: _ClassVar[int]
    tx_hash: str
    amount: int
    num_confirmations: int
    block_hash: str
    block_height: int
    time_stamp: int
    total_fees: int
    dest_addresses: _containers.RepeatedScalarFieldContainer[str]
    output_details: _containers.RepeatedCompositeFieldContainer[OutputDetail]
    raw_tx_hex: str
    label: str
    previous_outpoints: _containers.RepeatedCompositeFieldContainer[PreviousOutPoint]
    def __init__(self, tx_hash: _Optional[str] = ..., amount: _Optional[int] = ..., num_confirmations: _Optional[int] = ..., block_hash: _Optional[str] = ..., block_height: _Optional[int] = ..., time_stamp: _Optional[int] = ..., total_fees: _Optional[int] = ..., dest_addresses: _Optional[_Iterable[str]] = ..., output_details: _Optional[_Iterable[_Union[OutputDetail, _Mapping]]] = ..., raw_tx_hex: _Optional[str] = ..., label: _Optional[str] = ..., previous_outpoints: _Optional[_Iterable[_Union[PreviousOutPoint, _Mapping]]] = ...) -> None: ...

class GetTransactionsRequest(_message.Message):
    __slots__ = ("start_height", "end_height", "account", "index_offset", "max_transactions")
    START_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    END_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    INDEX_OFFSET_FIELD_NUMBER: _ClassVar[int]
    MAX_TRANSACTIONS_FIELD_NUMBER: _ClassVar[int]
    start_height: int
    end_height: int
    account: str
    index_offset: int
    max_transactions: int
    def __init__(self, start_height: _Optional[int] = ..., end_height: _Optional[int] = ..., account: _Optional[str] = ..., index_offset: _Optional[int] = ..., max_transactions: _Optional[int] = ...) -> None: ...

class TransactionDetails(_message.Message):
    __slots__ = ("transactions", "last_index", "first_index")
    TRANSACTIONS_FIELD_NUMBER: _ClassVar[int]
    LAST_INDEX_FIELD_NUMBER: _ClassVar[int]
    FIRST_INDEX_FIELD_NUMBER: _ClassVar[int]
    transactions: _containers.RepeatedCompositeFieldContainer[Transaction]
    last_index: int
    first_index: int
    def __init__(self, transactions: _Optional[_Iterable[_Union[Transaction, _Mapping]]] = ..., last_index: _Optional[int] = ..., first_index: _Optional[int] = ...) -> None: ...

class FeeLimit(_message.Message):
    __slots__ = ("fixed", "fixed_msat", "percent")
    FIXED_FIELD_NUMBER: _ClassVar[int]
    FIXED_MSAT_FIELD_NUMBER: _ClassVar[int]
    PERCENT_FIELD_NUMBER: _ClassVar[int]
    fixed: int
    fixed_msat: int
    percent: int
    def __init__(self, fixed: _Optional[int] = ..., fixed_msat: _Optional[int] = ..., percent: _Optional[int] = ...) -> None: ...

class SendRequest(_message.Message):
    __slots__ = ("dest", "dest_string", "amt", "amt_msat", "payment_hash", "payment_hash_string", "payment_request", "final_cltv_delta", "fee_limit", "outgoing_chan_id", "last_hop_pubkey", "cltv_limit", "dest_custom_records", "allow_self_payment", "dest_features", "payment_addr")
    class DestCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    DEST_FIELD_NUMBER: _ClassVar[int]
    DEST_STRING_FIELD_NUMBER: _ClassVar[int]
    AMT_FIELD_NUMBER: _ClassVar[int]
    AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_HASH_STRING_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    FINAL_CLTV_DELTA_FIELD_NUMBER: _ClassVar[int]
    FEE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    LAST_HOP_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    CLTV_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DEST_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    ALLOW_SELF_PAYMENT_FIELD_NUMBER: _ClassVar[int]
    DEST_FEATURES_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    dest: bytes
    dest_string: str
    amt: int
    amt_msat: int
    payment_hash: bytes
    payment_hash_string: str
    payment_request: str
    final_cltv_delta: int
    fee_limit: FeeLimit
    outgoing_chan_id: int
    last_hop_pubkey: bytes
    cltv_limit: int
    dest_custom_records: _containers.ScalarMap[int, bytes]
    allow_self_payment: bool
    dest_features: _containers.RepeatedScalarFieldContainer[FeatureBit]
    payment_addr: bytes
    def __init__(self, dest: _Optional[bytes] = ..., dest_string: _Optional[str] = ..., amt: _Optional[int] = ..., amt_msat: _Optional[int] = ..., payment_hash: _Optional[bytes] = ..., payment_hash_string: _Optional[str] = ..., payment_request: _Optional[str] = ..., final_cltv_delta: _Optional[int] = ..., fee_limit: _Optional[_Union[FeeLimit, _Mapping]] = ..., outgoing_chan_id: _Optional[int] = ..., last_hop_pubkey: _Optional[bytes] = ..., cltv_limit: _Optional[int] = ..., dest_custom_records: _Optional[_Mapping[int, bytes]] = ..., allow_self_payment: bool = ..., dest_features: _Optional[_Iterable[_Union[FeatureBit, str]]] = ..., payment_addr: _Optional[bytes] = ...) -> None: ...

class SendResponse(_message.Message):
    __slots__ = ("payment_error", "payment_preimage", "payment_route", "payment_hash")
    PAYMENT_ERROR_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ROUTE_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    payment_error: str
    payment_preimage: bytes
    payment_route: Route
    payment_hash: bytes
    def __init__(self, payment_error: _Optional[str] = ..., payment_preimage: _Optional[bytes] = ..., payment_route: _Optional[_Union[Route, _Mapping]] = ..., payment_hash: _Optional[bytes] = ...) -> None: ...

class SendToRouteRequest(_message.Message):
    __slots__ = ("payment_hash", "payment_hash_string", "route")
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_HASH_STRING_FIELD_NUMBER: _ClassVar[int]
    ROUTE_FIELD_NUMBER: _ClassVar[int]
    payment_hash: bytes
    payment_hash_string: str
    route: Route
    def __init__(self, payment_hash: _Optional[bytes] = ..., payment_hash_string: _Optional[str] = ..., route: _Optional[_Union[Route, _Mapping]] = ...) -> None: ...

class ChannelAcceptRequest(_message.Message):
    __slots__ = ("node_pubkey", "chain_hash", "pending_chan_id", "funding_amt", "push_amt", "dust_limit", "max_value_in_flight", "channel_reserve", "min_htlc", "fee_per_kw", "csv_delay", "max_accepted_htlcs", "channel_flags", "commitment_type", "wants_zero_conf", "wants_scid_alias")
    NODE_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    CHAIN_HASH_FIELD_NUMBER: _ClassVar[int]
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    FUNDING_AMT_FIELD_NUMBER: _ClassVar[int]
    PUSH_AMT_FIELD_NUMBER: _ClassVar[int]
    DUST_LIMIT_FIELD_NUMBER: _ClassVar[int]
    MAX_VALUE_IN_FLIGHT_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_RESERVE_FIELD_NUMBER: _ClassVar[int]
    MIN_HTLC_FIELD_NUMBER: _ClassVar[int]
    FEE_PER_KW_FIELD_NUMBER: _ClassVar[int]
    CSV_DELAY_FIELD_NUMBER: _ClassVar[int]
    MAX_ACCEPTED_HTLCS_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FLAGS_FIELD_NUMBER: _ClassVar[int]
    COMMITMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    WANTS_ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    WANTS_SCID_ALIAS_FIELD_NUMBER: _ClassVar[int]
    node_pubkey: bytes
    chain_hash: bytes
    pending_chan_id: bytes
    funding_amt: int
    push_amt: int
    dust_limit: int
    max_value_in_flight: int
    channel_reserve: int
    min_htlc: int
    fee_per_kw: int
    csv_delay: int
    max_accepted_htlcs: int
    channel_flags: int
    commitment_type: CommitmentType
    wants_zero_conf: bool
    wants_scid_alias: bool
    def __init__(self, node_pubkey: _Optional[bytes] = ..., chain_hash: _Optional[bytes] = ..., pending_chan_id: _Optional[bytes] = ..., funding_amt: _Optional[int] = ..., push_amt: _Optional[int] = ..., dust_limit: _Optional[int] = ..., max_value_in_flight: _Optional[int] = ..., channel_reserve: _Optional[int] = ..., min_htlc: _Optional[int] = ..., fee_per_kw: _Optional[int] = ..., csv_delay: _Optional[int] = ..., max_accepted_htlcs: _Optional[int] = ..., channel_flags: _Optional[int] = ..., commitment_type: _Optional[_Union[CommitmentType, str]] = ..., wants_zero_conf: bool = ..., wants_scid_alias: bool = ...) -> None: ...

class ChannelAcceptResponse(_message.Message):
    __slots__ = ("accept", "pending_chan_id", "error", "upfront_shutdown", "csv_delay", "reserve_sat", "in_flight_max_msat", "max_htlc_count", "min_htlc_in", "min_accept_depth", "zero_conf")
    ACCEPT_FIELD_NUMBER: _ClassVar[int]
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    UPFRONT_SHUTDOWN_FIELD_NUMBER: _ClassVar[int]
    CSV_DELAY_FIELD_NUMBER: _ClassVar[int]
    RESERVE_SAT_FIELD_NUMBER: _ClassVar[int]
    IN_FLIGHT_MAX_MSAT_FIELD_NUMBER: _ClassVar[int]
    MAX_HTLC_COUNT_FIELD_NUMBER: _ClassVar[int]
    MIN_HTLC_IN_FIELD_NUMBER: _ClassVar[int]
    MIN_ACCEPT_DEPTH_FIELD_NUMBER: _ClassVar[int]
    ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    accept: bool
    pending_chan_id: bytes
    error: str
    upfront_shutdown: str
    csv_delay: int
    reserve_sat: int
    in_flight_max_msat: int
    max_htlc_count: int
    min_htlc_in: int
    min_accept_depth: int
    zero_conf: bool
    def __init__(self, accept: bool = ..., pending_chan_id: _Optional[bytes] = ..., error: _Optional[str] = ..., upfront_shutdown: _Optional[str] = ..., csv_delay: _Optional[int] = ..., reserve_sat: _Optional[int] = ..., in_flight_max_msat: _Optional[int] = ..., max_htlc_count: _Optional[int] = ..., min_htlc_in: _Optional[int] = ..., min_accept_depth: _Optional[int] = ..., zero_conf: bool = ...) -> None: ...

class ChannelPoint(_message.Message):
    __slots__ = ("funding_txid_bytes", "funding_txid_str", "output_index")
    FUNDING_TXID_BYTES_FIELD_NUMBER: _ClassVar[int]
    FUNDING_TXID_STR_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_INDEX_FIELD_NUMBER: _ClassVar[int]
    funding_txid_bytes: bytes
    funding_txid_str: str
    output_index: int
    def __init__(self, funding_txid_bytes: _Optional[bytes] = ..., funding_txid_str: _Optional[str] = ..., output_index: _Optional[int] = ...) -> None: ...

class OutPoint(_message.Message):
    __slots__ = ("txid_bytes", "txid_str", "output_index")
    TXID_BYTES_FIELD_NUMBER: _ClassVar[int]
    TXID_STR_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_INDEX_FIELD_NUMBER: _ClassVar[int]
    txid_bytes: bytes
    txid_str: str
    output_index: int
    def __init__(self, txid_bytes: _Optional[bytes] = ..., txid_str: _Optional[str] = ..., output_index: _Optional[int] = ...) -> None: ...

class PreviousOutPoint(_message.Message):
    __slots__ = ("outpoint", "is_our_output")
    OUTPOINT_FIELD_NUMBER: _ClassVar[int]
    IS_OUR_OUTPUT_FIELD_NUMBER: _ClassVar[int]
    outpoint: str
    is_our_output: bool
    def __init__(self, outpoint: _Optional[str] = ..., is_our_output: bool = ...) -> None: ...

class LightningAddress(_message.Message):
    __slots__ = ("pubkey", "host")
    PUBKEY_FIELD_NUMBER: _ClassVar[int]
    HOST_FIELD_NUMBER: _ClassVar[int]
    pubkey: str
    host: str
    def __init__(self, pubkey: _Optional[str] = ..., host: _Optional[str] = ...) -> None: ...

class EstimateFeeRequest(_message.Message):
    __slots__ = ("AddrToAmount", "target_conf", "min_confs", "spend_unconfirmed", "coin_selection_strategy")
    class AddrToAmountEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    ADDRTOAMOUNT_FIELD_NUMBER: _ClassVar[int]
    TARGET_CONF_FIELD_NUMBER: _ClassVar[int]
    MIN_CONFS_FIELD_NUMBER: _ClassVar[int]
    SPEND_UNCONFIRMED_FIELD_NUMBER: _ClassVar[int]
    COIN_SELECTION_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    AddrToAmount: _containers.ScalarMap[str, int]
    target_conf: int
    min_confs: int
    spend_unconfirmed: bool
    coin_selection_strategy: CoinSelectionStrategy
    def __init__(self, AddrToAmount: _Optional[_Mapping[str, int]] = ..., target_conf: _Optional[int] = ..., min_confs: _Optional[int] = ..., spend_unconfirmed: bool = ..., coin_selection_strategy: _Optional[_Union[CoinSelectionStrategy, str]] = ...) -> None: ...

class EstimateFeeResponse(_message.Message):
    __slots__ = ("fee_sat", "feerate_sat_per_byte", "sat_per_vbyte")
    FEE_SAT_FIELD_NUMBER: _ClassVar[int]
    FEERATE_SAT_PER_BYTE_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_VBYTE_FIELD_NUMBER: _ClassVar[int]
    fee_sat: int
    feerate_sat_per_byte: int
    sat_per_vbyte: int
    def __init__(self, fee_sat: _Optional[int] = ..., feerate_sat_per_byte: _Optional[int] = ..., sat_per_vbyte: _Optional[int] = ...) -> None: ...

class SendManyRequest(_message.Message):
    __slots__ = ("AddrToAmount", "target_conf", "sat_per_vbyte", "sat_per_byte", "label", "min_confs", "spend_unconfirmed", "coin_selection_strategy")
    class AddrToAmountEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    ADDRTOAMOUNT_FIELD_NUMBER: _ClassVar[int]
    TARGET_CONF_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_VBYTE_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_BYTE_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    MIN_CONFS_FIELD_NUMBER: _ClassVar[int]
    SPEND_UNCONFIRMED_FIELD_NUMBER: _ClassVar[int]
    COIN_SELECTION_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    AddrToAmount: _containers.ScalarMap[str, int]
    target_conf: int
    sat_per_vbyte: int
    sat_per_byte: int
    label: str
    min_confs: int
    spend_unconfirmed: bool
    coin_selection_strategy: CoinSelectionStrategy
    def __init__(self, AddrToAmount: _Optional[_Mapping[str, int]] = ..., target_conf: _Optional[int] = ..., sat_per_vbyte: _Optional[int] = ..., sat_per_byte: _Optional[int] = ..., label: _Optional[str] = ..., min_confs: _Optional[int] = ..., spend_unconfirmed: bool = ..., coin_selection_strategy: _Optional[_Union[CoinSelectionStrategy, str]] = ...) -> None: ...

class SendManyResponse(_message.Message):
    __slots__ = ("txid",)
    TXID_FIELD_NUMBER: _ClassVar[int]
    txid: str
    def __init__(self, txid: _Optional[str] = ...) -> None: ...

class SendCoinsRequest(_message.Message):
    __slots__ = ("addr", "amount", "target_conf", "sat_per_vbyte", "sat_per_byte", "send_all", "label", "min_confs", "spend_unconfirmed", "coin_selection_strategy", "outpoints")
    ADDR_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    TARGET_CONF_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_VBYTE_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_BYTE_FIELD_NUMBER: _ClassVar[int]
    SEND_ALL_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    MIN_CONFS_FIELD_NUMBER: _ClassVar[int]
    SPEND_UNCONFIRMED_FIELD_NUMBER: _ClassVar[int]
    COIN_SELECTION_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    OUTPOINTS_FIELD_NUMBER: _ClassVar[int]
    addr: str
    amount: int
    target_conf: int
    sat_per_vbyte: int
    sat_per_byte: int
    send_all: bool
    label: str
    min_confs: int
    spend_unconfirmed: bool
    coin_selection_strategy: CoinSelectionStrategy
    outpoints: _containers.RepeatedCompositeFieldContainer[OutPoint]
    def __init__(self, addr: _Optional[str] = ..., amount: _Optional[int] = ..., target_conf: _Optional[int] = ..., sat_per_vbyte: _Optional[int] = ..., sat_per_byte: _Optional[int] = ..., send_all: bool = ..., label: _Optional[str] = ..., min_confs: _Optional[int] = ..., spend_unconfirmed: bool = ..., coin_selection_strategy: _Optional[_Union[CoinSelectionStrategy, str]] = ..., outpoints: _Optional[_Iterable[_Union[OutPoint, _Mapping]]] = ...) -> None: ...

class SendCoinsResponse(_message.Message):
    __slots__ = ("txid",)
    TXID_FIELD_NUMBER: _ClassVar[int]
    txid: str
    def __init__(self, txid: _Optional[str] = ...) -> None: ...

class ListUnspentRequest(_message.Message):
    __slots__ = ("min_confs", "max_confs", "account")
    MIN_CONFS_FIELD_NUMBER: _ClassVar[int]
    MAX_CONFS_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    min_confs: int
    max_confs: int
    account: str
    def __init__(self, min_confs: _Optional[int] = ..., max_confs: _Optional[int] = ..., account: _Optional[str] = ...) -> None: ...

class ListUnspentResponse(_message.Message):
    __slots__ = ("utxos",)
    UTXOS_FIELD_NUMBER: _ClassVar[int]
    utxos: _containers.RepeatedCompositeFieldContainer[Utxo]
    def __init__(self, utxos: _Optional[_Iterable[_Union[Utxo, _Mapping]]] = ...) -> None: ...

class NewAddressRequest(_message.Message):
    __slots__ = ("type", "account")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    type: AddressType
    account: str
    def __init__(self, type: _Optional[_Union[AddressType, str]] = ..., account: _Optional[str] = ...) -> None: ...

class NewAddressResponse(_message.Message):
    __slots__ = ("address",)
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    address: str
    def __init__(self, address: _Optional[str] = ...) -> None: ...

class SignMessageRequest(_message.Message):
    __slots__ = ("msg", "single_hash")
    MSG_FIELD_NUMBER: _ClassVar[int]
    SINGLE_HASH_FIELD_NUMBER: _ClassVar[int]
    msg: bytes
    single_hash: bool
    def __init__(self, msg: _Optional[bytes] = ..., single_hash: bool = ...) -> None: ...

class SignMessageResponse(_message.Message):
    __slots__ = ("signature",)
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    signature: str
    def __init__(self, signature: _Optional[str] = ...) -> None: ...

class VerifyMessageRequest(_message.Message):
    __slots__ = ("msg", "signature")
    MSG_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    msg: bytes
    signature: str
    def __init__(self, msg: _Optional[bytes] = ..., signature: _Optional[str] = ...) -> None: ...

class VerifyMessageResponse(_message.Message):
    __slots__ = ("valid", "pubkey")
    VALID_FIELD_NUMBER: _ClassVar[int]
    PUBKEY_FIELD_NUMBER: _ClassVar[int]
    valid: bool
    pubkey: str
    def __init__(self, valid: bool = ..., pubkey: _Optional[str] = ...) -> None: ...

class ConnectPeerRequest(_message.Message):
    __slots__ = ("addr", "perm", "timeout")
    ADDR_FIELD_NUMBER: _ClassVar[int]
    PERM_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    addr: LightningAddress
    perm: bool
    timeout: int
    def __init__(self, addr: _Optional[_Union[LightningAddress, _Mapping]] = ..., perm: bool = ..., timeout: _Optional[int] = ...) -> None: ...

class ConnectPeerResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class DisconnectPeerRequest(_message.Message):
    __slots__ = ("pub_key",)
    PUB_KEY_FIELD_NUMBER: _ClassVar[int]
    pub_key: str
    def __init__(self, pub_key: _Optional[str] = ...) -> None: ...

class DisconnectPeerResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class HTLC(_message.Message):
    __slots__ = ("incoming", "amount", "hash_lock", "expiration_height", "htlc_index", "forwarding_channel", "forwarding_htlc_index", "locked_in")
    INCOMING_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    HASH_LOCK_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    HTLC_INDEX_FIELD_NUMBER: _ClassVar[int]
    FORWARDING_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    FORWARDING_HTLC_INDEX_FIELD_NUMBER: _ClassVar[int]
    LOCKED_IN_FIELD_NUMBER: _ClassVar[int]
    incoming: bool
    amount: int
    hash_lock: bytes
    expiration_height: int
    htlc_index: int
    forwarding_channel: int
    forwarding_htlc_index: int
    locked_in: bool
    def __init__(self, incoming: bool = ..., amount: _Optional[int] = ..., hash_lock: _Optional[bytes] = ..., expiration_height: _Optional[int] = ..., htlc_index: _Optional[int] = ..., forwarding_channel: _Optional[int] = ..., forwarding_htlc_index: _Optional[int] = ..., locked_in: bool = ...) -> None: ...

class ChannelConstraints(_message.Message):
    __slots__ = ("csv_delay", "chan_reserve_sat", "dust_limit_sat", "max_pending_amt_msat", "min_htlc_msat", "max_accepted_htlcs")
    CSV_DELAY_FIELD_NUMBER: _ClassVar[int]
    CHAN_RESERVE_SAT_FIELD_NUMBER: _ClassVar[int]
    DUST_LIMIT_SAT_FIELD_NUMBER: _ClassVar[int]
    MAX_PENDING_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    MIN_HTLC_MSAT_FIELD_NUMBER: _ClassVar[int]
    MAX_ACCEPTED_HTLCS_FIELD_NUMBER: _ClassVar[int]
    csv_delay: int
    chan_reserve_sat: int
    dust_limit_sat: int
    max_pending_amt_msat: int
    min_htlc_msat: int
    max_accepted_htlcs: int
    def __init__(self, csv_delay: _Optional[int] = ..., chan_reserve_sat: _Optional[int] = ..., dust_limit_sat: _Optional[int] = ..., max_pending_amt_msat: _Optional[int] = ..., min_htlc_msat: _Optional[int] = ..., max_accepted_htlcs: _Optional[int] = ...) -> None: ...

class Channel(_message.Message):
    __slots__ = ("active", "remote_pubkey", "channel_point", "chan_id", "capacity", "local_balance", "remote_balance", "commit_fee", "commit_weight", "fee_per_kw", "unsettled_balance", "total_satoshis_sent", "total_satoshis_received", "num_updates", "pending_htlcs", "csv_delay", "private", "initiator", "chan_status_flags", "local_chan_reserve_sat", "remote_chan_reserve_sat", "static_remote_key", "commitment_type", "lifetime", "uptime", "close_address", "push_amount_sat", "thaw_height", "local_constraints", "remote_constraints", "alias_scids", "zero_conf", "zero_conf_confirmed_scid", "peer_alias", "peer_scid_alias", "memo", "custom_channel_data")
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    REMOTE_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_POINT_FIELD_NUMBER: _ClassVar[int]
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    LOCAL_BALANCE_FIELD_NUMBER: _ClassVar[int]
    REMOTE_BALANCE_FIELD_NUMBER: _ClassVar[int]
    COMMIT_FEE_FIELD_NUMBER: _ClassVar[int]
    COMMIT_WEIGHT_FIELD_NUMBER: _ClassVar[int]
    FEE_PER_KW_FIELD_NUMBER: _ClassVar[int]
    UNSETTLED_BALANCE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SATOSHIS_SENT_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SATOSHIS_RECEIVED_FIELD_NUMBER: _ClassVar[int]
    NUM_UPDATES_FIELD_NUMBER: _ClassVar[int]
    PENDING_HTLCS_FIELD_NUMBER: _ClassVar[int]
    CSV_DELAY_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    INITIATOR_FIELD_NUMBER: _ClassVar[int]
    CHAN_STATUS_FLAGS_FIELD_NUMBER: _ClassVar[int]
    LOCAL_CHAN_RESERVE_SAT_FIELD_NUMBER: _ClassVar[int]
    REMOTE_CHAN_RESERVE_SAT_FIELD_NUMBER: _ClassVar[int]
    STATIC_REMOTE_KEY_FIELD_NUMBER: _ClassVar[int]
    COMMITMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    LIFETIME_FIELD_NUMBER: _ClassVar[int]
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    CLOSE_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PUSH_AMOUNT_SAT_FIELD_NUMBER: _ClassVar[int]
    THAW_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    LOCAL_CONSTRAINTS_FIELD_NUMBER: _ClassVar[int]
    REMOTE_CONSTRAINTS_FIELD_NUMBER: _ClassVar[int]
    ALIAS_SCIDS_FIELD_NUMBER: _ClassVar[int]
    ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    ZERO_CONF_CONFIRMED_SCID_FIELD_NUMBER: _ClassVar[int]
    PEER_ALIAS_FIELD_NUMBER: _ClassVar[int]
    PEER_SCID_ALIAS_FIELD_NUMBER: _ClassVar[int]
    MEMO_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_CHANNEL_DATA_FIELD_NUMBER: _ClassVar[int]
    active: bool
    remote_pubkey: str
    channel_point: str
    chan_id: int
    capacity: int
    local_balance: int
    remote_balance: int
    commit_fee: int
    commit_weight: int
    fee_per_kw: int
    unsettled_balance: int
    total_satoshis_sent: int
    total_satoshis_received: int
    num_updates: int
    pending_htlcs: _containers.RepeatedCompositeFieldContainer[HTLC]
    csv_delay: int
    private: bool
    initiator: bool
    chan_status_flags: str
    local_chan_reserve_sat: int
    remote_chan_reserve_sat: int
    static_remote_key: bool
    commitment_type: CommitmentType
    lifetime: int
    uptime: int
    close_address: str
    push_amount_sat: int
    thaw_height: int
    local_constraints: ChannelConstraints
    remote_constraints: ChannelConstraints
    alias_scids: _containers.RepeatedScalarFieldContainer[int]
    zero_conf: bool
    zero_conf_confirmed_scid: int
    peer_alias: str
    peer_scid_alias: int
    memo: str
    custom_channel_data: bytes
    def __init__(self, active: bool = ..., remote_pubkey: _Optional[str] = ..., channel_point: _Optional[str] = ..., chan_id: _Optional[int] = ..., capacity: _Optional[int] = ..., local_balance: _Optional[int] = ..., remote_balance: _Optional[int] = ..., commit_fee: _Optional[int] = ..., commit_weight: _Optional[int] = ..., fee_per_kw: _Optional[int] = ..., unsettled_balance: _Optional[int] = ..., total_satoshis_sent: _Optional[int] = ..., total_satoshis_received: _Optional[int] = ..., num_updates: _Optional[int] = ..., pending_htlcs: _Optional[_Iterable[_Union[HTLC, _Mapping]]] = ..., csv_delay: _Optional[int] = ..., private: bool = ..., initiator: bool = ..., chan_status_flags: _Optional[str] = ..., local_chan_reserve_sat: _Optional[int] = ..., remote_chan_reserve_sat: _Optional[int] = ..., static_remote_key: bool = ..., commitment_type: _Optional[_Union[CommitmentType, str]] = ..., lifetime: _Optional[int] = ..., uptime: _Optional[int] = ..., close_address: _Optional[str] = ..., push_amount_sat: _Optional[int] = ..., thaw_height: _Optional[int] = ..., local_constraints: _Optional[_Union[ChannelConstraints, _Mapping]] = ..., remote_constraints: _Optional[_Union[ChannelConstraints, _Mapping]] = ..., alias_scids: _Optional[_Iterable[int]] = ..., zero_conf: bool = ..., zero_conf_confirmed_scid: _Optional[int] = ..., peer_alias: _Optional[str] = ..., peer_scid_alias: _Optional[int] = ..., memo: _Optional[str] = ..., custom_channel_data: _Optional[bytes] = ...) -> None: ...

class ListChannelsRequest(_message.Message):
    __slots__ = ("active_only", "inactive_only", "public_only", "private_only", "peer", "peer_alias_lookup")
    ACTIVE_ONLY_FIELD_NUMBER: _ClassVar[int]
    INACTIVE_ONLY_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_ONLY_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_ONLY_FIELD_NUMBER: _ClassVar[int]
    PEER_FIELD_NUMBER: _ClassVar[int]
    PEER_ALIAS_LOOKUP_FIELD_NUMBER: _ClassVar[int]
    active_only: bool
    inactive_only: bool
    public_only: bool
    private_only: bool
    peer: bytes
    peer_alias_lookup: bool
    def __init__(self, active_only: bool = ..., inactive_only: bool = ..., public_only: bool = ..., private_only: bool = ..., peer: _Optional[bytes] = ..., peer_alias_lookup: bool = ...) -> None: ...

class ListChannelsResponse(_message.Message):
    __slots__ = ("channels",)
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    channels: _containers.RepeatedCompositeFieldContainer[Channel]
    def __init__(self, channels: _Optional[_Iterable[_Union[Channel, _Mapping]]] = ...) -> None: ...

class AliasMap(_message.Message):
    __slots__ = ("base_scid", "aliases")
    BASE_SCID_FIELD_NUMBER: _ClassVar[int]
    ALIASES_FIELD_NUMBER: _ClassVar[int]
    base_scid: int
    aliases: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, base_scid: _Optional[int] = ..., aliases: _Optional[_Iterable[int]] = ...) -> None: ...

class ListAliasesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListAliasesResponse(_message.Message):
    __slots__ = ("alias_maps",)
    ALIAS_MAPS_FIELD_NUMBER: _ClassVar[int]
    alias_maps: _containers.RepeatedCompositeFieldContainer[AliasMap]
    def __init__(self, alias_maps: _Optional[_Iterable[_Union[AliasMap, _Mapping]]] = ...) -> None: ...

class ChannelCloseSummary(_message.Message):
    __slots__ = ("channel_point", "chan_id", "chain_hash", "closing_tx_hash", "remote_pubkey", "capacity", "close_height", "settled_balance", "time_locked_balance", "close_type", "open_initiator", "close_initiator", "resolutions", "alias_scids", "zero_conf_confirmed_scid", "custom_channel_data")
    class ClosureType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        COOPERATIVE_CLOSE: _ClassVar[ChannelCloseSummary.ClosureType]
        LOCAL_FORCE_CLOSE: _ClassVar[ChannelCloseSummary.ClosureType]
        REMOTE_FORCE_CLOSE: _ClassVar[ChannelCloseSummary.ClosureType]
        BREACH_CLOSE: _ClassVar[ChannelCloseSummary.ClosureType]
        FUNDING_CANCELED: _ClassVar[ChannelCloseSummary.ClosureType]
        ABANDONED: _ClassVar[ChannelCloseSummary.ClosureType]
    COOPERATIVE_CLOSE: ChannelCloseSummary.ClosureType
    LOCAL_FORCE_CLOSE: ChannelCloseSummary.ClosureType
    REMOTE_FORCE_CLOSE: ChannelCloseSummary.ClosureType
    BREACH_CLOSE: ChannelCloseSummary.ClosureType
    FUNDING_CANCELED: ChannelCloseSummary.ClosureType
    ABANDONED: ChannelCloseSummary.ClosureType
    CHANNEL_POINT_FIELD_NUMBER: _ClassVar[int]
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    CHAIN_HASH_FIELD_NUMBER: _ClassVar[int]
    CLOSING_TX_HASH_FIELD_NUMBER: _ClassVar[int]
    REMOTE_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    CLOSE_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    SETTLED_BALANCE_FIELD_NUMBER: _ClassVar[int]
    TIME_LOCKED_BALANCE_FIELD_NUMBER: _ClassVar[int]
    CLOSE_TYPE_FIELD_NUMBER: _ClassVar[int]
    OPEN_INITIATOR_FIELD_NUMBER: _ClassVar[int]
    CLOSE_INITIATOR_FIELD_NUMBER: _ClassVar[int]
    RESOLUTIONS_FIELD_NUMBER: _ClassVar[int]
    ALIAS_SCIDS_FIELD_NUMBER: _ClassVar[int]
    ZERO_CONF_CONFIRMED_SCID_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_CHANNEL_DATA_FIELD_NUMBER: _ClassVar[int]
    channel_point: str
    chan_id: int
    chain_hash: str
    closing_tx_hash: str
    remote_pubkey: str
    capacity: int
    close_height: int
    settled_balance: int
    time_locked_balance: int
    close_type: ChannelCloseSummary.ClosureType
    open_initiator: Initiator
    close_initiator: Initiator
    resolutions: _containers.RepeatedCompositeFieldContainer[Resolution]
    alias_scids: _containers.RepeatedScalarFieldContainer[int]
    zero_conf_confirmed_scid: int
    custom_channel_data: bytes
    def __init__(self, channel_point: _Optional[str] = ..., chan_id: _Optional[int] = ..., chain_hash: _Optional[str] = ..., closing_tx_hash: _Optional[str] = ..., remote_pubkey: _Optional[str] = ..., capacity: _Optional[int] = ..., close_height: _Optional[int] = ..., settled_balance: _Optional[int] = ..., time_locked_balance: _Optional[int] = ..., close_type: _Optional[_Union[ChannelCloseSummary.ClosureType, str]] = ..., open_initiator: _Optional[_Union[Initiator, str]] = ..., close_initiator: _Optional[_Union[Initiator, str]] = ..., resolutions: _Optional[_Iterable[_Union[Resolution, _Mapping]]] = ..., alias_scids: _Optional[_Iterable[int]] = ..., zero_conf_confirmed_scid: _Optional[int] = ..., custom_channel_data: _Optional[bytes] = ...) -> None: ...

class Resolution(_message.Message):
    __slots__ = ("resolution_type", "outcome", "outpoint", "amount_sat", "sweep_txid")
    RESOLUTION_TYPE_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    OUTPOINT_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_SAT_FIELD_NUMBER: _ClassVar[int]
    SWEEP_TXID_FIELD_NUMBER: _ClassVar[int]
    resolution_type: ResolutionType
    outcome: ResolutionOutcome
    outpoint: OutPoint
    amount_sat: int
    sweep_txid: str
    def __init__(self, resolution_type: _Optional[_Union[ResolutionType, str]] = ..., outcome: _Optional[_Union[ResolutionOutcome, str]] = ..., outpoint: _Optional[_Union[OutPoint, _Mapping]] = ..., amount_sat: _Optional[int] = ..., sweep_txid: _Optional[str] = ...) -> None: ...

class ClosedChannelsRequest(_message.Message):
    __slots__ = ("cooperative", "local_force", "remote_force", "breach", "funding_canceled", "abandoned")
    COOPERATIVE_FIELD_NUMBER: _ClassVar[int]
    LOCAL_FORCE_FIELD_NUMBER: _ClassVar[int]
    REMOTE_FORCE_FIELD_NUMBER: _ClassVar[int]
    BREACH_FIELD_NUMBER: _ClassVar[int]
    FUNDING_CANCELED_FIELD_NUMBER: _ClassVar[int]
    ABANDONED_FIELD_NUMBER: _ClassVar[int]
    cooperative: bool
    local_force: bool
    remote_force: bool
    breach: bool
    funding_canceled: bool
    abandoned: bool
    def __init__(self, cooperative: bool = ..., local_force: bool = ..., remote_force: bool = ..., breach: bool = ..., funding_canceled: bool = ..., abandoned: bool = ...) -> None: ...

class ClosedChannelsResponse(_message.Message):
    __slots__ = ("channels",)
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    channels: _containers.RepeatedCompositeFieldContainer[ChannelCloseSummary]
    def __init__(self, channels: _Optional[_Iterable[_Union[ChannelCloseSummary, _Mapping]]] = ...) -> None: ...

class Peer(_message.Message):
    __slots__ = ("pub_key", "address", "bytes_sent", "bytes_recv", "sat_sent", "sat_recv", "inbound", "ping_time", "sync_type", "features", "errors", "flap_count", "last_flap_ns", "last_ping_payload")
    class SyncType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNKNOWN_SYNC: _ClassVar[Peer.SyncType]
        ACTIVE_SYNC: _ClassVar[Peer.SyncType]
        PASSIVE_SYNC: _ClassVar[Peer.SyncType]
        PINNED_SYNC: _ClassVar[Peer.SyncType]
    UNKNOWN_SYNC: Peer.SyncType
    ACTIVE_SYNC: Peer.SyncType
    PASSIVE_SYNC: Peer.SyncType
    PINNED_SYNC: Peer.SyncType
    class FeaturesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: Feature
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[Feature, _Mapping]] = ...) -> None: ...
    PUB_KEY_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    BYTES_SENT_FIELD_NUMBER: _ClassVar[int]
    BYTES_RECV_FIELD_NUMBER: _ClassVar[int]
    SAT_SENT_FIELD_NUMBER: _ClassVar[int]
    SAT_RECV_FIELD_NUMBER: _ClassVar[int]
    INBOUND_FIELD_NUMBER: _ClassVar[int]
    PING_TIME_FIELD_NUMBER: _ClassVar[int]
    SYNC_TYPE_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    FLAP_COUNT_FIELD_NUMBER: _ClassVar[int]
    LAST_FLAP_NS_FIELD_NUMBER: _ClassVar[int]
    LAST_PING_PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    pub_key: str
    address: str
    bytes_sent: int
    bytes_recv: int
    sat_sent: int
    sat_recv: int
    inbound: bool
    ping_time: int
    sync_type: Peer.SyncType
    features: _containers.MessageMap[int, Feature]
    errors: _containers.RepeatedCompositeFieldContainer[TimestampedError]
    flap_count: int
    last_flap_ns: int
    last_ping_payload: bytes
    def __init__(self, pub_key: _Optional[str] = ..., address: _Optional[str] = ..., bytes_sent: _Optional[int] = ..., bytes_recv: _Optional[int] = ..., sat_sent: _Optional[int] = ..., sat_recv: _Optional[int] = ..., inbound: bool = ..., ping_time: _Optional[int] = ..., sync_type: _Optional[_Union[Peer.SyncType, str]] = ..., features: _Optional[_Mapping[int, Feature]] = ..., errors: _Optional[_Iterable[_Union[TimestampedError, _Mapping]]] = ..., flap_count: _Optional[int] = ..., last_flap_ns: _Optional[int] = ..., last_ping_payload: _Optional[bytes] = ...) -> None: ...

class TimestampedError(_message.Message):
    __slots__ = ("timestamp", "error")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    timestamp: int
    error: str
    def __init__(self, timestamp: _Optional[int] = ..., error: _Optional[str] = ...) -> None: ...

class ListPeersRequest(_message.Message):
    __slots__ = ("latest_error",)
    LATEST_ERROR_FIELD_NUMBER: _ClassVar[int]
    latest_error: bool
    def __init__(self, latest_error: bool = ...) -> None: ...

class ListPeersResponse(_message.Message):
    __slots__ = ("peers",)
    PEERS_FIELD_NUMBER: _ClassVar[int]
    peers: _containers.RepeatedCompositeFieldContainer[Peer]
    def __init__(self, peers: _Optional[_Iterable[_Union[Peer, _Mapping]]] = ...) -> None: ...

class PeerEventSubscription(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PeerEvent(_message.Message):
    __slots__ = ("pub_key", "type")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PEER_ONLINE: _ClassVar[PeerEvent.EventType]
        PEER_OFFLINE: _ClassVar[PeerEvent.EventType]
    PEER_ONLINE: PeerEvent.EventType
    PEER_OFFLINE: PeerEvent.EventType
    PUB_KEY_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    pub_key: str
    type: PeerEvent.EventType
    def __init__(self, pub_key: _Optional[str] = ..., type: _Optional[_Union[PeerEvent.EventType, str]] = ...) -> None: ...

class GetInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetInfoResponse(_message.Message):
    __slots__ = ("version", "commit_hash", "identity_pubkey", "alias", "color", "num_pending_channels", "num_active_channels", "num_inactive_channels", "num_peers", "block_height", "block_hash", "best_header_timestamp", "synced_to_chain", "synced_to_graph", "testnet", "chains", "uris", "features", "require_htlc_interceptor", "store_final_htlc_resolutions")
    class FeaturesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: Feature
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[Feature, _Mapping]] = ...) -> None: ...
    VERSION_FIELD_NUMBER: _ClassVar[int]
    COMMIT_HASH_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    ALIAS_FIELD_NUMBER: _ClassVar[int]
    COLOR_FIELD_NUMBER: _ClassVar[int]
    NUM_PENDING_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    NUM_ACTIVE_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    NUM_INACTIVE_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    NUM_PEERS_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HASH_FIELD_NUMBER: _ClassVar[int]
    BEST_HEADER_TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SYNCED_TO_CHAIN_FIELD_NUMBER: _ClassVar[int]
    SYNCED_TO_GRAPH_FIELD_NUMBER: _ClassVar[int]
    TESTNET_FIELD_NUMBER: _ClassVar[int]
    CHAINS_FIELD_NUMBER: _ClassVar[int]
    URIS_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    REQUIRE_HTLC_INTERCEPTOR_FIELD_NUMBER: _ClassVar[int]
    STORE_FINAL_HTLC_RESOLUTIONS_FIELD_NUMBER: _ClassVar[int]
    version: str
    commit_hash: str
    identity_pubkey: str
    alias: str
    color: str
    num_pending_channels: int
    num_active_channels: int
    num_inactive_channels: int
    num_peers: int
    block_height: int
    block_hash: str
    best_header_timestamp: int
    synced_to_chain: bool
    synced_to_graph: bool
    testnet: bool
    chains: _containers.RepeatedCompositeFieldContainer[Chain]
    uris: _containers.RepeatedScalarFieldContainer[str]
    features: _containers.MessageMap[int, Feature]
    require_htlc_interceptor: bool
    store_final_htlc_resolutions: bool
    def __init__(self, version: _Optional[str] = ..., commit_hash: _Optional[str] = ..., identity_pubkey: _Optional[str] = ..., alias: _Optional[str] = ..., color: _Optional[str] = ..., num_pending_channels: _Optional[int] = ..., num_active_channels: _Optional[int] = ..., num_inactive_channels: _Optional[int] = ..., num_peers: _Optional[int] = ..., block_height: _Optional[int] = ..., block_hash: _Optional[str] = ..., best_header_timestamp: _Optional[int] = ..., synced_to_chain: bool = ..., synced_to_graph: bool = ..., testnet: bool = ..., chains: _Optional[_Iterable[_Union[Chain, _Mapping]]] = ..., uris: _Optional[_Iterable[str]] = ..., features: _Optional[_Mapping[int, Feature]] = ..., require_htlc_interceptor: bool = ..., store_final_htlc_resolutions: bool = ...) -> None: ...

class GetDebugInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetDebugInfoResponse(_message.Message):
    __slots__ = ("config", "log")
    class ConfigEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    LOG_FIELD_NUMBER: _ClassVar[int]
    config: _containers.ScalarMap[str, str]
    log: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, config: _Optional[_Mapping[str, str]] = ..., log: _Optional[_Iterable[str]] = ...) -> None: ...

class GetRecoveryInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetRecoveryInfoResponse(_message.Message):
    __slots__ = ("recovery_mode", "recovery_finished", "progress")
    RECOVERY_MODE_FIELD_NUMBER: _ClassVar[int]
    RECOVERY_FINISHED_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    recovery_mode: bool
    recovery_finished: bool
    progress: float
    def __init__(self, recovery_mode: bool = ..., recovery_finished: bool = ..., progress: _Optional[float] = ...) -> None: ...

class Chain(_message.Message):
    __slots__ = ("chain", "network")
    CHAIN_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    chain: str
    network: str
    def __init__(self, chain: _Optional[str] = ..., network: _Optional[str] = ...) -> None: ...

class ChannelOpenUpdate(_message.Message):
    __slots__ = ("channel_point",)
    CHANNEL_POINT_FIELD_NUMBER: _ClassVar[int]
    channel_point: ChannelPoint
    def __init__(self, channel_point: _Optional[_Union[ChannelPoint, _Mapping]] = ...) -> None: ...

class CloseOutput(_message.Message):
    __slots__ = ("amount_sat", "pk_script", "is_local", "custom_channel_data")
    AMOUNT_SAT_FIELD_NUMBER: _ClassVar[int]
    PK_SCRIPT_FIELD_NUMBER: _ClassVar[int]
    IS_LOCAL_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_CHANNEL_DATA_FIELD_NUMBER: _ClassVar[int]
    amount_sat: int
    pk_script: bytes
    is_local: bool
    custom_channel_data: bytes
    def __init__(self, amount_sat: _Optional[int] = ..., pk_script: _Optional[bytes] = ..., is_local: bool = ..., custom_channel_data: _Optional[bytes] = ...) -> None: ...

class ChannelCloseUpdate(_message.Message):
    __slots__ = ("closing_txid", "success", "local_close_output", "remote_close_output", "additional_outputs")
    CLOSING_TXID_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    LOCAL_CLOSE_OUTPUT_FIELD_NUMBER: _ClassVar[int]
    REMOTE_CLOSE_OUTPUT_FIELD_NUMBER: _ClassVar[int]
    ADDITIONAL_OUTPUTS_FIELD_NUMBER: _ClassVar[int]
    closing_txid: bytes
    success: bool
    local_close_output: CloseOutput
    remote_close_output: CloseOutput
    additional_outputs: _containers.RepeatedCompositeFieldContainer[CloseOutput]
    def __init__(self, closing_txid: _Optional[bytes] = ..., success: bool = ..., local_close_output: _Optional[_Union[CloseOutput, _Mapping]] = ..., remote_close_output: _Optional[_Union[CloseOutput, _Mapping]] = ..., additional_outputs: _Optional[_Iterable[_Union[CloseOutput, _Mapping]]] = ...) -> None: ...

class CloseChannelRequest(_message.Message):
    __slots__ = ("channel_point", "force", "target_conf", "sat_per_byte", "delivery_address", "sat_per_vbyte", "max_fee_per_vbyte", "no_wait")
    CHANNEL_POINT_FIELD_NUMBER: _ClassVar[int]
    FORCE_FIELD_NUMBER: _ClassVar[int]
    TARGET_CONF_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_BYTE_FIELD_NUMBER: _ClassVar[int]
    DELIVERY_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_VBYTE_FIELD_NUMBER: _ClassVar[int]
    MAX_FEE_PER_VBYTE_FIELD_NUMBER: _ClassVar[int]
    NO_WAIT_FIELD_NUMBER: _ClassVar[int]
    channel_point: ChannelPoint
    force: bool
    target_conf: int
    sat_per_byte: int
    delivery_address: str
    sat_per_vbyte: int
    max_fee_per_vbyte: int
    no_wait: bool
    def __init__(self, channel_point: _Optional[_Union[ChannelPoint, _Mapping]] = ..., force: bool = ..., target_conf: _Optional[int] = ..., sat_per_byte: _Optional[int] = ..., delivery_address: _Optional[str] = ..., sat_per_vbyte: _Optional[int] = ..., max_fee_per_vbyte: _Optional[int] = ..., no_wait: bool = ...) -> None: ...

class CloseStatusUpdate(_message.Message):
    __slots__ = ("close_pending", "chan_close", "close_instant")
    CLOSE_PENDING_FIELD_NUMBER: _ClassVar[int]
    CHAN_CLOSE_FIELD_NUMBER: _ClassVar[int]
    CLOSE_INSTANT_FIELD_NUMBER: _ClassVar[int]
    close_pending: PendingUpdate
    chan_close: ChannelCloseUpdate
    close_instant: InstantUpdate
    def __init__(self, close_pending: _Optional[_Union[PendingUpdate, _Mapping]] = ..., chan_close: _Optional[_Union[ChannelCloseUpdate, _Mapping]] = ..., close_instant: _Optional[_Union[InstantUpdate, _Mapping]] = ...) -> None: ...

class PendingUpdate(_message.Message):
    __slots__ = ("txid", "output_index", "fee_per_vbyte", "local_close_tx")
    TXID_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_INDEX_FIELD_NUMBER: _ClassVar[int]
    FEE_PER_VBYTE_FIELD_NUMBER: _ClassVar[int]
    LOCAL_CLOSE_TX_FIELD_NUMBER: _ClassVar[int]
    txid: bytes
    output_index: int
    fee_per_vbyte: int
    local_close_tx: bool
    def __init__(self, txid: _Optional[bytes] = ..., output_index: _Optional[int] = ..., fee_per_vbyte: _Optional[int] = ..., local_close_tx: bool = ...) -> None: ...

class InstantUpdate(_message.Message):
    __slots__ = ("num_pending_htlcs",)
    NUM_PENDING_HTLCS_FIELD_NUMBER: _ClassVar[int]
    num_pending_htlcs: int
    def __init__(self, num_pending_htlcs: _Optional[int] = ...) -> None: ...

class ReadyForPsbtFunding(_message.Message):
    __slots__ = ("funding_address", "funding_amount", "psbt")
    FUNDING_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    FUNDING_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    PSBT_FIELD_NUMBER: _ClassVar[int]
    funding_address: str
    funding_amount: int
    psbt: bytes
    def __init__(self, funding_address: _Optional[str] = ..., funding_amount: _Optional[int] = ..., psbt: _Optional[bytes] = ...) -> None: ...

class BatchOpenChannelRequest(_message.Message):
    __slots__ = ("channels", "target_conf", "sat_per_vbyte", "min_confs", "spend_unconfirmed", "label", "coin_selection_strategy")
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    TARGET_CONF_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_VBYTE_FIELD_NUMBER: _ClassVar[int]
    MIN_CONFS_FIELD_NUMBER: _ClassVar[int]
    SPEND_UNCONFIRMED_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    COIN_SELECTION_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    channels: _containers.RepeatedCompositeFieldContainer[BatchOpenChannel]
    target_conf: int
    sat_per_vbyte: int
    min_confs: int
    spend_unconfirmed: bool
    label: str
    coin_selection_strategy: CoinSelectionStrategy
    def __init__(self, channels: _Optional[_Iterable[_Union[BatchOpenChannel, _Mapping]]] = ..., target_conf: _Optional[int] = ..., sat_per_vbyte: _Optional[int] = ..., min_confs: _Optional[int] = ..., spend_unconfirmed: bool = ..., label: _Optional[str] = ..., coin_selection_strategy: _Optional[_Union[CoinSelectionStrategy, str]] = ...) -> None: ...

class BatchOpenChannel(_message.Message):
    __slots__ = ("node_pubkey", "local_funding_amount", "push_sat", "private", "min_htlc_msat", "remote_csv_delay", "close_address", "pending_chan_id", "commitment_type", "remote_max_value_in_flight_msat", "remote_max_htlcs", "max_local_csv", "zero_conf", "scid_alias", "base_fee", "fee_rate", "use_base_fee", "use_fee_rate", "remote_chan_reserve_sat", "memo")
    NODE_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    LOCAL_FUNDING_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    PUSH_SAT_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    MIN_HTLC_MSAT_FIELD_NUMBER: _ClassVar[int]
    REMOTE_CSV_DELAY_FIELD_NUMBER: _ClassVar[int]
    CLOSE_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    COMMITMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    REMOTE_MAX_VALUE_IN_FLIGHT_MSAT_FIELD_NUMBER: _ClassVar[int]
    REMOTE_MAX_HTLCS_FIELD_NUMBER: _ClassVar[int]
    MAX_LOCAL_CSV_FIELD_NUMBER: _ClassVar[int]
    ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    SCID_ALIAS_FIELD_NUMBER: _ClassVar[int]
    BASE_FEE_FIELD_NUMBER: _ClassVar[int]
    FEE_RATE_FIELD_NUMBER: _ClassVar[int]
    USE_BASE_FEE_FIELD_NUMBER: _ClassVar[int]
    USE_FEE_RATE_FIELD_NUMBER: _ClassVar[int]
    REMOTE_CHAN_RESERVE_SAT_FIELD_NUMBER: _ClassVar[int]
    MEMO_FIELD_NUMBER: _ClassVar[int]
    node_pubkey: bytes
    local_funding_amount: int
    push_sat: int
    private: bool
    min_htlc_msat: int
    remote_csv_delay: int
    close_address: str
    pending_chan_id: bytes
    commitment_type: CommitmentType
    remote_max_value_in_flight_msat: int
    remote_max_htlcs: int
    max_local_csv: int
    zero_conf: bool
    scid_alias: bool
    base_fee: int
    fee_rate: int
    use_base_fee: bool
    use_fee_rate: bool
    remote_chan_reserve_sat: int
    memo: str
    def __init__(self, node_pubkey: _Optional[bytes] = ..., local_funding_amount: _Optional[int] = ..., push_sat: _Optional[int] = ..., private: bool = ..., min_htlc_msat: _Optional[int] = ..., remote_csv_delay: _Optional[int] = ..., close_address: _Optional[str] = ..., pending_chan_id: _Optional[bytes] = ..., commitment_type: _Optional[_Union[CommitmentType, str]] = ..., remote_max_value_in_flight_msat: _Optional[int] = ..., remote_max_htlcs: _Optional[int] = ..., max_local_csv: _Optional[int] = ..., zero_conf: bool = ..., scid_alias: bool = ..., base_fee: _Optional[int] = ..., fee_rate: _Optional[int] = ..., use_base_fee: bool = ..., use_fee_rate: bool = ..., remote_chan_reserve_sat: _Optional[int] = ..., memo: _Optional[str] = ...) -> None: ...

class BatchOpenChannelResponse(_message.Message):
    __slots__ = ("pending_channels",)
    PENDING_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    pending_channels: _containers.RepeatedCompositeFieldContainer[PendingUpdate]
    def __init__(self, pending_channels: _Optional[_Iterable[_Union[PendingUpdate, _Mapping]]] = ...) -> None: ...

class OpenChannelRequest(_message.Message):
    __slots__ = ("sat_per_vbyte", "node_pubkey", "node_pubkey_string", "local_funding_amount", "push_sat", "target_conf", "sat_per_byte", "private", "min_htlc_msat", "remote_csv_delay", "min_confs", "spend_unconfirmed", "close_address", "funding_shim", "remote_max_value_in_flight_msat", "remote_max_htlcs", "max_local_csv", "commitment_type", "zero_conf", "scid_alias", "base_fee", "fee_rate", "use_base_fee", "use_fee_rate", "remote_chan_reserve_sat", "fund_max", "memo", "outpoints")
    SAT_PER_VBYTE_FIELD_NUMBER: _ClassVar[int]
    NODE_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    NODE_PUBKEY_STRING_FIELD_NUMBER: _ClassVar[int]
    LOCAL_FUNDING_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    PUSH_SAT_FIELD_NUMBER: _ClassVar[int]
    TARGET_CONF_FIELD_NUMBER: _ClassVar[int]
    SAT_PER_BYTE_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    MIN_HTLC_MSAT_FIELD_NUMBER: _ClassVar[int]
    REMOTE_CSV_DELAY_FIELD_NUMBER: _ClassVar[int]
    MIN_CONFS_FIELD_NUMBER: _ClassVar[int]
    SPEND_UNCONFIRMED_FIELD_NUMBER: _ClassVar[int]
    CLOSE_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    FUNDING_SHIM_FIELD_NUMBER: _ClassVar[int]
    REMOTE_MAX_VALUE_IN_FLIGHT_MSAT_FIELD_NUMBER: _ClassVar[int]
    REMOTE_MAX_HTLCS_FIELD_NUMBER: _ClassVar[int]
    MAX_LOCAL_CSV_FIELD_NUMBER: _ClassVar[int]
    COMMITMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    ZERO_CONF_FIELD_NUMBER: _ClassVar[int]
    SCID_ALIAS_FIELD_NUMBER: _ClassVar[int]
    BASE_FEE_FIELD_NUMBER: _ClassVar[int]
    FEE_RATE_FIELD_NUMBER: _ClassVar[int]
    USE_BASE_FEE_FIELD_NUMBER: _ClassVar[int]
    USE_FEE_RATE_FIELD_NUMBER: _ClassVar[int]
    REMOTE_CHAN_RESERVE_SAT_FIELD_NUMBER: _ClassVar[int]
    FUND_MAX_FIELD_NUMBER: _ClassVar[int]
    MEMO_FIELD_NUMBER: _ClassVar[int]
    OUTPOINTS_FIELD_NUMBER: _ClassVar[int]
    sat_per_vbyte: int
    node_pubkey: bytes
    node_pubkey_string: str
    local_funding_amount: int
    push_sat: int
    target_conf: int
    sat_per_byte: int
    private: bool
    min_htlc_msat: int
    remote_csv_delay: int
    min_confs: int
    spend_unconfirmed: bool
    close_address: str
    funding_shim: FundingShim
    remote_max_value_in_flight_msat: int
    remote_max_htlcs: int
    max_local_csv: int
    commitment_type: CommitmentType
    zero_conf: bool
    scid_alias: bool
    base_fee: int
    fee_rate: int
    use_base_fee: bool
    use_fee_rate: bool
    remote_chan_reserve_sat: int
    fund_max: bool
    memo: str
    outpoints: _containers.RepeatedCompositeFieldContainer[OutPoint]
    def __init__(self, sat_per_vbyte: _Optional[int] = ..., node_pubkey: _Optional[bytes] = ..., node_pubkey_string: _Optional[str] = ..., local_funding_amount: _Optional[int] = ..., push_sat: _Optional[int] = ..., target_conf: _Optional[int] = ..., sat_per_byte: _Optional[int] = ..., private: bool = ..., min_htlc_msat: _Optional[int] = ..., remote_csv_delay: _Optional[int] = ..., min_confs: _Optional[int] = ..., spend_unconfirmed: bool = ..., close_address: _Optional[str] = ..., funding_shim: _Optional[_Union[FundingShim, _Mapping]] = ..., remote_max_value_in_flight_msat: _Optional[int] = ..., remote_max_htlcs: _Optional[int] = ..., max_local_csv: _Optional[int] = ..., commitment_type: _Optional[_Union[CommitmentType, str]] = ..., zero_conf: bool = ..., scid_alias: bool = ..., base_fee: _Optional[int] = ..., fee_rate: _Optional[int] = ..., use_base_fee: bool = ..., use_fee_rate: bool = ..., remote_chan_reserve_sat: _Optional[int] = ..., fund_max: bool = ..., memo: _Optional[str] = ..., outpoints: _Optional[_Iterable[_Union[OutPoint, _Mapping]]] = ...) -> None: ...

class OpenStatusUpdate(_message.Message):
    __slots__ = ("chan_pending", "chan_open", "psbt_fund", "pending_chan_id")
    CHAN_PENDING_FIELD_NUMBER: _ClassVar[int]
    CHAN_OPEN_FIELD_NUMBER: _ClassVar[int]
    PSBT_FUND_FIELD_NUMBER: _ClassVar[int]
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    chan_pending: PendingUpdate
    chan_open: ChannelOpenUpdate
    psbt_fund: ReadyForPsbtFunding
    pending_chan_id: bytes
    def __init__(self, chan_pending: _Optional[_Union[PendingUpdate, _Mapping]] = ..., chan_open: _Optional[_Union[ChannelOpenUpdate, _Mapping]] = ..., psbt_fund: _Optional[_Union[ReadyForPsbtFunding, _Mapping]] = ..., pending_chan_id: _Optional[bytes] = ...) -> None: ...

class KeyLocator(_message.Message):
    __slots__ = ("key_family", "key_index")
    KEY_FAMILY_FIELD_NUMBER: _ClassVar[int]
    KEY_INDEX_FIELD_NUMBER: _ClassVar[int]
    key_family: int
    key_index: int
    def __init__(self, key_family: _Optional[int] = ..., key_index: _Optional[int] = ...) -> None: ...

class KeyDescriptor(_message.Message):
    __slots__ = ("raw_key_bytes", "key_loc")
    RAW_KEY_BYTES_FIELD_NUMBER: _ClassVar[int]
    KEY_LOC_FIELD_NUMBER: _ClassVar[int]
    raw_key_bytes: bytes
    key_loc: KeyLocator
    def __init__(self, raw_key_bytes: _Optional[bytes] = ..., key_loc: _Optional[_Union[KeyLocator, _Mapping]] = ...) -> None: ...

class ChanPointShim(_message.Message):
    __slots__ = ("amt", "chan_point", "local_key", "remote_key", "pending_chan_id", "thaw_height", "musig2")
    AMT_FIELD_NUMBER: _ClassVar[int]
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    LOCAL_KEY_FIELD_NUMBER: _ClassVar[int]
    REMOTE_KEY_FIELD_NUMBER: _ClassVar[int]
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    THAW_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    MUSIG2_FIELD_NUMBER: _ClassVar[int]
    amt: int
    chan_point: ChannelPoint
    local_key: KeyDescriptor
    remote_key: bytes
    pending_chan_id: bytes
    thaw_height: int
    musig2: bool
    def __init__(self, amt: _Optional[int] = ..., chan_point: _Optional[_Union[ChannelPoint, _Mapping]] = ..., local_key: _Optional[_Union[KeyDescriptor, _Mapping]] = ..., remote_key: _Optional[bytes] = ..., pending_chan_id: _Optional[bytes] = ..., thaw_height: _Optional[int] = ..., musig2: bool = ...) -> None: ...

class PsbtShim(_message.Message):
    __slots__ = ("pending_chan_id", "base_psbt", "no_publish")
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    BASE_PSBT_FIELD_NUMBER: _ClassVar[int]
    NO_PUBLISH_FIELD_NUMBER: _ClassVar[int]
    pending_chan_id: bytes
    base_psbt: bytes
    no_publish: bool
    def __init__(self, pending_chan_id: _Optional[bytes] = ..., base_psbt: _Optional[bytes] = ..., no_publish: bool = ...) -> None: ...

class FundingShim(_message.Message):
    __slots__ = ("chan_point_shim", "psbt_shim")
    CHAN_POINT_SHIM_FIELD_NUMBER: _ClassVar[int]
    PSBT_SHIM_FIELD_NUMBER: _ClassVar[int]
    chan_point_shim: ChanPointShim
    psbt_shim: PsbtShim
    def __init__(self, chan_point_shim: _Optional[_Union[ChanPointShim, _Mapping]] = ..., psbt_shim: _Optional[_Union[PsbtShim, _Mapping]] = ...) -> None: ...

class FundingShimCancel(_message.Message):
    __slots__ = ("pending_chan_id",)
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    pending_chan_id: bytes
    def __init__(self, pending_chan_id: _Optional[bytes] = ...) -> None: ...

class FundingPsbtVerify(_message.Message):
    __slots__ = ("funded_psbt", "pending_chan_id", "skip_finalize")
    FUNDED_PSBT_FIELD_NUMBER: _ClassVar[int]
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    SKIP_FINALIZE_FIELD_NUMBER: _ClassVar[int]
    funded_psbt: bytes
    pending_chan_id: bytes
    skip_finalize: bool
    def __init__(self, funded_psbt: _Optional[bytes] = ..., pending_chan_id: _Optional[bytes] = ..., skip_finalize: bool = ...) -> None: ...

class FundingPsbtFinalize(_message.Message):
    __slots__ = ("signed_psbt", "pending_chan_id", "final_raw_tx")
    SIGNED_PSBT_FIELD_NUMBER: _ClassVar[int]
    PENDING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    FINAL_RAW_TX_FIELD_NUMBER: _ClassVar[int]
    signed_psbt: bytes
    pending_chan_id: bytes
    final_raw_tx: bytes
    def __init__(self, signed_psbt: _Optional[bytes] = ..., pending_chan_id: _Optional[bytes] = ..., final_raw_tx: _Optional[bytes] = ...) -> None: ...

class FundingTransitionMsg(_message.Message):
    __slots__ = ("shim_register", "shim_cancel", "psbt_verify", "psbt_finalize")
    SHIM_REGISTER_FIELD_NUMBER: _ClassVar[int]
    SHIM_CANCEL_FIELD_NUMBER: _ClassVar[int]
    PSBT_VERIFY_FIELD_NUMBER: _ClassVar[int]
    PSBT_FINALIZE_FIELD_NUMBER: _ClassVar[int]
    shim_register: FundingShim
    shim_cancel: FundingShimCancel
    psbt_verify: FundingPsbtVerify
    psbt_finalize: FundingPsbtFinalize
    def __init__(self, shim_register: _Optional[_Union[FundingShim, _Mapping]] = ..., shim_cancel: _Optional[_Union[FundingShimCancel, _Mapping]] = ..., psbt_verify: _Optional[_Union[FundingPsbtVerify, _Mapping]] = ..., psbt_finalize: _Optional[_Union[FundingPsbtFinalize, _Mapping]] = ...) -> None: ...

class FundingStateStepResp(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PendingHTLC(_message.Message):
    __slots__ = ("incoming", "amount", "outpoint", "maturity_height", "blocks_til_maturity", "stage")
    INCOMING_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    OUTPOINT_FIELD_NUMBER: _ClassVar[int]
    MATURITY_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    BLOCKS_TIL_MATURITY_FIELD_NUMBER: _ClassVar[int]
    STAGE_FIELD_NUMBER: _ClassVar[int]
    incoming: bool
    amount: int
    outpoint: str
    maturity_height: int
    blocks_til_maturity: int
    stage: int
    def __init__(self, incoming: bool = ..., amount: _Optional[int] = ..., outpoint: _Optional[str] = ..., maturity_height: _Optional[int] = ..., blocks_til_maturity: _Optional[int] = ..., stage: _Optional[int] = ...) -> None: ...

class PendingChannelsRequest(_message.Message):
    __slots__ = ("include_raw_tx",)
    INCLUDE_RAW_TX_FIELD_NUMBER: _ClassVar[int]
    include_raw_tx: bool
    def __init__(self, include_raw_tx: bool = ...) -> None: ...

class PendingChannelsResponse(_message.Message):
    __slots__ = ("total_limbo_balance", "pending_open_channels", "pending_closing_channels", "pending_force_closing_channels", "waiting_close_channels")
    class PendingChannel(_message.Message):
        __slots__ = ("remote_node_pub", "channel_point", "capacity", "local_balance", "remote_balance", "local_chan_reserve_sat", "remote_chan_reserve_sat", "initiator", "commitment_type", "num_forwarding_packages", "chan_status_flags", "private", "memo", "custom_channel_data")
        REMOTE_NODE_PUB_FIELD_NUMBER: _ClassVar[int]
        CHANNEL_POINT_FIELD_NUMBER: _ClassVar[int]
        CAPACITY_FIELD_NUMBER: _ClassVar[int]
        LOCAL_BALANCE_FIELD_NUMBER: _ClassVar[int]
        REMOTE_BALANCE_FIELD_NUMBER: _ClassVar[int]
        LOCAL_CHAN_RESERVE_SAT_FIELD_NUMBER: _ClassVar[int]
        REMOTE_CHAN_RESERVE_SAT_FIELD_NUMBER: _ClassVar[int]
        INITIATOR_FIELD_NUMBER: _ClassVar[int]
        COMMITMENT_TYPE_FIELD_NUMBER: _ClassVar[int]
        NUM_FORWARDING_PACKAGES_FIELD_NUMBER: _ClassVar[int]
        CHAN_STATUS_FLAGS_FIELD_NUMBER: _ClassVar[int]
        PRIVATE_FIELD_NUMBER: _ClassVar[int]
        MEMO_FIELD_NUMBER: _ClassVar[int]
        CUSTOM_CHANNEL_DATA_FIELD_NUMBER: _ClassVar[int]
        remote_node_pub: str
        channel_point: str
        capacity: int
        local_balance: int
        remote_balance: int
        local_chan_reserve_sat: int
        remote_chan_reserve_sat: int
        initiator: Initiator
        commitment_type: CommitmentType
        num_forwarding_packages: int
        chan_status_flags: str
        private: bool
        memo: str
        custom_channel_data: bytes
        def __init__(self, remote_node_pub: _Optional[str] = ..., channel_point: _Optional[str] = ..., capacity: _Optional[int] = ..., local_balance: _Optional[int] = ..., remote_balance: _Optional[int] = ..., local_chan_reserve_sat: _Optional[int] = ..., remote_chan_reserve_sat: _Optional[int] = ..., initiator: _Optional[_Union[Initiator, str]] = ..., commitment_type: _Optional[_Union[CommitmentType, str]] = ..., num_forwarding_packages: _Optional[int] = ..., chan_status_flags: _Optional[str] = ..., private: bool = ..., memo: _Optional[str] = ..., custom_channel_data: _Optional[bytes] = ...) -> None: ...
    class PendingOpenChannel(_message.Message):
        __slots__ = ("channel", "commit_fee", "commit_weight", "fee_per_kw", "funding_expiry_blocks", "confirmations_until_active", "confirmation_height")
        CHANNEL_FIELD_NUMBER: _ClassVar[int]
        COMMIT_FEE_FIELD_NUMBER: _ClassVar[int]
        COMMIT_WEIGHT_FIELD_NUMBER: _ClassVar[int]
        FEE_PER_KW_FIELD_NUMBER: _ClassVar[int]
        FUNDING_EXPIRY_BLOCKS_FIELD_NUMBER: _ClassVar[int]
        CONFIRMATIONS_UNTIL_ACTIVE_FIELD_NUMBER: _ClassVar[int]
        CONFIRMATION_HEIGHT_FIELD_NUMBER: _ClassVar[int]
        channel: PendingChannelsResponse.PendingChannel
        commit_fee: int
        commit_weight: int
        fee_per_kw: int
        funding_expiry_blocks: int
        confirmations_until_active: int
        confirmation_height: int
        def __init__(self, channel: _Optional[_Union[PendingChannelsResponse.PendingChannel, _Mapping]] = ..., commit_fee: _Optional[int] = ..., commit_weight: _Optional[int] = ..., fee_per_kw: _Optional[int] = ..., funding_expiry_blocks: _Optional[int] = ..., confirmations_until_active: _Optional[int] = ..., confirmation_height: _Optional[int] = ...) -> None: ...
    class WaitingCloseChannel(_message.Message):
        __slots__ = ("channel", "limbo_balance", "commitments", "closing_txid", "closing_tx_hex")
        CHANNEL_FIELD_NUMBER: _ClassVar[int]
        LIMBO_BALANCE_FIELD_NUMBER: _ClassVar[int]
        COMMITMENTS_FIELD_NUMBER: _ClassVar[int]
        CLOSING_TXID_FIELD_NUMBER: _ClassVar[int]
        CLOSING_TX_HEX_FIELD_NUMBER: _ClassVar[int]
        channel: PendingChannelsResponse.PendingChannel
        limbo_balance: int
        commitments: PendingChannelsResponse.Commitments
        closing_txid: str
        closing_tx_hex: str
        def __init__(self, channel: _Optional[_Union[PendingChannelsResponse.PendingChannel, _Mapping]] = ..., limbo_balance: _Optional[int] = ..., commitments: _Optional[_Union[PendingChannelsResponse.Commitments, _Mapping]] = ..., closing_txid: _Optional[str] = ..., closing_tx_hex: _Optional[str] = ...) -> None: ...
    class Commitments(_message.Message):
        __slots__ = ("local_txid", "remote_txid", "remote_pending_txid", "local_commit_fee_sat", "remote_commit_fee_sat", "remote_pending_commit_fee_sat")
        LOCAL_TXID_FIELD_NUMBER: _ClassVar[int]
        REMOTE_TXID_FIELD_NUMBER: _ClassVar[int]
        REMOTE_PENDING_TXID_FIELD_NUMBER: _ClassVar[int]
        LOCAL_COMMIT_FEE_SAT_FIELD_NUMBER: _ClassVar[int]
        REMOTE_COMMIT_FEE_SAT_FIELD_NUMBER: _ClassVar[int]
        REMOTE_PENDING_COMMIT_FEE_SAT_FIELD_NUMBER: _ClassVar[int]
        local_txid: str
        remote_txid: str
        remote_pending_txid: str
        local_commit_fee_sat: int
        remote_commit_fee_sat: int
        remote_pending_commit_fee_sat: int
        def __init__(self, local_txid: _Optional[str] = ..., remote_txid: _Optional[str] = ..., remote_pending_txid: _Optional[str] = ..., local_commit_fee_sat: _Optional[int] = ..., remote_commit_fee_sat: _Optional[int] = ..., remote_pending_commit_fee_sat: _Optional[int] = ...) -> None: ...
    class ClosedChannel(_message.Message):
        __slots__ = ("channel", "closing_txid")
        CHANNEL_FIELD_NUMBER: _ClassVar[int]
        CLOSING_TXID_FIELD_NUMBER: _ClassVar[int]
        channel: PendingChannelsResponse.PendingChannel
        closing_txid: str
        def __init__(self, channel: _Optional[_Union[PendingChannelsResponse.PendingChannel, _Mapping]] = ..., closing_txid: _Optional[str] = ...) -> None: ...
    class ForceClosedChannel(_message.Message):
        __slots__ = ("channel", "closing_txid", "limbo_balance", "maturity_height", "blocks_til_maturity", "recovered_balance", "pending_htlcs", "anchor")
        class AnchorState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = ()
            LIMBO: _ClassVar[PendingChannelsResponse.ForceClosedChannel.AnchorState]
            RECOVERED: _ClassVar[PendingChannelsResponse.ForceClosedChannel.AnchorState]
            LOST: _ClassVar[PendingChannelsResponse.ForceClosedChannel.AnchorState]
        LIMBO: PendingChannelsResponse.ForceClosedChannel.AnchorState
        RECOVERED: PendingChannelsResponse.ForceClosedChannel.AnchorState
        LOST: PendingChannelsResponse.ForceClosedChannel.AnchorState
        CHANNEL_FIELD_NUMBER: _ClassVar[int]
        CLOSING_TXID_FIELD_NUMBER: _ClassVar[int]
        LIMBO_BALANCE_FIELD_NUMBER: _ClassVar[int]
        MATURITY_HEIGHT_FIELD_NUMBER: _ClassVar[int]
        BLOCKS_TIL_MATURITY_FIELD_NUMBER: _ClassVar[int]
        RECOVERED_BALANCE_FIELD_NUMBER: _ClassVar[int]
        PENDING_HTLCS_FIELD_NUMBER: _ClassVar[int]
        ANCHOR_FIELD_NUMBER: _ClassVar[int]
        channel: PendingChannelsResponse.PendingChannel
        closing_txid: str
        limbo_balance: int
        maturity_height: int
        blocks_til_maturity: int
        recovered_balance: int
        pending_htlcs: _containers.RepeatedCompositeFieldContainer[PendingHTLC]
        anchor: PendingChannelsResponse.ForceClosedChannel.AnchorState
        def __init__(self, channel: _Optional[_Union[PendingChannelsResponse.PendingChannel, _Mapping]] = ..., closing_txid: _Optional[str] = ..., limbo_balance: _Optional[int] = ..., maturity_height: _Optional[int] = ..., blocks_til_maturity: _Optional[int] = ..., recovered_balance: _Optional[int] = ..., pending_htlcs: _Optional[_Iterable[_Union[PendingHTLC, _Mapping]]] = ..., anchor: _Optional[_Union[PendingChannelsResponse.ForceClosedChannel.AnchorState, str]] = ...) -> None: ...
    TOTAL_LIMBO_BALANCE_FIELD_NUMBER: _ClassVar[int]
    PENDING_OPEN_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    PENDING_CLOSING_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    PENDING_FORCE_CLOSING_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    WAITING_CLOSE_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    total_limbo_balance: int
    pending_open_channels: _containers.RepeatedCompositeFieldContainer[PendingChannelsResponse.PendingOpenChannel]
    pending_closing_channels: _containers.RepeatedCompositeFieldContainer[PendingChannelsResponse.ClosedChannel]
    pending_force_closing_channels: _containers.RepeatedCompositeFieldContainer[PendingChannelsResponse.ForceClosedChannel]
    waiting_close_channels: _containers.RepeatedCompositeFieldContainer[PendingChannelsResponse.WaitingCloseChannel]
    def __init__(self, total_limbo_balance: _Optional[int] = ..., pending_open_channels: _Optional[_Iterable[_Union[PendingChannelsResponse.PendingOpenChannel, _Mapping]]] = ..., pending_closing_channels: _Optional[_Iterable[_Union[PendingChannelsResponse.ClosedChannel, _Mapping]]] = ..., pending_force_closing_channels: _Optional[_Iterable[_Union[PendingChannelsResponse.ForceClosedChannel, _Mapping]]] = ..., waiting_close_channels: _Optional[_Iterable[_Union[PendingChannelsResponse.WaitingCloseChannel, _Mapping]]] = ...) -> None: ...

class ChannelEventSubscription(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ChannelEventUpdate(_message.Message):
    __slots__ = ("open_channel", "closed_channel", "active_channel", "inactive_channel", "pending_open_channel", "fully_resolved_channel", "channel_funding_timeout", "type")
    class UpdateType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        OPEN_CHANNEL: _ClassVar[ChannelEventUpdate.UpdateType]
        CLOSED_CHANNEL: _ClassVar[ChannelEventUpdate.UpdateType]
        ACTIVE_CHANNEL: _ClassVar[ChannelEventUpdate.UpdateType]
        INACTIVE_CHANNEL: _ClassVar[ChannelEventUpdate.UpdateType]
        PENDING_OPEN_CHANNEL: _ClassVar[ChannelEventUpdate.UpdateType]
        FULLY_RESOLVED_CHANNEL: _ClassVar[ChannelEventUpdate.UpdateType]
        CHANNEL_FUNDING_TIMEOUT: _ClassVar[ChannelEventUpdate.UpdateType]
    OPEN_CHANNEL: ChannelEventUpdate.UpdateType
    CLOSED_CHANNEL: ChannelEventUpdate.UpdateType
    ACTIVE_CHANNEL: ChannelEventUpdate.UpdateType
    INACTIVE_CHANNEL: ChannelEventUpdate.UpdateType
    PENDING_OPEN_CHANNEL: ChannelEventUpdate.UpdateType
    FULLY_RESOLVED_CHANNEL: ChannelEventUpdate.UpdateType
    CHANNEL_FUNDING_TIMEOUT: ChannelEventUpdate.UpdateType
    OPEN_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    CLOSED_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    INACTIVE_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    PENDING_OPEN_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    FULLY_RESOLVED_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FUNDING_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    open_channel: Channel
    closed_channel: ChannelCloseSummary
    active_channel: ChannelPoint
    inactive_channel: ChannelPoint
    pending_open_channel: PendingUpdate
    fully_resolved_channel: ChannelPoint
    channel_funding_timeout: ChannelPoint
    type: ChannelEventUpdate.UpdateType
    def __init__(self, open_channel: _Optional[_Union[Channel, _Mapping]] = ..., closed_channel: _Optional[_Union[ChannelCloseSummary, _Mapping]] = ..., active_channel: _Optional[_Union[ChannelPoint, _Mapping]] = ..., inactive_channel: _Optional[_Union[ChannelPoint, _Mapping]] = ..., pending_open_channel: _Optional[_Union[PendingUpdate, _Mapping]] = ..., fully_resolved_channel: _Optional[_Union[ChannelPoint, _Mapping]] = ..., channel_funding_timeout: _Optional[_Union[ChannelPoint, _Mapping]] = ..., type: _Optional[_Union[ChannelEventUpdate.UpdateType, str]] = ...) -> None: ...

class WalletAccountBalance(_message.Message):
    __slots__ = ("confirmed_balance", "unconfirmed_balance")
    CONFIRMED_BALANCE_FIELD_NUMBER: _ClassVar[int]
    UNCONFIRMED_BALANCE_FIELD_NUMBER: _ClassVar[int]
    confirmed_balance: int
    unconfirmed_balance: int
    def __init__(self, confirmed_balance: _Optional[int] = ..., unconfirmed_balance: _Optional[int] = ...) -> None: ...

class WalletBalanceRequest(_message.Message):
    __slots__ = ("account", "min_confs")
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    MIN_CONFS_FIELD_NUMBER: _ClassVar[int]
    account: str
    min_confs: int
    def __init__(self, account: _Optional[str] = ..., min_confs: _Optional[int] = ...) -> None: ...

class WalletBalanceResponse(_message.Message):
    __slots__ = ("total_balance", "confirmed_balance", "unconfirmed_balance", "locked_balance", "reserved_balance_anchor_chan", "account_balance")
    class AccountBalanceEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: WalletAccountBalance
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[WalletAccountBalance, _Mapping]] = ...) -> None: ...
    TOTAL_BALANCE_FIELD_NUMBER: _ClassVar[int]
    CONFIRMED_BALANCE_FIELD_NUMBER: _ClassVar[int]
    UNCONFIRMED_BALANCE_FIELD_NUMBER: _ClassVar[int]
    LOCKED_BALANCE_FIELD_NUMBER: _ClassVar[int]
    RESERVED_BALANCE_ANCHOR_CHAN_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_BALANCE_FIELD_NUMBER: _ClassVar[int]
    total_balance: int
    confirmed_balance: int
    unconfirmed_balance: int
    locked_balance: int
    reserved_balance_anchor_chan: int
    account_balance: _containers.MessageMap[str, WalletAccountBalance]
    def __init__(self, total_balance: _Optional[int] = ..., confirmed_balance: _Optional[int] = ..., unconfirmed_balance: _Optional[int] = ..., locked_balance: _Optional[int] = ..., reserved_balance_anchor_chan: _Optional[int] = ..., account_balance: _Optional[_Mapping[str, WalletAccountBalance]] = ...) -> None: ...

class Amount(_message.Message):
    __slots__ = ("sat", "msat")
    SAT_FIELD_NUMBER: _ClassVar[int]
    MSAT_FIELD_NUMBER: _ClassVar[int]
    sat: int
    msat: int
    def __init__(self, sat: _Optional[int] = ..., msat: _Optional[int] = ...) -> None: ...

class ChannelBalanceRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ChannelBalanceResponse(_message.Message):
    __slots__ = ("balance", "pending_open_balance", "local_balance", "remote_balance", "unsettled_local_balance", "unsettled_remote_balance", "pending_open_local_balance", "pending_open_remote_balance", "custom_channel_data")
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    PENDING_OPEN_BALANCE_FIELD_NUMBER: _ClassVar[int]
    LOCAL_BALANCE_FIELD_NUMBER: _ClassVar[int]
    REMOTE_BALANCE_FIELD_NUMBER: _ClassVar[int]
    UNSETTLED_LOCAL_BALANCE_FIELD_NUMBER: _ClassVar[int]
    UNSETTLED_REMOTE_BALANCE_FIELD_NUMBER: _ClassVar[int]
    PENDING_OPEN_LOCAL_BALANCE_FIELD_NUMBER: _ClassVar[int]
    PENDING_OPEN_REMOTE_BALANCE_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_CHANNEL_DATA_FIELD_NUMBER: _ClassVar[int]
    balance: int
    pending_open_balance: int
    local_balance: Amount
    remote_balance: Amount
    unsettled_local_balance: Amount
    unsettled_remote_balance: Amount
    pending_open_local_balance: Amount
    pending_open_remote_balance: Amount
    custom_channel_data: bytes
    def __init__(self, balance: _Optional[int] = ..., pending_open_balance: _Optional[int] = ..., local_balance: _Optional[_Union[Amount, _Mapping]] = ..., remote_balance: _Optional[_Union[Amount, _Mapping]] = ..., unsettled_local_balance: _Optional[_Union[Amount, _Mapping]] = ..., unsettled_remote_balance: _Optional[_Union[Amount, _Mapping]] = ..., pending_open_local_balance: _Optional[_Union[Amount, _Mapping]] = ..., pending_open_remote_balance: _Optional[_Union[Amount, _Mapping]] = ..., custom_channel_data: _Optional[bytes] = ...) -> None: ...

class QueryRoutesRequest(_message.Message):
    __slots__ = ("pub_key", "amt", "amt_msat", "final_cltv_delta", "fee_limit", "ignored_nodes", "ignored_edges", "source_pub_key", "use_mission_control", "ignored_pairs", "cltv_limit", "dest_custom_records", "outgoing_chan_id", "last_hop_pubkey", "route_hints", "blinded_payment_paths", "dest_features", "time_pref", "outgoing_chan_ids")
    class DestCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    PUB_KEY_FIELD_NUMBER: _ClassVar[int]
    AMT_FIELD_NUMBER: _ClassVar[int]
    AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    FINAL_CLTV_DELTA_FIELD_NUMBER: _ClassVar[int]
    FEE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    IGNORED_NODES_FIELD_NUMBER: _ClassVar[int]
    IGNORED_EDGES_FIELD_NUMBER: _ClassVar[int]
    SOURCE_PUB_KEY_FIELD_NUMBER: _ClassVar[int]
    USE_MISSION_CONTROL_FIELD_NUMBER: _ClassVar[int]
    IGNORED_PAIRS_FIELD_NUMBER: _ClassVar[int]
    CLTV_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DEST_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    LAST_HOP_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    ROUTE_HINTS_FIELD_NUMBER: _ClassVar[int]
    BLINDED_PAYMENT_PATHS_FIELD_NUMBER: _ClassVar[int]
    DEST_FEATURES_FIELD_NUMBER: _ClassVar[int]
    TIME_PREF_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_CHAN_IDS_FIELD_NUMBER: _ClassVar[int]
    pub_key: str
    amt: int
    amt_msat: int
    final_cltv_delta: int
    fee_limit: FeeLimit
    ignored_nodes: _containers.RepeatedScalarFieldContainer[bytes]
    ignored_edges: _containers.RepeatedCompositeFieldContainer[EdgeLocator]
    source_pub_key: str
    use_mission_control: bool
    ignored_pairs: _containers.RepeatedCompositeFieldContainer[NodePair]
    cltv_limit: int
    dest_custom_records: _containers.ScalarMap[int, bytes]
    outgoing_chan_id: int
    last_hop_pubkey: bytes
    route_hints: _containers.RepeatedCompositeFieldContainer[RouteHint]
    blinded_payment_paths: _containers.RepeatedCompositeFieldContainer[BlindedPaymentPath]
    dest_features: _containers.RepeatedScalarFieldContainer[FeatureBit]
    time_pref: float
    outgoing_chan_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, pub_key: _Optional[str] = ..., amt: _Optional[int] = ..., amt_msat: _Optional[int] = ..., final_cltv_delta: _Optional[int] = ..., fee_limit: _Optional[_Union[FeeLimit, _Mapping]] = ..., ignored_nodes: _Optional[_Iterable[bytes]] = ..., ignored_edges: _Optional[_Iterable[_Union[EdgeLocator, _Mapping]]] = ..., source_pub_key: _Optional[str] = ..., use_mission_control: bool = ..., ignored_pairs: _Optional[_Iterable[_Union[NodePair, _Mapping]]] = ..., cltv_limit: _Optional[int] = ..., dest_custom_records: _Optional[_Mapping[int, bytes]] = ..., outgoing_chan_id: _Optional[int] = ..., last_hop_pubkey: _Optional[bytes] = ..., route_hints: _Optional[_Iterable[_Union[RouteHint, _Mapping]]] = ..., blinded_payment_paths: _Optional[_Iterable[_Union[BlindedPaymentPath, _Mapping]]] = ..., dest_features: _Optional[_Iterable[_Union[FeatureBit, str]]] = ..., time_pref: _Optional[float] = ..., outgoing_chan_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class NodePair(_message.Message):
    __slots__ = ("to",)
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    to: bytes
    def __init__(self, to: _Optional[bytes] = ..., **kwargs) -> None: ...

class EdgeLocator(_message.Message):
    __slots__ = ("channel_id", "direction_reverse")
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_REVERSE_FIELD_NUMBER: _ClassVar[int]
    channel_id: int
    direction_reverse: bool
    def __init__(self, channel_id: _Optional[int] = ..., direction_reverse: bool = ...) -> None: ...

class QueryRoutesResponse(_message.Message):
    __slots__ = ("routes", "success_prob")
    ROUTES_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_PROB_FIELD_NUMBER: _ClassVar[int]
    routes: _containers.RepeatedCompositeFieldContainer[Route]
    success_prob: float
    def __init__(self, routes: _Optional[_Iterable[_Union[Route, _Mapping]]] = ..., success_prob: _Optional[float] = ...) -> None: ...

class Hop(_message.Message):
    __slots__ = ("chan_id", "chan_capacity", "amt_to_forward", "fee", "expiry", "amt_to_forward_msat", "fee_msat", "pub_key", "tlv_payload", "mpp_record", "amp_record", "custom_records", "metadata", "blinding_point", "encrypted_data", "total_amt_msat")
    class CustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    CHAN_CAPACITY_FIELD_NUMBER: _ClassVar[int]
    AMT_TO_FORWARD_FIELD_NUMBER: _ClassVar[int]
    FEE_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_FIELD_NUMBER: _ClassVar[int]
    AMT_TO_FORWARD_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    PUB_KEY_FIELD_NUMBER: _ClassVar[int]
    TLV_PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    MPP_RECORD_FIELD_NUMBER: _ClassVar[int]
    AMP_RECORD_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    BLINDING_POINT_FIELD_NUMBER: _ClassVar[int]
    ENCRYPTED_DATA_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    chan_capacity: int
    amt_to_forward: int
    fee: int
    expiry: int
    amt_to_forward_msat: int
    fee_msat: int
    pub_key: str
    tlv_payload: bool
    mpp_record: MPPRecord
    amp_record: AMPRecord
    custom_records: _containers.ScalarMap[int, bytes]
    metadata: bytes
    blinding_point: bytes
    encrypted_data: bytes
    total_amt_msat: int
    def __init__(self, chan_id: _Optional[int] = ..., chan_capacity: _Optional[int] = ..., amt_to_forward: _Optional[int] = ..., fee: _Optional[int] = ..., expiry: _Optional[int] = ..., amt_to_forward_msat: _Optional[int] = ..., fee_msat: _Optional[int] = ..., pub_key: _Optional[str] = ..., tlv_payload: bool = ..., mpp_record: _Optional[_Union[MPPRecord, _Mapping]] = ..., amp_record: _Optional[_Union[AMPRecord, _Mapping]] = ..., custom_records: _Optional[_Mapping[int, bytes]] = ..., metadata: _Optional[bytes] = ..., blinding_point: _Optional[bytes] = ..., encrypted_data: _Optional[bytes] = ..., total_amt_msat: _Optional[int] = ...) -> None: ...

class MPPRecord(_message.Message):
    __slots__ = ("payment_addr", "total_amt_msat")
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    payment_addr: bytes
    total_amt_msat: int
    def __init__(self, payment_addr: _Optional[bytes] = ..., total_amt_msat: _Optional[int] = ...) -> None: ...

class AMPRecord(_message.Message):
    __slots__ = ("root_share", "set_id", "child_index")
    ROOT_SHARE_FIELD_NUMBER: _ClassVar[int]
    SET_ID_FIELD_NUMBER: _ClassVar[int]
    CHILD_INDEX_FIELD_NUMBER: _ClassVar[int]
    root_share: bytes
    set_id: bytes
    child_index: int
    def __init__(self, root_share: _Optional[bytes] = ..., set_id: _Optional[bytes] = ..., child_index: _Optional[int] = ...) -> None: ...

class Route(_message.Message):
    __slots__ = ("total_time_lock", "total_fees", "total_amt", "hops", "total_fees_msat", "total_amt_msat", "first_hop_amount_msat", "custom_channel_data")
    TOTAL_TIME_LOCK_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FEES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMT_FIELD_NUMBER: _ClassVar[int]
    HOPS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FEES_MSAT_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    FIRST_HOP_AMOUNT_MSAT_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_CHANNEL_DATA_FIELD_NUMBER: _ClassVar[int]
    total_time_lock: int
    total_fees: int
    total_amt: int
    hops: _containers.RepeatedCompositeFieldContainer[Hop]
    total_fees_msat: int
    total_amt_msat: int
    first_hop_amount_msat: int
    custom_channel_data: bytes
    def __init__(self, total_time_lock: _Optional[int] = ..., total_fees: _Optional[int] = ..., total_amt: _Optional[int] = ..., hops: _Optional[_Iterable[_Union[Hop, _Mapping]]] = ..., total_fees_msat: _Optional[int] = ..., total_amt_msat: _Optional[int] = ..., first_hop_amount_msat: _Optional[int] = ..., custom_channel_data: _Optional[bytes] = ...) -> None: ...

class NodeInfoRequest(_message.Message):
    __slots__ = ("pub_key", "include_channels", "include_auth_proof")
    PUB_KEY_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_AUTH_PROOF_FIELD_NUMBER: _ClassVar[int]
    pub_key: str
    include_channels: bool
    include_auth_proof: bool
    def __init__(self, pub_key: _Optional[str] = ..., include_channels: bool = ..., include_auth_proof: bool = ...) -> None: ...

class NodeInfo(_message.Message):
    __slots__ = ("node", "num_channels", "total_capacity", "channels")
    NODE_FIELD_NUMBER: _ClassVar[int]
    NUM_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_CAPACITY_FIELD_NUMBER: _ClassVar[int]
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    node: LightningNode
    num_channels: int
    total_capacity: int
    channels: _containers.RepeatedCompositeFieldContainer[ChannelEdge]
    def __init__(self, node: _Optional[_Union[LightningNode, _Mapping]] = ..., num_channels: _Optional[int] = ..., total_capacity: _Optional[int] = ..., channels: _Optional[_Iterable[_Union[ChannelEdge, _Mapping]]] = ...) -> None: ...

class LightningNode(_message.Message):
    __slots__ = ("last_update", "pub_key", "alias", "addresses", "color", "features", "custom_records")
    class FeaturesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: Feature
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[Feature, _Mapping]] = ...) -> None: ...
    class CustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    LAST_UPDATE_FIELD_NUMBER: _ClassVar[int]
    PUB_KEY_FIELD_NUMBER: _ClassVar[int]
    ALIAS_FIELD_NUMBER: _ClassVar[int]
    ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    COLOR_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    last_update: int
    pub_key: str
    alias: str
    addresses: _containers.RepeatedCompositeFieldContainer[NodeAddress]
    color: str
    features: _containers.MessageMap[int, Feature]
    custom_records: _containers.ScalarMap[int, bytes]
    def __init__(self, last_update: _Optional[int] = ..., pub_key: _Optional[str] = ..., alias: _Optional[str] = ..., addresses: _Optional[_Iterable[_Union[NodeAddress, _Mapping]]] = ..., color: _Optional[str] = ..., features: _Optional[_Mapping[int, Feature]] = ..., custom_records: _Optional[_Mapping[int, bytes]] = ...) -> None: ...

class NodeAddress(_message.Message):
    __slots__ = ("network", "addr")
    NETWORK_FIELD_NUMBER: _ClassVar[int]
    ADDR_FIELD_NUMBER: _ClassVar[int]
    network: str
    addr: str
    def __init__(self, network: _Optional[str] = ..., addr: _Optional[str] = ...) -> None: ...

class RoutingPolicy(_message.Message):
    __slots__ = ("time_lock_delta", "min_htlc", "fee_base_msat", "fee_rate_milli_msat", "disabled", "max_htlc_msat", "last_update", "custom_records", "inbound_fee_base_msat", "inbound_fee_rate_milli_msat")
    class CustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    TIME_LOCK_DELTA_FIELD_NUMBER: _ClassVar[int]
    MIN_HTLC_FIELD_NUMBER: _ClassVar[int]
    FEE_BASE_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEE_RATE_MILLI_MSAT_FIELD_NUMBER: _ClassVar[int]
    DISABLED_FIELD_NUMBER: _ClassVar[int]
    MAX_HTLC_MSAT_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATE_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    INBOUND_FEE_BASE_MSAT_FIELD_NUMBER: _ClassVar[int]
    INBOUND_FEE_RATE_MILLI_MSAT_FIELD_NUMBER: _ClassVar[int]
    time_lock_delta: int
    min_htlc: int
    fee_base_msat: int
    fee_rate_milli_msat: int
    disabled: bool
    max_htlc_msat: int
    last_update: int
    custom_records: _containers.ScalarMap[int, bytes]
    inbound_fee_base_msat: int
    inbound_fee_rate_milli_msat: int
    def __init__(self, time_lock_delta: _Optional[int] = ..., min_htlc: _Optional[int] = ..., fee_base_msat: _Optional[int] = ..., fee_rate_milli_msat: _Optional[int] = ..., disabled: bool = ..., max_htlc_msat: _Optional[int] = ..., last_update: _Optional[int] = ..., custom_records: _Optional[_Mapping[int, bytes]] = ..., inbound_fee_base_msat: _Optional[int] = ..., inbound_fee_rate_milli_msat: _Optional[int] = ...) -> None: ...

class ChannelAuthProof(_message.Message):
    __slots__ = ("node_sig1", "bitcoin_sig1", "node_sig2", "bitcoin_sig2")
    NODE_SIG1_FIELD_NUMBER: _ClassVar[int]
    BITCOIN_SIG1_FIELD_NUMBER: _ClassVar[int]
    NODE_SIG2_FIELD_NUMBER: _ClassVar[int]
    BITCOIN_SIG2_FIELD_NUMBER: _ClassVar[int]
    node_sig1: bytes
    bitcoin_sig1: bytes
    node_sig2: bytes
    bitcoin_sig2: bytes
    def __init__(self, node_sig1: _Optional[bytes] = ..., bitcoin_sig1: _Optional[bytes] = ..., node_sig2: _Optional[bytes] = ..., bitcoin_sig2: _Optional[bytes] = ...) -> None: ...

class ChannelEdge(_message.Message):
    __slots__ = ("channel_id", "chan_point", "last_update", "node1_pub", "node2_pub", "capacity", "node1_policy", "node2_policy", "custom_records", "auth_proof")
    class CustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATE_FIELD_NUMBER: _ClassVar[int]
    NODE1_PUB_FIELD_NUMBER: _ClassVar[int]
    NODE2_PUB_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    NODE1_POLICY_FIELD_NUMBER: _ClassVar[int]
    NODE2_POLICY_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    AUTH_PROOF_FIELD_NUMBER: _ClassVar[int]
    channel_id: int
    chan_point: str
    last_update: int
    node1_pub: str
    node2_pub: str
    capacity: int
    node1_policy: RoutingPolicy
    node2_policy: RoutingPolicy
    custom_records: _containers.ScalarMap[int, bytes]
    auth_proof: ChannelAuthProof
    def __init__(self, channel_id: _Optional[int] = ..., chan_point: _Optional[str] = ..., last_update: _Optional[int] = ..., node1_pub: _Optional[str] = ..., node2_pub: _Optional[str] = ..., capacity: _Optional[int] = ..., node1_policy: _Optional[_Union[RoutingPolicy, _Mapping]] = ..., node2_policy: _Optional[_Union[RoutingPolicy, _Mapping]] = ..., custom_records: _Optional[_Mapping[int, bytes]] = ..., auth_proof: _Optional[_Union[ChannelAuthProof, _Mapping]] = ...) -> None: ...

class ChannelGraphRequest(_message.Message):
    __slots__ = ("include_unannounced", "include_auth_proof")
    INCLUDE_UNANNOUNCED_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_AUTH_PROOF_FIELD_NUMBER: _ClassVar[int]
    include_unannounced: bool
    include_auth_proof: bool
    def __init__(self, include_unannounced: bool = ..., include_auth_proof: bool = ...) -> None: ...

class ChannelGraph(_message.Message):
    __slots__ = ("nodes", "edges")
    NODES_FIELD_NUMBER: _ClassVar[int]
    EDGES_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[LightningNode]
    edges: _containers.RepeatedCompositeFieldContainer[ChannelEdge]
    def __init__(self, nodes: _Optional[_Iterable[_Union[LightningNode, _Mapping]]] = ..., edges: _Optional[_Iterable[_Union[ChannelEdge, _Mapping]]] = ...) -> None: ...

class NodeMetricsRequest(_message.Message):
    __slots__ = ("types",)
    TYPES_FIELD_NUMBER: _ClassVar[int]
    types: _containers.RepeatedScalarFieldContainer[NodeMetricType]
    def __init__(self, types: _Optional[_Iterable[_Union[NodeMetricType, str]]] = ...) -> None: ...

class NodeMetricsResponse(_message.Message):
    __slots__ = ("betweenness_centrality",)
    class BetweennessCentralityEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: FloatMetric
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[FloatMetric, _Mapping]] = ...) -> None: ...
    BETWEENNESS_CENTRALITY_FIELD_NUMBER: _ClassVar[int]
    betweenness_centrality: _containers.MessageMap[str, FloatMetric]
    def __init__(self, betweenness_centrality: _Optional[_Mapping[str, FloatMetric]] = ...) -> None: ...

class FloatMetric(_message.Message):
    __slots__ = ("value", "normalized_value")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    NORMALIZED_VALUE_FIELD_NUMBER: _ClassVar[int]
    value: float
    normalized_value: float
    def __init__(self, value: _Optional[float] = ..., normalized_value: _Optional[float] = ...) -> None: ...

class ChanInfoRequest(_message.Message):
    __slots__ = ("chan_id", "chan_point", "include_auth_proof")
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_AUTH_PROOF_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    chan_point: str
    include_auth_proof: bool
    def __init__(self, chan_id: _Optional[int] = ..., chan_point: _Optional[str] = ..., include_auth_proof: bool = ...) -> None: ...

class NetworkInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class NetworkInfo(_message.Message):
    __slots__ = ("graph_diameter", "avg_out_degree", "max_out_degree", "num_nodes", "num_channels", "total_network_capacity", "avg_channel_size", "min_channel_size", "max_channel_size", "median_channel_size_sat", "num_zombie_chans")
    GRAPH_DIAMETER_FIELD_NUMBER: _ClassVar[int]
    AVG_OUT_DEGREE_FIELD_NUMBER: _ClassVar[int]
    MAX_OUT_DEGREE_FIELD_NUMBER: _ClassVar[int]
    NUM_NODES_FIELD_NUMBER: _ClassVar[int]
    NUM_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_NETWORK_CAPACITY_FIELD_NUMBER: _ClassVar[int]
    AVG_CHANNEL_SIZE_FIELD_NUMBER: _ClassVar[int]
    MIN_CHANNEL_SIZE_FIELD_NUMBER: _ClassVar[int]
    MAX_CHANNEL_SIZE_FIELD_NUMBER: _ClassVar[int]
    MEDIAN_CHANNEL_SIZE_SAT_FIELD_NUMBER: _ClassVar[int]
    NUM_ZOMBIE_CHANS_FIELD_NUMBER: _ClassVar[int]
    graph_diameter: int
    avg_out_degree: float
    max_out_degree: int
    num_nodes: int
    num_channels: int
    total_network_capacity: int
    avg_channel_size: float
    min_channel_size: int
    max_channel_size: int
    median_channel_size_sat: int
    num_zombie_chans: int
    def __init__(self, graph_diameter: _Optional[int] = ..., avg_out_degree: _Optional[float] = ..., max_out_degree: _Optional[int] = ..., num_nodes: _Optional[int] = ..., num_channels: _Optional[int] = ..., total_network_capacity: _Optional[int] = ..., avg_channel_size: _Optional[float] = ..., min_channel_size: _Optional[int] = ..., max_channel_size: _Optional[int] = ..., median_channel_size_sat: _Optional[int] = ..., num_zombie_chans: _Optional[int] = ...) -> None: ...

class StopRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StopResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class GraphTopologySubscription(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GraphTopologyUpdate(_message.Message):
    __slots__ = ("node_updates", "channel_updates", "closed_chans")
    NODE_UPDATES_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_UPDATES_FIELD_NUMBER: _ClassVar[int]
    CLOSED_CHANS_FIELD_NUMBER: _ClassVar[int]
    node_updates: _containers.RepeatedCompositeFieldContainer[NodeUpdate]
    channel_updates: _containers.RepeatedCompositeFieldContainer[ChannelEdgeUpdate]
    closed_chans: _containers.RepeatedCompositeFieldContainer[ClosedChannelUpdate]
    def __init__(self, node_updates: _Optional[_Iterable[_Union[NodeUpdate, _Mapping]]] = ..., channel_updates: _Optional[_Iterable[_Union[ChannelEdgeUpdate, _Mapping]]] = ..., closed_chans: _Optional[_Iterable[_Union[ClosedChannelUpdate, _Mapping]]] = ...) -> None: ...

class NodeUpdate(_message.Message):
    __slots__ = ("addresses", "identity_key", "global_features", "alias", "color", "node_addresses", "features")
    class FeaturesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: Feature
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[Feature, _Mapping]] = ...) -> None: ...
    ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    IDENTITY_KEY_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_FEATURES_FIELD_NUMBER: _ClassVar[int]
    ALIAS_FIELD_NUMBER: _ClassVar[int]
    COLOR_FIELD_NUMBER: _ClassVar[int]
    NODE_ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    addresses: _containers.RepeatedScalarFieldContainer[str]
    identity_key: str
    global_features: bytes
    alias: str
    color: str
    node_addresses: _containers.RepeatedCompositeFieldContainer[NodeAddress]
    features: _containers.MessageMap[int, Feature]
    def __init__(self, addresses: _Optional[_Iterable[str]] = ..., identity_key: _Optional[str] = ..., global_features: _Optional[bytes] = ..., alias: _Optional[str] = ..., color: _Optional[str] = ..., node_addresses: _Optional[_Iterable[_Union[NodeAddress, _Mapping]]] = ..., features: _Optional[_Mapping[int, Feature]] = ...) -> None: ...

class ChannelEdgeUpdate(_message.Message):
    __slots__ = ("chan_id", "chan_point", "capacity", "routing_policy", "advertising_node", "connecting_node")
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    ROUTING_POLICY_FIELD_NUMBER: _ClassVar[int]
    ADVERTISING_NODE_FIELD_NUMBER: _ClassVar[int]
    CONNECTING_NODE_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    chan_point: ChannelPoint
    capacity: int
    routing_policy: RoutingPolicy
    advertising_node: str
    connecting_node: str
    def __init__(self, chan_id: _Optional[int] = ..., chan_point: _Optional[_Union[ChannelPoint, _Mapping]] = ..., capacity: _Optional[int] = ..., routing_policy: _Optional[_Union[RoutingPolicy, _Mapping]] = ..., advertising_node: _Optional[str] = ..., connecting_node: _Optional[str] = ...) -> None: ...

class ClosedChannelUpdate(_message.Message):
    __slots__ = ("chan_id", "capacity", "closed_height", "chan_point")
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    CLOSED_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    capacity: int
    closed_height: int
    chan_point: ChannelPoint
    def __init__(self, chan_id: _Optional[int] = ..., capacity: _Optional[int] = ..., closed_height: _Optional[int] = ..., chan_point: _Optional[_Union[ChannelPoint, _Mapping]] = ...) -> None: ...

class HopHint(_message.Message):
    __slots__ = ("node_id", "chan_id", "fee_base_msat", "fee_proportional_millionths", "cltv_expiry_delta")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    FEE_BASE_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEE_PROPORTIONAL_MILLIONTHS_FIELD_NUMBER: _ClassVar[int]
    CLTV_EXPIRY_DELTA_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    chan_id: int
    fee_base_msat: int
    fee_proportional_millionths: int
    cltv_expiry_delta: int
    def __init__(self, node_id: _Optional[str] = ..., chan_id: _Optional[int] = ..., fee_base_msat: _Optional[int] = ..., fee_proportional_millionths: _Optional[int] = ..., cltv_expiry_delta: _Optional[int] = ...) -> None: ...

class SetID(_message.Message):
    __slots__ = ("set_id",)
    SET_ID_FIELD_NUMBER: _ClassVar[int]
    set_id: bytes
    def __init__(self, set_id: _Optional[bytes] = ...) -> None: ...

class RouteHint(_message.Message):
    __slots__ = ("hop_hints",)
    HOP_HINTS_FIELD_NUMBER: _ClassVar[int]
    hop_hints: _containers.RepeatedCompositeFieldContainer[HopHint]
    def __init__(self, hop_hints: _Optional[_Iterable[_Union[HopHint, _Mapping]]] = ...) -> None: ...

class BlindedPaymentPath(_message.Message):
    __slots__ = ("blinded_path", "base_fee_msat", "proportional_fee_rate", "total_cltv_delta", "htlc_min_msat", "htlc_max_msat", "features")
    BLINDED_PATH_FIELD_NUMBER: _ClassVar[int]
    BASE_FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    PROPORTIONAL_FEE_RATE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_CLTV_DELTA_FIELD_NUMBER: _ClassVar[int]
    HTLC_MIN_MSAT_FIELD_NUMBER: _ClassVar[int]
    HTLC_MAX_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    blinded_path: BlindedPath
    base_fee_msat: int
    proportional_fee_rate: int
    total_cltv_delta: int
    htlc_min_msat: int
    htlc_max_msat: int
    features: _containers.RepeatedScalarFieldContainer[FeatureBit]
    def __init__(self, blinded_path: _Optional[_Union[BlindedPath, _Mapping]] = ..., base_fee_msat: _Optional[int] = ..., proportional_fee_rate: _Optional[int] = ..., total_cltv_delta: _Optional[int] = ..., htlc_min_msat: _Optional[int] = ..., htlc_max_msat: _Optional[int] = ..., features: _Optional[_Iterable[_Union[FeatureBit, str]]] = ...) -> None: ...

class BlindedPath(_message.Message):
    __slots__ = ("introduction_node", "blinding_point", "blinded_hops")
    INTRODUCTION_NODE_FIELD_NUMBER: _ClassVar[int]
    BLINDING_POINT_FIELD_NUMBER: _ClassVar[int]
    BLINDED_HOPS_FIELD_NUMBER: _ClassVar[int]
    introduction_node: bytes
    blinding_point: bytes
    blinded_hops: _containers.RepeatedCompositeFieldContainer[BlindedHop]
    def __init__(self, introduction_node: _Optional[bytes] = ..., blinding_point: _Optional[bytes] = ..., blinded_hops: _Optional[_Iterable[_Union[BlindedHop, _Mapping]]] = ...) -> None: ...

class BlindedHop(_message.Message):
    __slots__ = ("blinded_node", "encrypted_data")
    BLINDED_NODE_FIELD_NUMBER: _ClassVar[int]
    ENCRYPTED_DATA_FIELD_NUMBER: _ClassVar[int]
    blinded_node: bytes
    encrypted_data: bytes
    def __init__(self, blinded_node: _Optional[bytes] = ..., encrypted_data: _Optional[bytes] = ...) -> None: ...

class AMPInvoiceState(_message.Message):
    __slots__ = ("state", "settle_index", "settle_time", "amt_paid_msat")
    STATE_FIELD_NUMBER: _ClassVar[int]
    SETTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    SETTLE_TIME_FIELD_NUMBER: _ClassVar[int]
    AMT_PAID_MSAT_FIELD_NUMBER: _ClassVar[int]
    state: InvoiceHTLCState
    settle_index: int
    settle_time: int
    amt_paid_msat: int
    def __init__(self, state: _Optional[_Union[InvoiceHTLCState, str]] = ..., settle_index: _Optional[int] = ..., settle_time: _Optional[int] = ..., amt_paid_msat: _Optional[int] = ...) -> None: ...

class Invoice(_message.Message):
    __slots__ = ("memo", "r_preimage", "r_hash", "value", "value_msat", "settled", "creation_date", "settle_date", "payment_request", "description_hash", "expiry", "fallback_addr", "cltv_expiry", "route_hints", "private", "add_index", "settle_index", "amt_paid", "amt_paid_sat", "amt_paid_msat", "state", "htlcs", "features", "is_keysend", "payment_addr", "is_amp", "amp_invoice_state", "is_blinded", "blinded_path_config")
    class InvoiceState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        OPEN: _ClassVar[Invoice.InvoiceState]
        SETTLED: _ClassVar[Invoice.InvoiceState]
        CANCELED: _ClassVar[Invoice.InvoiceState]
        ACCEPTED: _ClassVar[Invoice.InvoiceState]
    OPEN: Invoice.InvoiceState
    SETTLED: Invoice.InvoiceState
    CANCELED: Invoice.InvoiceState
    ACCEPTED: Invoice.InvoiceState
    class FeaturesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: Feature
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[Feature, _Mapping]] = ...) -> None: ...
    class AmpInvoiceStateEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: AMPInvoiceState
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[AMPInvoiceState, _Mapping]] = ...) -> None: ...
    MEMO_FIELD_NUMBER: _ClassVar[int]
    R_PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    R_HASH_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    VALUE_MSAT_FIELD_NUMBER: _ClassVar[int]
    SETTLED_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_FIELD_NUMBER: _ClassVar[int]
    SETTLE_DATE_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_HASH_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_FIELD_NUMBER: _ClassVar[int]
    FALLBACK_ADDR_FIELD_NUMBER: _ClassVar[int]
    CLTV_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    ROUTE_HINTS_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    ADD_INDEX_FIELD_NUMBER: _ClassVar[int]
    SETTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    AMT_PAID_FIELD_NUMBER: _ClassVar[int]
    AMT_PAID_SAT_FIELD_NUMBER: _ClassVar[int]
    AMT_PAID_MSAT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    HTLCS_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    IS_KEYSEND_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    IS_AMP_FIELD_NUMBER: _ClassVar[int]
    AMP_INVOICE_STATE_FIELD_NUMBER: _ClassVar[int]
    IS_BLINDED_FIELD_NUMBER: _ClassVar[int]
    BLINDED_PATH_CONFIG_FIELD_NUMBER: _ClassVar[int]
    memo: str
    r_preimage: bytes
    r_hash: bytes
    value: int
    value_msat: int
    settled: bool
    creation_date: int
    settle_date: int
    payment_request: str
    description_hash: bytes
    expiry: int
    fallback_addr: str
    cltv_expiry: int
    route_hints: _containers.RepeatedCompositeFieldContainer[RouteHint]
    private: bool
    add_index: int
    settle_index: int
    amt_paid: int
    amt_paid_sat: int
    amt_paid_msat: int
    state: Invoice.InvoiceState
    htlcs: _containers.RepeatedCompositeFieldContainer[InvoiceHTLC]
    features: _containers.MessageMap[int, Feature]
    is_keysend: bool
    payment_addr: bytes
    is_amp: bool
    amp_invoice_state: _containers.MessageMap[str, AMPInvoiceState]
    is_blinded: bool
    blinded_path_config: BlindedPathConfig
    def __init__(self, memo: _Optional[str] = ..., r_preimage: _Optional[bytes] = ..., r_hash: _Optional[bytes] = ..., value: _Optional[int] = ..., value_msat: _Optional[int] = ..., settled: bool = ..., creation_date: _Optional[int] = ..., settle_date: _Optional[int] = ..., payment_request: _Optional[str] = ..., description_hash: _Optional[bytes] = ..., expiry: _Optional[int] = ..., fallback_addr: _Optional[str] = ..., cltv_expiry: _Optional[int] = ..., route_hints: _Optional[_Iterable[_Union[RouteHint, _Mapping]]] = ..., private: bool = ..., add_index: _Optional[int] = ..., settle_index: _Optional[int] = ..., amt_paid: _Optional[int] = ..., amt_paid_sat: _Optional[int] = ..., amt_paid_msat: _Optional[int] = ..., state: _Optional[_Union[Invoice.InvoiceState, str]] = ..., htlcs: _Optional[_Iterable[_Union[InvoiceHTLC, _Mapping]]] = ..., features: _Optional[_Mapping[int, Feature]] = ..., is_keysend: bool = ..., payment_addr: _Optional[bytes] = ..., is_amp: bool = ..., amp_invoice_state: _Optional[_Mapping[str, AMPInvoiceState]] = ..., is_blinded: bool = ..., blinded_path_config: _Optional[_Union[BlindedPathConfig, _Mapping]] = ...) -> None: ...

class BlindedPathConfig(_message.Message):
    __slots__ = ("min_num_real_hops", "num_hops", "max_num_paths", "node_omission_list", "incoming_channel_list")
    MIN_NUM_REAL_HOPS_FIELD_NUMBER: _ClassVar[int]
    NUM_HOPS_FIELD_NUMBER: _ClassVar[int]
    MAX_NUM_PATHS_FIELD_NUMBER: _ClassVar[int]
    NODE_OMISSION_LIST_FIELD_NUMBER: _ClassVar[int]
    INCOMING_CHANNEL_LIST_FIELD_NUMBER: _ClassVar[int]
    min_num_real_hops: int
    num_hops: int
    max_num_paths: int
    node_omission_list: _containers.RepeatedScalarFieldContainer[bytes]
    incoming_channel_list: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, min_num_real_hops: _Optional[int] = ..., num_hops: _Optional[int] = ..., max_num_paths: _Optional[int] = ..., node_omission_list: _Optional[_Iterable[bytes]] = ..., incoming_channel_list: _Optional[_Iterable[int]] = ...) -> None: ...

class InvoiceHTLC(_message.Message):
    __slots__ = ("chan_id", "htlc_index", "amt_msat", "accept_height", "accept_time", "resolve_time", "expiry_height", "state", "custom_records", "mpp_total_amt_msat", "amp", "custom_channel_data")
    class CustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    HTLC_INDEX_FIELD_NUMBER: _ClassVar[int]
    AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    ACCEPT_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    ACCEPT_TIME_FIELD_NUMBER: _ClassVar[int]
    RESOLVE_TIME_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    MPP_TOTAL_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    AMP_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_CHANNEL_DATA_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    htlc_index: int
    amt_msat: int
    accept_height: int
    accept_time: int
    resolve_time: int
    expiry_height: int
    state: InvoiceHTLCState
    custom_records: _containers.ScalarMap[int, bytes]
    mpp_total_amt_msat: int
    amp: AMP
    custom_channel_data: bytes
    def __init__(self, chan_id: _Optional[int] = ..., htlc_index: _Optional[int] = ..., amt_msat: _Optional[int] = ..., accept_height: _Optional[int] = ..., accept_time: _Optional[int] = ..., resolve_time: _Optional[int] = ..., expiry_height: _Optional[int] = ..., state: _Optional[_Union[InvoiceHTLCState, str]] = ..., custom_records: _Optional[_Mapping[int, bytes]] = ..., mpp_total_amt_msat: _Optional[int] = ..., amp: _Optional[_Union[AMP, _Mapping]] = ..., custom_channel_data: _Optional[bytes] = ...) -> None: ...

class AMP(_message.Message):
    __slots__ = ("root_share", "set_id", "child_index", "hash", "preimage")
    ROOT_SHARE_FIELD_NUMBER: _ClassVar[int]
    SET_ID_FIELD_NUMBER: _ClassVar[int]
    CHILD_INDEX_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    root_share: bytes
    set_id: bytes
    child_index: int
    hash: bytes
    preimage: bytes
    def __init__(self, root_share: _Optional[bytes] = ..., set_id: _Optional[bytes] = ..., child_index: _Optional[int] = ..., hash: _Optional[bytes] = ..., preimage: _Optional[bytes] = ...) -> None: ...

class AddInvoiceResponse(_message.Message):
    __slots__ = ("r_hash", "payment_request", "add_index", "payment_addr")
    R_HASH_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    ADD_INDEX_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    r_hash: bytes
    payment_request: str
    add_index: int
    payment_addr: bytes
    def __init__(self, r_hash: _Optional[bytes] = ..., payment_request: _Optional[str] = ..., add_index: _Optional[int] = ..., payment_addr: _Optional[bytes] = ...) -> None: ...

class PaymentHash(_message.Message):
    __slots__ = ("r_hash_str", "r_hash")
    R_HASH_STR_FIELD_NUMBER: _ClassVar[int]
    R_HASH_FIELD_NUMBER: _ClassVar[int]
    r_hash_str: str
    r_hash: bytes
    def __init__(self, r_hash_str: _Optional[str] = ..., r_hash: _Optional[bytes] = ...) -> None: ...

class ListInvoiceRequest(_message.Message):
    __slots__ = ("pending_only", "index_offset", "num_max_invoices", "reversed", "creation_date_start", "creation_date_end")
    PENDING_ONLY_FIELD_NUMBER: _ClassVar[int]
    INDEX_OFFSET_FIELD_NUMBER: _ClassVar[int]
    NUM_MAX_INVOICES_FIELD_NUMBER: _ClassVar[int]
    REVERSED_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_START_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_END_FIELD_NUMBER: _ClassVar[int]
    pending_only: bool
    index_offset: int
    num_max_invoices: int
    reversed: bool
    creation_date_start: int
    creation_date_end: int
    def __init__(self, pending_only: bool = ..., index_offset: _Optional[int] = ..., num_max_invoices: _Optional[int] = ..., reversed: bool = ..., creation_date_start: _Optional[int] = ..., creation_date_end: _Optional[int] = ...) -> None: ...

class ListInvoiceResponse(_message.Message):
    __slots__ = ("invoices", "last_index_offset", "first_index_offset")
    INVOICES_FIELD_NUMBER: _ClassVar[int]
    LAST_INDEX_OFFSET_FIELD_NUMBER: _ClassVar[int]
    FIRST_INDEX_OFFSET_FIELD_NUMBER: _ClassVar[int]
    invoices: _containers.RepeatedCompositeFieldContainer[Invoice]
    last_index_offset: int
    first_index_offset: int
    def __init__(self, invoices: _Optional[_Iterable[_Union[Invoice, _Mapping]]] = ..., last_index_offset: _Optional[int] = ..., first_index_offset: _Optional[int] = ...) -> None: ...

class InvoiceSubscription(_message.Message):
    __slots__ = ("add_index", "settle_index")
    ADD_INDEX_FIELD_NUMBER: _ClassVar[int]
    SETTLE_INDEX_FIELD_NUMBER: _ClassVar[int]
    add_index: int
    settle_index: int
    def __init__(self, add_index: _Optional[int] = ..., settle_index: _Optional[int] = ...) -> None: ...

class DelCanceledInvoiceReq(_message.Message):
    __slots__ = ("invoice_hash",)
    INVOICE_HASH_FIELD_NUMBER: _ClassVar[int]
    invoice_hash: str
    def __init__(self, invoice_hash: _Optional[str] = ...) -> None: ...

class DelCanceledInvoiceResp(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class Payment(_message.Message):
    __slots__ = ("payment_hash", "value", "creation_date", "fee", "payment_preimage", "value_sat", "value_msat", "payment_request", "status", "fee_sat", "fee_msat", "creation_time_ns", "htlcs", "payment_index", "failure_reason", "first_hop_custom_records")
    class PaymentStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNKNOWN: _ClassVar[Payment.PaymentStatus]
        IN_FLIGHT: _ClassVar[Payment.PaymentStatus]
        SUCCEEDED: _ClassVar[Payment.PaymentStatus]
        FAILED: _ClassVar[Payment.PaymentStatus]
        INITIATED: _ClassVar[Payment.PaymentStatus]
    UNKNOWN: Payment.PaymentStatus
    IN_FLIGHT: Payment.PaymentStatus
    SUCCEEDED: Payment.PaymentStatus
    FAILED: Payment.PaymentStatus
    INITIATED: Payment.PaymentStatus
    class FirstHopCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_FIELD_NUMBER: _ClassVar[int]
    FEE_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    VALUE_SAT_FIELD_NUMBER: _ClassVar[int]
    VALUE_MSAT_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    FEE_SAT_FIELD_NUMBER: _ClassVar[int]
    FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    CREATION_TIME_NS_FIELD_NUMBER: _ClassVar[int]
    HTLCS_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_INDEX_FIELD_NUMBER: _ClassVar[int]
    FAILURE_REASON_FIELD_NUMBER: _ClassVar[int]
    FIRST_HOP_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    payment_hash: str
    value: int
    creation_date: int
    fee: int
    payment_preimage: str
    value_sat: int
    value_msat: int
    payment_request: str
    status: Payment.PaymentStatus
    fee_sat: int
    fee_msat: int
    creation_time_ns: int
    htlcs: _containers.RepeatedCompositeFieldContainer[HTLCAttempt]
    payment_index: int
    failure_reason: PaymentFailureReason
    first_hop_custom_records: _containers.ScalarMap[int, bytes]
    def __init__(self, payment_hash: _Optional[str] = ..., value: _Optional[int] = ..., creation_date: _Optional[int] = ..., fee: _Optional[int] = ..., payment_preimage: _Optional[str] = ..., value_sat: _Optional[int] = ..., value_msat: _Optional[int] = ..., payment_request: _Optional[str] = ..., status: _Optional[_Union[Payment.PaymentStatus, str]] = ..., fee_sat: _Optional[int] = ..., fee_msat: _Optional[int] = ..., creation_time_ns: _Optional[int] = ..., htlcs: _Optional[_Iterable[_Union[HTLCAttempt, _Mapping]]] = ..., payment_index: _Optional[int] = ..., failure_reason: _Optional[_Union[PaymentFailureReason, str]] = ..., first_hop_custom_records: _Optional[_Mapping[int, bytes]] = ...) -> None: ...

class HTLCAttempt(_message.Message):
    __slots__ = ("attempt_id", "status", "route", "attempt_time_ns", "resolve_time_ns", "failure", "preimage")
    class HTLCStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        IN_FLIGHT: _ClassVar[HTLCAttempt.HTLCStatus]
        SUCCEEDED: _ClassVar[HTLCAttempt.HTLCStatus]
        FAILED: _ClassVar[HTLCAttempt.HTLCStatus]
    IN_FLIGHT: HTLCAttempt.HTLCStatus
    SUCCEEDED: HTLCAttempt.HTLCStatus
    FAILED: HTLCAttempt.HTLCStatus
    ATTEMPT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ROUTE_FIELD_NUMBER: _ClassVar[int]
    ATTEMPT_TIME_NS_FIELD_NUMBER: _ClassVar[int]
    RESOLVE_TIME_NS_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    attempt_id: int
    status: HTLCAttempt.HTLCStatus
    route: Route
    attempt_time_ns: int
    resolve_time_ns: int
    failure: Failure
    preimage: bytes
    def __init__(self, attempt_id: _Optional[int] = ..., status: _Optional[_Union[HTLCAttempt.HTLCStatus, str]] = ..., route: _Optional[_Union[Route, _Mapping]] = ..., attempt_time_ns: _Optional[int] = ..., resolve_time_ns: _Optional[int] = ..., failure: _Optional[_Union[Failure, _Mapping]] = ..., preimage: _Optional[bytes] = ...) -> None: ...

class ListPaymentsRequest(_message.Message):
    __slots__ = ("include_incomplete", "index_offset", "max_payments", "reversed", "count_total_payments", "creation_date_start", "creation_date_end")
    INCLUDE_INCOMPLETE_FIELD_NUMBER: _ClassVar[int]
    INDEX_OFFSET_FIELD_NUMBER: _ClassVar[int]
    MAX_PAYMENTS_FIELD_NUMBER: _ClassVar[int]
    REVERSED_FIELD_NUMBER: _ClassVar[int]
    COUNT_TOTAL_PAYMENTS_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_START_FIELD_NUMBER: _ClassVar[int]
    CREATION_DATE_END_FIELD_NUMBER: _ClassVar[int]
    include_incomplete: bool
    index_offset: int
    max_payments: int
    reversed: bool
    count_total_payments: bool
    creation_date_start: int
    creation_date_end: int
    def __init__(self, include_incomplete: bool = ..., index_offset: _Optional[int] = ..., max_payments: _Optional[int] = ..., reversed: bool = ..., count_total_payments: bool = ..., creation_date_start: _Optional[int] = ..., creation_date_end: _Optional[int] = ...) -> None: ...

class ListPaymentsResponse(_message.Message):
    __slots__ = ("payments", "first_index_offset", "last_index_offset", "total_num_payments")
    PAYMENTS_FIELD_NUMBER: _ClassVar[int]
    FIRST_INDEX_OFFSET_FIELD_NUMBER: _ClassVar[int]
    LAST_INDEX_OFFSET_FIELD_NUMBER: _ClassVar[int]
    TOTAL_NUM_PAYMENTS_FIELD_NUMBER: _ClassVar[int]
    payments: _containers.RepeatedCompositeFieldContainer[Payment]
    first_index_offset: int
    last_index_offset: int
    total_num_payments: int
    def __init__(self, payments: _Optional[_Iterable[_Union[Payment, _Mapping]]] = ..., first_index_offset: _Optional[int] = ..., last_index_offset: _Optional[int] = ..., total_num_payments: _Optional[int] = ...) -> None: ...

class DeletePaymentRequest(_message.Message):
    __slots__ = ("payment_hash", "failed_htlcs_only")
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    FAILED_HTLCS_ONLY_FIELD_NUMBER: _ClassVar[int]
    payment_hash: bytes
    failed_htlcs_only: bool
    def __init__(self, payment_hash: _Optional[bytes] = ..., failed_htlcs_only: bool = ...) -> None: ...

class DeleteAllPaymentsRequest(_message.Message):
    __slots__ = ("failed_payments_only", "failed_htlcs_only", "all_payments")
    FAILED_PAYMENTS_ONLY_FIELD_NUMBER: _ClassVar[int]
    FAILED_HTLCS_ONLY_FIELD_NUMBER: _ClassVar[int]
    ALL_PAYMENTS_FIELD_NUMBER: _ClassVar[int]
    failed_payments_only: bool
    failed_htlcs_only: bool
    all_payments: bool
    def __init__(self, failed_payments_only: bool = ..., failed_htlcs_only: bool = ..., all_payments: bool = ...) -> None: ...

class DeletePaymentResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class DeleteAllPaymentsResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class AbandonChannelRequest(_message.Message):
    __slots__ = ("channel_point", "pending_funding_shim_only", "i_know_what_i_am_doing")
    CHANNEL_POINT_FIELD_NUMBER: _ClassVar[int]
    PENDING_FUNDING_SHIM_ONLY_FIELD_NUMBER: _ClassVar[int]
    I_KNOW_WHAT_I_AM_DOING_FIELD_NUMBER: _ClassVar[int]
    channel_point: ChannelPoint
    pending_funding_shim_only: bool
    i_know_what_i_am_doing: bool
    def __init__(self, channel_point: _Optional[_Union[ChannelPoint, _Mapping]] = ..., pending_funding_shim_only: bool = ..., i_know_what_i_am_doing: bool = ...) -> None: ...

class AbandonChannelResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class DebugLevelRequest(_message.Message):
    __slots__ = ("show", "level_spec")
    SHOW_FIELD_NUMBER: _ClassVar[int]
    LEVEL_SPEC_FIELD_NUMBER: _ClassVar[int]
    show: bool
    level_spec: str
    def __init__(self, show: bool = ..., level_spec: _Optional[str] = ...) -> None: ...

class DebugLevelResponse(_message.Message):
    __slots__ = ("sub_systems",)
    SUB_SYSTEMS_FIELD_NUMBER: _ClassVar[int]
    sub_systems: str
    def __init__(self, sub_systems: _Optional[str] = ...) -> None: ...

class PayReqString(_message.Message):
    __slots__ = ("pay_req",)
    PAY_REQ_FIELD_NUMBER: _ClassVar[int]
    pay_req: str
    def __init__(self, pay_req: _Optional[str] = ...) -> None: ...

class PayReq(_message.Message):
    __slots__ = ("destination", "payment_hash", "num_satoshis", "timestamp", "expiry", "description", "description_hash", "fallback_addr", "cltv_expiry", "route_hints", "payment_addr", "num_msat", "features", "blinded_paths")
    class FeaturesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: Feature
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[Feature, _Mapping]] = ...) -> None: ...
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    NUM_SATOSHIS_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_HASH_FIELD_NUMBER: _ClassVar[int]
    FALLBACK_ADDR_FIELD_NUMBER: _ClassVar[int]
    CLTV_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    ROUTE_HINTS_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    NUM_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    BLINDED_PATHS_FIELD_NUMBER: _ClassVar[int]
    destination: str
    payment_hash: str
    num_satoshis: int
    timestamp: int
    expiry: int
    description: str
    description_hash: str
    fallback_addr: str
    cltv_expiry: int
    route_hints: _containers.RepeatedCompositeFieldContainer[RouteHint]
    payment_addr: bytes
    num_msat: int
    features: _containers.MessageMap[int, Feature]
    blinded_paths: _containers.RepeatedCompositeFieldContainer[BlindedPaymentPath]
    def __init__(self, destination: _Optional[str] = ..., payment_hash: _Optional[str] = ..., num_satoshis: _Optional[int] = ..., timestamp: _Optional[int] = ..., expiry: _Optional[int] = ..., description: _Optional[str] = ..., description_hash: _Optional[str] = ..., fallback_addr: _Optional[str] = ..., cltv_expiry: _Optional[int] = ..., route_hints: _Optional[_Iterable[_Union[RouteHint, _Mapping]]] = ..., payment_addr: _Optional[bytes] = ..., num_msat: _Optional[int] = ..., features: _Optional[_Mapping[int, Feature]] = ..., blinded_paths: _Optional[_Iterable[_Union[BlindedPaymentPath, _Mapping]]] = ...) -> None: ...

class Feature(_message.Message):
    __slots__ = ("name", "is_required", "is_known")
    NAME_FIELD_NUMBER: _ClassVar[int]
    IS_REQUIRED_FIELD_NUMBER: _ClassVar[int]
    IS_KNOWN_FIELD_NUMBER: _ClassVar[int]
    name: str
    is_required: bool
    is_known: bool
    def __init__(self, name: _Optional[str] = ..., is_required: bool = ..., is_known: bool = ...) -> None: ...

class FeeReportRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ChannelFeeReport(_message.Message):
    __slots__ = ("chan_id", "channel_point", "base_fee_msat", "fee_per_mil", "fee_rate", "inbound_base_fee_msat", "inbound_fee_per_mil")
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_POINT_FIELD_NUMBER: _ClassVar[int]
    BASE_FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEE_PER_MIL_FIELD_NUMBER: _ClassVar[int]
    FEE_RATE_FIELD_NUMBER: _ClassVar[int]
    INBOUND_BASE_FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    INBOUND_FEE_PER_MIL_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    channel_point: str
    base_fee_msat: int
    fee_per_mil: int
    fee_rate: float
    inbound_base_fee_msat: int
    inbound_fee_per_mil: int
    def __init__(self, chan_id: _Optional[int] = ..., channel_point: _Optional[str] = ..., base_fee_msat: _Optional[int] = ..., fee_per_mil: _Optional[int] = ..., fee_rate: _Optional[float] = ..., inbound_base_fee_msat: _Optional[int] = ..., inbound_fee_per_mil: _Optional[int] = ...) -> None: ...

class FeeReportResponse(_message.Message):
    __slots__ = ("channel_fees", "day_fee_sum", "week_fee_sum", "month_fee_sum")
    CHANNEL_FEES_FIELD_NUMBER: _ClassVar[int]
    DAY_FEE_SUM_FIELD_NUMBER: _ClassVar[int]
    WEEK_FEE_SUM_FIELD_NUMBER: _ClassVar[int]
    MONTH_FEE_SUM_FIELD_NUMBER: _ClassVar[int]
    channel_fees: _containers.RepeatedCompositeFieldContainer[ChannelFeeReport]
    day_fee_sum: int
    week_fee_sum: int
    month_fee_sum: int
    def __init__(self, channel_fees: _Optional[_Iterable[_Union[ChannelFeeReport, _Mapping]]] = ..., day_fee_sum: _Optional[int] = ..., week_fee_sum: _Optional[int] = ..., month_fee_sum: _Optional[int] = ...) -> None: ...

class InboundFee(_message.Message):
    __slots__ = ("base_fee_msat", "fee_rate_ppm")
    BASE_FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEE_RATE_PPM_FIELD_NUMBER: _ClassVar[int]
    base_fee_msat: int
    fee_rate_ppm: int
    def __init__(self, base_fee_msat: _Optional[int] = ..., fee_rate_ppm: _Optional[int] = ...) -> None: ...

class PolicyUpdateRequest(_message.Message):
    __slots__ = ("chan_point", "base_fee_msat", "fee_rate", "fee_rate_ppm", "time_lock_delta", "max_htlc_msat", "min_htlc_msat", "min_htlc_msat_specified", "inbound_fee", "create_missing_edge")
    GLOBAL_FIELD_NUMBER: _ClassVar[int]
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    BASE_FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEE_RATE_FIELD_NUMBER: _ClassVar[int]
    FEE_RATE_PPM_FIELD_NUMBER: _ClassVar[int]
    TIME_LOCK_DELTA_FIELD_NUMBER: _ClassVar[int]
    MAX_HTLC_MSAT_FIELD_NUMBER: _ClassVar[int]
    MIN_HTLC_MSAT_FIELD_NUMBER: _ClassVar[int]
    MIN_HTLC_MSAT_SPECIFIED_FIELD_NUMBER: _ClassVar[int]
    INBOUND_FEE_FIELD_NUMBER: _ClassVar[int]
    CREATE_MISSING_EDGE_FIELD_NUMBER: _ClassVar[int]
    chan_point: ChannelPoint
    base_fee_msat: int
    fee_rate: float
    fee_rate_ppm: int
    time_lock_delta: int
    max_htlc_msat: int
    min_htlc_msat: int
    min_htlc_msat_specified: bool
    inbound_fee: InboundFee
    create_missing_edge: bool
    def __init__(self, chan_point: _Optional[_Union[ChannelPoint, _Mapping]] = ..., base_fee_msat: _Optional[int] = ..., fee_rate: _Optional[float] = ..., fee_rate_ppm: _Optional[int] = ..., time_lock_delta: _Optional[int] = ..., max_htlc_msat: _Optional[int] = ..., min_htlc_msat: _Optional[int] = ..., min_htlc_msat_specified: bool = ..., inbound_fee: _Optional[_Union[InboundFee, _Mapping]] = ..., create_missing_edge: bool = ..., **kwargs) -> None: ...

class FailedUpdate(_message.Message):
    __slots__ = ("outpoint", "reason", "update_error")
    OUTPOINT_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    UPDATE_ERROR_FIELD_NUMBER: _ClassVar[int]
    outpoint: OutPoint
    reason: UpdateFailure
    update_error: str
    def __init__(self, outpoint: _Optional[_Union[OutPoint, _Mapping]] = ..., reason: _Optional[_Union[UpdateFailure, str]] = ..., update_error: _Optional[str] = ...) -> None: ...

class PolicyUpdateResponse(_message.Message):
    __slots__ = ("failed_updates",)
    FAILED_UPDATES_FIELD_NUMBER: _ClassVar[int]
    failed_updates: _containers.RepeatedCompositeFieldContainer[FailedUpdate]
    def __init__(self, failed_updates: _Optional[_Iterable[_Union[FailedUpdate, _Mapping]]] = ...) -> None: ...

class ForwardingHistoryRequest(_message.Message):
    __slots__ = ("start_time", "end_time", "index_offset", "num_max_events", "peer_alias_lookup", "incoming_chan_ids", "outgoing_chan_ids")
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    INDEX_OFFSET_FIELD_NUMBER: _ClassVar[int]
    NUM_MAX_EVENTS_FIELD_NUMBER: _ClassVar[int]
    PEER_ALIAS_LOOKUP_FIELD_NUMBER: _ClassVar[int]
    INCOMING_CHAN_IDS_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_CHAN_IDS_FIELD_NUMBER: _ClassVar[int]
    start_time: int
    end_time: int
    index_offset: int
    num_max_events: int
    peer_alias_lookup: bool
    incoming_chan_ids: _containers.RepeatedScalarFieldContainer[int]
    outgoing_chan_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, start_time: _Optional[int] = ..., end_time: _Optional[int] = ..., index_offset: _Optional[int] = ..., num_max_events: _Optional[int] = ..., peer_alias_lookup: bool = ..., incoming_chan_ids: _Optional[_Iterable[int]] = ..., outgoing_chan_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class ForwardingEvent(_message.Message):
    __slots__ = ("timestamp", "chan_id_in", "chan_id_out", "amt_in", "amt_out", "fee", "fee_msat", "amt_in_msat", "amt_out_msat", "timestamp_ns", "peer_alias_in", "peer_alias_out", "incoming_htlc_id", "outgoing_htlc_id")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    CHAN_ID_IN_FIELD_NUMBER: _ClassVar[int]
    CHAN_ID_OUT_FIELD_NUMBER: _ClassVar[int]
    AMT_IN_FIELD_NUMBER: _ClassVar[int]
    AMT_OUT_FIELD_NUMBER: _ClassVar[int]
    FEE_FIELD_NUMBER: _ClassVar[int]
    FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    AMT_IN_MSAT_FIELD_NUMBER: _ClassVar[int]
    AMT_OUT_MSAT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_NS_FIELD_NUMBER: _ClassVar[int]
    PEER_ALIAS_IN_FIELD_NUMBER: _ClassVar[int]
    PEER_ALIAS_OUT_FIELD_NUMBER: _ClassVar[int]
    INCOMING_HTLC_ID_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_HTLC_ID_FIELD_NUMBER: _ClassVar[int]
    timestamp: int
    chan_id_in: int
    chan_id_out: int
    amt_in: int
    amt_out: int
    fee: int
    fee_msat: int
    amt_in_msat: int
    amt_out_msat: int
    timestamp_ns: int
    peer_alias_in: str
    peer_alias_out: str
    incoming_htlc_id: int
    outgoing_htlc_id: int
    def __init__(self, timestamp: _Optional[int] = ..., chan_id_in: _Optional[int] = ..., chan_id_out: _Optional[int] = ..., amt_in: _Optional[int] = ..., amt_out: _Optional[int] = ..., fee: _Optional[int] = ..., fee_msat: _Optional[int] = ..., amt_in_msat: _Optional[int] = ..., amt_out_msat: _Optional[int] = ..., timestamp_ns: _Optional[int] = ..., peer_alias_in: _Optional[str] = ..., peer_alias_out: _Optional[str] = ..., incoming_htlc_id: _Optional[int] = ..., outgoing_htlc_id: _Optional[int] = ...) -> None: ...

class ForwardingHistoryResponse(_message.Message):
    __slots__ = ("forwarding_events", "last_offset_index")
    FORWARDING_EVENTS_FIELD_NUMBER: _ClassVar[int]
    LAST_OFFSET_INDEX_FIELD_NUMBER: _ClassVar[int]
    forwarding_events: _containers.RepeatedCompositeFieldContainer[ForwardingEvent]
    last_offset_index: int
    def __init__(self, forwarding_events: _Optional[_Iterable[_Union[ForwardingEvent, _Mapping]]] = ..., last_offset_index: _Optional[int] = ...) -> None: ...

class ExportChannelBackupRequest(_message.Message):
    __slots__ = ("chan_point",)
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    chan_point: ChannelPoint
    def __init__(self, chan_point: _Optional[_Union[ChannelPoint, _Mapping]] = ...) -> None: ...

class ChannelBackup(_message.Message):
    __slots__ = ("chan_point", "chan_backup")
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    CHAN_BACKUP_FIELD_NUMBER: _ClassVar[int]
    chan_point: ChannelPoint
    chan_backup: bytes
    def __init__(self, chan_point: _Optional[_Union[ChannelPoint, _Mapping]] = ..., chan_backup: _Optional[bytes] = ...) -> None: ...

class MultiChanBackup(_message.Message):
    __slots__ = ("chan_points", "multi_chan_backup")
    CHAN_POINTS_FIELD_NUMBER: _ClassVar[int]
    MULTI_CHAN_BACKUP_FIELD_NUMBER: _ClassVar[int]
    chan_points: _containers.RepeatedCompositeFieldContainer[ChannelPoint]
    multi_chan_backup: bytes
    def __init__(self, chan_points: _Optional[_Iterable[_Union[ChannelPoint, _Mapping]]] = ..., multi_chan_backup: _Optional[bytes] = ...) -> None: ...

class ChanBackupExportRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ChanBackupSnapshot(_message.Message):
    __slots__ = ("single_chan_backups", "multi_chan_backup")
    SINGLE_CHAN_BACKUPS_FIELD_NUMBER: _ClassVar[int]
    MULTI_CHAN_BACKUP_FIELD_NUMBER: _ClassVar[int]
    single_chan_backups: ChannelBackups
    multi_chan_backup: MultiChanBackup
    def __init__(self, single_chan_backups: _Optional[_Union[ChannelBackups, _Mapping]] = ..., multi_chan_backup: _Optional[_Union[MultiChanBackup, _Mapping]] = ...) -> None: ...

class ChannelBackups(_message.Message):
    __slots__ = ("chan_backups",)
    CHAN_BACKUPS_FIELD_NUMBER: _ClassVar[int]
    chan_backups: _containers.RepeatedCompositeFieldContainer[ChannelBackup]
    def __init__(self, chan_backups: _Optional[_Iterable[_Union[ChannelBackup, _Mapping]]] = ...) -> None: ...

class RestoreChanBackupRequest(_message.Message):
    __slots__ = ("chan_backups", "multi_chan_backup")
    CHAN_BACKUPS_FIELD_NUMBER: _ClassVar[int]
    MULTI_CHAN_BACKUP_FIELD_NUMBER: _ClassVar[int]
    chan_backups: ChannelBackups
    multi_chan_backup: bytes
    def __init__(self, chan_backups: _Optional[_Union[ChannelBackups, _Mapping]] = ..., multi_chan_backup: _Optional[bytes] = ...) -> None: ...

class RestoreBackupResponse(_message.Message):
    __slots__ = ("num_restored",)
    NUM_RESTORED_FIELD_NUMBER: _ClassVar[int]
    num_restored: int
    def __init__(self, num_restored: _Optional[int] = ...) -> None: ...

class ChannelBackupSubscription(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class VerifyChanBackupResponse(_message.Message):
    __slots__ = ("chan_points",)
    CHAN_POINTS_FIELD_NUMBER: _ClassVar[int]
    chan_points: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, chan_points: _Optional[_Iterable[str]] = ...) -> None: ...

class MacaroonPermission(_message.Message):
    __slots__ = ("entity", "action")
    ENTITY_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    entity: str
    action: str
    def __init__(self, entity: _Optional[str] = ..., action: _Optional[str] = ...) -> None: ...

class BakeMacaroonRequest(_message.Message):
    __slots__ = ("permissions", "root_key_id", "allow_external_permissions")
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    ROOT_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    ALLOW_EXTERNAL_PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    permissions: _containers.RepeatedCompositeFieldContainer[MacaroonPermission]
    root_key_id: int
    allow_external_permissions: bool
    def __init__(self, permissions: _Optional[_Iterable[_Union[MacaroonPermission, _Mapping]]] = ..., root_key_id: _Optional[int] = ..., allow_external_permissions: bool = ...) -> None: ...

class BakeMacaroonResponse(_message.Message):
    __slots__ = ("macaroon",)
    MACAROON_FIELD_NUMBER: _ClassVar[int]
    macaroon: str
    def __init__(self, macaroon: _Optional[str] = ...) -> None: ...

class ListMacaroonIDsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListMacaroonIDsResponse(_message.Message):
    __slots__ = ("root_key_ids",)
    ROOT_KEY_IDS_FIELD_NUMBER: _ClassVar[int]
    root_key_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, root_key_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class DeleteMacaroonIDRequest(_message.Message):
    __slots__ = ("root_key_id",)
    ROOT_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    root_key_id: int
    def __init__(self, root_key_id: _Optional[int] = ...) -> None: ...

class DeleteMacaroonIDResponse(_message.Message):
    __slots__ = ("deleted",)
    DELETED_FIELD_NUMBER: _ClassVar[int]
    deleted: bool
    def __init__(self, deleted: bool = ...) -> None: ...

class MacaroonPermissionList(_message.Message):
    __slots__ = ("permissions",)
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    permissions: _containers.RepeatedCompositeFieldContainer[MacaroonPermission]
    def __init__(self, permissions: _Optional[_Iterable[_Union[MacaroonPermission, _Mapping]]] = ...) -> None: ...

class ListPermissionsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListPermissionsResponse(_message.Message):
    __slots__ = ("method_permissions",)
    class MethodPermissionsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: MacaroonPermissionList
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[MacaroonPermissionList, _Mapping]] = ...) -> None: ...
    METHOD_PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    method_permissions: _containers.MessageMap[str, MacaroonPermissionList]
    def __init__(self, method_permissions: _Optional[_Mapping[str, MacaroonPermissionList]] = ...) -> None: ...

class Failure(_message.Message):
    __slots__ = ("code", "channel_update", "htlc_msat", "onion_sha_256", "cltv_expiry", "flags", "failure_source_index", "height")
    class FailureCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RESERVED: _ClassVar[Failure.FailureCode]
        INCORRECT_OR_UNKNOWN_PAYMENT_DETAILS: _ClassVar[Failure.FailureCode]
        INCORRECT_PAYMENT_AMOUNT: _ClassVar[Failure.FailureCode]
        FINAL_INCORRECT_CLTV_EXPIRY: _ClassVar[Failure.FailureCode]
        FINAL_INCORRECT_HTLC_AMOUNT: _ClassVar[Failure.FailureCode]
        FINAL_EXPIRY_TOO_SOON: _ClassVar[Failure.FailureCode]
        INVALID_REALM: _ClassVar[Failure.FailureCode]
        EXPIRY_TOO_SOON: _ClassVar[Failure.FailureCode]
        INVALID_ONION_VERSION: _ClassVar[Failure.FailureCode]
        INVALID_ONION_HMAC: _ClassVar[Failure.FailureCode]
        INVALID_ONION_KEY: _ClassVar[Failure.FailureCode]
        AMOUNT_BELOW_MINIMUM: _ClassVar[Failure.FailureCode]
        FEE_INSUFFICIENT: _ClassVar[Failure.FailureCode]
        INCORRECT_CLTV_EXPIRY: _ClassVar[Failure.FailureCode]
        CHANNEL_DISABLED: _ClassVar[Failure.FailureCode]
        TEMPORARY_CHANNEL_FAILURE: _ClassVar[Failure.FailureCode]
        REQUIRED_NODE_FEATURE_MISSING: _ClassVar[Failure.FailureCode]
        REQUIRED_CHANNEL_FEATURE_MISSING: _ClassVar[Failure.FailureCode]
        UNKNOWN_NEXT_PEER: _ClassVar[Failure.FailureCode]
        TEMPORARY_NODE_FAILURE: _ClassVar[Failure.FailureCode]
        PERMANENT_NODE_FAILURE: _ClassVar[Failure.FailureCode]
        PERMANENT_CHANNEL_FAILURE: _ClassVar[Failure.FailureCode]
        EXPIRY_TOO_FAR: _ClassVar[Failure.FailureCode]
        MPP_TIMEOUT: _ClassVar[Failure.FailureCode]
        INVALID_ONION_PAYLOAD: _ClassVar[Failure.FailureCode]
        INVALID_ONION_BLINDING: _ClassVar[Failure.FailureCode]
        INTERNAL_FAILURE: _ClassVar[Failure.FailureCode]
        UNKNOWN_FAILURE: _ClassVar[Failure.FailureCode]
        UNREADABLE_FAILURE: _ClassVar[Failure.FailureCode]
    RESERVED: Failure.FailureCode
    INCORRECT_OR_UNKNOWN_PAYMENT_DETAILS: Failure.FailureCode
    INCORRECT_PAYMENT_AMOUNT: Failure.FailureCode
    FINAL_INCORRECT_CLTV_EXPIRY: Failure.FailureCode
    FINAL_INCORRECT_HTLC_AMOUNT: Failure.FailureCode
    FINAL_EXPIRY_TOO_SOON: Failure.FailureCode
    INVALID_REALM: Failure.FailureCode
    EXPIRY_TOO_SOON: Failure.FailureCode
    INVALID_ONION_VERSION: Failure.FailureCode
    INVALID_ONION_HMAC: Failure.FailureCode
    INVALID_ONION_KEY: Failure.FailureCode
    AMOUNT_BELOW_MINIMUM: Failure.FailureCode
    FEE_INSUFFICIENT: Failure.FailureCode
    INCORRECT_CLTV_EXPIRY: Failure.FailureCode
    CHANNEL_DISABLED: Failure.FailureCode
    TEMPORARY_CHANNEL_FAILURE: Failure.FailureCode
    REQUIRED_NODE_FEATURE_MISSING: Failure.FailureCode
    REQUIRED_CHANNEL_FEATURE_MISSING: Failure.FailureCode
    UNKNOWN_NEXT_PEER: Failure.FailureCode
    TEMPORARY_NODE_FAILURE: Failure.FailureCode
    PERMANENT_NODE_FAILURE: Failure.FailureCode
    PERMANENT_CHANNEL_FAILURE: Failure.FailureCode
    EXPIRY_TOO_FAR: Failure.FailureCode
    MPP_TIMEOUT: Failure.FailureCode
    INVALID_ONION_PAYLOAD: Failure.FailureCode
    INVALID_ONION_BLINDING: Failure.FailureCode
    INTERNAL_FAILURE: Failure.FailureCode
    UNKNOWN_FAILURE: Failure.FailureCode
    UNREADABLE_FAILURE: Failure.FailureCode
    CODE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_UPDATE_FIELD_NUMBER: _ClassVar[int]
    HTLC_MSAT_FIELD_NUMBER: _ClassVar[int]
    ONION_SHA_256_FIELD_NUMBER: _ClassVar[int]
    CLTV_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    FLAGS_FIELD_NUMBER: _ClassVar[int]
    FAILURE_SOURCE_INDEX_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    code: Failure.FailureCode
    channel_update: ChannelUpdate
    htlc_msat: int
    onion_sha_256: bytes
    cltv_expiry: int
    flags: int
    failure_source_index: int
    height: int
    def __init__(self, code: _Optional[_Union[Failure.FailureCode, str]] = ..., channel_update: _Optional[_Union[ChannelUpdate, _Mapping]] = ..., htlc_msat: _Optional[int] = ..., onion_sha_256: _Optional[bytes] = ..., cltv_expiry: _Optional[int] = ..., flags: _Optional[int] = ..., failure_source_index: _Optional[int] = ..., height: _Optional[int] = ...) -> None: ...

class ChannelUpdate(_message.Message):
    __slots__ = ("signature", "chain_hash", "chan_id", "timestamp", "message_flags", "channel_flags", "time_lock_delta", "htlc_minimum_msat", "base_fee", "fee_rate", "htlc_maximum_msat", "extra_opaque_data")
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    CHAIN_HASH_FIELD_NUMBER: _ClassVar[int]
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FLAGS_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FLAGS_FIELD_NUMBER: _ClassVar[int]
    TIME_LOCK_DELTA_FIELD_NUMBER: _ClassVar[int]
    HTLC_MINIMUM_MSAT_FIELD_NUMBER: _ClassVar[int]
    BASE_FEE_FIELD_NUMBER: _ClassVar[int]
    FEE_RATE_FIELD_NUMBER: _ClassVar[int]
    HTLC_MAXIMUM_MSAT_FIELD_NUMBER: _ClassVar[int]
    EXTRA_OPAQUE_DATA_FIELD_NUMBER: _ClassVar[int]
    signature: bytes
    chain_hash: bytes
    chan_id: int
    timestamp: int
    message_flags: int
    channel_flags: int
    time_lock_delta: int
    htlc_minimum_msat: int
    base_fee: int
    fee_rate: int
    htlc_maximum_msat: int
    extra_opaque_data: bytes
    def __init__(self, signature: _Optional[bytes] = ..., chain_hash: _Optional[bytes] = ..., chan_id: _Optional[int] = ..., timestamp: _Optional[int] = ..., message_flags: _Optional[int] = ..., channel_flags: _Optional[int] = ..., time_lock_delta: _Optional[int] = ..., htlc_minimum_msat: _Optional[int] = ..., base_fee: _Optional[int] = ..., fee_rate: _Optional[int] = ..., htlc_maximum_msat: _Optional[int] = ..., extra_opaque_data: _Optional[bytes] = ...) -> None: ...

class MacaroonId(_message.Message):
    __slots__ = ("nonce", "storageId", "ops")
    NONCE_FIELD_NUMBER: _ClassVar[int]
    STORAGEID_FIELD_NUMBER: _ClassVar[int]
    OPS_FIELD_NUMBER: _ClassVar[int]
    nonce: bytes
    storageId: bytes
    ops: _containers.RepeatedCompositeFieldContainer[Op]
    def __init__(self, nonce: _Optional[bytes] = ..., storageId: _Optional[bytes] = ..., ops: _Optional[_Iterable[_Union[Op, _Mapping]]] = ...) -> None: ...

class Op(_message.Message):
    __slots__ = ("entity", "actions")
    ENTITY_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    entity: str
    actions: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, entity: _Optional[str] = ..., actions: _Optional[_Iterable[str]] = ...) -> None: ...

class CheckMacPermRequest(_message.Message):
    __slots__ = ("macaroon", "permissions", "fullMethod", "check_default_perms_from_full_method")
    MACAROON_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    FULLMETHOD_FIELD_NUMBER: _ClassVar[int]
    CHECK_DEFAULT_PERMS_FROM_FULL_METHOD_FIELD_NUMBER: _ClassVar[int]
    macaroon: bytes
    permissions: _containers.RepeatedCompositeFieldContainer[MacaroonPermission]
    fullMethod: str
    check_default_perms_from_full_method: bool
    def __init__(self, macaroon: _Optional[bytes] = ..., permissions: _Optional[_Iterable[_Union[MacaroonPermission, _Mapping]]] = ..., fullMethod: _Optional[str] = ..., check_default_perms_from_full_method: bool = ...) -> None: ...

class CheckMacPermResponse(_message.Message):
    __slots__ = ("valid",)
    VALID_FIELD_NUMBER: _ClassVar[int]
    valid: bool
    def __init__(self, valid: bool = ...) -> None: ...

class RPCMiddlewareRequest(_message.Message):
    __slots__ = ("request_id", "raw_macaroon", "custom_caveat_condition", "stream_auth", "request", "response", "reg_complete", "msg_id", "metadata_pairs")
    class MetadataPairsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: MetadataValues
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[MetadataValues, _Mapping]] = ...) -> None: ...
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    RAW_MACAROON_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_CAVEAT_CONDITION_FIELD_NUMBER: _ClassVar[int]
    STREAM_AUTH_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    REG_COMPLETE_FIELD_NUMBER: _ClassVar[int]
    MSG_ID_FIELD_NUMBER: _ClassVar[int]
    METADATA_PAIRS_FIELD_NUMBER: _ClassVar[int]
    request_id: int
    raw_macaroon: bytes
    custom_caveat_condition: str
    stream_auth: StreamAuth
    request: RPCMessage
    response: RPCMessage
    reg_complete: bool
    msg_id: int
    metadata_pairs: _containers.MessageMap[str, MetadataValues]
    def __init__(self, request_id: _Optional[int] = ..., raw_macaroon: _Optional[bytes] = ..., custom_caveat_condition: _Optional[str] = ..., stream_auth: _Optional[_Union[StreamAuth, _Mapping]] = ..., request: _Optional[_Union[RPCMessage, _Mapping]] = ..., response: _Optional[_Union[RPCMessage, _Mapping]] = ..., reg_complete: bool = ..., msg_id: _Optional[int] = ..., metadata_pairs: _Optional[_Mapping[str, MetadataValues]] = ...) -> None: ...

class MetadataValues(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, values: _Optional[_Iterable[str]] = ...) -> None: ...

class StreamAuth(_message.Message):
    __slots__ = ("method_full_uri",)
    METHOD_FULL_URI_FIELD_NUMBER: _ClassVar[int]
    method_full_uri: str
    def __init__(self, method_full_uri: _Optional[str] = ...) -> None: ...

class RPCMessage(_message.Message):
    __slots__ = ("method_full_uri", "stream_rpc", "type_name", "serialized", "is_error")
    METHOD_FULL_URI_FIELD_NUMBER: _ClassVar[int]
    STREAM_RPC_FIELD_NUMBER: _ClassVar[int]
    TYPE_NAME_FIELD_NUMBER: _ClassVar[int]
    SERIALIZED_FIELD_NUMBER: _ClassVar[int]
    IS_ERROR_FIELD_NUMBER: _ClassVar[int]
    method_full_uri: str
    stream_rpc: bool
    type_name: str
    serialized: bytes
    is_error: bool
    def __init__(self, method_full_uri: _Optional[str] = ..., stream_rpc: bool = ..., type_name: _Optional[str] = ..., serialized: _Optional[bytes] = ..., is_error: bool = ...) -> None: ...

class RPCMiddlewareResponse(_message.Message):
    __slots__ = ("ref_msg_id", "register", "feedback")
    REF_MSG_ID_FIELD_NUMBER: _ClassVar[int]
    REGISTER_FIELD_NUMBER: _ClassVar[int]
    FEEDBACK_FIELD_NUMBER: _ClassVar[int]
    ref_msg_id: int
    register: MiddlewareRegistration
    feedback: InterceptFeedback
    def __init__(self, ref_msg_id: _Optional[int] = ..., register: _Optional[_Union[MiddlewareRegistration, _Mapping]] = ..., feedback: _Optional[_Union[InterceptFeedback, _Mapping]] = ...) -> None: ...

class MiddlewareRegistration(_message.Message):
    __slots__ = ("middleware_name", "custom_macaroon_caveat_name", "read_only_mode")
    MIDDLEWARE_NAME_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_MACAROON_CAVEAT_NAME_FIELD_NUMBER: _ClassVar[int]
    READ_ONLY_MODE_FIELD_NUMBER: _ClassVar[int]
    middleware_name: str
    custom_macaroon_caveat_name: str
    read_only_mode: bool
    def __init__(self, middleware_name: _Optional[str] = ..., custom_macaroon_caveat_name: _Optional[str] = ..., read_only_mode: bool = ...) -> None: ...

class InterceptFeedback(_message.Message):
    __slots__ = ("error", "replace_response", "replacement_serialized")
    ERROR_FIELD_NUMBER: _ClassVar[int]
    REPLACE_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    REPLACEMENT_SERIALIZED_FIELD_NUMBER: _ClassVar[int]
    error: str
    replace_response: bool
    replacement_serialized: bytes
    def __init__(self, error: _Optional[str] = ..., replace_response: bool = ..., replacement_serialized: _Optional[bytes] = ...) -> None: ...
