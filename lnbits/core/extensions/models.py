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
    amount_sat: int = Field(..., gt=0)
    # todo: bridge for extensions to select currencies
    currency: str | None = Field(..., min_length=1, max_length=8)
    memo: str = Field(..., max_length=512)
    tag: str = Field(..., min_length=1, max_length=64)
    extra: dict[str, str] = Field(default_factory=dict)


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
