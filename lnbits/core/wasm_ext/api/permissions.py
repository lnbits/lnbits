from collections.abc import Iterable
from typing import Any

from lnbits.core.models.extensions import ExtensionPermission, InstallableExtension
from lnbits.core.wasm_ext.api.host import extension_api_permission_ids


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
        normalized_permissions.append(permission.copy(update={"label": None}))

    if unknown_ids and strict:
        raise ValueError(
            f"Extension '{ext_id}' requests unknown permissions: "
            + ", ".join(sorted(set(unknown_ids)))
        )

    return normalized_permissions


def validate_wasm_extension_permissions(
    ext_info: InstallableExtension,
    granted_permissions: list[ExtensionPermission] | None,
    extension_config: dict[str, Any],
) -> list[ExtensionPermission]:
    if extension_config.get("extension_type") != "wasm":
        return []

    requested_permissions = validate_extension_permissions(
        ext_info.id,
        ExtensionPermission.list_from_config(extension_config),
    )
    if not requested_permissions:
        return []

    if granted_permissions is None:
        raise ValueError(f"Extension '{ext_info.id}' requires permission approval.")

    requested_ids = {permission.id for permission in requested_permissions}
    granted_ids = {permission.id for permission in granted_permissions}
    if requested_ids != granted_ids:
        raise ValueError(
            f"Extension '{ext_info.id}' was not granted all requested permissions."
        )

    return requested_permissions
