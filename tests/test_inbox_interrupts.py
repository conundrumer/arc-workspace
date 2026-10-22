"""Interrupted reads and the record of a launch."""

import json
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
interrupts = script("read_interrupts")
journal = script("step_journal")
folds = script("transcript_folds")
reads = script("state_reads")

ME = "a0123456789abcdef"


def row(path: Path, entry: dict, complete: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(entry) + ("\n" if complete else ""))


def test_launch_record_is_atomic_with_inbox_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations.steps import Bash
    accepted = False
    append = journal.append
    def held_append(*args):
        nonlocal accepted
        accepted = True
        interrupts._due.set(0)
        interrupts.checkpoint()
        return append(*args)
    monkeypatch.setattr(journal, "append", held_append)
    with pytest.raises(interrupts.Accepted):
        with interrupts.scope(lambda: accepted):
            journal.start_run(tmp_path, Bash("printf kept", "check", occasion="test"), ME, tmp_path, 1.0)
    records = journal.records(tmp_path)
    assert len(records) == 1
    run = records[0].run
    assert run is not None
    # The foreground check waits for the command it started.
    import os
    os.waitpid(run.pid, 0)
    assert run.status.read_text().strip() == "0"
    assert run.output.read_text() == "kept"


def test_interrupted_fold_does_not_mutate_cached_value(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    fail = False
    def step(state, path, i, entry):
        state.append(entry["value"])
        if fail and entry["value"] == 2:
            raise interrupts.Accepted()
    @reads.state_cache(None)
    def read():
        return folds.fold(step, list, path, [path])
    row(path, {"value": 1})
    reads.new_state()
    before = read()
    row(path, {"value": 2})
    fail = True
    with pytest.raises(interrupts.Accepted):
        reads.new_state()
        read()
    assert before == [1]
    fail = False
    reads.new_state()
    assert read() == [1, 2]


def test_request_scopes_restore_checks_and_poll_deadlines(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(interrupts.time, "monotonic", lambda: now[0])
    checked = []
    with interrupts.request_scope(lambda: checked.append("outer")):
        interrupts.checkpoint()
        with interrupts.request_scope(lambda: checked.append("inner")):
            interrupts.checkpoint()
        interrupts.checkpoint()
        assert checked == ["outer", "inner"]
        interrupts.checkpoint(force=True)
        now[0] += 0.1
        interrupts.checkpoint()
    interrupts.checkpoint(force=True)
    with interrupts.request_scope(lambda: checked.append("later")):
        interrupts.checkpoint()
    assert checked == ["outer", "inner", "outer", "outer", "later"]


def test_request_cancellation_waits_for_persistent_write_and_restores_scope():
    events = []
    invalid = False

    def check():
        if invalid:
            raise RuntimeError("invalid request")

    @interrupts.deferred
    def write():
        nonlocal invalid
        invalid = True
        interrupts.checkpoint(force=True)
        events.append("written")

    with pytest.raises(RuntimeError):
        with interrupts.request_scope(check):
            write()
    interrupts.checkpoint(force=True)
    assert events == ["written"]


@pytest.mark.parametrize("force", [False, True])
def test_invalid_request_is_refused_before_the_next_inbox_poll(monkeypatch, force):
    now = [100.0]
    invalid = False
    inbox_checks = []
    monkeypatch.setattr(interrupts.time, "monotonic", lambda: now[0])

    def check():
        if invalid:
            raise RuntimeError("invalid request")

    def poll_inbox():
        inbox_checks.append(True)
        return False

    with interrupts.request_scope(check), interrupts.scope(poll_inbox):
        invalid = True
        now[0] += 0.1
        with pytest.raises(RuntimeError):
            interrupts.checkpoint(force=force)
    assert inbox_checks == [True]
