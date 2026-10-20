"""Account limit reads refuse malformed evidence and preserve partial appends."""

import json
from datetime import datetime, timezone

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
reads = script("dashboard_reads")


def event(at=1000, used: object = 25, minutes: object = 10080, reset: object = 2000):
    return {"type": "event_msg", "timestamp": datetime.fromtimestamp(at, timezone.utc).isoformat(),
            "payload": {"type": "token_count", "rate_limits": {
                "limit_id": "codex", "primary": {"used_percent": 99, "window_minutes": 300},
                "secondary": {"used_percent": used, "window_minutes": minutes, "resets_at": reset}}}}


def test_account_evidence_refuses_invalid_windows():
    assert (known := reads.codex_window(event())) is not None and known.used_pct == 25
    for kwargs in ({"used": True}, {"used": -1}, {"used": float("nan")},
                   {"minutes": 300}, {"reset": None}, {"reset": 500}):
        raw = event()
        raw["payload"]["rate_limits"]["secondary"].update(
            {"used_percent" if k == "used" else "window_minutes" if k == "minutes"
             else "resets_at": v for k, v in kwargs.items()})
        assert reads.codex_window(raw) is None
    assert reads.codex_window({"type": "event_msg", "payload": {"type": "token_count", "info": {
        "total_token_usage": {"total_tokens": 999999}}}}) is None


def test_partial_append_expiry_and_replacement(tmp_path):
    directory = tmp_path / ".codex" / "sessions"
    directory.mkdir(parents=True)
    path = directory / "rollout-one.jsonl"
    path.write_text(json.dumps(event()) + "\n")
    reader = reads.CodexLimits(tmp_path)
    assert (known := reader.read(1500)) is not None and known.used_pct == 25
    text = json.dumps(event(at=1600, used=40, reset=3000))
    with path.open("a") as stream:
        stream.write(text[:20])
    assert (known := reader.read(1700)) is not None and known.used_pct == 25
    with path.open("a") as stream:
        stream.write(text[20:] + "\n")
    assert (known := reader.read(1700)) is not None and known.used_pct == 40
    assert reader.read(3000) is None
    replacement = directory / "replacement"
    replacement.write_text(json.dumps(event(at=1700, used=10, reset=4000)) + "\n")
    replacement.replace(path)
    assert (known := reader.read(1800)) is not None and known.used_pct == 10
    path.write_text("")
    assert reader.read(1800) is None
