"""Overnight mode: the pace it holds, what it admits, the quota deaths it
resumes, and the usage it reads."""

import json
import os
import threading
import time
import types

import pytest

from .conftest import (
    backlog_solver,
    finalize_item,
    finalize_launch,
    item,
    lock_free,
    tagged,
    worker,
)

# ---------- overnight mode ----------

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


def opus_chain():
    return [{"name": "create", "backend": "claude", "model": "claude-opus-5"},
            {"name": "refine", "backend": "claude", "model": "claude-opus-5"}]


def night_on(srv, **dials):
    cfg = srv.night()
    cfg.update(on=True, since=0, **dials)
    return cfg


def test_night_config_starts_at_the_defaults(srv):
    cfg = srv.night()
    assert cfg["on"] is False
    assert (cfg["target"], cfg["reserve"], cfg["floor"]) == (6, 10, 5)
    assert cfg["catchup"] is True
    assert cfg["pace"] == "share"


def test_pacer_admits_below_the_pace_line(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=30, wk_elapsed=50)
    gate = srv.pacer()
    assert gate["open"] is True
    assert gate["line"] == 40  # elapsed 50 − reserve 10
    srv.night()["reserve"] = 25
    assert srv.pacer()["open"] is False


def test_pacer_holds_once_the_week_reaches_its_pace(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=45, wk_elapsed=50)
    gate = srv.pacer()
    assert gate["open"] is False
    assert gate["why"] == "wk pace"


def test_the_fable_week_paces_admissions_when_a_night_stage_runs_fable(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, fbl=(45, 50))
    assert srv.pacer()["open"] is True     # the night stops before finalize
    srv.act_auto({"finalize": True})
    gate = srv.pacer()
    assert gate["open"] is False
    assert gate["why"] == "fbl pace" and gate["fbl"] == 45
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, fbl=(30, 50))
    assert srv.pacer()["open"] is True


def test_the_floor_keeps_the_start_of_a_week_spendable(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=3, wk_elapsed=1)
    gate = srv.pacer()
    assert gate["open"] is True
    assert gate["line"] == 5
    set_usage(srv, monkeypatch, wk_pct=6, wk_elapsed=1)
    assert srv.pacer()["open"] is False


def test_catchup_off_caps_spending_at_strict_pace(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    cfg = night_on(srv, catchup=False, wk_start=20, wk_start_at=AT - 3600)
    set_usage(srv, monkeypatch, wk_pct=22, wk_elapsed=60)
    gate = srv.pacer()
    assert gate["open"] is False           # +2 points in an hour's worth of week
    assert gate["why"] == "wk strict"
    cfg["catchup"] = True
    assert srv.pacer()["open"] is True     # the slack is there to be spent


def test_strict_pace_restarts_when_the_weekly_window_rolls(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    cfg = night_on(srv, catchup=False, wk_start=80, wk_start_at=AT - 3600)
    set_usage(srv, monkeypatch, wk_pct=2, wk_elapsed=1)
    assert srv.pacer()["open"] is True
    assert cfg["wk_start"] == 2


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


def test_the_history_is_seeded_from_the_samples_file(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    rows = [{"t": int(AT - ago), "windows": {"5h": {"pct": pct, "end": int(AT + FIVE)},
                                             "wk": {"pct": 20, "end": int(AT + WEEK)}}}
            for ago, pct in [(600, 30), (300, 35), (0, 40)]]
    srv.SAMPLE_FILE.write_text("".join(json.dumps(r) + "\n" for r in rows))
    srv.seed_history()
    assert srv.rate("5h") == pytest.approx(60)
    assert srv.rate("wk") == pytest.approx(0)


def test_the_five_hour_rule_holds_a_fleet_over_the_windows_budget(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
              five_pct=80, five_left=2 * 3600)
    readings(srv, "5h", [(900, 60), (0, 80)], reset=AT + 2 * 3600)
    gate = srv.pacer()
    assert gate["open"] is False
    assert (gate["hold"], gate["why"]) == ("5h over budget", "5h")
    five = next(w for w in gate["windows"] if w["label"] == "5h")
    assert (five["rate"], five["budget"]) == (pytest.approx(80), pytest.approx(10))


def test_the_last_hour_before_a_reset_opens_no_wider(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
              five_pct=95, five_left=1800)
    gate = srv.pacer()
    assert gate["open"] is False           # 5 points left, one item spends 6 an hour
    assert gate["hold"] == "5h over budget"
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
              five_pct=90, five_left=1800)
    assert srv.pacer()["open"] is True


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


def test_a_fleet_under_the_pace_admits_with_the_reset_hours_out(srv, monkeypatch):
    """What is left must cover the fleet to the reset, plus one item's hour.
    With 94 points left and four hours to go, the fleet has 88 of them to
    climb through."""
    clock_at(srv, monkeypatch)
    srv.night()["pace"] = "exhaust"
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=6,
              five_left=4 * 3600)
    readings(srv, "5h", [(900, 1), (0, 6)], reset=AT + 4 * 3600)
    assert srv.pacer()["open"] is True          # 20 an hour takes 80 of them
    srv.HISTORY = {}
    readings(srv, "5h", [(900, 0), (0, 6)], reset=AT + 4 * 3600)
    assert srv.pacer()["hold"] == "5h over budget"   # 24 an hour takes 96


def test_a_five_hour_window_with_no_reset_is_a_full_window_away(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=0,
              five_reset=False)
    gate = srv.pacer()
    assert gate["open"] is True
    five = next(w for w in gate["windows"] if w["label"] == "5h")
    assert five["budget"] == pytest.approx(20)


def test_the_running_fleet_counts_at_its_share_before_the_slope_shows(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
              five_pct=76, five_left=2 * 3600)       # 24 points left, two hours
    assert srv.pacer()["open"] is True             # one item's hour fits
    running(srv, 2)
    gate = srv.pacer()
    assert gate["open"] is False                   # 12 an hour for two does not
    five = next(w for w in gate["windows"] if w["label"] == "5h")
    assert (five["rate"], five["share"]) == (pytest.approx(12), pytest.approx(6))


def test_the_observed_share_is_remembered_in_the_config(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=40)
    running(srv, 2)
    readings(srv, "5h", [(900, 30), (600, 34), (300, 38), (0, 42)],
             reset=AT + FIVE)                                  # 48 an hour, over two
    srv.pacer()
    assert srv.night()["share"]["5h"] == pytest.approx(24)
    srv.PROCS.clear()
    running(srv, 1)
    srv.HISTORY = {}
    five = next(w for w in srv.pacer()["windows"] if w["label"] == "5h")
    assert five["share"] == pytest.approx(24)


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


def test_an_idle_fleet_admits_by_the_prior_at_most(srv, monkeypatch):
    """A stored share above the window's budget is re-measured only by a
    running item. With nothing spending, the admission test uses the prior
    when that is smaller, and the one item admitted measures it again."""
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
              five_pct=9, five_left=4 * 3600)              # about 23 an hour to spend
    srv.night()["share"] = {"5h": 30.0}
    gate = srv.pacer()
    assert gate["open"] is True
    five = next(w for w in gate["windows"] if w["label"] == "5h")
    assert five["share"] == pytest.approx(6)
    running(srv, 1)
    gate = srv.pacer()
    assert gate["open"] is False
    five = next(w for w in gate["windows"] if w["label"] == "5h")
    assert (five["rate"], five["share"]) == (pytest.approx(30), pytest.approx(30))


