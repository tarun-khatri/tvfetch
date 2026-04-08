"""
Tests for scripts/lib/mock.py — fixture loading, matching, round-trip.

15+ tests using the real fixture files in tvfetch-skill/fixtures/.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.lib.mock import (
    _symbol_safe,
    find_fixture,
    load_fixture,
    create_fixture_json,
    FIXTURES_DIR,
)
from tvfetch.models import Bar, FetchResult


# ── _symbol_safe tests ────────────────────────────────────────────────────────

class TestSymbolSafe:
    def test_colon_replaced(self):
        assert _symbol_safe("BINANCE:BTCUSDT") == "binance_btcusdt"

    def test_lowercased(self):
        assert _symbol_safe("NASDAQ:AAPL") == "nasdaq_aapl"

    def test_no_colon(self):
        assert _symbol_safe("BTCUSDT") == "btcusdt"


# ── find_fixture tests ────────────────────────────────────────────────────────

class TestFindFixture:
    def test_find_fixture_exact_match(self, fixtures_dir):
        """btcusdt 1D 100 bars -> finds the matching fixture."""
        path = find_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=fixtures_dir)
        assert path is not None
        # On Windows the filesystem is case-insensitive, so the path object
        # may contain the constructed name (with uppercase 1D) even though
        # the on-disk file uses lowercase 1d. Compare case-insensitively.
        assert path.name.lower() == "fetch_binance_btcusdt_1d_100bars.json"

    def test_find_fixture_without_bars(self, fixtures_dir):
        """When exact bar-count match not available, should fall back to no-bars variant."""
        # Request 200 bars for btcusdt 1D -- no exact 200bars file exists
        # Should fall back through: no partial match -> symbol only -> default
        path = find_fixture("BINANCE:BTCUSDT", "1D", 200, fixtures_dir=fixtures_dir)
        assert path is not None
        # Could match the 100bars file (exact) won't match, should find some fallback
        assert path.is_file()

    def test_find_fixture_default_fallback(self, fixtures_dir):
        """Unknown symbol -> fetch_default.json."""
        path = find_fixture("UNKNOWN:XYZXYZ", "1D", 100, fixtures_dir=fixtures_dir)
        assert path is not None
        assert path.name == "fetch_default.json"

    def test_find_fixture_none_empty_dir(self, tmp_path):
        """No fixture files at all -> None."""
        empty_dir = tmp_path / "empty_fixtures"
        empty_dir.mkdir()
        path = find_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=empty_dir)
        assert path is None

    def test_find_fixture_nonexistent_dir(self, tmp_path):
        """Fixtures dir doesn't exist -> None."""
        path = find_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=tmp_path / "nope")
        assert path is None

    def test_find_fixture_aapl(self, fixtures_dir):
        """NASDAQ:AAPL 1D 50 bars -> fetch_nasdaq_aapl_1d_50bars.json."""
        path = find_fixture("NASDAQ:AAPL", "1D", 50, fixtures_dir=fixtures_dir)
        assert path is not None
        assert "aapl" in path.name

    def test_find_fixture_eurusd(self, fixtures_dir):
        """FX:EURUSD 60 200 bars -> fetch_fx_eurusd_60_200bars.json."""
        path = find_fixture("FX:EURUSD", "60", 200, fixtures_dir=fixtures_dir)
        assert path is not None
        assert "eurusd" in path.name


# ── load_fixture tests ────────────────────────────────────────────────────────

