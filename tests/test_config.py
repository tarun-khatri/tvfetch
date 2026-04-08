"""
Tests for scripts/lib/config.py — configuration resolution, JWT validation, env loading.

All 20+ tests run offline with no real env vars leaking in.
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ── JWT helper ──────────────────────────────────────────────────────────────────

def make_jwt(exp_offset: int = 3600) -> str:
    """Build a fake JWT with a given expiry offset from now."""
    header = base64.b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    payload = base64.b64encode(
        json.dumps({"exp": int(time.time()) + exp_offset}).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.fakesig"


# ── Tests ────────────────────────────────────────────────────────────────────────

class TestAnonymousDefaults:
    def test_anonymous_by_default(self, mock_config):
        """No env vars set -> anonymous auth."""
        from scripts.lib.config import get_config, ANONYMOUS_TOKEN
        cfg = get_config()
        assert cfg.auth_token == ANONYMOUS_TOKEN
        assert cfg.auth_source == "anonymous"
        assert cfg.is_anonymous is True

    def test_env_var_override(self, mock_config, monkeypatch):
        """TV_AUTH_TOKEN env var -> 'env' source."""
        token = make_jwt(3600)
        monkeypatch.setenv("TV_AUTH_TOKEN", token)
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.auth_token == token
        assert cfg.auth_source == "env"
        assert cfg.is_anonymous is False

    def test_env_file_loading(self, mock_config, tmp_path):
        """Write a temp .env file in the default location and verify it loads."""
        token = make_jwt(7200)
        env_file = tmp_path / ".env"
        env_file.write_text(f"TV_AUTH_TOKEN={token}\n", encoding="utf-8")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.auth_token == token
        assert cfg.auth_source == ".env"

    def test_resolution_order_env_beats_env_file(self, mock_config, monkeypatch, tmp_path):
        """Env var beats .env file."""
        env_token = make_jwt(3600)
        file_token = make_jwt(7200)
        monkeypatch.setenv("TV_AUTH_TOKEN", env_token)
        (tmp_path / ".env").write_text(f"TV_AUTH_TOKEN={file_token}\n", encoding="utf-8")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.auth_token == env_token
        assert cfg.auth_source == "env"


class TestValidateToken:
    def test_validate_token_anonymous(self):
        from scripts.lib.config import validate_token, ANONYMOUS_TOKEN
        valid, reason = validate_token(ANONYMOUS_TOKEN)
        assert valid is True
        assert reason == "anonymous"

    def test_validate_token_valid_jwt(self):
        """Fake JWT with future exp -> (True, 'valid')."""
        from scripts.lib.config import validate_token
        token = make_jwt(exp_offset=3600)
        valid, reason = validate_token(token)
        assert valid is True
        assert reason == "valid"

    def test_validate_token_expired(self):
        """Fake JWT with past exp -> (False, 'expired...')."""
        from scripts.lib.config import validate_token
        token = make_jwt(exp_offset=-3600)
        valid, reason = validate_token(token)
        assert valid is False
        assert "expired" in reason.lower()

    def test_validate_token_malformed(self):
        """'not.a.jwt' with bad base64 -> (False, ...)."""
        from scripts.lib.config import validate_token
        valid, reason = validate_token("not.a.jwt")
        assert valid is False
        assert reason  # non-empty error message

    def test_validate_token_two_parts_only(self):
        """Only two dot-separated parts -> not a valid JWT."""
        from scripts.lib.config import validate_token
        valid, reason = validate_token("header.payload")
        assert valid is False
        assert "3 dot-separated parts" in reason

    def test_validate_token_no_exp_field(self):
        """JWT with valid structure but no 'exp' field -> still valid."""
        from scripts.lib.config import validate_token
        header = base64.b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
        payload = base64.b64encode(json.dumps({"sub": "user"}).encode()).decode().rstrip("=")
        token = f"{header}.{payload}.sig"
        valid, reason = validate_token(token)
        assert valid is True
        assert reason == "valid"


class TestShowConfig:
    def test_show_config_prints_tags(self, mock_config, capsys):
        from scripts.lib.config import show_config, get_config
        cfg = get_config()
        show_config(cfg)
        out = capsys.readouterr().out
        assert "=== TVFETCH CONFIG ===" in out
        assert "=== END ===" in out

    def test_show_config_has_auth_mode(self, mock_config, capsys):
        from scripts.lib.config import show_config, get_config
        show_config(get_config())
        out = capsys.readouterr().out
        assert "AUTH_MODE:" in out

    def test_show_config_has_cache_path(self, mock_config, capsys):
        from scripts.lib.config import show_config, get_config
        show_config(get_config())
        out = capsys.readouterr().out
        assert "CACHE_PATH:" in out


class TestCheckAuthQuiet:
    def test_check_auth_quiet_anonymous(self, mock_config, capsys):
        from scripts.lib.config import check_auth_quiet
        check_auth_quiet()
        out = capsys.readouterr().out
        assert "TVFETCH AUTH: anonymous" in out

    def test_check_auth_quiet_with_token(self, mock_config, monkeypatch, capsys):
        token = make_jwt(3600)
        monkeypatch.setenv("TV_AUTH_TOKEN", token)
        from scripts.lib.config import check_auth_quiet
        check_auth_quiet()
        out = capsys.readouterr().out
        assert "TVFETCH AUTH: token found" in out
        assert "source: env" in out

    def test_check_auth_quiet_expired_token(self, mock_config, monkeypatch, capsys):
        token = make_jwt(-3600)
        monkeypatch.setenv("TV_AUTH_TOKEN", token)
        from scripts.lib.config import check_auth_quiet
        check_auth_quiet()
        out = capsys.readouterr().out
        assert "EXPIRED" in out


class TestConfigFields:
    def test_mock_mode_from_env(self, mock_config, monkeypatch):
        monkeypatch.setenv("TVFETCH_MOCK", "1")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.mock_mode is True

    def test_mock_mode_default_false(self, mock_config):
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.mock_mode is False

    def test_config_proxy(self, mock_config, monkeypatch):
        monkeypatch.setenv("TVFETCH_PROXY", "http://proxy.local:8080")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.proxy_url == "http://proxy.local:8080"

    def test_config_proxy_default_none(self, mock_config):
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.proxy_url is None

    def test_config_timeout(self, mock_config, monkeypatch):
        monkeypatch.setenv("TVFETCH_TIMEOUT", "60")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.timeout == 60

    def test_config_timeout_default(self, mock_config):
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.timeout == 120

    def test_config_fallback_enabled_by_default(self, mock_config):
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.fallback_enabled is True

    def test_config_fallback_disabled(self, mock_config, monkeypatch):
        monkeypatch.setenv("TVFETCH_FALLBACK", "false")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.fallback_enabled is False

    def test_config_fallback_disabled_zero(self, mock_config, monkeypatch):
        monkeypatch.setenv("TVFETCH_FALLBACK", "0")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.fallback_enabled is False

    def test_cache_path_from_env(self, mock_config, monkeypatch, tmp_path):
        custom_path = str(tmp_path / "custom_cache.db")
        monkeypatch.setenv("TVFETCH_CACHE_PATH", custom_path)
        from scripts.lib.config import get_config
        cfg = get_config()
        assert str(cfg.cache_path) == custom_path

    def test_cache_path_default(self, mock_config, tmp_path):
        from scripts.lib.config import get_config
        cfg = get_config()
        # Should use the monkeypatched default which is tmp_path / "cache.db"
        assert str(cfg.cache_path) == str(tmp_path / "cache.db")


class TestEnvFileParsing:
    def test_env_file_comments_ignored(self, mock_config, tmp_path):
        token = make_jwt(3600)
        env_content = f"""# This is a comment