def test_a_share_is_written_only_off_a_full_span_of_readings(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=40)
    running(srv, 2)
    readings(srv, "5h", [(300, 30), (0, 40)], reset=AT + FIVE)   # five minutes only
    srv.pacer()
    assert "5h" not in srv.night().get("share", {})


def test_seeded_readings_do_not_count_toward_the_share(srv, monkeypatch):
    """The file does not say how many were spending when a row was written,
    so the mean that turns a slope into one item's share skips those rows."""
    clock_at(srv, monkeypatch)
    rows = [{"t": int(AT - ago), "windows": {"5h": {"pct": pct, "end": int(AT + FIVE)}}}
            for ago, pct in [(900, 20), (600, 25), (300, 30)]]
    srv.SAMPLE_FILE.write_text("".join(json.dumps(r) + "\n" for r in rows))
    srv.seed_history()
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=35)
    running(srv, 4)
    readings(srv, "5h", [(0, 35)], reset=AT + FIVE)
    srv.pacer()
    assert srv.night()["share"]["5h"] == pytest.approx(15)     # 60 an hour over four


def test_a_garbled_samples_file_seeds_nothing_and_raises_nothing(srv):
    srv.SAMPLE_FILE.write_bytes(b'{"t": 1, "windows": {}}\n\xff\xfe{"t":')
    srv.seed_history()
    assert srv.rate("5h") is None


def test_readings_that_stopped_arriving_go_stale(srv, monkeypatch):
    at = clock_at(srv, monkeypatch)
    readings(srv, "5h", [(900, 50), (0, 65)], reset=AT + FIVE)
    assert srv.rate("5h") == pytest.approx(60)
    clock_at(srv, monkeypatch, at + 20 * 60)
    assert srv.rate("5h") is None


