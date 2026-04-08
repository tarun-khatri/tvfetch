"""
Tests for scripts/lib/formatter.py — tagged output formatting.

15+ tests capturing stdout and verifying tags, structure, edge cases.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pandas as pd
import pytest

from scripts.lib.formatter import (
    print_fetch_result,
    print_analysis_result,
    print_compare_result,
    print_search_results,
    print_indicator_result,
    print_stream_summary,
    print_json_output,
    print_warning,
    print_progress,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_ohlcv_df(n: int = 5) -> pd.DataFrame:
    """Build a simple OHLCV DataFrame for formatter tests."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({
        "open": [100.0 + i for i in range(n)],
        "high": [105.0 + i for i in range(n)],
        "low": [95.0 + i for i in range(n)],
        "close": [102.0 + i for i in range(n)],
        "volume": [10000.0 + i * 100 for i in range(n)],
    }, index=dates)


# ── Fetch result tests ───────────────────────────────────────────────────────

class TestFetchResult:
    def test_fetch_result_has_tags(self, capsys):
        df = _make_ohlcv_df(5)
        print_fetch_result("BINANCE:BTCUSDT", "1D", df, "tradingview", "anonymous")
        out = capsys.readouterr().out
        assert out.startswith("=== FETCH RESULT ===")

    def test_fetch_result_symbol(self, capsys):
        df = _make_ohlcv_df(5)
        print_fetch_result("BINANCE:BTCUSDT", "1D", df, "tradingview", "anonymous")
        out = capsys.readouterr().out
        assert "SYMBOL: BINANCE:BTCUSDT" in out

    def test_fetch_result_bars_count(self, capsys):
        df = _make_ohlcv_df(10)
        print_fetch_result("SYM", "1D", df, "tv", "anon")
        out = capsys.readouterr().out
        assert "BARS: 10" in out

    def test_fetch_result_table_tag(self, capsys):
        df = _make_ohlcv_df(5)
        print_fetch_result("SYM", "1D", df, "tv", "anon")
        out = capsys.readouterr().out
        assert "=== DATA TABLE ===" in out

    def test_fetch_result_end_tag(self, capsys):
        df = _make_ohlcv_df(5)
        print_fetch_result("SYM", "1D", df, "tv", "anon")
        out = capsys.readouterr().out
        assert "=== END ===" in out

    def test_fetch_result_date_range(self, capsys):
        df = _make_ohlcv_df(5)
        print_fetch_result("SYM", "1D", df, "tv", "anon")
        out = capsys.readouterr().out
        assert "DATE_FROM:" in out
        assert "DATE_TO:" in out

    def test_fetch_result_latest_prices(self, capsys):
        df = _make_ohlcv_df(5)
        print_fetch_result("SYM", "1D", df, "tv", "anon")
        out = capsys.readouterr().out
        assert "LATEST_CLOSE:" in out
        assert "LATEST_OPEN:" in out

    def test_fetch_result_change_pct(self, capsys):
        df = _make_ohlcv_df(5)
        print_fetch_result("SYM", "1D", df, "tv", "anon")
        out = capsys.readouterr().out
        assert "CHANGE_PCT:" in out

    def test_empty_df_handled(self, capsys):
        """No crash on empty DataFrame."""
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df.index.name = "datetime"
        print_fetch_result("SYM", "1D", df, "tv", "anon")
        out = capsys.readouterr().out
        assert "=== FETCH RESULT ===" in out
        assert "BARS: 0" in out
        assert "=== END ===" in out

    def test_max_rows_respected(self, capsys):
        """Only max_rows rows should be printed in the table."""
        df = _make_ohlcv_df(50)
        print_fetch_result("SYM", "1D", df, "tv", "anon", max_rows=5)
        out = capsys.readouterr().out
        assert "45 earlier bars not shown" in out

    def test_fetch_result_warnings(self, capsys):
        df = _make_ohlcv_df(5)
        print_fetch_result("SYM", "1D", df, "tv", "anon",
                           warnings=["This is a test warning"])
        out = capsys.readouterr().out
        assert "WARNING: This is a test warning" in out


# ── Analysis result tests ────────────────────────────────────────────────────

