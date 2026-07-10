from collections.abc import Iterable
from typing import Any

from lnbits.core.models.extensions import ExtensionPermission, InstallableExtension
from lnbits.core.wasm_ext.api.registry import extension_api_permission_ids
from lnbits.core.wasm_ext.client.http import _request_origin
from lnbits.core.wasm_ext.wasm.config import (
    WasmExtensionConfig,
    parse_wasm_extension_config,
)

_POLICY_AWARE_PERMISSION_IDS = {
    "ext.storage.read_public",
    "extension.api.request",
    "http.request",
    "wallet.create_invoice_public",
}


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
) -> list[ExtensionPermission]:
    if isinstance(extension_config, WasmExtensionConfig):
        config = extension_config
    elif extension_config.get("extension_type") != "wasm":
        return []
    else:
        config = parse_wasm_extension_config(ext_info.id, extension_config)

    requested_permissions = validate_extension_permissions(
        ext_info.id, config.permissions
    )
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
        if not _permission_grant_is_subset(requested_permission, granted_permission):
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
) -> bool:
    if requested.id != granted.id:
        return False
    if requested.id not in _POLICY_AWARE_PERMISSION_IDS:
        return True
    if requested.id == "http.request":
        return _http_request_grant_is_subset(requested.policies, granted.policies)
    if requested.id == "extension.api.request":
        return _extension_api_grant_is_subset(requested.policies, granted.policies)
    if requested.id == "ext.storage.read_public":
        return _public_storage_grant_is_subset(requested.policies, granted.policies)
    if requested.id == "wallet.create_invoice_public":
        return _public_invoice_grant_is_subset(requested.policies, granted.policies)
    return False


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
    for table_name, granted_fields in granted_tables.items():
        requested_fields = requested_tables.get(table_name)
        if requested_fields is None or not granted_fields.issubset(requested_fields):
            return False
    return True


def _public_storage_tables(policies: list[Any] | None) -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    for policy in _policy_list(policies):
        if not isinstance(policy, dict):
            continue
        table_name = policy.get("table_name")
        public_fields = policy.get("public_fields")
        if (
            not isinstance(table_name, str)
            or table_name in tables
            or not isinstance(public_fields, list)
        ):
            continue
        fields = {field for field in public_fields if isinstance(field, str) and field}
        if fields:
            tables[table_name] = fields
    return tables


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
