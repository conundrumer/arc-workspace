"""An interrupted attempt leaves its work available to another agent."""

from dataclasses import replace
from pathlib import Path

import pytest

from operations.roles import Purpose, Role, analyst_subject
from operations.pacing import Until
from operations.state import Agent, Message, Report, Waits
from operations.steps import Launch, Undecided
from tests.test_own_work import state
from tests.test_unreported_agents import ticket


def attempt(role: Role, subject: str = "9-1", reply: str | None = None,
            pending: bool = False, launched: float = 10.0) -> Agent:
    return Agent("a0000000000000001", "op", role, subject, "", launched, launched,
                 Waits.AT_WORK if pending else None,
                 () if reply is None else (Report(launched + 1, reply),), True)


def with_agents(tmp_path: Path, agents: list[Agent], tickets=()):
    s = state(tmp_path, tickets, messages=(Message("op", 1.0, None, "Op scope: all."),))
    return replace(s, transcripts=replace(s.transcripts, agents=tuple(agents)),
                   computed=replace(s.computed, pace=Until(0.0)))


@pytest.mark.parametrize("status", ["released", "waiting"])
@pytest.mark.parametrize("reply", [None, "## For the coordinator\n- unfinished: resolution",
                                   "Stopped at `scripts/step.py ticket-analyst --stop choose`."])
def test_released_ticket_gets_another_analyst(tmp_path: Path, status: str,
                                             reply: str | None) -> None:
    from operations.triage import given, selected, settle, unsettled_open
    t = ticket(tmp_path, status, "9-1_ticket_x_code-reviewer.md",
               "---\nkind: bug\n---\n# x: fault\n\n## Log\n"
               "2026-10-17T02:00:00Z new [code-reviewer]: filed\n"
               "2026-10-17T02:02:00Z assigned [ticket-analyst a0000000000000001]: taking\n"
               "2026-10-17T02:03:00Z released [operator]: released: holder "
               "a0000000000000001 is not live\n")
    a = attempt(Role.TICKET_ANALYST, analyst_subject(Purpose.TRIAGE, t.number), reply,
                launched=t.filed + 60)
    s = with_agents(tmp_path, [a], [t])
    s = replace(s, computed=replace(s.computed, to_settle=(t.number,)))
    assert not given(s, t.number)
    assert unsettled_open(s) == [t.number]
    assert selected(s) == [t.number]
    assert isinstance(settle(s), Launch)
    for line in ("Op pause.", "Op scope: own."):
        held = replace(s, transcripts=replace(s.transcripts, messages=(
            *s.transcripts.messages, Message("op", 2.0, None, line))))
        assert selected(held) == []
        assert settle(held) is None


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("reply", [None, "## For the coordinator\n- unfinished: work"])
def test_incomplete_role_does_not_satisfy_a_required_launch(
        role: Role, reply: str | None) -> None:
    from operations.change_agents import latest_of_role
    wanted = Launch(role, "9-1", "finish it", occasion="work")
    assert latest_of_role([attempt(role, reply=reply)], role, 0.0, "9-1",
                          lambda: wanted) == wanted


@pytest.mark.parametrize("reply,pending", [(None, True), ("done", False),
    ("## For the coordinator\n- decision: ask the user\n- unfinished: waiting", False)])
def test_running_or_finished_analyst_still_counts(reply: str | None, pending: bool) -> None:
    from operations.change_agents import latest_of_role
    a = attempt(Role.TICKET_ANALYST, reply=reply, pending=pending)
    assert latest_of_role([a], a.role, 0.0, "9-1", lambda: Launch(a.role, a.subject, "retry", occasion="work")) is None


def test_undecided_step_is_available_after_an_interrupted_analyst(tmp_path: Path) -> None:
    from operations.handled import repeated
    from operations.steps import analyst_key
    step = Undecided("work remains")
    a = attempt(Role.TICKET_ANALYST, analyst_subject(Purpose.STEP, analyst_key(step)))
    assert not repeated(step, with_agents(tmp_path, [a]))
    decision = replace(a, reports=(Report(20.0, "## For the coordinator\n- decision: ask"),))
    assert repeated(step, with_agents(tmp_path, [decision]))


