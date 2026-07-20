import os
from typing import cast
from unittest.mock import AsyncMock

import pytest
from loguru import logger

from lnbits.settings import settings
from lnbits.wallets import BlinkWallet, get_funding_source, set_funding_source
from lnbits.wallets.base import PaymentStatus

settings.lnbits_backend_wallet_class = "BlinkWallet"
settings.blink_token = "mock"
settings.blink_api_endpoint = "https://api.blink.sv/graphql"

# Check if BLINK_TOKEN environment variable is set
use_real_api = os.environ.get("BLINK_TOKEN") is not None
logger.info(f"use_real_api: {use_real_api}")

if use_real_api:
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": os.environ.get("BLINK_TOKEN"),
    }
    settings.blink_token = os.environ.get("BLINK_TOKEN")


logger.info(
    f"settings.lnbits_backend_wallet_class: {settings.lnbits_backend_wallet_class}"
)
logger.info(f"settings.blink_api_endpoint: {settings.blink_api_endpoint}")
logger.info(f"settings.blink_token: {settings.blink_token}")

set_funding_source()
funding_source = cast(BlinkWallet, get_funding_source())
assert isinstance(funding_source, BlinkWallet)


@pytest.fixture(scope="session")
def payhash():
    # put your external payment hash here
    payment_hash = "14d7899c3456bcd78f7f18a70d782b8eadb2de974e80dc5120e133032423dcda"
    return payment_hash


@pytest.fixture(scope="session")
def outbound_bolt11():
    # put your outbound bolt11 here
    bolt11 = "lnbc1u1pjl0uhypp5yxvdqq923atm9ywkpgtu3yxv9w2n44ensrkwfyagvmzqhml2x9gqdpv2phhwetjv4jzqcneypqyc6t8dp6xu6twva2xjuzzda6qcqzzsxqrrsssp5h3qlnnlfqekquacwwj9yu7fhujyzxhzqegpxenscw45pgv6xakfq9qyyssqqjruygw0jrcg3365jksxn6yhsxx7c5pdjrjdlyvuhs7xh8r409h4e3kucc54kgh34pscaq3mg7hn55l8a0qszgzex80amwrp4gkdgqcpkse88y"  # noqa: E501
    return bolt11


@pytest.mark.anyio
async def test_environment_variables():
    if use_real_api:
        assert "X-API-KEY" in headers, "X-API-KEY is not present in headers"
        assert isinstance(headers["X-API-KEY"], str), "X-API-KEY is not a string"
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_get_wallet_id():
    if use_real_api:
        wallet_id = await funding_source._init_wallet_id()
        logger.info(f"test_get_wallet_id: {wallet_id}")
        assert wallet_id
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_status():
    if use_real_api:
        status = await funding_source.status()
        logger.info(f"test_status: {status}")
        assert status
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_create_invoice():
    if use_real_api:
        invoice_response = await funding_source.create_invoice(amount=1000, memo="test")
        assert invoice_response.ok is True
        assert invoice_response.payment_request
        assert invoice_response.checking_id
        logger.info(f"test_create_invoice: ok: {invoice_response.ok}")
        logger.info(
            f"test_create_invoice: payment_request: {invoice_response.payment_request}"
        )

        payment_status = await funding_source.get_invoice_status(
            invoice_response.checking_id
        )
        assert payment_status.paid is None  # still pending

        logger.info(
            f"test_create_invoice: PaymentStatus is Still Pending: {payment_status.paid is None}"  # noqa: E501
        )
        logger.info(
            f"test_create_invoice: PaymentStatusfee_msat: {payment_status.fee_msat}"
        )
        logger.info(
            f"test_create_invoice: PaymentStatus preimage: {payment_status.preimage}"
        )

    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_pay_invoice_self_payment():
    if use_real_api:
        invoice_response = await funding_source.create_invoice(amount=100, memo="test")
        assert invoice_response.ok is True
        bolt11 = invoice_response.payment_request
        assert bolt11 is not None
        payment_response = await funding_source.pay_invoice(bolt11, fee_limit_msat=100)
        assert payment_response.ok is False  # can't pay self
        assert payment_response.error_message

    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_outbound_invoice_payment(outbound_bolt11):
    if use_real_api:
        payment_response = await funding_source.pay_invoice(
            outbound_bolt11, fee_limit_msat=100
        )
        assert payment_response.ok is True
        assert payment_response.checking_id
        logger.info(f"test_outbound_invoice_payment: ok: {payment_response.ok}")
        logger.info(
            f"test_outbound_invoice_payment: checking_id: {payment_response.checking_id}"  # noqa: E501
        )
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_get_payment_status(payhash):
    if use_real_api:
        payment_status = await funding_source.get_payment_status(payhash)
        assert payment_status.paid
        logger.info(f"test_get_payment_status: payment_status: {payment_status.paid}")
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


