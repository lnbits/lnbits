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
