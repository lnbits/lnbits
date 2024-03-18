import pytest
import os
from loguru import logger

from lnbits.wallets import get_wallet_class
from lnbits.settings import settings

settings.blink_token = "mock"
settings.blink_api_endpoint="https://api.blink.sv/graphql"

# Check if BLINK_TOKEN environment variable is set
use_real_api = os.environ.get("BLINK_TOKEN") is not None
logger.info(f'use_real_api: {use_real_api}')

if use_real_api:
  headers = {
      "Content-Type": "application/json",
      "X-API-KEY": os.environ.get("BLINK_TOKEN"),
  }
  settings.blink_token = os.environ.get("BLINK_TOKEN")

logger.info(f'settings.blink_api_endpoint: {settings.blink_api_endpoint}')
logger.info(f'settings.blink_token: {settings.blink_token}')

WALLET = get_wallet_class()

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
      # WALLET = get_wallet_class()
      id = await WALLET.get_wallet_id()
      logger.info(f'test_get_wallet_id: {id}')
      assert id
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"

@pytest.mark.asyncio
async def test_status():
   if use_real_api:
     status = await WALLET.status()
     logger.info(f'test_status: {status}')
     assert status
   else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"

@pytest.mark.asyncio
async def test_create_invoice():
   if use_real_api:
      invoice_response = await WALLET.create_invoice(amount=1000,
                                                       memo="test")
      assert invoice_response.ok is True
      assert invoice_response.payment_request
      assert invoice_response.checking_id
      logger.info(f'test_create_invoice: ok: {invoice_response.ok}')
      logger.info(f'test_create_invoice: payment_request: {invoice_response.payment_request}')

      payment_status = await WALLET.get_invoice_status(invoice_response.checking_id)
      assert payment_status.paid is None # still pending

      logger.info(f'test_create_invoice: PaymentStatus is Still Pending: {payment_status.paid is None}')
      logger.info(f'test_create_invoice: PaymentStatusfee_msat: {payment_status.fee_msat}')
      logger.info(f'test_create_invoice: PaymentStatus preimage: {payment_status.preimage}')

   else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"

# @pytest.mark.asyncio
# async def test_pay_invoice():
#    if use_real_api:

