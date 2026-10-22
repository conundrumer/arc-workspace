"""Reads that hold back a step, each of whose faults would go on with no
sign: a question ticket filed after the brief of the last ticket analyst
on a change held as judged, a draft whose coordinator's findings go to a
ticket reviewer, and a held step on a ticket analyst's `unfinished:` items
given to a second analyst while one on an earlier reply of that analyst
runs."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from operations.briefs import QUESTIONS
from operations.change_holds import questions_given
from operations.state import Agent, Ticket


def ticket(number: str) -> Ticket:
    return cast(Ticket, SimpleNamespace(number=number))


@pytest.mark.parametrize(("given", "held"), [(["9-2"], False), (["9-2", "9-3"], True)])
def test_question_hold_needs_each_question_in_the_brief(given: list[str], held: bool) -> None:
    brief = "Change 9-1.\n" + QUESTIONS.format(questions=", ".join(given)) + "\nEnd.\n"
    analyst = cast(Agent, SimpleNamespace(brief=brief))
    assert questions_given(analyst, [ticket("9-2"), ticket("9-3")]) is held


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
def test_later_reply_waits_on_the_analyst_of_an_earlier_reply(tmp_path: Path, pending: bool,
                                                             held: bool) -> None:
    from operations.briefs import held_step
    from operations.roles import Purpose, Role, analyst_subject
    from operations.state import Agent as Launched, Ended, Report, Running, Waits
    from operations.steps import Undecided
    from operations.triage import unfinished
    from tests.test_unreported_agents import ME, state, ticket as filed
    t = filed(tmp_path, "draft", "9-1_change_x_ticket-analyst.md",
              "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
              "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n")
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"
    reply = "Done.\n\n## For the coordinator\n- decision: choose item a\n- unfinished: item a\n"

    def analyst(replies: tuple[float, ...]) -> Launched:
        return Launched("a8e99dabca9ddb4de", ME, Role.TICKET_ANALYST,
                        analyst_subject(Purpose.DRAFT, "9-1"), "", 10.0, 10.0, Ended(),
                        tuple(Report(r, reply) for r in replies), True)

    earlier = unfinished(state(tmp_path, [t], [analyst((100.0,))], w))
    assert isinstance(earlier, Undecided)
    on_earlier = Launched("afea5a8bdac482d84", ME, Role.TICKET_ANALYST,
                          analyst_subject(Purpose.STEP, "k"),
                          held_step(earlier.text, ME, False, None), 150.0, 150.0,
                          Running(Waits.AT_WORK) if pending else Ended(), (), True)
    later = unfinished(state(tmp_path, [t], [analyst((100.0, 200.0)), on_earlier], w))
    assert (later is None) is held
