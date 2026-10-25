"""`refused_at` gives the time of the refused message that ended an attempt."""

from operations import attempts as a
from operations.attempt_view import refused_at
from operations.roles import Described, Role
from operations.state import Report


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
