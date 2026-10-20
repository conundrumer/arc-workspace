"""Refusals and forced interleavings at the ticket control boundary."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()

from operations.roles import Role

codex_agent = script("codex_agent")
ticket = script("codex_ticket")
Assignment = ticket.Assignment
Binding = ticket.Binding
Refused = ticket.Refused
Store = ticket.Store
allocate = ticket.allocate


def assignment(tmp_path: Path, store, role: Role = Role.CODE_EDITOR):
    agent = allocate(tmp_path)
    brief = tmp_path / f"{agent}.md"
    brief.write_text("assigned input")
    out = Assignment("11-2572", "a0123456789abcdef", agent, role, 1,
                     tmp_path, brief, tmp_path / agent, tmp_path / f"{agent}.txt",
                     hashlib.sha256(brief.read_bytes()).hexdigest())
    store.file(out)
    return out


def test_lock_refuses_without_queue_or_state_change(tmp_path: Path):
    store = Store(tmp_path / "ticket")
    root = assignment(tmp_path, store)
    before = (store.path / "state.json").read_bytes()
    with store.locked():
        with pytest.raises(Refused):
            Store(store.path).reserve(root)
    assert (store.path / "state.json").read_bytes() == before


def test_root_cannot_resume_until_interrupted_child_ends(tmp_path: Path):
    store = Store(tmp_path / "ticket")
    root = assignment(tmp_path, store)
    token = store.reserve(root)
    store.accepted(root.agent, token, "native-root", "root-turn")
    child = assignment(tmp_path, store, Role.ITEM_CHECKER)
    child_token = store.reserve(child, root.agent)
    store.accepted(child.agent, child_token, "native-child", "child-turn")
    assert store.interrupting(root.agent) == ("native-root", "root-turn")
    store.ended(root.agent, "root-turn", "interrupted")
    later = replace(root, revision=2)
    store.file(later)
    with pytest.raises(Refused):
        store.reserve(later)
    with pytest.raises(Refused):
        store.reserve(assignment(tmp_path, store, Role.ITEM_CHECKER), child.agent)
    store.ended(child.agent, "child-turn", "completed")
    store.ended(child.agent, "child-turn", "completed")
    resumed = store.reserve(later)
    with pytest.raises(Refused):
        store.accepted(root.agent, resumed, "replacement-root", "next-turn")
    store.accepted(root.agent, resumed, "native-root", "next-turn")
    with pytest.raises(Refused):
        store.target(root.agent, child.agent)
    old_child = replace(child, revision=2)
    store.file(old_child)
    with pytest.raises(Refused):
        store.reserve(old_child, root.agent)


def test_unknown_submission_stays_interrupted(tmp_path: Path):
    store = Store(tmp_path / "ticket")
    root = assignment(tmp_path, store)
    token = store.reserve(root)
    with pytest.raises(Refused):
        store.interrupting(root.agent)
    store.accepted(root.agent, token, "native-root", "root-turn")
    state = json.loads((store.path / "state.json").read_text())
    assert state["agents"][root.agent]["phase"] == "interrupting"
    with pytest.raises(Refused):
        store.reserve(assignment(tmp_path, store, Role.ITEM_CHECKER), root.agent)


def test_cross_ticket_target_and_scratch_reuse_refused(tmp_path: Path):
    first = Store(tmp_path / "first")
    second = Store(tmp_path / "second")
    root = assignment(tmp_path, first)
    other = assignment(tmp_path, second)
    token = first.reserve(root)
    first.accepted(root.agent, token, "native-root", "turn")
    with pytest.raises(Refused):
        first.target(root.agent, other.agent)
    with pytest.raises(Refused):
        second.file(replace(other, revision=2, scratch=root.scratch))
    binding = Binding.read(root.scratch)
    assert binding is not None and binding.store == first.path


def test_legacy_steer_and_resume_do_not_submit(tmp_path: Path):
    store = Store(tmp_path / "ticket")
    root = assignment(tmp_path, store)
    (root.scratch / "codex-session").write_text("native-root")

    def forbidden():
        pytest.fail("legacy mutation reached transport")

    before = (store.path / "state.json").read_bytes()
    with pytest.raises(Refused):
        codex_agent.control(["steer", str(root.scratch), "correction"], forbidden)
    with pytest.raises(Refused):
        codex_agent.run("code-editor", root.scratch, root.brief, "model", "high", "input",
                        tmp_path, tmp_path, tmp_path, tmp_path, transport=forbidden, resume=True)
    assert (store.path / "state.json").read_bytes() == before


def test_interrupt_invalidates_before_transport_failure(tmp_path: Path):
    store = Store(tmp_path / "ticket")
    root = assignment(tmp_path, store)
    token = store.reserve(root)
    store.accepted(root.agent, token, "native-root", "turn")

    def unavailable():
        raise OSError("daemon unavailable")

    with pytest.raises(OSError):
        codex_agent.control(["interrupt", str(root.scratch)], unavailable)
    state = json.loads((store.path / "state.json").read_text())
    assert state["agents"][root.agent]["phase"] == "interrupting"
    assert state["agents"][root.agent]["validated"] is False