def test_stopped_checker_does_not_consume_its_review_round(tmp_path: Path) -> None:
    from operations import briefs
    from operations.item_check import check_round
    t = ticket(tmp_path, "assigned", "9-1_change_x_ticket-analyst.md",
               "---\nkind: change\n---\n# x: fix\n\n## Log\n"
               "2026-10-17T02:00:00Z approved [ticket-reviewer]: reviewed\n")
    agents = [attempt(Role.ITEM_CHECKER, launched=t.last_time + i) for i in (1, 2, 3)]
    assert check_round(with_agents(tmp_path, agents, [t]), t) is briefs.Round.OPEN


def test_interrupted_unbatched_work_does_not_advance_its_window(tmp_path: Path) -> None:
    from operations.occasions import opened
    a = attempt(Role.GATE)
    s = with_agents(tmp_path, [a])
    assert opened(s, [a]) == s.started


def test_stopped_load_check_does_not_cover_its_alert(tmp_path: Path) -> None:
    from operations.load_check import load_check
    a = attempt(Role.LOAD_CHECK, "alert-1")
    s = with_agents(tmp_path, [a])
    s = replace(s, sessions=replace(s.sessions, main=True),
                machine_alerts=(tmp_path / "alert-1.md",))
    assert isinstance(load_check(s), Launch)


def test_stopped_pass_is_not_a_completed_pipeline_stage(tmp_path: Path) -> None:
    from operations.passes import latest
    a = attempt(Role.CREATE, "1234abcd")
    assert latest(with_agents(tmp_path, [a]), a.role, a.subject, 0.0) is None


def test_a_done_launch_entry_does_not_hide_the_retry(tmp_path: Path) -> None:
    from operations.handled import repeated
    from operations.journal import Close, Entry, Journal, Outcome
    from operations.order import place
    from operations.state import Tool
    from operations.steps import digest, key
    a = attempt(Role.LOAD_CHECK, "alert-1")
    launch = Launch(a.role, a.subject, "check", occasion="alert-1")
    entry = Entry(key(launch), digest(launch), launch.origin, "op", 9.0, Tool.AGENT,
                  None, "", None, None, Close(Outcome.DONE, 10.0, ""))
    s = replace(with_agents(tmp_path, [a]), journal=Journal((entry,)))
    assert not repeated(launch, s)
    ready, _, _ = place(s, launch)
    assert isinstance(ready, Launch)
    assert key(ready) != key(launch)
    assert place(s, ready)[0] == ready
    running = replace(s, transcripts=replace(s.transcripts, agents=(
        replace(a, waits=Waits.AT_WORK),)))
    assert repeated(launch, running)


def test_resumed_work_needs_a_fresh_result() -> None:
    from operations.completion import occupies
    a = attempt(Role.ITEM_CHECKER, reply="## Left for a decision\n- none")
    assert occupies(a)
    assert not occupies(replace(a, since=20.0))


def test_checker_findings_are_a_completed_check() -> None:
    from operations.completion import occupies
    a = attempt(Role.ITEM_CHECKER, reply="## Left for a decision\n- item: unfinished: needs a ruling")
    assert occupies(a)


def test_released_ticket_still_waits_on_a_live_analyst_or_returned_decision(tmp_path: Path) -> None:
    from operations.triage import given
    t = ticket(tmp_path, "released", "9-1_ticket_x_code-reviewer.md",
               "---\nkind: bug\n---\n# x: fault\n\n## Log\n"
               "2026-10-17T02:00:00Z new [code-reviewer]: filed\n"
               "2026-10-17T02:03:00Z released [operator]: released: holder "
               "a0000000000000001 is not live\n")
    subject = analyst_subject(Purpose.TRIAGE, t.number)
    for a in (attempt(Role.TICKET_ANALYST, subject, pending=True, launched=t.filed + 60),
              attempt(Role.TICKET_ANALYST, subject, "## For the coordinator\n- decision: ask",
                      launched=t.filed + 60)):
        assert given(with_agents(tmp_path, [a], [t]), t.number)


