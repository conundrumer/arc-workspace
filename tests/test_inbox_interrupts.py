"""Accepted-message races and incomplete transcript records."""

import json
import threading
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
inboxes = script("accepted_messages")
interrupts = script("read_interrupts")
loop = script("operate_loop")
journal = script("step_journal")
folds = script("transcript_folds")
reads = script("state_reads")

ME = "a0123456789abcdef"
CHILD = "a1123456789abcdef"


def row(path: Path, entry: dict, complete: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(entry) + ("\n" if complete else ""))


def call(path: Path, ident: str = "call", tool: str = "SubagentHandback") -> None:
    row(path, {"type": "assistant", "timestamp": "2026-10-20T00:00:02Z",
               "message": {"content": [{"type": "tool_use", "id": ident,
                 "name": tool, "input": {"to": ME}}]}})


def result(path: Path, ident: str = "call", success: bool = True,
           message: str = "Report delivered", complete: bool = True,
           timestamp: str = "2026-10-20T00:00:03Z") -> None:
    row(path, {"type": "user", "timestamp": timestamp,
        "message": {"content": [{"type": "tool_result", "tool_use_id": ident}]},
        "toolUseResult": {"success": success, "message": message}}, complete)


@pytest.fixture
def inbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    session = tmp_path / "session"
    own = session / "subagents" / f"agent-{ME}.jsonl"
    child = own.with_name(f"agent-{CHILD}.jsonl")
    row(own, {"type": "user", "timestamp": "2026-10-20T00:00:01Z"})
    monkeypatch.setattr(inboxes, "run_sessions", lambda path: [session])
    monkeypatch.setattr(inboxes, "launched_or_resumed", lambda *args, **kwargs: {CHILD})
    return inboxes.Inbox(own, []), child


def test_pending_and_partial_acceptance(inbox) -> None:
    reader, child = inbox
    call(child)
    result(child, complete=False)
    assert not reader.accepted()
    with child.open("a") as stream:
        stream.write("\n")
    assert reader.accepted()


@pytest.mark.parametrize("tool,success,message,timestamp", [
    ("SubagentHandback", False, "Report delivered", "2026-10-20T00:00:03Z"),
    ("SubagentHandback", True, "Refused", "2026-10-20T00:00:03Z"),
    ("SendMessage", False, "Message queued", "2026-10-20T00:00:03Z"),
    ("SendMessage", True, "Message queued", "2026-10-20T00:00:00Z"),
    ("SendMessage", True, "Message queued", "2026-10-20T00:00:01.500Z"),
])
def test_unaccepted_results_do_not_release(inbox, tool, success, message, timestamp) -> None:
    reader, child = inbox
    call(child, tool=tool)
    result(child, success=success, message=message, timestamp=timestamp)
    assert not reader.accepted()


def test_fork_prefix_and_replacement(inbox) -> None:
    reader, child = inbox
    child.with_suffix(".meta.json").write_text(json.dumps({"isFork": True, "toolUseId": "fork"}))
    call(child)
    result(child)
    assert not reader.accepted()
    result(child, "fork", message="launched")
    call(child, "own")
    result(child, "own")
    assert reader.accepted()
    replacement = child.with_suffix(".new")
    call(replacement, "new", "SendMessage")
    result(replacement, "new", message="Message queued")
    replacement.replace(child)
    child.with_suffix(".meta.json").unlink()
    assert reader.accepted()


def test_initial_acceptance_needs_no_state(inbox, monkeypatch: pytest.MonkeyPatch) -> None:
    reader, child = inbox
    call(child)
    result(child)
    monkeypatch.setattr(loop, "Inbox", lambda *args: reader)
    monkeypatch.setattr(loop, "find", lambda me: reader.path)
    monkeypatch.setattr(loop, "single_instance", lambda me: None)
    monkeypatch.setattr(loop, "arm_watchdog", lambda me: None)
    def never(deadline):
        pytest.fail("acceptance must precede state assembly")
    assert isinstance(loop.waited(ME, never, lambda out: True), loop.MessageAccepted)


def test_slow_inbox_scan_leaves_time_for_the_read(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 0.0
    scans = 0

    def accepted():
        nonlocal now, scans
        scans += 1
        now += 2.0
        if scans > 2:
            raise TimeoutError("inbox scans exhausted the foreground bound")
        return False

    class SlowInbox:
        def __init__(self, *args):
            pass

        def accepted(self):
            return accepted()

    monkeypatch.setattr(loop, "Inbox", SlowInbox)
    monkeypatch.setattr(loop, "find", lambda me: Path(me))
    monkeypatch.setattr(loop, "single_instance", lambda me: None)
    monkeypatch.setattr(loop, "arm_watchdog", lambda me: None)
    monkeypatch.setattr(interrupts.time, "monotonic", lambda: now)

    def read(deadline):
        for _ in range(10):
            interrupts.checkpoint()
        return "planned"

    assert loop.waited(ME, read, lambda out: True) == "planned"


def test_acceptance_during_read_has_no_full_confirmation(inbox, monkeypatch: pytest.MonkeyPatch) -> None:
    reader, child = inbox
    monkeypatch.setattr(loop, "Inbox", lambda *args: reader)
    monkeypatch.setattr(loop, "find", lambda me: reader.path)
    monkeypatch.setattr(loop, "single_instance", lambda me: None)
    monkeypatch.setattr(loop, "arm_watchdog", lambda me: None)
    entered, release = threading.Event(), threading.Event()
    def sender():
        assert entered.wait(5)
        call(child)
        result(child)
        release.set()
    sender_thread = threading.Thread(target=sender)
    sender_thread.start()
    def state(deadline):
        entered.set()
        assert release.wait(5)
        # Advance the checkpoint clock without an elapsed-time assertion.
        interrupts._due.set(0)
        interrupts.checkpoint()
        pytest.fail("an incomplete read must unwind")
    try:
        assert isinstance(loop.waited(ME, state, lambda out: True), loop.MessageAccepted)
    finally:
        sender_thread.join(5)


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


@pytest.mark.parametrize("phase", ["pacing", "journal", "partial"])
def test_wait_phases_release_without_another_state(inbox, monkeypatch: pytest.MonkeyPatch, phase: str) -> None:
    reader, child = inbox
    def accept():
        call(child)
        result(child)
        interrupts._due.set(0)
    with pytest.raises(interrupts.Accepted):
        with interrupts.scope(reader.accepted):
            if phase == "pacing":
                class Events:
                    def wait(self, seconds):
                        accept()
                    def take(self):
                        return set()
                reads_at = loop.Reads(loop.time.monotonic() + 90)
                reads_at.changed_paths(Events(), loop.time.monotonic() - 15, 0)
            elif phase == "journal":
                def running(*args):
                    accept()
                    return [object()]
                monkeypatch.setattr(journal, "running", running)
                loop.ran(child.parent, loop.time.monotonic() + 90)
            else:
                calls = 0
                def state(deadline):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        accept()
                        interrupts.checkpoint()
                    assert calls <= 2, "partial acceptance must bypass full confirmation"
                    return False
                monkeypatch.setattr(loop.Reads, "after", lambda *args: (True, {str(child)}))
                loop.watched(state, bool, 90)
