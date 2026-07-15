from types import SimpleNamespace
from typing import Any, cast

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.extensions import (
    ExtensionBackgroundPaymentDestinationPolicy,
    ExtensionPermission,
)
from lnbits.core.views.extension_api import (
    WALLET_PAY_INVOICE_BACKGROUND_PERMISSION,
    WALLET_PAYMENTS_WATCH_PERMISSION,
    _background_destination_policy_covers,
    _check_background_payment_permission,
    _check_wallet_payments_watch_permission,
    _find_background_payment_grant,
    _find_wallet_payments_watch_grant,
    _remove_user_permission_grant,
    _safe_user_extension_permissions,
    _user_permission_grant_id_for_wallet,
)
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


def test_validate_wasm_permissions_allows_narrower_public_append_grant():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config(
        "demoext",
        [
            {
                "id": "ext.storage.append_public",
                "description": "Append public messages.",
                "policies": [
                    {
                        "table": "messages",
                        "source_table": "threads",
                        "source_id_field": "thread_id",
                        "allowed_fields": ["name", "message"],
                        "max_rows_per_source": 100,
                    }
                ],
            }
        ],
    )

    permissions = validate_wasm_extension_permissions(
        ext_info,
        [
            ExtensionPermission(
                id="ext.storage.append_public",
                policies=[
                    {
                        "table": "messages",
                        "source_table": "threads",
                        "source_id_field": "thread_id",
                        "allowed_fields": ["message"],
                        "max_rows_per_source": 50,
                    }
                ],
            )
        ],
        extension_config,
    )

    assert permissions == [
        ExtensionPermission(
            id="ext.storage.append_public",
            description="Append public messages.",
            policies=[
                {
                    "table": "messages",
                    "source_table": "threads",
                    "source_id_field": "thread_id",
                    "allowed_fields": ["message"],
                    "max_rows_per_source": 50,
                }
            ],
        )
    ]


def test_validate_wasm_permissions_rejects_broader_public_append_grant():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config(
        "demoext",
        [
            {
                "id": "ext.storage.append_public",
                "policies": [
                    {
                        "table": "messages",
                        "source_table": "threads",
                        "source_id_field": "thread_id",
                        "allowed_fields": ["message"],
                        "max_rows_per_source": 100,
                    }
                ],
            }
        ],
    )

    with pytest.raises(ValueError, match="broader policies"):
        validate_wasm_extension_permissions(
            ext_info,
            [
                ExtensionPermission(
                    id="ext.storage.append_public",
                    policies=[
                        {
                            "table": "messages",
                            "source_table": "threads",
                            "source_id_field": "thread_id",
                            "allowed_fields": ["message", "admin"],
                            "max_rows_per_source": 101,
                        }
                    ],
                )
            ],
            extension_config,
        )


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


def test_validate_wasm_permissions_allows_wallet_payments_watch_permission():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config(
        "demoext",
        [{"id": "wallet.payments.watch"}],
    )

    assert validate_wasm_extension_permissions(
        ext_info,
        [ExtensionPermission(id="wallet.payments.watch")],
        extension_config,
    ) == [ExtensionPermission(id="wallet.payments.watch")]


def test_validate_wasm_permissions_allows_websocket_permissions():
    ext_info = make_installable_extension("demoext")
    extension_config = _wasm_config(
        "demoext",
        [
            {"id": "websocket.publish"},
            {"id": "websocket.subscribe"},
        ],
    )

    assert validate_wasm_extension_permissions(
        ext_info,
        [
            ExtensionPermission(id="websocket.publish"),
            ExtensionPermission(id="websocket.subscribe"),
        ],
        extension_config,
    ) == [
        ExtensionPermission(id="websocket.publish"),
        ExtensionPermission(id="websocket.subscribe"),
    ]


def test_background_payment_grant_lookup_and_policy_coverage():
    permissions = {
        WALLET_PAY_INVOICE_BACKGROUND_PERMISSION: [
            {
                "id": "grant-1",
                "wallet_id": "wallet-1",
                "enabled": True,
                "max_amount": 5000,
                "destination_policy": "external_allowed",
            }
        ]
    }

    grant = _find_background_payment_grant(permissions, "wallet-1")

    assert grant
    assert grant.max_amount == 5000
    assert _background_destination_policy_covers(
        grant.destination_policy,
        ExtensionBackgroundPaymentDestinationPolicy.OWN_WALLETS_ONLY,
    )
    assert _background_destination_policy_covers(
        grant.destination_policy,
        ExtensionBackgroundPaymentDestinationPolicy.EXTERNAL_ALLOWED,
    )
    assert not _background_destination_policy_covers(
        ExtensionBackgroundPaymentDestinationPolicy.OWN_WALLETS_ONLY,
        ExtensionBackgroundPaymentDestinationPolicy.EXTERNAL_ALLOWED,
    )


