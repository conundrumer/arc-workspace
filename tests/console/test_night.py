"""Overnight mode: the readings the pacer rates, the admission pass under
LOCK, the quota death it reads, and the usage files."""

import json
import os
import time
import types

import pytest

from .conftest import (
    backlog_solver,
    finalize_launch,
    item,
    lock_free,
    worker,
)

WEEK = 7 * 86400
FIVE = 5 * 3600
AT = 1_700_000_000.0


def clock_at(srv, monkeypatch, at=AT):
    monkeypatch.setattr(srv, "now", lambda: at)
    return at


def set_usage(srv, monkeypatch, wk_pct=0.0, wk_elapsed=0.0, five_pct=0.0,
              five_left=FIVE, at=AT, five_reset=True, fbl=None):
    """Rate-limit rows placing each window where the test wants it. `fbl` is
    the Fable window as (pct, elapsed), absent by default."""
    five = {"label": "5h", "pct": five_pct, "window": FIVE,
            "reset": at + five_left if five_reset else None}
    rows = [{"label": "wk", "pct": wk_pct, "window": WEEK,
             "reset": at + WEEK * (1 - wk_elapsed / 100)}, five]
    if fbl:
        rows.append({"label": "fbl", "pct": fbl[0], "window": WEEK,
                     "reset": at + WEEK * (1 - fbl[1] / 100)})
    monkeypatch.setattr(srv, "USAGE", rows)


def night_on(srv, **dials):
    cfg = srv.night()
    cfg.update(on=True, since=0, **dials)
    return cfg


def readings(srv, label, points, reset=None, at=AT):
    """Feed the pacer a window's readings: (seconds before `at`, pct) pairs,
    oldest first, the way the usage loop notes them."""
    for ago, pct in points:
        srv.note_usage([{"label": label, "pct": pct, "reset": reset}], at=at - ago)


def running(srv, n):
    """`n` workers mid-turn, on items of their own."""
    for i in range(n):
        worker(srv, item(srv, f"run{i}", srv.RUNNING), state="running")


def test_the_rate_is_the_slope_of_a_windows_readings(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    readings(srv, "5h", [(900, 50), (600, 55), (300, 60), (0, 65)])
    assert srv.rate("5h") == pytest.approx(60)      # 5 points per 5 minutes
    readings(srv, "wk", [(60, 10), (0, 11)])
    assert srv.rate("wk") is None                    # too short a span to read


def test_a_window_that_rolled_over_starts_its_history_again(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    readings(srv, "5h", [(900, 80), (600, 90)], reset=AT + 600)
    readings(srv, "5h", [(300, 2)], reset=AT + FIVE)   # the value fell: a new window
    assert srv.rate("5h") is None
    readings(srv, "5h", [(0, 7)], reset=AT + FIVE + 1)  # a one-second wobble of the reset
    assert srv.rate("5h") == pytest.approx(60)
    readings(srv, "5h", [(-60, 8)], reset=AT + FIVE + 3600)   # the reset moved
    assert srv.rate("5h") is None


def eta_held(w):
    """Whether the panel paints the +1 column red: the window runs out before
    the time the gate holds against."""
    return isinstance(w["runs_out_more"], float) \
        and w["runs_out_more"] < w["limit"]


def test_the_windows_eta_agrees_with_the_spend_hold(srv, monkeypatch):
    """The panel reads when a window runs out; the gate reads what is left
    against what the fleet spends. One more item running the window out
    before its limit is the spend hold."""
    clock_at(srv, monkeypatch)
    srv.night()["pace"] = "exhaust"
    for hours in (2, 4):
        for pct in (0, 50, 80, 90, 95, 99, 100):
            set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
                      five_pct=pct, five_left=hours * 3600)
            gate = srv.pacer()
            five = next(w for w in gate["windows"] if w["label"] == "5h")
            assert eta_held(five) is (gate["hold"] == "5h over budget")
    # a fleet climbing under the pace, with the reset four hours away
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=6,
              five_left=4 * 3600)
    readings(srv, "5h", [(900, 1), (0, 6)], reset=AT + 4 * 3600)
    gate = srv.pacer()
    five = next(w for w in gate["windows"] if w["label"] == "5h")
    assert gate["open"] is True
    assert eta_held(five) is False


