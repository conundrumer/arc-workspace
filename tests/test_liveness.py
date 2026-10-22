"""`attempt_state` gives one state per attempt from its facts: one case per
condition of stage 1 and of stage 2, and `refusal_of`, which tests the
refused message once."""

import json
from pathlib import Path

from operations.completion import refusal_of
from operations.constants import STUCK_SECONDS
from operations.liveness import AttemptFacts, CodexEnd, CodexRead, Written, attempt_state
from operations.state import Call, Ended, Report, Running, Tool, Unknown, Waits

WRITE = 1000.0


def facts(waits: Waits | None = Waits.AT_WORK, *, codex: CodexEnd = CodexEnd.DONE,
          report: Report | None = None, refused: float | None = None,
          reads: list[str] | None = None, **flags: bool) -> AttemptFacts:
    """Facts that give the Codex read `codex`, which a call of it records in `reads`."""
    def read() -> CodexRead:
        if reads is not None:
            reads.append("codex")
        return CodexRead(codex, "why")

    return AttemptFacts(waits, lambda: report, read, lambda rollout, unknown: Written(WRITE),
                        refused, **flags)


def test_work_the_listing_gives_running_runs_with_the_waits_of_its_sign() -> None:
    assert attempt_state(facts(Waits.AT_WORK, listed=True)) == Running(
        Waits.AT_WORK, WRITE + STUCK_SECONDS)


def test_work_the_listing_gives_running_runs_still_running_where_its_sign_is_not_pending() -> None:
    assert attempt_state(facts(None, listed=True)) == Running(
        Waits.STILL_RUNNING, WRITE + STUCK_SECONDS)


def test_an_attempt_whose_tickets_closed_ends_with_no_codex_read() -> None:
    reads: list[str] = []
    done = Report(5.0, "done")
    assert attempt_state(facts(Waits.AT_WORK, outlived=True, report=done, reads=reads,
                               codex=CodexEnd.LIVE)) == Ended(done)
    assert reads == []


def test_a_sign_that_is_not_pending_ends_the_attempt() -> None:
    assert attempt_state(facts(None)) == Ended()


def test_a_sign_that_is_not_pending_gives_a_live_codex_turn_running() -> None:
    assert attempt_state(facts(None, codex=CodexEnd.LIVE)) == Running(Waits.STILL_RUNNING, WRITE + STUCK_SECONDS)


def test_a_stalled_codex_attempt_with_a_live_turn_runs() -> None:
    assert attempt_state(facts(stalled=True, codex=CodexEnd.LIVE)) == Running(Waits.STILL_RUNNING, WRITE + STUCK_SECONDS)


def test_a_stalled_codex_attempt_with_an_unknown_turn_is_unknown() -> None:
    state = attempt_state(facts(stalled=True, codex=CodexEnd.UNKNOWN))
    assert isinstance(state, Unknown)
    assert "unknown (why)" in state.reason
    assert state.until == WRITE + STUCK_SECONDS


def test_an_idle_ended_codex_attempt_with_a_live_turn_runs() -> None:
    assert attempt_state(facts(Waits.STILL_RUNNING, idle=True, codex=CodexEnd.LIVE)) == Running(
        Waits.STILL_RUNNING, WRITE + STUCK_SECONDS)


def test_an_idle_ended_attempt_at_work_ends_where_its_codex_read_is_done() -> None:
    done = Report(5.0, "done")
    assert attempt_state(facts(Waits.AT_WORK, idle=True, report=done)) == Ended(done)


def test_an_idle_turn_leaves_an_attempt_the_usage_limit_stopped_running() -> None:
    reads: list[str] = []
    assert attempt_state(facts(Waits.LIMITED, idle=True, reads=reads)) == Running(
        Waits.LIMITED, WRITE + STUCK_SECONDS)
    assert reads == []


def test_an_attempt_of_another_operator_with_no_work_open_ends() -> None:
    assert attempt_state(facts(elsewhere=True, codex=CodexEnd.DEAD)) == Ended()


