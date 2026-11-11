from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from lnbits.core.crud import create_wallet, get_payment, update_payment
from lnbits.core.db import core_app_extra
from lnbits.core.models import CreateInvoice, PaymentState
from lnbits.core.models.wallets import Wallet, WalletPermission, WalletType
from lnbits.core.services.payments import create_payment_request
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import (
    CreateInvoicePublicRequest,
    CreateInvoiceRequest,
)
from lnbits.core.wasm_ext.storage.crud import OWNER_ID_FIELD
from lnbits.core.wasm_ext.wasm.events import (
    _wasm_invoice_paid_owner_id,
    dispatch_wasm_invoice_paid,
)
from lnbits.helpers import sha256s
from lnbits.wallets.fake import FakeWallet
from tests.unit.test_wasm_extension_events import _payment as _event_payment
from tests.unit.test_wasm_extension_events import _wasm_extension


@pytest.mark.anyio
@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("metadata", [None, '[["text/plain","Fortune ⚡"]]'])
async def test_public_invoice_binds_owner_and_survives_wallet_change(
    mocker, shared, metadata
):
    wallet = _wallet(shared=shared)
    owner = sha256s(wallet.user)
    row = {"wallet_id": wallet.id, OWNER_ID_FIELD: owner}
    mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_public_row",
        mocker.AsyncMock(return_value=row),
    )
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", mocker.AsyncMock(return_value=wallet)
    )
    payment = _payment("tips")
    if metadata is not None:
        invoice = await FakeWallet().create_invoice(
            21, unhashed_description=metadata.encode("utf-8")
        )
        payment.payment_request = invoice.payment_request
    create = mocker.patch(
        "lnbits.core.services.payments.create_payment_request",
        mocker.AsyncMock(return_value=payment),
    )
    api = ExtensionHostAPI(
        "tips",
        [
            {
                "id": "wallet.create_invoice_public",
                "policies": [{"table": "jars", "wallet_field": "wallet_id"}],
            }
        ],
    )
    await api.wallet_create_invoice_public(
        CreateInvoicePublicRequest(
            source_id="row-1",
            amount=21,
            currency="sat",
            memo="Tip",
            extra={"owner_id": "victim"},
            **({"unhashed_description": metadata} if metadata is not None else {}),
        )
    )
    expected = metadata.encode("utf-8").hex() if metadata is not None else None
    assert create.await_args.args[1].unhashed_description == expected
    payment.extension_context = create.await_args.kwargs["extension_context"]
    payment.wallet_id = wallet.source_wallet_id
    assert payment.extension_context == {
        "extension_id": "tips",
        "owner_id": owner,
        "wallet_id": wallet.source_wallet_id,
        "source_id": "row-1",
    }
    # Current records and permissions may change while the invoice is outstanding.
    row["wallet_id"] = "replacement-wallet"
    source_lookup = mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.storage_get_public_row",
        mocker.AsyncMock(side_effect=AssertionError("must use original binding")),
    )
    wallet_lookup = mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.get_wallet",
        mocker.AsyncMock(side_effect=AssertionError("must use original binding")),
    )
    assert (
        await _wasm_invoice_paid_owner_id(SimpleNamespace(id="tips"), payment) == owner
    )
    source_lookup.assert_not_awaited()
    wallet_lookup.assert_not_awaited()


@pytest.mark.parametrize("metadata", [None, "a" * 4096, "⚡" * 1365 + "a"])
def test_public_invoice_metadata_accepts_utf8_byte_boundary(metadata):
    request = CreateInvoicePublicRequest(
        source_id="row-1",
        amount=21,
        currency="sat",
        memo="",
        unhashed_description=metadata,
    )
    assert request.unhashed_description == metadata


@pytest.mark.parametrize("metadata", ["", "a" * 4097, "⚡" * 1365 + "ab", "😀" * 1025])
def test_public_invoice_metadata_rejects_oversize_utf8(metadata):
    with pytest.raises(ValidationError):
        CreateInvoicePublicRequest(
            source_id="row-1",
            amount=21,
            currency="sat",
            memo="",
            unhashed_description=metadata,
        )


