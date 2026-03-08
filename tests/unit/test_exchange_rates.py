from unittest.mock import AsyncMock

import httpx
import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.settings import ExchangeRateProvider, Settings
from lnbits.utils.exchange_rates import (
    allowed_currencies,
    apply_trimmed_mean_filter,
    btc_price,
    btc_rates,
    fiat_amount_as_satoshis,
    get_fiat_rate_and_price_satoshis,
    get_fiat_rate_satoshis,
    satoshis_amount_as_fiat,
)


class MockResponse:
    def __init__(self, *, text: str = "", json_data=None, error: Exception | None = None):
        self.text = text
        self._json_data = json_data or {}
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._json_data


class MockAsyncClient:
    def __init__(self, response: MockResponse):
        self.response = response
        self.calls: list[tuple[str, int]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, timeout: int = 3):
        self.calls.append((url, timeout))
        return self.response


class TestApplyTrimmedMeanFilter:
    """Test the trimmed mean filtering function"""

    def test_trimmed_mean_filter_with_outliers(self):
        """Test filtering removes outliers that deviate more than threshold"""
        # Mock rates with one outlier (20% deviation)
        rates = [
            ("Binance", 50000.0),
            ("Coinbase", 51000.0),
            ("Kraken", 52000.0),
            ("Outlier", 60000.0),  # 20% higher than others
        ]

        result = apply_trimmed_mean_filter(rates, threshold_percentage=0.01)

        # Should remove the outliers (binance and outlier)
        assert len(result) == 2
        assert ("Outlier", 60000.0) not in result
        assert ("Binance", 50000.0) not in result
        assert ("Coinbase", 51000.0) in result
        assert ("Kraken", 52000.0) in result

    def test_trimmed_mean_filter_no_outliers(self):
        """Test filtering keeps all rates when none are outliers"""
        rates = [
            ("Binance", 50000.0),
            ("Coinbase", 50100.0),
            ("Kraken", 50200.0),
        ]

        result = apply_trimmed_mean_filter(rates, threshold_percentage=0.01)

        # Should keep all rates
        assert len(result) == 3
        assert result == rates

    def test_trimmed_mean_filter_insufficient_data(self):
        """Test filtering returns original data when less than 3 rates"""
        rates = [
            ("Binance", 50000.0),
            ("Coinbase", 51000.0),
        ]

        result = apply_trimmed_mean_filter(rates, threshold_percentage=0.01)

        # Should return original rates unchanged
        assert result == rates

    def test_trimmed_mean_filter_single_rate(self):
        """Test filtering with single rate"""
        rates = [("Binance", 50000.0)]

        result = apply_trimmed_mean_filter(rates, threshold_percentage=0.01)

        # Should return original rate unchanged
        assert result == rates

    def test_trimmed_mean_filter_empty_list(self):
        """Test filtering with empty list"""
        rates = []

        result = apply_trimmed_mean_filter(rates, threshold_percentage=0.01)

        # Should return empty list
        assert result == []

    def test_trimmed_mean_filter_too_many_outliers(self):
        """Test fallback to median when filtering removes too many values"""
        rates = [
            ("Provider1", 50000.0),
            ("Provider2", 60000.0),  # 20% higher
            ("Provider3", 40000.0),  # 20% lower
        ]

        result = apply_trimmed_mean_filter(rates, threshold_percentage=0.01)

        # Should fall back to rate closest to median (Provider1)
        assert len(result) == 1
        assert result[0] == ("Provider1", 50000.0)

    def test_trimmed_mean_filter_different_thresholds(self):
        """Test filtering with different threshold percentages"""
        rates = [
            ("Binance", 50000.0),
            ("Coinbase", 51000.0),
            ("Kraken", 53000.0),
            ("Outlier", 55000.0),
        ]

        # For the values, the average is 52250
        #  1% either side of the average is 51727.50 and 52772.50
        # This would result in three rates being removed (Binance, Kraken and Outlier)
        result_1pct = apply_trimmed_mean_filter(rates, threshold_percentage=0.01)

        assert len(result_1pct) == 1
        assert ("Binance", 50000.0) not in result_1pct
        assert ("Coinbase", 51000.0) in result_1pct
        assert ("Kraken", 53000.0) not in result_1pct
        assert ("Outlier", 55000.0) not in result_1pct

        # With 5% threshold, should keep just three
        result_5pct = apply_trimmed_mean_filter(rates, threshold_percentage=0.05)
        assert len(result_5pct) == 3
        assert ("Binance", 50000.0) in result_5pct
        assert ("Coinbase", 51000.0) in result_5pct
        assert ("Kraken", 53000.0) in result_5pct
        assert ("Outlier", 55000.0) not in result_5pct

    def test_trimmed_mean_filter_edge_case_exact_threshold(self):
        """Test filtering with rates exactly at the threshold"""
        rates = [
            ("Binance", 50000.0),
            ("Coinbase", 50500.0),  # Exactly 1% higher
        ]

        result = apply_trimmed_mean_filter(rates, threshold_percentage=0.01)

        # Should keep the rate at exactly 1% deviation
        assert len(result) == 2
        assert result == rates


def test_allowed_currencies_returns_full_list_by_default(settings: Settings):
    original_allowed_currencies = settings.lnbits_allowed_currencies
    try:
        settings.lnbits_allowed_currencies = []

        currencies = allowed_currencies()

        assert "USD" in currencies
        assert "EUR" in currencies
    finally:
        settings.lnbits_allowed_currencies = original_allowed_currencies


