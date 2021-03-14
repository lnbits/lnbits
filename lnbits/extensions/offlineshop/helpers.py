import trio  # type: ignore
import httpx
import base64
import struct
import hmac
import time


async def get_fiat_rate(currency: str):
    assert currency == "USD", "Only USD is supported as fiat currency."
    return await get_usd_rate()


async def get_usd_rate():
    """
    Returns an average satoshi price from multiple sources.
    """

    satoshi_prices = [None, None, None]

    async def fetch_price(index, url, getter):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url)
                r.raise_for_status()
                satoshi_price = int(100_000_000 / float(getter(r.json())))
                satoshi_prices[index] = satoshi_price
        except Exception:
            pass

    async with trio.open_nursery() as nursery:
        nursery.start_soon(
            fetch_price,
            0,
            "https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD",
            lambda d: d["result"]["XXBTCZUSD"]["c"][0],
        )
        nursery.start_soon(
            fetch_price,
            1,
            "https://www.bitstamp.net/api/v2/ticker/btcusd",
            lambda d: d["last"],
        )
        nursery.start_soon(
            fetch_price,
            2,
            "https://api.coincap.io/v2/rates/bitcoin",
            lambda d: d["data"]["rateUsd"],
        )

    satoshi_prices = [x for x in satoshi_prices if x]
    return sum(satoshi_prices) / len(satoshi_prices)


def hotp(key, counter, digits=6, digest="sha1"):
    key = base64.b32decode(key.upper() + "=" * ((8 - len(key)) % 8))
    counter = struct.pack(">Q", counter)
    mac = hmac.new(key, counter, digest).digest()
    offset = mac[-1] & 0x0F
    binary = struct.unpack(">L", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary)[-digits:].zfill(digits)


def totp(key, time_step=30, digits=6, digest="sha1"):
    return hotp(key, int(time.time() / time_step), digits, digest)