@pytest.mark.anyio
@pytest.mark.parametrize("backend_metadata", [None, b"different metadata", b"invalid"])
async def test_public_invoice_rejects_invalid_description_commitment(
    mocker, backend_metadata
):
    wallet = _wallet()
    mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_public_row",
        mocker.AsyncMock(
            return_value={"wallet_id": wallet.id, OWNER_ID_FIELD: sha256s(wallet.user)}
        ),
    )
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", mocker.AsyncMock(return_value=wallet)
    )
    invoice = await FakeWallet().create_invoice(
        21, memo="Plain description", unhashed_description=backend_metadata
    )
    payment = _payment("tips")
    payment.payment_request = (
        "invalid" if backend_metadata == b"invalid" else invoice.payment_request
    )
    mocker.patch(
        "lnbits.core.services.payments.create_payment_request",
        mocker.AsyncMock(return_value=payment),
    )
    api = ExtensionHostAPI(
        "tips",
        [
            {
                "id": "wallet.create_invoice_public",
                "policies": [{"table": "jars", "wallet_field": "wallet_id"}],
            }
        ],
    )
    with pytest.raises(ValueError, match="Funding backend returned"):
        await api.wallet_create_invoice_public(
            CreateInvoicePublicRequest(
                source_id="row-1",
                amount=21,
                currency="sat",
                memo="",
                unhashed_description='[["text/plain","Fortune ⚡"]]',
            )
        )


@pytest.mark.anyio
async def test_public_invoice_rejects_source_using_another_users_wallet(mocker):
    mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_public_row",
        mocker.AsyncMock(
            return_value={"wallet_id": "wallet-1", OWNER_ID_FIELD: sha256s("attacker")}
        ),
    )
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", mocker.AsyncMock(return_value=_wallet())
    )
    create = mocker.patch(
        "lnbits.core.services.payments.create_payment_request", mocker.AsyncMock()
    )
    api = ExtensionHostAPI(
        "tips",
        [
            {
                "id": "wallet.create_invoice_public",
                "policies": [{"table": "jars", "wallet_field": "wallet_id"}],
            }
        ],
    )
    with pytest.raises(PermissionError, match="does not own"):
        await api.wallet_create_invoice_public(
            CreateInvoicePublicRequest(
                source_id="row-1", amount=21, currency="sat", memo="Tip"
            )
        )
    create.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("source_id", ["victim-source", "", None])
async def test_authenticated_shared_wallet_invoice_uses_authenticated_owner(
    mocker, source_id
):
    wallet = _wallet(shared=True)
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", mocker.AsyncMock(return_value=wallet)
    )
    create = mocker.patch(
        "lnbits.core.services.payments.create_payment_request",
        mocker.AsyncMock(return_value=_payment("tips")),
    )
    api = ExtensionHostAPI("tips", ["wallet.create_invoice"], user_id=wallet.user)
    await api.wallet_create_invoice(
        CreateInvoiceRequest(
            wallet_id=wallet.id,
            tag="tips",
            amount=21,
            currency="sat",
            memo="Tip",
            extra={
                **({"source_id": source_id} if source_id is not None else {}),
                "extension_context": "victim",
            },
        )
    )
    assert create.await_args.kwargs["extension_context"]["source_id"] == (
        source_id or None
    )
    assert create.await_args.kwargs["extension_context"]["owner_id"] == sha256s(
        wallet.user
    )
    assert (
        create.await_args.kwargs["extension_context"]["wallet_id"]
        == wallet.source_wallet_id
    )


@pytest.mark.anyio
@pytest.mark.parametrize("shared", [False, True])
async def test_legacy_invoices_accept_authorised_wallets_and_reject_forged_sources(
    mocker, shared
):
    wallet = _wallet(shared=shared)
    payment = _payment("tips")
    payment.wallet_id = wallet.source_wallet_id
    installed = SimpleNamespace(
        permissions=[
            {
                "id": "wallet.create_invoice_public",
                "policies": [{"table": "jars", "wallet_field": "wallet_id"}],
            }
        ]
    )
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.get_installed_extension",
        mocker.AsyncMock(return_value=installed),
    )
    row = {"wallet_id": wallet.id, OWNER_ID_FIELD: sha256s(wallet.user)}
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.storage_get_public_row",
        mocker.AsyncMock(return_value=row),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.get_wallet",
        mocker.AsyncMock(return_value=wallet),
    )
    extension = SimpleNamespace(id="tips")
    assert await _wasm_invoice_paid_owner_id(extension, payment) == sha256s(wallet.user)
    # A forged owner in extra never replaces the database owner or wallet checks.
    payment.extra["extension_context"] = {"owner_id": "victim"}
    payment.wallet_id = "attacker-wallet"
    assert await _wasm_invoice_paid_owner_id(extension, payment) is None
    payment.wallet_id = wallet.source_wallet_id
    row[OWNER_ID_FIELD] = sha256s("different-owner")
    assert await _wasm_invoice_paid_owner_id(extension, payment) is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field,value",
    [
        ("extension_id", "other"),
        ("wallet_id", "other"),
        ("source_id", "other"),
        ("owner_id", ""),
    ],
)
async def test_invalid_binding_fails_closed_without_legacy_fallback(
    mocker, field, value
):
    payment = _payment("tips")
    payment.extension_context = {
        "extension_id": "tips",
        "wallet_id": "wallet-1",
        "source_id": "row-1",
        "owner_id": "owner",
    }
    payment.extension_context[field] = value
    lookup = mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.storage_get_public_row", mocker.AsyncMock()
    )
    assert (
        await _wasm_invoice_paid_owner_id(SimpleNamespace(id="tips"), payment) is None
    )
    lookup.assert_not_awaited()


