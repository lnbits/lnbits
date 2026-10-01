from __future__ import annotations

import re
from typing import Any, Literal, TypeAlias

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictStr,
    ValidationError,
    conint,
)

from lnbits.core.models.extensions import ExtensionPermission

_EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_CHANNEL_EVENT_FIELD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
_PositiveStrictInt: TypeAlias = conint(strict=True, ge=1)  # type: ignore[valid-type]


class _StrictWasmModel(BaseModel):
    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class WasmExtensionExport(_StrictWasmModel):
    name: StrictStr
    visibility: Literal["authenticated", "authoritative", "event", "public"]


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


class WasmRouteOwnerContext(_StrictWasmModel):
    table: StrictStr
    id_param: StrictStr = Field(..., alias="idParam")


class WasmAuthoritativeChannelConfig(_StrictWasmModel):
    authorize_connection: StrictStr = Field(..., alias="authorizeConnection")
    on_event: StrictStr | None = Field(None, alias="onEvent")
    on_schedule: StrictStr | None = Field(None, alias="onSchedule")
    owner_context: WasmRouteOwnerContext = Field(..., alias="ownerContext")
    result_table: StrictStr | None = Field(None, alias="resultTable")
    result_field: StrictStr = Field("result", alias="resultField")
    event_fields: list[StrictStr] = Field(
        default_factory=list, alias="eventFields", max_items=32
    )
    schedule_interval_ms: _PositiveStrictInt | None = Field(
        None, alias="scheduleIntervalMs"
    )
    max_events_per_second: _PositiveStrictInt = Field(..., alias="maxEventsPerSecond")
    max_queue_depth: _PositiveStrictInt = Field(..., alias="maxQueueDepth")
    max_active_rooms: _PositiveStrictInt = Field(..., alias="maxActiveRooms")
    persistence: Literal["durable", "ephemeral"] = "durable"


class WasmAPIRouteConfig(_StrictWasmModel):
    method: Literal["DELETE", "GET", "PATCH", "POST", "PUT"]
    path: StrictStr
    export: StrictStr
    auth: Literal["public", "user"]
    path_params: dict[str, StrictStr] = Field(default_factory=dict)
    owner_context: WasmRouteOwnerContext | None = Field(None, alias="ownerContext")
    serialize_room: StrictBool = Field(False, alias="serializeRoom")
    openapi: StrictStr | None = None


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
    authoritative_channel: WasmAuthoritativeChannelConfig | None = Field(
        None, alias="authoritativeChannel"
    )
    events: WasmEventsConfig = Field(
        default_factory=lambda: WasmEventsConfig.parse_obj({})
    )
    ui: WasmUIConfig | None = None
    sdk: WasmSDKConfig | None = None
    openapi: StrictStr | None = None
    ui_routes: list[WasmUIRouteConfig] = Field(default_factory=list)
    api_routes: list[WasmAPIRouteConfig] = Field(default_factory=list)
    permissions: list[ExtensionPermission] = Field(default_factory=list)


def parse_wasm_extension_config(
    ext_id: str,
    config: dict[str, Any],
) -> WasmExtensionConfig:
    validate_wasm_extension_config_id(ext_id, config)
    try:
        parsed = WasmExtensionConfig.parse_obj(config)
    except ValidationError as exc:
        raise ValueError(
            f"Invalid WASM extension config for '{ext_id}': {exc}"
        ) from exc
    _validate_authoritative_channel_config(ext_id, parsed)
    return parsed


def _validate_authoritative_channel_config(
    ext_id: str,
    config: WasmExtensionConfig,
) -> None:
    channel = config.authoritative_channel
    if channel:
        permission_ids = {permission.id for permission in config.permissions}
        if not {"websocket.authoritative", "websocket.subscribe"}.issubset(
            permission_ids
        ):
            raise ValueError(
                f"WASM authoritative channel '{ext_id}' must request "
                "websocket.authoritative and websocket.subscribe permissions."
            )
        _validate_authoritative_event_fields(ext_id, channel)
        _validate_authoritative_result_config(ext_id, channel)
        if bool(channel.on_schedule) != bool(channel.schedule_interval_ms):
            raise ValueError(
                f"WASM authoritative channel '{ext_id}' must configure both "
                "onSchedule and scheduleIntervalMs."
            )
        _validate_authoritative_exports(ext_id, config, channel)

    for route in config.api_routes:
        if not route.serialize_room:
            continue
        if not channel or not route.owner_context:
            raise ValueError(
                f"WASM room-serialized API route for '{ext_id}' requires "
                "authoritativeChannel and ownerContext."
            )
        if route.owner_context.table != channel.owner_context.table:
            raise ValueError(
                f"WASM room-serialized API route for '{ext_id}' must use the "
                "authoritative channel owner-context table."
            )


def _validate_authoritative_result_config(
    ext_id: str,
    channel: WasmAuthoritativeChannelConfig,
) -> None:
    if channel.result_table and not _CHANNEL_EVENT_FIELD_RE.fullmatch(
        channel.result_table
    ):
        raise ValueError(f"WASM authoritative result table for '{ext_id}' is invalid.")
    if channel.result_table and not _CHANNEL_EVENT_FIELD_RE.fullmatch(
        channel.result_field
    ):
        raise ValueError(f"WASM authoritative result field for '{ext_id}' is invalid.")
    if not channel.result_table and channel.result_field != "result":
        raise ValueError(
            f"WASM authoritative result field for '{ext_id}' requires resultTable."
        )


def _validate_authoritative_event_fields(
    ext_id: str,
    channel: WasmAuthoritativeChannelConfig,
) -> None:
    reserved_fields = {
        "cansend",
        "connectionid",
        "clientsequence",
        "extensionid",
        "ownerid",
        "principalid",
        "principalrole",
        "roomid",
        "sessiontoken",
        "servertime",
        "servertimems",
        "sequence",
        "state",
        "timestamp",
        "token",
    }
    invalid_fields = len(set(channel.event_fields)) != len(channel.event_fields) or any(
        not _CHANNEL_EVENT_FIELD_RE.fullmatch(field) or field.lower() in reserved_fields
        for field in channel.event_fields
    )
    if invalid_fields:
        raise ValueError(
            f"WASM authoritative channel '{ext_id}' has invalid eventFields."
        )
    if bool(channel.on_event) != bool(channel.event_fields):
        raise ValueError(
            f"WASM authoritative channel '{ext_id}' must declare eventFields "
            "only when onEvent is configured."
        )


def _validate_authoritative_exports(
    ext_id: str,
    config: WasmExtensionConfig,
    channel: WasmAuthoritativeChannelConfig,
) -> None:
    export_names = [channel.authorize_connection]
    if channel.on_event:
        export_names.append(channel.on_event)
    if channel.on_schedule:
        export_names.append(channel.on_schedule)
    for export_name in export_names:
        if not any(
            export.name == export_name and export.visibility == "authoritative"
            for export in config.wasm.exports
        ):
            raise ValueError(
                f"WASM authoritative channel export '{export_name}' for '{ext_id}' "
                "must be declared with authoritative visibility."
            )


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
