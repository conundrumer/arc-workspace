"""Partial rollout files and the sources a spend read watches."""

import json
from datetime import datetime, timezone


from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
spends = script("spends")
rollout = script("codex_rollout")
state_reads = script("state_reads")


def at(second):
    return datetime.fromtimestamp(second, timezone.utc).isoformat()


def usage(total):
    return {"input_tokens": total - 2, "cached_input_tokens": 0,
            "output_tokens": 2, "reasoning_output_tokens": 1, "total_tokens": total}


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