def test_wallet_payments_watch_grant_lookup_ignores_disabled_grant():
    permissions = {
        WALLET_PAYMENTS_WATCH_PERMISSION: [
            {"id": "grant-1", "wallet_id": "wallet-1", "enabled": False}
        ]
    }

    grant = _find_wallet_payments_watch_grant(permissions, "wallet-1")

    assert grant
    assert grant.enabled is False


def test_safe_user_extension_permissions_keeps_only_grants_with_ids():
    permissions = {
        WALLET_PAYMENTS_WATCH_PERMISSION: [
            {"id": "grant-1", "wallet_id": "wallet-1", "enabled": True},
            {"wallet_id": "wallet-2", "enabled": True},
            "broken",
        ],
        "broken": "not-a-list",
    }

    safe_permissions = _safe_user_extension_permissions(permissions)

    assert safe_permissions == {
        WALLET_PAYMENTS_WATCH_PERMISSION: [
            {"id": "grant-1", "wallet_id": "wallet-1", "enabled": True}
        ]
    }


def test_user_permission_grant_id_for_wallet_returns_existing_grant_id():
    permissions = {
        WALLET_PAY_INVOICE_BACKGROUND_PERMISSION: [
            {"id": "grant-1", "wallet_id": "wallet-1", "enabled": True}
        ]
    }

    grant_id = _user_permission_grant_id_for_wallet(
        permissions, WALLET_PAY_INVOICE_BACKGROUND_PERMISSION, "wallet-1"
    )

    assert grant_id == "grant-1"


def test_remove_user_permission_grant_removes_only_matching_grant_id():
    permissions = {
        WALLET_PAY_INVOICE_BACKGROUND_PERMISSION: [
            {"id": "grant-1", "wallet_id": "wallet-1", "enabled": True},
            {"id": "grant-2", "wallet_id": "wallet-2", "enabled": True},
        ],
        WALLET_PAYMENTS_WATCH_PERMISSION: [{"id": "grant-3", "wallet_id": "wallet-1"}],
    }

    updated_permissions = _remove_user_permission_grant(permissions, "grant-1")

    assert updated_permissions == {
        WALLET_PAY_INVOICE_BACKGROUND_PERMISSION: [
            {"id": "grant-2", "wallet_id": "wallet-2", "enabled": True}
        ],
        WALLET_PAYMENTS_WATCH_PERMISSION: [{"id": "grant-3", "wallet_id": "wallet-1"}],
    }


def test_remove_user_permission_grant_drops_empty_permission():
    permissions = {
        WALLET_PAYMENTS_WATCH_PERMISSION: [{"id": "grant-1", "wallet_id": "wallet-1"}]
    }

    updated_permissions = _remove_user_permission_grant(permissions, "grant-1")

    assert updated_permissions == {}


@pytest.mark.anyio
async def test_background_payment_check_reports_approved_grant(
    mocker: MockerFixture,
):
    permissions = {
        WALLET_PAY_INVOICE_BACKGROUND_PERMISSION: [
            {
                "id": "grant-1",
                "wallet_id": "wallet-1",
                "enabled": True,
                "max_amount": 5000,
                "destination_policy": "external_allowed",
            }
        ]
    }
    mocker.patch(
        "lnbits.core.views.extension_api.get_wallet",
        mocker.AsyncMock(
            return_value=SimpleNamespace(
                user="user-1",
                is_lightning_shared_wallet=False,
                can_send_payments=True,
            )
        ),
    )

    result = await _check_background_payment_permission(
        "user-1",
        permissions,
        {
            "wallet_id": "wallet-1",
            "max_amount": 1000,
            "destination_policy": "own_wallets_only",
        },
    )

    assert result.id == WALLET_PAY_INVOICE_BACKGROUND_PERMISSION
    assert result.approved is True
    assert result.grant["id"] == "grant-1"
    assert result.grant["max_amount"] == 5000


@pytest.mark.anyio
async def test_wallet_payment_watch_check_returns_requested_unapproved_grant(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.core.views.extension_api.get_wallet",
        mocker.AsyncMock(return_value=SimpleNamespace(user="user-1")),
    )

    result = await _check_wallet_payments_watch_permission(
        "user-1",
        {},
        {"wallet_id": "wallet-1"},
    )

    assert result.id == WALLET_PAYMENTS_WATCH_PERMISSION
    assert result.approved is False
    assert result.grant["wallet_id"] == "wallet-1"
    assert result.grant["enabled"] is True
    assert isinstance(result.grant["id"], str)


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