def test_stopped_fragment_editor_leaves_fragments_due(tmp_path: Path) -> None:
    from operations import briefs
    from operations.change_fragments import fragments_due
    builder = attempt(Role.CODE_EDITOR, reply="done")
    stopped = replace(attempt(Role.DOC_EDITOR), brief=briefs.FRAGMENTS_PART)
    assert fragments_due([builder, stopped])
    from operations.change_agents import unstaffed
    documents = attempt(Role.DOC_EDITOR, reply="done", launched=5.0)
    assert unstaffed((Role.CODE_EDITOR, Role.DOC_EDITOR), [builder, documents, stopped]) == []


def test_stopped_checker_is_replaced_before_a_change_can_merge(tmp_path: Path) -> None:
    from operations.changes import leftover
    t = ticket(tmp_path, "assigned", "9-1_change_x_ticket-analyst.md",
               "---\nkind: change\neditors: code-editor\n---\n# x: fix\n\n## Log\n"
               "2026-10-17T02:00:00Z approved [ticket-reviewer]: reviewed\n")
    editor = attempt(Role.CODE_EDITOR, reply="done", launched=t.last_time + 10)
    checker = attempt(Role.ITEM_CHECKER, launched=t.last_time + 20)
    s = with_agents(tmp_path, [editor, checker], [t])
    step = leftover(s, t, tmp_path, [editor], [editor, checker], False, "op")
    assert isinstance(step, Launch) and step.role is Role.ITEM_CHECKER


def test_stopped_change_analyst_leaves_the_checkers_items_due(tmp_path: Path) -> None:
    from operations.changes import leftover
    t = ticket(tmp_path, "assigned", "9-1_change_x_ticket-analyst.md",
               "---\nkind: change\neditors: code-editor\n---\n# x: fix\n\n## Log\n"
               "2026-10-17T02:00:00Z approved [ticket-reviewer]: reviewed\n")
    editor = attempt(Role.CODE_EDITOR, reply="done", launched=t.last_time + 10)
    checker = attempt(Role.ITEM_CHECKER, reply="## Left for a decision\n- choose a resolution",
                      launched=t.last_time + 20)
    analyst = attempt(Role.TICKET_ANALYST, analyst_subject(Purpose.CHANGE, t.number),
                      launched=t.last_time + 30)
    agents = [editor, checker, analyst]
    s = with_agents(tmp_path, agents, [t])
    step = leftover(s, t, tmp_path, [editor], agents, False, "op")
    assert isinstance(step, Launch) and step.role is Role.TICKET_ANALYST


def test_stopped_after_merge_agent_cannot_close_the_ticket(tmp_path: Path) -> None:
    from operations.merging import close
    from operations.state import Commit
    t = ticket(tmp_path, "assigned", "9-1_change_x_ticket-analyst.md",
               "---\nkind: change\n---\n# x: fix\n\n## Scope\n- After the merge: echo finished.\n\n## Log\n"
               "2026-10-17T02:00:00Z approved [ticket-reviewer]: reviewed\n")
    s = with_agents(tmp_path, [attempt(Role.AFTER_MERGE)], [t])
    s = replace(s, git=replace(s.git, commits=(Commit("a" * 40, 0.0, frozenset(), "fix",
                                                    False, frozenset()),)))
    step = close(s, t, [])
    assert isinstance(step, Launch) and step.role is Role.AFTER_MERGE


