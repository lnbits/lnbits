from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.payments import Payment, PaymentState
from lnbits.core.models.wallets import WalletPermission
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import (
    CreateFiatInvoicePublicRequest,
    EmptyRequest,
    InvoiceStatusRequest,
)
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.helpers import sha256s
from tests.helpers import make_installable_extension
from tests.unit.test_wasm_extension_permissions import _wasm_config
from tests.unit.test_wasm_invoice_security import _wallet

STATUS_PERMISSION = "wallet.invoice_status"
FIAT_PERMISSION = "wallet.create_fiat_invoice_public"
POLICY = {"table": "attempts", "wallet_field": "wallet", "provider_field": "provider"}


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["pending", "success", "failed"])
async def test_status_only_returns_bound_invoice_state(mocker, state):
    payment = _payment(state)
    lookup = mocker.patch(
        "lnbits.core.crud.payments.get_standalone_payment",
        AsyncMock(return_value=payment),
    )
    reconciled = payment.model_copy(update={"status": PaymentState.SUCCESS})
    update = mocker.patch(
        "lnbits.core.services.payments.update_pending_payment",
        AsyncMock(return_value=reconciled),
    )
    api = ExtensionHostAPI("paywallwasm", [STATUS_PERMISSION], user_id="source-owner")
    result = await api.wallet_invoice_status(_status_request())
    lookup.assert_awaited_once_with("a" * 64, incoming=True)
    assert update.await_count == (state == "pending")
    assert result.model_dump() == {
        "paid": state != "failed",
        "pending": False,
        "failed": state == "failed",
        "amount_msat": 21000,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid",
    [
        "missing",
        "legacy",
        "owner",
        "source",
        "wallet",
        "extension",
        "binding_extension",
        "hash",
        "outgoing",
        "forged_extra",
        "no_owner",
        "no_permission",
        "anonymous",
    ],
)
async def test_status_denies_unrelated_payments_before_backend_lookup(mocker, invalid):
    payment = _payment()
    if invalid == "legacy":
        payment.extension_context = None
    elif invalid == "forged_extra":
        payment.extra = {"source_id": "attempt", "owner_id": sha256s("source-owner")}
        payment.extension_context = None
    elif invalid in {"owner", "source", "wallet", "binding_extension"}:
        field = "extension" if invalid == "binding_extension" else invalid
        assert payment.extension_context is not None
        payment.extension_context[field + "_id"] = "different"
    elif invalid == "extension":
        payment.extension = "other"
    elif invalid == "hash":
        payment.payment_hash = "b" * 64
    elif invalid == "outgoing":
        payment.amount = -21000
    mocker.patch(
        "lnbits.core.crud.payments.get_standalone_payment",
        AsyncMock(return_value=None if invalid == "missing" else payment),
    )
    update = mocker.patch(
        "lnbits.core.services.payments.update_pending_payment", AsyncMock()
    )
    api = ExtensionHostAPI(
        "paywallwasm",
        [] if invalid == "no_permission" else [STATUS_PERMISSION],
        user_id=None if invalid in {"no_owner", "anonymous"} else "source-owner",
        context="event" if invalid == "no_owner" else "user",
    )
    with pytest.raises(PermissionError):
        await api.wallet_invoice_status(_status_request())
    update.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("shared", [False, True])
