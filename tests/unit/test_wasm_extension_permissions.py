from types import SimpleNamespace
from typing import Any, cast

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.wasm.events import _wasm_invoice_paid_owner_id
from lnbits.core.wasm_ext.wasm.invoke import _active_installed_extension
from tests.helpers import make_installable_extension


def test_validate_wasm_permissions_rejects_broader_policy_grant():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config(
        "demoext",
        [
            {
                "id": "http.request",
                "policies": [{"host": "https://api.example.com"}],
            }
        ],
    )

    with pytest.raises(ValueError, match="broader policies"):
        validate_wasm_extension_permissions(
            ext_info,
            [
                ExtensionPermission(
                    id="http.request",
                    policies=[
                        {"host": "https://api.example.com"},
                        {"host": "https://evil.example.com"},
                    ],
                )
            ],
            extension_config,
        )


def test_validate_wasm_permissions_stores_narrower_policy_grant():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config(
        "demoext",
        [
            {
                "id": "ext.storage.read_public",
                "description": "Read public storage.",
                "policies": [
                    {
                        "table_name": "tip_jars",
                        "public_fields": ["id", "title", "description"],
                    }
                ],
            }
        ],
    )

    permissions = validate_wasm_extension_permissions(
        ext_info,
        [
            ExtensionPermission(
                id="ext.storage.read_public",
                policies=[
                    {
                        "table_name": "tip_jars",
                        "public_fields": ["id", "title"],
                    }
                ],
            )
        ],
        extension_config,
    )

    assert permissions == [
        ExtensionPermission(
            id="ext.storage.read_public",
            description="Read public storage.",
            policies=[
                {
                    "table_name": "tip_jars",
                    "public_fields": ["id", "title"],
                }
            ],
        )
    ]


def test_validate_wasm_permissions_rejects_broader_extension_api_access():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config(
        "demoext",
        [
            {
                "id": "extension.api.request",
                "policies": [{"id": "targetext", "access": ["read"]}],
            }
        ],
    )

    with pytest.raises(ValueError, match="broader policies"):
        validate_wasm_extension_permissions(
            ext_info,
            [
                ExtensionPermission(
                    id="extension.api.request",
                    policies=[{"id": "targetext", "access": ["read", "write"]}],
                )
            ],
            extension_config,
        )


def test_validate_wasm_permissions_allows_empty_grant():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config(
        "demoext",
        [
            {
                "id": "wallet.create_invoice_public",
                "policies": [{"table": "tip_jars", "wallet_field": "wallet_id"}],
            }
        ],
    )

    assert validate_wasm_extension_permissions(ext_info, [], extension_config) == []


def test_validate_wasm_permissions_rejects_unrequested_permission_grant():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config("demoext", [{"id": "utils.basic"}])

    with pytest.raises(ValueError, match="unrequested permissions"):
        validate_wasm_extension_permissions(
            ext_info,
            [
                ExtensionPermission(id="utils.basic"),
                ExtensionPermission(id="wallet.list"),
            ],
            extension_config,
        )


@pytest.mark.anyio
async def test_invoice_paid_owner_lookup_uses_stored_granted_policies(
    mocker: MockerFixture,
):
    extension = SimpleNamespace(
        id="demoext",
        config=_wasm_config(
            "demoext",
            [
                {
                    "id": "wallet.create_invoice_public",
                    "policies": [
                        {"table": "requested_table", "wallet_field": "wallet_id"}
                    ],
                }
            ],
        ),
    )
    payment = SimpleNamespace(extra={"source_id": "source-1"})
    installed_extension = SimpleNamespace(
        permissions=[
            ExtensionPermission(
                id="wallet.create_invoice_public",
                policies=[{"table": "granted_table", "wallet_field": "wallet_id"}],
            )
        ]
    )
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.get_installed_extension",
        mocker.AsyncMock(return_value=installed_extension),
    )
    storage_mock = mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.storage_get_row_owner_id",
        mocker.AsyncMock(return_value="owner-1"),
    )

    owner_id = await _wasm_invoice_paid_owner_id(extension, payment)

    assert owner_id == "owner-1"
    storage_mock.assert_awaited_once_with("demoext", "granted_table", "source-1")


@pytest.mark.anyio
async def test_wasm_invocation_requires_installed_active_extension(
    mocker: MockerFixture,
):
    extension = SimpleNamespace(id="demoext")
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke.get_installed_extension",
        mocker.AsyncMock(return_value=None),
    )

    with pytest.raises(PermissionError, match="deactivated"):
        await _active_installed_extension(cast(Any, extension))


def _wasm_config(ext_id: str, permissions: list[dict]) -> dict:
    return {
        "id": ext_id,
        "name": ext_id,
        "short_description": "Demo extension",
        "version": "1.0.0",
        "extension_type": "wasm",
        "wasm": {"module": "extension.wasm"},
        "permissions": permissions,
    }
