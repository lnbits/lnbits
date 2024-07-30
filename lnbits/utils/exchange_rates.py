import asyncio
from typing import Callable, NamedTuple

import httpx
from loguru import logger

from lnbits.settings import settings
from lnbits.utils.cache import cache

currencies = {
    "AED": "United Arab Emirates Dirham",
    "AFN": "Afghan Afghani",
    "ALL": "Albanian Lek",
    "AMD": "Armenian Dram",
    "ANG": "Netherlands Antillean Gulden",
    "AOA": "Angolan Kwanza",
    "ARS": "Argentine Peso",
    "AUD": "Australian Dollar",
    "AWG": "Aruban Florin",
    "AZN": "Azerbaijani Manat",
    "BAM": "Bosnia and Herzegovina Convertible Mark",
    "BBD": "Barbadian Dollar",
    "BDT": "Bangladeshi Taka",
    "BGN": "Bulgarian Lev",
    "BHD": "Bahraini Dinar",
    "BIF": "Burundian Franc",
    "BMD": "Bermudian Dollar",
    "BND": "Brunei Dollar",
    "BOB": "Bolivian Boliviano",
    "BRL": "Brazilian Real",
    "BSD": "Bahamian Dollar",
    "BTN": "Bhutanese Ngultrum",
    "BWP": "Botswana Pula",
    "BYN": "Belarusian Ruble",
    "BYR": "Belarusian Ruble",
    "BZD": "Belize Dollar",
    "CAD": "Canadian Dollar",
    "CDF": "Congolese Franc",
    "CHF": "Swiss Franc",
    "CLF": "Unidad de Fomento",
    "CLP": "Chilean Peso",
    "CNH": "Chinese Renminbi Yuan Offshore",
    "CNY": "Chinese Renminbi Yuan",
    "COP": "Colombian Peso",
    "CRC": "Costa Rican Colón",
    "CUC": "Cuban Convertible Peso",
    "CVE": "Cape Verdean Escudo",
    "CZK": "Czech Koruna",
    "DJF": "Djiboutian Franc",
    "DKK": "Danish Krone",
    "DOP": "Dominican Peso",
    "DZD": "Algerian Dinar",
    "EGP": "Egyptian Pound",
    "ERN": "Eritrean Nakfa",
    "ETB": "Ethiopian Birr",
    "EUR": "Euro",
    "FJD": "Fijian Dollar",
    "FKP": "Falkland Pound",
    "GBP": "British Pound",
    "GEL": "Georgian Lari",
    "GGP": "Guernsey Pound",
    "GHS": "Ghanaian Cedi",
    "GIP": "Gibraltar Pound",
    "GMD": "Gambian Dalasi",
    "GNF": "Guinean Franc",
    "GTQ": "Guatemalan Quetzal",
    "GYD": "Guyanese Dollar",
    "HKD": "Hong Kong Dollar",
    "HNL": "Honduran Lempira",
    "HRK": "Croatian Kuna",
    "HTG": "Haitian Gourde",
    "HUF": "Hungarian Forint",
    "IDR": "Indonesian Rupiah",
    "ILS": "Israeli New Sheqel",
    "IMP": "Isle of Man Pound",
    "INR": "Indian Rupee",
    "IQD": "Iraqi Dinar",
    "IRT": "Iranian Toman",
    "ISK": "Icelandic Króna",
    "JEP": "Jersey Pound",
    "JMD": "Jamaican Dollar",
    "JOD": "Jordanian Dinar",
    "JPY": "Japanese Yen",
    "KES": "Kenyan Shilling",
    "KGS": "Kyrgyzstani Som",
    "KHR": "Cambodian Riel",
    "KMF": "Comorian Franc",
    "KRW": "South Korean Won",
    "KWD": "Kuwaiti Dinar",
    "KYD": "Cayman Islands Dollar",
    "KZT": "Kazakhstani Tenge",
    "LAK": "Lao Kip",
    "LBP": "Lebanese Pound",
    "LKR": "Sri Lankan Rupee",
    "LRD": "Liberian Dollar",
    "LSL": "Lesotho Loti",
    "LYD": "Libyan Dinar",
    "MAD": "Moroccan Dirham",
    "MDL": "Moldovan Leu",
    "MGA": "Malagasy Ariary",
    "MKD": "Macedonian Denar",
    "MMK": "Myanmar Kyat",
    "MNT": "Mongolian Tögrög",
    "MOP": "Macanese Pataca",
    "MRO": "Mauritanian Ouguiya",
    "MUR": "Mauritian Rupee",
    "MVR": "Maldivian Rufiyaa",
    "MWK": "Malawian Kwacha",
    "MXN": "Mexican Peso",
    "MYR": "Malaysian Ringgit",
    "MZN": "Mozambican Metical",
    "NAD": "Namibian Dollar",
    "NGN": "Nigerian Naira",
    "NIO": "Nicaraguan Córdoba",
    "NOK": "Norwegian Krone",
    "NPR": "Nepalese Rupee",
    "NZD": "New Zealand Dollar",
    "OMR": "Omani Rial",
    "PAB": "Panamanian Balboa",
    "PEN": "Peruvian Sol",
    "PGK": "Papua New Guinean Kina",
    "PHP": "Philippine Peso",
    "PKR": "Pakistani Rupee",
    "PLN": "Polish Złoty",
    "PYG": "Paraguayan Guaraní",
    "QAR": "Qatari Riyal",
    "RON": "Romanian Leu",
    "RSD": "Serbian Dinar",
    "RUB": "Russian Ruble",
    "RWF": "Rwandan Franc",
    "SAR": "Saudi Riyal",
    "SBD": "Solomon Islands Dollar",
    "SCR": "Seychellois Rupee",
    "SEK": "Swedish Krona",
    "SGD": "Singapore Dollar",
    "SHP": "Saint Helenian Pound",
    "SLL": "Sierra Leonean Leone",
    "SOS": "Somali Shilling",
    "SRD": "Surinamese Dollar",
    "SSP": "South Sudanese Pound",
    "STD": "São Tomé and Príncipe Dobra",
    "SVC": "Salvadoran Colón",
    "SZL": "Swazi Lilangeni",
    "THB": "Thai Baht",
    "TJS": "Tajikistani Somoni",
    "TMT": "Turkmenistani Manat",
    "TND": "Tunisian Dinar",
    "TOP": "Tongan Pa'anga",
    "TRY": "Turkish Lira",
    "TTD": "Trinidad and Tobago Dollar",
    "TWD": "New Taiwan Dollar",
    "TZS": "Tanzanian Shilling",
    "UAH": "Ukrainian Hryvnia",
    "UGX": "Ugandan Shilling",
    "USD": "US Dollar",
    "UYU": "Uruguayan Peso",
    "UZS": "Uzbekistan Som",
    "VEF": "Venezuelan Bolívar",
    "VES": "Venezuelan Bolívar Soberano",
    "VND": "Vietnamese Đồng",
    "VUV": "Vanuatu Vatu",
    "WST": "Samoan Tala",
    "XAF": "Central African Cfa Franc",
    "XAG": "Silver (Troy Ounce)",
    "XAU": "Gold (Troy Ounce)",
    "XCD": "East Caribbean Dollar",
    "XDR": "Special Drawing Rights",
    "XOF": "West African Cfa Franc",
    "XPD": "Palladium",
    "XPF": "Cfp Franc",
    "XPT": "Platinum",
    "YER": "Yemeni Rial",
    "ZAR": "South African Rand",
    "ZMW": "Zambian Kwacha",
    "ZWL": "Zimbabwean Dollar",
}


