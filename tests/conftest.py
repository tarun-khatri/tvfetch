"""
Shared pytest fixtures for tvfetch tests.

All tests run without any real network connections. The WebSocket is mocked
at the websocket.WebSocketApp level.
"""

from __future__ import annotations

import json
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from tvfetch.core import protocol
from tvfetch.models import Bar, FetchResult


# ── Sample data ───────────────────────────────────────────────────────────────

SAMPLE_BAR_RAW = [1700000000.0, 42000.0, 43000.0, 41500.0, 42500.0, 1234.56]

SAMPLE_BAR = Bar(
    timestamp=datetime.fromtimestamp(1700000000.0, tz=timezone.utc),
    open=42000.0,
    high=43000.0,
    low=41500.0,
    close=42500.0,
    volume=1234.56,
)


def make_sample_bars(n: int = 5) -> list[list]:
    """Return n fake raw bar lists with incrementing timestamps."""
    base_ts = 1700000000
    return [
        [float(base_ts + i * 86400), 42000.0 + i, 43000.0 + i, 41500.0 + i, 42500.0 + i, 1000.0 + i]
        for i in range(n)
    ]


def make_fetch_result(symbol="BINANCE:BTCUSDT", timeframe="1D", n=5) -> FetchResult:
    """Build a FetchResult with n sample bars."""
    return FetchResult(
        symbol=symbol,
        timeframe=timeframe,
        bars=[Bar.from_tv(b) for b in make_sample_bars(n)],
        source="tradingview",
        auth_mode="anonymous",
    )


# ── WS message builders ────────────────────────────────────────────────────────

def ws_msg_symbol_resolved(sess_id: str, symbol: str = "BTCUSDT") -> str:
    return protocol.encode_json({"m": "symbol_resolved", "p": [sess_id, {"name": symbol}]})


def ws_msg_timescale_update(sess_id: str, bars: list[list]) -> str:
    bar_objs = [{"v": b} for b in bars]
    return protocol.encode_json({
        "m": "timescale_update",
        "p": [sess_id, {"sds_1": {"s": bar_objs}}],
    })


def ws_msg_series_completed(sess_id: str) -> str:
    return protocol.encode_json({"m": "series_completed", "p": [sess_id, "s1"]})


def ws_msg_series_error(sess_id: str, err: str = "unknown") -> str:
    return protocol.encode_json({"m": "series_error", "p": [sess_id, err]})


def ws_msg_heartbeat(hb_id: int = 1) -> str:
    return protocol.encode(f"~h~{hb_id}")


# ── Network block ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """
    Block any real socket connections during tests.
    All WebSocket usage must go through mock fixtures.
    """
    import socket as _socket

    _original = _socket.getaddrinfo

    def _block(host, port, *args, **kwargs):
        if host in ("localhost", "127.0.0.1", "::1"):
            return _original(host, port, *args, **kwargs)
        raise RuntimeError(
            f"Real network call blocked in tests! Host={host}:{port}. "
            "Patch websocket.WebSocketApp or use the fake_ws_factory fixture."
        )

    monkeypatch.setattr(_socket, "getaddrinfo", _block)


# ── WebSocket mock ─────────────────────────────────────────────────────────────

class FakeWebSocketApp:
    """
    Simulates websocket.WebSocketApp for testing.

    On run_forever(), immediately fires on_open, then processes
    the message_sequence list in order, then stays idle.
    """

    def __init__(self, url, header=None, on_open=None, on_message=None,
                 on_error=None, on_close=None):
        self.url = url
        self._on_open = on_open
        self._on_message = on_message
        self._on_error = on_error
        self._on_close = on_close
        self.sent_messages: list[str] = []
        self.message_sequence: list[str] = []
        self._closed = False

    def send(self, data: str) -> None:
        self.sent_messages.append(data)

    def close(self) -> None:
        self._closed = True
        if self._on_close:
            self._on_close(self, 1000, "Normal closure")

    def run_forever(self, ping_interval=0) -> None:
        if self._on_open:
            self._on_open(self)
        # Brief pause so the main thread can register sessions after _ready is set.
        # Without this, all messages would be processed before create_live_session()
        # or create_historical_session() registers their session IDs.
        time.sleep(0.05)
        for msg in self.message_sequence:
            if self._closed:
                break
            if self._on_message:
                self._on_message(self, msg)


@pytest.fixture
def fake_ws_factory():
    """
    Returns a factory that creates FakeWebSocketApp instances.
    Each call to the factory returns a new instance configured with
    the provided message_sequence.
    """
    instances = []

    def factory(message_sequence: list[str] = None):
        def _make_ws(url, header=None, on_open=None, on_message=None,
                     on_error=None, on_close=None):
            ws = FakeWebSocketApp(url, header=header, on_open=on_open,
                                  on_message=on_message, on_error=on_error,
                                  on_close=on_close)
            ws.message_sequence = message_sequence or []
            instances.append(ws)
            return ws
        return _make_ws

    factory.instances = instances
    return factory


# ── NEW fixtures for tvfetch-skill scripts/lib/ tests ──────────────────────────

@pytest.fixture
def mock_config(monkeypatch, tmp_path):
    """
    Monkeypatch Config resolution so it uses temp paths and no real env vars
    leak into tests. Returns a factory to create Config with overrides.
    """
    from scripts.lib.config import Config, ANONYMOUS_TOKEN, DEFAULT_CACHE_PATH

    # Clear all TVFETCH_* and TV_* env vars so tests start from a clean slate
    for key in list(monkeypatch._patches if hasattr(monkeypatch, '_patches') else []):
        pass  # monkeypatch handles cleanup automatically

    env_vars_to_clear = [
        "TV_AUTH_TOKEN", "TVFETCH_MOCK", "TVFETCH_PROXY",
        "TVFETCH_TIMEOUT", "TVFETCH_FALLBACK", "TVFETCH_CACHE_PATH",
        "TVFETCH_LOG_LEVEL",
    ]
    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)

    # Redirect default paths to temp dir
    monkeypatch.setattr("scripts.lib.config.DEFAULT_TVFETCH_DIR", tmp_path)
    monkeypatch.setattr("scripts.lib.config.DEFAULT_CACHE_PATH", tmp_path / "cache.db")
    monkeypatch.setattr("scripts.lib.config.DEFAULT_ENV_PATH", tmp_path / ".env")

    return tmp_path


@pytest.fixture
def fixtures_dir():
    """Return the path to the tvfetch-skill fixtures directory."""
    return Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def sample_df():
    """
    100-bar daily DataFrame with OHLCV columns and datetime index.
    Uses seeded np.random for reproducibility.
    """
    rng = np.random.RandomState(42)
    n = 100

    # Generate a random-walk close price starting at 100
    close = 100 + np.cumsum(rng.randn(n) * 2)

    # Generate OHLCV from close
    high = close + rng.uniform(0.5, 3.0, n)
    low = close - rng.uniform(0.5, 3.0, n)
    open_ = close + rng.randn(n) * 1.0
    volume = rng.uniform(1000, 50000, n)

    dates = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")

    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=dates)

    return df
