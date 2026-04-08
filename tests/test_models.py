"""Tests for tvfetch.models — Bar, FetchResult, SymbolInfo."""

import pytest
from datetime import datetime, timezone

from tvfetch.models import Bar, FetchResult, SymbolInfo
from tests.conftest import SAMPLE_BAR_RAW, SAMPLE_BAR, make_sample_bars, make_fetch_result


class TestBarFromTv:
    def test_parses_valid_raw(self):
        bar = Bar.from_tv(SAMPLE_BAR_RAW)
        assert bar.open == 42000.0
        assert bar.high == 43000.0
        assert bar.low == 41500.0
        assert bar.close == 42500.0
        assert bar.volume == 1234.56
        assert bar.timestamp.tzinfo == timezone.utc

    def test_timestamp_conversion(self):
        raw = [1700000000.0, 1.0, 2.0, 0.5, 1.5, 100.0]
        bar = Bar.from_tv(raw)
        expected = datetime.fromtimestamp(1700000000.0, tz=timezone.utc)
        assert bar.timestamp == expected

    def test_raises_on_short_list(self):
        with pytest.raises(ValueError, match="expected at least 6 fields"):
            Bar.from_tv([1.0, 2.0, 3.0])

    def test_raises_on_empty_list(self):
        with pytest.raises(ValueError):
            Bar.from_tv([])

    def test_accepts_extra_fields(self):
        # TV may add extra fields in the future — should not raise
        raw = SAMPLE_BAR_RAW + [999.0, 888.0]
        bar = Bar.from_tv(raw)
        assert bar.close == 42500.0


class TestFetchResult:
    def test_df_has_correct_columns(self):
        result = make_fetch_result(n=3)
        df = result.df
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_df_sorted_by_datetime(self):
        result = make_fetch_result(n=5)
        df = result.df
        assert df.index.is_monotonic_increasing

    def test_df_empty_result(self):
        result = FetchResult("SYM", "1D", [], "tradingview", "anonymous")
        df = result.df
        assert df.empty

    def test_len(self):
        result = make_fetch_result(n=7)
        assert len(result) == 7

    def test_repr_contains_symbol(self):
        result = make_fetch_result(symbol="TEST:SYM")
        assert "TEST:SYM" in repr(result)

    def test_repr_empty(self):
        result = FetchResult("X", "1D", [], "tradingview", "anonymous")
        assert "no data" in repr(result)

    def test_to_csv(self, tmp_path):
        result = make_fetch_result(n=3)
        path = str(tmp_path / "test.csv")
        result.to_csv(path)
        import pandas as pd
        df = pd.read_csv(path, index_col=0)
        assert len(df) == 3

    def test_to_json(self, tmp_path):
        result = make_fetch_result(n=3)
        path = str(tmp_path / "test.json")
        result.to_json(path)
        import json
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 3


class TestSymbolInfo:
    def test_ticker_strips_exchange(self):
        sym = SymbolInfo("BINANCE:BTCUSDT", "Bitcoin", "BINANCE", "crypto", "USDT")
        assert sym.ticker == "BTCUSDT"

    def test_ticker_no_colon(self):
        # Symbol without exchange prefix returns full string
        sym = SymbolInfo("BTCUSDT", "Bitcoin", "BINANCE", "crypto", "USDT")
        assert sym.ticker == "BTCUSDT"
