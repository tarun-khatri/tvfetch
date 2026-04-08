"""Tests for tvfetch.cache — SQLite caching layer."""

import time
import pytest
from pathlib import Path

from tvfetch.cache import Cache, STALE_INTRADAY, STALE_DAILY, STALE_WEEKLY
from tests.conftest import make_fetch_result


@pytest.fixture
def cache(tmp_path):
    """Return a fresh Cache instance backed by a temp file."""
    c = Cache(path=tmp_path / "test_cache.db")
    yield c
    c.close()


class TestIsFresh:
    def test_empty_cache_not_fresh(self, cache):
        assert not cache.is_fresh("BINANCE:BTCUSDT", "1D")

    def test_fresh_after_save(self, cache):
        result = make_fetch_result(symbol="BINANCE:BTCUSDT", timeframe="1D")
        cache.save(result)
        assert cache.is_fresh("BINANCE:BTCUSDT", "1D")

    def test_different_timeframe_not_fresh(self, cache):
        result = make_fetch_result(symbol="BINANCE:BTCUSDT", timeframe="1D")
        cache.save(result)
        assert not cache.is_fresh("BINANCE:BTCUSDT", "60")

    def test_different_symbol_not_fresh(self, cache):
        result = make_fetch_result(symbol="BINANCE:BTCUSDT", timeframe="1D")
        cache.save(result)
        assert not cache.is_fresh("BINANCE:ETHUSDT", "1D")


class TestSaveAndLoad:
    def test_save_and_load_round_trip(self, cache):
        result = make_fetch_result(symbol="TEST:SYM", timeframe="1D", n=5)
        cache.save(result)
        df = cache.load("TEST:SYM", "1D")
        assert df is not None
        assert len(df) == 5
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_load_returns_none_when_not_cached(self, cache):
        assert cache.load("MISSING:SYM", "1D") is None

    def test_save_empty_bars_is_noop(self, cache):
        from tvfetch.models import FetchResult
        result = FetchResult("SYM", "1D", [], "tradingview", "anonymous")
        cache.save(result)  # Should not raise
        assert cache.load("SYM", "1D") is None

    def test_upsert_overwrites_old_data(self, cache):
        r1 = make_fetch_result(symbol="A:B", timeframe="1D", n=3)
        r2 = make_fetch_result(symbol="A:B", timeframe="1D", n=7)
        cache.save(r1)
        cache.save(r2)
        df = cache.load("A:B", "1D")
        # All 7 bars should be present (upsert by primary key ts)
        assert len(df) == 7


class TestClear:
    def test_clear_all(self, cache):
        cache.save(make_fetch_result("A:B", "1D"))
        cache.save(make_fetch_result("C:D", "60"))
        deleted = cache.clear()
        assert deleted >= 5  # at least the 5 bars from each
        assert cache.load("A:B", "1D") is None

    def test_clear_by_symbol(self, cache):
        cache.save(make_fetch_result("A:B", "1D"))
        cache.save(make_fetch_result("C:D", "1D"))
        cache.clear(symbol="A:B")
        assert cache.load("A:B", "1D") is None
        assert cache.load("C:D", "1D") is not None

    def test_clear_by_symbol_and_timeframe(self, cache):
        cache.save(make_fetch_result("A:B", "1D"))
        cache.save(make_fetch_result("A:B", "60"))
        cache.clear(symbol="A:B", timeframe="1D")
        assert cache.load("A:B", "1D") is None
        assert cache.load("A:B", "60") is not None


class TestStats:
    def test_stats_returns_dataframe(self, cache):
        cache.save(make_fetch_result("A:B", "1D"))
        df = cache.stats()
        assert not df.empty
        assert "symbol" in df.columns

    def test_stats_empty_when_no_data(self, cache):
        df = cache.stats()
        assert df.empty


class TestStaleness:
    def test_intraday_stale_threshold(self):
        from tvfetch.cache import _stale_seconds
        assert _stale_seconds("1") == STALE_INTRADAY
        assert _stale_seconds("60") == STALE_INTRADAY
        assert _stale_seconds("240") == STALE_INTRADAY

    def test_daily_stale_threshold(self):
        from tvfetch.cache import _stale_seconds
        assert _stale_seconds("1D") == STALE_DAILY

    def test_weekly_monthly_stale_threshold(self):
        from tvfetch.cache import _stale_seconds
        assert _stale_seconds("1W") == STALE_WEEKLY
        assert _stale_seconds("1M") == STALE_WEEKLY