def test_stopped_audit_retries_even_after_its_launch_reset_the_spend_window(tmp_path: Path) -> None:
    from operations.cost_audit import audit
    from operations.state import AuditWindow
    s = with_agents(tmp_path, [attempt(Role.COST_AUDIT, "1")])
    s = replace(s, sessions=replace(s.sessions, main=True),
                computed=replace(s.computed, audit_window=AuditWindow(10.0, 0.1)))
    step = audit(s)
    assert isinstance(step, Launch) and step.role is Role.COST_AUDIT


def test_an_incomplete_decision_reply_leaves_the_step_for_a_new_analyst(tmp_path: Path) -> None:
    from operations.decisions import returned
    from operations.handled import repeated
    from operations.steps import analyst_key, held
    step = held("choose", {"again": "retry"})
    a = replace(attempt(Role.TICKET_ANALYST,
                        analyst_subject(Purpose.STEP, analyst_key(step)), "not decided"),
                brief=step.text)
    s = with_agents(tmp_path, [a])
    assert not repeated(step, s)
    assert returned(s) == []


def test_an_interrupted_analyst_report_does_not_replace_retry_with_a_handoff(tmp_path: Path) -> None:
    from operations.triage import unfinished
    a = attempt(Role.TICKET_ANALYST, analyst_subject(Purpose.TRIAGE, "9-1"),
                "## For the coordinator\n- unfinished: resolution")
    assert unfinished(with_agents(tmp_path, [a])) is None


@pytest.mark.parametrize("role", [Role.CODE_REVIEWER, Role.LIB_REVIEWER])
def test_a_review_without_its_baseline_is_due_again(tmp_path: Path, role: Role) -> None:
    from operations.reviews import review
    from operations.state import Baseline, Review
    from operations.steps import key
    of = next(r for r in Review if r.role is role)
    s = with_agents(tmp_path, [])
    s = replace(s, git=replace(s.git, reviews={of: Baseline(1, ("a" * 40,))}))
    first = review(s, of)
    assert isinstance(first, Launch)
    a = attempt(role, first.subject, "stopped before writing the baseline")
    s = replace(s, transcripts=replace(s.transcripts, agents=(a,)))
    again = review(s, of)
    assert isinstance(again, Launch) and key(again) != key(first)


def test_a_solver_fix_without_its_completion_line_is_due_again(tmp_path: Path) -> None:
    from operations.passes import fix_step, fixes, releases
    t = ticket(tmp_path, "closed", "9-1_task_1234abcd_ticket-analyst.md",
               "---\nkind: interference\n---\n# solver: fault\n\n## Log\n"
               "2026-10-18T02:00:00Z new [ticket-analyst]: filed\n"
               "2026-10-18T02:01:00Z closed [ticket-analyst]: wontfix: settled\n")
    a = attempt(Role.SOLVER_FIX, t.number, "done", launched=t.last_time + 10)
    s = with_agents(tmp_path, [a], [t])
    s = replace(s, git=replace(s.git, solvers=frozenset({t.subject}),
                              claims={t.subject: s.session}))
    assert [f.ticket for f in fixes(s)] == [t]
    assert releases(s) == []
    step = fix_step(s)
    assert isinstance(step, Launch) and step.role is Role.SOLVER_FIX


def test_a_standing_review_without_its_tag_is_due_again(tmp_path: Path) -> None:
    from operations import briefs
    from handbook.reader_names import ReaderName
    from operations.standing_reviews import overdue_review, standing_review
    from operations.state import Commit, Deferred, Reader
    reader = Reader(ReaderName.AGENT, ("operator",))
    head = Commit("a" * 40, 100.0, frozenset(), "fix", False, frozenset())
    a = replace(attempt(Role.DOC_REVIEWER, reader.tag, "done"),
                brief=briefs.standing_doc_review("agent operator", reader.tag, head.hash, "op"))
    s = with_agents(tmp_path, [a])
    s = replace(s, sessions=replace(s.sessions, main=True),
                git=replace(s.git, commits=(head,), doc_reviews={}),
                readers=Deferred(lambda: (reader,)))
    assert isinstance(standing_review(s), Launch)
    assert isinstance(overdue_review(s), Launch)
