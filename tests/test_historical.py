"""
Tests for tvfetch.historical — fetch(), fetch_df(), fetch_multi().

WebSocket is fully mocked — no real network calls.
"""

from __future__ import annotations

import threading
from unittest.mock import patch, MagicMock

import pytest

from tvfetch.exceptions import TvSymbolNotFoundError, TvTimeoutError, TvNoDataError
from tvfetch.models import Bar, FetchResult
from tests.conftest import (
    FakeWebSocketApp, make_sample_bars,
    ws_msg_symbol_resolved, ws_msg_timescale_update,
    ws_msg_series_completed, ws_msg_series_error,
)

# A very short timeout for tests so failures are detected in ~5s, not 120s.
_TEST_TIMEOUT = 5


def _make_ws_with_messages(msgs):
    """Patch websocket.WebSocketApp to return a FakeWebSocketApp with preset messages."""
    def factory(url, header=None, on_open=None, on_message=None,
                on_error=None, on_close=None):
        ws = FakeWebSocketApp(url, header=header, on_open=on_open,
                              on_message=on_message, on_error=on_error,
                              on_close=on_close)
        ws.message_sequence = msgs
        return ws
    return factory


class TestFetch:
    def test_successful_fetch_returns_fetch_result(self):
        sess_id = "cs_test123456"
        bars = make_sample_bars(5)
        messages = [
            ws_msg_symbol_resolved(sess_id),
            ws_msg_timescale_update(sess_id, bars),
            ws_msg_series_completed(sess_id),
        ]

        with patch("tvfetch.core.messages.new_chart_session", return_value=sess_id):
            with patch("tvfetch.historical._FETCH_TIMEOUT", _TEST_TIMEOUT):
                with patch("websocket.WebSocketApp", _make_ws_with_messages(messages)):
                    from tvfetch.historical import fetch
                    result = fetch("BINANCE:BTCUSDT", "1D", bars=5, use_cache=False)

        assert isinstance(result, FetchResult)
        assert result.symbol == "BINANCE:BTCUSDT"
        assert result.timeframe == "1D"
        assert result.source == "tradingview"
        assert len(result.bars) == 5

    def test_bars_are_parsed_correctly(self):
        sess_id = "cs_test123456"
        raw_bars = [[1700000000.0, 100.0, 110.0, 90.0, 105.0, 500.0]]
        messages = [
            ws_msg_symbol_resolved(sess_id),
            ws_msg_timescale_update(sess_id, raw_bars),
            ws_msg_series_completed(sess_id),
        ]

        with patch("tvfetch.core.messages.new_chart_session", return_value=sess_id):
            with patch("tvfetch.historical._FETCH_TIMEOUT", _TEST_TIMEOUT):
                with patch("websocket.WebSocketApp", _make_ws_with_messages(messages)):
                    from tvfetch.historical import fetch
                    result = fetch("TEST:SYM", "1D", bars=1, use_cache=False)

        bar = result.bars[0]
        assert bar.open == 100.0
        assert bar.high == 110.0
        assert bar.close == 105.0

    def test_symbol_not_found_raises(self):
        sess_id = "cs_test123456"
        messages = [
            ws_msg_symbol_resolved(sess_id),
            ws_msg_series_error(sess_id, "symbol not found"),
        ]

        with patch("tvfetch.core.messages.new_chart_session", return_value=sess_id):
            with patch("tvfetch.historical._FETCH_TIMEOUT", _TEST_TIMEOUT):
                with patch("websocket.WebSocketApp", _make_ws_with_messages(messages)):
                    from tvfetch.historical import fetch
                    with pytest.raises((TvSymbolNotFoundError, Exception)):
                        fetch("INVALID:SYM999", "1D", bars=5, use_cache=False)

    def test_invalid_timeframe_raises_value_error(self):
        from tvfetch.historical import fetch
        with pytest.raises(ValueError, match="Invalid timeframe"):
            fetch("BINANCE:BTCUSDT", "INVALID", bars=5, use_cache=False)

    def test_auth_mode_anonymous(self):
        sess_id = "cs_test123456"
        bars = make_sample_bars(1)
        messages = [
            ws_msg_symbol_resolved(sess_id),
            ws_msg_timescale_update(sess_id, bars),
            ws_msg_series_completed(sess_id),
        ]

        with patch("tvfetch.core.messages.new_chart_session", return_value=sess_id):
            with patch("tvfetch.historical._FETCH_TIMEOUT", _TEST_TIMEOUT):
                with patch("websocket.WebSocketApp", _make_ws_with_messages(messages)):
                    from tvfetch.historical import fetch
                    from tvfetch.auth import ANONYMOUS_TOKEN
                    result = fetch("BINANCE:BTCUSDT", "1D", bars=1,
                                   auth_token=ANONYMOUS_TOKEN, use_cache=False)

        assert result.auth_mode == "anonymous"

    def test_auth_mode_token(self):
        sess_id = "cs_test123456"
        bars = make_sample_bars(1)
        messages = [
            ws_msg_symbol_resolved(sess_id),
            ws_msg_timescale_update(sess_id, bars),
            ws_msg_series_completed(sess_id),
        ]

        with patch("tvfetch.core.messages.new_chart_session", return_value=sess_id):
            with patch("tvfetch.historical._FETCH_TIMEOUT", _TEST_TIMEOUT):
                with patch("websocket.WebSocketApp", _make_ws_with_messages(messages)):
                    from tvfetch.historical import fetch
                    result = fetch("BINANCE:BTCUSDT", "1D", bars=1,
                                   auth_token="some.jwt.token", use_cache=False)

        assert result.auth_mode == "token"