def test_a_pending_codex_attempt_that_is_no_end_candidate_is_never_read() -> None:
    reads: list[str] = []
    assert attempt_state(facts(Waits.AT_WORK, reads=reads, codex=CodexEnd.DONE)) == Running(
        Waits.AT_WORK, WRITE + STUCK_SECONDS)
    assert reads == []


def test_a_codex_read_that_gives_the_attempt_done_or_dead_ends_it() -> None:
    for end in (CodexEnd.DONE, CodexEnd.DEAD):
        assert attempt_state(facts(None, codex=end)) == Ended()


def test_an_ended_attempt_takes_its_refusal() -> None:
    assert attempt_state(facts(None, refused=7.0)) == Ended(None, 7.0)


def test_a_running_attempt_takes_no_refusal() -> None:
    assert attempt_state(facts(Waits.AT_WORK, refused=7.0)) == Running(
        Waits.AT_WORK, WRITE + STUCK_SECONDS)


def message(time: float, *, success: bool = False, to: str = "a1") -> Call:
    return Call("op", time, Tool.SEND_MESSAGE, {"to": to, "message": "x"},
                json.dumps({"success": success}), False)


def refusal(since: float, reports: tuple[Report, ...], *calls: Call) -> float | None:
    return refusal_of("a1", since, reports, calls)


def test_an_attempt_that_ended_with_no_result_and_got_a_refused_message_is_refused() -> None:
    assert refusal(10.0, (), message(20.0)) == 20.0


def test_a_refused_message_before_the_resume_gives_no_refusal() -> None:
    assert refusal(30.0, (), message(20.0)) is None


def test_a_report_after_the_refused_message_gives_no_refusal() -> None:
    assert refusal(10.0, (Report(25.0, "done"),), message(20.0)) is None


def test_a_later_accepted_message_gives_no_refusal() -> None:
    assert refusal(10.0, (), message(20.0), message(22.0, success=True)) is None


def test_a_refused_message_to_another_agent_gives_no_refusal() -> None:
    assert refusal(10.0, (), message(20.0, to="a2")) is None


def live(rollout_time: float) -> AttemptFacts:
    """Facts of a sign-ended Codex attempt whose turn is live, whose rollout was written at `rollout_time`."""
    def read() -> CodexRead:
        return CodexRead(CodexEnd.LIVE, "why", None, Path("rollout.jsonl"))

    return AttemptFacts(None, lambda: None, read,
                        lambda rollout, unknown: Written(rollout_time if rollout else None))


def test_a_live_codex_turn_with_a_quiet_rollout_has_a_lease_that_runs_out() -> None:
    state = attempt_state(live(WRITE))
    assert state == Running(Waits.STILL_RUNNING, WRITE + STUCK_SECONDS)


def test_a_live_codex_turn_with_a_fresh_rollout_has_a_later_lease() -> None:
    old = attempt_state(live(WRITE))
    fresh = attempt_state(live(WRITE + 1000))
    assert isinstance(old, Running) and isinstance(fresh, Running)
    assert old.until is not None and fresh.until is not None and fresh.until > old.until


def test_a_sign_pending_native_attempt_with_no_transcript_gets_a_lease_from_since(
        monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    from handbook.paths import scripts_importable
    from operations.roles import Role
    from operations.state import Agent
    from tests.conftest import script

    scripts_importable()
    operator_state = script("operator_state")
    codex_reads = sys.modules["codex_reads"]
    monkeypatch.setattr(operator_state, "launched_find", lambda aid: None)
    monkeypatch.setattr(codex_reads, "native_find",
                        lambda aid: SimpleNamespace(state={"native": None}))
    a = Agent("a1", "op", Role.CODE_EDITOR, "1-1", "", 0.0, 500.0, Running(Waits.AT_WORK), (), True)
    facts = operator_state.attempt_facts(a, "op", (), [], [], {}, {}, frozenset(), frozenset(),
                                         set())
    assert attempt_state(facts) == Running(Waits.AT_WORK, 500.0 + STUCK_SECONDS)
