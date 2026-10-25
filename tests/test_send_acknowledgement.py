"""A message to a Codex launcher is in flight until its worker acknowledges it."""

from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from operations import attempts as a
from operations.command_words import next_command
from operations.journal import Close, Entry, Outcome, closing
from operations.roles import CODEX_LAUNCHER, Described, Role
from operations.state import Call, Tool
from tests.conftest import script

scripts_importable()
attempt_record = script("attempt_record")
operator_state = script("operator_state")
step_journal = script("step_journal")

OP, LAUNCHER, ORDINARY = "a0000000000000f01", "a0000000000000c01", "a0000000000000c02"
SEAT = Described(Role.CODE_EDITOR, "9-1")
TEXT = "Review the change again."


def launch(agent: str, kind: str) -> a.Launched:
    return a.Launched(source=f"launch:{agent}", at=1.0, agent=agent, seat=SEAT, parent=OP,
                      agent_type=kind, transport=a.Transport.CLAUDE)


def sent(to: str, *, outcome: a.Outcome = a.Outcome.ACCEPTED, call: str = "t1") -> a.Message:
    return a.Message(source=f"claude:{OP}:{call}", at=11.0, agent=OP, recipient=to, text=TEXT,
                     outcome=outcome, delivery=f"claude:{OP}:{call}", call=call)


def entry(to: str) -> Entry:
    return Entry("k", "e", "d", "origin", OP, 10.0, Tool.SEND_MESSAGE, to, TEXT, None, None, None)


def send_call(to: str, *, result: str | None = "sent", error: bool = False) -> Call:
    return Call(OP, 11.0, Tool.SEND_MESSAGE, {"to": to, "message": TEXT}, result, error, id="t1")


def close(to: str, *calls: Call, ended: bool = False, now: float = 50.0) -> Close | None:
    acknowledged = step_journal.acknowledgement(lambda aid: ended)
    return closing(entry(to), calls, True, now, acknowledged)


def received(at: float = 30.0) -> a.Received:
    return a.Received(source="received", at=at, agent=LAUNCHER, delivery=f"claude:{OP}:t1",
                      revision=1, thread="t", turn="u")


@pytest.fixture
def record():
    return attempt_record.Record()


def test_a_message_to_a_codex_launcher_is_in_flight_until_its_worker_takes_it(record) -> None:
    record.append(launch(LAUNCHER, CODEX_LAUNCHER), sent(LAUNCHER))
    assert close(LAUNCHER, send_call(LAUNCHER)) is None
    record.append(received())
    assert close(LAUNCHER, send_call(LAUNCHER)) == Close(Outcome.DONE, 30.0, "")


def test_a_message_to_an_ordinary_agent_is_done_at_its_call(record) -> None:
    record.append(launch(ORDINARY, "doc-reviewer"), sent(ORDINARY))
    assert close(ORDINARY, send_call(ORDINARY)) == Close(Outcome.DONE, 11.0, "")


def test_a_refused_message_to_a_launcher_fails_at_once(record) -> None:
    record.append(launch(LAUNCHER, CODEX_LAUNCHER), sent(LAUNCHER, outcome=a.Outcome.REFUSED))
    result = close(LAUNCHER, send_call(LAUNCHER))
    assert result is not None and result.outcome is Outcome.FAILED and result.time == 11.0


def test_a_launcher_that_ended_without_taking_the_message_fails_it(record) -> None:
    record.append(launch(LAUNCHER, CODEX_LAUNCHER), sent(LAUNCHER))
    result = close(LAUNCHER, send_call(LAUNCHER), ended=True)
    assert result == Close(Outcome.FAILED, 50.0, "the Codex launcher ended without taking the message")


def test_a_later_turn_that_omits_the_message_does_not_complete_it(record) -> None:
    record.append(launch(LAUNCHER, CODEX_LAUNCHER), sent(LAUNCHER))
    attempt_record.acknowledge_input(record, LAUNCHER, "an unrelated input", "t", "omitting", 1, 40.0)
    assert close(LAUNCHER, send_call(LAUNCHER)) is None
    attempt_record.acknowledge_input(record, LAUNCHER, f"{OP}: {TEXT}", "t", "consuming", 1, 41.0)
    assert close(LAUNCHER, send_call(LAUNCHER)) == Close(Outcome.DONE, 41.0, "")


def test_a_call_of_next_after_the_send_does_not_fail_the_delivery_in_flight(record) -> None:
    record.append(launch(LAUNCHER, CODEX_LAUNCHER), sent(LAUNCHER))
    again = Call(OP, 12.0, Tool.BASH, {"command": next_command(OP)}, "", False)
    assert close(LAUNCHER, send_call(LAUNCHER), again) is None


def test_a_message_with_no_message_event_is_not_a_success(record) -> None:
    record.append(launch(LAUNCHER, CODEX_LAUNCHER))
    assert close(LAUNCHER, send_call(LAUNCHER)) is None


def test_a_call_the_harness_gave_an_error_fails_as_before(record) -> None:
    record.append(launch(LAUNCHER, CODEX_LAUNCHER))
    result = close(LAUNCHER, send_call(LAUNCHER, result="boom", error=True))
    assert result == Close(Outcome.FAILED, 11.0, "boom")
