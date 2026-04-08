"""
Tests for scripts/lib/validators.py — symbol resolution, timeframe validation, bar parsing.

25+ tests covering all symbol aliases, timeframe alternatives, bar limit warnings.
"""

from __future__ import annotations

import pytest

from scripts.lib.validators import (
    SYMBOL_ALIASES,
    VALID_TIMEFRAMES,
    ANON_BAR_LIMITS,
    resolve_symbol,
    validate_timeframe,
    parse_bars,
    check_bar_limit_warning,
    is_intraday,
)


# ── Symbol resolution ────────────────────────────────────────────────────────

class TestResolveSymbolAliases:
    """Test that common aliases resolve to correct EXCHANGE:TICKER."""

    def test_btc_alias(self):
        assert resolve_symbol("BTC") == "BINANCE:BTCUSDT"

    def test_bitcoin_alias(self):
        assert resolve_symbol("BITCOIN") == "BINANCE:BTCUSDT"

    def test_eth_alias(self):
        assert resolve_symbol("ETH") == "BINANCE:ETHUSDT"

    def test_sol_alias(self):
        assert resolve_symbol("SOL") == "BINANCE:SOLUSDT"

    def test_aapl_alias(self):
        assert resolve_symbol("AAPL") == "NASDAQ:AAPL"

    def test_apple_alias(self):
        assert resolve_symbol("APPLE") == "NASDAQ:AAPL"

    def test_spx_alias(self):
        assert resolve_symbol("SPX") == "SP:SPX"

    def test_eurusd_alias(self):
        assert resolve_symbol("EURUSD") == "FX:EURUSD"

    def test_gold_alias(self):
        assert resolve_symbol("GOLD") == "TVC:GOLD"

    def test_xau_alias(self):
        assert resolve_symbol("XAU") == "TVC:GOLD"

    def test_doge_alias(self):
        assert resolve_symbol("DOGE") == "BINANCE:DOGEUSDT"

    def test_tsla_alias(self):
        assert resolve_symbol("TSLA") == "NASDAQ:TSLA"

    def test_vix_alias(self):
        assert resolve_symbol("VIX") == "CBOE:VIX"

    def test_dxy_alias(self):
        assert resolve_symbol("DXY") == "TVC:DXY"

    def test_oil_alias(self):
        assert resolve_symbol("OIL") == "TVC:USOIL"

    def test_spy_alias(self):
        assert resolve_symbol("SPY") == "AMEX:SPY"


class TestResolveSymbolFormats:
    def test_resolve_symbol_with_colon(self):
        """Already qualified -> returned as-is (uppercased)."""
        assert resolve_symbol("BINANCE:BTCUSDT") == "BINANCE:BTCUSDT"

    def test_resolve_symbol_with_colon_lowercase(self):
        assert resolve_symbol("binance:btcusdt") == "BINANCE:BTCUSDT"

    def test_resolve_symbol_case_insensitive(self):
        """Lowercase alias -> resolved."""
        assert resolve_symbol("btc") == "BINANCE:BTCUSDT"

    def test_resolve_symbol_mixed_case(self):
        assert resolve_symbol("Btc") == "BINANCE:BTCUSDT"

    def test_resolve_symbol_unknown(self):
        """Unknown symbol without colon -> returned as uppercase."""
        assert resolve_symbol("FOOBAR") == "FOOBAR"

    def test_resolve_symbol_unknown_lowercase(self):
        assert resolve_symbol("foobar") == "FOOBAR"

    def test_resolve_symbol_whitespace_stripped(self):
        assert resolve_symbol("  BTC  ") == "BINANCE:BTCUSDT"


# ── Timeframe validation ────────────────────────────────────────────────────