class TestAnalysisResult:
    def test_analysis_result_tags(self, capsys):
        stats = {"MEAN": 100.5, "STD": 2.3, "IS_TRENDING": True}
        print_analysis_result(stats)
        out = capsys.readouterr().out
        assert "=== ANALYSIS RESULT ===" in out
        assert "=== END ===" in out

    def test_analysis_result_float_format(self, capsys):
        stats = {"PRICE": 123.456789}
        print_analysis_result(stats)
        out = capsys.readouterr().out
        assert "PRICE: 123.4568" in out

    def test_analysis_result_bool_format(self, capsys):
        stats = {"IS_BULL": True, "IS_BEAR": False}
        print_analysis_result(stats)
        out = capsys.readouterr().out
        assert "IS_BULL: true" in out
        assert "IS_BEAR: false" in out


# ── Compare result tests ─────────────────────────────────────────────────────

class TestCompareResult:
    def test_compare_result_tags(self, capsys):
        print_compare_result("table data here", {"CORR": 0.95})
        out = capsys.readouterr().out
        assert "=== COMPARISON ===" in out
        assert "=== TABLE ===" in out
        assert "=== END ===" in out


# ── Search results tests ─────────────────────────────────────────────────────

class TestSearchResults:
    def test_search_results_tags(self, capsys):
        results = [
            {"symbol": "BINANCE:BTCUSDT", "description": "Bitcoin",
             "exchange": "BINANCE", "type": "crypto", "currency": "USDT"},
        ]
        print_search_results(results)
        out = capsys.readouterr().out
        assert "=== SEARCH RESULTS ===" in out
        assert "COUNT: 1" in out
        assert "=== END ===" in out

    def test_search_results_empty(self, capsys):
        print_search_results([])
        out = capsys.readouterr().out
        assert "COUNT: 0" in out


# ── Indicator result tests ───────────────────────────────────────────────────

class TestIndicatorResult:
    def test_indicator_result_tags(self, capsys):
        print_indicator_result(
            symbol="BINANCE:BTCUSDT",
            timeframe="1D",
            latest_close=42000.0,
            indicators={"SMA_20": 41000.0, "RSI_14": 55.5},
            signals=["BULLISH: Price above SMA_20"],
        )
        out = capsys.readouterr().out
        assert "=== INDICATORS ===" in out
        assert "SYMBOL: BINANCE:BTCUSDT" in out
        assert "LATEST_CLOSE:" in out
        assert "=== SIGNALS ===" in out
        assert "=== END ===" in out

    def test_indicator_result_no_signals(self, capsys):
        print_indicator_result("SYM", "1D", 100.0, {"SMA_20": 99.0}, [])
        out = capsys.readouterr().out
        assert "=== INDICATORS ===" in out
        # No SIGNALS section if no signals
        assert "=== SIGNALS ===" not in out
        assert "=== END ===" in out


# ── Stream summary tests ─────────────────────────────────────────────────────

class TestStreamSummary:
    def test_stream_summary_tags(self, capsys):
        print_stream_summary(
            symbols=["BINANCE:BTCUSDT", "BINANCE:ETHUSDT"],
            duration=120.5,
            update_count=42,
            session_stats={"BINANCE:BTCUSDT": {"LAST_PRICE": 42000.0}},
        )
        out = capsys.readouterr().out
        assert "=== STREAM SUMMARY ===" in out
        assert "DURATION: 120.5s" in out
        assert "UPDATES: 42" in out
        assert "=== END ===" in out


# ── Utility output tests ────────────────────────────────────────────────────

class TestUtilityOutputs:
    def test_warning_format(self, capsys):
        print_warning("test message")
        out = capsys.readouterr().out
        assert out.strip() == "WARNING: test message"

    def test_progress_format(self, capsys):
        print_progress(100, 500)
        out = capsys.readouterr().out
        assert out.strip() == "PROGRESS: 100/500 bars"

    def test_json_output_valid(self, capsys):
        data = {"symbol": "BTCUSDT", "price": 42000.0, "bars": [1, 2, 3]}
        print_json_output(data)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["symbol"] == "BTCUSDT"
        assert parsed["price"] == 42000.0

    def test_json_output_handles_datetime(self, capsys):
        """json.dumps with default=str should handle datetimes."""
        data = {"timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc)}
        print_json_output(data)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "2024" in parsed["timestamp"]
