import pytest
from pydantic import ValidationError

from lnbits.core.models import CreateInvoice


@pytest.mark.parametrize("payment_request", ["lnbc1invoice", "lno1offer"])
@pytest.mark.parametrize(
    "fields", [("payment_request",), ("bolt11",), ("payment_request", "bolt11")]
)
def test_create_invoice_accepts_payment_request(payment_request, fields):
    invoice = CreateInvoice.parse_obj(dict.fromkeys(fields, payment_request))

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
