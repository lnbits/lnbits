import lnbits.wallets.lnd_grpc_files.lightning_pb2 as _lightning_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FailureDetail(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNKNOWN: _ClassVar[FailureDetail]
    NO_DETAIL: _ClassVar[FailureDetail]
    ONION_DECODE: _ClassVar[FailureDetail]
    LINK_NOT_ELIGIBLE: _ClassVar[FailureDetail]
    ON_CHAIN_TIMEOUT: _ClassVar[FailureDetail]
    HTLC_EXCEEDS_MAX: _ClassVar[FailureDetail]
    INSUFFICIENT_BALANCE: _ClassVar[FailureDetail]
    INCOMPLETE_FORWARD: _ClassVar[FailureDetail]
    HTLC_ADD_FAILED: _ClassVar[FailureDetail]
    FORWARDS_DISABLED: _ClassVar[FailureDetail]
    INVOICE_CANCELED: _ClassVar[FailureDetail]
    INVOICE_UNDERPAID: _ClassVar[FailureDetail]
    INVOICE_EXPIRY_TOO_SOON: _ClassVar[FailureDetail]
    INVOICE_NOT_OPEN: _ClassVar[FailureDetail]
    MPP_INVOICE_TIMEOUT: _ClassVar[FailureDetail]
    ADDRESS_MISMATCH: _ClassVar[FailureDetail]
    SET_TOTAL_MISMATCH: _ClassVar[FailureDetail]
    SET_TOTAL_TOO_LOW: _ClassVar[FailureDetail]
    SET_OVERPAID: _ClassVar[FailureDetail]
    UNKNOWN_INVOICE: _ClassVar[FailureDetail]
    INVALID_KEYSEND: _ClassVar[FailureDetail]
    MPP_IN_PROGRESS: _ClassVar[FailureDetail]
    CIRCULAR_ROUTE: _ClassVar[FailureDetail]

class PaymentState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    IN_FLIGHT: _ClassVar[PaymentState]
    SUCCEEDED: _ClassVar[PaymentState]
    FAILED_TIMEOUT: _ClassVar[PaymentState]
    FAILED_NO_ROUTE: _ClassVar[PaymentState]
    FAILED_ERROR: _ClassVar[PaymentState]
    FAILED_INCORRECT_PAYMENT_DETAILS: _ClassVar[PaymentState]
    FAILED_INSUFFICIENT_BALANCE: _ClassVar[PaymentState]

class ResolveHoldForwardAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SETTLE: _ClassVar[ResolveHoldForwardAction]
    FAIL: _ClassVar[ResolveHoldForwardAction]
    RESUME: _ClassVar[ResolveHoldForwardAction]
    RESUME_MODIFIED: _ClassVar[ResolveHoldForwardAction]

class ChanStatusAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ENABLE: _ClassVar[ChanStatusAction]
    DISABLE: _ClassVar[ChanStatusAction]
    AUTO: _ClassVar[ChanStatusAction]
UNKNOWN: FailureDetail
NO_DETAIL: FailureDetail
ONION_DECODE: FailureDetail
LINK_NOT_ELIGIBLE: FailureDetail
ON_CHAIN_TIMEOUT: FailureDetail
HTLC_EXCEEDS_MAX: FailureDetail
INSUFFICIENT_BALANCE: FailureDetail
INCOMPLETE_FORWARD: FailureDetail
HTLC_ADD_FAILED: FailureDetail
FORWARDS_DISABLED: FailureDetail
INVOICE_CANCELED: FailureDetail
INVOICE_UNDERPAID: FailureDetail
INVOICE_EXPIRY_TOO_SOON: FailureDetail
INVOICE_NOT_OPEN: FailureDetail
MPP_INVOICE_TIMEOUT: FailureDetail
ADDRESS_MISMATCH: FailureDetail
SET_TOTAL_MISMATCH: FailureDetail
SET_TOTAL_TOO_LOW: FailureDetail
SET_OVERPAID: FailureDetail
UNKNOWN_INVOICE: FailureDetail
INVALID_KEYSEND: FailureDetail
MPP_IN_PROGRESS: FailureDetail
CIRCULAR_ROUTE: FailureDetail
IN_FLIGHT: PaymentState
SUCCEEDED: PaymentState
FAILED_TIMEOUT: PaymentState
FAILED_NO_ROUTE: PaymentState
FAILED_ERROR: PaymentState
FAILED_INCORRECT_PAYMENT_DETAILS: PaymentState
FAILED_INSUFFICIENT_BALANCE: PaymentState
SETTLE: ResolveHoldForwardAction
FAIL: ResolveHoldForwardAction
RESUME: ResolveHoldForwardAction
RESUME_MODIFIED: ResolveHoldForwardAction
ENABLE: ChanStatusAction
DISABLE: ChanStatusAction
AUTO: ChanStatusAction

class SendPaymentRequest(_message.Message):
    __slots__ = ("dest", "amt", "payment_hash", "final_cltv_delta", "payment_request", "timeout_seconds", "fee_limit_sat", "outgoing_chan_id", "cltv_limit", "route_hints", "dest_custom_records", "amt_msat", "fee_limit_msat", "last_hop_pubkey", "allow_self_payment", "dest_features", "max_parts", "no_inflight_updates", "outgoing_chan_ids", "payment_addr", "max_shard_size_msat", "amp", "time_pref", "cancelable", "first_hop_custom_records")
    class DestCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    class FirstHopCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    DEST_FIELD_NUMBER: _ClassVar[int]
    AMT_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    FINAL_CLTV_DELTA_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    FEE_LIMIT_SAT_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    CLTV_LIMIT_FIELD_NUMBER: _ClassVar[int]
    ROUTE_HINTS_FIELD_NUMBER: _ClassVar[int]
    DEST_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    FEE_LIMIT_MSAT_FIELD_NUMBER: _ClassVar[int]
    LAST_HOP_PUBKEY_FIELD_NUMBER: _ClassVar[int]
    ALLOW_SELF_PAYMENT_FIELD_NUMBER: _ClassVar[int]
    DEST_FEATURES_FIELD_NUMBER: _ClassVar[int]
    MAX_PARTS_FIELD_NUMBER: _ClassVar[int]
    NO_INFLIGHT_UPDATES_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_CHAN_IDS_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    MAX_SHARD_SIZE_MSAT_FIELD_NUMBER: _ClassVar[int]
    AMP_FIELD_NUMBER: _ClassVar[int]
    TIME_PREF_FIELD_NUMBER: _ClassVar[int]
    CANCELABLE_FIELD_NUMBER: _ClassVar[int]
    FIRST_HOP_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    dest: bytes
    amt: int
    payment_hash: bytes
    final_cltv_delta: int
    payment_request: str
    timeout_seconds: int
    fee_limit_sat: int
    outgoing_chan_id: int
    cltv_limit: int
    route_hints: _containers.RepeatedCompositeFieldContainer[_lightning_pb2.RouteHint]
    dest_custom_records: _containers.ScalarMap[int, bytes]
    amt_msat: int
    fee_limit_msat: int
    last_hop_pubkey: bytes
    allow_self_payment: bool
    dest_features: _containers.RepeatedScalarFieldContainer[_lightning_pb2.FeatureBit]
    max_parts: int
    no_inflight_updates: bool
    outgoing_chan_ids: _containers.RepeatedScalarFieldContainer[int]
    payment_addr: bytes
    max_shard_size_msat: int
    amp: bool
    time_pref: float
    cancelable: bool
    first_hop_custom_records: _containers.ScalarMap[int, bytes]
    def __init__(self, dest: _Optional[bytes] = ..., amt: _Optional[int] = ..., payment_hash: _Optional[bytes] = ..., final_cltv_delta: _Optional[int] = ..., payment_request: _Optional[str] = ..., timeout_seconds: _Optional[int] = ..., fee_limit_sat: _Optional[int] = ..., outgoing_chan_id: _Optional[int] = ..., cltv_limit: _Optional[int] = ..., route_hints: _Optional[_Iterable[_Union[_lightning_pb2.RouteHint, _Mapping]]] = ..., dest_custom_records: _Optional[_Mapping[int, bytes]] = ..., amt_msat: _Optional[int] = ..., fee_limit_msat: _Optional[int] = ..., last_hop_pubkey: _Optional[bytes] = ..., allow_self_payment: bool = ..., dest_features: _Optional[_Iterable[_Union[_lightning_pb2.FeatureBit, str]]] = ..., max_parts: _Optional[int] = ..., no_inflight_updates: bool = ..., outgoing_chan_ids: _Optional[_Iterable[int]] = ..., payment_addr: _Optional[bytes] = ..., max_shard_size_msat: _Optional[int] = ..., amp: bool = ..., time_pref: _Optional[float] = ..., cancelable: bool = ..., first_hop_custom_records: _Optional[_Mapping[int, bytes]] = ...) -> None: ...

class TrackPaymentRequest(_message.Message):
    __slots__ = ("payment_hash", "no_inflight_updates")
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    NO_INFLIGHT_UPDATES_FIELD_NUMBER: _ClassVar[int]
    payment_hash: bytes
    no_inflight_updates: bool
    def __init__(self, payment_hash: _Optional[bytes] = ..., no_inflight_updates: bool = ...) -> None: ...

class TrackPaymentsRequest(_message.Message):
    __slots__ = ("no_inflight_updates",)
    NO_INFLIGHT_UPDATES_FIELD_NUMBER: _ClassVar[int]
    no_inflight_updates: bool
    def __init__(self, no_inflight_updates: bool = ...) -> None: ...

class RouteFeeRequest(_message.Message):
    __slots__ = ("dest", "amt_sat", "payment_request", "timeout")
    DEST_FIELD_NUMBER: _ClassVar[int]
    AMT_SAT_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    dest: bytes
    amt_sat: int
    payment_request: str
    timeout: int
    def __init__(self, dest: _Optional[bytes] = ..., amt_sat: _Optional[int] = ..., payment_request: _Optional[str] = ..., timeout: _Optional[int] = ...) -> None: ...

class RouteFeeResponse(_message.Message):
    __slots__ = ("routing_fee_msat", "time_lock_delay", "failure_reason")
    ROUTING_FEE_MSAT_FIELD_NUMBER: _ClassVar[int]
    TIME_LOCK_DELAY_FIELD_NUMBER: _ClassVar[int]
    FAILURE_REASON_FIELD_NUMBER: _ClassVar[int]
    routing_fee_msat: int
    time_lock_delay: int
    failure_reason: _lightning_pb2.PaymentFailureReason
    def __init__(self, routing_fee_msat: _Optional[int] = ..., time_lock_delay: _Optional[int] = ..., failure_reason: _Optional[_Union[_lightning_pb2.PaymentFailureReason, str]] = ...) -> None: ...

class SendToRouteRequest(_message.Message):
    __slots__ = ("payment_hash", "route", "skip_temp_err", "first_hop_custom_records")
    class FirstHopCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    ROUTE_FIELD_NUMBER: _ClassVar[int]
    SKIP_TEMP_ERR_FIELD_NUMBER: _ClassVar[int]
    FIRST_HOP_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    payment_hash: bytes
    route: _lightning_pb2.Route
    skip_temp_err: bool
    first_hop_custom_records: _containers.ScalarMap[int, bytes]
    def __init__(self, payment_hash: _Optional[bytes] = ..., route: _Optional[_Union[_lightning_pb2.Route, _Mapping]] = ..., skip_temp_err: bool = ..., first_hop_custom_records: _Optional[_Mapping[int, bytes]] = ...) -> None: ...

class SendToRouteResponse(_message.Message):
    __slots__ = ("preimage", "failure")
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    preimage: bytes
    failure: _lightning_pb2.Failure
    def __init__(self, preimage: _Optional[bytes] = ..., failure: _Optional[_Union[_lightning_pb2.Failure, _Mapping]] = ...) -> None: ...

class ResetMissionControlRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ResetMissionControlResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class QueryMissionControlRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class QueryMissionControlResponse(_message.Message):
    __slots__ = ("pairs",)
    PAIRS_FIELD_NUMBER: _ClassVar[int]
    pairs: _containers.RepeatedCompositeFieldContainer[PairHistory]
    def __init__(self, pairs: _Optional[_Iterable[_Union[PairHistory, _Mapping]]] = ...) -> None: ...

class XImportMissionControlRequest(_message.Message):
    __slots__ = ("pairs", "force")
    PAIRS_FIELD_NUMBER: _ClassVar[int]
    FORCE_FIELD_NUMBER: _ClassVar[int]
    pairs: _containers.RepeatedCompositeFieldContainer[PairHistory]
    force: bool
    def __init__(self, pairs: _Optional[_Iterable[_Union[PairHistory, _Mapping]]] = ..., force: bool = ...) -> None: ...

class XImportMissionControlResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PairHistory(_message.Message):
    __slots__ = ("node_from", "node_to", "history")
    NODE_FROM_FIELD_NUMBER: _ClassVar[int]
    NODE_TO_FIELD_NUMBER: _ClassVar[int]
    HISTORY_FIELD_NUMBER: _ClassVar[int]
    node_from: bytes
    node_to: bytes
    history: PairData
    def __init__(self, node_from: _Optional[bytes] = ..., node_to: _Optional[bytes] = ..., history: _Optional[_Union[PairData, _Mapping]] = ...) -> None: ...

class PairData(_message.Message):
    __slots__ = ("fail_time", "fail_amt_sat", "fail_amt_msat", "success_time", "success_amt_sat", "success_amt_msat")
    FAIL_TIME_FIELD_NUMBER: _ClassVar[int]
    FAIL_AMT_SAT_FIELD_NUMBER: _ClassVar[int]
    FAIL_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_TIME_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_AMT_SAT_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    fail_time: int
    fail_amt_sat: int
    fail_amt_msat: int
    success_time: int
    success_amt_sat: int
    success_amt_msat: int
    def __init__(self, fail_time: _Optional[int] = ..., fail_amt_sat: _Optional[int] = ..., fail_amt_msat: _Optional[int] = ..., success_time: _Optional[int] = ..., success_amt_sat: _Optional[int] = ..., success_amt_msat: _Optional[int] = ...) -> None: ...

class GetMissionControlConfigRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetMissionControlConfigResponse(_message.Message):
    __slots__ = ("config",)
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    config: MissionControlConfig
    def __init__(self, config: _Optional[_Union[MissionControlConfig, _Mapping]] = ...) -> None: ...

class SetMissionControlConfigRequest(_message.Message):
    __slots__ = ("config",)
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    config: MissionControlConfig
    def __init__(self, config: _Optional[_Union[MissionControlConfig, _Mapping]] = ...) -> None: ...

class SetMissionControlConfigResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class MissionControlConfig(_message.Message):
    __slots__ = ("half_life_seconds", "hop_probability", "weight", "maximum_payment_results", "minimum_failure_relax_interval", "model", "apriori", "bimodal")
    class ProbabilityModel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        APRIORI: _ClassVar[MissionControlConfig.ProbabilityModel]
        BIMODAL: _ClassVar[MissionControlConfig.ProbabilityModel]
    APRIORI: MissionControlConfig.ProbabilityModel
    BIMODAL: MissionControlConfig.ProbabilityModel
    HALF_LIFE_SECONDS_FIELD_NUMBER: _ClassVar[int]
    HOP_PROBABILITY_FIELD_NUMBER: _ClassVar[int]
    WEIGHT_FIELD_NUMBER: _ClassVar[int]
    MAXIMUM_PAYMENT_RESULTS_FIELD_NUMBER: _ClassVar[int]
    MINIMUM_FAILURE_RELAX_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    APRIORI_FIELD_NUMBER: _ClassVar[int]
    BIMODAL_FIELD_NUMBER: _ClassVar[int]
    half_life_seconds: int
    hop_probability: float
    weight: float
    maximum_payment_results: int
    minimum_failure_relax_interval: int
    model: MissionControlConfig.ProbabilityModel
    apriori: AprioriParameters
    bimodal: BimodalParameters
    def __init__(self, half_life_seconds: _Optional[int] = ..., hop_probability: _Optional[float] = ..., weight: _Optional[float] = ..., maximum_payment_results: _Optional[int] = ..., minimum_failure_relax_interval: _Optional[int] = ..., model: _Optional[_Union[MissionControlConfig.ProbabilityModel, str]] = ..., apriori: _Optional[_Union[AprioriParameters, _Mapping]] = ..., bimodal: _Optional[_Union[BimodalParameters, _Mapping]] = ...) -> None: ...

class BimodalParameters(_message.Message):
    __slots__ = ("node_weight", "scale_msat", "decay_time")
    NODE_WEIGHT_FIELD_NUMBER: _ClassVar[int]
    SCALE_MSAT_FIELD_NUMBER: _ClassVar[int]
    DECAY_TIME_FIELD_NUMBER: _ClassVar[int]
    node_weight: float
    scale_msat: int
    decay_time: int
    def __init__(self, node_weight: _Optional[float] = ..., scale_msat: _Optional[int] = ..., decay_time: _Optional[int] = ...) -> None: ...

class AprioriParameters(_message.Message):
    __slots__ = ("half_life_seconds", "hop_probability", "weight", "capacity_fraction")
    HALF_LIFE_SECONDS_FIELD_NUMBER: _ClassVar[int]
    HOP_PROBABILITY_FIELD_NUMBER: _ClassVar[int]
    WEIGHT_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FRACTION_FIELD_NUMBER: _ClassVar[int]
    half_life_seconds: int
    hop_probability: float
    weight: float
    capacity_fraction: float
    def __init__(self, half_life_seconds: _Optional[int] = ..., hop_probability: _Optional[float] = ..., weight: _Optional[float] = ..., capacity_fraction: _Optional[float] = ...) -> None: ...

class QueryProbabilityRequest(_message.Message):
    __slots__ = ("from_node", "to_node", "amt_msat")
    FROM_NODE_FIELD_NUMBER: _ClassVar[int]
    TO_NODE_FIELD_NUMBER: _ClassVar[int]
    AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    from_node: bytes
    to_node: bytes
    amt_msat: int
    def __init__(self, from_node: _Optional[bytes] = ..., to_node: _Optional[bytes] = ..., amt_msat: _Optional[int] = ...) -> None: ...

class QueryProbabilityResponse(_message.Message):
    __slots__ = ("probability", "history")
    PROBABILITY_FIELD_NUMBER: _ClassVar[int]
    HISTORY_FIELD_NUMBER: _ClassVar[int]
    probability: float
    history: PairData
    def __init__(self, probability: _Optional[float] = ..., history: _Optional[_Union[PairData, _Mapping]] = ...) -> None: ...

class BuildRouteRequest(_message.Message):
    __slots__ = ("amt_msat", "final_cltv_delta", "outgoing_chan_id", "hop_pubkeys", "payment_addr", "first_hop_custom_records")
    class FirstHopCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    FINAL_CLTV_DELTA_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    HOP_PUBKEYS_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    FIRST_HOP_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    amt_msat: int
    final_cltv_delta: int
    outgoing_chan_id: int
    hop_pubkeys: _containers.RepeatedScalarFieldContainer[bytes]
    payment_addr: bytes
    first_hop_custom_records: _containers.ScalarMap[int, bytes]
    def __init__(self, amt_msat: _Optional[int] = ..., final_cltv_delta: _Optional[int] = ..., outgoing_chan_id: _Optional[int] = ..., hop_pubkeys: _Optional[_Iterable[bytes]] = ..., payment_addr: _Optional[bytes] = ..., first_hop_custom_records: _Optional[_Mapping[int, bytes]] = ...) -> None: ...

class BuildRouteResponse(_message.Message):
    __slots__ = ("route",)
    ROUTE_FIELD_NUMBER: _ClassVar[int]
    route: _lightning_pb2.Route
    def __init__(self, route: _Optional[_Union[_lightning_pb2.Route, _Mapping]] = ...) -> None: ...

class SubscribeHtlcEventsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HtlcEvent(_message.Message):
    __slots__ = ("incoming_channel_id", "outgoing_channel_id", "incoming_htlc_id", "outgoing_htlc_id", "timestamp_ns", "event_type", "forward_event", "forward_fail_event", "settle_event", "link_fail_event", "subscribed_event", "final_htlc_event")
    class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNKNOWN: _ClassVar[HtlcEvent.EventType]
        SEND: _ClassVar[HtlcEvent.EventType]
        RECEIVE: _ClassVar[HtlcEvent.EventType]
        FORWARD: _ClassVar[HtlcEvent.EventType]
    UNKNOWN: HtlcEvent.EventType
    SEND: HtlcEvent.EventType
    RECEIVE: HtlcEvent.EventType
    FORWARD: HtlcEvent.EventType
    INCOMING_CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    INCOMING_HTLC_ID_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_HTLC_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_NS_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    FORWARD_EVENT_FIELD_NUMBER: _ClassVar[int]
    FORWARD_FAIL_EVENT_FIELD_NUMBER: _ClassVar[int]
    SETTLE_EVENT_FIELD_NUMBER: _ClassVar[int]
    LINK_FAIL_EVENT_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIBED_EVENT_FIELD_NUMBER: _ClassVar[int]
    FINAL_HTLC_EVENT_FIELD_NUMBER: _ClassVar[int]
    incoming_channel_id: int
    outgoing_channel_id: int
    incoming_htlc_id: int
    outgoing_htlc_id: int
    timestamp_ns: int
    event_type: HtlcEvent.EventType
    forward_event: ForwardEvent
    forward_fail_event: ForwardFailEvent
    settle_event: SettleEvent
    link_fail_event: LinkFailEvent
    subscribed_event: SubscribedEvent
    final_htlc_event: FinalHtlcEvent
    def __init__(self, incoming_channel_id: _Optional[int] = ..., outgoing_channel_id: _Optional[int] = ..., incoming_htlc_id: _Optional[int] = ..., outgoing_htlc_id: _Optional[int] = ..., timestamp_ns: _Optional[int] = ..., event_type: _Optional[_Union[HtlcEvent.EventType, str]] = ..., forward_event: _Optional[_Union[ForwardEvent, _Mapping]] = ..., forward_fail_event: _Optional[_Union[ForwardFailEvent, _Mapping]] = ..., settle_event: _Optional[_Union[SettleEvent, _Mapping]] = ..., link_fail_event: _Optional[_Union[LinkFailEvent, _Mapping]] = ..., subscribed_event: _Optional[_Union[SubscribedEvent, _Mapping]] = ..., final_htlc_event: _Optional[_Union[FinalHtlcEvent, _Mapping]] = ...) -> None: ...

class HtlcInfo(_message.Message):
    __slots__ = ("incoming_timelock", "outgoing_timelock", "incoming_amt_msat", "outgoing_amt_msat")
    INCOMING_TIMELOCK_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_TIMELOCK_FIELD_NUMBER: _ClassVar[int]
    INCOMING_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_AMT_MSAT_FIELD_NUMBER: _ClassVar[int]
    incoming_timelock: int
    outgoing_timelock: int
    incoming_amt_msat: int
    outgoing_amt_msat: int
    def __init__(self, incoming_timelock: _Optional[int] = ..., outgoing_timelock: _Optional[int] = ..., incoming_amt_msat: _Optional[int] = ..., outgoing_amt_msat: _Optional[int] = ...) -> None: ...

class ForwardEvent(_message.Message):
    __slots__ = ("info",)
    INFO_FIELD_NUMBER: _ClassVar[int]
    info: HtlcInfo
    def __init__(self, info: _Optional[_Union[HtlcInfo, _Mapping]] = ...) -> None: ...

class ForwardFailEvent(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SettleEvent(_message.Message):
    __slots__ = ("preimage",)
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    preimage: bytes
    def __init__(self, preimage: _Optional[bytes] = ...) -> None: ...

class FinalHtlcEvent(_message.Message):
    __slots__ = ("settled", "offchain")
    SETTLED_FIELD_NUMBER: _ClassVar[int]
    OFFCHAIN_FIELD_NUMBER: _ClassVar[int]
    settled: bool
    offchain: bool
    def __init__(self, settled: bool = ..., offchain: bool = ...) -> None: ...

class SubscribedEvent(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class LinkFailEvent(_message.Message):
    __slots__ = ("info", "wire_failure", "failure_detail", "failure_string")
    INFO_FIELD_NUMBER: _ClassVar[int]
    WIRE_FAILURE_FIELD_NUMBER: _ClassVar[int]
    FAILURE_DETAIL_FIELD_NUMBER: _ClassVar[int]
    FAILURE_STRING_FIELD_NUMBER: _ClassVar[int]
    info: HtlcInfo
    wire_failure: _lightning_pb2.Failure.FailureCode
    failure_detail: FailureDetail
    failure_string: str
    def __init__(self, info: _Optional[_Union[HtlcInfo, _Mapping]] = ..., wire_failure: _Optional[_Union[_lightning_pb2.Failure.FailureCode, str]] = ..., failure_detail: _Optional[_Union[FailureDetail, str]] = ..., failure_string: _Optional[str] = ...) -> None: ...

class PaymentStatus(_message.Message):
    __slots__ = ("state", "preimage", "htlcs")
    STATE_FIELD_NUMBER: _ClassVar[int]
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    HTLCS_FIELD_NUMBER: _ClassVar[int]
    state: PaymentState
    preimage: bytes
    htlcs: _containers.RepeatedCompositeFieldContainer[_lightning_pb2.HTLCAttempt]
    def __init__(self, state: _Optional[_Union[PaymentState, str]] = ..., preimage: _Optional[bytes] = ..., htlcs: _Optional[_Iterable[_Union[_lightning_pb2.HTLCAttempt, _Mapping]]] = ...) -> None: ...

class CircuitKey(_message.Message):
    __slots__ = ("chan_id", "htlc_id")
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    HTLC_ID_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    htlc_id: int
    def __init__(self, chan_id: _Optional[int] = ..., htlc_id: _Optional[int] = ...) -> None: ...

class ForwardHtlcInterceptRequest(_message.Message):
    __slots__ = ("incoming_circuit_key", "incoming_amount_msat", "incoming_expiry", "payment_hash", "outgoing_requested_chan_id", "outgoing_amount_msat", "outgoing_expiry", "custom_records", "onion_blob", "auto_fail_height", "in_wire_custom_records")
    class CustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    class InWireCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    INCOMING_CIRCUIT_KEY_FIELD_NUMBER: _ClassVar[int]
    INCOMING_AMOUNT_MSAT_FIELD_NUMBER: _ClassVar[int]
    INCOMING_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_REQUESTED_CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_AMOUNT_MSAT_FIELD_NUMBER: _ClassVar[int]
    OUTGOING_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    ONION_BLOB_FIELD_NUMBER: _ClassVar[int]
    AUTO_FAIL_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    IN_WIRE_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    incoming_circuit_key: CircuitKey
    incoming_amount_msat: int
    incoming_expiry: int
    payment_hash: bytes
    outgoing_requested_chan_id: int
    outgoing_amount_msat: int
    outgoing_expiry: int
    custom_records: _containers.ScalarMap[int, bytes]
    onion_blob: bytes
    auto_fail_height: int
    in_wire_custom_records: _containers.ScalarMap[int, bytes]
    def __init__(self, incoming_circuit_key: _Optional[_Union[CircuitKey, _Mapping]] = ..., incoming_amount_msat: _Optional[int] = ..., incoming_expiry: _Optional[int] = ..., payment_hash: _Optional[bytes] = ..., outgoing_requested_chan_id: _Optional[int] = ..., outgoing_amount_msat: _Optional[int] = ..., outgoing_expiry: _Optional[int] = ..., custom_records: _Optional[_Mapping[int, bytes]] = ..., onion_blob: _Optional[bytes] = ..., auto_fail_height: _Optional[int] = ..., in_wire_custom_records: _Optional[_Mapping[int, bytes]] = ...) -> None: ...

class ForwardHtlcInterceptResponse(_message.Message):
    __slots__ = ("incoming_circuit_key", "action", "preimage", "failure_message", "failure_code", "in_amount_msat", "out_amount_msat", "out_wire_custom_records")
    class OutWireCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    INCOMING_CIRCUIT_KEY_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    FAILURE_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    FAILURE_CODE_FIELD_NUMBER: _ClassVar[int]
    IN_AMOUNT_MSAT_FIELD_NUMBER: _ClassVar[int]
    OUT_AMOUNT_MSAT_FIELD_NUMBER: _ClassVar[int]
    OUT_WIRE_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    incoming_circuit_key: CircuitKey
    action: ResolveHoldForwardAction
    preimage: bytes
    failure_message: bytes
    failure_code: _lightning_pb2.Failure.FailureCode
    in_amount_msat: int
    out_amount_msat: int
    out_wire_custom_records: _containers.ScalarMap[int, bytes]
    def __init__(self, incoming_circuit_key: _Optional[_Union[CircuitKey, _Mapping]] = ..., action: _Optional[_Union[ResolveHoldForwardAction, str]] = ..., preimage: _Optional[bytes] = ..., failure_message: _Optional[bytes] = ..., failure_code: _Optional[_Union[_lightning_pb2.Failure.FailureCode, str]] = ..., in_amount_msat: _Optional[int] = ..., out_amount_msat: _Optional[int] = ..., out_wire_custom_records: _Optional[_Mapping[int, bytes]] = ...) -> None: ...

class UpdateChanStatusRequest(_message.Message):
    __slots__ = ("chan_point", "action")
    CHAN_POINT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    chan_point: _lightning_pb2.ChannelPoint
    action: ChanStatusAction
    def __init__(self, chan_point: _Optional[_Union[_lightning_pb2.ChannelPoint, _Mapping]] = ..., action: _Optional[_Union[ChanStatusAction, str]] = ...) -> None: ...

class UpdateChanStatusResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AddAliasesRequest(_message.Message):
    __slots__ = ("alias_maps",)
    ALIAS_MAPS_FIELD_NUMBER: _ClassVar[int]
    alias_maps: _containers.RepeatedCompositeFieldContainer[_lightning_pb2.AliasMap]
    def __init__(self, alias_maps: _Optional[_Iterable[_Union[_lightning_pb2.AliasMap, _Mapping]]] = ...) -> None: ...

class AddAliasesResponse(_message.Message):
    __slots__ = ("alias_maps",)
    ALIAS_MAPS_FIELD_NUMBER: _ClassVar[int]
    alias_maps: _containers.RepeatedCompositeFieldContainer[_lightning_pb2.AliasMap]
    def __init__(self, alias_maps: _Optional[_Iterable[_Union[_lightning_pb2.AliasMap, _Mapping]]] = ...) -> None: ...

class DeleteAliasesRequest(_message.Message):
    __slots__ = ("alias_maps",)
    ALIAS_MAPS_FIELD_NUMBER: _ClassVar[int]
    alias_maps: _containers.RepeatedCompositeFieldContainer[_lightning_pb2.AliasMap]
    def __init__(self, alias_maps: _Optional[_Iterable[_Union[_lightning_pb2.AliasMap, _Mapping]]] = ...) -> None: ...

class DeleteAliasesResponse(_message.Message):
    __slots__ = ("alias_maps",)
    ALIAS_MAPS_FIELD_NUMBER: _ClassVar[int]
    alias_maps: _containers.RepeatedCompositeFieldContainer[_lightning_pb2.AliasMap]
    def __init__(self, alias_maps: _Optional[_Iterable[_Union[_lightning_pb2.AliasMap, _Mapping]]] = ...) -> None: ...

class FindBaseAliasRequest(_message.Message):
    __slots__ = ("alias",)
    ALIAS_FIELD_NUMBER: _ClassVar[int]
    alias: int
    def __init__(self, alias: _Optional[int] = ...) -> None: ...

class FindBaseAliasResponse(_message.Message):
    __slots__ = ("base",)
    BASE_FIELD_NUMBER: _ClassVar[int]
    base: int
    def __init__(self, base: _Optional[int] = ...) -> None: ...