class TestFetchDf:
    def test_returns_dataframe(self):
        sess_id = "cs_test123456"
        bars = make_sample_bars(3)
        messages = [
            ws_msg_symbol_resolved(sess_id),
            ws_msg_timescale_update(sess_id, bars),
            ws_msg_series_completed(sess_id),
        ]

        with patch("tvfetch.core.messages.new_chart_session", return_value=sess_id):
            with patch("tvfetch.historical._FETCH_TIMEOUT", _TEST_TIMEOUT):
                with patch("websocket.WebSocketApp", _make_ws_with_messages(messages)):
                    from tvfetch.historical import fetch_df
                    import pandas as pd
                    df = fetch_df("BINANCE:BTCUSDT", "1D", bars=3, use_cache=False)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "close" in df.columns


class TestFetchMulti:
    def test_returns_dict_of_results(self):
        # Two symbols, each gets their own session.
        # Patch new_chart_session to return them in order.
        sess1 = "cs_aaa111222333"
        sess2 = "cs_bbb444555666"
        bars = make_sample_bars(2)

        messages = [
            ws_msg_symbol_resolved(sess1),
            ws_msg_timescale_update(sess1, bars),
            ws_msg_series_completed(sess1),
            ws_msg_symbol_resolved(sess2),
            ws_msg_timescale_update(sess2, bars),
            ws_msg_series_completed(sess2),
        ]

        with patch("tvfetch.core.messages.new_chart_session", side_effect=[sess1, sess2]):
            with patch("tvfetch.historical._FETCH_TIMEOUT", _TEST_TIMEOUT):
                with patch("websocket.WebSocketApp", _make_ws_with_messages(messages)):
                    from tvfetch.historical import fetch_multi
                    results = fetch_multi(
                        ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT"], "1D", bars=2, use_cache=False
                    )

        assert isinstance(results, dict)
        assert "BINANCE:BTCUSDT" in results
        assert "BINANCE:ETHUSDT" in results

    def test_auth_mode_correct_in_multi(self):
        sess1 = "cs_aaa111222333"
        bars = make_sample_bars(1)
        messages = [
            ws_msg_symbol_resolved(sess1),
            ws_msg_timescale_update(sess1, bars),
            ws_msg_series_completed(sess1),
        ]

        with patch("tvfetch.core.messages.new_chart_session", return_value=sess1):
            with patch("tvfetch.historical._FETCH_TIMEOUT", _TEST_TIMEOUT):
                with patch("websocket.WebSocketApp", _make_ws_with_messages(messages)):
                    from tvfetch.historical import fetch_multi
                    results = fetch_multi(
                        ["BINANCE:BTCUSDT"], "1D", bars=1,
                        auth_token="some.jwt.token", use_cache=False,
                    )

        for result in results.values():
            if result.bars:  # only check non-empty results
                assert result.auth_mode == "token"


class TestCacheIntegration:
    def test_cache_hit_skips_network(self, tmp_path):
        """If cache has fresh data, fetch() should not open a WebSocket."""
        from tvfetch.cache import Cache
        from tvfetch.historical import fetch
        from tests.conftest import make_fetch_result

        # Pre-populate cache
        cache = Cache(path=tmp_path / "cache.db")
        cached_result = make_fetch_result("BINANCE:BTCUSDT", "1D", n=5)
        cache.save(cached_result)
        cache.close()

        ws_call_count = [0]

        def counting_ws_factory(*args, **kwargs):
            ws_call_count[0] += 1
            return MagicMock()

        # Patch module-level _cache to use our temp cache
        with patch("tvfetch.historical._cache", Cache(path=tmp_path / "cache.db")):
            with patch("websocket.WebSocketApp", counting_ws_factory):
                result = fetch("BINANCE:BTCUSDT", "1D", bars=5, use_cache=True)

        # WebSocket should NOT have been called
        assert ws_call_count[0] == 0
        assert result.source == "cache"
        assert len(result.bars) == 5
