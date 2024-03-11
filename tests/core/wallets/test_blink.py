import asyncio
import httpx
import hashlib
import json
import os

import pytest

from lnbits import bolt11
from lnbits.wallets import get_wallet_class

WALLET = get_wallet_class()

url = "https://api.blink.sv/graphql"
headers = {
    "Content-Type": "application/json",
    "X-API-KEY": os.environ.get("BLINK_TOKEN"),
}

@pytest.mark.asyncio
async def test_environment_variables():
  assert 'X-API-KEY' in headers, "X-API-KEY is not present in headers"
  assert isinstance(headers['X-API-KEY'], str), "X-API-KEY is not a string"


@pytest.mark.asyncio
async def test_endpoint():
  async with httpx.AsyncClient() as client:
        url = "https://www.blink.sv/"
        response = await client.get(url)
        assert response.status_code == 200, f"API call failed with status code {response.status_code}"


@pytest.mark.asyncio
async def test_get_balance():
    balance_query = """
        query Me {
        me {
            defaultAccount {
            wallets {
                walletCurrency
                balance
            }
            }
        }
        }
    """
    data = {"query": balance_query, "variables": {}}
    async with httpx.AsyncClient() as client:
      response = await client.post(url, json=data, headers=headers)
      res = response.json()
      wallets = (
          res.get("data", {})
          .get("me", {})
          .get("defaultAccount", {})
          .get("wallets", [])
      )
      btc_balance = next(
          (wallet["balance"] for wallet in wallets if wallet["walletCurrency"] == "BTC"),
          None,
      )
      print("BTC BALANCE {}".format(btc_balance))
      assert True , f"response: {res}"
      assert isinstance(btc_balance, (int, float)), f"Value should be an integer or float, actual value is {btc_balance}"
      assert btc_balance >= 0, "Value should be greater than or equal to 0"
    
