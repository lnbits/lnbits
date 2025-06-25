from lnbits.utils.exchange_rates import (
    apply_trimmed_mean_filter,
)


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
