"""Unit tests for BOLT12 offer detection (lnbits#2581)."""

from lnbits.core.services.offers import (
    is_bolt12,
    is_bolt12_invoice,
    is_bolt12_offer,
    normalize_bolt12_string,
)


def test_is_bolt12_offer_accepts_lno1_prefix():
    assert is_bolt12_offer("lno1" + "a" * 40)
    assert is_bolt12_offer("lno" + "abcdefghij")


def test_is_bolt12_offer_normalizes_case_uri_and_whitespace():
    raw = "lno1" + "a" * 40
    assert is_bolt12_offer("  " + raw.upper() + "  ")
    assert is_bolt12_offer("lightning:" + raw)
    assert is_bolt12_offer("LIGHTNING://" + raw.upper() + "?amount=1")
    assert normalize_bolt12_string("lightning:" + raw.upper()) == raw


def test_is_bolt12_offer_rejects_bolt11_and_garbage():
    bolt11 = (
        "lnbc1pvjluezpp5qqqsyqcyq5rqwzqfqqqsyqcyq5rqwzqfqqqsyqcyq5rqwzqfqypq"
        "dpl2pkx2ctnv5sxxmmwwd5kgetjypeh2ursdae8g6twvus8g6rfwvs8qun0dfjkxaq"
    )
    assert not is_bolt12_offer(bolt11)
    assert not is_bolt12_offer("")
    assert not is_bolt12_offer("not-an-offer")
    assert not is_bolt12_offer("lnurl1xyz")


def test_is_bolt12_invoice_prefix():
    assert is_bolt12_invoice("lni1abc")
    assert is_bolt12_invoice("  LNI1ABC  ")
    assert not is_bolt12_invoice("lno1abc")


def test_is_bolt12_union():
    assert is_bolt12("lno1" + "x" * 30)
    assert is_bolt12("lni1" + "x" * 30)
    assert not is_bolt12("lnbc1xyz")
