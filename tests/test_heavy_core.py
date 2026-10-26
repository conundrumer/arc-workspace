"""The resource daemon's decisions (`scripts/heavy_core.py`), on readings of
the machine that the test gives as data: which waiting request starts, which
ungated command of a session is adopted, which job is killed at each memory
pressure, and which message goes to which session."""

import signal

from handbook.paths import scripts_importable

scripts_importable()

from heavy_core import Core, Grant, Log, Proc, Sample, Signal  # pyright: ignore[reportMissingImports]
from heavy_enforcer import ADOPT_GIB_SECONDS, KILL_GRACE, KILL_SETTLE, LAST_RESORT_SECONDS  # pyright: ignore[reportMissingImports]
from heavy_model import Amount, Job, Kind, Lane, Need, Waiter  # pyright: ignore[reportMissingImports]
from heavy_scheduler import estimates, next_waiters, queues, Holding  # pyright: ignore[reportMissingImports]

TOTAL = Amount(14, 20)
GIB_KIB = 1 << 20
CLAUDE = 100
SESSION = "s1"
SNAPSHOT_SHELL = "bash -c source /home/u/.claude/shell-snapshots/snapshot-bash-1.sh 2>/dev/null"


def proc(pid, ppid, command, session=SESSION, gib=0.0, cpu=0.0, start=1000.0):
    return Proc(pid, ppid, start, command, session, int(gib * GIB_KIB), cpu)


def reading(at, procs, level=1, swap=None, alive=()):
    table = {CLAUDE: proc(CLAUDE, 1, "claude"), **{p.pid: p for p in procs}}
    return Sample(at, table, {CLAUDE: SESSION}, frozenset(alive), level, swap)


def gated(core, pid, need=Need.SOON, gib=2, owner=SESSION, minutes=10.0):
    job = Job(pid, 1000.0, owner, Kind.GATED, need, Amount(2, gib), minutes, f"cmd{pid}", 0.0,
              members={pid: 1000.0})
    core.jobs[pid] = job
    return job


def killed(effects):
    return [e.pid for e in effects if isinstance(e, Signal) and e.number == signal.SIGTERM]


def test_an_ungated_command_that_stays_heavy_is_adopted_once_and_its_owner_told_once():
    core = Core(TOTAL)
    shell = proc(101, CLAUDE, SNAPSHOT_SHELL)
    hook = proc(103, CLAUDE, "node mcp-server", gib=3)
    below_hook = proc(104, 103, "python big.py", gib=3)
    hook_shell = proc(105, CLAUDE, "sh -c bash ~/.claude/scripts/check.sh # claude-config:check")
    below_shell = proc(106, 105, "python hook_heavy.py", gib=3)

    def sample(at):
        return reading(at, [shell, hook, below_hook, hook_shell, below_shell, proc(102, 101, "python allpoints.py", gib=3)])

    core.tick(sample(0), 0)
    assert core.tick(sample(ADOPT_GIB_SECONDS - 1), ADOPT_GIB_SECONDS - 1) == []
    effects = core.tick(sample(ADOPT_GIB_SECONDS), ADOPT_GIB_SECONDS)
    assert [(e.event, e.fields["reason"]) for e in effects if isinstance(e, Log)] == [("adopt", "memory")]
    assert list(core.jobs) == [102] and core.jobs[102].kind is Kind.UNGATED
    assert [j["kind"] for j in core.snapshot(0)["jobs"]] == ["ungated"]
    core.tick(sample(60), 60)
    messages = core.messages(60)
    assert len(messages) == 1 and messages[0][0] == CLAUDE and "allpoints.py" in messages[0][1]
    core.tick(sample(200), 200)
    assert core.messages(200) == []


