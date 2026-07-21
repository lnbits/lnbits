from collections.abc import Iterable
from typing import Any

from lnbits.core.models.extensions import ExtensionPermission, InstallableExtension
from lnbits.core.wasm_ext.api.registry import extension_api_permission_ids
from lnbits.core.wasm_ext.api.websockets import (
    WEBSOCKET_PUBLISH_MAX_MESSAGES_PER_SECOND_LIMIT,
)
from lnbits.core.wasm_ext.client.http import _request_origin
from lnbits.core.wasm_ext.wasm.config import (
    WasmExtensionConfig,
    parse_wasm_extension_config,
)

_POLICY_AWARE_PERMISSION_IDS = {
    "ext.storage.append_public",
    "ext.storage.read_public",
    "extension.api.request",
    "http.request",
    "wallet.create_invoice_public",
    "websocket.publish",
}
_OWNER_ID_FIELD = "__lnbits_owner_id__"
_PUBLIC_APPEND_DEFAULT_MAX_ROWS_PER_SOURCE = 10_000
PUBLIC_APPEND_MAX_ROWS_PER_SOURCE_LIMIT = 1_000_000


def validate_extension_permissions(
    ext_id: str,
    permissions: Iterable[ExtensionPermission],
    *,
    strict: bool = True,
) -> list[ExtensionPermission]:
    known_permission_ids = extension_api_permission_ids()
    normalized_permissions: list[ExtensionPermission] = []
    unknown_ids: list[str] = []

    for permission in permissions:
        if permission.id not in known_permission_ids:
            unknown_ids.append(permission.id)
            if strict:
                continue
        normalized_permissions.append(permission.copy())

    if unknown_ids and strict:
        raise ValueError(
            f"Extension '{ext_id}' requests unknown permissions: "
            + ", ".join(sorted(set(unknown_ids)))
        )

    return normalized_permissions


def validate_wasm_extension_permissions(
    ext_info: InstallableExtension,
    granted_permissions: list[ExtensionPermission] | None,
    extension_config: dict[str, Any] | WasmExtensionConfig,
    *,
    allow_admin_policy_overrides: bool = False,
    require_wasm: bool = False,
) -> list[ExtensionPermission]:
    if isinstance(extension_config, WasmExtensionConfig):
        config = extension_config
    elif extension_config.get("extension_type") != "wasm":
        if require_wasm:
            raise ValueError(
                f"Extension '{ext_info.id}' archive is not a WASM extension."
            )
        return []
    else:
        config = parse_wasm_extension_config(ext_info.id, extension_config)

    requested_permissions = validate_extension_permissions(
        ext_info.id, config.permissions
    )
    _validate_requested_permission_policies(ext_info.id, requested_permissions)
    if not requested_permissions:
        return []

    if granted_permissions is None:
        raise ValueError(f"Extension '{ext_info.id}' requires permission approval.")

    granted_permissions = validate_extension_permissions(
        ext_info.id,
        granted_permissions,
    )
    requested_by_id = _permission_index(ext_info.id, requested_permissions, "requested")
    granted_by_id = _permission_index(ext_info.id, granted_permissions, "granted")

    extra_granted_ids = sorted(set(granted_by_id) - set(requested_by_id))
    if extra_granted_ids:
        raise ValueError(
            f"Extension '{ext_info.id}' was granted unrequested permissions: "
            + ", ".join(extra_granted_ids)
        )

    effective_permissions: list[ExtensionPermission] = []
    for permission_id, granted_permission in granted_by_id.items():
        requested_permission = requested_by_id[permission_id]
        if not _permission_grant_is_subset(
            requested_permission,
            granted_permission,
            allow_admin_policy_overrides=allow_admin_policy_overrides,
        ):
            raise ValueError(
                f"Extension '{ext_info.id}' was granted broader policies for "
                f"permission '{permission_id}'."
            )
        effective_permissions.append(
            requested_permission.copy(update={"policies": granted_permission.policies})
        )

    return effective_permissions


def _permission_index(
    ext_id: str,
    permissions: Iterable[ExtensionPermission],
    source: str,
) -> dict[str, ExtensionPermission]:
    indexed: dict[str, ExtensionPermission] = {}
    duplicate_ids: list[str] = []

    for permission in permissions:
        if permission.id in indexed:
            duplicate_ids.append(permission.id)
            continue
        indexed[permission.id] = permission

    if duplicate_ids:
        raise ValueError(
            f"Extension '{ext_id}' has duplicate {source} permissions: "
            + ", ".join(sorted(set(duplicate_ids)))
        )
    return indexed


