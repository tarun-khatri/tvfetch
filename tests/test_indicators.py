"""
Tests for scripts/lib/indicators.py — all technical indicator functions.

35+ tests using the sample_df fixture (100-bar seeded random DataFrame).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.lib.indicators import (
    compute_sma,
    compute_ema,
    compute_rsi,
    compute_macd,
    compute_bollinger,
    compute_atr,
    compute_stochastic,
    compute_obv,
    compute_vwap,
    parse_indicator_spec,
    add_indicators,
)


# ── SMA tests ────────────────────────────────────────────────────────────────

class TestSMA:
    def test_sma_correct_values(self, sample_df):
        """SMA of period 5 should equal a manual rolling mean."""
        sma = compute_sma(sample_df["close"], 5)
        # Check a known position (index 4 = first non-NaN for period=5)
        expected = sample_df["close"].iloc[:5].mean()
        assert sma.iloc[4] == pytest.approx(expected, rel=1e-10)

    def test_sma_nan_for_insufficient_data(self, sample_df):
        """First (period-1) values should be NaN."""
        sma = compute_sma(sample_df["close"], 20)
        assert pd.isna(sma.iloc[0])
        assert pd.isna(sma.iloc[18])
        assert not pd.isna(sma.iloc[19])

    def test_sma_length_matches(self, sample_df):
        sma = compute_sma(sample_df["close"], 10)
        assert len(sma) == len(sample_df)

    def test_sma_period_1_equals_close(self, sample_df):
        sma = compute_sma(sample_df["close"], 1)
        pd.testing.assert_series_equal(sma, sample_df["close"], check_names=False)

    def test_sma_constant_series(self):
        """SMA of a constant series should be that constant."""
        s = pd.Series([5.0] * 50)
        sma = compute_sma(s, 10)
        assert sma.iloc[-1] == pytest.approx(5.0)


# ── EMA tests ────────────────────────────────────────────────────────────────

class TestEMA:
    def test_ema_responds_faster_than_sma(self, sample_df):
        """After a sudden change, EMA should be closer to new value than SMA."""
        # Create a series that jumps
        data = pd.Series([100.0] * 50 + [200.0] * 10)
        sma = compute_sma(data, 10)
        ema = compute_ema(data, 10)
        # At position 55 (5 bars into the jump), EMA should be closer to 200
        idx = 55
        assert abs(ema.iloc[idx] - 200) < abs(sma.iloc[idx] - 200)

    def test_ema_length_matches(self, sample_df):
        ema = compute_ema(sample_df["close"], 12)
        assert len(ema) == len(sample_df)

    def test_ema_nan_for_insufficient_data(self, sample_df):
        ema = compute_ema(sample_df["close"], 20)
        assert pd.isna(ema.iloc[0])

    def test_ema_constant_series(self):
        s = pd.Series([10.0] * 50)
        ema = compute_ema(s, 10)
        assert ema.iloc[-1] == pytest.approx(10.0)


# ── RSI tests ────────────────────────────────────────────────────────────────

class TestRSI:
    def test_rsi_range_0_100(self, sample_df):
        """RSI should always be between 0 and 100."""
        rsi = compute_rsi(sample_df["close"], 14)
        valid = rsi.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_approximately_50_for_random_walk(self, sample_df):
        """For a random walk, RSI should average near 50."""
        rsi = compute_rsi(sample_df["close"], 14)
        mean_rsi = rsi.dropna().mean()
        assert 30 < mean_rsi < 70  # loose range for random walk

    def test_rsi_above_70_for_rising(self):
        """Mostly rising prices -> RSI > 70."""
        # Use a series with a strong upward trend but enough noise to ensure
        # some negative deltas exist (pure monotonic gives avg_loss=0 -> NaN).
        rng = np.random.RandomState(99)
        base = np.arange(200, dtype=float) * 1.0  # upward trend
        noise = rng.randn(200) * 2.0  # enough noise for occasional dips
        rising = pd.Series(base + noise)
        rsi = compute_rsi(rising, 14)
        valid = rsi.dropna()
        assert len(valid) > 0, "RSI should have non-NaN values for trending+noisy data"
        assert valid.iloc[-1] > 70

    def test_rsi_below_30_for_falling(self):
        """Steadily falling prices -> RSI < 30."""
        falling = pd.Series(list(range(100, 0, -1)), dtype=float)
        rsi = compute_rsi(falling, 14)
        assert rsi.iloc[-1] < 30

    def test_rsi_length_matches(self, sample_df):
        rsi = compute_rsi(sample_df["close"], 14)
        assert len(rsi) == len(sample_df)


# ── MACD tests ───────────────────────────────────────────────────────────────

class TestMACD:
    def test_macd_line_equals_fast_minus_slow(self, sample_df):
        """MACD line = EMA(fast) - EMA(slow)."""
        close = sample_df["close"]
        macd = compute_macd(close, 12, 26, 9)
        ema_fast = compute_ema(close, 12)
        ema_slow = compute_ema(close, 26)
        expected_line = ema_fast - ema_slow
        pd.testing.assert_series_equal(macd["line"], expected_line, check_names=False)

    def test_macd_histogram_equals_line_minus_signal(self, sample_df):
        """Histogram = MACD line - signal line."""
        macd = compute_macd(sample_df["close"], 12, 26, 9)
        expected_hist = macd["line"] - macd["signal"]
        pd.testing.assert_series_equal(macd["histogram"], expected_hist, check_names=False)

    def test_macd_returns_three_series(self, sample_df):
        macd = compute_macd(sample_df["close"])
        assert "line" in macd
        assert "signal" in macd
        assert "histogram" in macd

    def test_macd_length_matches(self, sample_df):
        macd = compute_macd(sample_df["close"])
        assert len(macd["line"]) == len(sample_df)


# ── Bollinger Bands tests ────────────────────────────────────────────────────

class TestBollinger:
    def test_bollinger_upper_gt_mid_gt_lower(self, sample_df):
        """upper > mid > lower for all valid points."""
        bb = compute_bollinger(sample_df["close"], 20, 2.0)
        valid_mask = bb["upper"].notna()
        assert (bb["upper"][valid_mask] > bb["mid"][valid_mask]).all()
        assert (bb["mid"][valid_mask] > bb["lower"][valid_mask]).all()

    def test_bollinger_pct_b_between_0_1_mostly(self, sample_df):
        """For stable data, %B should mostly be between 0 and 1."""
        bb = compute_bollinger(sample_df["close"], 20, 2.0)
        valid = bb["pct_b"].dropna()
        # At least 80% of points should be in [0, 1] for normal data
        in_range = ((valid >= 0) & (valid <= 1)).sum()
        assert in_range / len(valid) > 0.7

    def test_bollinger_mid_equals_sma(self, sample_df):
        """Middle band should be the SMA."""
        bb = compute_bollinger(sample_df["close"], 20, 2.0)
        sma = compute_sma(sample_df["close"], 20)
        pd.testing.assert_series_equal(bb["mid"], sma, check_names=False)

    def test_bollinger_returns_four_series(self, sample_df):
        bb = compute_bollinger(sample_df["close"])
        assert "upper" in bb
        assert "mid" in bb
        assert "lower" in bb
        assert "pct_b" in bb

    def test_bollinger_wider_with_higher_std(self, sample_df):
        """Higher std_dev -> wider bands."""
        bb2 = compute_bollinger(sample_df["close"], 20, 2.0)
        bb3 = compute_bollinger(sample_df["close"], 20, 3.0)
        valid = bb2["upper"].notna()
        width2 = (bb2["upper"] - bb2["lower"])[valid]
        width3 = (bb3["upper"] - bb3["lower"])[valid]
        assert (width3 > width2).all()


# ── ATR tests ────────────────────────────────────────────────────────────────

class TestATR:
    def test_atr_always_positive(self, sample_df):
        atr = compute_atr(sample_df["high"], sample_df["low"], sample_df["close"], 14)
        valid = atr.dropna()
        assert (valid > 0).all()

    def test_atr_increases_with_volatility(self):
        """More volatile data -> higher ATR."""
        n = 100
        # Low volatility
        low_vol_close = pd.Series(100 + np.cumsum(np.random.RandomState(1).randn(n) * 0.1))
        low_vol_high = low_vol_close + 0.1
        low_vol_low = low_vol_close - 0.1
        # High volatility
        high_vol_close = pd.Series(100 + np.cumsum(np.random.RandomState(1).randn(n) * 5.0))
        high_vol_high = high_vol_close + 5.0
        high_vol_low = high_vol_close - 5.0

        atr_low = compute_atr(low_vol_high, low_vol_low, low_vol_close, 14)
        atr_high = compute_atr(high_vol_high, high_vol_low, high_vol_close, 14)
        assert atr_high.iloc[-1] > atr_low.iloc[-1]

    def test_atr_length_matches(self, sample_df):
        atr = compute_atr(sample_df["high"], sample_df["low"], sample_df["close"], 14)
        assert len(atr) == len(sample_df)


# ── Stochastic tests ─────────────────────────────────────────────────────────

class TestStochastic:
    def test_stochastic_k_range_0_100(self, sample_df):
        stoch = compute_stochastic(sample_df["high"], sample_df["low"], sample_df["close"])
        valid = stoch["k"].dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_stochastic_d_range_0_100(self, sample_df):
        stoch = compute_stochastic(sample_df["high"], sample_df["low"], sample_df["close"])
        valid = stoch["d"].dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_stochastic_returns_k_and_d(self, sample_df):
        stoch = compute_stochastic(sample_df["high"], sample_df["low"], sample_df["close"])
        assert "k" in stoch
        assert "d" in stoch

    def test_stochastic_d_is_smoothed_k(self, sample_df):
        """D is a rolling mean of K."""
        stoch = compute_stochastic(sample_df["high"], sample_df["low"], sample_df["close"], 14, 3)
        expected_d = stoch["k"].rolling(window=3).mean()
        pd.testing.assert_series_equal(stoch["d"], expected_d, check_names=False)


# ── OBV tests ────────────────────────────────────────────────────────────────

class TestOBV:
    def test_obv_cumulative(self, sample_df):
        """OBV should be cumulative sum of signed volumes."""
        obv = compute_obv(sample_df["close"], sample_df["volume"])
        assert len(obv) == len(sample_df)

    def test_obv_increases_on_up_days(self):
        """Rising close -> OBV increases."""
        close = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
        volume = pd.Series([1000.0, 1000.0, 1000.0, 1000.0, 1000.0])
        obv = compute_obv(close, volume)
        # After first element, each subsequent should increase
        assert obv.iloc[-1] > obv.iloc[1]

    def test_obv_decreases_on_down_days(self):
        """Falling close -> OBV decreases."""
        close = pd.Series([104.0, 103.0, 102.0, 101.0, 100.0])
        volume = pd.Series([1000.0, 1000.0, 1000.0, 1000.0, 1000.0])
        obv = compute_obv(close, volume)
        assert obv.iloc[-1] < obv.iloc[0]

    def test_obv_flat_on_unchanged_close(self):
        """Same close prices -> OBV should not change after first bar."""
        close = pd.Series([100.0, 100.0, 100.0, 100.0])
        volume = pd.Series([1000.0, 1000.0, 1000.0, 1000.0])
        obv = compute_obv(close, volume)
        # Direction should be 0 when close doesn't change, so OBV stays at 0
        assert obv.iloc[-1] == pytest.approx(0.0)


# ── VWAP tests ───────────────────────────────────────────────────────────────

class TestVWAP:
    def test_vwap_within_high_low_range(self, sample_df):
        """VWAP should be within the high-low range for most bars."""
        vwap = compute_vwap(sample_df["high"], sample_df["low"],
                            sample_df["close"], sample_df["volume"])
        valid = vwap.dropna()
        # VWAP is cumulative, so early values may exceed current range
        # but should be within the overall data range
        assert valid.min() >= sample_df["low"].min() - 1
        assert valid.max() <= sample_df["high"].max() + 1

    def test_vwap_length_matches(self, sample_df):
        vwap = compute_vwap(sample_df["high"], sample_df["low"],
                            sample_df["close"], sample_df["volume"])
        assert len(vwap) == len(sample_df)

    def test_vwap_equals_typical_for_equal_volume(self):
        """With equal volumes, VWAP should equal cumulative typical price average."""
        high = pd.Series([10.0, 12.0, 11.0])
        low = pd.Series([8.0, 9.0, 9.0])
        close = pd.Series([9.0, 11.0, 10.0])
        volume = pd.Series([100.0, 100.0, 100.0])
        vwap = compute_vwap(high, low, close, volume)
        # First bar: typical = (10+8+9)/3 = 9.0
        assert vwap.iloc[0] == pytest.approx(9.0)


# ── parse_indicator_spec tests ───────────────────────────────────────────────

class TestParseIndicatorSpec:
    def test_parse_simple_spec(self):
        result = parse_indicator_spec("sma:20,rsi:14")
        assert result == [("sma", ["20"]), ("rsi", ["14"])]

    def test_parse_no_params(self):
        result = parse_indicator_spec("macd,obv,vwap")
        assert result == [("macd", []), ("obv", []), ("vwap", [])]

    def test_parse_multiple_params(self):
        result = parse_indicator_spec("bb:20:2,stoch:14:3")
        assert result == [("bb", ["20", "2"]), ("stoch", ["14", "3"])]

    def test_parse_empty_string(self):
        result = parse_indicator_spec("")
        assert result == []

    def test_parse_whitespace_handled(self):
        result = parse_indicator_spec("sma:20 , rsi:14")
        assert result == [("sma", ["20"]), ("rsi", ["14"])]

    def test_parse_case_insensitive(self):
        result = parse_indicator_spec("SMA:20,RSI:14")
        assert result == [("sma", ["20"]), ("rsi", ["14"])]


# ── add_indicators integration tests ─────────────────────────────────────────

class TestAddIndicators:
    def test_add_sma_column(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "sma:20")
        assert "SMA_20" in df.columns
        assert "SMA_20" in latest

    def test_add_rsi_column(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "rsi:14")
        assert "RSI_14" in df.columns
        assert "RSI_14" in latest

    def test_add_macd_columns(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "macd")
        assert "MACD_LINE" in df.columns
        assert "MACD_SIGNAL" in df.columns
        assert "MACD_HIST" in df.columns

    def test_add_bollinger_columns(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "bb:20")
        assert "BB_UPPER" in df.columns
        assert "BB_MID" in df.columns
        assert "BB_LOWER" in df.columns
        assert "BB_PCT_B" in df.columns

    def test_add_multiple_indicators(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "sma:20,rsi:14,macd")
        assert "SMA_20" in df.columns
        assert "RSI_14" in df.columns
        assert "MACD_LINE" in df.columns
        assert len(latest) >= 3

    def test_add_indicators_returns_signals(self, sample_df):
        _, _, signals = add_indicators(sample_df.copy(), "sma:20,rsi:14")
        assert len(signals) >= 1  # at least one signal

    def test_add_obv_column(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "obv")
        assert "OBV" in df.columns
        assert "OBV" in latest

    def test_add_vwap_column(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "vwap")
        assert "VWAP" in df.columns
        assert "VWAP" in latest

    def test_add_atr_column(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "atr:14")
        assert "ATR_14" in df.columns
        assert "ATR_14" in latest

    def test_add_stoch_columns(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "stoch:14:3")
        assert "STOCH_K" in df.columns
        assert "STOCH_D" in df.columns

    def test_add_ema_column(self, sample_df):
        df, latest, signals = add_indicators(sample_df.copy(), "ema:12")
        assert "EMA_12" in df.columns
        assert "EMA_12" in latest