def test_warn_pressure_kills_nothing_and_critical_kills_the_ungated_before_the_over_declared_before_idle():
    core = Core(TOTAL)
    ungated = Job(10, 1000.0, SESSION, Kind.UNGATED, None, Amount(1, 3), None, "py", 0.0, 3 * GIB_KIB, members={10: 1000.0})
    over = gated(core, 11, Need.NOW, gib=1)
    idle = gated(core, 12, Need.IDLE, gib=4)
    soon = gated(core, 13, Need.SOON, gib=4)
    within = gated(core, 14, Need.NOW, gib=4)
    core.jobs[10] = ungated
    footprints = {10: 3, 11: 2, 12: 1, 13: 1, 14: 1}
    procs = [proc(pid, 1, "x", gib=gib) for pid, gib in footprints.items()]
    alive = [11, 12, 13, 14]
    for at in (0, 5):
        assert [e for e in core.tick(reading(at, procs, level=2, alive=alive), at) if isinstance(e, Signal)] == []
    order = []
    at = 10
    for _ in range(4):
        order += killed(core.tick(reading(at, procs, level=4, alive=alive), at))
        at += KILL_SETTLE
        procs = [p for p in procs if p.pid not in order]
        for pid in order:
            core.jobs.pop(pid, None)
        alive = [pid for pid in alive if pid not in order]
    assert order == [10, 11, 12, 13]
    assert within.pid in core.jobs and over.pid not in core.jobs and idle.pid not in core.jobs and soon.pid not in core.jobs


def test_a_term_is_followed_by_a_kill_after_the_grace_and_the_victim_is_told_once():
    core = Core(TOTAL)
    gated(core, 20, Need.IDLE)
    procs = [proc(20, 1, "x", gib=1)]
    first = core.tick(reading(0, procs, level=4, alive=[20]), 0)
    assert killed(first) == [20]
    assert [e for e in core.tick(reading(KILL_GRACE - 1, procs, level=4, alive=[20]), KILL_GRACE - 1)
            if isinstance(e, Signal)] == []
    later = core.tick(reading(KILL_GRACE, procs, level=4, alive=[20]), KILL_GRACE)
    assert [(e.pid, e.number) for e in later if isinstance(e, Signal)] == [(20, signal.SIGKILL)]
    assert len(core.messages(KILL_GRACE)) == 1


def test_a_job_that_is_within_its_declaration_and_needs_now_goes_only_as_a_last_resort():
    core = Core(TOTAL)
    gated(core, 30, Need.NOW, gib=4)
    procs = [proc(30, 1, "x", gib=1)]
    for at in range(0, LAST_RESORT_SECONDS, 5):
        assert killed(core.tick(reading(at, procs, level=4, alive=[30]), at)) == []
    assert killed(core.tick(reading(LAST_RESORT_SECONDS, procs, level=4, alive=[30]), LAST_RESORT_SECONDS)) == [30]


def test_at_the_last_resort_a_larger_now_job_within_its_declaration_goes_before_a_smaller_idle_job():
    core = Core(TOTAL)
    gated(core, 31, Need.NOW, gib=8)
    gated(core, 32, Need.IDLE, gib=8)
    procs = [proc(31, 1, "x", gib=3), proc(32, 1, "x", gib=1)]
    assert killed(core.tick(reading(0, procs, level=4, alive=[31, 32]), 0)) == [32]
    other = Core(TOTAL)
    gated(other, 31, Need.NOW, gib=8)
    gated(other, 32, Need.IDLE, gib=8)
    other.critical_since = -LAST_RESORT_SECONDS
    assert killed(other.tick(reading(0, procs, level=4, alive=[31, 32]), 0)) == [31]


def test_a_process_of_no_session_and_a_claude_process_are_never_killed():
    core = Core(TOTAL)
    gated(core, 40, Need.IDLE, owner="-")
    job = gated(core, 41, Need.IDLE)
    job.members[CLAUDE] = 1000.0
    procs = [proc(40, 1, "x", gib=9, session="-"), proc(41, 1, "x", gib=1)]
    for at in (0, 30, 60):
        out = core.tick(reading(at, procs, level=4, alive=[40, 41]), at)
        assert 40 not in killed(out) and CLAUDE not in killed(out)


