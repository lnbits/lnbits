from typing import Literal

from pydantic import BaseModel, Field


class EmptyRequest(BaseModel):
    pass


class KvGetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=512)


class KvGetResponse(BaseModel):
    value: str | None = None


class KvSetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=512)
    value: str = Field(..., max_length=65536)


class KvSetResponse(BaseModel):
    ok: bool = True


class KvListRequest(BaseModel):
    prefix: str = Field(..., min_length=1, max_length=512)


class KvListResponse(BaseModel):
    keys: list[str] = []


class CreateInvoiceRequest(BaseModel):
    wallet_id: str = Field(..., min_length=1, max_length=128)
    amount_sat: int = Field(..., gt=0)
    memo: str = Field(..., max_length=512)
    tag: str = Field(..., min_length=1, max_length=64)
    extra: dict[str, str] = Field(default_factory=dict)


class CreateInvoiceResponse(BaseModel):
    payment_hash: str
    payment_request: str
    checking_id: str


class WatchPaymentRequest(BaseModel):
    payment_hash: str = Field(..., min_length=1, max_length=128)
    callback_export: str = Field(..., min_length=1, max_length=128)


class WatchPaymentResponse(BaseModel):
    ok: bool = True


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