@pytest.mark.anyio
async def test_rejected_tagged_event_cannot_fall_back_to_watch_grant(mocker):
    extension = _wasm_extension("tips")
    registry = core_app_extra.wasm_extension_registry
    registry.register(extension)
    payment = _payment("tips")
    payment.extension_context = {"extension_id": "forged"}
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.get_wallet",
        mocker.AsyncMock(return_value=_wallet()),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.wasm.events._wallet_watch_extension_ids",
        mocker.AsyncMock(return_value=["tips"]),
    )
    invoke = mocker.patch(
        "lnbits.core.wasm_ext.wasm.events.invoke_wasm_extension_export",
        mocker.AsyncMock(),
    )
    try:
        await dispatch_wasm_invoice_paid(payment)
    finally:
        registry._extensions.pop("tips", None)
    invoke.assert_not_awaited()


def test_invoice_request_cannot_supply_trusted_context():
    data = CreateInvoice.model_validate(
        {
            "amount": 1,
            "extension_context": {"owner_id": "victim"},
            "extra": {"extension_context": {"owner_id": "victim"}},
        }
    )
    assert "extension_context" not in data.model_dump()
    assert data.extra is not None
    assert data.extra["extension_context"]["owner_id"] == "victim"


@pytest.mark.anyio
async def test_trusted_context_persists_with_invoice_and_survives_updates(
    app, from_user
):
    wallet = await create_wallet(user_id=from_user.id)
    context = {
        "extension_id": "tips",
        "owner_id": sha256s(wallet.user),
        "wallet_id": wallet.id,
        "source_id": "row-1",
    }
    payment = await create_payment_request(
        wallet.id,
        CreateInvoice(amount=1, extension="tips", extra={"source_id": "row-1"}),
        extension_context=context,
    )
    stored = await get_payment(payment.checking_id)
    assert stored.extension_context == context
    stored.status = PaymentState.SUCCESS
    stored.extra["note"] = "updated"
    await update_payment(stored)
    reloaded = await get_payment(payment.checking_id)
    assert reloaded.extension_context == context
    assert (
        await _wasm_invoice_paid_owner_id(SimpleNamespace(id="tips"), reloaded)
        == context["owner_id"]
    )
    # Ordinary invoices may carry arbitrary metadata but cannot create a binding.
    ordinary = await create_payment_request(
        wallet.id, CreateInvoice(amount=1, extra={"extension_context": context})
    )
    assert (await get_payment(ordinary.checking_id)).extension_context is None


@pytest.mark.anyio
async def test_context_migration_preserves_existing_payments(tmp_path, settings):
    from lnbits.core.migrations import m057_add_payment_extension_context
    from lnbits.db import DB_TYPE, SQLITE, Database

    if DB_TYPE != SQLITE:
        pytest.skip("Temporary database test requires SQLite")
    settings.lnbits_data_folder = str(tmp_path)
    database = Database("context_migration")
    async with database.connect() as conn:
        await conn.execute(
            "CREATE TABLE apipayments (checking_id TEXT, amount INTEGER, extra TEXT)"
        )
        await conn.execute(
            "INSERT INTO apipayments VALUES ('old', 21000, :extra)",
            {"extra": '{"source_id":"original"}'},
        )
        await m057_add_payment_extension_context(conn)
        row = await conn.fetchone("SELECT * FROM apipayments WHERE checking_id = 'old'")
        assert row is not None
        assert dict(row) == {
            "checking_id": "old",
            "amount": 21000,
            "extra": '{"source_id":"original"}',
            "extension_context": None,
        }


def _wallet(*, shared=False):
    return Wallet(
        id="shared-alias" if shared else "wallet-1",
        user="source-owner",
        name="Test",
        adminkey="unused",
        inkey="unused",
        wallet_type=(
            WalletType.LIGHTNING_SHARED.value if shared else WalletType.LIGHTNING.value
        ),
        shared_wallet_id="wallet-1" if shared else None,
        share_permissions=[WalletPermission.RECEIVE_PAYMENTS] if shared else [],
    )


def _payment(extension_id):
    payment = _event_payment(extension_id)
    payment.payment_request = payment.bolt11
    return payment