# Another comment
TV_AUTH_TOKEN={token}
"""
        (tmp_path / ".env").write_text(env_content, encoding="utf-8")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.auth_token == token

    def test_env_file_quoted_values(self, mock_config, tmp_path):
        token = make_jwt(3600)
        env_content = f'TV_AUTH_TOKEN="{token}"\n'
        (tmp_path / ".env").write_text(env_content, encoding="utf-8")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.auth_token == token
        assert '"' not in cfg.auth_token

    def test_env_file_single_quoted_values(self, mock_config, tmp_path):
        token = make_jwt(3600)
        env_content = f"TV_AUTH_TOKEN='{token}'\n"
        (tmp_path / ".env").write_text(env_content, encoding="utf-8")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.auth_token == token
        assert "'" not in cfg.auth_token

    def test_env_file_empty_lines_skipped(self, mock_config, tmp_path):
        token = make_jwt(3600)
        env_content = f"\n\n\nTV_AUTH_TOKEN={token}\n\n"
        (tmp_path / ".env").write_text(env_content, encoding="utf-8")
        from scripts.lib.config import get_config
        cfg = get_config()
        assert cfg.auth_token == token


class TestCliTokenPriority:
    def test_config_cli_token_highest_priority(self, mock_config, monkeypatch, tmp_path):
        """cli_token beats env var and .env file."""
        cli_token = make_jwt(1800)
        env_token = make_jwt(3600)
        file_token = make_jwt(7200)
        monkeypatch.setenv("TV_AUTH_TOKEN", env_token)
        (tmp_path / ".env").write_text(f"TV_AUTH_TOKEN={file_token}\n", encoding="utf-8")
        from scripts.lib.config import get_config
        cfg = get_config(cli_token=cli_token)
        assert cfg.auth_token == cli_token
        assert cfg.auth_source == "cli_flag"