def test_a_worker_counts_as_spending_from_the_moment_its_turn_is_sent(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    worker(srv, item(srv, "s", srv.RUNNING), state="sending")
    worker(srv, item(srv, "p", srv.RUNNING), state="spawning")
    worker(srv, item(srv, "i", srv.NEEDS_REVIEW), state="idle")
    assert srv.spending() == 2


def test_a_pace_line_hold_still_reads_every_window(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=45, wk_elapsed=50)
    gate = srv.pacer()
    assert gate["open"] is False
    assert {w["label"] for w in gate["windows"]} == {"5h", "wk"}


def test_a_spend_hold_is_logged_once_while_its_numbers_move(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50,
              five_pct=80, five_left=2 * 3600)
    night_on(srv)
    readings(srv, "5h", [(900, 60), (600, 67), (300, 73), (0, 80)],
             reset=AT + 2 * 3600)
    srv.night_tick()
    readings(srv, "5h", [(-60, 81)], reset=AT + 2 * 3600)
    srv.night_tick()
    texts = [e["text"] for e in srv.night()["log"]]
    assert texts == ["hold · 5h over budget"]


def test_exhaust_skips_the_pace_lines(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=45, wk_elapsed=50, fbl=(60, 50))
    srv.act_auto({"finalize": True})
    assert srv.pacer()["open"] is False
    srv.night()["pace"] = "exhaust"
    gate = srv.pacer()
    assert gate["open"] is True
    assert gate["line"] is None


def test_the_wall_holds_a_weekly_window_an_hour_out(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    srv.night()["pace"] = "exhaust"
    set_usage(srv, monkeypatch, wk_pct=99, wk_elapsed=50)
    gate = srv.pacer()
    assert gate["open"] is False           # one point left, an item spends 1.4 an hour
    assert (gate["hold"], gate["why"]) == ("wk over budget", "wk")
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, fbl=(97, 50))
    assert srv.pacer(models=[srv.MODEL_IDS["opus"]])["open"] is True
    assert srv.pacer(models=[srv.MODEL_IDS["fable"]])["hold"] == "fbl over budget"


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


def test_the_admitter_fills_to_target_and_stops(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv, target=2)
    assert srv.night_tick()["admitted"] == ["t00"]
    assert srv.night_tick()["admitted"] == ["t01"]
    assert srv.night_tick()["admitted"] == []
    assert [it["id"] for it in srv.STATE["items"]] == ["t00", "t01"]


def test_the_admitter_respects_the_gate(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=60, wk_elapsed=50)
    night_on(srv)
    out = srv.night_tick()
    assert out["admitted"] == [] and "wk at pace" in out["held"]
    assert srv.STATE["items"] == []
    assert "hold · " in srv.night()["log"][-1]["text"]


def test_a_held_pass_logs_its_reason_once(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=60, wk_elapsed=50)
    night_on(srv)
    srv.night_tick()
    srv.night_tick()
    assert len(srv.night()["log"]) == 1


def test_the_mode_off_admits_nothing(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    assert srv.night_tick() == {"resumed": [], "admitted": [], "held": None}
    assert srv.STATE["items"] == []


def test_a_night_admission_looks_like_a_wave_item(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv, target=2)
    srv.night_tick()
    srv.night_tick()
    first, second = srv.STATE["items"]
    assert first["state"] == srv.QUEUED
    assert first["auto_advance"] is True
    assert first["auto_stop"] == "finalize"
    assert first["night"] is True
    assert first["chain"] == srv.default_chain()
    # one wave, one appendix: the night's stages share the cached prefix
    assert (first["wave"], first["append"]) == (second["wave"], second["append"])
    assert srv.STATE["wave"] == 1


def test_a_night_admission_clears_the_committed_items(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    item(srv, "old", srv.COMMITTED)
    night_on(srv, target=1)
    srv.night_tick()
    assert [it["id"] for it in srv.STATE["items"]] == ["t00"]


def test_a_queue_failure_leaves_the_night_running(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv)

    def boom(n, order, held=()):
        raise srv.Reject("queue.sh failed: no bun")
    monkeypatch.setattr(srv, "queue_pick", boom)
    assert srv.night_tick()["admitted"] == []
    assert "admission deferred" in srv.night()["log"][-1]["text"]
    assert srv.STATE["items"] == []


def night_item(srv, item_id="a", **kw):
    """An item admitted by the mode: the whole chain but the last stage."""
    chain = srv.default_chain()
    kw.setdefault("night", True)
    return item(srv, item_id, srv.RUNNING, chain=chain, auto_advance=True,
                auto_stop=chain[-1]["name"],
                sessions={"create": "cs", "refine": "rs", "finalize": None},
                phase="refine", landed=["create"], **kw)


def test_auto_advance_runs_up_to_the_stage_it_stops_before(srv):
    it = night_item(srv)
    assert srv.auto_advances(it, "create") is True
    assert srv.auto_advances(it, "refine") is False
    assert srv.auto_advances(it, "finalize") is False


def test_the_stage_before_the_last_lands_for_review_with_its_report(srv, monkeypatch):
    launched = []
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: launched.append(a))
    it = night_item(srv)
    srv.finish_turn(it, {"result": "what refine found"}, None, time.time(),
                    "refine", True)
    assert it["state"] == srv.NEEDS_REVIEW
    assert it["phase"] == "refine"
    assert it["reports"]["refine"] == "what refine found"
    assert srv.report_path("a", "refine").read_text() == "what refine found"
    assert launched == []
    assert not it.get("handoff_pending")


def test_an_earlier_stage_still_hands_off_by_itself(srv, monkeypatch):
    landed = threading.Event()
    monkeypatch.setattr(srv, "advance_stage", lambda it: landed.set())
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    chain = srv.default_chain()
    it = item(srv, "a", srv.RUNNING, chain=chain, auto_advance=True,
              auto_stop="finalize", phase="create", landed=[],
              sessions={"create": "cs", "refine": None, "finalize": None})
    worker(srv, it, phase="create", state="running", turn_seq=4)
    srv.finish_turn(it, {"result": tagged("the report")}, None, time.time(), "create", True)
    srv.finish_turn(it, {"result": "## Callouts\n\nnone"}, None,
                    time.time(), "create", False)
    assert landed.wait(1)


def test_auto_advance_into_finalize_marks_the_pass(srv, monkeypatch):
    monkeypatch.setattr(srv, "advance_stage", lambda it: it.update(phase="finalize"))
    it = item(srv, "a", srv.RUNNING, chain=srv.default_chain(), phase="refine",
              handoff_pending=True)
    w = worker(srv, it, phase="refine", state="idle", turn_seq=3)
    srv.DEFERRED.put_nowait(("handoff", "a", "refine", w["turn_seq"]))
    srv.ensure_drain()
    deadline = time.time() + 1
    while it.get("handoff_pending") and time.time() < deadline:
        time.sleep(0.01)
    assert it["auto_finalize"] is True


def test_an_auto_launched_finalize_lands_into_a_callout_turn(srv, monkeypatch):
    monkeypatch.setattr(srv, "launch", lambda *a, **kw: None)
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = finalize_item(srv, state=srv.RUNNING, auto_finalize=True)
    w = srv.PROCS[("a", "finalize")]
    w["state"], w["turn_seq"] = "running", 4
    srv.finish_turn(it, {"result": "the solver holds up"}, None,
                    time.time(), "finalize", False)
    assert "auto_finalize" not in it
    assert it["reports"]["finalize"] == "the solver holds up"
    assert it["callout_wait"] == "finalize"
    assert srv.DEFERRED.get_nowait() == ("callout", "a", "finalize", 4)
    # the callout landing files the section and waits for the user
    srv.finish_turn(it, {"result": "<callouts>\n1. [P2] a call\n</callouts>"}, None,
                    time.time(), "finalize", False)
    assert it["reports"]["finalize"] == "the solver holds up\n\n## Callouts\n\n1. [P2] a call"
    assert it["callouts"] == ["[P2] a call"]
    assert "callout_wait" not in it and "handoff_pending" not in it
    assert it["state"] == srv.NEEDS_REVIEW and it["updated"]
    # a later landing on the same session asks nothing more
    srv.finish_turn(it, {"result": "promoted"}, None, time.time(), "finalize", False)
    assert "callout_wait" not in it and it["state"] == srv.NEEDS_REVIEW


def test_an_auto_launched_finalize_with_callouts_inline_skips_the_turn(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = finalize_item(srv, state=srv.RUNNING, auto_finalize=True)
    srv.PROCS[("a", "finalize")]["state"] = "running"
    srv.finish_turn(it, {"result": "holds up\n\n<callouts>\n1. [P1] a call\n</callouts>"},
                    None, time.time(), "finalize", False)
    assert it["reports"]["finalize"] == "holds up\n\n## Callouts\n\n1. [P1] a call"
    assert it["callouts"] == ["[P1] a call"]
    assert "callout_wait" not in it and it["state"] == srv.NEEDS_REVIEW
    assert srv.DEFERRED.empty()


def test_an_auto_launched_finalize_waits_out_its_tasks(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = finalize_item(srv, state=srv.RUNNING, auto_finalize=True)
    w = srv.PROCS[("a", "finalize")]
    w["state"], w["bg"] = "running", {"x": "survey"}
    srv.finish_turn(it, {"result": "survey dispatched"}, None, time.time(), "finalize", False)
    assert it["auto_finalize"] is True and "callout_wait" not in it
    assert it["state"] == srv.NEEDS_REVIEW and srv.DEFERRED.empty()


def test_a_finalize_the_user_launched_lands_as_before(srv, monkeypatch):
    monkeypatch.setattr(srv, "ensure_drain", lambda: None)
    it = finalize_item(srv, state=srv.RUNNING)
    srv.PROCS[("a", "finalize")]["state"] = "running"
    srv.finish_turn(it, {"result": "the solver holds up"}, None,
                    time.time(), "finalize", False)
    assert it["reports"] == {} and "callout_wait" not in it
    assert it["state"] == srv.NEEDS_REVIEW and srv.DEFERRED.empty()


def test_quota_death_is_read_from_the_status_then_the_wording(srv):
    assert srv.quota_death(429, "api_error", "") is True
    assert srv.quota_death("429", None, "") is True
    assert srv.quota_death(None, "rate_limit", "") is True
    assert srv.quota_death(None, None, "Claude AI usage limit reached") is True
    assert srv.quota_death(None, "api_error", "") is False
    assert srv.quota_death(500, "api_error", "overloaded") is False
    assert srv.quota_death(None, None, "souffle exceeded the 5s CPU limit") is False


def quota_result(srv, it, phase="refine", handoff=False):
    w = worker(srv, it, phase=phase, state="running")
    w["started"] = time.time()
    w["handoff"] = handoff
    srv.handle_event(w, {"type": "result", "terminal_reason": "api_error",
                         "api_error_status": 429,
                         "result": "Claude AI usage limit reached"}, None)
    return w


def test_a_quota_death_schedules_a_resume_after_the_reset(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, five_pct=100,
              five_left=1200)
    monkeypatch.setattr(srv.random, "uniform", lambda lo, hi: 60)
    night_on(srv)
    it = item(srv, "a", srv.RUNNING)
    quota_result(srv, it, handoff=True)
    assert it["state"] == srv.NEEDS_REVIEW
    assert it["resume_at"] == AT + 1200 + 60
    assert it["resume_phase"] == "refine"
    assert it["resume_handoff"] is True
    assert it["quota_retry"] == "refine"
    assert "usage limit" in it["feed"][-2]["text"]


def test_a_weekly_limit_death_resumes_after_the_weekly_reset(srv, monkeypatch):
    """The 5h window resets first, but the weekly limit is what ran out."""
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=100, wk_elapsed=99, five_pct=40,
              five_left=1200)
    monkeypatch.setattr(srv.random, "uniform", lambda lo, hi: 60)
    night_on(srv)
    it = item(srv, "a", srv.RUNNING)
    quota_result(srv, it)
    assert it["resume_at"] == AT + WEEK // 100 + 60


def test_a_full_fable_window_is_read_only_for_a_fable_stage(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, five_pct=100, five_left=1200, fbl=(100, 50))
    monkeypatch.setattr(srv.random, "uniform", lambda lo, hi: 60)
    night_on(srv)
    opus = item(srv, "a", srv.RUNNING, chain=opus_chain())
    quota_result(srv, opus)
    assert opus["resume_at"] == AT + 1200 + 60
    fable = item(srv, "b", srv.RUNNING)      # the default chain's refine runs fable
    quota_result(srv, fable)
    assert fable["resume_at"] == AT + WEEK // 2 + 60


def test_a_death_with_no_window_reading_full_waits_on_the_5h_reset(srv, monkeypatch):
    """The usage cache lags the API, so a death with every window under full
    is taken as the usual 5h one."""
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=97, wk_elapsed=50, five_pct=90,
              five_left=1200)
    monkeypatch.setattr(srv.random, "uniform", lambda lo, hi: 60)
    night_on(srv)
    it = item(srv, "a", srv.RUNNING)
    quota_result(srv, it)
    assert it["resume_at"] == AT + 1200 + 60


def test_a_quota_death_with_the_mode_off_just_lands(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, five_left=1200)
    it = item(srv, "a", srv.RUNNING)
    quota_result(srv, it)
    assert it["state"] == srv.NEEDS_REVIEW
    assert "resume_at" not in it


def test_a_quota_death_records_the_handoff_flag_whatever_the_mode(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, five_left=1200)
    it = item(srv, "a", srv.RUNNING)
    quota_result(srv, it, handoff=True)
    assert it["resume_phase"] == "refine"
    assert it["resume_handoff"] is True


def test_a_resume_by_hand_keeps_the_cut_turns_flag(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase, kw)))
    it = item(srv, "a", srv.NEEDS_REVIEW,
              resume_phase="refine", resume_handoff=True)
    assert srv.act_resume("a") == {"ok": True}
    assert sent == [(srv.RESUME_BRIEF + srv.RESUME_AGENTS_GONE + srv.RESUME_HANDOFF_NOTE,
                     "refine", {"trigger": "resume", "handoff": True, "admitted": True})]
    assert it["state"] == srv.COMMENTED
    assert "resume_phase" not in it and "resume_handoff" not in it


