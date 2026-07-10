from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
)

from lnbits.core.models.extensions import ExtensionPermission

_EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class _StrictWasmModel(BaseModel):
    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class WasmExtensionExport(_StrictWasmModel):
    name: StrictStr
    visibility: Literal["authenticated", "event", "public"]


class WasmRuntimeConfig(_StrictWasmModel):
    module: StrictStr
    wit: StrictStr | None = None
    world: StrictStr = ""
    exports: list[WasmExtensionExport] = Field(default_factory=list)


class WasmUIConfig(_StrictWasmModel):
    entrypoint: StrictStr | None = None
    sandbox: StrictBool | None = None


class WasmSDKConfig(_StrictWasmModel):
    frontend_js: StrictStr | None = None


class WasmUIRouteConfig(_StrictWasmModel):
    path: StrictStr
    entrypoint: StrictStr
    auth: Literal["public", "user"]
    path_params: dict[str, StrictStr] = Field(default_factory=dict)


class WasmAPIRouteConfig(_StrictWasmModel):
    method: Literal["DELETE", "GET", "PATCH", "POST", "PUT"]
    path: StrictStr
    export: StrictStr
    auth: Literal["public", "user"]
    path_params: dict[str, StrictStr] = Field(default_factory=dict)


class WasmEventsConfig(_StrictWasmModel):
    on_invoice_paid: StrictStr | None = Field(None, alias="onInvoicePaid")


class WasmExtensionConfig(_StrictWasmModel):
    id: StrictStr
    name: StrictStr
    short_description: StrictStr
    tile: StrictStr | None = None
    version: StrictStr
    min_lnbits_version: StrictStr | None = None
    max_lnbits_version: StrictStr | None = None
    extension_type: Literal["wasm"]
    wasm: WasmRuntimeConfig
    events: WasmEventsConfig = Field(
        default_factory=lambda: WasmEventsConfig.parse_obj({})
    )
    ui: WasmUIConfig | None = None
    sdk: WasmSDKConfig | None = None
    ui_routes: list[WasmUIRouteConfig] = Field(default_factory=list)
    api_routes: list[WasmAPIRouteConfig] = Field(default_factory=list)
    permissions: list[ExtensionPermission] = Field(default_factory=list)


def parse_wasm_extension_config(
    ext_id: str,
    config: dict[str, Any],
) -> WasmExtensionConfig:
    validate_wasm_extension_config_id(ext_id, config)
    try:
        return WasmExtensionConfig.parse_obj(config)
    except ValidationError as exc:
        raise ValueError(
            f"Invalid WASM extension config for '{ext_id}': {exc}"
        ) from exc


def validate_wasm_extension_config_id(
    ext_id: str,
    config: dict[str, Any] | WasmExtensionConfig,
) -> str:
    if not _EXTENSION_ID_RE.fullmatch(ext_id):
        raise ValueError(f"Invalid WASM extension id '{ext_id}'.")

    config_id = (
        config.id if isinstance(config, WasmExtensionConfig) else config.get("id")
    )
    if not isinstance(config_id, str) or not config_id:
        raise ValueError(f"WASM extension '{ext_id}' config must define id.")
    if config_id != ext_id:
        raise ValueError(
            f"WASM extension id mismatch: installed as '{ext_id}' "
            f"but config declares '{config_id}'."
        )
    return config_id
