"""Tests for tvfetch.core.protocol — frame encode/decode."""

import pytest
from tvfetch.core import protocol


class TestEncode:
    def test_encode_wraps_in_frame(self):
        result = protocol.encode("hello")
        assert result == "~m~5~m~hello"

    def test_encode_counts_bytes(self):
        # UTF-8: 3 bytes per Chinese char
        result = protocol.encode("hi")
        assert result == "~m~2~m~hi"

    def test_encode_json_produces_valid_frame(self):
        obj = {"m": "test", "p": [1, 2]}
        result = protocol.encode_json(obj)
        assert result.startswith("~m~")
        # Should contain valid JSON
        import json
        payload = result.split("~m~", 2)[-1]
        parsed = json.loads(payload)
        assert parsed["m"] == "test"


class TestDecode:
    def test_decode_single_frame(self):
        raw = "~m~5~m~hello"
        payloads = protocol.decode(raw)
        assert payloads == ["hello"]

    def test_decode_multiple_frames(self):
        raw = "~m~3~m~foo~m~3~m~bar"
        payloads = protocol.decode(raw)
        assert payloads == ["foo", "bar"]

    def test_decode_empty_returns_empty_list(self):
        assert protocol.decode("") == []

    def test_decode_json_parses_valid_json(self):
        import json
        payload = json.dumps({"m": "test", "p": ["session1"]})
        raw = protocol.encode(payload)
        msgs = protocol.decode_json(raw)
        assert len(msgs) == 1
        assert msgs[0]["m"] == "test"

    def test_decode_json_skips_heartbeats(self):
        heartbeat = protocol.encode("~h~42")
        msgs = protocol.decode_json(heartbeat)
        assert msgs == []

    def test_decode_json_skips_non_json(self):
        raw = protocol.encode("not json at all")
        msgs = protocol.decode_json(raw)
        assert msgs == []


class TestHeartbeat:
    def test_is_heartbeat_true(self):
        assert protocol.is_heartbeat("~m~7~m~~h~123")

    def test_is_heartbeat_false(self):
        assert not protocol.is_heartbeat("~m~5~m~hello")

    def test_extract_heartbeat_returns_echo(self):
        raw = "~m~7~m~~h~123"
        reply = protocol.extract_heartbeat(raw)
        assert reply is not None
        assert "~h~123" in reply

    def test_extract_heartbeat_none_for_non_heartbeat(self):
        assert protocol.extract_heartbeat("~m~5~m~hello") is None