async def test_fiat_delegates_to_core_with_source_bound_provider(
    mocker, settings, shared
):
    wallet, create = _fiat_setup(mocker, settings, shared=shared)
    result = await _api().wallet_create_fiat_invoice_public(_fiat_request())
    assert result.model_dump() == {
        "payment_hash": "a" * 64,
        "payment_request": "https://checkout.example/pay",
        "amount_msat": 21000,
        "fiat_provider": "stripe",
    }
    args = create.await_args
    assert args.args[0] == wallet.id
    invoice = args.args[1]
    assert invoice.amount == 2.5 and invoice.unit == "USD"
    assert invoice.fiat_provider == "stripe"
    assert invoice.extra == {"tag": "paywallwasm", "source_id": "attempt"}
    assert args.kwargs["extension_context"] == _payment().extension_context
    assert (await _api().wallet_list_fiat_providers(EmptyRequest())).providers == [
        "stripe"
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid",
    [
        "missing_source",
        "other_owner",
        "read_only",
        "provider",
        "disabled",
        "no_permission",
        "no_context",
    ],
)
async def test_fiat_rejects_unapproved_wallets_and_providers(mocker, settings, invalid):
    wallet, create = _fiat_setup(mocker, settings, shared=True)
    if invalid == "missing_source":
        mocker.patch(
            "lnbits.core.wasm_ext.api.host.storage_get_row",
            AsyncMock(return_value=None),
        )
    elif invalid == "other_owner":
        wallet.user = "other"
    elif invalid == "read_only":
        wallet.share_permissions = [WalletPermission.VIEW_PAYMENTS]
    elif invalid == "provider":
        settings.stripe_limits.allowed_users = ["other"]
    elif invalid == "disabled":
        settings.stripe_enabled = False
    api = _api()
    if invalid == "no_permission":
        api.permissions.clear()
    if invalid == "no_context":
        api.user_id = api.owner_id = None
    with pytest.raises(PermissionError):
        await api.wallet_create_fiat_invoice_public(_fiat_request())
    create.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "http://checkout.example",
        "javascript:alert(1)",
        "https://user:secret@checkout.example",
        "https://checkout.example/\nsecret",
        "https://checkout.example\\@evil.example",
        None,
    ],
)
async def test_fiat_rejects_unsafe_checkout_urls(mocker, settings, url):
    _, create = _fiat_setup(mocker, settings)
    create.return_value.extra["fiat_payment_request"] = url
    with pytest.raises(ValueError, match="checkout URL"):
        await _api().wallet_create_fiat_invoice_public(_fiat_request())


def test_checkout_permissions_cannot_expand_wallet_or_provider_sources():
    permission = {"id": FIAT_PERMISSION, "policies": [POLICY]}
    config = _wasm_config("paywallwasm", [permission])
    extension = make_installable_extension("paywallwasm")
    grant = ExtensionPermission.model_validate(permission)
    assert validate_wasm_extension_permissions(extension, [grant], config) == [grant]
    for field in POLICY:
        grant.policies = [{**POLICY, field: "other"}]
        with pytest.raises(ValueError):
            validate_wasm_extension_permissions(extension, [grant], config)
    config["permissions"][0]["policies"] = [{"table": "attempts"}]
    with pytest.raises(ValueError):
        validate_wasm_extension_permissions(extension, [], config)


@pytest.mark.parametrize(
    "amount,currency",
    [(float("inf"), "USD"), (float("nan"), "USD"), (0, "USD"), (1, "sat")],
)
def test_fiat_request_rejects_invalid_amounts_and_currencies(amount, currency):
    with pytest.raises(ValidationError):
        CreateFiatInvoicePublicRequest(
            source_id="attempt", amount=amount, currency=currency
        )


def _payment(state="pending"):
    return Payment(
        checking_id="private",
        payment_hash="a" * 64,
        wallet_id="wallet-1",
        amount=21000,
        fee=0,
        bolt11="invoice",
        status=state,
        extension="paywallwasm",
        preimage="private",
        extra={"fiat_payment_request": "https://checkout.example/pay"},
        extension_context={
            "extension_id": "paywallwasm",
            "owner_id": sha256s("source-owner"),
            "wallet_id": "wallet-1",
            "source_id": "attempt",
        },
    )


def _status_request():
    return InvoiceStatusRequest(payment_hash="a" * 64, source_id="attempt")


def _fiat_request():
    return CreateFiatInvoicePublicRequest(
        source_id="attempt", amount=2.5, currency="USD"
    )


def _api():
    return ExtensionHostAPI(
        "paywallwasm",
        [{"id": FIAT_PERMISSION, "policies": [POLICY]}],
        user_id="source-owner",
    )


def _fiat_setup(mocker, settings, shared=False):
    wallet = _wallet(shared=shared)
    mocker.patch("lnbits.core.crud.wallets.get_wallet", AsyncMock(return_value=wallet))
    mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_row",
        AsyncMock(return_value={"wallet": wallet.id, "provider": "stripe"}),
    )

    # The real storage API scopes returned rows to the invocation owner.
    settings.stripe_enabled = True
    settings.stripe_limits.allowed_users = ["source-owner"]
    create = mocker.patch(
        "lnbits.core.services.payments.create_payment_request",
        AsyncMock(return_value=_payment()),
    )
    return wallet, create