def _permission_grant_is_subset(
    requested: ExtensionPermission,
    granted: ExtensionPermission,
    *,
    allow_admin_policy_overrides: bool = False,
) -> bool:
    if requested.id != granted.id:
        return False
    if requested.id not in _POLICY_AWARE_PERMISSION_IDS:
        return True
    if requested.id == "http.request":
        return _http_request_grant_is_subset(requested.policies, granted.policies)
    if requested.id == "extension.api.request":
        return _extension_api_grant_is_subset(requested.policies, granted.policies)
    if requested.id == "ext.storage.append_public":
        return _public_storage_append_grant_is_subset(
            requested.policies,
            granted.policies,
            allow_max_rows_per_source_override=allow_admin_policy_overrides,
        )
    if requested.id == "ext.storage.read_public":
        return _public_storage_grant_is_subset(requested.policies, granted.policies)
    if requested.id == "wallet.create_invoice_public":
        return _public_invoice_grant_is_subset(requested.policies, granted.policies)
    if requested.id == "websocket.publish":
        return _websocket_publish_grant_is_subset(
            requested.policies,
            granted.policies,
            allow_max_messages_per_second_override=allow_admin_policy_overrides,
        )
    return False


def _validate_requested_permission_policies(
    ext_id: str,
    permissions: Iterable[ExtensionPermission],
) -> None:
    for permission in permissions:
        if permission.id != "websocket.publish":
            continue
        if _websocket_publish_policy(permission.policies) is None:
            raise ValueError(
                f"Extension '{ext_id}' requests invalid policies for permission "
                "'websocket.publish'."
            )


def _policy_list(policies: list[Any] | None) -> list[Any]:
    return policies if isinstance(policies, list) else []


def _http_request_grant_is_subset(
    requested_policies: list[Any] | None,
    granted_policies: list[Any] | None,
) -> bool:
    return _http_origins(granted_policies).issubset(_http_origins(requested_policies))


def _http_origins(policies: list[Any] | None) -> set[str]:
    origins: set[str] = set()
    for policy in _policy_list(policies):
        host = policy.get("host") if isinstance(policy, dict) else policy
        if not isinstance(host, str) or not host:
            continue
        try:
            origins.add(_request_origin(host))
        except PermissionError:
            continue
    return origins


def _extension_api_grant_is_subset(
    requested_policies: list[Any] | None,
    granted_policies: list[Any] | None,
) -> bool:
    requested_targets = _extension_api_targets(requested_policies)
    granted_targets = _extension_api_targets(granted_policies)
    for extension_id, granted_access in granted_targets.items():
        requested_access = requested_targets.get(extension_id)
        if requested_access is None or not granted_access.issubset(requested_access):
            return False
    return True


def _extension_api_targets(policies: list[Any] | None) -> dict[str, set[str]]:
    targets: dict[str, set[str]] = {}
    for policy in _policy_list(policies):
        extension_id: str | None = None
        access: list[Any] = []
        if isinstance(policy, str):
            extension_id = policy
            access = ["read"]
        elif isinstance(policy, dict):
            raw_extension_id = policy.get("id")
            raw_access = policy.get("access")
            if isinstance(raw_extension_id, str) and isinstance(raw_access, list):
                extension_id = raw_extension_id
                access = raw_access
        if not extension_id or extension_id in targets:
            continue
        clean_access = {
            item
            for item in access
            if isinstance(item, str) and item in {"read", "write"}
        }
        if clean_access:
            targets[extension_id] = clean_access
    return targets


def _public_storage_grant_is_subset(
    requested_policies: list[Any] | None,
    granted_policies: list[Any] | None,
) -> bool:
    requested_tables = _public_storage_tables(requested_policies)
    granted_tables = _public_storage_tables(granted_policies)
    for table_name, granted_policy in granted_tables.items():
        requested_policy = requested_tables.get(table_name)
        if requested_policy is None:
            return False
        if not granted_policy["public_fields"].issubset(
            requested_policy["public_fields"]
        ):
            return False
        requested_source_id_field = requested_policy["source_id_field"]
        if (
            requested_source_id_field
            and granted_policy["source_id_field"] != requested_source_id_field
        ):
            return False
    return True


