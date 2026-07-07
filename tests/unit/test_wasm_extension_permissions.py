from __future__ import annotations

import pytest

from lnbits.core.models.extensions import ExtensionPermission, InstallableExtension
from lnbits.core.wasm_ext.api.permissions import (
    validate_extension_permissions,
    validate_wasm_extension_permissions,
)


def test_validate_extension_permissions_rejects_unknown_permission() -> None:
    permissions = [
        ExtensionPermission(id="wallet.list"),
        ExtensionPermission(id="unknown.permission"),
    ]

    with pytest.raises(ValueError, match="unknown.permission"):
        validate_extension_permissions("demo", permissions)


def test_validate_wasm_extension_permissions_requires_grant() -> None:
    extension = InstallableExtension(id="demo", name="Demo", version="0.0.1")
    config = {
        "extension_type": "wasm",
        "permissions": [{"id": "wallet.list"}],
    }

    with pytest.raises(ValueError, match="requires permission approval"):
        validate_wasm_extension_permissions(extension, None, config)


def test_validate_wasm_extension_permissions_requires_exact_grants() -> None:
    extension = InstallableExtension(id="demo", name="Demo", version="0.0.1")
    config = {
        "extension_type": "wasm",
        "permissions": [{"id": "wallet.list"}, {"id": "utils.basic"}],
    }

    with pytest.raises(ValueError, match="was not granted all requested permissions"):
        validate_wasm_extension_permissions(
            extension,
            [ExtensionPermission(id="wallet.list")],
            config,
        )


def test_validate_wasm_extension_permissions_returns_core_normalized_grants() -> None:
    extension = InstallableExtension(id="demo", name="Demo", version="0.0.1")
    config = {
        "extension_type": "wasm",
        "permissions": [
            {
                "id": "wallet.list",
                "label": "Extension supplied label",
                "description": "Show wallets.",
            }
        ],
    }

    permissions = validate_wasm_extension_permissions(
        extension,
        [ExtensionPermission(id="wallet.list", label="Extension supplied label")],
        config,
    )

    assert len(permissions) == 1
    assert permissions[0].id == "wallet.list"
    assert permissions[0].label is None
    assert permissions[0].description == "Show wallets."
