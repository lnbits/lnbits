import json
from typing import Any, Literal

from pydantic import BaseModel, Field, root_validator


class EmptyRequest(BaseModel):
    pass


class StorageGetRequest(BaseModel):
    table: str = Field(..., min_length=1, max_length=128)
    id: str = Field(..., min_length=1, max_length=512)


class StorageGetResponse(BaseModel):
    data_json: str | None = None


class StorageSetRequest(BaseModel):
    table: str = Field(..., min_length=1, max_length=128)
    data: dict[str, Any] = Field(default_factory=dict)

    @root_validator(pre=True)
    def parse_data_json(cls, values: dict[str, Any]) -> dict[str, Any]:
        data_json = values.get("data_json")
        if data_json is not None and "data" not in values:
            values["data"] = json.loads(data_json)
        return values


class StorageSetResponse(BaseModel):
    ok: bool = True


class StoragePaginatedRequest(BaseModel):
    table: str = Field(..., min_length=1, max_length=128)
    filters: dict[str, Any] = Field(default_factory=dict)
    search: str | None = Field(None, max_length=256)
    search_fields: list[str] = Field(default_factory=list)
    sort_by: str | None = Field(None, min_length=1, max_length=128)
    descending: bool = False
    limit: int = Field(25, ge=1, le=1000)
    offset: int = Field(0, ge=0)

    @root_validator(pre=True)
    def parse_json_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        filters_json = values.get("filters_json")
        if filters_json is not None and "filters" not in values:
            values["filters"] = json.loads(filters_json)

        search_fields_json = values.get("search_fields_json")
        if search_fields_json is not None and "search_fields" not in values:
            values["search_fields"] = json.loads(search_fields_json)

        if values.get("sort_by") == "":
            values["sort_by"] = None
        return values


class StoragePaginatedResponse(BaseModel):
    rows_json: str = "[]"
    total: int = 0


class StorageDeleteRequest(BaseModel):
    table: str = Field(..., min_length=1, max_length=128)
    id: str = Field(..., min_length=1, max_length=512)


class StorageDeleteResponse(BaseModel):
    ok: bool = True


class CreateInvoiceRequest(BaseModel):
    wallet_id: str = Field(..., min_length=1, max_length=128)
    amount: float = Field(..., gt=0)
    currency: str = Field("sat", min_length=1, max_length=8)
    memo: str = Field(..., max_length=512)
    tag: str = Field(..., min_length=1, max_length=64)
    extra: dict[str, str] = Field(default_factory=dict)


class CreateInvoicePublicRequest(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=512)
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=1, max_length=8)
    memo: str = Field("", max_length=512)
    extra: dict[str, Any] = Field(default_factory=dict)

    @root_validator
    def validate_extra_size(cls, values: dict[str, Any]) -> dict[str, Any]:
        extra = values.get("extra") or {}
        try:
            encoded = json.dumps(extra, separators=(",", ":"))
        except TypeError as exc:
            raise ValueError("extra must be JSON serializable.") from exc
        if len(encoded.encode()) > 4096:
            raise ValueError("extra must not exceed 4096 bytes.")
        values["extra"] = extra
        return values


class CreateInvoiceResponse(BaseModel):
    payment_hash: str
    payment_request: str
    checking_id: str


class UserWalletSummary(BaseModel):
    id: str
    name: str
    currency: str | None = None


class ListUserWalletsResponse(BaseModel):
    wallets: list[UserWalletSummary] = Field(default_factory=list)


class WalletBalanceRequest(BaseModel):
    wallet_id: str = Field(..., min_length=1, max_length=128)


class WalletBalanceResponse(BaseModel):
    wallet_id: str
    name: str
    currency: str | None = None
    balance_msat: int
    balance_sat: int
    withdrawable_msat: int
    withdrawable_sat: int
    fee_reserve_msat: int
    fee_reserve_sat: int
    can_send_payments: bool


class PayInvoiceRequest(BaseModel):
    wallet_id: str = Field(..., min_length=1, max_length=128)
    payment_request: str = Field(..., min_length=1, max_length=8192)
    max_sat: int | None = Field(None, gt=0)
    description: str = Field("", max_length=512)
    extra: dict[str, str] = Field(default_factory=dict)


