"""
Tests for cli/main.py — CLI commands.

Uses Click's CliRunner to invoke commands without a real process.
All tvfetch library calls are mocked.

NOTE: These tests require the cli/ package. If it is not available
(e.g. in tvfetch-skill which uses scripts/ instead), the entire module
is skipped.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

try:
    from cli.main import cli
except ImportError:
    pytest.skip("cli module not available in this project layout", allow_module_level=True)

from tests.conftest import make_fetch_result


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_fetch_result():
    return make_fetch_result("BINANCE:BTCUSDT", "1D", n=25)


class TestFetchCommand:
    def test_fetch_prints_table(self, runner, mock_fetch_result):
        with patch("tvfetch.fetch", return_value=mock_fetch_result):
            result = runner.invoke(cli, ["fetch", "BINANCE:BTCUSDT"])
        assert result.exit_code == 0
        assert "BINANCE:BTCUSDT" in result.output

    def test_fetch_saves_csv(self, runner, mock_fetch_result, tmp_path):
        out = str(tmp_path / "test.csv")
        with patch("tvfetch.fetch", return_value=mock_fetch_result):
            result = runner.invoke(cli, ["fetch", "BINANCE:BTCUSDT", "--output", out])
        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_fetch_invalid_symbol_shows_error(self, runner):
        from tvfetch.exceptions import TvSymbolNotFoundError
        with patch("tvfetch.fetch", side_effect=TvSymbolNotFoundError("BAD:SYM")):
            result = runner.invoke(cli, ["fetch", "BAD:SYM"])
        assert result.exit_code == 1

    def test_fetch_no_cache_flag_passed(self, runner, mock_fetch_result):
        """--no-cache should pass use_cache=False to tvfetch.fetch()."""
        call_kwargs = {}

        def capture_fetch(**kwargs):
            call_kwargs.update(kwargs)
            return mock_fetch_result

        with patch("tvfetch.fetch", side_effect=capture_fetch):
            runner.invoke(cli, ["fetch", "BINANCE:BTCUSDT", "--no-cache"])

        assert call_kwargs.get("use_cache") is False

    def test_fetch_default_uses_cache(self, runner, mock_fetch_result):
        """Default fetch should pass use_cache=True."""
        call_kwargs = {}

        def capture_fetch(**kwargs):
            call_kwargs.update(kwargs)
            return mock_fetch_result

        with patch("tvfetch.fetch", side_effect=capture_fetch):
            runner.invoke(cli, ["fetch", "BINANCE:BTCUSDT"])

        assert call_kwargs.get("use_cache") is True

    def test_fetch_freqtrade_format(self, runner, mock_fetch_result, tmp_path):
        out = str(tmp_path / "data.json")
        with patch("tvfetch.fetch", return_value=mock_fetch_result):
            result = runner.invoke(cli, [
                "fetch", "BINANCE:BTCUSDT", "--output", out, "--format", "freqtrade"
            ])
        assert result.exit_code == 0


class TestSearchCommand:
    def test_search_displays_results(self, runner):
        from tvfetch.models import SymbolInfo
        mock_results = [
            SymbolInfo("BINANCE:BTCUSDT", "Bitcoin", "BINANCE", "crypto", "USDT"),
        ]
        with patch("tvfetch.search", return_value=mock_results):
            result = runner.invoke(cli, ["search", "bitcoin"])
        assert result.exit_code == 0
        assert "BINANCE:BTCUSDT" in result.output

    def test_search_no_results(self, runner):
        with patch("tvfetch.search", return_value=[]):
            result = runner.invoke(cli, ["search", "xyznotexist"])
        assert result.exit_code == 0
        assert "No symbols found" in result.output


class TestAuthCommand:
    def test_auth_token_shows_instructions(self, runner):
        result = runner.invoke(cli, ["auth", "token"])
        assert result.exit_code == 0
        assert "TradingView" in result.output
        assert "JWT" in result.output or "token" in result.output.lower()


class TestCacheCommand:
    def test_cache_stats_empty(self, runner, tmp_path):
        from tvfetch.cache import Cache
        with patch("tvfetch.cache.DEFAULT_CACHE_PATH", tmp_path / "cache.db"):
            result = runner.invoke(cli, ["cache", "stats"])
        assert result.exit_code == 0

    def test_cache_clear_requires_confirm(self, runner, tmp_path):
        with patch("tvfetch.cache.DEFAULT_CACHE_PATH", tmp_path / "cache.db"):
            # Answer "n" to the confirmation prompt
            result = runner.invoke(cli, ["cache", "clear"], input="n\n")
        # Should abort without error
        assert result.exit_code != 0 or "Aborted" in result.output
