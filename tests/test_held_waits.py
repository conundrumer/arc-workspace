"""Reads that hold back a step or refuse a write, each of whose faults
would go on with no sign: a question ticket filed after the brief of the
last ticket analyst on a change held as judged, a draft given to a
second analyst while the one that filed it still runs, a draft whose
coordinator's findings go to a ticket reviewer, a held step on an unread
ticket file or on a ticket analyst's `unfinished:` items given to a
second analyst while one on an earlier content of that file or an earlier
reply of that analyst runs, and a refused `case` call that writes its
evidence all the same."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from handbook.paths import scripts_importable
from operations.briefs import QUESTIONS
from operations.change_holds import questions_given
from operations.drafts import analyst_writers
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
    assert bool(analyst_writers(state, t)) is waits


def test_coordinator_finding_sends_the_draft_to_an_analyst(tmp_path: Path) -> None:
    from operations.drafts import Group, Joined, draft_step
    from tests.test_unreported_agents import state, ticket as filed
    t = filed(tmp_path, "draft", "9-1_change_x_ticket-analyst.md",
              "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
              "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n"
              "2026-10-17T02:20:00Z draft [coordinator]: finding: depends-on gains 9-2\n")
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"
    assert draft_step(state(tmp_path, [t], [], w), t) == Joined(Group.WAITING, 0.0)


@pytest.mark.parametrize(("pending", "held"), [(True, True), (False, False)])
def test_unread_file_waits_on_the_analyst_of_its_earlier_content(pending: bool,
                                                                held: bool) -> None:
    from operations.briefs import held_step
    from operations.decisions import unread_steps
    from operations.handled import on_subject
    from operations.roles import Purpose

    def steps(digest: str) -> list:
        u = SimpleNamespace(path=Path("tickets/deferred/9-1_x_y.md"), why="w", digest=digest,
                            modified=0.0, session=None)
        return unread_steps(cast(State, SimpleNamespace(
            tracker=SimpleNamespace(unread=(u,)), now=1000.0)))

    earlier = steps("771036df")[0]
    analyst = SimpleNamespace(pending=pending, brief=held_step(earlier.text, "o", False, None))
    later = cast(State, SimpleNamespace(analysts=lambda: [(analyst, Purpose.STEP, ["k"])]))
    assert on_subject(later, steps("aa78d0ea")[0]) is held


@pytest.mark.parametrize(("pending", "held"), [(True, True), (False, False)])
def test_later_reply_waits_on_the_analyst_of_an_earlier_reply(tmp_path: Path, pending: bool,
                                                             held: bool) -> None:
    from operations.briefs import held_step
    from operations.roles import Purpose, Role, analyst_subject
    from operations.state import Agent as Launched, Report, Waits
    from operations.steps import Undecided
    from operations.triage import unfinished
    from tests.test_unreported_agents import ME, state, ticket as filed
    t = filed(tmp_path, "draft", "9-1_change_x_ticket-analyst.md",
              "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
              "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n")
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"
    reply = "Done.\n\n## For the coordinator\n- unfinished: item a\n"

    def analyst(replies: tuple[float, ...]) -> Launched:
        return Launched("a8e99dabca9ddb4de", ME, Role.TICKET_ANALYST,
                        analyst_subject(Purpose.DRAFT, "9-1"), "", 10.0, 10.0, None,
                        tuple(Report(r, reply) for r in replies), True)

    earlier = unfinished(state(tmp_path, [t], [analyst((100.0,))], w))
    assert isinstance(earlier, Undecided)
    on_earlier = Launched("afea5a8bdac482d84", ME, Role.TICKET_ANALYST,
                          analyst_subject(Purpose.STEP, "k"),
                          held_step(earlier.text, ME, False, None), 150.0, 150.0,
                          Waits.AT_WORK if pending else None, (), True)
    later = unfinished(state(tmp_path, [t], [analyst((100.0, 200.0)), on_earlier], w))
    assert (later is None) is held


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