class PayInvoiceResponse(BaseModel):
    ok: bool = True
    error: str | None = None
    checking_id: str | None = None
    payment_hash: str | None = None
    status: str | None = None
    amount_msat: int = 0
    fee_msat: int = 0
    pending: bool = False
    success: bool = False


class HttpRequest(BaseModel):
    method: Literal["DELETE", "GET", "HEAD", "PATCH", "POST", "PUT"] = "GET"
    url: str = Field(..., min_length=1, max_length=2048)
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = Field(None, max_length=65536)

    @root_validator(pre=True)
    def normalize_method(cls, values: dict[str, Any]) -> dict[str, Any]:
        method = values.get("method")
        if isinstance(method, str):
            values["method"] = method.upper()
        return values

    @root_validator
    def validate_headers_size(cls, values: dict[str, Any]) -> dict[str, Any]:
        headers = values.get("headers") or {}
        if len(headers) > 32:
            raise ValueError("headers must not contain more than 32 entries.")
        for key, value in headers.items():
            if len(key) > 128 or len(value) > 4096:
                raise ValueError("headers are too large.")
        values["headers"] = headers
        return values


class HttpResponse(BaseModel):
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""


class ExtensionApiRequest(BaseModel):
    extension_id: str = Field(..., min_length=1, max_length=128)
    method: Literal["DELETE", "GET", "HEAD", "PATCH", "POST", "PUT"] = "GET"
    path: str = Field(..., min_length=1, max_length=2048)
    body: str | None = Field(None, max_length=65536)

    @root_validator(pre=True)
    def normalize_method(cls, values: dict[str, Any]) -> dict[str, Any]:
        method = values.get("method")
        if isinstance(method, str):
            values["method"] = method.upper()
        return values


class CurrencyListResponse(BaseModel):
    currencies: list[str] = Field(default_factory=list)


class CurrencyRateRequest(BaseModel):
    currency: str = Field(..., min_length=1, max_length=8)


class CurrencyRateResponse(BaseModel):
    rate: float
    price: float


class CurrencyConvertRequest(BaseModel):
    amount: float = Field(..., gt=0)
    from_currency: str = Field(..., alias="from", min_length=1, max_length=8)
    to: str = Field(..., min_length=1, max_length=256)

    class Config:
        allow_population_by_field_name = True


class CurrencyConvertResponse(BaseModel):
    amounts: list[tuple[str, float]] = Field(default_factory=list)


class FiatToSatsRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=1, max_length=8)


class FiatToSatsResponse(BaseModel):
    amount_sat: int


class SatsToFiatRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=1, max_length=8)


class SatsToFiatResponse(BaseModel):
    amount: float


class ServerHealthResponse(BaseModel):
    server_time: int
    up_time: str


class Bolt11Request(BaseModel):
    bolt11: str = Field(..., min_length=1, max_length=8192)


class DecodeInvoiceResponse(BaseModel):
    valid: bool = True
    payment_hash: str | None = None
    amount_msat: int | None = None
    expiry: int | None = None
    expires_at: int | None = None
    memo: str | None = None


class ValidateInvoiceResponse(BaseModel):
    valid: bool
    error: str | None = None


class InvoicePaymentHashResponse(BaseModel):
    payment_hash: str


class InvoiceAmountMsatResponse(BaseModel):
    amount_msat: int | None = None


class InvoiceExpiryResponse(BaseModel):
    expires_at: int | None = None


class InvoiceMemoResponse(BaseModel):
    memo: str | None = None


class VerifyPreimageRequest(BaseModel):
    preimage: str = Field(..., min_length=64, max_length=64)
    payment_hash: str = Field(..., min_length=64, max_length=64)


class VerifyPreimageResponse(BaseModel):
    valid: bool


class RandomSecretAndHashRequest(BaseModel):
    length: int = Field(32, ge=16, le=64)


class RandomSecretAndHashResponse(BaseModel):
    secret: str
    hash: str


class RandomIdRequest(BaseModel):
    prefix: str = Field(..., min_length=1, max_length=32)


class RandomIdResponse(BaseModel):
    id: str


class NowResponse(BaseModel):
    timestamp: int


class LogRequest(BaseModel):
    level: Literal["debug", "info", "warning", "error"] = "info"
    message: str = Field(..., min_length=1, max_length=2048)


class LogResponse(BaseModel):
    ok: bool = True
