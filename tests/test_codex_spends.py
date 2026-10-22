"""Ambiguous attribution, partial files and settled record invalidation."""

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from handbook.paths import scripts_importable
from ticketing.subscription import CLAUDE_LIST_TO_SUBSCRIPTION
from tests.conftest import script

scripts_importable()
spends = script("spends")
measure = script("codex_spends")
rollout = script("codex_rollout")
state_reads = script("state_reads")


def at(second):
    return datetime.fromtimestamp(second, timezone.utc).isoformat()


def launch(scratch, second=10, role="code-editor", call="call"):
    return {"type": "assistant", "timestamp": at(second), "message": {"content": [
        {"type": "tool_use", "name": "Bash", "id": call, "input": {"command":
         f"uv run python scripts/codex_agent.py {role} {scratch} /tmp/brief model high"}}]}}


def usage(total):
    return {"input_tokens": total - 2, "cached_input_tokens": 0,
            "output_tokens": 2, "reasoning_output_tokens": 1, "total_tokens": total}


def record(total=12, turn="turn", start=11):
    return {"thread": "thread", "turn": turn, "usage": usage(total),
            "usage_reason": None, "running": False, "started": start, "ended": start + 1}


def test_ambiguous_reused_scratch_refuses_lifetime_usage(tmp_path, monkeypatch):
    launcher = tmp_path / "launcher.jsonl"
    launcher.write_text("")
    monkeypatch.setattr(measure, "run_entries", lambda _: iter([launch(tmp_path)]))
    # Historical records give no accepted turn or call interval. An extra record
    # must not be assigned to the launcher's single call.
    (tmp_path / "codex-events.jsonl").write_text(
        '\n'.join(json.dumps({"thread": "thread", "output": "", "ok": True})
                  for _ in range(2)) + '\n')
    result = spends.codex_spend({launcher: "code-editor"}, home=tmp_path / "home")
    assert result.status == "unknown"
    assert result.totals().total_tokens is None
    assert result.sources[0].reason is not None


def test_partial_rollout_tail_cannot_complete_a_turn(tmp_path):
    directory = tmp_path / ".codex" / "sessions"
    directory.mkdir(parents=True)
    path = directory / "rollout-now-thread.jsonl"
    payloads = [
        {"type": "task_started", "turn_id": "a"},
        {"type": "token_count", "info": {"total_token_usage": usage(12),
                                         "last_token_usage": usage(12)}},
        {"type": "token_count", "info": {"total_token_usage": usage(12),
                                         "last_token_usage": usage(12)}},
        {"type": "task_complete", "turn_id": "a"},
        {"type": "task_started", "turn_id": "b"},
        {"type": "token_count", "info": {"total_token_usage": usage(22)}},
    ]
    lines = [json.dumps({"type": "event_msg", "timestamp": at(10 + n), "payload": p})
             + '\n' for n, p in enumerate(payloads)]
    path.write_text(''.join(lines) + '{"type":')
    turns = rollout.turns("thread", tmp_path)
    assert [t.usage.total_tokens for t in turns] == [12, 10]
    assert turns[-1].ended is None
    path.write_text(''.join(lines) + json.dumps({"type": "event_msg", "timestamp": at(20),
                    "payload": {"type": "turn_aborted", "turn_id": "b"}}) + '\n')
    assert rollout.turns("thread", tmp_path)[-1].ended == 20


