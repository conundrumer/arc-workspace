"""What `turn_read` gives for an attempt whose record shows an accepted Codex turn with no end."""

import fcntl
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from operations import attempts as a
from operations.roles import CODEX_LAUNCHER, Described, Role
from tests.conftest import script

scripts_importable()
operator_state = script("operator_state")
attempt_record = script("attempt_record")
codex_daemon = script("codex_daemon")

LAUNCHER = "a0000000000000c01"
SEAT = Described(Role.CODE_EDITOR, "9-1")


def open_turn(tmp_path: Path) -> a.Attempt:
    return a.fold([
        a.Launched(source="launch", at=1.0, agent=LAUNCHER, seat=SEAT, parent="op",
                   agent_type=CODEX_LAUNCHER, transport=a.Transport.CLAUDE, scratch=str(tmp_path)),
        a.Reserved(source="reserved", at=2.0, agent=LAUNCHER, reservation="r", revision=0),
        a.Accepted(source="accepted", at=3.0, agent=LAUNCHER, reservation="r", thread="t", turn="u"),
    ])[LAUNCHER]


def daemon(monkeypatch: pytest.MonkeyPatch, answer) -> None:
    def status(thread: str, turn: str):
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(codex_daemon, "turn_status", status)


def test_a_daemon_that_does_not_read_gives_its_error_alone(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon(monkeypatch, OSError("daemon unreachable"))
    read = operator_state.turn_read(open_turn(tmp_path), tmp_path)
    assert read.end is operator_state.CodexEnd.UNKNOWN
    assert read.why.endswith("daemon unreachable") and read.scratch == tmp_path


@pytest.mark.parametrize("answer", ["completed", None])
def test_a_turn_the_daemon_gives_over_is_terminal_evidence(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str | None) -> None:
    daemon(monkeypatch, answer)
    assert operator_state.turn_read(open_turn(tmp_path), tmp_path).end is operator_state.CodexEnd.DEAD


def test_a_held_work_lock_gives_a_running_turn_without_the_daemon(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon(monkeypatch, AssertionError("the daemon must not be read"))
    attempt = open_turn(tmp_path)
    path = attempt_record.seat_path(SEAT)
    path.parent.mkdir(parents=True)
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert operator_state.turn_read(attempt, tmp_path).end is operator_state.CodexEnd.LIVE
