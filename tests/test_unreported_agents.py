"""An agent that ended with no report since its launch or its last resume
did none of the work it was given: a second ticket reviewer or doc
reviewer so ended holds its review, and an editor so ended holds its
change in place of its merge. The merge of a change closes only its open
`question` tickets."""

from pathlib import Path
from dataclasses import replace

import pytest

from tests.conftest import script
from tests.test_change_overrun import worktree

ME = "a00000000000000f1"
FIRST, SECOND = "a0000000000000001", "a0000000000000002"
CHANGE_LOG = ("## Log\n2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n"
              "2026-10-17T02:23:18Z approved [ticket-reviewer ab225add95550521a]: reviewed\n"
              "2026-10-17T02:23:56Z assigned [operator {me}]: taking: budget 2.43 dollars, "
              "1951 s\n"
              "2026-10-17T02:24:00Z assigned [operator {me}]: worktree {w}\n")


def ticket(tmp_path: Path, status: str, name: str, text: str):
    script("file_ticket")
    path = tmp_path / "tickets" / status / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return script("ticket_reads").held_ticket(path)


def agent(agent_id: str, role, subject: str, brief: str, launched: float, since: float,
          reports: list[float]):
    from operations.state import Agent, Report
    return Agent(agent_id, ME, role, subject, brief, launched, since, None,
                 tuple(Report(r, "done") for r in reports), True)


def state(tmp_path: Path, tickets: list, agents: list, w: Path, commits=()):
    from operations.journal import Journal
    from operations.state import (Computed, GitRead, HeldRead, SessionsRead, Spend, State,
                                  TrackerRead, TranscriptsRead)
    now = max([a.since for a in agents] + [t.last_time for t in tickets]) + 1000
    return State(
        me=ME, now=now, session="s", started=0.0, transcripts_dir=tmp_path,
        main_tree=w.parents[2], scratch=tmp_path, operators=(ME,), open_operators=frozenset(),
        past_bound=False, open_holders=frozenset(), session_holders=frozenset(),
        tracker=TrackerRead({t.number: t for t in tickets}, (), 1),
        transcripts=TranscriptsRead(tuple(agents), (), (), {}, {}, {}, {}, {}, (), {}, {}),
        git=GitRead(tuple(commits), frozenset({w}), {}, {}, {}, frozenset(), {}, None, {}),
        taken_up=frozenset(), held=HeldRead({}, {}),
        sessions=SessionsRead(frozenset(), frozenset(), False, False, None),
        journal=Journal(()), listing=None,
        computed=Computed(spent={t.number: Spend(0.1, 1.0, {"code-editor": 0.1})
                                 for t in tickets}))


def test_two_ticket_reviewers_that_gave_no_report_hold_the_draft(tmp_path: Path) -> None:
    from operations.drafts import draft_step
    from operations.roles import Role
    from operations.steps import Undecided
    t = ticket(tmp_path, "draft", "9-1_change_x_ticket-analyst.md",
               "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
               "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n")
    reviewers = [agent(i, Role.TICKET_REVIEWER, t.number, "", t.last_time + n,
                       t.last_time + n, []) for n, i in ((10, FIRST), (20, SECOND))]
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"
    step = draft_step(state(tmp_path, [t], reviewers, w), t)
    assert isinstance(step, Undecided)


def change(tmp_path: Path, w: Path, editors: str = "code-editor"):
    return ticket(tmp_path, "assigned", "9-1_change_x_ticket-analyst.md",
                  f"---\nkind: change\neditors: {editors}\n---\n# x: y\n\n"
                  + CHANGE_LOG.format(me=ME, w=w))


@pytest.mark.parametrize("resumed", [False, True])
def test_an_unreported_editor_blocks_review_and_merge(tmp_path: Path, resumed: bool) -> None:
    from operations import briefs
    from operations.changes import carry, next_step
    from operations.journal import Close, Entry, Journal, Outcome
    from operations.state import Tool, Waits
    from operations.roles import Role
    from operations.steps import Send, Undecided, analyst_key
    w = worktree(tmp_path)
    (w / "a.txt").write_text("b\n")
    t = change(tmp_path, w)
    launched = t.last_time + 10
    editor = agent(FIRST, Role.CODE_EDITOR, t.number, briefs.WORK_IN.format(worktree=w),
                   launched, launched + 100 if resumed else launched,
                   [launched + 50] if resumed else [])
    initial = state(tmp_path, [t], [editor], w)
    step = next_step(initial, t)
    assert isinstance(step, Send) and step.to == FIRST
    resumed_at = editor.since + 10
    entry = Entry(None, "", step.origin, ME, resumed_at, Tool.SEND_MESSAGE,
                  FIRST, step.message, None, t.number,
                  Close(Outcome.DONE, resumed_at + 1, ""))
    recovery = replace(initial, journal=Journal((entry,)),
                       transcripts=replace(initial.transcripts,
                           agents=(replace(editor, since=resumed_at),)))
    failed = next_step(recovery, t)
    assert isinstance(failed, Undecided) and FIRST in failed.what and str(w) in failed.what
    again = next_step(replace(recovery, now=recovery.now + 100), t)
    assert isinstance(again, Undecided) and analyst_key(again) == analyst_key(failed)
    running = replace(recovery, transcripts=replace(recovery.transcripts,
        agents=(replace(editor, since=resumed_at, waits=Waits.AT_WORK),)))
    assert carry(running, t) is None
    independent = replace(recovery, transcripts=replace(recovery.transcripts,
        agents=(replace(editor, since=resumed_at + 10),)))
    assert isinstance(next_step(independent, t), Send)


def test_two_doc_reviewers_that_gave_no_reply_hold_the_review(tmp_path: Path) -> None:
    from operations import briefs
    from operations.doc_review import doc_review
    from operations.roles import Role
    from operations.steps import Undecided
    w = worktree(tmp_path)
    t = change(tmp_path, w, "doc-editor")
    launched = t.last_time + 10
    editor = agent("a00000000000000e1", Role.DOC_EDITOR, t.number,
                   briefs.WORK_IN.format(worktree=w), launched, launched, [launched + 10])
    line = briefs.fingerprint_line(w)
    reviewers = [agent(i, Role.DOC_REVIEWER, t.number, line, launched + n, launched + n, [])
                 for n, i in ((20, FIRST), (40, SECOND))]
    agents = [editor, *reviewers]
    assert isinstance(doc_review(state(tmp_path, [t], agents, w), t, w, [editor], agents, ME),
                      Undecided)


def test_the_merge_closes_no_question_that_waits(tmp_path: Path) -> None:
    from operations.merging import close
    from operations.state import Commit
    from operations.steps import Bash
    w = worktree(tmp_path)
    t = change(tmp_path, w)
    question = ticket(tmp_path, "waiting", "9-2_change_9-1_code-editor.md",
                      "---\nkind: question\n---\n# x: y?\n\n## Log\n"
                      "2026-10-17T02:30:00Z new [code-editor]: filed\n"
                      "2026-10-17T02:31:00Z waiting [ticket-analyst]: change 9-3\n")
    commit = Commit("h" * 40, t.last_time + 100, frozenset(), t.title, False, frozenset())
    step = close(state(tmp_path, [t, question], [], w, [commit]), t, [])
    assert isinstance(step, Bash) and question.number not in step.command
