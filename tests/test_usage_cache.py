"""The reading of the usage cache refuses a cache it cannot read, and a
stale one, and gives a `null` window as absent and a window past its reset
as unused."""

import json
from pathlib import Path

import pytest

from engine import checkout
from tests.conftest import script

NOW = 1_800_000_000.0


def reading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cache: object):
    """The reading at `NOW` of the cache `cache` written as JSON, with
    the fetch a script that does not exist, and its `undecided` lines."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(checkout.scripts()))
    usage = script("usage_limit")
    monkeypatch.setattr(usage, "FETCH", tmp_path / "absent.sh")
    (tmp_path / "usage-api.json").write_text(json.dumps(cache))
    undecided: list[str] = []
    return usage, usage.read(NOW, undecided), undecided


def stamp(seconds: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def test_a_full_window_gives_the_limit_in_force_and_a_reset_one_gives_it_lifted(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = {"five_hour": {"utilization": 100.0, "resets_at": stamp(NOW + 60)},
            "seven_day": None,
            "limits": [{"percent": 3, "resets_at": stamp(NOW + 3600),
                        "scope": {"model": {"display_name": "Fable"}}}]}
    usage, r, undecided = reading(tmp_path, monkeypatch, {"fetched_at": NOW - 10, "data": data})
    assert r.limit is usage.Limit.IN_FORCE and not undecided
    assert set(r.usage.windows) == {"five_hour", "fable_weekly"}
    data["five_hour"]["resets_at"] = stamp(NOW - 60)
    usage, r, _ = reading(tmp_path, monkeypatch, {"fetched_at": NOW - 10, "data": data})
    assert r.limit is usage.Limit.LIFTED and r.fetched == NOW - 10
    assert r.usage.windows["five_hour"].used_pct == 0


@pytest.mark.parametrize("cache", [
    {"fetched_at": NOW - 10, "data": {"five_hour": {"utilization": "x", "resets_at": stamp(NOW)}}},
    {"fetched_at": NOW - 10, "data": {"five_hour": {"utilization": 5, "resets_at": "2026-10-18"}}},
    {"fetched_at": "x", "data": {}},
    {"fetched_at": NOW - 10, "data": {"five_hour": None, "seven_day": None}},
])
def test_a_cache_that_does_not_read_leaves_the_limit_unknown(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cache: object) -> None:
    usage, r, undecided = reading(tmp_path, monkeypatch, cache)
    assert r.limit is usage.Limit.UNKNOWN and undecided


def test_a_stale_cache_leaves_the_limit_unknown_and_gives_no_window(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = {"five_hour": {"utilization": 1.0, "resets_at": stamp(NOW + 60)}}
    usage, r, _ = reading(tmp_path, monkeypatch,
                          {"fetched_at": NOW - 10 * 60, "data": data})
    assert r.limit is usage.Limit.UNKNOWN and not r.usage.windows
