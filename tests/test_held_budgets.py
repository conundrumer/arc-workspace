"""Admission changes must reach the budgets used to rank and take changes."""

from dataclasses import replace
from pathlib import Path

import pytest

from handbook.paths import scripts_importable
from tests.conftest import script
from tests.test_ticket_stall import state


scripts_importable()


@pytest.mark.parametrize("hold", ["scope", "pause", "takes", "pace", "codex", "none"])
def test_take_budgets_follow_the_completed_states_admission(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hold: str) -> None:
    from operations import change_take, codex_mode
    from operations.pacing import Until, Usage
    from operations.state import Budget, Message, NotComputed

    assembly = script("state_assembly")
    budgets = script("held_budgets")
    s = state(tmp_path, {"approved/9-1_change_x_ticket-analyst.md": ""})
    messages = (() if hold == "scope" else
                (Message(s.me, 1.0, None, "Op scope: all."),))
    if hold == "pause":
        messages += (Message(s.me, 2.0, None, "Op pause."),)
    s = replace(s, transcripts=replace(s.transcripts, messages=messages),
                computed=replace(s.computed, pace=NotComputed()))
    monkeypatch.setattr(codex_mode, "enabled", lambda: hold == "codex")
    monkeypatch.setattr(assembly, "read_runs", lambda _: (
        {}, {"run": frozenset()} if hold == "takes" else {}))
    monkeypatch.setattr(assembly, "pace", lambda _: lambda usage: Until(
        s.now + 1 if hold in ("pace", "codex") else 0.0))
    monkeypatch.setattr(assembly, "to_settle", lambda *args: ())
    monkeypatch.setattr(assembly, "audit_window_read", lambda *args: NotComputed())
    b = Budget(2.0, 100.0)
    monkeypatch.setattr(budgets, "budget", lambda *args: b)

    computed = assembly.computed_read(s, tmp_path / "tickets", [], Usage(s.now, {}))
    complete = replace(s, computed=computed)
    expected = {"9-1": b} if hold in ("none", "codex") else {}
    assert computed.budgets == expected
    assert {t.number for t in change_take.takeable(complete)} == set(expected)
    assert (change_take.take(complete) is not None) is bool(expected)
