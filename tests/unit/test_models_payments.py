import json

import pytest
from pydantic import ValidationError

from lnbits.core.models import (
    CreateInvoice,
    CreatePayment,
    Payment,
    PaymentExtensionContext,
)
from lnbits.db import POSTGRES, SQLITE, dict_to_model, model_to_dict


@pytest.mark.parametrize("payment_request", ["lnbc1invoice", "lno1offer"])
@pytest.mark.parametrize(
    "fields", [("payment_request",), ("bolt11",), ("payment_request", "bolt11")]
)
def test_create_invoice_accepts_payment_request(payment_request, fields):
    invoice = CreateInvoice.model_validate(dict.fromkeys(fields, payment_request))

    assert invoice.payment_request == payment_request


@pytest.mark.parametrize("payment_request", [None, ""])
def test_create_invoice_uses_legacy_payment_request_when_empty(payment_request):
    invoice = CreateInvoice(payment_request=payment_request, bolt11="lnbc1invoice")

    assert invoice.payment_request == "lnbc1invoice"


@pytest.mark.parametrize("bolt11", [None, ""])
def test_create_invoice_accepts_empty_legacy_payment_request(bolt11):
    invoice = CreateInvoice(payment_request="lno1offer", bolt11=bolt11)

    assert invoice.payment_request == "lno1offer"


def test_create_invoice_rejects_conflicting_payment_requests():
    with pytest.raises(ValidationError, match="payment_request and bolt11 must match"):
        CreateInvoice(payment_request="lno1offer", bolt11="lnbc1invoice")


def test_create_invoice_receiving_does_not_require_payment_request():
    invoice = CreateInvoice(out=False, amount=21)

    assert invoice.payment_request is None


@pytest.mark.parametrize("db_type", [SQLITE, POSTGRES])
@pytest.mark.parametrize("source_id", [None, "row-1"])
def test_payment_extension_context_preserves_database_and_api_json(
    monkeypatch, db_type, source_id
):
    monkeypatch.setattr("lnbits.db.DB_TYPE", db_type)
    context = {**_extension_context(), "source_id": source_id}
    payment = Payment.model_validate({**_payment_data(), "extension_context": context})
    assert isinstance(payment.extension_context, PaymentExtensionContext)
    row = model_to_dict(payment)
    assert json.loads(row["extension_context"]) == context

    restored = dict_to_model(row, Payment)
    assert restored.extension_context == payment.extension_context
    assert json.loads(restored.model_dump_json())["extension_context"] == context


@pytest.mark.parametrize("stored_context", [None, "null"])
def test_payment_reads_legacy_null_extension_context(stored_context):
    row = {**_payment_data(), "extension_context": stored_context}
    assert dict_to_model(row, Payment).extension_context is None


def test_payment_reads_extension_context_without_optional_source():
    context = _extension_context()
    row = {**_payment_data(), "extension_context": json.dumps(context)}
    payment = dict_to_model(row, Payment)
    assert payment.extension_context == PaymentExtensionContext(**context)
    assert payment.extension_context is not None
    assert payment.extension_context.source_id is None


@pytest.mark.parametrize("field", ["extension_id", "owner_id", "wallet_id"])
@pytest.mark.parametrize("invalid", ["missing", "empty", "null", "wrong_type"])
def test_payment_rejects_invalid_extension_context_on_creation_and_load(field, invalid):
    context = _extension_context()
    if invalid == "missing":
        context.pop(field)
    else:
        context[field] = {"empty": "", "null": None, "wrong_type": 123}[invalid]

    with pytest.raises(ValidationError):
        CreatePayment.model_validate(
            {
                "wallet_id": "wallet-1",
                "payment_hash": "a" * 64,
                "bolt11": "invoice",
                "amount_msat": 21000,
                "memo": "Tip",
                "extension_context": context,
            }
        )
    with pytest.raises(ValidationError):
        dict_to_model(
            {**_payment_data(), "extension_context": json.dumps(context)}, Payment
        )


@pytest.mark.parametrize(
    "field", ["extension_id", "owner_id", "wallet_id", "source_id"]
)
def test_payment_extension_context_is_frozen(field):
    context = PaymentExtensionContext(**_extension_context())
    with pytest.raises(ValidationError, match="frozen"):
        setattr(context, field, "different")


def _extension_context():
    return {"extension_id": "tips", "owner_id": "owner", "wallet_id": "wallet-1"}


def _payment_data():
    return {
        "checking_id": "checking-id",
        "payment_hash": "a" * 64,
        "wallet_id": "wallet-1",
        "amount": 21000,
        "fee": 0,
        "bolt11": "invoice",
        "extension": "tips",
    }
