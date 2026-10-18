"""Reads that hold back a step or refuse a write, each of whose faults
would go on with no sign: a question ticket filed after the brief of the
last ticket analyst on a change held as judged, a draft given to a
second analyst while the one that filed it still runs, and a refused
`case` call that writes its evidence all the same."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from handbook.paths import scripts_importable
from operations.briefs import QUESTIONS
from operations.change_holds import questions_given
from operations.drafts import analyst_writes
from operations.state import Agent, State, Ticket
from tests.conftest import script


def ticket(number: str) -> Ticket:
    return cast(Ticket, SimpleNamespace(number=number))


@pytest.mark.parametrize(("given", "held"), [(["9-2"], False), (["9-2", "9-3"], True)])
def test_question_hold_needs_each_question_in_the_brief(given: list[str], held: bool) -> None:
    brief = "Change 9-1.\n" + QUESTIONS.format(questions=", ".join(given)) + "\nEnd.\n"
    analyst = cast(Agent, SimpleNamespace(brief=brief))
    assert questions_given(analyst, [ticket("9-2"), ticket("9-3")]) is held


def line(time: float, agent: str, agent_id: str | None, note: str) -> SimpleNamespace:
    return SimpleNamespace(time=time, agent=agent, agent_id=agent_id, note=note)


@pytest.mark.parametrize(("launched", "pending", "waits"),
                         [(10.0, True, True), (30.0, True, False), (10.0, False, False)])
def test_draft_waits_on_analyst_that_may_have_filed_it(launched: float, pending: bool,
                                                      waits: bool) -> None:
    analyst = SimpleNamespace(launched=launched, pending=pending)
    state = cast(State, SimpleNamespace(analysts=lambda: [(analyst, None, [])]))
    t = cast(Ticket, SimpleNamespace(log=[line(20.0, "ticket-analyst", None, "filed")]))
    assert analyst_writes(state, t) is waits


def test_refused_case_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scripts_importable()
    module: Any = script("ticket_cases")
    watch: Any = script("ticket_watch")
    (tmp_path / "deferred").mkdir()
    path = tmp_path / "deferred" / "9-1_operations_slow_code-editor.md"
    text = ("---\nkind: delay\n---\n# t: w\n\n## Log\n"
            "2026-10-17T00:00:00Z deferred [code-editor]: filed\n\n## Evidence\ne\n")
    path.write_text(text)
    monkeypatch.setattr(module, "case_loss",
                        lambda run, start, end, undecided: watch.Case(run, start, end, None, 0.0))
    monkeypatch.setattr("sys.stdin", SimpleNamespace(read=lambda: "more\n"))
    with pytest.raises(module.Refused):
        module.case_command(tmp_path, "9-1", "code-editor", "a" * 17, "1", "2")
    assert path.read_text() == text
