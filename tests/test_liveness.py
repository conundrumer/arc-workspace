"""`refused_at` gives the time of the refused message that ended an attempt."""

import pytest

from operations import attempts as a
from operations.attempt_view import refused_at
from operations.liveness import AttemptFacts, CodexEnd, CodexRead, Written, attempt_state
from operations.roles import Described, Role
from operations.state import AttemptState, Ended, Report, Running, Unknown, Waits


def refused(*times: float, to: str = "a1", accepted: tuple[float, ...] = ()) -> dict[str, a.Attempt]:
    events = [a.Launched(source="launch", at=1.0, agent="a1", seat=Described(Role.DOC_EDITOR, "9-1"),
                         parent="op", agent_type="doc-editor", transport=a.Transport.CLAUDE)]
    events += [a.Message(source=f"m{t}", at=t, agent="op", recipient=to, text="x",
                         outcome=a.Outcome.REFUSED, delivery=f"d{t}", call=f"c{t}") for t in times]
    events += [a.Message(source=f"m{t}", at=t, agent="op", recipient=to, text="x",
                         outcome=a.Outcome.ACCEPTED, delivery=f"d{t}", call=f"c{t}") for t in accepted]
    return a.fold(events)


def refusal(since: float, reports: tuple[Report, ...], *times: float, to: str = "a1",
            accepted: tuple[float, ...] = ()) -> float | None:
    return refused_at(refused(*times, to=to, accepted=accepted)["a1"], since, reports)


def test_an_attempt_that_ended_with_no_result_and_got_a_refused_message_is_refused() -> None:
    assert refusal(10.0, (), 20.0) == 20.0


def test_a_refused_message_before_the_resume_gives_no_refusal() -> None:
    assert refusal(30.0, (), 20.0) is None


def test_a_report_after_the_refused_message_gives_no_refusal() -> None:
    assert refusal(10.0, (Report(25.0, "done"),), 20.0) is None


def test_a_later_accepted_message_gives_no_refusal() -> None:
    assert refusal(10.0, (), 20.0, accepted=(22.0,)) is None


def test_the_latest_refused_message_gives_the_refusal() -> None:
    assert refusal(10.0, (), 20.0, 22.0) == 22.0


def test_a_refused_message_to_another_agent_gives_no_refusal() -> None:
    assert refusal(10.0, (), 20.0, to="a2") is None


SEAT = Described(Role.CODE_EDITOR, "9-1")


def attempt_of(*events: a.Event) -> a.Attempt:
    launch = a.Launched(source="launch", at=1.0, agent="a1", seat=SEAT, parent="op",
                        agent_type="code-editor", transport=a.Transport.CLAUDE)
    return a.fold([launch, *events])["a1"]


def gap(complete: bool, producer: bool) -> a.Coverage:
    return a.Coverage(source="cover", at=2.0, agent="a1", complete=complete,
                      reason="" if complete else "a gap", producer=producer)


def state_of(attempt: a.Attempt, *, turn: CodexEnd = CodexEnd.DEAD, **facts: bool) -> AttemptState:
    return attempt_state(attempt, AttemptFacts(
        lambda: CodexRead(turn), lambda rollout, unknown: Written(2.0), **facts))


@pytest.mark.parametrize("coverage", [gap(False, False), gap(True, True)])
def test_a_record_with_a_gap_is_ended_by_the_close_of_its_tickets_and_held_otherwise(
        coverage: a.Coverage) -> None:
    attempt = attempt_of(coverage)
    assert isinstance(state_of(attempt, outlived=True), Ended)
    assert isinstance(state_of(attempt, outlived=False), Unknown)


def reserved(accepted: bool) -> list[a.Event]:
    events: list[a.Event] = [a.Reserved(source="reserved", at=3.0, agent="a1", reservation="r", revision=1)]
    if accepted:
        events.append(a.Accepted(source="accepted", at=3.0, agent="a1", reservation="r",
                                 thread="t", turn="u"))
    return events


def test_the_close_of_its_tickets_does_not_end_a_record_with_a_gap_and_a_turn_with_no_end() -> None:
    attempt = attempt_of(gap(False, False), *reserved(accepted=True))
    unread = state_of(attempt, turn=CodexEnd.UNKNOWN, outlived=True)
    assert isinstance(unread, Unknown)
    live = state_of(attempt, turn=CodexEnd.LIVE, outlived=True)
    assert isinstance(live, Running) and live.waits is Waits.STILL_RUNNING


def test_the_close_of_its_tickets_does_not_end_a_record_with_a_gap_and_a_running_descendant() -> None:
    attempt = attempt_of(gap(False, False))
    assert isinstance(state_of(attempt, outlived=True, descendants=True), Running)
    assert isinstance(state_of(attempt, outlived=True, working=True), Running)


def test_the_close_of_its_tickets_leaves_a_submission_in_doubt_unknown() -> None:
    attempt = attempt_of(gap(False, False), *reserved(accepted=False))
    assert isinstance(state_of(attempt, outlived=True), Unknown)