def _public_storage_tables(policies: list[Any] | None) -> dict[str, dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = {}
    for policy in _policy_list(policies):
        if not isinstance(policy, dict):
            continue
        table_name = policy.get("table_name")
        public_fields = policy.get("public_fields")
        source_id_field = policy.get("source_id_field")
        if (
            not isinstance(table_name, str)
            or table_name in tables
            or not isinstance(public_fields, list)
            or (
                source_id_field is not None
                and (not isinstance(source_id_field, str) or not source_id_field)
            )
        ):
            continue
        fields = {field for field in public_fields if isinstance(field, str) and field}
        if fields:
            tables[table_name] = {
                "public_fields": fields,
                "source_id_field": source_id_field,
            }
    return tables


def _public_storage_append_grant_is_subset(
    requested_policies: list[Any] | None,
    granted_policies: list[Any] | None,
    *,
    allow_max_rows_per_source_override: bool = False,
) -> bool:
    requested_targets = _public_storage_append_targets(requested_policies)
    granted_targets = _public_storage_append_targets(granted_policies)
    if len(granted_targets) != len(_policy_list(granted_policies)):
        return False
    for target, granted_policy in granted_targets.items():
        requested_policy = requested_targets.get(target)
        if requested_policy is None:
            return False
        if not granted_policy["allowed_fields"].issubset(
            requested_policy["allowed_fields"]
        ):
            return False
        if (
            granted_policy["max_rows_per_source"]
            > requested_policy["max_rows_per_source"]
            and not allow_max_rows_per_source_override
        ):
            return False
    return True


def _public_storage_append_targets(policies: list[Any] | None) -> dict[Any, dict]:
    targets: dict[Any, dict] = {}
    for policy in _policy_list(policies):
        if not isinstance(policy, dict):
            continue
        table = policy.get("table")
        source_table = policy.get("source_table")
        source_id_field = policy.get("source_id_field")
        allowed_fields = policy.get("allowed_fields")
        max_rows_per_source = policy.get(
            "max_rows_per_source", _PUBLIC_APPEND_DEFAULT_MAX_ROWS_PER_SOURCE
        )
        if (
            not isinstance(table, str)
            or not table
            or not isinstance(source_table, str)
            or not source_table
            or not isinstance(source_id_field, str)
            or not source_id_field
            or source_id_field == "id"
            or not isinstance(allowed_fields, list)
            or isinstance(max_rows_per_source, bool)
            or not isinstance(max_rows_per_source, int)
            or max_rows_per_source <= 0
            or max_rows_per_source > PUBLIC_APPEND_MAX_ROWS_PER_SOURCE_LIMIT
        ):
            continue
        fields = {field for field in allowed_fields if isinstance(field, str) and field}
        if "id" in fields or _OWNER_ID_FIELD in fields or source_id_field in fields:
            continue
        targets[(table, source_table, source_id_field)] = {
            "allowed_fields": fields,
            "max_rows_per_source": max_rows_per_source,
        }
    return targets


def _public_invoice_grant_is_subset(
    requested_policies: list[Any] | None,
    granted_policies: list[Any] | None,
) -> bool:
    return _public_invoice_sources(granted_policies).issubset(
        _public_invoice_sources(requested_policies)
    )


def _public_invoice_sources(policies: list[Any] | None) -> set[tuple[str, str]]:
    sources: set[tuple[str, str]] = set()
    for policy in _policy_list(policies):
        if not isinstance(policy, dict):
            continue
        table = policy.get("table")
        wallet_field = policy.get("wallet_field")
        if isinstance(table, str) and table and isinstance(wallet_field, str):
            sources.add((table, wallet_field))
    return sources


def _websocket_publish_grant_is_subset(
    requested_policies: list[Any] | None,
    granted_policies: list[Any] | None,
    *,
    allow_max_messages_per_second_override: bool = False,
) -> bool:
    requested_policy = _websocket_publish_policy(requested_policies)
    granted_policy = _websocket_publish_policy(granted_policies)
    if requested_policy is None or granted_policy is None:
        return False
    if (
        granted_policy["max_messages_per_second"]
        > requested_policy["max_messages_per_second"]
        and not allow_max_messages_per_second_override
    ):
        return False
    return True


def _websocket_publish_policy(policies: list[Any] | None) -> dict[str, int] | None:
    policy_list = _policy_list(policies)
    if len(policy_list) != 1:
        return None
    policy = policy_list[0]
    if not isinstance(policy, dict):
        return None
    max_messages_per_second = policy.get("max_messages_per_second")
    if (
        isinstance(max_messages_per_second, bool)
        or not isinstance(max_messages_per_second, int)
        or max_messages_per_second <= 0
        or max_messages_per_second > WEBSOCKET_PUBLISH_MAX_MESSAGES_PER_SECOND_LIMIT
    ):
        return None
    return {"max_messages_per_second": max_messages_per_second}
