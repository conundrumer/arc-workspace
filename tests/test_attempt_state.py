"""The state of an attempt is read from its record, for Claude and native attempts alike."""

import fcntl
from pathlib import Path
from typing import Any

import pytest

from handbook.paths import scripts_importable
from operations import attempts as a
from operations.completion import occupies
from operations.roles import CODEX_LAUNCHER, Described, Role
from operations.state import Agent, Ended, Running, Unknown, Waits
from tests.conftest import script

scripts_importable()
operator_state = script("operator_state")
attempt_record = script("attempt_record")
codex_daemon = script("codex_daemon")
codex_reads = script("codex_reads")

OP, LAUNCHER, CHILD = "a0000000000000f01", "a0000000000000c01", "a0000000000000c02"
SEAT = Described(Role.CODE_EDITOR, "9-1")


def launch(agent: str = LAUNCHER, *, at: float = 1.0, parent: str = OP, native: bool = False,
           kind: str = CODEX_LAUNCHER) -> a.Launched:
    return a.Launched(source=f"launch:{agent}", at=at, agent=agent, seat=SEAT, parent=parent,
                      agent_type=kind, transport=a.Transport.NATIVE if native else a.Transport.CLAUDE)


def work(agent: str = LAUNCHER, *, accepted: bool = True, ended: a.Terminal | None = None,
         at: float = 2.0) -> list[a.Event]:
    events: list[a.Event] = [a.Reserved(source=f"reserved:{agent}", at=at, agent=agent,
                                        reservation="r", revision=1)]
    if accepted:
        events.append(a.Accepted(source=f"accepted:{agent}", at=at, agent=agent, reservation="r",
                                 thread="t", turn="u"))
    if ended is not None:
        events.append(a.TurnEnded(source=f"ended:{agent}", at=at + 1, agent=agent,
                                  reservation="r", status=ended))
    return events


def stop(agent: str = LAUNCHER, at: float = 3.0, text: str = "Done.") -> a.Stopped:
    return a.Stopped(source=f"stop:{agent}:{at}", at=at, agent=agent, text=text)


class Reader:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path = tmp_path
        self.turns: dict[str, str | None | Exception] = {}
        self.read: Any
        monkeypatch.setattr(operator_state, "launched_find", lambda aid: None)
        monkeypatch.setattr(codex_reads, "native_find", lambda aid: None)

        def status(thread: str, turn: str):
            answer = self.turns["u"]
            if isinstance(answer, Exception):
                raise answer
            return answer

        monkeypatch.setattr(codex_daemon, "turn_status", status)

    def state(self, *events: a.Event, agent: str = LAUNCHER, **facts) -> Agent:
        attempt_record.Record().append(*events)
        built = Agent(agent, OP, Role.CODE_EDITOR, "9-1", "", 0.5, 0.5, Running(Waits.AT_WORK), (), True)
        self.read = operator_state.attempt_reads([built], home=self.tmp_path, **facts)
        return self.read.agents[0]


@pytest.fixture
def reader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Reader:
    return Reader(tmp_path, monkeypatch)


def test_a_launch_with_a_stop_after_it_is_ended_and_one_with_no_stop_runs(reader: Reader) -> None:
    assert isinstance(reader.state(launch()).state, Running)
    assert isinstance(reader.state(stop()).state, Ended)


def hook_launch(at: float) -> a.Launched:
    return a.Launched(source="claude:op:call", at=at, agent="hook", seat=SEAT, parent=OP,
                      agent_type=CODEX_LAUNCHER, transport=a.Transport.CLAUDE)


def incomplete(at: float) -> a.Coverage:
    return a.Coverage(source="coverage", at=at, agent=LAUNCHER, complete=False, reason="a gap", producer=False)