def allowed_currencies():
    if len(settings.lnbits_allowed_currencies) > 0:
        return [
            item
            for item in currencies.keys()
            if item.upper() in settings.lnbits_allowed_currencies
        ]
    return list(currencies.keys())


class Provider(NamedTuple):
    name: str
    domain: str
    api_url: str
    getter: Callable
    exclude_to: list = []


exchange_rate_providers = {
    # https://binance-docs.github.io/apidocs/spot/en/#symbol-price-ticker
    "binance": Provider(
        "Binance",
        "binance.com",
        "https://api.binance.com/api/v3/ticker/price?symbol={FROM}{TO}",
        lambda data, replacements: data["price"],
        ["czk"],
    ),
    "blockchain": Provider(
        "Blockchain",
        "blockchain.com",
        "https://blockchain.info/tobtc?currency={TO}&value=1000000",
        lambda data, replacements: 1000000 / data,
    ),
    "exir": Provider(
        "Exir",
        "exir.io",
        "https://api.exir.io/v1/ticker?symbol={from}-{to}",
        lambda data, replacements: data["last"],
        ["czk", "eur"],
    ),
    "bitfinex": Provider(
        "Bitfinex",
        "bitfinex.com",
        "https://api.bitfinex.com/v1/pubticker/{from}{to}",
        lambda data, replacements: data["last_price"],
        ["czk"],
    ),
    "bitstamp": Provider(
        "Bitstamp",
        "bitstamp.net",
        "https://www.bitstamp.net/api/v2/ticker/{from}{to}/",
        lambda data, replacements: data["last"],
        ["czk"],
    ),
    "coinbase": Provider(
        "Coinbase",
        "coinbase.com",
        "https://api.coinbase.com/v2/exchange-rates?currency={FROM}",
        lambda data, replacements: data["data"]["rates"][replacements["TO"]],
    ),
    "coinmate": Provider(
        "CoinMate",
        "coinmate.io",
        "https://coinmate.io/api/ticker?currencyPair={FROM}_{TO}",
        lambda data, replacements: data["data"]["last"],
    ),
    "kraken": Provider(
        "Kraken",
        "kraken.com",
        "https://api.kraken.com/0/public/Ticker?pair=XBT{TO}",
        lambda data, replacements: data["result"]["XXBTZ" + replacements["TO"]]["c"][0],
        ["czk"],
    ),
    "bitpay": Provider(
        "BitPay",
        "bitpay.com",
        "https://bitpay.com/rates",
        lambda data, replacements: next(
            i["rate"] for i in data["data"] if i["code"] == replacements["TO"]
        ),
    ),
    "yadio": Provider(
        "yadio",
        "yadio.io",
        "https://api.yadio.io/exrates/{FROM}",
        lambda data, replacements: data[replacements["FROM"]][replacements["TO"]],
    ),
}


