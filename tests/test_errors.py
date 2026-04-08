"""
Tests for scripts/lib/errors.py — error handling, exit codes, tagged output.

10+ tests verifying each error type maps to correct exit code and output.
"""

from __future__ import annotations

import sys

import pytest

from scripts.lib.errors import (
    handle_error,
    EXIT_OK,
    EXIT_GENERAL,
    EXIT_SYMBOL_NOT_FOUND,
    EXIT_NO_DATA,
    EXIT_CONNECTION,
    EXIT_AUTH,
    EXIT_RATE_LIMIT,
    EXIT_TIMEOUT,
    EXIT_CONFIG,
)
from tvfetch.exceptions import (
    TvSymbolNotFoundError,
    TvNoDataError,
    TvConnectionError,
    TvAuthError,
    TvRateLimitError,
    TvTimeoutError,
)


# ── Exit code mapping ────────────────────────────────────────────────────────

class TestExitCodes:
    def test_symbol_not_found_exit_code(self, capsys):
        exc = TvSymbolNotFoundError("FAKE:XXX")
        code = handle_error(exc, symbol="FAKE:XXX")
        assert code == EXIT_SYMBOL_NOT_FOUND

    def test_no_data_exit_code(self, capsys):
        exc = TvNoDataError("BINANCE:BTCUSDT", "1")
        code = handle_error(exc, symbol="BINANCE:BTCUSDT", timeframe="1")
        assert code == EXIT_NO_DATA

    def test_connection_error_exit_code(self, capsys):
        exc = TvConnectionError("Connection failed")
        code = handle_error(exc)
        assert code == EXIT_CONNECTION

    def test_auth_error_exit_code(self, capsys):
        exc = TvAuthError("Token invalid")
        code = handle_error(exc)
        assert code == EXIT_AUTH

    def test_rate_limit_exit_code(self, capsys):
        exc = TvRateLimitError("Rate limited")
        code = handle_error(exc)
        assert code == EXIT_RATE_LIMIT

    def test_timeout_exit_code(self, capsys):
        exc = TvTimeoutError("Timed out")
        code = handle_error(exc, symbol="BINANCE:BTCUSDT")
        assert code == EXIT_TIMEOUT

    def test_value_error_exit_code(self, capsys):
        exc = ValueError("Bad argument")
        code = handle_error(exc)
        assert code == EXIT_GENERAL

    def test_generic_exception_exit_code(self, capsys):
        exc = RuntimeError("Something went wrong")
        code = handle_error(exc)
        assert code == EXIT_GENERAL


# ── Tagged output verification ───────────────────────────────────────────────

class TestTaggedOutput:
    def test_symbol_not_found_has_error_type(self, capsys):
        exc = TvSymbolNotFoundError("FAKE:XXX")
        handle_error(exc, symbol="FAKE:XXX")
        err = capsys.readouterr().err
        assert "ERROR_TYPE: TvSymbolNotFoundError" in err

    def test_symbol_not_found_has_error_message(self, capsys):
        exc = TvSymbolNotFoundError("FAKE:XXX")
        handle_error(exc, symbol="FAKE:XXX")
        err = capsys.readouterr().err
        assert "ERROR_MESSAGE:" in err

    def test_symbol_not_found_has_recovery_hint(self, capsys):
        exc = TvSymbolNotFoundError("FAKE:XXX")
        handle_error(exc, symbol="FAKE:XXX")
        err = capsys.readouterr().err
        assert "RECOVERY_HINT:" in err

    def test_symbol_not_found_has_search_suggestion(self, capsys):
        exc = TvSymbolNotFoundError("FAKE:XXX")
        handle_error(exc, symbol="FAKE:XXX")
        err = capsys.readouterr().err
        assert "SEARCH_SUGGESTION: XXX" in err

    def test_symbol_not_found_search_suggestion_no_colon(self, capsys):
        """Symbol without colon -> full symbol as search suggestion."""
        exc = TvSymbolNotFoundError("BTCUSDT")
        handle_error(exc, symbol="BTCUSDT")
        err = capsys.readouterr().err
        assert "SEARCH_SUGGESTION: BTCUSDT" in err

    def test_no_data_has_suggested_timeframe(self, capsys):
        exc = TvNoDataError("SYM", "1")
        handle_error(exc, symbol="SYM", timeframe="1")
        err = capsys.readouterr().err
        assert "SUGGESTED_TIMEFRAME: 5" in err

    def test_no_data_suggested_timeframe_60(self, capsys):
        exc = TvNoDataError("SYM", "15")
        handle_error(exc, symbol="SYM", timeframe="15")
        err = capsys.readouterr().err
        assert "SUGGESTED_TIMEFRAME: 60" in err

    def test_no_data_suggested_timeframe_1d(self, capsys):
        exc = TvNoDataError("SYM", "60")
        handle_error(exc, symbol="SYM", timeframe="60")
        err = capsys.readouterr().err
        assert "SUGGESTED_TIMEFRAME: 1D" in err

    def test_no_data_suggested_timeframe_fallback(self, capsys):
        """Unknown timeframe in escalation map -> 1D."""
        exc = TvNoDataError("SYM", "240")
        handle_error(exc, symbol="SYM", timeframe="240")
        err = capsys.readouterr().err
        assert "SUGGESTED_TIMEFRAME: 1D" in err

    def test_connection_error_has_retry_hint(self, capsys):
        exc = TvConnectionError("Connection refused")
        handle_error(exc)
        err = capsys.readouterr().err
        assert "RECOVERY_HINT:" in err
        assert "Retry" in err or "retry" in err or "fallback" in err

    def test_auth_error_has_hint(self, capsys):
        exc = TvAuthError("Invalid token")
        handle_error(exc)
        err = capsys.readouterr().err
        assert "RECOVERY_HINT:" in err
        assert "auth_mgr" in err

    def test_rate_limit_has_wait_hint(self, capsys):
        exc = TvRateLimitError("Rate limited")
        handle_error(exc)
        err = capsys.readouterr().err
        assert "RECOVERY_HINT:" in err
        assert "Wait" in err or "wait" in err

    def test_timeout_error_output(self, capsys):
        exc = TvTimeoutError("Request timed out")
        handle_error(exc, symbol="BINANCE:BTCUSDT")
        err = capsys.readouterr().err
        assert "ERROR_TYPE: TvTimeoutError" in err
        assert "ERROR_SYMBOL: BINANCE:BTCUSDT" in err
        assert "fewer bars" in err


# ── Stable exit code constants ───────────────────────────────────────────────

class TestExitCodeConstants:
    """Verify exit code constants have expected values — they must stay stable."""

    def test_exit_ok(self):
        assert EXIT_OK == 0

    def test_exit_general(self):
        assert EXIT_GENERAL == 1

    def test_exit_symbol_not_found(self):
        assert EXIT_SYMBOL_NOT_FOUND == 2

    def test_exit_no_data(self):
        assert EXIT_NO_DATA == 3

    def test_exit_connection(self):
        assert EXIT_CONNECTION == 4

    def test_exit_auth(self):
        assert EXIT_AUTH == 5

    def test_exit_rate_limit(self):
        assert EXIT_RATE_LIMIT == 6

    def test_exit_timeout(self):
        assert EXIT_TIMEOUT == 7

    def test_exit_config(self):
        assert EXIT_CONFIG == 8