def test_a_resume_by_hand_needs_a_cut_turn(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    item(srv, "a", srv.NEEDS_REVIEW)
    assert "no cut turn" in srv.act_resume("a")["error"]


def test_a_second_quota_death_lands_for_review(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, five_left=1200)
    night_on(srv)
    it = item(srv, "a", srv.RUNNING, quota_retry="refine")
    quota_result(srv, it)
    assert "resume_at" not in it
    assert "second usage limit" in it["feed"][-1]["text"]


def test_a_turn_that_lands_clears_the_retry_and_the_cut(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    it = item(srv, "a", srv.RUNNING, quota_retry="refine",
              resume_phase="refine", resume_handoff=True)
    srv.finish_turn(it, {"result": "done"}, None, time.time(), "refine", False)
    assert "quota_retry" not in it
    assert "resume_phase" not in it and "resume_handoff" not in it


def test_a_turn_through_the_cut_stage_drops_the_scheduled_resume(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    it = item(srv, "a", srv.RUNNING, resume_at=AT + 600,
              resume_phase="refine", resume_handoff=True)
    srv.finish_turn(it, {"result": "done"}, None, time.time(), "refine", False)
    assert not any(k in it for k in ("resume_at", "resume_phase", "resume_handoff"))


def test_a_slash_turn_or_another_stage_leaves_the_scheduled_resume(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    it = item(srv, "a", srv.RUNNING, resume_at=AT + 600, resume_phase="refine",
              resume_handoff=True, sessions={"create": "cs", "refine": "rs"})
    srv.finish_turn(it, {"result": "done"}, None, time.time(), "create", False)
    worker(srv, it, phase="refine")["slash"] = True
    srv.finish_turn(it, {"result": "compacted"}, None, time.time(), "refine", False)
    assert it["resume_at"] == AT + 600 and it["resume_phase"] == "refine"


def test_a_worker_that_dies_of_quota_is_scheduled_too(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, five_left=600)
    monkeypatch.setattr(srv.random, "uniform", lambda lo, hi: 0)
    night_on(srv)
    it = item(srv, "a", srv.RUNNING)

    class Proc:
        stdout = iter([])
        returncode = 1

        def wait(self):
            return 1
    w = worker(srv, it, state="running")
    w["proc"] = Proc()
    w["started"] = time.time()
    (srv.LOG_DIR / "a.log").write_text("Claude AI usage limit reached|1700000000")
    srv.reader(w)
    assert it["resume_at"] == AT + 600


def test_a_scheduled_resume_holds_a_slot(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT + 600)
    assert srv.live_items() == [it]


def test_a_due_resume_relaunches_the_same_stage(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append((msg, phase, kw)))
    night_on(srv, target=1)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT - 1,
              resume_phase="refine", resume_handoff=True)
    out = srv.night_tick()
    assert out["resumed"] == ["a"]
    brief = srv.RESUME_BRIEF + srv.RESUME_AGENTS_GONE + srv.RESUME_HANDOFF_NOTE
    assert sent == [(brief, "refine",
                     {"trigger": "resume", "handoff": True, "admitted": True})]
    assert it["state"] == srv.COMMENTED
    assert "resume_at" not in it and "resume_phase" not in it
    assert it["feed"][-1] == {"kind": "you", "text": brief, "sess": "refine"}


def test_a_resume_into_the_live_process_has_it_message_its_agents(srv, monkeypatch):
    """A message reaches an agent only from the process that spawned it, so
    the brief says what to do with the agents the cut killed by whether the
    worker is still there."""
    clock_at(srv, monkeypatch)
    sent = []
    monkeypatch.setattr(srv, "launch",
                        lambda it, msg, phase, **kw: sent.append(msg))
    night_on(srv, target=1)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT - 1, resume_phase="refine")
    worker(srv, it, state="idle")
    srv.night_tick()
    assert sent == [srv.RESUME_BRIEF + srv.RESUME_AGENTS_LIVE]


def test_a_resume_that_is_not_due_waits(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    night_on(srv, target=1)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT + 60,
              resume_phase="refine")
    assert srv.night_tick()["resumed"] == []
    assert it["state"] == srv.NEEDS_REVIEW


def test_a_resume_without_a_session_lands_for_review(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    night_on(srv, target=1)
    it = item(srv, "a", srv.NEEDS_REVIEW, resume_at=AT - 1,
              resume_phase="create", sessions={"create": None, "refine": "rs"})
    assert srv.night_tick()["resumed"] == ["a"]
    assert it["state"] == srv.NEEDS_REVIEW
    assert "no session to resume" in it["feed"][-1]["text"]


def test_the_night_counts_what_landed_unreviewed(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    night_on(srv)
    srv.night()["since"] = AT - 10
    item(srv, "old", srv.NEEDS_REVIEW, landed_at=AT - 100)
    item(srv, "new", srv.NEEDS_REVIEW, landed_at=AT - 1)
    item(srv, "run", srv.RUNNING, landed_at=AT - 1)
    assert srv.night_landed() == 1


def test_the_mode_and_its_dials_survive_a_restart(srv):
    assert srv.act_night({"on": True, "target": 3, "catchup": False,
                          "pace": "exhaust"}) == {"ok": True}
    srv.STATE.clear()
    srv.STATE.update({"seq": 0, "wave": 0, "items": []})
    srv.load()
    cfg = srv.night()
    assert (cfg["on"], cfg["target"], cfg["pace"]) == (True, 3, "exhaust")
    assert cfg["catchup"] is False


def test_an_unknown_pace_is_refused(srv):
    assert "error" in srv.act_night({"pace": "fast"})
    assert srv.night()["pace"] == "share"


def test_the_dials_are_held_to_their_range(srv):
    srv.act_night({"target": 999, "reserve": -5})
    cfg = srv.night()
    assert (cfg["target"], cfg["reserve"]) == (40, 0)
    assert srv.act_night({"target": "lots"})["error"] == "target must be a number"


def test_turning_the_mode_on_starts_a_fresh_night(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=42, wk_elapsed=50)
    srv.night()["wave"] = 7
    srv.act_night({"on": True})
    cfg = srv.night()
    assert cfg["since"] == AT
    assert cfg["wave"] is None       # the night gets its own wave when it admits
    assert cfg["wk_start"] == 42     # where strict pace measures from
    srv.act_night({"on": False})
    assert srv.night()["wave"] is None


def test_the_console_payload_carries_the_night(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv, target=4)
    view = srv.night_view()
    assert (view["on"], view["target"], view["live"], view["landed"]) == \
        (True, 4, 0, 0)
    assert view["gate"]["open"] is True
    assert view["next"]["what"] == "pass"


# ---------- the unfinalized source ----------

def test_the_night_source_is_queue_until_set(srv):
    cfg = srv.night()
    assert (cfg["source"], cfg["finalize_target"]) == ("queue", 3)
    assert srv.act_night({"source": "unfinalized"}) == {"ok": True}
    assert srv.night()["source"] == "unfinalized"
    assert "source must be" in srv.act_night({"source": "backlog"})["error"]
    assert srv.night()["source"] == "unfinalized"
    assert srv.act_night({"finalize_target": 5}) == {"ok": True}
    assert srv.night()["finalize_target"] == 5


def test_the_unfinalized_source_starts_finalize_passes_in_triage_order(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    sent = finalize_launch(srv, monkeypatch)
    for tid in ("bbb", "ccc"):
        backlog_solver(srv, tid)
    # a chain that wrote no solver leads the triage order
    srv.save_report("aaa", "refine", "no file written")
    lead = item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain())
    night_on(srv, source="unfinalized", finalize_target=2)
    assert srv.night_tick()["admitted"] == ["aaa"]
    assert lead["phase"] == "finalize" and lead["auto_finalize"] is True
    assert srv.night_tick()["admitted"] == ["bbb"]
    assert srv.find("bbb")["auto_finalize"] is True
    # the target counts every item with work coming
    assert srv.night_tick()["admitted"] == []
    assert [phase for _, phase in sent] == ["finalize", "finalize"]
    assert "admitted aaa · finalize" in srv.night()["log"][0]["text"]
    # the queue was never drawn from
    assert {it["id"] for it in srv.STATE["items"]} == {"aaa", "bbb"}


def test_the_unfinalized_source_passes_over_a_pass_in_flight(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    sent = finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    item(srv, "aaa", srv.RUNNING, chain=srv.default_chain(), phase="finalize")
    backlog_solver(srv, "bbb")
    night_on(srv, source="unfinalized", finalize_target=5)
    assert srv.night_tick()["admitted"] == ["bbb"]
    assert [phase for _, phase in sent] == ["finalize"]


def test_the_unfinalized_source_passes_over_items_not_done_up_to_finalize(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    sent = finalize_launch(srv, monkeypatch)
    # a refine the usage limit cut, waiting for its resume, and a queued task
    # whose solver is on disk from an earlier pass: neither is a candidate
    backlog_solver(srv, "aaa")
    item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain(), resume_phase="refine")
    backlog_solver(srv, "bbb")
    item(srv, "bbb", srv.QUEUED, chain=srv.default_chain(), phase="create",
         sessions={"create": None, "refine": None, "finalize": None}, landed=[])
    backlog_solver(srv, "ccc")
    night_on(srv, source="unfinalized", finalize_target=5)
    assert srv.night_tick()["admitted"] == ["ccc"]
    assert [phase for _, phase in sent] == ["finalize"]
    srv.night_tick()
    assert not [e for e in srv.night()["log"] if "not started" in e["text"]]


def test_a_worker_that_fails_to_start_ends_the_admitter_pass(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    tried = []

    def failing(it, msg, phase, **kw):
        tried.append(it["id"])
        raise OSError("no claude binary")
    monkeypatch.setattr(srv, "launch", failing)
    for tid in ("aaa", "bbb", "ccc"):
        backlog_solver(srv, tid)
    night_on(srv, source="unfinalized", finalize_target=5)
    assert srv.night_tick()["admitted"] == []
    assert tried == ["aaa"]
    assert srv.STATE["items"] == []
    assert [e["text"] for e in srv.night()["log"]] == \
        ["aaa · finalize not started — could not start the worker: no claude binary"]


def test_the_queue_slot_is_not_paced_on_fable_when_the_admitter_owns_finalize(srv):
    srv.auto()["finalize"] = True
    fable = srv.MODEL_IDS["fable"]
    assert fable in srv.night_models()
    night_on(srv, source="both")
    assert fable not in srv.slot_models("queue")
    assert srv.slot_models("finalize") == [fable]
    srv.night()["source"] = "queue"
    assert fable in srv.slot_models("queue")


def test_an_empty_unfinalized_list_is_logged_once(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv, source="unfinalized")
    assert srv.night_tick()["admitted"] == []
    srv.night_tick()
    assert [e["text"] for e in srv.night()["log"]] == ["nothing to finalize"]
    assert srv.night()["on"] is True


def test_the_unfinalized_source_paces_on_the_fable_window(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, fbl=(45, 50))
    night_on(srv, source="unfinalized")
    assert srv.admit_models() == [srv.MODEL_IDS["fable"]]
    assert srv.night_tick()["held"].startswith("fbl at pace")
    assert srv.pacer(models=[srv.MODEL_IDS["opus"]])["open"] is True
    assert srv.pacer(models=[srv.MODEL_IDS["fable"]])["open"] is False


def test_the_unfinalized_source_keeps_finalize_behind_the_pacer(srv):
    srv.start_wave(1)
    it = srv.find("t00")
    srv.act_auto({"finalize": True})
    assert srv.auto_advances(it, "refine")
    night_on(srv, source="unfinalized")
    assert not srv.auto_advances(it, "refine")
    srv.night()["source"] = "queue"
    assert srv.auto_advances(it, "refine")
    srv.night().update(source="unfinalized", on=False)
    assert srv.auto_advances(it, "refine")


def test_a_finalize_the_user_starts_asks_for_callouts_too(srv, monkeypatch):
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    srv.act_finalize({"id": "aaa"})
    assert srv.find("aaa")["auto_finalize"] is True


def test_a_chain_that_wrote_no_solver_still_finalizes(srv, monkeypatch):
    sent = finalize_launch(srv, monkeypatch)
    srv.save_report("aaa", "refine", "the handoff")
    it = item(srv, "aaa", srv.NEEDS_REVIEW, chain=srv.default_chain())
    assert srv.act_finalize({"id": "aaa"})["advanced"] is True
    assert it["phase"] == "finalize"
    (msg, _), = sent
    assert "wrote no solver" in msg and "Write it from the reports" in msg
    assert "Read programs/solvers/aaa.dl first" not in msg
    assert srv.REVIEW_TAIL in msg


def test_the_payload_carries_the_source_and_both_targets(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    night_on(srv, source="unfinalized", finalize_target=4)
    view = srv.night_view()
    assert (view["source"], view["target"], view["finalize_target"]) == \
        ("unfinalized", 6, 4)
    assert "autopilot on" not in " ".join(e["text"] for e in view["log"])
    srv.act_night({"on": False})
    srv.act_night({"on": True})
    assert srv.night()["log"][-1]["text"] == "autopilot on · unfinalized · target 4"


# ---------- the both source ----------

def test_the_both_source_is_accepted(srv):
    assert srv.act_night({"source": "both"}) == {"ok": True}
    assert srv.night()["source"] == "both"
    srv.act_night({"on": True})
    assert srv.night()["log"][-1]["text"] == "autopilot on · both · target 6 · finalize target 3"


def test_the_both_source_admits_one_of_each_kind_in_a_pass(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    sent = finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    night_on(srv, source="both")
    assert srv.night_tick()["admitted"] == ["aaa", "t00"]
    assert [phase for _, phase in sent] == ["finalize"]
    assert srv.find("aaa")["phase"] == "finalize" and srv.find("t00")["phase"] == "create"
    texts = [e["text"] for e in srv.night()["log"]]
    assert texts[0].startswith("admitted aaa · finalize · 1/3 live")
    assert texts[1].startswith("admitted t00 · create · 1/6 live")


def test_the_both_source_fills_each_slot_to_its_own_target(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    finalize_launch(srv, monkeypatch)
    for tid in ("aaa", "bbb"):
        backlog_solver(srv, tid)
    night_on(srv, source="both", target=2, finalize_target=1)
    assert srv.night_tick()["admitted"] == ["aaa", "t00"]
    # the finalize slot is full; the queue slot still has room
    assert srv.night_tick()["admitted"] == ["t01"]
    assert srv.night_tick()["admitted"] == []
    cfg = srv.night()
    assert (srv.slot_live(cfg, "finalize"), srv.slot_live(cfg, "queue")) == (1, 2)
    assert srv.find("bbb") is None


def test_the_both_source_holds_one_slot_while_the_other_admits(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, fbl=(45, 50))
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    night_on(srv, source="both")
    out = srv.night_tick()
    assert out["admitted"] == ["t00"]
    assert out["held"].startswith("finalize: fbl at pace")
    assert srv.find("aaa") is None
    assert srv.night()["log"][-1]["text"] == "hold · finalize: fbl at pace"
    view = srv.night_view()
    assert view["gate"]["open"] is True
    assert view["gate"]["why"] == "finalize held (fbl pace), queue open"


def test_two_standing_notes_do_not_take_turns_filling_the_log(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50, fbl=(45, 50))
    monkeypatch.setattr(srv, "queue_pick", lambda n, order, held=(): [])
    night_on(srv, source="both")
    for _ in range(5):
        srv.night_tick()
    texts = [e["text"] for e in srv.night()["log"]]
    assert texts == ["queue is empty", "hold · finalize: fbl at pace"]


def test_the_both_source_keeps_finalize_behind_the_pacer(srv):
    srv.start_wave(1)
    it = srv.find("t00")
    srv.act_auto({"finalize": True})
    assert srv.auto_advances(it, "refine")
    night_on(srv, source="both")
    assert not srv.auto_advances(it, "refine")


def test_exhaust_holds_the_queue_slot_while_the_fable_window_trails(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=55, wk_elapsed=50, fbl=(40, 50))
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    backlog_solver(srv, "bbb")
    night_on(srv, source="both", pace="exhaust")
    out = srv.night_tick()
    assert out["admitted"] == ["aaa"]           # bbb still waits, so the queue holds
    assert out["held"].startswith("queue: Fable window trails")
    assert srv.night_view()["gate"]["open"] is True


def test_the_queue_slot_runs_while_the_finalize_slot_is_full(srv, monkeypatch):
    """Holding the queue behind a slot that cannot take more would run the
    night at the finalize target alone."""
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=55, wk_elapsed=50, fbl=(40, 50))
    finalize_launch(srv, monkeypatch)
    for i in range(3):
        finalize_item(srv, f"f{i}", state=srv.RUNNING)
    backlog_solver(srv, "aaa")
    night_on(srv, source="both", pace="exhaust", finalize_target=3)
    out = srv.night_tick()
    assert out["admitted"] == ["t00"]
    assert out["held"] is None


def test_the_queue_slot_runs_when_fable_has_caught_up_or_nothing_waits(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    finalize_launch(srv, monkeypatch)
    night_on(srv, source="both", pace="exhaust")
    set_usage(srv, monkeypatch, wk_pct=55, wk_elapsed=50, fbl=(53, 50))
    backlog_solver(srv, "aaa")
    assert srv.night_tick()["admitted"] == ["aaa", "t00"]
    set_usage(srv, monkeypatch, wk_pct=55, wk_elapsed=50, fbl=(40, 50))
    assert srv.night_tick()["admitted"] == ["t01"]      # nothing left to finalize


def test_balance_holds_the_finalize_slot_while_the_fable_window_leads(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=40, wk_elapsed=50, fbl=(55, 50))
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    night_on(srv, source="both", pace="exhaust", balance=True)
    out = srv.night_tick()
    assert out["admitted"] == ["t00"]
    assert out["held"].startswith("finalize: Fable window leads")


def test_balance_off_leaves_a_leading_fable_window_alone(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=40, wk_elapsed=50, fbl=(55, 50))
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    night_on(srv, source="both", pace="exhaust")
    out = srv.night_tick()
    assert out["admitted"] == ["aaa", "t00"]
    assert out["held"] is None


def test_a_leading_fable_window_holds_nothing_with_an_empty_queue(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=40, wk_elapsed=50, fbl=(55, 50))
    finalize_launch(srv, monkeypatch)
    monkeypatch.setattr(srv, "queue_pick", lambda n, order, held=(): [])
    backlog_solver(srv, "aaa")
    night_on(srv, source="both", pace="exhaust", balance=True)
    out = srv.night_tick()
    assert out["admitted"] == ["aaa"]
    assert out["held"] is None


def test_balance_checks_the_queue_slot_first_while_fable_leads(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    cfg = night_on(srv, source="both", pace="exhaust", balance=True)
    set_usage(srv, monkeypatch, wk_pct=40, wk_elapsed=50, fbl=(55, 50))
    assert srv.slot_order(cfg) == ("queue", "finalize")
    set_usage(srv, monkeypatch, wk_pct=55, wk_elapsed=50, fbl=(40, 50))
    assert srv.slot_order(cfg) == ("finalize", "queue")
    cfg["balance"] = False
    set_usage(srv, monkeypatch, wk_pct=40, wk_elapsed=50, fbl=(55, 50))
    assert srv.slot_order(cfg) == ("finalize", "queue")


def test_the_payload_carries_a_count_per_slot(srv, monkeypatch):
    clock_at(srv, monkeypatch)
    set_usage(srv, monkeypatch, wk_pct=10, wk_elapsed=50)
    finalize_launch(srv, monkeypatch)
    backlog_solver(srv, "aaa")
    night_on(srv, source="both")
    srv.night_tick()
    assert srv.night_view()["slots"] == [
        {"kind": "finalize", "live": 1, "target": 3},
        {"kind": "queue", "live": 1, "target": 6}]
    srv.night()["source"] = "unfinalized"
    assert srv.night_view()["slots"] == [{"kind": "finalize", "live": 2, "target": 3}]


# ---------- usage readings ----------

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


def test_the_usage_poll_forces_a_fetch_and_keeps_the_last_reading(srv, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(srv.subprocess, "run", lambda cmd, **kw: (
        calls.append((cmd, kw)), types.SimpleNamespace(returncode=0))[1])
    monkeypatch.setattr(srv.quota.Sampler, "record", lambda self, path: None)
    monkeypatch.setattr(srv, "USAGE_FETCH", tmp_path / "fetch.sh")
    (tmp_path / "fetch.sh").write_text("")
    a, s = usage_files(tmp_path)
    monkeypatch.setattr(srv, "USAGE_API", a)
    monkeypatch.setattr(srv, "USAGE_STATUS", s)
    monkeypatch.setattr(srv, "USAGE_POLL", 0)

    def one_pass(_):
        raise StopIteration
    monkeypatch.setattr(srv.time, "sleep", one_pass)
    with pytest.raises(StopIteration):
        srv.usage_loop()
    cmd, kw = calls[0]
    assert cmd[1:] == [str(tmp_path / "fetch.sh"), "--force"]
    # The script reads the account the console's home is logged into.
    assert kw["env"]["CLAUDE_CONFIG_DIR"] == str(srv.CLAUDE_HOME)
    assert [r["pct"] for r in srv.USAGE] == [55, 14, 4]
    assert s.stat().st_mtime == srv.USAGE_AT
    # A poll that finds the same reading again notes nothing new: a cache
    # that stopped moving must not read as a fleet that stopped spending.
    with pytest.raises(StopIteration):
        srv.usage_loop()
    assert len(srv.HISTORY["5h"]) == 1
    fetched = srv.USAGE_AT
    a.unlink()
    s.unlink()
    with pytest.raises(StopIteration):
        srv.usage_loop()
    assert [r["pct"] for r in srv.USAGE] == [55, 14, 4]
    assert fetched == srv.USAGE_AT


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