async def btc_price(currency: str) -> float:
    replacements = {
        "FROM": "BTC",
        "from": "btc",
        "TO": currency.upper(),
        "to": currency.lower(),
    }

    async def fetch_price(provider: Provider):
        if currency.lower() in provider.exclude_to:
            raise Exception(f"Provider {provider.name} does not support {currency}.")

        url = provider.api_url.format(**replacements)
        try:
            headers = {"User-Agent": settings.user_agent}
            async with httpx.AsyncClient(headers=headers) as client:
                r = await client.get(url, timeout=0.5)
                r.raise_for_status()
                data = r.json()
                return float(provider.getter(data, replacements))
        except Exception as e:
            logger.warning(
                f"Failed to fetch Bitcoin price "
                f"for {currency} from {provider.name}: {e}"
            )
            raise

    results = await asyncio.gather(
        *[fetch_price(provider) for provider in exchange_rate_providers.values()],
        return_exceptions=True,
    )
    rates = [r for r in results if not isinstance(r, BaseException)]

    if not rates:
        return 9999999999
    elif len(rates) == 1:
        logger.warning("Could only fetch one Bitcoin price.")

    return sum(rates) / len(rates)


async def get_fiat_rate_satoshis(currency: str) -> float:
    price = await cache.save_result(
        lambda: btc_price(currency), f"btc-price-{currency}"
    )
    return float(100_000_000 / price)


async def fiat_amount_as_satoshis(amount: float, currency: str) -> int:
    return int(amount * (await get_fiat_rate_satoshis(currency)))


async def satoshis_amount_as_fiat(amount: float, currency: str) -> float:
    return float(amount / (await get_fiat_rate_satoshis(currency)))
