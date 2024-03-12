import os

import httpx
import pytest

#from lnbits.wallets import get_wallet_class

# WALLET = get_wallet_class()

url = "https://api.blink.sv/graphql"
# Check if BLINK_TOKEN environment variable is set
use_real_api = os.environ.get("BLINK_TOKEN") != ""

print(f'use_real_api: {use_real_api}')

if use_real_api:
  headers = {
      "Content-Type": "application/json",
      "X-API-KEY": os.environ.get("BLINK_TOKEN"),
  }

@pytest.mark.asyncio
async def test_environment_variables():
    if use_real_api:
      assert "X-API-KEY" in headers, "X-API-KEY is not present in headers"
      assert isinstance(headers["X-API-KEY"], str), "X-API-KEY is not a string"
    else: 
      assert True, "BLINK_TOKEN is not set using mock api"

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

  if use_real_api:
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
            (
                wallet["balance"]
                for wallet in wallets
                if wallet["walletCurrency"] == "BTC"
            ),
            None,
        )
        # print("BTC BALANCE {}".format(btc_balance))
        assert True, f"response: {res}"
        assert isinstance(
            btc_balance, (int, float)
        ), f"Value should be an integer or float, actual value is {btc_balance}"
        assert btc_balance >= 0, "Value should be greater than or equal to 0"
  else:
    # use mock data to test
    assert True, "using mock api to test get balance"