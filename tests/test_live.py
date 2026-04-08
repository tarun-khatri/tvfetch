"""
Tests for tvfetch.live — LiveBar, LiveStream, stream().

WebSocket is fully mocked — no real network calls.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from tvfetch.live import LiveBar, LiveStream
from tvfetch.core import protocol
from tests.conftest import FakeWebSocketApp, ws_msg_symbol_resolved, ws_msg_series_completed


# ── LiveBar tests ─────────────────────────────────────────────────────────────

class TestLiveBar:
    def setup_method(self):
        self.bar = LiveBar(
            symbol="BINANCE:BTCUSDT",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=40000.0,
            high=42000.0,
            low=39000.0,
            close=41000.0,
            volume=100.0,
        )

    def test_change_positive(self):
        assert self.bar.change == pytest.approx(1000.0)

    def test_change_pct(self):
        assert self.bar.change_pct == pytest.approx(2.5)

    def test_change_pct_zero_open(self):
        bar = LiveBar(
            symbol="X", timestamp=datetime.now(tz=timezone.utc),
            open=0.0, high=1.0, low=0.0, close=0.5, volume=0.0
        )
        assert bar.change_pct == 0.0

    def test_repr_contains_symbol(self):
        assert "BINANCE:BTCUSDT" in repr(self.bar)

    def test_repr_shows_plus_for_positive_change(self):
        assert "+" in repr(self.bar)

    def test_repr_no_plus_for_negative_change(self):
        bar = LiveBar(
            symbol="X", timestamp=datetime.now(tz=timezone.utc),
            open=50000.0, high=50001.0, low=49000.0, close=49500.0, volume=1.0
        )
        assert "+" not in repr(bar)


# ── LiveStream tests ──────────────────────────────────────────────────────────

def _make_du_message(sess_id: str, bar_data: list) -> str:
    """Build a fake 'du' (data update) WS message."""
    return protocol.encode_json({
        "m": "du",
        "p": [sess_id, {"sds_1": {"s": [{"v": bar_data}]}}],
    })


class TestLiveStream:
    def test_callback_called_on_du_message(self):
        sess_id = "cs_live111222333"
        bar_data = [1700000000.0, 42000.0, 43000.0, 41500.0, 42500.0, 100.0]

        messages = [
            ws_msg_symbol_resolved(sess_id),
            ws_msg_series_completed(sess_id),
            _make_du_message(sess_id, bar_data),
        ]

        received: list[LiveBar] = []

        def on_update(bar: LiveBar) -> None:
            received.append(bar)

        def ws_factory(url, header=None, on_open=None, on_message=None,
                       on_error=None, on_close=None):
            ws = FakeWebSocketApp(url, header=header, on_open=on_open,
                                  on_message=on_message, on_error=on_error,
                                  on_close=on_close)
            ws.message_sequence = messages
            return ws

        # Patch new_chart_session so the session ID in the fake messages matches
        # the one registered by create_live_session().
        with patch("tvfetch.core.messages.new_chart_session", return_value=sess_id):
            with patch("websocket.WebSocketApp", ws_factory):
                ls = LiveStream(["BINANCE:BTCUSDT"])
                ls.on_update(on_update)
                ls.start(block=False)
                # Give the background thread time to process messages.
                # FakeWebSocketApp.run_forever() has a 0.05s delay after on_open,
                # then processes messages synchronously.
                time.sleep(0.3)
                ls.stop()

        assert len(received) >= 1
        bar = received[0]
        assert bar.symbol == "BINANCE:BTCUSDT"
        assert bar.close == 42500.0

    def test_stop_clears_session_ids(self):
        def ws_factory(url, header=None, on_open=None, on_message=None,
                       on_error=None, on_close=None):
            ws = FakeWebSocketApp(url, header=header, on_open=on_open,
                                  on_message=on_message, on_error=on_error,
                                  on_close=on_close)
            ws.message_sequence = []
            return ws

        with patch("websocket.WebSocketApp", ws_factory):
            ls = LiveStream(["BINANCE:BTCUSDT"])
            ls.on_update(lambda b: None)
            ls.start(block=False)
            ls.stop()

        assert ls._session_ids == []
        assert ls._conn is None
        assert not ls._running

    def test_on_update_chainable(self):
        ls = LiveStream(["X:Y"])
        result = ls.on_update(lambda b: None)
        assert result is ls

    def test_context_manager_calls_stop(self):
        mock_conn = MagicMock()
        mock_conn.start = MagicMock()
        mock_conn.stop = MagicMock()
        mock_conn.create_live_session = MagicMock(return_value=MagicMock(session_id="cs_test"))

        with patch("tvfetch.live.TvConnection", return_value=mock_conn):
            with LiveStream(["BINANCE:BTCUSDT"]) as ls:
                ls._session_ids = []  # prevent stop() from trying to close sessions
                pass  # __exit__ calls stop()

        mock_conn.stop.assert_called_once()

    def test_start_idempotent(self):
        """Calling start() twice should not create two connections."""
        mock_conn = MagicMock()
        mock_conn.start = MagicMock()
        mock_conn.create_live_session = MagicMock(return_value=MagicMock(session_id="cs_x"))

        with patch("tvfetch.live.TvConnection", return_value=mock_conn):
            ls = LiveStream(["BINANCE:BTCUSDT"])
            ls.start(block=False)
            ls.start(block=False)  # second call should be a no-op

        # TvConnection() should only have been created once (via _conn assignment)
        assert mock_conn.start.call_count == 1
