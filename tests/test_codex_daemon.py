"""The proxy must preserve notifications while RPC replies and frames interleave."""

import io
import json
import struct
from collections import deque

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
daemon = script("codex_daemon")


def frame(data, opcode=1, final=True):
    length = len(data)
    size = bytes([length]) if length < 126 else b"\x7e" + struct.pack(">H", length)
    return bytes([(128 if final else 0) | opcode]) + size + data


def wire(data):
    client = daemon.Proxy.__new__(daemon.Proxy)
    client.input = io.BytesIO()
    client.buffer = b""
    client.serial = 0
    client.pending = deque()
    chunks = iter(bytes([b]) for b in data)

    def fill(_):
        client.buffer += next(chunks)

    client.fill = fill
    return client


def sent_frames(client):
    data = client.input.getvalue()
    out = []
    while data:
        opcode, length = data[0] & 15, data[1] & 127
        assert data[1] & 128
        offset = 2
        extra = 2 if length == 126 else 8 if length == 127 else 0
        if extra:
            length = int.from_bytes(data[offset : offset + extra], "big")
            offset += extra
        mask = data[offset : offset + 4]
        body = data[offset + 4 : offset + 4 + length]
        out.append((opcode, bytes(b ^ mask[i % 4] for i, b in enumerate(body))))
        data = data[offset + 4 + length :]
    return out


def test_fragmented_reply_preserves_notifications_and_answers_ping():
    notice = {"method": "turn/completed", "params": {"threadId": "thread"}}
    reply = json.dumps({"id": 1, "result": {"turnId": "turn"}}).encode()
    client = wire(
        frame(json.dumps(notice).encode())
        + frame(reply[:10], final=False)
        + frame(b"ping", opcode=9)
        + frame(reply[10:], opcode=0)
    )
    assert client.call("turn/steer", {"input": "x" * 70000}) == {"turnId": "turn"}
    assert client.event() == notice
    sent = sent_frames(client)
    assert json.loads(sent[0][1])["params"]["input"] == "x" * 70000
    assert sent[1] == (10, b"ping")


def test_explicit_rpc_error_is_a_refusal():
    client = wire(frame(json.dumps({"id": 1, "error": {"message": "no turn running"}}).encode()))
    with pytest.raises(daemon.Refused, match="no turn running"):
        client.call("turn/interrupt", {})