def test_a_swap_in_rate_kills_only_where_it_holds_for_two_samples():
    core = Core(TOTAL)
    gated(core, 50, Need.IDLE)
    procs = [proc(50, 1, "x", gib=1)]
    assert killed(core.tick(reading(0, procs, swap=5000, alive=[50]), 0)) == []
    assert killed(core.tick(reading(5, procs, swap=10, alive=[50]), 5)) == []
    assert killed(core.tick(reading(10, procs, swap=5000, alive=[50]), 10)) == []
    assert killed(core.tick(reading(15, procs, swap=5000, alive=[50]), 15)) == [50]


def test_an_overrun_is_logged_once_and_its_owner_told_once():
    core = Core(TOTAL)
    gated(core, 60, Need.SOON, gib=1, minutes=1.0)
    procs = [proc(60, 1, "x", gib=3)]
    first = core.tick(reading(0, procs, alive=[60]), 0)
    again = core.tick(reading(5, procs, alive=[60]), 5)
    assert [e.fields["reason"] for e in first if isinstance(e, Log)] == ["memory"]
    assert [e for e in again if isinstance(e, Log)] == []
    assert len(core.messages(5)) == 1
    later = core.tick(reading(125, procs, alive=[60]), 125)
    assert [e.fields["reason"] for e in later if isinstance(e, Log)] == ["time"]
    (claude, text), = core.messages(125)
    assert claude == CLAUDE and "minutes" in text


def test_the_messages_for_one_session_within_a_minute_go_as_one():
    core = Core(TOTAL)
    gated(core, 61, Need.SOON, gib=1, minutes=1.0).granted = -300.0
    core.tick(reading(0, [proc(61, 1, "x", gib=3)], alive=[61]), 0)
    (claude, text), = core.messages(0)
    assert text.count("pid 61") == 2


def test_a_job_that_ends_leaves_its_children_killed_unless_it_ran_for_no_session():
    core = Core(TOTAL)
    kept = gated(core, 70, owner=SESSION)
    gone = gated(core, 71, owner="-")
    kept.members[72] = 1000.0
    gone.members[73] = 1000.0
    procs = [proc(70, 1, "x"), proc(71, 1, "x"), proc(72, 70, "child"), proc(73, 71, "child")]
    core.tick(reading(0, procs, alive=[70, 71]), 0)
    left = [proc(72, 1, "child", session="-"), proc(73, 1, "child", session="-")]
    assert killed(core.tick(reading(5, left, alive=[]), 5)) == [72]


def test_a_restarted_daemon_keeps_the_jobs_of_the_registry_over_its_budget():
    old = Core(TOTAL)
    gated(old, 80, Need.NOW, gib=18)
    gated(old, 81, Need.NOW, gib=18)
    new = Core(Amount(14, 20))
    new.restore(old.snapshot(0))
    procs = [proc(80, 1, "x"), proc(81, 1, "x")]
    new.tick(reading(0, procs, alive=[80, 81]), 0)
    assert sorted(new.jobs) == [80, 81]
    waiter = Waiter(1, 90, 1000, SESSION, Need.NOW, Amount(1, 1), 1.0, "y", 0.0, None)
    new.submit(waiter, False, TOTAL)
    assert new.admit(1) == []


def test_a_long_waiter_does_not_block_a_short_one_and_a_waiter_is_not_passed_by_a_smaller_one():
    def waiter(id, minutes, cpus, need=Need.SOON, arrived=0.0):
        return Waiter(id, id, 1, SESSION, need, Amount(cpus, 1), minutes, "c", arrived, None)

    running = [Holding(Lane.LONG, Need.NOW, Amount(10, 10), 600.0)]
    waiting = [waiter(1, 10, 3, Need.NOW), waiter(2, 10, 1), waiter(3, 5, 4, Need.IDLE)]
    started = next_waiters(waiting, running, TOTAL, 0.0)
    assert [w.id for w in started] == [3]
    assert [w.id for w in queues(waiting, 0.0)[Lane.LONG]] == [1, 2]
    assert estimates(waiting, running, TOTAL, 0.0)[1] == 600.0