def test_a_gap_in_the_readings_writes_no_share(srv, monkeypatch):
    """A slope across a stretch with no readings is shaped by the gap, not
    by the fleet, so it must not set what later admissions are measured by."""
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=9)
    running(srv, 1)
    readings(srv, "5h", [(900, 5), (780, 5), (660, 5), (540, 5), (0, 9)],
             reset=AT + FIVE)
    srv.pacer()
    assert "5h" not in srv.night().get("share", {})
    srv.HISTORY = {}
    readings(srv, "5h", [(900, 5), (600, 6), (300, 7), (0, 8)], reset=AT + FIVE)
    srv.pacer()
    assert srv.night()["share"]["5h"] == pytest.approx(12)


def test_a_garbled_samples_file_seeds_nothing_and_raises_nothing(srv):
    srv.SAMPLE_FILE.write_bytes(b'{"t": 1, "windows": {}}\n\xff\xfe{"t":')
    srv.seed_history()
    assert srv.rate("5h") is None


def test_pacer_holds_without_a_weekly_reading(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    monkeypatch.setattr(srv, "USAGE", [])
    gate = srv.pacer()
    assert gate["open"] is False
    assert gate["why"] == "no wk reading"


def test_a_pass_reads_the_queue_and_git_with_the_lock_down(srv, monkeypatch):
    """A pass runs every 30 seconds, and every worker reader thread and page
    poll waits on LOCK, so the subprocesses a pass reads through run outside
    it."""
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    free = []
    picks, ages = srv.queue_pick, srv.solver_ages
    monkeypatch.setattr(srv, "queue_pick", lambda n, order, held=(): (
        free.append(("queue", lock_free(srv))), picks(n, order, held))[1])
    monkeypatch.setattr(srv, "solver_ages", lambda: (
        free.append(("git", lock_free(srv))), ages())[1])
    night_on(srv, source="both")
    assert srv.night_tick()["admitted"] == ["aaa", "t00"]
    assert sorted(free) == [("git", True), ("queue", True)]


@pytest.mark.parametrize("flag", ["SHUTTING_DOWN", "RELOADING"])
def test_a_stop_during_the_reads_calls_the_admission_off(srv, monkeypatch, flag):
    """A pass reads the queue script and git with LOCK down, and a shutdown or
    a reload arrives in that stretch. Both call the admission off, the way the
    pass reads them before the reads: a session started after a shutdown
    outlives the console, and an item admitted into a reload holds the
    quiesce open."""
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    picks = srv.queue_pick

    def picking(n, order, held=()):
        setattr(srv, flag, True)
        return picks(n, order, held)

    monkeypatch.setattr(srv, "queue_pick", picking)
    night_on(srv, source="both")
    assert srv.night_tick()["admitted"] == []
    assert srv.STATE["items"] == []


def test_quota_death_is_read_from_the_status_then_the_wording(srv):
    assert srv.quota_death(429, "api_error", "") is True
    assert srv.quota_death("429", None, "") is True
    assert srv.quota_death(None, "rate_limit", "") is True
    assert srv.quota_death(None, None, "Claude AI usage limit reached") is True
    assert srv.quota_death(None, "api_error", "") is False
    assert srv.quota_death(500, "api_error", "overloaded") is False
    assert srv.quota_death(None, None, "souffle exceeded the 5s CPU limit") is False


API_USAGE = {"fetched_at": 1000, "data": {"limits": [
    {"kind": "session", "percent": 40, "resets_at": "2026-09-04T12:00:00+00:00"},
    {"kind": "weekly_all", "percent": 12, "resets_at": "2026-09-09T12:00:00+00:00"},
    {"kind": "weekly_scoped", "percent": 3, "scope": {"model": {"display_name": "Fable"}},
     "resets_at": "2026-09-09T12:00:00+00:00"}]}}
STATUS_USAGE = {"five_hour": {"used_pct": 55, "resets_at_epoch": 1788540000},
                "seven_day": {"used_pct": 14, "resets_at_epoch": 1789106400},
                "fable_weekly": {"used_pct": 4, "resets_at_epoch": 1789106399}}


def usage_files(tmp_path, api=API_USAGE, status=STATUS_USAGE, status_at=2000):
    a, s = tmp_path / "usage-api.json", tmp_path / "usage.json"
    if api is not None:
        a.write_text(json.dumps(api))
    if status is not None:
        s.write_text(json.dumps(status))
        os.utime(s, (status_at, status_at))
    return a, s


def test_the_fresher_usage_file_is_the_reading(srv, tmp_path):
    a, s = usage_files(tmp_path)
    rows = srv.read_usage(api=a, status=s)
    assert [(r["label"], r["pct"], r["window"]) for r in rows] == \
        [("5h", 55, 5 * 3600), ("wk", 14, 7 * 86400), ("fbl", 4, 7 * 86400)]
    assert rows[0]["reset"] == 1788540000
    a, s = usage_files(tmp_path, status_at=500)
    rows = srv.read_usage(api=a, status=s)
    assert [(r["label"], r["pct"]) for r in rows] == [("5h", 40), ("wk", 12), ("fbl", 3)]


def test_a_usage_file_that_is_missing_or_broken_yields_to_the_other(srv, tmp_path):
    a, s = usage_files(tmp_path, status=None)
    assert [r["label"] for r in srv.read_usage(api=a, status=s)] == ["5h", "wk", "fbl"]
    a, s = usage_files(tmp_path, api=None)
    assert [r["pct"] for r in srv.read_usage(api=a, status=s)] == [55, 14, 4]
    a.write_text("{")
    assert [r["pct"] for r in srv.read_usage(api=a, status=s)] == [55, 14, 4]
    s.unlink()
    assert srv.read_usage(api=a, status=s) == []


def test_a_refused_usage_fetch_backs_off_before_asking_again(srv, tmp_path, monkeypatch):
    """The usage endpoint rate-limits a token that asks too often, and keeps
    refusing while the asking goes on. A refusal earns a pause that doubles
    up to a cap; a reading clears it."""
    calls = []
    codes = iter([1, 1, 0, 0] + [1] * 8)

    def run(cmd, **kw):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=next(codes), stdout="", stderr="HTTP 429")
    monkeypatch.setattr(srv.subprocess, "run", run)
    monkeypatch.setattr(srv, "USAGE_FETCH", tmp_path / "fetch.sh")
    (tmp_path / "fetch.sh").write_text("")
    srv.quota.fetch(force=True)
    assert len(calls) == 1
    assert srv.quota.NEXT_TRY - time.time() == pytest.approx(2 * srv.USAGE_POLL, abs=1)
    srv.quota.fetch(force=True)
    assert len(calls) == 1, "no ask inside the pause"
    srv.quota.NEXT_TRY = 0
    srv.quota.fetch(force=True)
    assert len(calls) == 2
    assert srv.quota.NEXT_TRY - time.time() == pytest.approx(4 * srv.USAGE_POLL, abs=1)
    srv.quota.NEXT_TRY = 0
    srv.quota.fetch(force=True)
    srv.quota.fetch(force=True)
    assert len(calls) == 4, "a reading clears the pause"
    for _ in range(8):
        srv.quota.NEXT_TRY = 0
        srv.quota.fetch(force=True)
    assert srv.quota.NEXT_TRY - time.time() == pytest.approx(srv.quota.BACKOFF_MAX, abs=1)


def test_a_stale_usage_reading_holds_admissions(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    srv.USAGE_AT = AT - 60
    assert srv.pacer()["open"] is True
    srv.USAGE_AT = AT - 15 * 60
    gate = srv.pacer()
    assert gate["open"] is False
    assert gate["hold"] == "usage reading stale"