def test_an_attempt_launched_before_the_record_began_with_nothing_since_is_ended(reader: Reader) -> None:
    events = [hook_launch(10.0), launch(), incomplete(11.0)]
    assert isinstance(reader.state(*events).state, Ended)
    assert isinstance(reader.state(live=frozenset({LAUNCHER})).state, Running)
    resumed = a.Resumed(source="resume", at=12.0, agent=LAUNCHER, parent=OP)
    assert isinstance(reader.state(resumed).state, Unknown)


def test_a_resume_after_the_stop_runs_again(reader: Reader) -> None:
    resumed = a.Resumed(source="resume", at=4.0, agent=LAUNCHER, parent=OP)
    assert isinstance(reader.state(launch(), stop(), resumed).state, Running)


def test_a_stopped_launcher_runs_while_its_codex_turn_runs(reader: Reader) -> None:
    reader.turns["u"] = "inProgress"
    read = reader.state(launch(), *work(), stop())
    assert isinstance(read.state, Running) and read.state.waits is Waits.STILL_RUNNING
    assert occupies(read)
    assert reader.read.held == {LAUNCHER}


def test_a_stopped_launcher_whose_codex_turn_is_over_is_ended(reader: Reader) -> None:
    reader.turns["u"] = "completed"
    assert isinstance(reader.state(launch(), *work(), stop()).state, Ended)


def test_a_turn_that_cannot_be_read_holds_the_attempt_as_unknown(reader: Reader) -> None:
    reader.turns["u"] = OSError("daemon unreachable")
    read = reader.state(launch(), *work(), stop())
    assert isinstance(read.state, Unknown) and "daemon unreachable" in read.state.reason


def test_a_held_work_lock_runs_the_attempt_without_the_daemon(reader: Reader) -> None:
    reader.turns["u"] = AssertionError("not read")
    events = [launch(), *work(), stop()]
    path = attempt_record.seat_path(SEAT)
    path.parent.mkdir(parents=True)
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert isinstance(reader.state(*events).state, Running)


def test_an_attempt_with_no_record_is_held_as_unknown(reader: Reader) -> None:
    read = reader.state(agent="a0000000000000e99")
    assert isinstance(read.state, Unknown) and "no record" in read.state.reason


def test_an_unrecorded_acceptance_holds_the_attempt_as_unknown(reader: Reader) -> None:
    read = reader.state(launch(), *work(accepted=False), stop())
    assert isinstance(read.state, Unknown) and "took up" in read.state.reason


@pytest.mark.parametrize("coverage", [
    a.Coverage(source="c", at=5.0, agent=LAUNCHER, complete=False, reason="a gap", producer=False),
    a.Coverage(source="c", at=5.0, agent=LAUNCHER, complete=True, reason="", producer=True)])
def test_incomplete_coverage_or_an_old_producer_holds_the_attempt(
        reader: Reader, coverage: a.Coverage) -> None:
    assert isinstance(reader.state(launch(), stop(), coverage).state, Unknown)


def test_complete_coverage_with_no_old_producer_lets_the_record_decide(reader: Reader) -> None:
    covered = a.Coverage(source="c", at=5.0, agent=LAUNCHER, complete=True, reason="", producer=False)
    assert isinstance(reader.state(launch(), stop(), covered).state, Ended)


def test_a_running_descendant_holds_its_parent_and_an_ended_one_does_not(reader: Reader) -> None:
    reader.turns["u"] = "inProgress"
    child = [launch(CHILD, parent=LAUNCHER, native=True), *work(CHILD)]
    assert isinstance(reader.state(launch(), stop(), *child).state, Running)
    over = [launch(CHILD, parent=LAUNCHER, native=True), *work(CHILD, ended=a.Terminal.COMPLETED)]
    assert isinstance(reader.state(launch(), stop(), *over).state, Ended)


def test_a_native_attempt_ends_with_its_turn_with_no_claude_stop(reader: Reader) -> None:
    native = [launch(native=True), *work(ended=a.Terminal.COMPLETED)]
    assert isinstance(reader.state(*native).state, Ended)