def test_a_short_job_does_not_take_the_capacity_a_long_head_waits_for_but_starts_within_the_reserve():
    def waiter(id, minutes, cpus, gib, need=Need.NOW):
        return Waiter(id, id, 1, SESSION, need, Amount(cpus, gib), minutes, "c", 0.0, None)

    running = [Holding(Lane.LONG, Need.NOW, Amount(4, 4), 600.0)]
    head = waiter(1, 10, 8, 8)
    assert [w.id for w in next_waiters([head, waiter(2, 5, 6, 2)], running, TOTAL, 0.0)] == []
    assert [w.id for w in next_waiters([head, waiter(3, 5, 4, 2)], running, TOTAL, 0.0)] == [3]
    assert estimates([head, waiter(2, 5, 6, 2)], running, TOTAL, 0.0)[1] == 600.0


def test_a_short_job_that_runs_past_its_minutes_holds_as_a_long_job_of_its_need():
    def admitted(now, *waiters):
        core = Core(TOTAL)
        gated(core, 10, Need.IDLE, gib=8, minutes=5.0)
        for w in waiters:
            core.submit(w, False, TOTAL)
        return [e.waiter.pid for e in core.admit(now) if isinstance(e, Grant)]

    def waiter(pid, need, cpus, gib, minutes):
        return Waiter(pid, pid, 1, SESSION, need, Amount(cpus, gib), minutes, "c", 0.0, None)

    within, past = 5 * 60 - 1.0, 5 * 60 + 1.0
    idle_share = waiter(20, Need.IDLE, 1, 1, 10.0)
    assert admitted(within, idle_share) == [20] and admitted(past, idle_share) == []
    pool = waiter(21, Need.NOW, 1, 9, 10.0)
    assert admitted(within, pool) == [21] and admitted(past, pool) == []
    short = waiter(22, Need.NOW, 4, 4, 5.0)
    assert admitted(within, pool, short) == [21] and admitted(past, pool, short) == [22]


def test_a_large_footprint_outside_the_jobs_holds_a_request_that_the_fixed_budget_admits():
    core = Core(TOTAL)
    core.tick(reading(0, [proc(500, 1, "browser", session="-", gib=18)]), 0)
    waiter = Waiter(1, 5, 1000, SESSION, Need.NOW, Amount(1, 4), 5.0, "pytest", 0.0, None)
    core.submit(waiter, False, TOTAL)
    assert core.available().gib == 2 and core.admit(1.0) == []
    core.tick(reading(5, []), 5)
    assert any(isinstance(e, Grant) for e in core.admit(6.0))


def test_an_adopted_process_counts_once_in_the_budget():
    core = Core(TOTAL)
    shell = proc(101, CLAUDE, SNAPSHOT_SHELL)

    def sample(at):
        return reading(at, [shell, proc(102, 101, "python allpoints.py", gib=3),
                            proc(500, 1, "other", session="-", gib=2)])

    for at in (0, ADOPT_GIB_SECONDS):
        core.tick(sample(at), at)
    assert 102 in core.jobs
    assert core.outside_kib == 2 * GIB_KIB + 0  # the claude process has no footprint here
    assert core.available().gib == TOTAL.gib - 2
    assert sum(h.amount.gib for h in core.holdings(0.0)) == 3


def test_a_changed_need_reorders_the_waiting_requests():
    core = Core(TOTAL)
    core.hold = "memory pressure"

    def waiter(id, need):
        return Waiter(id, id, 1, SESSION, need, Amount(1, 1), 10.0, "c", float(id), None, 1, 1)

    first, second = waiter(1, Need.IDLE), waiter(2, Need.SOON)
    core.submit(first, False, TOTAL)
    core.submit(second, False, TOTAL)
    assert [w["pid"] for w in core.snapshot(10.0)["waiting"]] == [2, 1]
    assert core.set_need(1, Need.NOW, 10.0) is first
    assert [w["pid"] for w in core.snapshot(10.0)["waiting"]] == [1, 2]
    assert core.set_need(99, Need.NOW, 10.0) is None