def test_legacy_record_refresh_and_source_invalidation(tmp_path, monkeypatch):
    closed = tmp_path / "closed"
    closed.mkdir()
    ticket = closed / "11-1_change_example_code-editor.md"
    ticket.write_text("ticket")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    launcher = tmp_path / "launcher.jsonl"
    launcher.write_text("launcher")
    entries = [launch(scratch)]
    events = scratch / "codex-events.jsonl"
    events.write_text(json.dumps(record()) + '\n')
    monkeypatch.setattr(measure, "run_entries", lambda _: iter(entries))
    monkeypatch.setattr(spends, "known_owners", lambda *_: {launcher: "code-editor"})
    monkeypatch.setattr(spends, "first_time", lambda _: 10)
    monkeypatch.setattr(spends, "last_time", lambda _: 20)
    monkeypatch.setattr(spends, "cost_of", lambda *_: None)
    monkeypatch.setattr(spends, "all_stopped", lambda *_: True)
    monkeypatch.setattr(spends, "held_closed", lambda _: SimpleNamespace(log=[SimpleNamespace(
        status=spends.Status.CLOSED, resolution=spends.Resolution.FIXED,
        note="fixed 11-1 commit launcher", time=30)]))
    monkeypatch.setattr(spends, "file_text", lambda p: p.read_text())
    monkeypatch.setattr(spends, "stat_read", lambda p: p.stat() if p.exists() else None)
    saved = spends.spend_record(ticket)
    saved.parent.mkdir()
    saved.write_text(json.dumps({"dollars": 2.0, "seconds": 99.0, "by_role": {"code-editor": 2.0}}))
    first = spends.change_spend(ticket, [])
    assert first.dollars == pytest.approx(2.0 * CLAUDE_LIST_TO_SUBSCRIPTION) and first.seconds == 99.0
    assert first.codex.totals().total_tokens == 12
    assert spends.change_spend(ticket, []).codex.totals().total_tokens == 12
    # A resumed call invalidates the record; repeated reads do not add it twice.
    entries.append(launch(scratch, 20, call="resume"))
    launcher.write_text("launcher resumed")
    with events.open("a") as out:
        out.write(json.dumps(record(22, "resumed", 21)) + '\n')
    state_reads.new_state()
    resumed = spends.change_spend(ticket, [])
    assert resumed.codex.totals().total_tokens == 34
    assert spends.change_spend(ticket, []).codex.totals().total_tokens == 34
    # JSON null does not prove zero; unknown dollars preserve measured tokens.
    saved.write_text('null\n')
    state_reads.new_state()
    assert spends.change_spend(ticket, []) is None
    measured = spends.recorded_spend(ticket)
    assert measured.codex.totals().total_tokens == 34


def test_absent_initial_boundary_is_unknown(tmp_path):
    directory = tmp_path / ".codex" / "sessions"
    directory.mkdir(parents=True)
    path = directory / "rollout-now-thread.jsonl"
    payloads = [{"type": "task_started", "turn_id": "turn"},
                {"type": "token_count", "info": {"total_token_usage": usage(120)}}]
    path.write_text(''.join(json.dumps({"type": "event_msg", "timestamp": at(10),
                                       "payload": p}) + '\n' for p in payloads))
    assert rollout.turns("thread", tmp_path)[0].usage is None


def test_unresolved_sources_follow_directory_changes(tmp_path, monkeypatch):
    """Shared discovery must keep watching for missing transcripts at later states."""
    projects = tmp_path / "projects"
    session = projects / "project" / "session"
    session.mkdir(parents=True)
    (session / "transcript.jsonl").write_text("")
    external = tmp_path / "external"
    (external / "child").mkdir(parents=True)
    link = projects / "linked"
    link.symlink_to(external, target_is_directory=True)
    ticket = tmp_path / "ticket.md"
    ticket.write_text("")
    monkeypatch.setattr(spends, "project_dirs", lambda: [projects])

    def inputs():
        return spends.unresolved_spend(ticket, [], 0).codex.inputs

    watched = {ticket, projects, session.parent, session, link}
    state_reads.new_state()
    assert inputs() == tuple(sorted(spends.fingerprint(p) for p in watched))

    added = session / "subagents"
    added.mkdir()
    watched.add(added)
    state_reads.new_state()
    assert inputs() == tuple(sorted(spends.fingerprint(p) for p in watched))

    added.rmdir()
    link.unlink()
    watched -= {added, link}
    state_reads.new_state()
    assert inputs() == tuple(sorted(spends.fingerprint(p) for p in watched))


def test_shared_spend_inputs_are_statted_once_and_refresh_at_next_state(tmp_path, monkeypatch):
    """Old tickets share watched directories; their revisions still invalidate."""
    source = tmp_path / "source"
    source.mkdir()
    import os
    original = os.stat
    seen = []

    def stat(path, *args, **kwargs):
        if str(path) == str(source):
            seen.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", stat)
    state_reads.new_state()
    before = spends.fingerprint(source)
    assert all(spends.fingerprint(source) == before for _ in range(100))
    assert len(seen) == 1
    (source / "new").write_text("")
    state_reads.new_state()
    assert spends.fingerprint(source) != before