def test_a_native_attempt_with_a_submission_in_doubt_is_unknown(reader: Reader) -> None:
    assert isinstance(reader.state(launch(native=True), *work(accepted=False)).state, Unknown)


def test_a_native_attempt_with_no_reservation_is_unknown(reader: Reader) -> None:
    assert isinstance(reader.state(launch(native=True)).state, Unknown)


def test_a_closed_ticket_ends_a_plain_attempt_but_not_a_running_turn(reader: Reader) -> None:
    reader.turns["u"] = "inProgress"
    closed = {"9-1": 9.0}
    assert isinstance(reader.state(launch(), closes=closed).state, Ended)
    assert isinstance(reader.state(*work(), closes=closed).state, Running)


def test_a_refused_message_to_an_ended_attempt_is_its_refusal(reader: Reader) -> None:
    refused = a.Message(source="m", at=10.0, agent=OP, recipient=LAUNCHER, text="x",
                        outcome=a.Outcome.REFUSED, delivery="d", call="c")
    read = reader.state(launch(), stop(), refused)
    assert read.state == Ended(None, 10.0)
    assert not occupies(read)


def test_a_stopped_attempt_with_work_of_its_own_running_waits_on_it(reader: Reader) -> None:
    read = reader.state(launch(), stop(), live=frozenset({LAUNCHER}))
    assert isinstance(read.state, Running) and read.state.waits is Waits.STILL_RUNNING


@pytest.mark.parametrize("awaited", [True, False])
def test_only_an_agent_whose_result_was_awaited_is_among_the_ended_it_reports(
        reader: Reader, awaited: bool) -> None:
    attempt_record.Record().append(launch(), stop())
    built = Agent(LAUNCHER, OP, Role.CODE_EDITOR, "9-1", "", 0.5, 0.5, Running(Waits.AT_WORK), (), True,
                  awaited=awaited)
    read = operator_state.ends_read([built], [], [], 100.0, [], closes={})
    assert isinstance(read.agents[0].state, Ended)
    assert (LAUNCHER in read.ended) is awaited


def test_a_stopped_record_runs_while_the_transcript_of_another_session_shows_its_work_open(
        reader: Reader, monkeypatch: pytest.MonkeyPatch) -> None:
    elsewhere_reads = script("elsewhere_reads")
    monkeypatch.setattr(elsewhere_reads, "launched_find", lambda aid: Path("/run"))
    monkeypatch.setattr(elsewhere_reads, "work_open", lambda path, undecided: True)
    built = Agent(LAUNCHER, OP, Role.CODE_EDITOR, "9-1", "", 0.5, 0.5, Running(Waits.AT_WORK), (), True)
    working = elsewhere_reads.working([built], [])
    assert working == {LAUNCHER}
    attempt_record.Record().append(launch(), stop())
    read = operator_state.attempt_reads([built], live=working, home=reader.tmp_path)
    assert isinstance(read.agents[0].state, Running)


def test_a_transcript_that_cannot_be_read_counts_as_working_and_is_named(
        reader: Reader, monkeypatch: pytest.MonkeyPatch) -> None:
    elsewhere_reads = script("elsewhere_reads")

    def refuse(aid: str) -> Path:
        raise OSError("unreadable")

    monkeypatch.setattr(elsewhere_reads, "launched_find", refuse)
    built = Agent(LAUNCHER, OP, Role.CODE_EDITOR, "9-1", "", 0.5, 0.5, Running(Waits.AT_WORK), (), True)
    undecided: list[str] = []
    assert elsewhere_reads.working([built], undecided) == {LAUNCHER}
    assert len(undecided) == 1 and "unreadable" in undecided[0]


def test_a_probe_of_the_work_lock_leaves_its_probe_lock_free(reader: Reader) -> None:
    path = attempt_record.seat_path(SEAT)
    with attempt_record.seat_lock(SEAT):
        pass
    assert not attempt_record.lock_held(path)
    with path.with_suffix(".probe.lock").open("a") as probe:
        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