def test_an_idle_waiter_goes_as_soon_after_half_an_hour():
    def waiter(id, need, arrived):
        return Waiter(id, id, 1, SESSION, need, Amount(1, 1), 10.0, "c", arrived, None)

    waiting = [waiter(1, Need.IDLE, 0.0), waiter(2, Need.SOON, 1000.0)]
    assert [w.id for w in queues(waiting, 1000.0)[Lane.LONG]] == [2, 1]
    assert [w.id for w in queues(waiting, 1900.0)[Lane.LONG]] == [1, 2]


def test_a_grant_is_logged_with_the_owner_and_its_figures():
    core = Core(TOTAL)
    waiter = Waiter(1, 5, 1000, SESSION, Need.NOW, Amount(2, 3), 5.0, "pytest", 0.0, None)
    core.submit(waiter, False, TOTAL)
    effects = core.admit(4.0)
    log, = [e for e in effects if isinstance(e, Log)]
    assert log.event == "grant" and log.fields["owner"] == SESSION and log.fields["cpus"] == 2
    assert any(isinstance(e, Grant) for e in effects)


OLD_GATE_CALL = "timeout 900 scripts/run_heavy.py --cpus 1 uv run python -u -m arclog_convert.convert"


def test_the_adoption_notice_does_not_tell_the_session_to_stop_the_process():
    core = Core(TOTAL)
    shell = proc(101, CLAUDE, SNAPSHOT_SHELL)
    for at in (0, ADOPT_GIB_SECONDS):
        core.tick(reading(at, [shell, proc(102, 101, "python allpoints.py", gib=3)]), at)
    (_, text), = core.messages(ADOPT_GIB_SECONDS)
    assert "Stop it" not in text and "keeps running" in text


def test_a_call_of_a_run_heavy_the_daemon_does_not_see_is_counted_and_its_session_told_no_outside_the_gate():
    core = Core(TOTAL)
    shell = proc(101, CLAUDE, SNAPSHOT_SHELL)

    def sample(at, level=1):
        return reading(at, [shell, proc(102, 101, OLD_GATE_CALL, gib=3)], level=level)

    for at in (0, ADOPT_GIB_SECONDS):
        core.tick(sample(at), at)
    assert core.jobs[102].kind is Kind.UNGATED
    assert core.messages(ADOPT_GIB_SECONDS) == []
    core.tick(sample(40, level=2), 40)
    assert core.messages(40) == []
    core.tick(sample(50, level=4), 50)
    (_, text), = core.messages(50)
    assert "were killed" in text and "`" + OLD_GATE_CALL + "`" in text.split("Run it again as ")[1]


def test_a_gated_job_holds_its_declared_gib_for_a_minute_and_then_its_peak_and_a_gib():
    core = Core(TOTAL)
    gated(core, 10, gib=7)
    core.tick(reading(1, [proc(10, CLAUDE, "convert", gib=1.0)], alive=[10]), 1)

    def held(now):
        return core.holdings(now)[0].amount

    assert held(59.0) == Amount(2, 7) and held(61.0) == Amount(2, 2)
    core.tick(reading(70, [proc(10, CLAUDE, "convert", gib=0.2)], alive=[10]), 70)
    assert held(71.0) == Amount(2, 2)
    core.tick(reading(80, [proc(10, CLAUDE, "convert", gib=4.5)], alive=[10]), 80)
    assert held(81.0) == Amount(2, 6)


def test_a_request_that_the_declared_gib_of_a_running_job_would_hold_starts_once_the_minute_has_passed():
    core = Core(TOTAL)
    core.tick(reading(0, [proc(500, 1, "browser", session="-", gib=8)]), 0)
    gated(core, 10, gib=7)
    core.tick(reading(1, [proc(10, CLAUDE, "convert", gib=1.0), proc(500, 1, "browser", session="-", gib=8)],
                      alive=[10]), 1)
    assert core.available().gib == 12
    waiter = Waiter(1, 5, 1000, SESSION, Need.NOW, Amount(1, 6), 5.0, "eval", 0.0, None)
    core.submit(waiter, False, TOTAL)
    assert core.admit(30.0) == []
    assert any(isinstance(e, Grant) for e in core.admit(61.0))
