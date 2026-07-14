import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.db import core_app_extra
from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.wasm_ext.wasm.config import parse_wasm_extension_config
from lnbits.core.wasm_ext.wasm.events import (
    _payment_extension_id,
    _payment_source_id,
    _wasm_public_invoice_source_tables_from_permissions,
    dispatch_wasm_invoice_paid,
)
from lnbits.core.wasm_ext.wasm.loader import WasmExtension


def test_wasm_invoice_paid_helpers_extract_extension_and_source_tables():
    payment = SimpleNamespace(
        extension="",
        extra={"tag": "demoext", "source_id": "row-1"},
        tag="fallback",
    )
    permissions = [
        ExtensionPermission(
            id="wallet.create_invoice_public",
            policies=[
                {"table": "tip_jars", "wallet_field": "wallet_id"},
                {"table": "", "wallet_field": "wallet_id"},
            ],
        ),
        ExtensionPermission(id="http.request"),
    ]

    assert _payment_extension_id(payment) == "demoext"
    assert _payment_source_id(payment) == "row-1"
    assert _wasm_public_invoice_source_tables_from_permissions(permissions) == [
        "tip_jars"
    ]


@pytest.mark.anyio
async def test_dispatch_wasm_invoice_paid_invokes_registered_event_export_with_owner(
    mocker: MockerFixture,
):
    ext_id = "demo_event_ext"
    extension = _wasm_extension(ext_id)
    registry = core_app_extra.wasm_extension_registry
    registry.register(extension)
    installed_extension = SimpleNamespace(
        permissions=[
            ExtensionPermission(
                id="wallet.create_invoice_public",
                policies=[{"table": "tip_jars", "wallet_field": "wallet_id"}],
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
    invoke_mock = mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.invoke_wasm_extension_export",
        mocker.AsyncMock(),
    )
    payment = _payment(ext_id)

    try:
        await dispatch_wasm_invoice_paid(payment)
    finally:
        registry._extensions.pop(ext_id, None)

    storage_mock.assert_awaited_once_with(ext_id, "tip_jars", "row-1")
    invoke_mock.assert_awaited_once()
    args = invoke_mock.await_args.args
    kwargs = invoke_mock.await_args.kwargs
    assert args[0] == ext_id
    assert args[1] == "on_invoice_paid"
    assert args[2]["paymentHash"] == "payment-hash"
    assert args[2]["payment"] == {"id": "payment-row"}
    assert kwargs["context"] == "event"
    assert kwargs["owner_id"] == "owner-1"
    assert kwargs["trigger_type"] == "event"
    assert kwargs["event_type"] == "invoice_paid"
    assert kwargs["wallet_id"] == "wallet-1"
    assert kwargs["payment_hash"] == "payment-hash"
    assert kwargs["checking_id"] == "checking-id"


@pytest.mark.anyio
async def test_dispatch_wasm_invoice_paid_skips_invalid_event_export_visibility(
    mocker: MockerFixture,
):
    ext_id = "demo_public_event_ext"
    extension = _wasm_extension(ext_id, visibility="public")
    registry = core_app_extra.wasm_extension_registry
    registry.register(extension)
    invoke_mock = mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.invoke_wasm_extension_export",
        mocker.AsyncMock(),
    )

    try:
        await dispatch_wasm_invoice_paid(_payment(ext_id))
    finally:
        registry._extensions.pop(ext_id, None)

    invoke_mock.assert_not_awaited()


def _wasm_extension(ext_id: str, *, visibility: str = "event") -> WasmExtension:
    config = parse_wasm_extension_config(
        ext_id,
        {
            "id": ext_id,
            "name": "Demo event extension",
            "short_description": "Demo",
            "version": "1.0.0",
            "extension_type": "wasm",
            "wasm": {
                "module": "extension.wasm",
                "exports": [
                    {
                        "name": "on_invoice_paid",
                        "visibility": visibility,
                    }
                ],
            },
            "events": {"onInvoicePaid": "on_invoice_paid"},
        },
    )
    root_path = Path(__file__).resolve().parent / ext_id
    return WasmExtension(
        id=ext_id,
        name=config.name,
        version=config.version,
        root_path=root_path,
        module_path=root_path / "extension.wasm",
        wit_path=None,
        world=config.wasm.world,
        exports=config.wasm.exports,
        config=config,
    )


def _payment(ext_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        extension=ext_id,
        extra={"source_id": "row-1"},
        tag=None,
        wallet_id="wallet-1",
        payment_hash="payment-hash",
        checking_id="checking-id",
        amount=1000,
        fee=0,
        bolt11="lnbc1",
        memo="memo",
        pending=False,
        status="success",
        json=lambda: json.dumps({"id": "payment-row"}),
    )