def test_allowed_currencies_respects_allow_list(settings: Settings):
    original_allowed_currencies = settings.lnbits_allowed_currencies
    try:
        settings.lnbits_allowed_currencies = ["USD", "EUR"]

        assert allowed_currencies() == ["EUR", "USD"]
    finally:
        settings.lnbits_allowed_currencies = original_allowed_currencies


@pytest.mark.anyio
async def test_btc_rates_rejects_disallowed_currency(settings: Settings):
    original_allowed_currencies = settings.lnbits_allowed_currencies
    try:
        settings.lnbits_allowed_currencies = ["EUR"]

        with pytest.raises(ValueError, match="Currency 'usd' not allowed."):
            await btc_rates("usd")
    finally:
        settings.lnbits_allowed_currencies = original_allowed_currencies


@pytest.mark.anyio
async def test_btc_rates_parses_plain_text_response(
    settings: Settings, mocker: MockerFixture
):
    provider = ExchangeRateProvider(
        name="PlainText",
        api_url="https://plain.test/{TO}",
        path="",
    )
    client = MockAsyncClient(MockResponse(text="12,345.67"))
    mocker.patch.object(settings, "lnbits_allowed_currencies", [])
    mocker.patch.object(settings, "lnbits_exchange_rate_providers", [provider])
    mocker.patch("lnbits.utils.exchange_rates.httpx.AsyncClient", return_value=client)

    rates = await btc_rates("usd")

    assert rates == [("PlainText", 12345.67)]
    assert client.calls == [("https://plain.test/USD", 3)]


@pytest.mark.anyio
async def test_btc_rates_parses_json_path_response(
    settings: Settings, mocker: MockerFixture
):
    provider = ExchangeRateProvider(
        name="JsonProvider",
        api_url="https://json.test/{TO}",
        path="$.data.rates.{TO}",
    )
    client = MockAsyncClient(
        MockResponse(json_data={"data": {"rates": {"USD": "54321.0"}}})
    )
    mocker.patch.object(settings, "lnbits_allowed_currencies", [])
    mocker.patch.object(settings, "lnbits_exchange_rate_providers", [provider])
    mocker.patch("lnbits.utils.exchange_rates.httpx.AsyncClient", return_value=client)

    rates = await btc_rates("usd")

    assert rates == [("JsonProvider", 54321.0)]
    assert client.calls == [("https://json.test/USD", 3)]


@pytest.mark.anyio
async def test_btc_rates_skips_unsupported_and_failing_providers(
    settings: Settings, mocker: MockerFixture
):
    unsupported = ExchangeRateProvider(
        name="Unsupported",
        api_url="https://unsupported.test/{TO}",
        path="$.price",
        exclude_to=["usd"],
    )
    failing = ExchangeRateProvider(
        name="Failing",
        api_url="https://failing.test/{TO}",
        path="$.price",
    )
    client = MockAsyncClient(MockResponse(error=httpx.HTTPError("boom")))
    mocker.patch.object(settings, "lnbits_allowed_currencies", [])
    mocker.patch.object(settings, "lnbits_exchange_rate_providers", [unsupported, failing])
    mocker.patch("lnbits.utils.exchange_rates.httpx.AsyncClient", return_value=client)

    assert await btc_rates("usd") == []


@pytest.mark.anyio
async def test_btc_price_handles_empty_single_and_multiple_rates(mocker: MockerFixture):
    mocker.patch("lnbits.utils.exchange_rates.btc_rates", AsyncMock(return_value=[]))
    assert await btc_price("usd") == 0.0

    mocker.patch(
        "lnbits.utils.exchange_rates.btc_rates",
        AsyncMock(return_value=[("Only", 50000.0)]),
    )
    assert await btc_price("usd") == 50000.0

    mocker.patch(
        "lnbits.utils.exchange_rates.btc_rates",
        AsyncMock(return_value=[("A", 40000.0), ("B", 50000.0)]),
    )
    assert await btc_price("usd") == 45000.0


@pytest.mark.anyio
async def test_rate_and_amount_conversion_helpers(mocker: MockerFixture):
    cache_result = AsyncMock(return_value=50000.0)
    mocker.patch("lnbits.utils.exchange_rates.cache.save_result", cache_result)

    rate, price = await get_fiat_rate_and_price_satoshis("usd")

    assert price == 50000.0
    assert rate == 2000.0
    cache_result.assert_awaited_once()

    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_and_price_satoshis",
        AsyncMock(return_value=(1250.0, 80000.0)),
    )
    assert await get_fiat_rate_satoshis("usd") == 1250.0

    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=100.0),
    )
    assert await fiat_amount_as_satoshis(2.5, "usd") == 250
    assert await satoshis_amount_as_fiat(500, "usd") == 5.0


@pytest.mark.anyio
async def test_amount_conversion_helpers_raise_when_rate_missing(
    mocker: MockerFixture,
):
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=0.0),
    )

    with pytest.raises(ValueError, match="Could not get exchange rate for usd."):
        await fiat_amount_as_satoshis(1, "usd")

    with pytest.raises(ValueError, match="Could not get exchange rate for usd."):
        await satoshis_amount_as_fiat(100, "usd")
