"""`refusal_of` gives the time of the refused message that ended an attempt."""

import json

from operations.completion import latest_sends, refusal_of
from operations.state import Call, Report, Tool


def message(time: float, *, success: bool = False, to: str = "a1") -> Call:
    return Call("op", time, Tool.SEND_MESSAGE, {"to": to, "message": "x"},
                json.dumps({"success": success}), False)


def refusal(since: float, reports: tuple[Report, ...], *calls: Call) -> float | None:
    return refusal_of("a1", since, reports, latest_sends(calls))


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


def test_the_latest_message_of_calls_at_one_time_is_the_last_of_them() -> None:
    first, second = message(20.0), message(20.0, success=True)
    assert latest_sends([first, second]) == {"a1": second}


def test_a_message_the_harness_gave_an_error_is_no_latest_message() -> None:
    errored = Call("op", 30.0, Tool.SEND_MESSAGE, {"to": "a1", "message": "x"}, "boom", True)
    assert latest_sends([message(20.0), errored]) == {"a1": message(20.0)}
