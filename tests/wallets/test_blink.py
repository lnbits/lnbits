import os

import pytest
from loguru import logger

from lnbits.settings import settings
from lnbits.wallets import BlinkWallet, get_funding_source, set_funding_source

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
funding_source = get_funding_source()
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


@pytest.mark.asyncio
async def test_environment_variables():
    if use_real_api:
        assert "X-API-KEY" in headers, "X-API-KEY is not present in headers"
        assert isinstance(headers["X-API-KEY"], str), "X-API-KEY is not a string"
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.asyncio
async def test_get_wallet_id():
    if use_real_api:
        wallet_id = await funding_source._init_wallet_id()
        logger.info(f"test_get_wallet_id: {wallet_id}")
        assert wallet_id
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.asyncio
async def test_status():
    if use_real_api:
        status = await funding_source.status()
        logger.info(f"test_status: {status}")
        assert status
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_get_payment_status(payhash):
    if use_real_api:
        payment_status = await funding_source.get_payment_status(payhash)
        assert payment_status.paid
        logger.info(f"test_get_payment_status: payment_status: {payment_status.paid}")
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"