# Reproducible bolt11 invoices (fixed timestamp, long expiry) used to test the
# fee probing logic in pay_invoice without hitting the live Blink API.
# amount invoice: 1000 sat (1_000_000 msat)
AMOUNT_BOLT11 = (
    "lnbc10u1pj48ugqpp5qqqsyqcyq5rqwzqfqqqsyqcyq5rqwzqfqqqsyqcyq5rqwzqfqypqsp5"
    "zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zygsdq8w3jhxaqxq8zals8squ"
    "qsakyemlpj9guae3a9havssjcjewgr24hedxkq6t978jk99srrxx9azy6k0cs66a757cfdc43"
    "vkfhmlexyzdqtytzzteh2n4qngapgpesavte"
)
# zero-amount (amountless) invoice
ZERO_BOLT11 = (
    "lnbc1pj48ugqpp5qqqsyqcyq5rqwzqfqqqsyqcyq5rqwzqfqqqsyqcyq5rqwzqfqypqsp5zyg"
    "3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3zygsdq8w3jhxaqxq8zals8sq3c00"
    "hc6end9u8pafqge29y690e2x0kztq0l9z4dfd2yg8au9xuwxz9a2hy2hn2jqzq2mpy43tx9td"
    "wxcy6yuc9ghuqkzj3kruh4tpcgp7n84qu"
)


def _make_blink_wallet_with_mock(graphql_side_effect):
    """Build a BlinkWallet with a mocked GraphQL layer for pay_invoice tests."""
    settings.blink_api_endpoint = "https://api.blink.sv/graphql"
    settings.blink_ws_endpoint = "wss://ws.blink.sv/graphql"
    settings.blink_token = settings.blink_token or "mock"
    wallet = BlinkWallet()
    wallet._wallet_id = "mock_wallet_id"
    wallet._graphql_query = graphql_side_effect  # type: ignore[method-assign]
    wallet.get_payment_status = AsyncMock(  # type: ignore[method-assign]
        return_value=PaymentStatus(paid=True, fee_msat=1000, preimage="preimage")
    )
    return wallet


@pytest.mark.anyio
async def test_pay_invoice_amount_invoice_probes_and_sends():
    """Amount invoices are probed via lnInvoiceFeeProbe then sent."""
    calls = {"probe": 0, "send": 0}

    async def graphql(payload):
        query = payload["query"]
        if "lnInvoiceFeeProbe" in query:
            calls["probe"] += 1
            return {"data": {"lnInvoiceFeeProbe": {"amount": 1, "errors": []}}}
        if "lnNoAmountInvoiceFeeProbe" in query:
            raise AssertionError("must not probe amount invoice as no-amount")
        if "lnInvoicePaymentSend" in query:
            calls["send"] += 1
            return {
                "data": {"lnInvoicePaymentSend": {"status": "SUCCESS", "errors": []}}
            }
        return {"data": {}}

    wallet = _make_blink_wallet_with_mock(graphql)
    response = await wallet.pay_invoice(AMOUNT_BOLT11, fee_limit_msat=5000)

    assert calls["probe"] == 1
    assert calls["send"] == 1
    assert response.ok is True
    assert response.fee_msat == 1000


@pytest.mark.anyio
async def test_pay_invoice_rejects_when_probed_fee_exceeds_limit():
    """A probed fee above the fee limit rejects the payment before sending."""
    calls = {"send": 0}

    async def graphql(payload):
        query = payload["query"]
        if "lnInvoiceFeeProbe" in query:
            # 1 sat = 1000 msat, above the 500 msat limit below
            return {"data": {"lnInvoiceFeeProbe": {"amount": 1, "errors": []}}}
        if "lnInvoicePaymentSend" in query:
            calls["send"] += 1
            return {
                "data": {"lnInvoicePaymentSend": {"status": "SUCCESS", "errors": []}}
            }
        return {"data": {}}

    wallet = _make_blink_wallet_with_mock(graphql)
    response = await wallet.pay_invoice(AMOUNT_BOLT11, fee_limit_msat=500)

    assert calls["send"] == 0
    assert response.ok is False
    assert response.error_message is not None
    assert "exceeds" in response.error_message


@pytest.mark.anyio
async def test_pay_invoice_zero_amount_skips_probe_and_sends():
    """Zero-amount invoices cannot be probed and fall back to sending."""
    settings.blink_send_without_probe = True
    calls = {"probe": 0, "send": 0}

    async def graphql(payload):
        query = payload["query"]
        if "FeeProbe" in query:
            calls["probe"] += 1
            raise AssertionError("zero-amount invoices must not be probed")
        if "lnInvoicePaymentSend" in query:
            calls["send"] += 1
            return {
                "data": {"lnInvoicePaymentSend": {"status": "SUCCESS", "errors": []}}
            }
        return {"data": {}}

    wallet = _make_blink_wallet_with_mock(graphql)
    response = await wallet.pay_invoice(ZERO_BOLT11, fee_limit_msat=5000)

    assert calls["probe"] == 0
    assert calls["send"] == 1
    assert response.ok is True