class TestValidateTimeframe:
    @pytest.mark.parametrize("tf", sorted(VALID_TIMEFRAMES, key=lambda x: (x[-1].isalpha(), x)))
    def test_validate_timeframe_valid(self, tf):
        """All 14 valid timeframes should pass through."""
        result = validate_timeframe(tf)
        assert result in VALID_TIMEFRAMES

    def test_validate_timeframe_1h(self):
        assert validate_timeframe("1H") == "60"

    def test_validate_timeframe_4h(self):
        assert validate_timeframe("4H") == "240"

    def test_validate_timeframe_2h(self):
        assert validate_timeframe("2H") == "120"

    def test_validate_timeframe_3h(self):
        assert validate_timeframe("3H") == "180"

    def test_validate_timeframe_d(self):
        assert validate_timeframe("D") == "1D"

    def test_validate_timeframe_w(self):
        assert validate_timeframe("W") == "1W"

    def test_validate_timeframe_5m(self):
        assert validate_timeframe("5M") == "5"

    def test_validate_timeframe_15m(self):
        assert validate_timeframe("15M") == "15"

    def test_validate_timeframe_30m(self):
        assert validate_timeframe("30M") == "30"

    def test_validate_timeframe_invalid(self):
        with pytest.raises(ValueError, match="Invalid timeframe"):
            validate_timeframe("7M")

    def test_validate_timeframe_garbage(self):
        with pytest.raises(ValueError, match="Invalid timeframe"):
            validate_timeframe("XYZABC")

    def test_validate_timeframe_empty_string(self):
        with pytest.raises(ValueError):
            validate_timeframe("")


# ── Bar parsing ──────────────────────────────────────────────────────────────

class TestParseBars:
    def test_parse_bars_int(self):
        assert parse_bars("500") == 500

    def test_parse_bars_k_notation_lower(self):
        assert parse_bars("1k") == 1000

    def test_parse_bars_k_notation_upper(self):
        assert parse_bars("5K") == 5000

    def test_parse_bars_fractional_k(self):
        assert parse_bars("1.5k") == 1500

    def test_parse_bars_10k(self):
        assert parse_bars("10k") == 10000

    def test_parse_bars_whitespace(self):
        assert parse_bars("  500  ") == 500

    def test_parse_bars_invalid(self):
        with pytest.raises(ValueError):
            parse_bars("abc")

    def test_parse_bars_empty(self):
        with pytest.raises(ValueError):
            parse_bars("")


# ── Bar limit warnings ──────────────────────────────────────────────────────

class TestBarLimitWarning:
    def test_bar_limit_warning_anonymous_intraday(self):
        """1 min, 10000 bars (anonymous) -> warning since limit is 6500."""
        warning = check_bar_limit_warning("1", 10000, is_anonymous=True)
        assert warning is not None
        assert "WARNING" in warning
        assert "6,500" in warning

    def test_bar_limit_no_warning_daily(self):
        """1D, 99999 bars -> None (daily is unlimited for anon)."""
        warning = check_bar_limit_warning("1D", 99999, is_anonymous=True)
        assert warning is None

    def test_bar_limit_no_warning_weekly(self):
        warning = check_bar_limit_warning("1W", 99999, is_anonymous=True)
        assert warning is None

    def test_bar_limit_no_warning_monthly(self):
        warning = check_bar_limit_warning("1M", 99999, is_anonymous=True)
        assert warning is None

    def test_bar_limit_no_warning_authenticated(self):
        """Authenticated user -> no limit warning."""
        warning = check_bar_limit_warning("1", 10000, is_anonymous=False)
        assert warning is None

    def test_bar_limit_no_warning_within_limit(self):
        """Within anonymous limit -> None."""
        warning = check_bar_limit_warning("1", 100, is_anonymous=True)
        assert warning is None

    def test_bar_limit_warning_60min(self):
        """60 min at 20000 bars (limit ~10800) -> warning."""
        warning = check_bar_limit_warning("60", 20000, is_anonymous=True)
        assert warning is not None
        assert "10,800" in warning


# ── is_intraday ──────────────────────────────────────────────────────────────

class TestIsIntraday:
    def test_60_is_intraday(self):
        assert is_intraday("60") is True

    def test_1_is_intraday(self):
        assert is_intraday("1") is True

    def test_240_is_intraday(self):
        assert is_intraday("240") is True

    def test_1d_not_intraday(self):
        assert is_intraday("1D") is False

    def test_1w_not_intraday(self):
        assert is_intraday("1W") is False

    def test_1m_not_intraday(self):
        assert is_intraday("1M") is False
