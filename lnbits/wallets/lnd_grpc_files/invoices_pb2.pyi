import lnbits.wallets.lnd_grpc_files.lightning_pb2 as _lightning_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LookupModifier(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DEFAULT: _ClassVar[LookupModifier]
    HTLC_SET_ONLY: _ClassVar[LookupModifier]
    HTLC_SET_BLANK: _ClassVar[LookupModifier]
DEFAULT: LookupModifier
HTLC_SET_ONLY: LookupModifier
HTLC_SET_BLANK: LookupModifier

class CancelInvoiceMsg(_message.Message):
    __slots__ = ("payment_hash",)
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    payment_hash: bytes
    def __init__(self, payment_hash: _Optional[bytes] = ...) -> None: ...

class CancelInvoiceResp(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class AddHoldInvoiceRequest(_message.Message):
    __slots__ = ("memo", "hash", "value", "value_msat", "description_hash", "expiry", "fallback_addr", "cltv_expiry", "route_hints", "private")
    MEMO_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    VALUE_MSAT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_HASH_FIELD_NUMBER: _ClassVar[int]
    EXPIRY_FIELD_NUMBER: _ClassVar[int]
    FALLBACK_ADDR_FIELD_NUMBER: _ClassVar[int]
    CLTV_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    ROUTE_HINTS_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_FIELD_NUMBER: _ClassVar[int]
    memo: str
    hash: bytes
    value: int
    value_msat: int
    description_hash: bytes
    expiry: int
    fallback_addr: str
    cltv_expiry: int
    route_hints: _containers.RepeatedCompositeFieldContainer[_lightning_pb2.RouteHint]
    private: bool
    def __init__(self, memo: _Optional[str] = ..., hash: _Optional[bytes] = ..., value: _Optional[int] = ..., value_msat: _Optional[int] = ..., description_hash: _Optional[bytes] = ..., expiry: _Optional[int] = ..., fallback_addr: _Optional[str] = ..., cltv_expiry: _Optional[int] = ..., route_hints: _Optional[_Iterable[_Union[_lightning_pb2.RouteHint, _Mapping]]] = ..., private: bool = ...) -> None: ...

class AddHoldInvoiceResp(_message.Message):
    __slots__ = ("payment_request", "add_index", "payment_addr")
    PAYMENT_REQUEST_FIELD_NUMBER: _ClassVar[int]
    ADD_INDEX_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    payment_request: str
    add_index: int
    payment_addr: bytes
    def __init__(self, payment_request: _Optional[str] = ..., add_index: _Optional[int] = ..., payment_addr: _Optional[bytes] = ...) -> None: ...

class SettleInvoiceMsg(_message.Message):
    __slots__ = ("preimage",)
    PREIMAGE_FIELD_NUMBER: _ClassVar[int]
    preimage: bytes
    def __init__(self, preimage: _Optional[bytes] = ...) -> None: ...

class SettleInvoiceResp(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SubscribeSingleInvoiceRequest(_message.Message):
    __slots__ = ("r_hash",)
    R_HASH_FIELD_NUMBER: _ClassVar[int]
    r_hash: bytes
    def __init__(self, r_hash: _Optional[bytes] = ...) -> None: ...

class LookupInvoiceMsg(_message.Message):
    __slots__ = ("payment_hash", "payment_addr", "set_id", "lookup_modifier")
    PAYMENT_HASH_FIELD_NUMBER: _ClassVar[int]
    PAYMENT_ADDR_FIELD_NUMBER: _ClassVar[int]
    SET_ID_FIELD_NUMBER: _ClassVar[int]
    LOOKUP_MODIFIER_FIELD_NUMBER: _ClassVar[int]
    payment_hash: bytes
    payment_addr: bytes
    set_id: bytes
    lookup_modifier: LookupModifier
    def __init__(self, payment_hash: _Optional[bytes] = ..., payment_addr: _Optional[bytes] = ..., set_id: _Optional[bytes] = ..., lookup_modifier: _Optional[_Union[LookupModifier, str]] = ...) -> None: ...

class CircuitKey(_message.Message):
    __slots__ = ("chan_id", "htlc_id")
    CHAN_ID_FIELD_NUMBER: _ClassVar[int]
    HTLC_ID_FIELD_NUMBER: _ClassVar[int]
    chan_id: int
    htlc_id: int
    def __init__(self, chan_id: _Optional[int] = ..., htlc_id: _Optional[int] = ...) -> None: ...

class HtlcModifyRequest(_message.Message):
    __slots__ = ("invoice", "exit_htlc_circuit_key", "exit_htlc_amt", "exit_htlc_expiry", "current_height", "exit_htlc_wire_custom_records")
    class ExitHtlcWireCustomRecordsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: bytes
        def __init__(self, key: _Optional[int] = ..., value: _Optional[bytes] = ...) -> None: ...
    INVOICE_FIELD_NUMBER: _ClassVar[int]
    EXIT_HTLC_CIRCUIT_KEY_FIELD_NUMBER: _ClassVar[int]
    EXIT_HTLC_AMT_FIELD_NUMBER: _ClassVar[int]
    EXIT_HTLC_EXPIRY_FIELD_NUMBER: _ClassVar[int]
    CURRENT_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    EXIT_HTLC_WIRE_CUSTOM_RECORDS_FIELD_NUMBER: _ClassVar[int]
    invoice: _lightning_pb2.Invoice
    exit_htlc_circuit_key: CircuitKey
    exit_htlc_amt: int
    exit_htlc_expiry: int
    current_height: int
    exit_htlc_wire_custom_records: _containers.ScalarMap[int, bytes]
    def __init__(self, invoice: _Optional[_Union[_lightning_pb2.Invoice, _Mapping]] = ..., exit_htlc_circuit_key: _Optional[_Union[CircuitKey, _Mapping]] = ..., exit_htlc_amt: _Optional[int] = ..., exit_htlc_expiry: _Optional[int] = ..., current_height: _Optional[int] = ..., exit_htlc_wire_custom_records: _Optional[_Mapping[int, bytes]] = ...) -> None: ...

class HtlcModifyResponse(_message.Message):
    __slots__ = ("circuit_key", "amt_paid", "cancel_set")
    CIRCUIT_KEY_FIELD_NUMBER: _ClassVar[int]
    AMT_PAID_FIELD_NUMBER: _ClassVar[int]
    CANCEL_SET_FIELD_NUMBER: _ClassVar[int]
    circuit_key: CircuitKey
    amt_paid: int
    cancel_set: bool
    def __init__(self, circuit_key: _Optional[_Union[CircuitKey, _Mapping]] = ..., amt_paid: _Optional[int] = ..., cancel_set: bool = ...) -> None: ...
