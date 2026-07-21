"""Load shipped offers.py without importing the full lnbits package."""

from __future__ import annotations

import re
from pathlib import Path


def _load_offers_module():
    path = Path(__file__).resolve().parents[2] / "lnbits" / "core" / "services" / "offers.py"
    src = path.read_text(encoding="utf-8")
    src = re.sub(
        r"from loguru import logger\n",
        "class logger:\n    @staticmethod\n    def debug(*a, **k): pass\n",
        src,
    )
    ns: dict = {"__name__": "offers_under_test"}
    exec(compile(src, str(path), "exec"), ns)
    return ns


def test_shipped_offers_module_detects_lno1():
    m = _load_offers_module()
    assert m["is_bolt12_offer"]("lno1" + "a" * 40) is True
    assert m["is_bolt12_offer"]("lnbc1notanoffer") is False
    assert m["is_bolt12_invoice"]("lni1abc") is True
    assert m["is_bolt12"]("lno1" + "x" * 30) is True
    assert m["is_bolt12"]("hello") is False


def test_normalize_accepts_uri_and_case():
    m = _load_offers_module()
    offer = "LNO1" + "A" * 40
    assert m["is_bolt12_offer"](offer) is True
    assert m["is_bolt12_offer"]("  lightning:" + offer + "  ") is True
    assert m["is_bolt12_offer"]("lightning://" + offer.lower() + "?amount=1") is True
    assert m["normalize_bolt12_string"](" lightning:LNO1ABC ") == "lno1abc"


def test_shipped_backends_declare_pay_offer():
    root = Path(__file__).resolve().parents[2]
    for rel in (
        "lnbits/wallets/eclair.py",
        "lnbits/wallets/corelightning.py",
        "lnbits/wallets/clnrest.py",
        "lnbits/wallets/phoenixd.py",
        "lnbits/wallets/base.py",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        assert "def pay_offer" in text, rel


def test_phoenixd_and_eclair_advertise_bolt12_feature():
    root = Path(__file__).resolve().parents[2]
    for rel in ("lnbits/wallets/phoenixd.py", "lnbits/wallets/eclair.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "Feature.bolt12" in text, rel


def test_payments_routes_offers_via_normalize():
    root = Path(__file__).resolve().parents[2]
    payments = (root / "lnbits/core/services/payments.py").read_text(encoding="utf-8")
    assert "is_bolt12_offer" in payments
    assert "pay_offer" in payments
    assert "normalize_bolt12_string" in payments or "is_bolt12_offer" in payments
    assert "fee_reserve(" in payments


def test_pay_offer_uses_negative_outgoing_amount():
    root = Path(__file__).resolve().parents[2]
    payments = (root / "lnbits/core/services/payments.py").read_text(encoding="utf-8")
    start = payments.find("async def pay_offer")
    end = payments.find("async def create_payment_request")
    chunk = payments[start:end]
    # Explicit max_sat/amount reserves a negative outgoing debit.
    assert "create_amount_msat = -amount_msat_hint" in chunk
    assert "check_wallet_limits" in chunk
    assert "ceiling_sat" in chunk
    assert "secrets.token_hex" in chunk  # unique provisional id per attempt
    assert "fee_reserve(" in payments[payments.find("_fundingsource_pay_offer") :]
    # Success path must require backend amount and write negative debit.
    pay_body = payments[payments.find("async def _pay_offer") :]
    assert "payment.amount = -actual" in pay_body
    assert "no amount" in pay_body or "amount_msat is None" in pay_body
    assert "new_checking_id" in pay_body  # persist backend payment hash


def test_payment_api_wires_amount_as_max_sat():
    root = Path(__file__).resolve().parents[2]
    api = (root / "lnbits/core/views/payment_api.py").read_text(encoding="utf-8")
    assert "max_sat=max_sat" in api
    assert "invoice_data.amount" in api


def test_eclair_reads_sent_amount():
    root = Path(__file__).resolve().parents[2]
    eclair = (root / "lnbits/wallets/eclair.py").read_text(encoding="utf-8")
    assert "_sent_amount_msat" in eclair
    assert "recipientAmount" in eclair
    assert "_parse_msat" in eclair


def test_invoice_response_keeps_upstream_fields():
    """Regression: do not reorder/remove InvoiceResponse fields for bolt12 work."""
    root = Path(__file__).resolve().parents[2]
    base = (root / "lnbits/wallets/base.py").read_text(encoding="utf-8")
    start = base.find("class InvoiceResponse")
    end = base.find("class PaymentResponse")
    chunk = base[start:end]
    assert "checking_id" in chunk
    assert "payment_request" in chunk
    assert "preimage" in chunk
    assert "fee_msat" in chunk
    # Field order: checking_id before payment_request (upstream).
    assert chunk.find("checking_id") < chunk.find("payment_request")


def test_cln_pay_offer_uses_fetchinvoice():
    root = Path(__file__).resolve().parents[2]
    cln = (root / "lnbits/wallets/corelightning.py").read_text(encoding="utf-8")
    start = cln.find("async def pay_offer")
    end = cln.find("async def get_invoice_status", start)
    chunk = cln[start:end]
    assert "fetchinvoice" in chunk
    assert '"bolt11": invoice' in chunk
    # pay RPC must not take a top-level "offer" key (that is fetchinvoice only).
    assert 'pay_payload: dict = {"offer"' not in chunk
    assert 'payload = {"offer": offer}' not in chunk


def test_pay_offer_requires_bolt12_feature():
    """pay_offer should fail fast when funding source lacks Feature.bolt12."""
    root = Path(__file__).resolve().parents[2]
    payments = (root / "lnbits/core/services/payments.py").read_text(encoding="utf-8")
    assert "Feature.bolt12" in payments
    assert "does not support BOLT12 offers" in payments


def test_clnrest_advertises_bolt12_and_pay_offer():
    root = Path(__file__).resolve().parents[2]
    text = (root / "lnbits/wallets/clnrest.py").read_text(encoding="utf-8")
    assert "Feature.bolt12" in text
    assert "async def pay_offer" in text
    assert "/v1/fetchinvoice" in text