class TestLoadFixture:
    def test_load_fixture_returns_fetch_result(self, fixtures_dir):
        result = load_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=fixtures_dir)
        assert isinstance(result, FetchResult)

    def test_load_fixture_bars_parsed(self, fixtures_dir):
        result = load_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=fixtures_dir)
        assert len(result.bars) == 100
        bar = result.bars[0]
        assert isinstance(bar, Bar)
        assert bar.open > 0
        assert bar.high > 0
        assert bar.close > 0
        assert bar.volume > 0
        assert isinstance(bar.timestamp, datetime)

    def test_load_fixture_trimmed_to_bars(self, fixtures_dir):
        """Load 100-bar fixture and verify trimming works."""
        # Load full 100-bar fixture
        full = load_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=fixtures_dir)
        assert full is not None
        assert len(full.bars) == 100
        # Now test trimming by using the default fixture (20 bars)
        # and requesting 10 bars for an unknown symbol (falls back to default)
        result = load_fixture("UNKNOWN:TRIMTEST", "1D", 10, fixtures_dir=fixtures_dir)
        assert result is not None
        assert len(result.bars) == 10

    def test_load_fixture_no_trim_when_fewer(self, fixtures_dir):
        """Requesting more bars than fixture has -> all bars returned."""
        # Default fixture has 20 bars; unknown symbol falls to default
        result = load_fixture("UNKNOWN:NOTRIMTEST", "1D", 999, fixtures_dir=fixtures_dir)
        assert result is not None
        # Default fixture has 20 bars, no trimming because 20 < 999
        assert len(result.bars) == 20

    def test_load_fixture_source_is_mock(self, fixtures_dir):
        result = load_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=fixtures_dir)
        assert result.source == "mock"

    def test_load_fixture_symbol_set(self, fixtures_dir):
        result = load_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=fixtures_dir)
        assert result.symbol == "BINANCE:BTCUSDT"

    def test_load_fixture_default_fallback(self, fixtures_dir):
        """Unknown symbol loads default fixture."""
        result = load_fixture("UNKNOWN:XYZXYZ", "1D", 100, fixtures_dir=fixtures_dir)
        assert result is not None
        assert len(result.bars) > 0

    def test_load_fixture_none_empty_dir(self, tmp_path):
        """No fixtures available -> None."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = load_fixture("BINANCE:BTCUSDT", "1D", 100, fixtures_dir=empty_dir)
        assert result is None


# ── create_fixture_json tests ────────────────────────────────────────────────

class TestCreateFixtureJson:
    def test_round_trip(self, fixtures_dir):
        """FetchResult -> JSON -> FetchResult should have matching data."""
        original = load_fixture("BINANCE:BTCUSDT", "1D", 10, fixtures_dir=fixtures_dir)
        assert original is not None

        fixture_json = create_fixture_json(original)

        # Verify JSON structure
        assert fixture_json["symbol"] == original.symbol
        assert fixture_json["timeframe"] == original.timeframe
        assert len(fixture_json["bars"]) == len(original.bars)

        # Verify bars can be parsed back
        for orig_bar, json_bar in zip(original.bars, sorted(fixture_json["bars"], key=lambda x: x["ts"])):
            assert json_bar["o"] == orig_bar.open
            assert json_bar["h"] == orig_bar.high
            assert json_bar["l"] == orig_bar.low
            assert json_bar["c"] == orig_bar.close
            assert json_bar["v"] == orig_bar.volume

    def test_create_fixture_json_fields(self):
        """Verify the JSON has all expected fields."""
        bars = [
            Bar(
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                open=100.0, high=110.0, low=90.0, close=105.0, volume=5000.0,
            ),
        ]
        result = FetchResult("TEST:SYM", "1D", bars, "tradingview", "anonymous")
        fixture_json = create_fixture_json(result)

        assert "symbol" in fixture_json
        assert "timeframe" in fixture_json
        assert "bars" in fixture_json
        bar = fixture_json["bars"][0]
        assert all(k in bar for k in ("ts", "o", "h", "l", "c", "v"))

    def test_create_fixture_json_bars_sorted(self):
        """Bars should be sorted by timestamp in the JSON output."""
        bars = [
            Bar(timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc),
                open=103.0, high=113.0, low=93.0, close=108.0, volume=3000.0),
            Bar(timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                open=100.0, high=110.0, low=90.0, close=105.0, volume=5000.0),
            Bar(timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
                open=102.0, high=112.0, low=92.0, close=107.0, volume=4000.0),
        ]
        result = FetchResult("TEST:SYM", "1D", bars, "tradingview", "anonymous")
        fixture_json = create_fixture_json(result)

        timestamps = [b["ts"] for b in fixture_json["bars"]]
        assert timestamps == sorted(timestamps)