def test_spend_history_is_shared_by_budgets_and_rechecked_next_state(tmp_path, monkeypatch):
    ticket = tmp_path / "closed/11-1_change_example_code-editor.md"
    ticket.parent.mkdir()
    ticket.write_text("ticket")
    monkeypatch.setattr(spends, "project_dirs", lambda: [])
    monkeypatch.setattr(spends, "held_closed", lambda _: SimpleNamespace(log=[SimpleNamespace(
        status=spends.Status.CLOSED, resolution=spends.Resolution.FIXED,
        note="fixed 11-1 commit", time=30)]))
    saved = []
    monkeypatch.setattr(spends, "write_record", lambda _, value: saved.append(value))
    state_reads.new_state()
    assert spends.change_spend(ticket, []) is None
    assert spends.change_spend(ticket, []) is None
    assert len(saved) == 1
    ticket.write_text("changed ticket")
    state_reads.new_state()
    assert spends.change_spend(ticket, []) is None
    assert len(saved) == 2
    assert saved[0]["codex"]["inputs"] != saved[1]["codex"]["inputs"]


def test_shared_owner_walk_refreshes_after_a_source_changes(tmp_path, monkeypatch):
    source = tmp_path / "owner"
    source.write_text("code-editor")
    walked = []

    def children(*_):
        walked.append(True)
        return []

    monkeypatch.setattr(spends, "held_find", lambda _: source)
    monkeypatch.setattr(spends, "counted_type", lambda *_: source.read_text())
    monkeypatch.setattr(spends, "runs_under", children)
    state_reads.new_state()
    walked.clear()
    assert spends.known_owners(["run"], {}) == {source: "code-editor"}
    assert spends.known_owners(["run"], {}) == {source: "code-editor"}
    assert len(walked) == 1
    source.write_text("code-reviewer")
    state_reads.new_state()
    assert spends.known_owners(["run"], {}) == {source: "code-reviewer"}


def test_recovered_record_refreshes_after_rollout_arrival_and_append(tmp_path, monkeypatch):
    ticket = tmp_path / 'closed/11-1_change_example_code-editor.md'
    ticket.parent.mkdir()
    ticket.write_text('ticket')
    launcher = tmp_path / 'launcher.jsonl'
    launcher.write_text('launcher')
    (tmp_path / 'codex-session').write_text('thread\n')
    directory = tmp_path / '.codex/sessions'
    directory.mkdir(parents=True)
    monkeypatch.setattr(measure, 'run_entries', lambda _: iter([
        launch(tmp_path), {'type': 'user', 'timestamp': at(30)}]))
    monkeypatch.setattr(spends, 'known_owners', lambda *_: {launcher: 'code-editor'})
    monkeypatch.setattr(spends, 'priced', lambda owner, _, before: spends.Spend(
        2.0, 99.0, {'code-editor': 2.0}, spends.codex_spend(owner, before, tmp_path)))
    monkeypatch.setattr(spends, 'all_stopped', lambda *_: True)
    monkeypatch.setattr(spends, 'held_closed', lambda _: SimpleNamespace(log=[SimpleNamespace(
        status=spends.Status.CLOSED, resolution=spends.Resolution.FIXED,
        note='fixed 11-1 commit launcher', time=30)]))
    state_reads.new_state()
    assert spends.change_spend(ticket, []).codex.status == 'unknown'
    path = directory / 'rollout-now-thread.jsonl'
    path.write_text(json.dumps({'type': 'event_msg', 'timestamp': at(11),
                               'payload': {'type': 'task_started', 'turn_id': 'a'}}) + '\n')
    state_reads.new_state()
    assert spends.change_spend(ticket, []).codex.sources[0].turn == 'a'
    with path.open('a') as out:
        for second, payload in [(12, {'type': 'token_count', 'info': {
                'total_token_usage': usage(12), 'last_token_usage': usage(12)}}),
                (13, {'type': 'task_complete', 'turn_id': 'a'})]:
            out.write(json.dumps({'type': 'event_msg', 'timestamp': at(second),
                                  'payload': payload}) + '\n')
    state_reads.new_state()
    result = spends.change_spend(ticket, [])
    assert result.codex.totals().total_tokens == 12
    assert not result.codex.sources[0].running
    assert result.dollars == pytest.approx(2.0) and result.seconds == 99.0
