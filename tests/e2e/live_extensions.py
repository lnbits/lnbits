from __future__ import annotations

from tests.e2e.extension_helpers import ExtensionUnderTest

TIPS = ExtensionUnderTest(
    ext_id="tips",
    name="Tips",
    manifest_url=(
        "https://raw.githubusercontent.com/lnbits/tips/refs/heads/main/manifest.json"
    ),
    repository="lnbits/tips",
    permission_texts=("Make background payments",),
)
BIGPAYMENT = ExtensionUnderTest(
    ext_id="bigpayment",
    name="BigPayment",
    manifest_url=(
        "https://raw.githubusercontent.com/lnbits/bigpayment/refs/heads/main/"
        "manifest.json"
    ),
    repository="lnbits/bigpayment",
    permission_texts=("Pay invoices",),
)
PINGPONG = ExtensionUnderTest(
    ext_id="pingpong",
    name="Ping Pong",
    manifest_url=(
        "https://raw.githubusercontent.com/lnbits/pingpong/refs/heads/main/"
        "manifest.json"
    ),
    repository="lnbits/pingpong",
    permission_texts=("Make background payments",),
)
PAYSPLIT = ExtensionUnderTest(
    ext_id="paysplit",
    name="PaySplit",
    manifest_url=(
        "https://raw.githubusercontent.com/lnbits/paysplit/refs/heads/main/"
        "manifest.json"
    ),
    repository="lnbits/paysplit",
    permission_texts=("Watch wallet payments",),
)

LIVE_EXTENSIONS = (TIPS, BIGPAYMENT, PINGPONG, PAYSPLIT)
