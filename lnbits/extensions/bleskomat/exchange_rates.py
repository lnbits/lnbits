import json
import os
from typing import Callable, Union

import httpx

fiat_currencies = json.load(
    open(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "fiat_currencies.json"
        ),
        "r",
    )
)

exchange_rate_providers: dict[
    str, dict[str, Union[str, Callable[[dict, dict], str]]]
] = {
    "bitfinex": {
        "name": "Bitfinex",
        "domain": "bitfinex.com",
        "api_url": "https://api.bitfinex.com/v1/pubticker/{from}{to}",
        "getter": lambda data, replacements: data["last_price"],
    },
    "bitstamp": {
        "name": "Bitstamp",
        "domain": "bitstamp.net",
        "api_url": "https://www.bitstamp.net/api/v2/ticker/{from}{to}/",
        "getter": lambda data, replacements: data["last"],
    },
    "coinbase": {
        "name": "Coinbase",
        "domain": "coinbase.com",
        "api_url": "https://api.coinbase.com/v2/exchange-rates?currency={FROM}",
        "getter": lambda data, replacements: data["data"]["rates"][replacements["TO"]],
    },
    "coinmate": {
        "name": "CoinMate",
        "domain": "coinmate.io",
        "api_url": "https://coinmate.io/api/ticker?currencyPair={FROM}_{TO}",
        "getter": lambda data, replacements: data["data"]["last"],
    },
    "kraken": {
        "name": "Kraken",
        "domain": "kraken.com",
        "api_url": "https://api.kraken.com/0/public/Ticker?pair=XBT{TO}",
        "getter": lambda data, replacements: data["result"][
            "XXBTZ" + replacements["TO"]
        ]["c"][0],
    },
}

exchange_rate_providers_serializable = {}
for ref, exchange_rate_provider in exchange_rate_providers.items():
    exchange_rate_provider_serializable = {}
    for key, value in exchange_rate_provider.items():
        if not callable(value):
            exchange_rate_provider_serializable[key] = value
    exchange_rate_providers_serializable[ref] = exchange_rate_provider_serializable


async def fetch_fiat_exchange_rate(currency: str, provider: str):

    replacements = {
        "FROM": "BTC",
        "from": "btc",
        "TO": currency.upper(),
        "to": currency.lower(),
    }

    api_url_or_none = exchange_rate_providers[provider]["api_url"]
    if api_url_or_none is not None:
        api_url = str(api_url_or_none)
        for key in replacements.keys():
            api_url = api_url.replace("{" + key + "}", replacements[key])
        async with httpx.AsyncClient() as client:
            r = await client.get(api_url)
            r.raise_for_status()
            data = r.json()
    else:
        data = {}
    getter = exchange_rate_providers[provider]["getter"]
    print(getter)
    if callable(getter):
        rate = float(getter(data, replacements))
    return rate
